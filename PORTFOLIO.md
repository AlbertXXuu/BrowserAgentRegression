# Browser Agent Regression portfolio evidence

## Problem

A browser-agent stack can change while its happy-path demo still succeeds. Developers need repeated,
independently scored workflows that reveal whether a previously passing behavior regressed and where
the first contract failure occurred.

## Why it was difficult

Agent self-report is not a reliable outcome oracle, browser fixtures must reset exactly, and model,
harness, prompt, tool and UI changes can be confounded. The project therefore separates the local
fixture, attempt driver, independent DOM checkpoints and evidence aggregation.

## Project-specific decisions

- Freeze task-level checkpoint contracts rather than selectors or agent prose.
- Calibrate the harness with deterministic reference and deliberately degraded drivers.
- Keep synthetic calibration distinct from named real-agent evidence.
- Recompute summaries/regressions during verification and reject credential-shaped fields.
- Use exit codes that distinguish experiment failure from invalid evidence/runtime setup.

See [the project charter](PROJECT.md) and [evidence schema](docs/evidence-schema.md).

## Most demanding engineering failure mode

A candidate can appear to act successfully while a state transition is missing. The independent
checkpoint scorer and first-failure field preserve the expected/observed state rather than trusting
the agent's final statement. The v1 popup-blind calibration demonstrates this failure mode in
[committed evidence](docs/evidence/v1.0.0-calibration.json).

## Verified result

The reference oracle passed all `36/36` task/variant attempts. For the deliberately popup-blind
candidate, all three popup conditions fell from `100%` baseline success to `0%`, with consistent
first-failure localization. This validates the designed synthetic calibration, not general agent
quality.

## Negative evidence and limits

The one historical Browser Use + DeepSeek run proves integration feasibility only. Three tasks,
four controlled variants and synthetic drivers do not establish broad model reliability, product
demand or superiority to BrowserGym/WebArena/team evals.

## External use

As of `2026-08-28`, this repository contains no qualifying independent target-developer run. The
next evidence target is a browser-agent maintainer producing a v1 report, reproducible Issue or
workflow decision.

## Personal contribution

The repository history shows AlbertXXuu as the sole human code contributor. The owner is responsible
for task/variant design, checkpoint contracts, evidence semantics, implementation acceptance,
controlled and real-agent evidence boundaries, and the v1 release decision.
