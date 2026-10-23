# Hronaut MCP browser: one-task integration pilot

Reviewed 2026-10-19 against BAR `main` at `1f134ba` (including the report-completeness fix in
[PR #18](https://github.com/AlbertXXuu/BrowserAgentRegression/pull/18)). This recipe addresses
[Issue #14](https://github.com/AlbertXXuu/BrowserAgentRegression/issues/14).

The first deliverable is **one task, `clean`, one attempt** with independent observation of the
same live page. BAR's baseline commands below work today. Hronaut execution and a named report
entry point require the contributor's connection details and a small adapter change; there is
currently no `hronaut` CLI command. A successful pilot establishes integration feasibility.

## 1. Run the current BAR baseline

Use a fresh clone so existing work is preserved. Use Python 3.11–3.13. The Issue #14 environment
was reported as Linux/Python 3.12; record the versions actually used for this pilot.

```sh
git clone --branch v1.1.3 --depth 1 https://github.com/AlbertXXuu/BrowserAgentRegression.git bar-mcp-pilot
cd bar-mcp-pilot
git rev-parse HEAD
```

On Linux/macOS:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
.venv/bin/python -m playwright install chromium
.venv/bin/python -m browser_agent_regression doctor
.venv/bin/python -m browser_agent_regression demo --task preferences.notifications.v1 --runs 1 --output runs/mcp-onboarding-demo.json
.venv/bin/python -m browser_agent_regression verify --report runs/mcp-onboarding-demo.json
```

On Windows PowerShell:

```powershell
python -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -e ".[dev]"
& .\.venv\Scripts\python.exe -m playwright install chromium
& .\.venv\Scripts\python.exe -m browser_agent_regression doctor
& .\.venv\Scripts\python.exe -m browser_agent_regression demo --task preferences.notifications.v1 --runs 1 --output runs/mcp-onboarding-demo.json
& .\.venv\Scripts\python.exe -m browser_agent_regression verify --report runs/mcp-onboarding-demo.json
```

Expected: `doctor` succeeds; the demo reports one controlled regression; `verify` prints
`PASS schema=1.0 command=demo attempts=4`. These four attempts are the two built-in drivers on
two variants. Keep this `synthetic-calibration` report separate from the one-attempt Hronaut pilot.
The `v1.1.3` release includes the completeness fix and this guide. Record the exact revision above;
the earlier `v1.1.2` tag predates the fix.

## 2. Make the pilot page and goal available

In terminal A, keep the fixture server running:

```sh
.venv/bin/python -u -m browser_agent_regression serve --port 8765
```

PowerShell equivalent:

```powershell
& .\.venv\Scripts\python.exe -u -m browser_agent_regression serve --port 8765
```

The server prints all 12 task/variant URLs. For this pilot use exactly:

```text
task_id: preferences.notifications.v1
variant: clean
URL: http://127.0.0.1:8765/preferences.html?variant=clean
goal: Disable product updates, enable security alerts, and save the notification preferences.
```

If port 8765 is occupied, choose another free port and use the URL printed by that process.
Read the goal and checkpoint order from
[`preferences.json`](../../src/browser_agent_regression/fixtures/preferences.json), rather than
adding instructions that complete the task for the controller.

`FixtureServer` binds to loopback. Run BAR and the pilot browser on the same host/network namespace.
If Hronaut uses a container, remote host or managed browser, first explain how that browser reaches
this exact server; `127.0.0.1` inside a container refers to the container. The initial recipe does
not change the server's bind address or expose it publicly.

## 3. Agree on page access, then run one attempt

The contributor supplies the actual Hronaut launch command and tool/API invocation. There is no
placeholder Hronaut command to execute in this recipe.

| Step | Responsibility and observable result |
| --- | --- |
| Prepare | BAR creates the attempt record with the declared task, variant, driver, ordered false checkpoints and start time before browser/controller operations. Agree on a step limit and wall-clock timeout. |
| Open | The adapter opens the exact fixture URL and retains the page/target handle. Record the browser/workspace identity and navigation boundary. |
| Observe the negative control | A read-only BAR observer sees all three checkpoints false on a fresh page. This is a plumbing control, not an Agent attempt. |
| Execute | Hronaut receives the exact goal and controls that page through its actual MCP tools. BAR does not click, fill, save, or otherwise complete the goal on its behalf. |
| Score | After the controller stops, BAR independently reads the same live document before reload or cleanup. The observer checks target identity, complete URL including variant, required DOM nodes and checkpoint types. |
| Record | Preserve partial checkpoints, duration and bounded redacted errors. Timeout, disconnect, lost page or scoring failure retains an attempt. All checkpoints true plus a runtime/cleanup error still means `passed=False`. |
| Reset and clean up | Once scoring is recorded, reload according to the manifest and confirm the initial state. Close only resources owned by this attempt. |

The ordered checkpoint result after a successful action is:

```json
{
  "preferences.product_updates.disabled": true,
  "preferences.security_alerts.enabled": true,
  "preferences.saved": true
}
```

This object must come from BAR's observer. The agent's text, screenshot interpretation or returned
checkpoint booleans do not replace the observer. Require the expected controls/status node to
exist before reading them; a missing element must produce a scoring error. Require an object,
exactly these keys and actual boolean values, then restore the declared order. A string such as
`"false"` must be rejected rather than converted with `bool(...)`.

Retain the original page handle and track unexpected navigation/reload. Finding another tab at
the same URL does not establish page identity. On first integration, an unexpected disconnect
can simply fail the attempt; reconnect recovery is a later test if the runtime supports it.

### Independent observation: choose a supported route

- **Shared Chromium/CDP, if Hronaut supports it:** agree who owns the browser; both sides attach
  to that same browser, and BAR selects the agreed target explicitly. Playwright can attach via
  `chromium.connect_over_cdp()`. CDP is Chromium-only and has lower fidelity than Playwright's own
  connection protocol; confirm target, navigation and cleanup behavior on the actual versions.
  Do not assume a Playwright websocket endpoint and a CDP endpoint are interchangeable.
- **Another independent page API:** provide its concrete call and response shape, stable page
  selection and lifecycle behavior. BAR must be able to make a read-only observation after the
  agent finishes. If the controller supplies the only evidence and no independently callable
  observation path exists, this pilot's scoring prerequisite has not been met.

For a shared browser, disconnect the observer without closing the owner's browser or unrelated
tabs. Use a dedicated test profile/session. Keep endpoints and authentication material local.

## 4. Reuse these seams; change only the named execution path

| Existing location | Reuse or narrowly scoped addition |
| --- | --- |
| [`server.py`](../../src/browser_agent_regression/server.py): `FixtureServer.url()` | Exact fixture URL, loopback serving and reset-by-reload. The final adapter may own a server context instead of the standalone `serve` process. |
| [`runner.py`](../../src/browser_agent_regression/runner.py): `TASK_FIXTURES`, `TASK_CHECKPOINTS`, `Attempt` | Existing task contract, checkpoint order and attempt result. |
| [`browser_use_deepseek.py`](../../src/browser_agent_regression/browser_use_deepseek.py): `_task_goal()` | Example of reading the goal from the packaged manifest. Private implementation, not a stable external API. |
| Same file: `_run_attempt()`, `run_deepseek_matrix()` | Example of keeping the page alive through scoring, retaining failures and running every declared cell. Substitute the actual Hronaut control path. |
| Same file: `_CHECKPOINT_SCRIPTS`, `_score_page()` | Review the DOM semantics. `_score_page()` decodes a Browser Use JSON string; Playwright usually returns a dictionary directly. Normalize once and validate strictly; do not copy the wrapper blindly. |
| Same file: `deepseek_run_identity()` | Shape of a named run identity; populate Hronaut's actual values. |
| [`runner.py`](../../src/browser_agent_regression/runner.py): `build_report()` | Reuse schema `1.0`, fixture hashes, attempts and accounting with `evidence_kind="real-agent"`. One feasibility run does not need a new schema or regression-comparison feature. |
| [`cli.py`](../../src/browser_agent_regression/cli.py): `_deepseek()`, `build_parser()` | Example of a named command and dispatch. `serve` alone is not an external-agent runner or report ingester. |

The adapter proposal must include all of the following, together:

1. A small repository-local Hronaut execution module with explicit lifecycle ownership.
2. An agreed named driver and CLI entry point. For discussion, `hronaut/mcp` and `hronaut` are
   proposed names, **not current commands or supported driver values**.
3. An explicit branch in `validate_report()` for that command's driver, `real-agent` evidence kind
   and Hronaut run identity. Retain exact matrix coverage and the existing commands' checks.
   Adding only a `Driver` literal or accepting arbitrary strings will not work.
4. A run identity and targeted tests. Preserve the fixtures, protocol, historical evidence and
   existing Browser Use/DeepSeek identity rules.

Current `main` rejects an honest Hronaut report until that named path is implemented.
Do not label it `deepseek`, `oracle` or `demo` to obtain a verifier pass. A development-only
connection probe can emit a separate `seam-preflight` artifact; it is not a formal BAR report.

## 5. Validate the named adapter before sharing a result

| Check | Required observation |
| --- | --- |
| No-op control | Fresh `preferences/clean` page yields three false checkpoints. |
| One real attempt | One Hronaut run controls the retained page; BAR observes the three checkpoints and preserves the actual outcome, including failure. |
| Partial action plus error | Partial checkpoints remain; runtime error makes the attempt fail. |
| Wrong/lost target, wrong URL or missing DOM | Scoring refuses the wrong state and the attempt remains recorded. No fresh replacement page is scored. |
| Invalid observation | Missing/extra checkpoint keys or non-boolean values are rejected. Cover the actual MCP response wrapper and dictionary/string decoding once. |
| Disconnect, timeout and cleanup | Bounded failure evidence is retained; shared browser resources are preserved. If reconnect is claimed, demonstrate the same browser/workspace/page/document boundary. |
| Reset | A successful fixture reloads to three false checkpoints before the next attempt. |
| Report coverage | Exactly one declared pilot attempt; missing, extra, wrong-driver or mislabeled records are rejected even after recomputing summaries. |
| Existing evidence | Existing supported reports still pass; original fixture-hash mismatches and unsupported formats remain rejected. |

After the named path is implemented, use the existing verifier on the resulting JSON:

```sh
.venv/bin/python -m browser_agent_regression verify --report runs/hronaut-pilot.json
.venv/bin/python -m ruff check .
.venv/bin/python -m pytest
.venv/bin/python scripts/check_repository.py
```

PowerShell uses the same arguments with `& .\.venv\Scripts\python.exe`.
`hronaut-pilot.json` in this block is the future adapter's output, not a file created by today's
baseline commands. `verify` checks report validity: a valid report containing a failed attempt
may pass verification. Inspect `passed`, `error` and `first_failed_checkpoint` separately; the
named runner should retain the existing exit-code distinction between task failure and invalid
input/setup. See the [evidence protocol](../evidence-schema.md).

Agree on any broader task/variant/repetition matrix and model-call budget after the one-task
pilot. Scripted plumbing controls do not count as Hronaut/model reliability observations.

## 6. Information requested from the Hronaut maintainer

Please provide these three groups before the implementation PR; redact connection secrets.

1. **Invocation and identity:** repository/revision (or a minimal reproducible client), client and
   MCP server versions/start commands, transport and negotiated protocol version;
   relevant navigation/action `tools/list` definitions and sanitized call/result examples;
   the read API only if it is used for independent observation;
   model/provider, prompt/tool configuration, and proposed step/time budget.
2. **Browser and observation:** who launches/owns the browser; whether it can attach to a shared
   Chromium CDP endpoint or offers another independent observation API; stable tab/target
   selection and result types; browser/Playwright versions; same-host versus container/remote
   networking and access to the BAR fixture URL.
3. **Completion and lifecycle:** the signal that control has finished; whether finish/stop or MCP
   disconnect closes the page/browser; how to keep the original document alive until BAR scores
   it; reset/cleanup ownership; what survives reconnect, if that behavior is in scope.

Before an adapter exists, exact BAR/Hronaut revisions, sanitized launch/call instructions and
connection/independent-observation output or a specific blocking error are enough. Once the named
path exists, add one run's identity, report and verification output. Attach the synthetic baseline
separately. A full benchmark run is not required to settle the integration seam.

## References

Checked 2026-10-19:

- [Issue #14 and maintainer response](https://github.com/AlbertXXuu/BrowserAgentRegression/issues/14).
- [Playwright Python: connect over CDP](https://playwright.dev/python/docs/api/class-browsertype#browser-type-connect-over-cdp).
- [MCP lifecycle](https://modelcontextprotocol.io/specification/2025-11-25/basic/lifecycle) and
  [tools](https://modelcontextprotocol.io/specification/2025-11-25/server/tools). Record the version
  actually negotiated by Hronaut rather than assuming the reference version.
