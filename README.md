<p align="center">
  <img src="docs/assets/alvenx-wordmark.svg" width="320" alt="AlvenX — Agent Reliability">
</p>

# Browser Agent Regression

**Browser Agent Regression is the open-source browser-agent reliability project in the
AlvenX series.**

[![CI](https://github.com/AlbertXXuu/BrowserAgentRegression/actions/workflows/ci.yml/badge.svg)](https://github.com/AlbertXXuu/BrowserAgentRegression/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12%20%7C%203.13-3776AB)
[![License](https://img.shields.io/badge/License-Apache--2.0-blue.svg)](LICENSE)

[简体中文](README.zh-CN.md)

A local-first experiment for answering one practical question: **did a browser-agent change
improve reliability, or did it quietly break a workflow that used to pass?**

The project is in a **5–7 day Phase 0 validation**. It is not yet a general-purpose framework.
The current executable slice provides deterministic checkout, catalog, and notification-
preference fixtures, controlled semantic-preserving UI perturbations, checkpoint-level scoring,
repeated runs, and a JSON regression report.

> Status: all three required tasks are implemented, and the deterministic fixture, synthetic
> regression, and real-agent feasibility gates pass. Two independent developer runs remain
> pending. Phase 0 is a **GO only if every gate in [PROJECT.md](PROJECT.md) passes**; until then,
> this repository remains a falsifiable project hypothesis, not a finished product.

The repository tracks AlvenX [AOS-0.1 conformance](docs/alvenx-conformance.md)
without expanding the Phase 0 scope.

## Zero-key quick start

Python 3.11–3.13 is supported. Create a virtual environment:

```bash
python -m venv .venv
```

Activate it with `.venv\Scripts\Activate.ps1` in PowerShell or
`source .venv/bin/activate` on macOS/Linux, then run:

```bash
python -m pip install -e ".[dev]"
python -m playwright install chromium
browser-agent-regression demo
```

The `demo` command requires no API key, model account, paid request, or external model service.
It runs 12 deterministic local attempts, prints a short explanation, and writes full evidence
to `runs/demo-report.json`. The expected result is three localized controlled regressions with
clean behavior preserved.

This is synthetic harness calibration, not an AI-agent benchmark. Browser installation may
download Chromium once; subsequent demo runs are local.

## Phase 0 calibration evidence

The third slice was run locally from one source snapshot. The deterministic reference oracle
completed 30/30 repetitions for all three tasks under every current condition:

| Task | Condition | Reference oracle | Calibration baseline | Calibration candidate |
|---|---|---:|---:|---:|
| `checkout.basic.v1` | `clean` | 30/30 | 10/10 | 10/10 |
| `checkout.basic.v1` | `popup-overlay` | 30/30 | 10/10 | **0/10** |
| `checkout.basic.v1` | `delayed-render` | 30/30 | — | — |
| `checkout.basic.v1` | `layout-shift` | 30/30 | — | — |
| `catalog.find-and-save.v1` | `clean` | 30/30 | 10/10 | 10/10 |
| `catalog.find-and-save.v1` | `popup-overlay` | 30/30 | 10/10 | **0/10** |
| `catalog.find-and-save.v1` | `delayed-render` | 30/30 | — | — |
| `catalog.find-and-save.v1` | `layout-shift` | 30/30 | — | — |
| `preferences.notifications.v1` | `clean` | 30/30 | 10/10 | 10/10 |
| `preferences.notifications.v1` | `popup-overlay` | 30/30 | 10/10 | **0/10** |
| `preferences.notifications.v1` | `delayed-render` | 30/30 | — | — |
| `preferences.notifications.v1` | `layout-shift` | 30/30 | — | — |

The intentionally popup-blind candidate preserved clean performance on all three tasks but
regressed by 100 percentage points under the overlay. All failures localized first to the
expected task-specific checkpoint: `checkout.email.accepted`, `catalog.query.applied`, or
`preferences.product_updates.disabled`. Inspect the preserved
[oracle evidence](docs/evidence/phase0-slice-03-oracle.json) and
[calibration evidence](docs/evidence/phase0-slice-03-calibration.json).

These are **synthetic harness-calibration results**, not model or browser-agent benchmark
scores. Their purpose is to prove fixture stability and regression sensitivity before a real
agent adapter is added.

## Gate C real-agent feasibility evidence

On revision `b817b68`, Browser Use 0.13.7 with `deepseek-v4-flash` completed one authenticated
clean attempt for each task. Independent DOM scoring produced:

| Task | Independent result | Duration |
|---|---:|---:|
| `checkout.basic.v1` | 1/1 | 45.36 s |
| `catalog.find-and-save.v1` | 1/1 | 33.69 s |
| `preferences.notifications.v1` | 1/1 | 31.07 s |

Inspect the [Gate C report](docs/evidence/phase0-deepseek-gate-c-02.json) and its
[interpretation](docs/evidence/phase0-deepseek-gate-c-02.md). This passes integration feasibility,
not repeated reliability: all three trajectories contained recoverable empty or malformed model
outputs, and checkout incorrectly self-reported failure after the DOM goal had passed. The
independent scorer, rather than the Agent's claim, remains authoritative.

## Why this exists

Browser-agent demos usually show that a task can pass once. Upgrade decisions need stronger
evidence: the same tasks, repeated runs, controlled changes, explicit checkpoints, and a
baseline-versus-candidate comparison.

This repository is testing whether that smaller developer workflow is useful before any
platform is built.

## Current executable slice

The included checkout, catalog find-and-save, and notification-preference tasks each have four
conditions:

- `clean`
- `popup-overlay`
- `delayed-render`
- `layout-shift`

All conditions preserve the task's meaning. A reference driver acts as the deterministic
oracle. A deliberately popup-blind calibration driver proves that the runner can distinguish
a real regression from fixture instability. Neither driver is presented as an AI-agent
benchmark result.

## Deeper local checks

Run the stronger fixture-stability check used by Phase 0 evidence:

```bash
browser-agent-regression oracle --runs 30
```

Run only one task when diagnosing a fixture:

```bash
browser-agent-regression oracle --task catalog.find-and-save.v1 --runs 3
```

Run the synthetic regression calibration:

```bash
browser-agent-regression calibrate --runs 10 --output calibration.json
```

Expected calibration behavior:

- the reference baseline passes `clean` and `popup-overlay`;
- the popup-blind candidate still passes `clean`;
- the candidate fails `popup-overlay` at `checkout.email.accepted`;
- the command emits a machine-readable regression report.

Run the local fixture manually:

```bash
browser-agent-regression serve
```

## Optional real agent: Browser Use + DeepSeek

This section is not part of the quick start. Use it only when you deliberately want to make
paid external model requests.

Install the isolated agent extra and start with one paid attempt:

```bash
python -m pip install -e ".[agent]"
browser-agent-regression deepseek --task preferences.notifications.v1 --runs 1 --headed
```

When `DEEPSEEK_API_KEY` is absent, the CLI guides you to the official platform and accepts the
key through hidden input without storing it. Read the complete [DeepSeek setup and safe-key
guide](docs/deepseek.md) before running all three tasks. Real-agent results use independent DOM
checks and remain separate from the synthetic calibration above.

## Help validate Phase 0

If you maintain, evaluate, or study browser agents, clone the repository and run the two
commands above on your own machine. Then submit the
[Phase 0 independent-run form](https://github.com/AlbertXXuu/BrowserAgentRegression/issues/new?template=phase0-run.yml).

A successful report and a blocked report are both useful. The external-demand gate counts only
non-maintainer runs that include a tested revision, environment, commands, safe evidence, and
concrete workflow feedback. Stars and page views do not count.

## Development

```bash
python -m ruff check .
python -m pytest
```

## License

Apache-2.0.

---

An AlvenX open-source project. The functional project name remains independent of the
series brand.
