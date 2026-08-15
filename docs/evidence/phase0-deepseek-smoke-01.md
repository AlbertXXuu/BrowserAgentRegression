# DeepSeek smoke 01 — retained failure

**Source revision:** `219bcbb`

**Date:** 2026-08-15

**Result:** 0/1 (`preferences.notifications.v1`, `clean`)

The first authenticated Browser Use + `deepseek-v4-flash` run reached the provider but did not
perform a browser action. Four consecutive model requests returned HTTP 400 because DeepSeek V4
defaults to thinking mode while Browser Use 0.13.7 forces a named `tool_choice` for its structured
agent output. DeepSeek V4 does not accept that combination.

The generated JSON retained `No current target found`, a secondary scoring error that replaced the
more useful provider error after the failed agent loop. The follow-up correction therefore has two
parts:

1. inject `thinking: {type: disabled}` into DeepSeek requests while preserving the required
   structured tool choice;
2. retain the agent/provider error when independent scoring cannot access the page.

The correction was verified without another paid call by capturing the final OpenAI-compatible
request through a local mock transport. The captured body contained both the named `tool_choice`
and `thinking: {type: disabled}`. The failed JSON contains no API key. It remains in the repository
so the unsuccessful experiment and diagnostic limitation are not hidden.
