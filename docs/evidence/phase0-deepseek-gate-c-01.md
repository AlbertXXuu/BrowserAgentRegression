# DeepSeek Gate C 01 — retained structured-output failure

**Source revision:** `2a0cef8`

**Date:** 2026-08-15

**Result:** 1/3 (`clean`; checkout failed, catalog failed, preferences passed)

The first authenticated three-task run produced valid independent evidence. Checkout and catalog
both failed before their first browser action because `deepseek-v4-flash` returned direct action
parameters such as `{"index": 3, "text": "...", "clear": true}` where Browser Use 0.13.7 required
the complete `AgentOutput` object containing an `action` list. Each task repeated the same invalid
shape three times and then terminated. Preferences recovered from two similar malformed click
outputs and passed all three DOM checkpoints.

The fixture and scorer behaved correctly: the two unmodified pages failed at their first expected
checkpoint, while preferences passed. The report therefore remains a real 1/3 agent-system result,
not a scorer false negative. It does not pass Gate C.

Browser Use's DeepSeek wrapper routes every Pydantic `output_format` through a forced function call;
its later JSON Output branch is unreachable for that same condition. The repository-local adapter
now takes the narrower provider-supported path: request a complete JSON object, validate it against
the unmodified Browser Use Pydantic output model, and reject invalid output instead of guessing an
action. A local mock transport verifies that the request uses `response_format: json_object`, keeps
DeepSeek thinking disabled, and sends neither `tools` nor `tool_choice`. A new authenticated run is
still required to determine whether this compatibility change works against the live model.
