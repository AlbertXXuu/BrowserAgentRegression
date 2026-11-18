"""Repository-local Hronaut MCP adapter with a DeepSeek model loop.

Hronaut owns the browser. This adapter connects to its loopback Streamable HTTP
MCP endpoint, opens the exact fixture itself, lets the model act only through a
small allowlist of page tools bound to that one tab, and then reads the
checkpoints from the same live document before any cleanup. The model never
sees the scoring call and its final message is ignored for scoring.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import secrets
from collections.abc import AsyncIterator, Callable, Coroutine
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass, field
from hashlib import sha256
from importlib.metadata import version
from pathlib import Path
from time import monotonic, perf_counter
from typing import Any, NamedTuple, Protocol, TypeVar, cast
from urllib.parse import urlsplit

from browser_agent_regression import __version__
from browser_agent_regression.browser_use_deepseek import (
    _CHECKPOINT_SCRIPTS,
    _bounded_message,
    _NonThinkingClient,
    _task_goal,
)
from browser_agent_regression.runner import (
    TASK_CHECKPOINTS,
    TASK_FIXTURES,
    Attempt,
    Driver,
    TaskId,
    Variant,
)
from browser_agent_regression.server import FixtureServer

AGENT = "hronaut-mcp"
COMMAND = "hronaut-mcp-deepseek"
DEFAULT_MCP_URL = "http://127.0.0.1:47812/mcp"
MODEL_PROVIDERS = ("deepseek", "openrouter")
DEFAULT_TIME_LIMIT_SECONDS = 300
TOOL_CALL_TIMEOUT_SECONDS = 60.0
MAX_ACTIONS_PER_STEP = 3
OBSERVATION_KIND = "bar-hronaut-observation/1"

_MARKER_PROPERTY = "__barHronautDocument"
_BIND_TIMEOUT_SECONDS = 10.0
_BIND_POLL_SECONDS = 0.2
_MODEL_RESULT_CHARS = 6_000
_ERROR_CHARS = 500
_REDACTED = "<redacted>"
_T = TypeVar("_T")

# Nodes each checkpoint script reads. All of them exist in the initial fixture
# document (some hidden), so a missing node is a scoring error, never "false".
_REQUIRED_NODES: dict[TaskId, tuple[str, ...]] = {
    "checkout.basic.v1": ("#email", "#shipping", '[role="status"]'),
    "catalog.find-and-save.v1": (
        "#result-status",
        '[aria-label="Product details"]',
        "#detail-name",
        "#saved-status",
    ),
    "preferences.notifications.v1": (
        "#product-updates",
        "#security-alerts",
        '[role="status"]',
    ),
}


@dataclass(frozen=True)
class _ModelTool:
    description: str
    parameters: tuple[str, ...]
    read_only: bool = False
    fixed_arguments: tuple[tuple[str, Any], ...] = ()


# The only Hronaut tools the model can reach. Workspace management, navigation,
# tab management and script evaluation are not exposed; workspaceId and tabId
# are injected by the adapter and cannot be supplied by the model.
MODEL_TOOLS: dict[str, _ModelTool] = {
    "browser_snapshot": _ModelTool(
        "Read the current page as compact text with element refs such as e1.",
        (),
        read_only=True,
        fixed_arguments=(("action", "capture"),),
    ),
    "browser_click": _ModelTool(
        "Click one element by snapshot ref or CSS selector.",
        ("ref", "selector"),
    ),
    "browser_type": _ModelTool(
        "Type text into one field by snapshot ref or CSS selector.",
        ("ref", "selector", "text", "submit"),
    ),
    "browser_fill_form": _ModelTool(
        "Fill several form fields in one call.",
        ("fields",),
    ),
    "browser_select": _ModelTool(
        "Select one option of a select element by value or label.",
        ("ref", "selector", "value"),
    ),
    "browser_wait": _ModelTool(
        "Wait for an element state or for visible text.",
        ("selector", "state", "text", "timeoutMs"),
        read_only=True,
    ),
}

# Tools only the adapter calls.
_ADAPTER_TOOLS = ("browser_workspaces", "browser_new_tab", "browser_tabs", "browser_evaluate")


class HronautSetupError(RuntimeError):
    """The Hronaut connection or tool schema is unusable before any attempt."""


class _StageError(Exception):
    """An adapter-owned step failed in a way the attempt record must retain."""


class _TransportError(_StageError):
    """An adapter-owned call did not return a result at all."""


@dataclass(frozen=True)
class ToolResult:
    """One MCP tool result, normalized once from the SDK wrapper."""

    is_error: bool
    text: str
    structured: dict[str, Any] | None = None

    @property
    def status(self) -> str | None:
        status = (self.structured or {}).get("status")
        return status if isinstance(status, str) else None


class ToolSession(Protocol):
    async def call_tool(
        self, name: str, arguments: dict[str, Any], *, timeout: float
    ) -> ToolResult: ...


class ChatModel(Protocol):
    async def complete(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> dict[str, Any]: ...


@dataclass(frozen=True)
class HronautConnection:
    session: ToolSession
    protocol_version: str
    server_name: str
    server_version: str
    tools: dict[str, dict[str, Any]]


Connector = Callable[[], AbstractAsyncContextManager[HronautConnection]]


@dataclass(frozen=True)
class HronautIdentity:
    protocol_version: str
    server_name: str
    server_version: str
    model_tools: list[dict[str, Any]]
    upstream_tools: dict[str, dict[str, Any]]
    authenticated: bool

    @property
    def tool_schema_sha256(self) -> str:
        return sha256(_canonical(self.model_tools).encode("utf-8")).hexdigest()


@dataclass
class _AttemptRecord:
    task_id: TaskId
    variant: Variant
    checkpoints: dict[str, bool]
    errors: dict[str, str] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)
    secrets: list[str] = field(default_factory=list)
    browser: str | None = None
    # True only once an observation of the original page was accepted as the score.
    scored: bool = False
    cancelled: bool = False

    def fail(self, stage: str, error: BaseException | str) -> None:
        message = _bounded_message(error, secrets=tuple(self.secrets)) or type(error).__name__
        self.errors.setdefault(stage, message)

    def cancel(self, during: str) -> None:
        self.cancelled = True
        self.errors.setdefault("cancelled", f"the run was cancelled during {during}")

    def event(self, step: str, **details: Any) -> None:
        self.events.append({"step": step, **details})

    def error(self) -> str | None:
        if not self.errors:
            return None
        budget = max(40, (_ERROR_CHARS - 12 * len(self.errors)) // len(self.errors))
        parts = [f"{stage}: {message[:budget]}" for stage, message in self.errors.items()]
        return "; ".join(parts)[:_ERROR_CHARS]


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def require_loopback_url(url: str) -> str:
    parts = urlsplit(url)
    if parts.scheme != "http" or parts.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError(
            f"the Hronaut MCP endpoint must be an http:// loopback URL such as {DEFAULT_MCP_URL}"
        )
    return url


def resolve_bearer_credential() -> str | None:
    """Read the optional Hronaut bearer credential without placing it on argv."""

    direct = os.environ.get("HRONAUT_MCP_TOKEN", "").strip()
    if direct:
        return direct
    path = os.environ.get("HRONAUT_MCP_TOKEN_FILE", "").strip()
    if not path:
        return None
    try:
        value = Path(path).expanduser().read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise HronautSetupError(
            f"HRONAUT_MCP_TOKEN_FILE could not be read: {exc.strerror or exc}"
        ) from exc
    if not value:
        raise HronautSetupError("HRONAUT_MCP_TOKEN_FILE is empty.")
    return value


def build_model_tools(upstream: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Project the live Hronaut tool schemas onto the model-facing allowlist.

    A missing tool or parameter is a setup error: schema drift is surfaced
    instead of silently changing what the model can do.
    """

    for name in _ADAPTER_TOOLS:
        if name not in upstream:
            raise HronautSetupError(f"Hronaut does not advertise the required tool {name}.")
    definitions: list[dict[str, Any]] = []
    for name, tool in MODEL_TOOLS.items():
        if name not in upstream:
            raise HronautSetupError(f"Hronaut does not advertise the required tool {name}.")
        schema = upstream[name].get("inputSchema") or {}
        properties = schema.get("properties") or {}
        missing = [parameter for parameter in tool.parameters if parameter not in properties]
        if missing:
            raise HronautSetupError(f"Hronaut tool {name} no longer accepts: {', '.join(missing)}.")
        required = [item for item in schema.get("required") or [] if item in tool.parameters]
        definitions.append(
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": tool.description,
                    "parameters": {
                        "type": "object",
                        "properties": {
                            parameter: properties[parameter] for parameter in tool.parameters
                        },
                        "required": required,
                        "additionalProperties": False,
                    },
                },
            }
        )
    return definitions


def _upstream_evidence(upstream: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    evidence: dict[str, dict[str, Any]] = {}
    for name in (*_ADAPTER_TOOLS, *MODEL_TOOLS):
        tool = upstream[name]
        description = str(tool.get("description") or "")
        evidence[name] = {
            "inputSchema": tool.get("inputSchema"),
            "annotations": tool.get("annotations"),
            "description_sha256": sha256(description.encode("utf-8")).hexdigest(),
        }
    return evidence


def _json_text(result: ToolResult, what: str) -> Any:
    if result.is_error:
        raise _StageError(f"{what} failed: {result.text}")
    try:
        return json.loads(result.text)
    except json.JSONDecodeError as exc:
        raise _StageError(f"{what} did not return JSON.") from exc


def _bind_script(expected_url: str, nonce: str) -> str:
    """Mark the loaded fixture document once; a reload discards the marker."""

    return f"""(() => {{
        const ready = location.href === {json.dumps(expected_url)}
            && document.readyState === "complete";
        if (ready && !Object.prototype.hasOwnProperty.call(window, {json.dumps(_MARKER_PROPERTY)})) {{
            Object.defineProperty(window, {json.dumps(_MARKER_PROPERTY)}, {{
                value: {json.dumps(nonce)},
                enumerable: false, writable: false, configurable: false
            }});
        }}
        const marker = window[{json.dumps(_MARKER_PROPERTY)}];
        return {{
            kind: {json.dumps(OBSERVATION_KIND)},
            href: location.href,
            readyState: document.readyState,
            marker: typeof marker === "string" ? marker : null,
            timeOrigin: performance.timeOrigin,
            userAgent: navigator.userAgent
        }};
    }})()"""


def _observation_script(task_id: TaskId) -> str:
    """Read identity, required nodes and checkpoints in one synchronous call.

    browser_evaluate evaluates an expression, so both this wrapper and the
    existing checkpoint function are invoked explicitly. The checkpoint
    function runs only when every required node is present exactly once.
    """

    required = json.dumps(list(_REQUIRED_NODES[task_id]))
    return f"""(() => {{
        const required = {required};
        const requiredNodes = Object.fromEntries(
            required.map((selector) => [selector, document.querySelectorAll(selector).length])
        );
        const complete = required.every((selector) => requiredNodes[selector] === 1);
        const marker = window[{json.dumps(_MARKER_PROPERTY)}];
        return {{
            kind: {json.dumps(OBSERVATION_KIND)},
            href: location.href,
            readyState: document.readyState,
            marker: typeof marker === "string" ? marker : null,
            timeOrigin: performance.timeOrigin,
            requiredNodes,
            checkpoints: complete ? ({_CHECKPOINT_SCRIPTS[task_id]})() : null
        }};
    }})()"""


def validate_observation(
    observation: Any,
    *,
    task_id: TaskId,
    expected_url: str,
    nonce: str,
    time_origin: float,
) -> dict[str, bool]:
    """Accept checkpoints only from the original fixture document.

    ``expected_url`` is the complete fixture URL including its variant query,
    so a different variant or page is rejected together with a reloaded one.
    """

    if not isinstance(observation, dict) or observation.get("kind") != OBSERVATION_KIND:
        raise ValueError("the page did not return a BAR observation object")
    if observation.get("href") != expected_url:
        raise ValueError("the tab is no longer at the exact fixture URL and variant")
    if observation.get("marker") != nonce:
        raise ValueError("the original document marker is missing; the page was replaced")
    origin = observation.get("timeOrigin")
    if type(origin) not in {int, float} or origin != time_origin:
        raise ValueError("the document time origin changed; the page was replaced")

    expected_nodes = _REQUIRED_NODES[task_id]
    nodes = observation.get("requiredNodes")
    if not isinstance(nodes, dict) or set(nodes) != set(expected_nodes):
        raise ValueError("the observation did not report the required DOM nodes")
    wrong = [
        selector
        for selector in expected_nodes
        if type(nodes[selector]) is not int or nodes[selector] != 1
    ]
    if wrong:
        raise ValueError(f"required DOM nodes are missing or duplicated: {', '.join(wrong)}")

    expected = TASK_CHECKPOINTS[task_id]
    result = observation.get("checkpoints")
    if not isinstance(result, dict) or set(result) != set(expected):
        raise ValueError("the observation returned an unexpected checkpoint set")
    if any(type(result[checkpoint]) is not bool for checkpoint in expected):
        raise ValueError("checkpoint values must be booleans")
    return {checkpoint: result[checkpoint] for checkpoint in expected}


def _absorb_cancellation(record: _AttemptRecord, during: str) -> None:
    """Record a cancellation that the attempt finishes through instead of obeying at once.

    The attempt still reaches a terminal result, with its score, the cancellation
    and cleanup recorded separately. The matrix re-raises once that result is saved.
    """

    record.cancel(during)
    task = asyncio.current_task()
    if task is not None:
        task.uncancel()


async def _uninterrupted(
    record: _AttemptRecord, during: str, work: Coroutine[Any, Any, _T]
) -> _T:
    """Finish adapter-owned scoring or cleanup even if the run is cancelled meanwhile."""

    task = asyncio.ensure_future(work)
    while True:
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            if task.cancelled():
                raise  # The work itself was cancelled, for example by event-loop shutdown.
            _absorb_cancellation(record, during)
            if task.done():
                return task.result()


async def _adapter_call(
    session: ToolSession, record: _AttemptRecord, step: str, name: str, arguments: dict[str, Any]
) -> ToolResult:
    try:
        result = await session.call_tool(name, arguments, timeout=TOOL_CALL_TIMEOUT_SECONDS)
    except Exception as exc:
        record.event(step, tool=name, outcome="transport-error")
        raise _TransportError(f"{name} did not complete: {exc or type(exc).__name__}") from exc
    return result


async def _evaluate(
    session: ToolSession,
    record: _AttemptRecord,
    step: str,
    *,
    workspace_id: str,
    tab_id: str,
    script: str,
) -> Any:
    arguments = {"workspaceId": workspace_id, "tabId": tab_id, "script": script}
    result = await _adapter_call(session, record, step, "browser_evaluate", arguments)
    if result.is_error and result.status == "LEASE_LOST":
        # A lost lease means the call was not dispatched, so one retry is safe.
        claim = {"action": "claim-ownership", "workspaceId": workspace_id}
        await _adapter_call(session, record, f"{step}.claim", "browser_workspaces", claim)
        result = await _adapter_call(session, record, step, "browser_evaluate", arguments)
    return _json_text(result, "browser_evaluate")


async def _create_workspace(session: ToolSession, record: _AttemptRecord, label: str) -> str:
    call = {"action": "create", "name": label, "storage": "scratch"}
    created = await _adapter_call(session, record, "workspace.create", "browser_workspaces", call)
    workspace = _json_text(created, "workspace creation")
    if not isinstance(workspace, dict) or not isinstance(workspace.get("id"), str):
        raise _StageError("workspace creation did not return a workspace id")
    resume_key = workspace.get("resumeKey")
    if isinstance(resume_key, str) and resume_key:
        record.secrets.append(resume_key)
    record.event(
        "workspace.create",
        call=call,
        result={
            "id": workspace["id"],
            "activeTabId": workspace.get("activeTabId"),
            "tabCount": workspace.get("tabCount"),
            "contextClass": workspace.get("contextClass"),
            "writeLease": (workspace.get("writeLease") or {}).get("status"),
            "resumeKey": _REDACTED if resume_key else None,
        },
    )
    return cast(str, workspace["id"])


async def _open_tab(
    session: ToolSession, record: _AttemptRecord, *, workspace_id: str, url: str
) -> str:
    # A new scratch workspace has no tab, so the adapter creates and binds one.
    opened = await _adapter_call(
        session,
        record,
        "tab.create",
        "browser_new_tab",
        {"workspaceId": workspace_id, "url": url, "active": True},
    )
    state = _json_text(opened, "tab creation")
    tabs = state.get("tabs") if isinstance(state, dict) else None
    owned = [
        tab
        for tab in tabs or []
        if isinstance(tab, dict) and tab.get("workspaceId") == workspace_id
    ]
    record.event(
        "tab.create",
        call={"workspaceId": workspace_id, "url": url, "active": True},
        result={"tabs": [_tab_evidence(tab) for tab in owned]},
    )
    if len(owned) != 1 or not isinstance(owned[0].get("id"), str):
        raise _StageError("tab creation did not return exactly one tab in the new workspace")
    if owned[0].get("url") != url:
        raise _StageError(
            "the new tab did not report the exact fixture URL; Hronaut must show full URLs, "
            "including query strings, to this client"
        )
    return cast(str, owned[0]["id"])


def _tab_evidence(tab: dict[str, Any]) -> dict[str, Any]:
    keys = ("id", "url", "loading", "active", "workspaceId", "documentGeneration")
    return {key: tab.get(key) for key in keys}


async def _bind_document(
    session: ToolSession,
    record: _AttemptRecord,
    *,
    workspace_id: str,
    tab_id: str,
    url: str,
    nonce: str,
) -> float:
    deadline = monotonic() + _BIND_TIMEOUT_SECONDS
    last = "it was not complete at the exact URL"
    while True:
        try:
            bound = await _evaluate(
                session,
                record,
                "document.bind",
                workspace_id=workspace_id,
                tab_id=tab_id,
                script=_bind_script(url, nonce),
            )
        except _TransportError:
            raise
        except _StageError as exc:
            # Hronaut rejects a call while the load is still committing; retry until bound.
            bound, last = None, str(exc)
        if isinstance(bound, dict) and bound.get("marker") == nonce:
            break
        if monotonic() >= deadline:
            raise _StageError(f"the fixture document could not be bound: {last}")
        await asyncio.sleep(_BIND_POLL_SECONDS)
    origin = bound.get("timeOrigin")
    if bound.get("href") != url or type(origin) not in {int, float}:
        raise _StageError("the bound document did not report the fixture URL and time origin")
    record.browser = _browser_version(bound.get("userAgent"))
    record.event(
        "document.bind",
        result={key: bound.get(key) for key in ("href", "readyState", "marker", "timeOrigin")},
    )
    return cast(float, origin)


def _browser_version(user_agent: Any) -> str | None:
    if not isinstance(user_agent, str):
        return None
    products = re.findall(r"\b(?:hronaut|Chrome|Electron)/[\w.]+", user_agent)
    return " ".join(products) or None


async def _observe(
    session: ToolSession,
    record: _AttemptRecord,
    step: str,
    *,
    workspace_id: str,
    tab_id: str,
    url: str,
    nonce: str,
    time_origin: float,
) -> dict[str, bool]:
    listed = _json_text(
        await _adapter_call(
            session, record, f"{step}.tabs", "browser_tabs", {"workspaceId": workspace_id}
        ),
        "browser_tabs",
    )
    tab = next(
        (item for item in listed or [] if isinstance(item, dict) and item.get("id") == tab_id),
        None,
    )
    if tab is None:
        raise _StageError("the recorded tab no longer exists in the recorded workspace")
    if tab.get("url") != url:
        raise _StageError("the recorded tab is no longer at the exact fixture URL and variant")
    observation = await _evaluate(
        session,
        record,
        step,
        workspace_id=workspace_id,
        tab_id=tab_id,
        script=_observation_script(record.task_id),
    )
    record.event(step, tab=_tab_evidence(tab), result=observation)
    try:
        return validate_observation(
            observation,
            task_id=record.task_id,
            expected_url=url,
            nonce=nonce,
            time_origin=time_origin,
        )
    except ValueError as exc:
        raise _StageError(str(exc)) from exc


@dataclass
class _LoopOutcome:
    stop_reason: str
    quiescent: bool
    fatal: str | None = None
    agent_errors: list[str] = field(default_factory=list)


def _prompt(task_id: TaskId) -> list[dict[str, Any]]:
    return [
        {
            "role": "system",
            "content": (
                "You control one browser tab through the provided tools. Read the page with "
                "browser_snapshot before acting and after acting. When the goal is complete, "
                "reply with a short final message and no tool call."
            ),
        },
        {
            "role": "user",
            "content": (
                "You are on a controlled local test page. Complete exactly this goal: "
                f"{_task_goal(task_id)} Use only the current tab and do not navigate away. "
                "Finish only after the requested state is visibly confirmed."
            ),
        },
    ]


def _parse_tool_call(call: Any) -> tuple[str, str, dict[str, Any] | None, str | None]:
    function = call.get("function") if isinstance(call, dict) else None
    call_id = str(call.get("id") or "") if isinstance(call, dict) else ""
    name = str((function or {}).get("name") or "")
    tool = MODEL_TOOLS.get(name)
    if tool is None:
        return call_id, name, None, f"tool {name or '(missing)'} is not available"
    try:
        arguments = json.loads((function or {}).get("arguments") or "{}")
    except json.JSONDecodeError:
        return call_id, name, None, "tool arguments were not valid JSON"
    if not isinstance(arguments, dict):
        return call_id, name, None, "tool arguments must be a JSON object"
    unknown = sorted(set(arguments) - set(tool.parameters))
    if unknown:
        return call_id, name, None, f"arguments are not available: {', '.join(unknown)}"
    return call_id, name, arguments, None


async def _model_loop(
    session: ToolSession,
    model: ChatModel,
    record: _AttemptRecord,
    *,
    tools: list[dict[str, Any]],
    workspace_id: str,
    tab_id: str,
    max_steps: int,
    deadline: float,
) -> _LoopOutcome:
    """Run the model until it stops, without cancelling a dispatched action.

    The wall-clock limit is enforced during model turns, before each action and
    after each step, including the last permitted one. A page action that was
    dispatched but did not return a definite result, because of a transport
    failure or a cancellation, leaves the page non-quiescent, and the caller
    must not score it.
    """

    messages = _prompt(record.task_id)
    outcome = _LoopOutcome(stop_reason="max_steps", quiescent=True)
    for step in range(1, max_steps + 1):
        remaining = deadline - monotonic()
        if remaining <= 0:
            outcome.stop_reason = "time_limit"
            return outcome
        try:
            reply = await asyncio.wait_for(model.complete(messages, tools), timeout=remaining)
        except TimeoutError:
            outcome.stop_reason = "time_limit"
            return outcome
        except asyncio.CancelledError:
            # No page action is in flight during a model turn, so the page stays scorable.
            _absorb_cancellation(record, "a model turn")
            outcome.stop_reason = "cancelled"
            return outcome
        except Exception as exc:
            outcome.stop_reason = "model_error"
            outcome.fatal = f"model request failed: {exc or type(exc).__name__}"
            return outcome
        calls = reply.get("tool_calls") or []
        messages.append(
            {
                "role": "assistant",
                "content": reply.get("content"),
                **({"tool_calls": calls} if calls else {}),
            }
        )
        if not calls:
            record.event("model.step", index=step, tools=[])
            outcome.stop_reason = "final_answer"
            return outcome

        executed: list[dict[str, Any]] = []
        out_of_time = False
        for position, call in enumerate(calls):
            call_id, name, arguments, problem = _parse_tool_call(call)
            if problem is not None:
                outcome.agent_errors.append(f"{name or 'tool'}: {problem}")
            elif position >= MAX_ACTIONS_PER_STEP:
                problem = f"skipped: at most {MAX_ACTIONS_PER_STEP} actions per step"
            elif out_of_time or deadline - monotonic() <= 0:
                out_of_time = True
                problem = "not dispatched: the time limit was reached"
            if problem is not None or arguments is None:
                executed.append({"tool": name, "dispatched": False})
                messages.append(
                    {"role": "tool", "tool_call_id": call_id, "content": f"ERROR: {problem}"}
                )
                continue

            tool = MODEL_TOOLS[name]
            bound = {
                **arguments,
                **dict(tool.fixed_arguments),
                "workspaceId": workspace_id,
                "tabId": tab_id,
            }
            try:
                result = await session.call_tool(name, bound, timeout=TOOL_CALL_TIMEOUT_SECONDS)
            except asyncio.CancelledError:
                _absorb_cancellation(record, name)
                executed.append({"tool": name, "arguments": arguments, "outcome": "unknown"})
                record.event("model.step", index=step, tools=executed)
                outcome.stop_reason = "cancelled"
                outcome.quiescent = tool.read_only
                return outcome
            except Exception as exc:
                executed.append({"tool": name, "arguments": arguments, "outcome": "unknown"})
                record.event("model.step", index=step, tools=executed)
                outcome.stop_reason = "transport_error"
                outcome.quiescent = tool.read_only
                outcome.fatal = f"{name} did not complete: {exc or type(exc).__name__}"
                return outcome
            executed.append(
                {
                    "tool": name,
                    "arguments": arguments,
                    "is_error": result.is_error,
                    **({"status": result.status} if result.status else {}),
                }
            )
            unknown = result.status in {"OUTCOME_UNKNOWN", "TIMED_OUT"}
            if result.is_error and unknown and not tool.read_only:
                record.event("model.step", index=step, tools=executed)
                outcome.stop_reason = "action_outcome_unknown"
                outcome.quiescent = False
                outcome.fatal = f"{name} reported {result.status}"
                return outcome
            if result.is_error:
                outcome.agent_errors.append(f"{name}: {result.text}")
            text = result.text[:_MODEL_RESULT_CHARS]
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call_id,
                    "content": f"ERROR: {text}" if result.is_error else text,
                }
            )
        record.event("model.step", index=step, tools=executed)
        # Every dispatched action has a definite outcome here. An action that began
        # before the deadline and ended after it exceeds the limit on any step,
        # including the last permitted one.
        if out_of_time or monotonic() >= deadline:
            outcome.stop_reason = "time_limit"
            return outcome
    return outcome


async def _drive(
    connection: HronautConnection,
    model: ChatModel | None,
    record: _AttemptRecord,
    *,
    identity: HronautIdentity,
    url: str,
    label: str,
    max_steps: int,
    time_limit_seconds: float,
) -> None:
    """Open, control, score and clean up one attempt on an open connection."""

    session = connection.session
    workspace_id: str | None = None
    try:
        negotiated = (
            connection.protocol_version,
            connection.server_name,
            connection.server_version,
        )
        declared = (identity.protocol_version, identity.server_name, identity.server_version)
        if negotiated != declared:
            raise _StageError("the Hronaut server or MCP version changed during the run")
        if build_model_tools(connection.tools) != identity.model_tools:
            raise _StageError("the Hronaut tool schema changed during the run")

        workspace_id = await _create_workspace(session, record, label)
        tab_id = await _open_tab(session, record, workspace_id=workspace_id, url=url)
        nonce = secrets.token_hex(16)
        page: dict[str, Any] = {
            "workspace_id": workspace_id,
            "tab_id": tab_id,
            "url": url,
            "nonce": nonce,
            "time_origin": await _bind_document(
                session, record, workspace_id=workspace_id, tab_id=tab_id, url=url, nonce=nonce
            ),
        }
        # Plumbing control: a fresh page must read all-false through the same observer.
        if any((await _observe(session, record, "negative-control", **page)).values()):
            raise _StageError("the fresh fixture was not in its initial state")
        if model is not None:
            await _control_and_score(
                session,
                model,
                record,
                tools=identity.model_tools,
                page=page,
                max_steps=max_steps,
                time_limit_seconds=time_limit_seconds,
            )
    except (_StageError, HronautSetupError) as exc:
        record.fail("setup", exc)
    except asyncio.CancelledError:
        # The model loop and scoring absorb their own cancellations, so this is setup.
        _absorb_cancellation(record, "setup")
        if workspace_id is None:
            record.fail(
                "cleanup",
                "skipped: workspace creation was interrupted, so there is no workspace id "
                "to close",
            )
    finally:
        if workspace_id is not None:
            await _cleanup(session, record, workspace_id)


async def _control_and_score(
    session: ToolSession,
    model: ChatModel,
    record: _AttemptRecord,
    *,
    tools: list[dict[str, Any]],
    page: dict[str, Any],
    max_steps: int,
    time_limit_seconds: float,
) -> None:
    try:
        outcome = await _model_loop(
            session,
            model,
            record,
            tools=tools,
            workspace_id=page["workspace_id"],
            tab_id=page["tab_id"],
            max_steps=max_steps,
            deadline=monotonic() + time_limit_seconds,
        )
    except Exception as exc:  # Unknown loop state: retain the failure and do not score.
        record.fail("agent", f"model loop failed: {exc or type(exc).__name__}")
        record.fail("scoring", "skipped: the page state after the failure is unknown")
        return
    record.event("model.stop", reason=outcome.stop_reason, quiescent=outcome.quiescent)
    if outcome.stop_reason == "time_limit":
        record.fail("agent", f"time limit of {time_limit_seconds:g} s reached")
    elif outcome.fatal is not None:
        record.fail("agent", outcome.fatal)

    if not outcome.quiescent:
        record.fail("scoring", "skipped: a dispatched page action has an unknown outcome")
        return
    try:
        record.checkpoints = await _uninterrupted(
            record, "scoring", _observe(session, record, "score", **page)
        )
    except _StageError as exc:
        record.fail("scoring", exc)
        return
    except asyncio.CancelledError:
        _absorb_cancellation(record, "scoring")
        record.fail("scoring", "interrupted before an observation was accepted")
        return
    record.scored = True
    if not all(record.checkpoints.values()) and outcome.agent_errors:
        record.fail("agent", outcome.agent_errors[-1])


async def _close_workspace(session: ToolSession, record: _AttemptRecord, workspace_id: str) -> None:
    """Close only the workspace this attempt created; keep any failure."""

    arguments = {"action": "close", "workspaceId": workspace_id}
    try:
        closed = await session.call_tool(
            "browser_workspaces", arguments, timeout=TOOL_CALL_TIMEOUT_SECONDS
        )
    except Exception as exc:
        record.event("workspace.close", call=arguments, outcome="transport-error")
        record.fail("cleanup", f"workspace close did not complete: {exc or type(exc).__name__}")
        return
    record.event(
        "workspace.close",
        call=arguments,
        result={"is_error": closed.is_error, "text": closed.text[:200]},
    )
    if closed.is_error:
        record.fail("cleanup", f"workspace close failed: {closed.text}")


async def _cleanup(session: ToolSession, record: _AttemptRecord, workspace_id: str) -> None:
    """Close the workspace to completion; a cancellation is recorded, not obeyed."""

    try:
        await _uninterrupted(
            record, "cleanup", _close_workspace(session, record, workspace_id)
        )
    except asyncio.CancelledError:
        _absorb_cancellation(record, "cleanup")
        record.fail("cleanup", "workspace close was interrupted; its outcome is unknown")


class _Terminal(NamedTuple):
    """The terminal result of one attempt; ``cancelled`` asks the matrix to stop."""

    attempt: Attempt
    trace: dict[str, Any]
    browser: str | None
    cancelled: bool


async def _run_attempt(
    connect: Connector,
    model: ChatModel | None,
    server: FixtureServer,
    *,
    identity: HronautIdentity,
    driver: Driver,
    task_id: TaskId,
    variant: Variant,
    index: int,
    max_steps: int,
    time_limit_seconds: float,
    known_secrets: tuple[str, ...],
) -> _Terminal:
    """Run one declared attempt and always return its record, also when cancelled."""

    record = _AttemptRecord(
        task_id=task_id,
        variant=variant,
        checkpoints=dict.fromkeys(TASK_CHECKPOINTS[task_id], False),
        secrets=[secret for secret in known_secrets if secret],
    )
    url = server.url(TASK_FIXTURES[task_id], variant=variant)
    started = perf_counter()
    entered = False
    try:
        async with connect() as connection:
            entered = True
            await _drive(
                connection,
                model,
                record,
                identity=identity,
                url=url,
                label=f"bar {task_id} {variant} {index}",
                max_steps=max_steps,
                time_limit_seconds=time_limit_seconds,
            )
    except asyncio.CancelledError:
        _absorb_cancellation(record, "the MCP connection")
    except Exception as exc:  # The report must retain connection and teardown failures.
        record.fail("connection" if entered else "setup", f"MCP connection: {_root_cause(exc)}")
    duration_ms = round((perf_counter() - started) * 1_000, 3)
    # Without an accepted score the checkpoints are placeholders, not observed
    # failures, so the attempt names no first-failure checkpoint.
    first_failed = (
        next((name for name, passed in record.checkpoints.items() if not passed), None)
        if record.scored
        else None
    )
    error = record.error()
    attempt = Attempt(
        task_id=task_id,
        driver=driver,
        variant=variant,
        passed=record.scored and first_failed is None and error is None,
        duration_ms=duration_ms,
        checkpoints=record.checkpoints,
        first_failed_checkpoint=first_failed,
        error=error,
        scored=record.scored,
    )
    trace = {
        "task_id": task_id,
        "variant": variant,
        "fixture_url": url,
        "scored": record.scored,
        "cancelled": record.cancelled,
        "errors": dict(record.errors),
        "events": record.events,
    }
    return _Terminal(attempt, _redact(trace, tuple(record.secrets)), record.browser, record.cancelled)


def _redact(value: Any, known_secrets: tuple[str, ...]) -> Any:
    if isinstance(value, dict):
        return {key: _redact(item, known_secrets) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact(item, known_secrets) for item in value]
    if isinstance(value, str):
        for secret in known_secrets:
            if secret:
                value = value.replace(secret, _REDACTED)
    return value


def _normalize_sdk_result(result: Any) -> ToolResult:
    content = getattr(result, "content", None)
    if content is None:
        raise RuntimeError("Hronaut returned a result without tool content.")
    texts = [item.text for item in content if getattr(item, "type", None) == "text"]
    structured = getattr(result, "structured_content", None)
    return ToolResult(
        is_error=bool(getattr(result, "is_error", False)),
        text="\n".join(texts),
        structured=structured if isinstance(structured, dict) else None,
    )


class _SdkSession:
    def __init__(self, session: Any) -> None:
        self._session = session

    async def call_tool(
        self, name: str, arguments: dict[str, Any], *, timeout: float
    ) -> ToolResult:
        result = await asyncio.wait_for(
            self._session.call_tool(name, arguments, read_timeout_seconds=timeout),
            timeout=timeout + 5,
        )
        return _normalize_sdk_result(result)


def sdk_connector(url: str, bearer: str | None) -> Connector:
    """Connect with the official Python MCP SDK over Streamable HTTP."""

    @asynccontextmanager
    async def connect() -> AsyncIterator[HronautConnection]:
        try:
            from mcp import ClientSession
            from mcp.client.streamable_http import (
                create_mcp_http_client,
                streamable_http_client,
            )
            from mcp.types import Implementation
        except ImportError as exc:
            raise HronautSetupError(
                'The MCP SDK is not installed. Run: python -m pip install -e ".[hronaut]"'
            ) from exc

        headers = {"Authorization": f"Bearer {bearer}"} if bearer else None
        async with (
            create_mcp_http_client(headers=headers) as http_client,
            streamable_http_client(url, http_client=http_client) as streams,
            ClientSession(
                streams[0],
                streams[1],
                client_info=Implementation(name="browser-agent-regression", version=__version__),
            ) as session,
        ):
            initialized = await session.initialize()
            listed = await session.list_tools()
            tools = {
                tool.name: tool.model_dump(by_alias=True, exclude_none=True)
                for tool in listed.tools
            }
            yield HronautConnection(
                session=_SdkSession(session),
                protocol_version=str(initialized.protocol_version),
                server_name=initialized.server_info.name,
                server_version=initialized.server_info.version,
                tools=tools,
            )

    return connect


async def probe_identity(connect: Connector, *, authenticated: bool) -> HronautIdentity:
    """Negotiate once before the matrix; an unreachable server is a setup error."""

    try:
        async with connect() as connection:
            return HronautIdentity(
                protocol_version=connection.protocol_version,
                server_name=connection.server_name,
                server_version=connection.server_version,
                model_tools=build_model_tools(connection.tools),
                upstream_tools=_upstream_evidence(connection.tools),
                authenticated=authenticated,
            )
    except HronautSetupError:
        raise
    except Exception as exc:
        raise HronautSetupError(
            "Hronaut's MCP endpoint is not usable. Start Hronaut, and if MCP authentication "
            "is enabled set HRONAUT_MCP_TOKEN_FILE to the profile's mcp-token file. "
            f"({_bounded_message(_root_cause(exc))[:200]})"
        ) from exc


def _root_cause(error: BaseException) -> BaseException:
    while isinstance(error, BaseExceptionGroup) and error.exceptions:
        error = error.exceptions[0]
    return error


class DeepSeekChat:
    """A DeepSeek model through chat completions with function calling, thinking disabled.

    ``provider="deepseek"`` calls DeepSeek's own API. ``provider="openrouter"`` requests the
    same model id through OpenRouter, restricted to one named upstream host with fallbacks
    off. OpenRouter serves these models from third-party hosts, so that route is recorded in
    the run identity and is not the same serving stack as DeepSeek's API.
    """

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        provider: str = "deepseek",
        upstream: str | None = None,
    ) -> None:
        if provider not in MODEL_PROVIDERS:
            raise HronautSetupError(f"unknown model provider: {provider}")
        if provider == "openrouter" and not re.fullmatch(r"[a-z0-9][a-z0-9/._-]*", upstream or ""):
            raise HronautSetupError(
                "--provider openrouter needs --upstream-provider with one OpenRouter provider "
                "slug, such as deepinfra/fp8."
            )
        if provider == "deepseek" and upstream is not None:
            raise HronautSetupError("--upstream-provider applies only to --provider openrouter.")
        try:
            from openai import AsyncOpenAI
        except ImportError as exc:
            raise HronautSetupError(
                'The OpenAI SDK is not installed. Run: python -m pip install -e ".[hronaut]"'
            ) from exc
        self.provider = provider
        self.upstream = upstream
        self.upstream_observed: list[str] = []
        self._request: dict[str, Any]
        if provider == "openrouter":
            self._client = AsyncOpenAI(api_key=api_key, base_url="https://openrouter.ai/api/v1")
            self._request = {
                "model": f"deepseek/{model}",
                "extra_body": {
                    "provider": {
                        "only": [upstream],
                        "allow_fallbacks": False,
                        "require_parameters": True,
                    },
                    "reasoning": {"effort": "none"},
                },
            }
        else:
            self._client = _NonThinkingClient(
                AsyncOpenAI(api_key=api_key, base_url="https://api.deepseek.com")
            )
            self._request = {"model": model}

    def describe(self) -> dict[str, object]:
        """Name the model route for the run identity; never includes the key."""

        if self.provider == "deepseek":
            return _DEEPSEEK_ROUTE
        return {
            "provider": "openrouter",
            "model_route": self._request["model"],
            "model_transport": (
                "OpenRouter chat completions with function calling, tool_choice auto; a "
                "third-party host of the model, not DeepSeek's own API"
            ),
            "upstream_provider_requested": self.upstream,
            "upstream_provider_fallbacks": False,
            "upstream_provider_observed": list(self.upstream_observed),
            "thinking": "disabled (reasoning effort none)",
        }

    async def complete(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> dict[str, Any]:
        response = await self._client.chat.completions.create(
            messages=messages,
            tools=tools,
            tool_choice="auto",
            temperature=0.0,
            **self._request,
        )
        served = getattr(response, "provider", None)
        if isinstance(served, str) and served and served not in self.upstream_observed:
            self.upstream_observed.append(served)
        message = response.choices[0].message
        return {
            "content": message.content,
            "tool_calls": [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {
                        "name": call.function.name,
                        "arguments": call.function.arguments,
                    },
                }
                for call in message.tool_calls or []
            ],
        }


Persist = Callable[[list[Attempt], dict[str, Any], str | None], None]


@dataclass
class _Cell:
    """One declared attempt, registered before any attempt is scheduled."""

    task_id: TaskId
    variant: Variant
    index: int
    attempt: Attempt
    trace: dict[str, Any]
    terminal: bool = False

    def close(self, attempt: Attempt, trace: dict[str, Any]) -> None:
        self.attempt, self.trace, self.terminal = attempt, trace, True


def _unstarted(
    driver: Driver, task_id: TaskId, variant: Variant, stage: str, message: str
) -> tuple[Attempt, dict[str, Any]]:
    """A retained record for a declared attempt that produced no result of its own."""

    attempt = Attempt(
        task_id=task_id,
        driver=driver,
        variant=variant,
        passed=False,
        duration_ms=0.0,
        checkpoints=dict.fromkeys(TASK_CHECKPOINTS[task_id], False),
        first_failed_checkpoint=None,
        error=f"{stage}: {message}",
        scored=False,
    )
    trace = {
        "task_id": task_id,
        "variant": variant,
        "fixture_url": None,
        "scored": False,
        "cancelled": stage == "cancelled",
        "errors": {stage: message},
        "events": [],
    }
    return attempt, trace


async def _settle(worker: asyncio.Future[_Terminal]) -> bool:
    """Wait until the attempt worker is terminal; return whether the run was cancelled.

    The first cancellation is forwarded to the worker, which records it and still
    scores a quiescent page and cleans up. Later ones are absorbed, so a repeated
    cancellation cannot interrupt cleanup. The caller re-raises after saving.
    """

    cancelled = False
    while not worker.done():
        try:
            await asyncio.shield(worker)
        except asyncio.CancelledError:
            if not cancelled and not worker.done():
                worker.cancel()
            cancelled = True
        except Exception:  # Read below from the finished worker.
            break
    return cancelled


async def run_hronaut_matrix(
    *,
    connect: Connector,
    model_client: ChatModel | None,
    model: str,
    identity: HronautIdentity,
    tasks: list[TaskId],
    variants: list[Variant],
    runs: int,
    max_steps: int,
    time_limit_seconds: float,
    known_secrets: tuple[str, ...] = (),
    persist: Persist | None = None,
) -> tuple[list[Attempt], dict[str, Any], str | None]:
    """Run every declared cell. ``model_client=None`` is the key-free preflight.

    Every declared attempt is registered first, and ``persist`` receives the whole
    matrix before the first attempt and after each terminal result. A cancelled run
    therefore keeps its finished attempts, records the interrupted and the unstarted
    ones as cancelled, saves, and only then propagates the cancellation.
    """

    driver = cast(Driver, f"{AGENT}/{model}")
    cells = [
        _Cell(
            task_id,
            variant,
            index,
            *_unstarted(
                driver,
                task_id,
                variant,
                "not completed",
                "the run ended before this attempt reached a terminal result",
            ),
        )
        for task_id in tasks
        for variant in variants
        for index in range(1, runs + 1)
    ]
    browser: str | None = None
    cancelled = False
    current = asyncio.current_task()

    def snapshot() -> tuple[list[Attempt], dict[str, Any], str | None]:
        trace_document = {
            "artifact": "seam-preflight" if model_client is None else "hronaut-mcp-attempt-trace",
            "note": "Sanitized adapter-owned MCP calls. This is not a BAR evidence report.",
            "mcp": {
                "protocol_version": identity.protocol_version,
                "server_name": identity.server_name,
                "server_version": identity.server_version,
                "client": f"mcp {version('mcp')} (Python SDK, Streamable HTTP)",
                "authenticated": identity.authenticated,
            },
            "browser": browser,
            "cancelled": cancelled,
            "model_tools": identity.model_tools,
            "model_tool_schema_sha256": identity.tool_schema_sha256,
            "upstream_tools": identity.upstream_tools,
            "attempts": [cell.trace for cell in cells],
        }
        return [cell.attempt for cell in cells], _redact(trace_document, known_secrets), browser

    def save() -> None:
        if persist is not None:
            persist(*snapshot())

    save()  # The registered matrix: an unwritable output fails before any paid request.
    with FixtureServer() as server:
        for cell in cells:
            worker = asyncio.ensure_future(
                _run_attempt(
                    connect,
                    model_client,
                    server,
                    identity=identity,
                    driver=driver,
                    task_id=cell.task_id,
                    variant=cell.variant,
                    index=cell.index,
                    max_steps=max_steps,
                    time_limit_seconds=time_limit_seconds,
                    known_secrets=known_secrets,
                )
            )
            if current is not None and current.cancelling():
                # Cancelled between attempts: stop this worker before it starts.
                worker.cancel()
            cancelled = await _settle(worker)
            if worker.cancelled():
                # Cancelled before the worker ran: only the registered record exists.
                cell.close(
                    *_unstarted(
                        driver,
                        cell.task_id,
                        cell.variant,
                        "cancelled",
                        "the run was cancelled before this attempt started",
                    )
                )
            elif (unexpected := worker.exception()) is not None:
                cell.close(
                    *_unstarted(
                        driver,
                        cell.task_id,
                        cell.variant,
                        "adapter",
                        f"unexpected failure: {_bounded_message(unexpected)[:200]}",
                    )
                )
            else:
                result = worker.result()
                cell.close(result.attempt, result.trace)
                browser = browser or result.browser
                cancelled = cancelled or result.cancelled
            if cancelled:
                break
            save()
    if cancelled:
        for cell in cells:
            if not cell.terminal:
                cell.close(
                    *_unstarted(
                        driver,
                        cell.task_id,
                        cell.variant,
                        "cancelled",
                        "the run was cancelled before this attempt started",
                    )
                )
        save()
        raise asyncio.CancelledError
    return snapshot()


_DEEPSEEK_ROUTE: dict[str, object] = {
    "provider": "deepseek",
    "model_transport": "DeepSeek chat completions with function calling, tool_choice auto",
    "thinking": "disabled",
}


def hronaut_run_identity(
    *,
    identity: HronautIdentity,
    model: str,
    max_steps: int,
    time_limit_seconds: float,
    model_route: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "agent": AGENT,
        "agent_version": identity.server_version,
        "mcp_server_name": identity.server_name,
        "mcp_server_version": identity.server_version,
        "mcp_protocol_version": identity.protocol_version,
        "mcp_client": "mcp (official Python SDK)",
        "mcp_client_version": version("mcp"),
        "mcp_transport": "Streamable HTTP on loopback",
        "mcp_authentication": (
            "bearer credential from the local environment"
            if identity.authenticated
            else "none; the server accepted an unauthenticated loopback client"
        ),
        "model": model,
        **(model_route or _DEEPSEEK_ROUTE),
        "model_client_version": version("openai"),
        "temperature": 0.0,
        "max_steps": max_steps,
        "max_actions_per_step": MAX_ACTIONS_PER_STEP,
        "time_limit_seconds": time_limit_seconds,
        "tool_call_timeout_seconds": TOOL_CALL_TIMEOUT_SECONDS,
        "prompt_strategy": "manifest goal with current-tab and visible-confirmation constraints",
        "tools": list(MODEL_TOOLS),
        "tool_schema_sha256": identity.tool_schema_sha256,
        "browser_owner": "Hronaut desktop app, already running; not launched by BAR",
        "page_binding": (
            "adapter-created scratch workspace and tab; workspaceId and tabId injected by "
            "the adapter"
        ),
        "document_identity": (
            "adapter nonce on the original document, performance.timeOrigin and the exact "
            "fixture URL"
        ),
        "scoring": (
            "adapter-owned browser_evaluate on the recorded tab before cleanup; model output "
            "ignored; skipped while a dispatched action has an unknown outcome; each attempt "
            "records whether a score was accepted"
        ),
        "reset_policy": (
            "fresh scratch workspace and tab per attempt; negative control before the first "
            "model turn"
        ),
        "cleanup": (
            "workspace closed after scoring, also when the run is cancelled; cleanup errors "
            "are retained"
        ),
        "reconnect": "out of scope; a disconnect fails the attempt",
        "credential_input": "environment or hidden interactive prompt",
    }
