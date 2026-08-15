# DeepSeek smoke 04 — independent pass, Agent self-report failure

**Source revision:** `2e41fa3`

**Date:** 2026-08-15

**Independent result:** 1/1 (`checkout.basic.v1`, `clean`)

**Agent self-report:** unsuccessful

This authenticated run verifies the JSON Output compatibility change against the live
`deepseek-v4-flash` API. The agent successfully entered `agent@example.test`, selected Express
shipping, and submitted the form. All three independent DOM checkpoints passed against fixture
hashes matching the tested source revision.

The trajectory was still inefficient. After the successful submission, the model produced empty
or malformed actions, repeated the submit action, reached step 12, and called `done` with
`success=false` because Browser Use's page representation did not convince it that the confirmation
was visible. The fixture's deterministic DOM oracle independently observed the exact visible
`Order confirmed` state, so the report correctly records a pass.

This disagreement is evidence for the project's scoring boundary: Agent self-reports are not used
as ground truth. It also remains a reliability warning rather than a quality claim. The JSON Output
transport restored executable actions, but a single smoke run does not establish stable model
performance. Gate C still requires a preserved three-task run from the corrected revision.
