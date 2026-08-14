<p align="center">
  <img src="docs/assets/ailumetra-wordmark.svg" width="320" alt="Ailumetra — Agent Reliability">
</p>

# Browser Agent Regression

**Browser Agent Regression is the open-source browser-agent reliability project in the
Ailumetra series.**

[![CI](https://github.com/AlbertXXuu/BrowserAgentRegression/actions/workflows/ci.yml/badge.svg)](https://github.com/AlbertXXuu/BrowserAgentRegression/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12%20%7C%203.13-3776AB)
[![License](https://img.shields.io/badge/License-Apache--2.0-blue.svg)](LICENSE)

[简体中文](README.zh-CN.md)

A local-first experiment for answering one practical question: **did a browser-agent change
improve reliability, or did it quietly break a workflow that used to pass?**

The project is in a **5–7 day Phase 0 validation**. It is not yet a general-purpose framework.
The first executable slice provides a deterministic checkout fixture, controlled
semantic-preserving UI perturbations, checkpoint-level scoring, repeated runs, and a JSON
regression report.

> Status: one of three required tasks is implemented. Phase 0 is a **GO only if all technical
> and user-validation gates in [PROJECT.md](PROJECT.md) pass**. Until then, the repository
> should be read as a falsifiable project hypothesis, not a finished product.

## Phase 0 calibration evidence

The first slice was run locally from one source snapshot. The deterministic reference oracle
completed 30/30 repetitions under every current condition:

| Condition | Reference oracle | Calibration baseline | Calibration candidate |
|---|---:|---:|---:|
| `clean` | 30/30 | 10/10 | 10/10 |
| `popup-overlay` | 30/30 | 10/10 | **0/10** |
| `delayed-render` | 30/30 | — | — |
| `layout-shift` | 30/30 | — | — |

The intentionally popup-blind candidate preserved clean performance but regressed by 100
percentage points under the overlay. All ten failures localized first to
`checkout.email.accepted`. Inspect the preserved
[oracle evidence](docs/evidence/phase0-slice-01-oracle.json) and
[calibration evidence](docs/evidence/phase0-slice-01-calibration.json).

These are **synthetic harness-calibration results**, not model or browser-agent benchmark
scores. Their purpose is to prove fixture stability and regression sensitivity before a real
agent adapter is added.

## Why this exists

Browser-agent demos usually show that a task can pass once. Upgrade decisions need stronger
evidence: the same tasks, repeated runs, controlled changes, explicit checkpoints, and a
baseline-versus-candidate comparison.

This repository is testing whether that smaller developer workflow is useful before any
platform is built.

## Current executable slice

The included checkout task has four conditions:

- `clean`
- `popup-overlay`
- `delayed-render`
- `layout-shift`

All conditions preserve the task's meaning. A reference driver acts as the deterministic
oracle. A deliberately popup-blind calibration driver proves that the runner can distinguish
a real regression from fixture instability. Neither driver is presented as an AI-agent
benchmark result.

## Quick start

Python 3.11–3.13 is supported.

```bash
python -m venv .venv
```

Activate it with `.venv\Scripts\Activate.ps1` in PowerShell or
`source .venv/bin/activate` on macOS/Linux, then install the project and browser:

```bash
python -m pip install -e ".[dev]"
python -m playwright install chromium
```

Verify that the fixture and oracle are stable:

```bash
browser-agent-regression oracle --runs 30
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

## Development

```bash
python -m ruff check .
python -m pytest
```

## License

Apache-2.0.

---

An Ailumetra open-source project. The functional project name remains independent of the
series brand.
