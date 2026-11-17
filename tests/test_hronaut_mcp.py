import asyncio
import json
import re
import sys
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

import browser_agent_regression.cli as cli_module
import browser_agent_regression.hronaut_mcp as hronaut
from browser_agent_regression.hronaut_mcp import (
    MODEL_TOOLS,
    OBSERVATION_KIND,
    HronautConnection,
    HronautIdentity,
    HronautSetupError,
    ToolResult,
    build_model_tools,
    hronaut_run_identity,
    probe_identity,
    validate_observation,
)
from browser_agent_regression.runner import TASK_CHECKPOINTS, Attempt, build_report, validate_report

TASK = "preferences.notifications.v1"
URL = "http://127.0.0.1:8765/preferences.html?variant=clean"
RESUME_KEY = "resume-key-that-must-never-be-recorded"
API_KEY = "sk-example-secret"
PRODUCT, SECURITY, SAVED = TASK_CHECKPOINTS[TASK]
ALL_PARAMETERS = {
    "workspaceId",
    "tabId",
    "reviewId",
    "action",
    "name",
    "storage",
    "url",
    "active",
    "script",
    "ref",
    "selector",
    "text",
    "submit",
    "fields",
    "value",
    "state",
    "timeoutMs",
}
UPSTREAM = {
    name: {
        "name": name,
        "description": f"{name} description",
        "inputSchema": {
            "type": "object",
            "properties": {parameter: {"type": "string"} for parameter in sorted(ALL_PARAMETERS)},
            "required": ["workspaceId"],
        },
        "annotations": {"readOnlyHint": False},
    }
    for name in (
        "browser_workspaces",
        "browser_new_tab",
        "browser_tabs",
        "browser_evaluate",
        "browser_navigate",
        *MODEL_TOOLS,
    )
}


def text(value) -> ToolResult:
    rendered = value if isinstance(value, str) else json.dumps(value, indent=2, sort_keys=True)
    return ToolResult(is_error=False, text=rendered)


def failure(message: str, status: str | None = None) -> ToolResult:
    return ToolResult(
        is_error=True, text=message, structured={"status": status} if status else None
    )


class FakeHronaut:
    """In-memory stand-in for the Hronaut tools the adapter and the model call."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []
        self.inject: dict[str, list] = {}
        self.observation_filter = None
        self.closed = False
        self.loads = 0
        self.page: dict | None = None

    def load(self, href: str) -> None:
        self.loads += 1
        self.page = {
            "href": href,
            "marker": None,
            "timeOrigin": 1_000.5 + self.loads,
            "missing": set(),
            "product": True,
            "security": False,
            "saved": False,
        }

    def names(self) -> list[str]:
        return [name for name, _arguments in self.calls]

    async def call_tool(self, name: str, arguments: dict, *, timeout: float) -> ToolResult:
        self.calls.append((name, dict(arguments)))
        key = f"{name}:{arguments.get('action')}" if name == "browser_workspaces" else name
        if self.inject.get(key):
            injected = self.inject[key].pop(0)
            if isinstance(injected, Exception):
                raise injected
            return injected
        return getattr(self, f"_{name}")(arguments)

    def _browser_workspaces(self, arguments: dict) -> ToolResult:
        if arguments["action"] == "close":
            self.closed = True
            return text([])
        if arguments["action"] == "claim-ownership":
            return text({"status": "owned"})
        return text(
            {
                "id": "ws-1",
                "activeTabId": None,
                "tabCount": 0,
                "contextClass": "standard",
                "resumeKey": RESUME_KEY,
                "writeLease": {"status": "owned"},
            }
        )

    def _browser_new_tab(self, arguments: dict) -> ToolResult:
        self.load(arguments["url"])
        return text(
            {
                "profilePath": "/home/someone/.config/hronaut",
                "tabs": [
                    {
                        "id": "tab-1",
                        "url": arguments["url"],
                        "workspaceId": "ws-1",
                        "loading": True,
                        "active": True,
                        "documentGeneration": 0,
                    }
                ],
            }
        )

    def _browser_tabs(self, arguments: dict) -> ToolResult:
        if self.page is None:
            return text([])
        return text([{"id": "tab-1", "url": self.page["href"], "workspaceId": "ws-1"}])

    def _browser_evaluate(self, arguments: dict) -> ToolResult:
        assert (arguments["workspaceId"], arguments["tabId"]) == ("ws-1", "tab-1")
        script, page = arguments["script"], self.page
        assert script.lstrip().startswith("(() =>") and script.rstrip().endswith("})()")
        if "defineProperty" in script:
            nonce = re.search(r'value: "([0-9a-f]{32})"', script).group(1)
            if page["marker"] is None and f'location.href === "{page["href"]}"' in script:
                page["marker"] = nonce
            observation = {
                "userAgent": "Mozilla/5.0 hronaut/3.14.33 Chrome/156.0.1 Electron/45.3.0"
            }
        else:
            required = json.loads(re.search(r"const required = (\[.*?\]);", script).group(1))
            nodes = {selector: int(selector not in page["missing"]) for selector in required}
            observation = {
                "requiredNodes": nodes,
                "checkpoints": {
                    PRODUCT: not page["product"],
                    SECURITY: page["security"],
                    SAVED: page["saved"],
                }
                if all(nodes.values())
                else None,
            }
        observation |= {
            "kind": OBSERVATION_KIND,
            "href": page["href"],
            "readyState": "complete",
            "marker": page["marker"],
            "timeOrigin": page["timeOrigin"],
        }
        if self.observation_filter is not None and "defineProperty" not in script:
            observation = self.observation_filter(observation)
        return text(observation)

    def _browser_snapshot(self, arguments: dict) -> ToolResult:
        assert arguments["action"] == "capture"
        return text('[e1] input "" checked\n[e2] input ""\n[e4] button "Save preferences"')

    def _browser_click(self, arguments: dict) -> ToolResult:
        target = arguments.get("ref") or arguments.get("selector")
        if target == "e1":
            self.page["product"] = not self.page["product"]
        elif target == "e2":
            self.page["security"] = not self.page["security"]
        elif target == "e4":
            self.page["saved"] = True
        else:
            return failure(f"No element matches {target}")
        return text("Clicked")


class ScriptedModel:
    """Each step is a list of (tool, arguments) calls, a final string, or an exception."""

    def __init__(self, *steps) -> None:
        self.steps = list(steps)
        self.requests: list[tuple[list, list]] = []

    async def complete(self, messages, tools) -> dict:
        self.requests.append((list(messages), tools))
        step = self.steps.pop(0) if self.steps else "done"
        if callable(step):
            step = await step()
        if isinstance(step, Exception):
            raise step
        if isinstance(step, str):
            return {"content": step, "tool_calls": []}
        return {
            "content": None,
            "tool_calls": [
                {
                    "id": f"call-{len(self.requests)}-{index}",
                    "type": "function",
                    "function": {"name": name, "arguments": json.dumps(arguments)},
                }
                for index, (name, arguments) in enumerate(step)
            ],
        }


def click(ref: str) -> tuple[str, dict]:
    return "browser_click", {"ref": ref}


COMPLETE = ([("browser_snapshot", {})], [click("e1"), click("e2"), click("e4")], "Saved.")
IDENTITY = HronautIdentity(
    protocol_version="2025-11-25",
    server_name="hronaut",
    server_version="3.14.33",
    model_tools=build_model_tools(UPSTREAM),
    upstream_tools={},
    authenticated=False,
)


def connector(fake: FakeHronaut, *, tools=UPSTREAM, server_version="3.14.33", on_exit=None):
    @asynccontextmanager
    async def connect():
        yield HronautConnection(
            session=fake,
            protocol_version="2025-11-25",
            server_name="hronaut",
            server_version=server_version,
            tools=tools,
        )
        if on_exit is not None:
            raise on_exit

    return connect


def run(fake: FakeHronaut, model, *, connect=None, max_steps=12, time_limit=30.0):
    server = SimpleNamespace(
        url=lambda fixture, *, variant: f"http://127.0.0.1:8765/{fixture}?variant={variant}"
    )
    attempt, trace, _browser = asyncio.run(
        hronaut._run_attempt(
            connect or connector(fake),
            model,
            server,
            identity=IDENTITY,
            driver="hronaut-mcp/deepseek-v4-flash",
            task_id=TASK,
            variant="clean",
            index=1,
            max_steps=max_steps,
            time_limit_seconds=time_limit,
            known_secrets=(API_KEY,),
        )
    )
    return attempt, trace


def test_complete_attempt_is_scored_by_the_adapter_before_cleanup() -> None:
    fake, model = FakeHronaut(), ScriptedModel(*COMPLETE)

    attempt, trace = run(fake, model)

    assert attempt.passed is True and attempt.error is None
    assert attempt.checkpoints == dict.fromkeys(TASK_CHECKPOINTS[TASK], True)
    assert list(attempt.checkpoints) == list(TASK_CHECKPOINTS[TASK])
    # A new workspace has no tab: the adapter creates one, binds it, runs the
    # negative control, lets the model act, scores, and only then closes.
    assert fake.names() == [
        "browser_workspaces",
        "browser_new_tab",
        "browser_evaluate",
        "browser_tabs",
        "browser_evaluate",
        "browser_snapshot",
        "browser_click",
        "browser_click",
        "browser_click",
        "browser_tabs",
        "browser_evaluate",
        "browser_workspaces",
    ]
    assert fake.calls[-1][1] == {"action": "close", "workspaceId": "ws-1"}
    assert [event["step"] for event in trace["events"]][-2:] == ["score", "workspace.close"]


def test_model_is_bound_to_the_page_and_never_sees_adapter_tools() -> None:
    fake, model = FakeHronaut(), ScriptedModel(*COMPLETE)

    run(fake, model)

    offered = [tool["function"]["name"] for tool in model.requests[0][1]]
    assert offered == list(MODEL_TOOLS)
    assert not {"browser_evaluate", "browser_workspaces", "browser_navigate"} & set(offered)
    for tool in model.requests[0][1]:
        assert not {"workspaceId", "tabId"} & set(tool["function"]["parameters"]["properties"])
    for name, arguments in fake.calls:
        if name in MODEL_TOOLS:
            assert (arguments["workspaceId"], arguments["tabId"]) == ("ws-1", "tab-1")
    transcript = json.dumps([messages for messages, _tools in model.requests])
    assert OBSERVATION_KIND not in transcript and "checkpoints" not in transcript


def test_no_op_attempt_keeps_three_false_checkpoints() -> None:
    attempt, _trace = run(FakeHronaut(), ScriptedModel("Nothing to do."))

    assert attempt.passed is False and attempt.error is None
    assert attempt.checkpoints == dict.fromkeys(TASK_CHECKPOINTS[TASK], False)
    assert attempt.first_failed_checkpoint == PRODUCT


def test_model_success_message_does_not_change_the_score() -> None:
    attempt, _trace = run(FakeHronaut(), ScriptedModel([click("e1")], "All three are done."))

    assert attempt.passed is False
    assert attempt.checkpoints == {PRODUCT: True, SECURITY: False, SAVED: False}
    assert attempt.first_failed_checkpoint == SECURITY


def test_partial_action_and_model_error_keep_partial_checkpoints() -> None:
    model = ScriptedModel([click("e1")], RuntimeError(f"provider rejected {API_KEY}"))

    attempt, _trace = run(FakeHronaut(), model)

    assert attempt.passed is False
    assert attempt.checkpoints == {PRODUCT: True, SECURITY: False, SAVED: False}
    assert attempt.error.startswith("agent: model request failed")
    assert API_KEY not in attempt.error and "[REDACTED]" in attempt.error


def test_all_checkpoints_true_with_a_runtime_error_still_fails() -> None:
    model = ScriptedModel(COMPLETE[1], RuntimeError("provider unavailable"))

    attempt, _trace = run(FakeHronaut(), model)

    assert all(attempt.checkpoints.values()) and attempt.first_failed_checkpoint is None
    assert attempt.passed is False and "agent:" in attempt.error


def test_reload_at_the_same_url_is_not_scored_as_a_fresh_success() -> None:
    fake = FakeHronaut()

    async def reload_then_finish():
        fake.load(URL)
        fake.page.update(product=False, security=True, saved=True)
        return "Done."

    attempt, _trace = run(fake, ScriptedModel(reload_then_finish))

    assert attempt.passed is False
    assert attempt.checkpoints == dict.fromkeys(TASK_CHECKPOINTS[TASK], False)
    assert "scoring: the original document marker is missing" in attempt.error


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (
            lambda fake: fake.page.update(href=URL.replace("clean", "layout-shift")),
            "exact fixture URL",
        ),
        (
            lambda fake: fake.page.update(href="http://127.0.0.1:8765/checkout.html?variant=clean"),
            "exact fixture URL",
        ),
        (lambda fake: setattr(fake, "page", None), "recorded tab no longer exists"),
        (lambda fake: fake.page.update(timeOrigin=9.0), "time origin changed"),
        (lambda fake: fake.page["missing"].add("#product-updates"), "missing or duplicated"),
        (lambda fake: fake.page["missing"].add('[role="status"]'), "missing or duplicated"),
    ],
)
def test_wrong_lost_or_incomplete_page_is_refused(mutate, message) -> None:
    fake = FakeHronaut()

    async def damage():
        fake.page.update(product=False, security=True, saved=True)
        mutate(fake)
        return "Done."

    attempt, _trace = run(fake, ScriptedModel(damage))

    assert attempt.passed is False
    assert attempt.checkpoints == dict.fromkeys(TASK_CHECKPOINTS[TASK], False)
    assert attempt.error.startswith("scoring:") and message in attempt.error
    assert fake.closed is True


def test_tab_listed_at_another_url_is_refused_even_if_the_page_reads_clean() -> None:
    fake = FakeHronaut()

    async def move_tab():
        fake.page.update(product=False, security=True, saved=True)
        fake.inject["browser_tabs"] = [
            text([{"id": "tab-1", "workspaceId": "ws-1", "url": URL.split("?")[0]}])
        ]
        return "Done."

    attempt, _trace = run(fake, ScriptedModel(move_tab))

    assert attempt.passed is False
    assert "scoring: the recorded tab is no longer at the exact fixture URL" in attempt.error
    assert fake.names()[-2:] == ["browser_tabs", "browser_workspaces"]


def observation(**changes) -> dict:
    base = {
        "kind": OBSERVATION_KIND,
        "href": URL,
        "marker": "nonce",
        "timeOrigin": 12.5,
        "requiredNodes": {"#product-updates": 1, "#security-alerts": 1, '[role="status"]': 1},
        "checkpoints": {SAVED: True, PRODUCT: False, SECURITY: True},
    }
    return base | changes


def validated(value):
    return validate_observation(
        value, task_id=TASK, expected_url=URL, nonce="nonce", time_origin=12.5
    )


def test_observation_restores_declared_checkpoint_order() -> None:
    assert list(validated(observation()).items()) == [
        (PRODUCT, False),
        (SECURITY, True),
        (SAVED, True),
    ]


@pytest.mark.parametrize(
    "value",
    [
        {},  # an uninvoked function serializes to an empty object
        "false",
        None,
        [observation()],
        observation(kind="other"),
        observation(href=URL.replace("clean", "layout-shift")),
        observation(href=URL.split("?")[0]),
        observation(marker=None),
        observation(timeOrigin="12.5"),
        observation(timeOrigin=True),
        observation(requiredNodes={"#product-updates": 1}),
        observation(
            requiredNodes={"#product-updates": 0, "#security-alerts": 1, '[role="status"]': 1}
        ),
        observation(
            requiredNodes={"#product-updates": True, "#security-alerts": 1, '[role="status"]': 1}
        ),
        observation(checkpoints=None),
        observation(checkpoints={PRODUCT: True, SECURITY: True}),
        observation(checkpoints={PRODUCT: True, SECURITY: True, SAVED: True, "extra": True}),
        observation(checkpoints={PRODUCT: "false", SECURITY: True, SAVED: True}),
        observation(checkpoints={PRODUCT: 1, SECURITY: True, SAVED: True}),
        observation(checkpoints={PRODUCT: None, SECURITY: True, SAVED: True}),
    ],
)
def test_invalid_observation_is_rejected(value) -> None:
    with pytest.raises(ValueError):
        validated(value)


@pytest.mark.parametrize("raw", ["{}", "undefined", "false", "not json"])
def test_unwrapped_or_non_json_scoring_result_fails_the_attempt(raw) -> None:
    fake = FakeHronaut()

    async def break_scoring():
        fake.page.update(product=False, security=True, saved=True)
        fake.inject["browser_evaluate"] = [text(raw)]
        return "Done."

    attempt, _trace = run(fake, ScriptedModel(break_scoring))

    assert attempt.passed is False and attempt.error.startswith("scoring:")
    assert attempt.checkpoints == dict.fromkeys(TASK_CHECKPOINTS[TASK], False)


@pytest.mark.parametrize(
    "injected",
    [
        TimeoutError("request timed out"),
        ConnectionError("stream closed"),
        failure("native press may have happened", "OUTCOME_UNKNOWN"),
        failure("click timed out", "TIMED_OUT"),
    ],
)
def test_unknown_action_outcome_is_never_scored(injected) -> None:
    fake = FakeHronaut()
    fake.inject["browser_click"] = [injected]

    attempt, trace = run(fake, ScriptedModel([click("e1")], "unreachable"))

    assert attempt.passed is False
    assert attempt.checkpoints == dict.fromkeys(TASK_CHECKPOINTS[TASK], False)
    assert "agent: browser_click" in attempt.error
    assert "scoring: skipped: a dispatched page action has an unknown outcome" in attempt.error
    # Negative control is the last observation; cleanup still runs.
    assert fake.names()[-2:] == ["browser_click", "browser_workspaces"]
    assert "score" not in [event["step"] for event in trace["events"]]


def test_known_tool_error_is_returned_to_the_model_and_scored() -> None:
    fake = FakeHronaut()
    model = ScriptedModel([click("e9")], [click("e1")], "Done.")

    attempt, _trace = run(fake, model)

    tool_messages = [m for m in model.requests[1][0] if m["role"] == "tool"]
    assert tool_messages[0]["content"].startswith("ERROR: No element matches e9")
    assert attempt.checkpoints[PRODUCT] is True
    assert attempt.error == "agent: browser_click: No element matches e9"


@pytest.mark.parametrize(
    ("call", "problem"),
    [
        (("browser_navigate", {"url": "http://127.0.0.1:8765/"}), "is not available"),
        (("browser_evaluate", {"script": "1"}), "is not available"),
        (("browser_workspaces", {"action": "close"}), "is not available"),
        (("browser_click", {"ref": "e1", "tabId": "other"}), "arguments are not available: tabId"),
        (("browser_click", {"ref": "e1", "workspaceId": "x"}), "arguments are not available"),
        (("browser_click", {"ref": "e1", "native": True}), "arguments are not available: native"),
    ],
)
def test_model_cannot_reach_other_tools_tabs_or_parameters(call, problem) -> None:
    fake = FakeHronaut()
    model = ScriptedModel([call], "Done.")

    attempt, _trace = run(fake, model)

    assert problem in model.requests[1][0][-1]["content"]
    assert not [name for name in fake.names() if name in MODEL_TOOLS or name == "browser_navigate"]
    assert attempt.passed is False


def test_only_three_actions_run_per_step() -> None:
    fake = FakeHronaut()
    model = ScriptedModel([click("e1"), click("e2"), click("e4"), click("e1")], "Done.")

    attempt, _trace = run(fake, model)

    assert fake.names().count("browser_click") == 3
    assert "skipped: at most 3 actions per step" in model.requests[1][0][-1]["content"]
    assert attempt.passed is True


def test_step_limit_keeps_the_observed_partial_state() -> None:
    model = ScriptedModel(*([[("browser_snapshot", {})]] * 5))

    attempt, _trace = run(FakeHronaut(), model, max_steps=2)

    assert len(model.requests) == 2
    assert attempt.passed is False and attempt.error is None


def test_time_limit_during_a_model_turn_scores_the_quiescent_page() -> None:
    async def never():
        await asyncio.sleep(30)

    attempt, _trace = run(FakeHronaut(), ScriptedModel([click("e1")], never), time_limit=0.2)

    assert attempt.error == "agent: time limit of 0.2 s reached"
    assert attempt.checkpoints == {PRODUCT: True, SECURITY: False, SAVED: False}
    assert attempt.passed is False


def test_cleanup_failure_is_recorded_separately_and_fails_the_attempt() -> None:
    fake = FakeHronaut()
    fake.inject["browser_workspaces:close"] = [failure("Workspace is busy")]

    attempt, trace = run(fake, ScriptedModel(*COMPLETE))

    assert all(attempt.checkpoints.values()) and attempt.first_failed_checkpoint is None
    assert attempt.passed is False
    assert attempt.error == "cleanup: workspace close failed: Workspace is busy"
    assert trace["errors"] == {"cleanup": "workspace close failed: Workspace is busy"}


def test_agent_scoring_and_cleanup_errors_are_all_retained() -> None:
    fake = FakeHronaut()
    fake.inject["browser_click"] = [ConnectionError("stream closed " + "x" * 900)]
    fake.inject["browser_workspaces:close"] = [ConnectionError("stream closed")]

    attempt, _trace = run(fake, ScriptedModel([click("e1")]))

    assert len(attempt.error) <= 500
    assert [part.split(":")[0] for part in attempt.error.split("; ")] == [
        "agent",
        "scoring",
        "cleanup",
    ]


def test_connection_teardown_failure_keeps_the_scored_attempt() -> None:
    fake = FakeHronaut()
    connect = connector(fake, on_exit=ConnectionError("session delete failed"))

    attempt, _trace = run(fake, ScriptedModel(*COMPLETE), connect=connect)

    assert all(attempt.checkpoints.values())
    assert attempt.passed is False
    assert attempt.error == "connection: MCP connection: session delete failed"


def test_connection_failure_before_the_attempt_is_retained() -> None:
    @asynccontextmanager
    async def refuse():
        raise ConnectionError("connection refused")
        yield

    attempt, _trace = run(FakeHronaut(), ScriptedModel(), connect=refuse)

    assert attempt.passed is False
    assert attempt.error == "setup: MCP connection: connection refused"
    assert attempt.checkpoints == dict.fromkeys(TASK_CHECKPOINTS[TASK], False)


@pytest.mark.parametrize(
    ("prepare", "message"),
    [
        (
            lambda fake: fake.inject.update({"browser_workspaces:create": [failure("denied")]}),
            "workspace creation failed",
        ),
        (
            lambda fake: fake.inject.update({"browser_new_tab": [text({"tabs": []})]}),
            "exactly one tab",
        ),
        (
            lambda fake: fake.inject.update(
                {
                    "browser_new_tab": [
                        text(
                            {
                                "tabs": [
                                    {
                                        "id": "tab-1",
                                        "workspaceId": "ws-1",
                                        "url": "http://127.0.0.1:8765/preferences.html",
                                    }
                                ]
                            }
                        )
                    ]
                }
            ),
            "exact fixture URL",
        ),
    ],
)
def test_setup_failure_is_retained_without_calling_the_model(prepare, message) -> None:
    fake, model = FakeHronaut(), ScriptedModel(*COMPLETE)
    prepare(fake)

    attempt, _trace = run(fake, model)

    assert model.requests == []
    assert attempt.passed is False and attempt.error.startswith("setup:")
    assert message in attempt.error


def test_stale_fixture_fails_the_negative_control() -> None:
    fake, model = FakeHronaut(), ScriptedModel(*COMPLETE)
    fake.observation_filter = lambda value: (
        value | {"checkpoints": {PRODUCT: True, SECURITY: False, SAVED: False}}
    )

    attempt, _trace = run(fake, model)

    assert model.requests == []
    assert attempt.error == "setup: the fresh fixture was not in its initial state"
    assert attempt.checkpoints == dict.fromkeys(TASK_CHECKPOINTS[TASK], False)
    assert fake.closed is True


def test_changed_server_version_is_a_retained_setup_failure() -> None:
    fake = FakeHronaut()

    attempt, _trace = run(
        fake, ScriptedModel(*COMPLETE), connect=connector(fake, server_version="9.9.9")
    )

    assert attempt.error.startswith("setup: the Hronaut server or MCP version changed")
    assert fake.calls == []


def test_lost_write_lease_is_reclaimed_once_for_scoring() -> None:
    fake = FakeHronaut()

    async def lose_lease():
        fake.page.update(product=False, security=True, saved=True)
        fake.inject["browser_evaluate"] = [failure("lease expired", "LEASE_LOST")]
        return "Done."

    attempt, _trace = run(fake, ScriptedModel(lose_lease))

    assert attempt.passed is True
    assert (
        "browser_workspaces",
        {"action": "claim-ownership", "workspaceId": "ws-1"},
    ) in fake.calls


def test_trace_and_error_never_contain_resume_key_or_local_paths() -> None:
    fake = FakeHronaut()
    fake.inject["browser_workspaces:close"] = [failure(f"cannot close {RESUME_KEY}")]

    attempt, trace = run(fake, ScriptedModel(*COMPLETE))

    rendered = json.dumps([attempt.error, trace])
    assert RESUME_KEY not in rendered and "/home/someone" not in rendered
    assert trace["events"][0]["result"]["resumeKey"] == "<redacted>"
    assert trace["events"][0]["result"]["activeTabId"] is None


@pytest.mark.parametrize(
    "drift",
    [
        lambda tools: tools.pop("browser_click"),
        lambda tools: tools.pop("browser_evaluate"),
        lambda tools: tools["browser_type"]["inputSchema"]["properties"].pop("text"),
    ],
)
def test_tool_schema_drift_is_a_setup_error(drift) -> None:
    tools = json.loads(json.dumps(UPSTREAM))
    drift(tools)

    with pytest.raises(HronautSetupError, match="Hronaut"):
        build_model_tools(tools)


def test_unreachable_server_is_a_setup_error_before_any_attempt() -> None:
    @asynccontextmanager
    async def refuse():
        raise ExceptionGroup("unhandled", [ConnectionError("connection refused")])
        yield

    with pytest.raises(HronautSetupError, match="not usable.*connection refused"):
        asyncio.run(probe_identity(refuse, authenticated=False))


def test_missing_sdk_reports_the_install_command(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "mcp", None)
    connect = hronaut.sdk_connector("http://127.0.0.1:47812/mcp", None)

    with pytest.raises(HronautSetupError, match=r"pip install -e \"\.\[hronaut\]\""):
        asyncio.run(probe_identity(connect, authenticated=False))


def test_sdk_result_is_normalized_once() -> None:
    result = SimpleNamespace(
        content=[SimpleNamespace(type="text", text='{"a": 1}'), SimpleNamespace(type="image")],
        structured_content={"status": "OUTCOME_UNKNOWN"},
        is_error=True,
    )

    normalized = hronaut._normalize_sdk_result(result)

    assert normalized == ToolResult(True, '{"a": 1}', {"status": "OUTCOME_UNKNOWN"})
    assert normalized.status == "OUTCOME_UNKNOWN"
    with pytest.raises(RuntimeError, match="without tool content"):
        hronaut._normalize_sdk_result(SimpleNamespace())


@pytest.mark.parametrize(
    "url",
    ["https://127.0.0.1:47812/mcp", "http://192.168.1.5:47812/mcp", "http://example.test/mcp"],
)
def test_endpoint_must_be_loopback_http(url) -> None:
    with pytest.raises(ValueError, match="loopback"):
        hronaut.require_loopback_url(url)


def test_bearer_credential_comes_from_the_environment_or_a_file(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("HRONAUT_MCP_TOKEN", raising=False)
    monkeypatch.delenv("HRONAUT_MCP_TOKEN_FILE", raising=False)
    assert hronaut.resolve_bearer_credential() is None

    path = tmp_path / "mcp-token"
    path.write_text("file-secret\n", encoding="utf-8")
    monkeypatch.setenv("HRONAUT_MCP_TOKEN_FILE", str(path))
    assert hronaut.resolve_bearer_credential() == "file-secret"

    monkeypatch.setenv("HRONAUT_MCP_TOKEN_FILE", str(tmp_path / "missing"))
    with pytest.raises(HronautSetupError, match="could not be read"):
        hronaut.resolve_bearer_credential()

    monkeypatch.setenv("HRONAUT_MCP_TOKEN", "direct-secret")
    assert hronaut.resolve_bearer_credential() == "direct-secret"


def _identity(monkeypatch, **changes) -> dict:
    monkeypatch.setattr(hronaut, "version", lambda _package: "0.0.0")
    identity = hronaut_run_identity(
        identity=IDENTITY, model="deepseek-v4-flash", max_steps=12, time_limit_seconds=300.0
    )
    return identity | changes


def _report(monkeypatch, *, driver="hronaut-mcp/deepseek-v4-flash", **identity_changes) -> dict:
    attempt = Attempt(
        task_id=TASK,
        driver=driver,
        variant="clean",
        passed=False,
        duration_ms=10.0,
        checkpoints={PRODUCT: True, SECURITY: False, SAVED: False},
        first_failed_checkpoint=SECURITY,
        error=None,
    )
    return build_report(
        [attempt],
        command="hronaut-mcp-deepseek",
        runs=1,
        tasks=[TASK],
        variants=["clean"],
        browser_version="hronaut/3.14.33 Chrome/156.0.1",
        evidence_kind="real-agent",
        run_identity=_identity(monkeypatch, **identity_changes),
    )


def test_run_identity_names_the_negotiated_boundary_without_credentials(monkeypatch) -> None:
    identity = _identity(monkeypatch)

    assert identity["agent"] == "hronaut-mcp"
    assert identity["mcp_protocol_version"] == "2025-11-25"
    assert identity["mcp_server_version"] == "3.14.33"
    assert identity["tools"] == list(MODEL_TOOLS)
    assert identity["tool_schema_sha256"] == IDENTITY.tool_schema_sha256
    assert not {"api_key", "authorization", "token"} & {key.casefold() for key in identity}


def test_report_validator_accepts_a_failed_hronaut_attempt(monkeypatch) -> None:
    report = _report(monkeypatch)

    assert report["evidence_kind"] == "real-agent"
    validate_report(report)


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"agent": "browser-use"}, "identity agent"),
        ({"model": "other"}, "real-agent model"),
        ({"mcp_protocol_version": ""}, "mcp_protocol_version"),
        ({"mcp_server_name": None}, "mcp_server_name"),
        ({"mcp_server_version": 3}, "mcp_server_version"),
    ],
)
def test_report_validator_rejects_an_invalid_hronaut_identity(
    monkeypatch, changes, message
) -> None:
    with pytest.raises(ValueError, match=message):
        validate_report(_report(monkeypatch, **changes))


@pytest.mark.parametrize(
    "driver",
    ["hronaut-mcp/deepseek-v4-pro", "browser-use/deepseek-v4-flash", "reference"],
)
def test_report_validator_binds_the_hronaut_driver_to_command_and_model(
    monkeypatch, driver
) -> None:
    with pytest.raises(ValueError, match="driver.*command"):
        validate_report(_report(monkeypatch, driver=driver))


def test_report_validator_rejects_relabeling_between_real_agent_commands(monkeypatch) -> None:
    report = _report(monkeypatch)
    report["command"] = "deepseek"
    with pytest.raises(ValueError, match="identity agent"):
        validate_report(report)

    report = _report(monkeypatch)
    report["evidence_kind"] = "synthetic-calibration"
    with pytest.raises(ValueError, match="evidence kind.*command"):
        validate_report(report)

    report = _report(monkeypatch)
    report["attempts"].append(dict(report["attempts"][0]))
    with pytest.raises(ValueError, match="attempt coverage mismatch"):
        validate_report(report)


def _patch_cli(monkeypatch, fake: FakeHronaut, model) -> None:
    monkeypatch.setattr(hronaut, "version", lambda _package: "0.0.0")
    monkeypatch.setattr(hronaut, "sdk_connector", lambda _url, _bearer: connector(fake))
    monkeypatch.setattr(hronaut, "DeepSeekChat", lambda **_kwargs: model)
    monkeypatch.delenv("HRONAUT_MCP_TOKEN", raising=False)
    monkeypatch.delenv("HRONAUT_MCP_TOKEN_FILE", raising=False)


def test_cli_writes_a_verifiable_report_and_a_separate_trace(tmp_path, monkeypatch, capsys) -> None:
    fake = FakeHronaut()
    _patch_cli(monkeypatch, fake, ScriptedModel(*COMPLETE))
    monkeypatch.setenv("DEEPSEEK_API_KEY", API_KEY)
    output, trace = tmp_path / "report.json", tmp_path / "trace.json"

    result = cli_module.main(
        [
            "hronaut-mcp-deepseek",
            "--task",
            TASK,
            "--output",
            str(output),
            "--trace-output",
            str(trace),
        ]
    )

    assert result == 0
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["command"] == "hronaut-mcp-deepseek"
    assert report["evidence_kind"] == "real-agent"
    assert report["environment"]["browser"] == "hronaut/3.14.33 Chrome/156.0.1 Electron/45.3.0"
    assert [raw["driver"] for raw in report["attempts"]] == ["hronaut-mcp/deepseek-v4-flash"]
    assert report["configuration"]["run_identity"]["time_limit_seconds"] == 300.0
    assert cli_module.main(["verify", "--report", str(output)]) == 0
    seam = json.loads(trace.read_text(encoding="utf-8"))
    assert seam["artifact"] == "hronaut-mcp-attempt-trace"
    assert seam["mcp"]["protocol_version"] == "2025-11-25"
    rendered = output.read_text(encoding="utf-8") + trace.read_text(encoding="utf-8")
    assert API_KEY not in rendered and RESUME_KEY not in rendered
    assert "1/1 attempts passed independent checks" in capsys.readouterr().out


def test_cli_exits_one_and_keeps_a_failed_attempt(tmp_path, monkeypatch) -> None:
    _patch_cli(monkeypatch, FakeHronaut(), ScriptedModel("Done."))
    monkeypatch.setenv("DEEPSEEK_API_KEY", API_KEY)
    output = tmp_path / "report.json"

    assert cli_module.main(["hronaut-mcp-deepseek", "--task", TASK, "--output", str(output)]) == 1
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["attempts"][0]["first_failed_checkpoint"] == PRODUCT
    validate_report(report)


def test_cli_preflight_needs_no_key_and_writes_no_report(tmp_path, monkeypatch, capsys) -> None:
    fake = FakeHronaut()
    _patch_cli(monkeypatch, fake, None)
    monkeypatch.setattr(
        cli_module,
        "_resolve_deepseek_api_key",
        lambda: (_ for _ in ()).throw(AssertionError("preflight must not resolve an API key")),
    )
    output, trace = tmp_path / "report.json", tmp_path / "trace.json"

    result = cli_module.main(
        [
            "hronaut-mcp-deepseek",
            "--preflight",
            "--task",
            TASK,
            "--output",
            str(output),
            "--trace-output",
            str(trace),
        ]
    )

    assert result == 0 and not output.exists()
    assert json.loads(trace.read_text(encoding="utf-8"))["artifact"] == "seam-preflight"
    assert fake.closed is True and not set(fake.names()) & set(MODEL_TOOLS)
    assert "1/1 pages opened" in capsys.readouterr().out


def test_cli_rejects_a_remote_endpoint_and_an_unreachable_server(monkeypatch, capsys) -> None:
    assert (
        cli_module.main(
            ["hronaut-mcp-deepseek", "--preflight", "--mcp-url", "http://example.test/mcp"]
        )
        == 2
    )
    assert "loopback" in capsys.readouterr().err

    @asynccontextmanager
    async def refuse():
        raise ConnectionError("connection refused")
        yield

    monkeypatch.setattr(hronaut, "sdk_connector", lambda _url, _bearer: refuse)
    assert cli_module.main(["hronaut-mcp-deepseek", "--preflight"]) == 2
    assert "Start Hronaut" in capsys.readouterr().err


def test_cli_defaults_match_the_browser_use_command() -> None:
    args = cli_module.build_parser().parse_args(["hronaut-mcp-deepseek"])

    assert (args.model, args.max_steps, args.runs) == ("deepseek-v4-flash", 12, 1)
    assert args.time_limit == 300.0
    assert args.mcp_url == "http://127.0.0.1:47812/mcp"
    assert args.preflight is False and args.trace_output is None


def sdk_response(*calls, content=None, provider=None) -> SimpleNamespace:
    tool_calls = [
        SimpleNamespace(
            id=f"call-{index}",
            function=SimpleNamespace(name=name, arguments=json.dumps(arguments)),
        )
        for index, (name, arguments) in enumerate(calls)
    ]
    message = SimpleNamespace(content=content, tool_calls=tool_calls or None)
    return SimpleNamespace(provider=provider, choices=[SimpleNamespace(message=message)])


def fake_openai(monkeypatch, *responses) -> SimpleNamespace:
    """Replace the OpenAI SDK module and record how the adapter uses it."""

    seen = SimpleNamespace(clients=[], requests=[], pending=list(responses))

    async def create(**kwargs):
        seen.requests.append(kwargs)
        return seen.pending.pop(0)

    def client(**kwargs):
        seen.clients.append(kwargs)
        return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(AsyncOpenAI=client))
    return seen


def test_default_route_calls_the_deepseek_api_with_thinking_disabled(monkeypatch) -> None:
    seen = fake_openai(monkeypatch, sdk_response(click("e1"), provider=None))
    chat = hronaut.DeepSeekChat(api_key=API_KEY, model="deepseek-v4-flash")

    reply = asyncio.run(chat.complete([{"role": "user", "content": "go"}], IDENTITY.model_tools))

    assert seen.clients == [{"api_key": API_KEY, "base_url": "https://api.deepseek.com"}]
    request = seen.requests[0]
    assert request["model"] == "deepseek-v4-flash"
    assert (request["tool_choice"], request["temperature"]) == ("auto", 0.0)
    assert request["extra_body"] == {"thinking": {"type": "disabled"}}
    assert reply == {
        "content": None,
        "tool_calls": [
            {
                "id": "call-0",
                "type": "function",
                "function": {"name": "browser_click", "arguments": '{"ref": "e1"}'},
            }
        ],
    }
    assert chat.describe() == {
        "provider": "deepseek",
        "model_transport": "DeepSeek chat completions with function calling, tool_choice auto",
        "thinking": "disabled",
    }


def test_openrouter_route_pins_one_upstream_and_records_who_served(monkeypatch) -> None:
    seen = fake_openai(
        monkeypatch,
        sdk_response(click("e1"), provider="DeepInfra"),
        sdk_response(content="Done.", provider="DeepInfra"),
    )
    chat = hronaut.DeepSeekChat(
        api_key=API_KEY, model="deepseek-v4-flash", provider="openrouter", upstream="deepinfra/fp8"
    )

    asyncio.run(chat.complete([], IDENTITY.model_tools))
    final = asyncio.run(chat.complete([], IDENTITY.model_tools))

    assert seen.clients == [{"api_key": API_KEY, "base_url": "https://openrouter.ai/api/v1"}]
    request = seen.requests[0]
    assert request["model"] == "deepseek/deepseek-v4-flash"
    assert request["extra_body"] == {
        "provider": {
            "only": ["deepinfra/fp8"],
            "allow_fallbacks": False,
            "require_parameters": True,
        },
        "reasoning": {"effort": "none"},
    }
    assert final == {"content": "Done.", "tool_calls": []}
    route = chat.describe()
    assert route["provider"] == "openrouter"
    assert route["model_route"] == "deepseek/deepseek-v4-flash"
    assert route["upstream_provider_requested"] == "deepinfra/fp8"
    assert route["upstream_provider_fallbacks"] is False
    assert route["upstream_provider_observed"] == ["DeepInfra"]
    assert "not DeepSeek's own API" in route["model_transport"]
    assert API_KEY not in json.dumps(route)


@pytest.mark.parametrize(
    ("provider", "upstream"),
    [
        ("openrouter", None),
        ("openrouter", ""),
        ("openrouter", "Deep Infra"),
        ("openrouter", "deepinfra,fireworks"),
        ("deepseek", "deepinfra/fp8"),
        ("other", None),
    ],
)
def test_model_route_configuration_is_validated(monkeypatch, provider, upstream) -> None:
    fake_openai(monkeypatch)

    with pytest.raises(HronautSetupError, match="provider"):
        hronaut.DeepSeekChat(
            api_key=API_KEY, model="deepseek-v4-flash", provider=provider, upstream=upstream
        )


def test_cli_openrouter_run_names_its_route_in_the_report(tmp_path, monkeypatch) -> None:
    fake = FakeHronaut()
    monkeypatch.setattr(hronaut, "version", lambda _package: "0.0.0")
    monkeypatch.setattr(hronaut, "sdk_connector", lambda _url, _bearer: connector(fake))
    monkeypatch.delenv("HRONAUT_MCP_TOKEN", raising=False)
    monkeypatch.delenv("HRONAUT_MCP_TOKEN_FILE", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", API_KEY)
    monkeypatch.setattr(
        cli_module,
        "_resolve_deepseek_api_key",
        lambda: (_ for _ in ()).throw(AssertionError("must not ask for a DeepSeek key")),
    )
    seen = fake_openai(
        monkeypatch,
        sdk_response(click("e1"), click("e2"), click("e4"), provider="DeepInfra"),
        sdk_response(content="Saved.", provider="DeepInfra"),
    )
    output = tmp_path / "report.json"

    result = cli_module.main(
        [
            "hronaut-mcp-deepseek",
            "--provider",
            "openrouter",
            "--upstream-provider",
            "deepinfra/fp8",
            "--task",
            TASK,
            "--output",
            str(output),
        ]
    )

    assert result == 0
    assert seen.clients[0]["base_url"] == "https://openrouter.ai/api/v1"
    report = json.loads(output.read_text(encoding="utf-8"))
    identity = report["configuration"]["run_identity"]
    assert identity["model"] == "deepseek-v4-flash"
    assert identity["provider"] == "openrouter"
    assert identity["upstream_provider_requested"] == "deepinfra/fp8"
    assert identity["upstream_provider_observed"] == ["DeepInfra"]
    assert report["attempts"][0]["driver"] == "hronaut-mcp/deepseek-v4-flash"
    assert API_KEY not in output.read_text(encoding="utf-8")
    validate_report(report)


@pytest.mark.parametrize(
    "arguments",
    [["--provider", "openrouter"], ["--upstream-provider", "deepinfra/fp8"]],
)
def test_cli_rejects_an_incomplete_model_route(monkeypatch, capsys, arguments) -> None:
    fake_openai(monkeypatch)
    monkeypatch.setattr(hronaut, "sdk_connector", lambda _url, _bearer: connector(FakeHronaut()))
    monkeypatch.setenv("OPENROUTER_API_KEY", API_KEY)
    monkeypatch.setenv("DEEPSEEK_API_KEY", API_KEY)

    assert cli_module.main(["hronaut-mcp-deepseek", "--task", TASK, *arguments]) == 2
    assert "--upstream-provider" in capsys.readouterr().err
