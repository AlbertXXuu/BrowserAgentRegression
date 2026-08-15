# DeepSeek Gate C 02 — feasibility pass with reliability warnings

**Source revision:** `b817b68`

**Date:** 2026-08-15

**Independent result:** 3/3 tasks; 9/9 checkpoints (`clean`)

The corrected authenticated run used Browser Use 0.13.7, `deepseek-v4-flash`, disabled thinking,
DeepSeek JSON Output with strict Pydantic validation, no vision or model judge, and a headed local
browser. The tested fixture and manifest hashes match the source revision. The three results were:

| Task | Independent result | Duration |
|---|---:|---:|
| `checkout.basic.v1` | 1/1 | 45.36 s |
| `catalog.find-and-save.v1` | 1/1 | 33.69 s |
| `preferences.notifications.v1` | 1/1 | 31.07 s |

This satisfies Phase 0 Gate C: one current browser-agent implementation executed every required
goal through the repository-local adapter, credentials remained outside evidence, and the same
report schema captured every result.

It does not establish repeated reliability. All three trajectories contained recoverable empty or
malformed model outputs. Checkout reached the correct DOM state but exhausted 12 steps and called
`done` with `success=false`; the deterministic scorer nevertheless observed the requested email,
Express shipping, and visible confirmation. Catalog passed after seven steps and two empty-action
failures. Preferences passed after five steps and three empty-action failures.

The discrepancy is intentional evidence for the project boundary: deterministic task checkpoints
are authoritative, while Agent self-reports and a single successful run are not. Gate D remains
open until two non-author developers independently clone and run the documented workflow.
