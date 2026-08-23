# Evidence protocol v1

Protocol: `browser-agent-regression-controlled-ui-v1`

Schema: `1.0`

## Purpose

An evidence report records enough information to decide whether a candidate browser-agent system
regressed relative to a baseline on the same controlled tasks. The independent fixture checkpoints,
not an agent's self-reported success, determine the result.

## Stable fields

| field | meaning |
| --- | --- |
| `schema_version` | evidence shape; v1 emits `1.0` |
| `protocol_id` | frozen v1 task/variant/scoring protocol |
| `tool_version` | package version that wrote the report |
| `evidence_kind` | `synthetic-calibration` or `real-agent` |
| `created_at` | UTC creation timestamp |
| `task_ids` | evaluated task contracts |
| `command` | CLI experiment that produced the report |
| `environment` | Python, platform, Playwright, and browser versions |
| `fixture_sha256` | hashes for every task HTML and JSON manifest |
| `configuration` | run count, tasks, variants, and optional non-secret run identity |
| `attempts` | ordered checkpoints, first failure, bounded error, duration, and pass flag |
| `summaries` | success counts/rates and failure-checkpoint counts by cell |
| `regressions` | negative candidate-minus-baseline deltas and localization agreement |

## Validation

`browser-agent-regression verify --report <path>` performs structural and semantic checks:

1. task and variant identifiers are declared and known;
2. every attempt contains exactly the ordered checkpoints for its task;
3. `first_failed_checkpoint` and `passed` agree with checkpoint/error evidence;
4. summaries and regressions recompute exactly from attempts;
5. fixture hashes match the bytes installed with the package; and
6. no `api_key`, `authorization`, or `token` field exists anywhere in the report.

Schema `0.2` reports from Phase 0 remain supported by the validator. Schema `0.1` is retained only as
historical provenance and is not part of the v1 compatibility promise.

## Reproducibility boundary

Pass/fail outcomes, fixture hashes, summaries, regressions, and first-failure localization should be
reproducible for the deterministic drivers. Wall-clock duration, UTC timestamp, OS description,
Playwright version, and browser version are expected to vary. Real-agent outputs may also vary and
must not be interpreted as deterministic evidence from a single run.

## Exit codes

- `0`: command completed and met its acceptance condition.
- `1`: experiment completed, but an oracle/calibration/agent acceptance condition failed.
- `2`: invalid input/evidence or runtime/setup failure.
