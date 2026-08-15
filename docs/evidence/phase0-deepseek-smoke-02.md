# DeepSeek smoke 02 — retained false negative

**Source revision:** `e5b812c`

**Date:** 2026-08-15

**Reported result:** 0/1 (`preferences.notifications.v1`, `clean`)

**Observed browser result:** completed

The second authenticated Browser Use + `deepseek-v4-flash` run confirmed that disabling DeepSeek
thinking mode resolved the first run's HTTP 400 failure. The agent reached the fixture, changed the
requested settings, saved them, and reported all three requested outcomes as visibly confirmed.

The generated JSON nevertheless recorded all checkpoints as false. This is a runner false negative,
not valid agent-performance evidence: Browser Use 0.13.7 calls `Agent.close()` before `Agent.run()`
returns. Because the adapter created the browser with `keep_alive=False`, that close killed the
shared browser session before the independent DOM scorer ran. The scorer error was then hidden by
the last transient AgentOutput validation error from the model history.

The correction keeps the browser alive through independent scoring, force-kills it in the adapter's
`finally` block, and reports both scoring and agent-history errors when scoring itself fails. A local
lifecycle check confirmed that the page remains scoreable after Browser Use closes its event bus and
that the subsequent forced kill succeeds.

The model also produced three transient malformed structured outputs during this run before
recovering. That behavior is a useful reliability observation, but this one-run smoke test is not a
benchmark and the invalid checkpoint result is not included as a Gate C success or failure.
