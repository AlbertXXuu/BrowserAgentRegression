# Hronaut MCP pilot 01 — one-task integration feasibility

**Source revision:** the adapter commit of this change, on top of `8e2f204` (`v1.1.3`)

**Date:** 2026-11-17

**Independent result:** 1/1 attempt; 3/3 checkpoints (`preferences.notifications.v1`, `clean`)

One `hronaut-mcp-deepseek` attempt against a running Hronaut 3.14.33 desktop app on Linux, for
[Issue #14](https://github.com/AlbertXXuu/BrowserAgentRegression/issues/14). It was the first and
only model-backed attempt made with the adapter, not one selected from several.

- [`hronaut-mcp-pilot-01.json`](hronaut-mcp-pilot-01.json) is the BAR report; it passes `verify`.
- [`hronaut-mcp-pilot-01-trace.json`](hronaut-mcp-pilot-01-trace.json) is the sanitized
  `--trace-output` of the same attempt. It is supporting material, not a BAR report.

```sh
browser-agent-regression hronaut-mcp-deepseek \
  --provider openrouter --upstream-provider deepinfra/fp8 \
  --task preferences.notifications.v1 --variant clean --runs 1 \
  --output hronaut-mcp-pilot-01.json --trace-output hronaut-mcp-pilot-01-trace.json
```

## Model route: not DeepSeek's own API

The contributor had no direct DeepSeek API key, so this run used the adapter's OpenRouter route.
It requested `deepseek/deepseek-v4-flash` restricted to the `deepinfra/fp8` endpoint with fallbacks
off and reasoning off; `DeepInfra` was the only serving provider the responses reported. On the run
date OpenRouter's endpoint list for this model contained only third-party hosts.

The model id is the one the Browser Use adapter uses by default, but the serving stack and
quantization differ. This attempt is therefore not comparable with the Phase 0 Browser Use runs,
and the default `--provider deepseek` route is covered by unit tests only; it has not been run
against DeepSeek's API.

## What the trace confirms

| Detail | Observed |
|---|---|
| Negotiation | MCP `2025-11-25`; server `hronaut` 3.14.33; Python `mcp` SDK 2.3.0 over loopback Streamable HTTP; MCP authentication was off in this profile, so no bearer credential was sent |
| Workspace creation | `activeTabId: null`, `tabCount: 0`: a new scratch workspace has no tab |
| Tab creation | `browser_new_tab` returned one tab in that workspace at the exact fixture URL, still `loading` |
| Response wrapping | one text item holding pretty-printed JSON with sorted keys, so checkpoints arrive as `…disabled`, `…saved`, `…enabled` and the adapter restores the declared order |
| Document marker | the same nonce and `performance.timeOrigin` in `document.bind`, `negative-control` and `score`: the marker survives across three separate `browser_evaluate` calls |
| Negative control | three false checkpoints; each required node present exactly once |
| Model loop | 7 model turns, 6 tool calls: snapshot, click `e1`, click `e2`, snapshot, click `e4`, snapshot, then a final message; no tool errors |
| Score | three true checkpoints read by the adapter from the recorded tab before cleanup |
| Close | `browser_workspaces` `close` returned `[]` without error |
| Duration | 22.84 s for the whole attempt |

The trace also contains the projected model-tool schemas, their SHA-256
(`44051cfb…533cf118`, also in the report's run identity) and the upstream input schemas of every
Hronaut tool the adapter or the model can call. Resume keys are redacted; no credential or local
profile path is present.

## Limits

This is one run on one task and one variant. It shows that the adapter, a live Hronaut MCP
session, a model loop and independent scoring work together end to end. It is not evidence of
reliability, of behavior under the perturbed variants, or of broader Hronaut compatibility.
Failure paths (lost or replaced page, unknown action outcome, cleanup errors) are exercised by
the unit tests, not by this attempt. Reconnect recovery remains out of scope.
