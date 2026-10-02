# A browser lifecycle false negative and independent outcome scoring

2026-10-02 · BrowserAgentRegression

[简体中文](browser-agent-independent-scoring.zh-CN.md) · [Website reading view](https://alvenx.com/notes/engineering/browser-agent-independent-scoring)

A completed settings task was recorded as a failure because the browser closed before scoring. The correction preserves the page for an independent DOM check, while a separate checkout run shows why an agent's own success report cannot define the result.

## A completed task received a failing score

BrowserAgentRegression evaluates explicit outcomes on resettable local pages. A settings task asks an agent to disable product updates, enable security alerts, and save. Those three checkpoints make completion observable even when a model's description of its actions is uncertain.

On August 15, 2026, the second authenticated Browser Use and deepseek-v4-flash smoke run reached those visible outcomes, yet its JSON recorded 0/1 with every checkpoint false. The retained report identifies source revision e5b812c and classifies this as a runner false negative. Treating the number as model performance would have attributed an infrastructure defect to the agent.

[Retained lifecycle failure and source revision](https://github.com/AlbertXXuu/BrowserAgentRegression/blob/ab28892e36d6e89dd418d703e1fa2c46560c7bb1/docs/evidence/phase0-deepseek-smoke-02.md)

## Keep the page available until scoring finishes

The failure came from the ownership of the browser session. Browser Use 0.13.7 called Agent.close() before Agent.run() returned. With keep_alive=False, that close destroyed the shared session before the adapter could inspect the DOM. A transient AgentOutput validation error also obscured the later scoring error.

The engineering decision was to preserve the scorer's observation window and retain both error sources. The task contract stayed the same: actual page state determines completion, and trajectory errors remain diagnostic evidence. An infrastructure failure must be investigated before an experiment can support a performance conclusion.

[Lifecycle diagnosis](https://github.com/AlbertXXuu/BrowserAgentRegression/blob/ab28892e36d6e89dd418d703e1fa2c46560c7bb1/docs/evidence/phase0-deepseek-smoke-02.md)

## Score the DOM before forced cleanup

The current browser_use_deepseek.py creates the browser with keep_alive=True, awaits the agent, and then calls _score_page against the same page. Cleanup always attempts browser.kill() in finally. When scoring fails, _scoring_failure_message records the scorer error alongside agent history and redacts the API key.

The scorer checks concrete selectors and values. For checkout it requires the requested email, Express shipping, and a visible status whose text is exactly Order confirmed. The adapter disables the model judge and vision for these controlled tasks. This keeps the outcome check separate from the model's observation and final narrative.

[Current adapter and deterministic checkpoint scripts](https://github.com/AlbertXXuu/BrowserAgentRegression/blob/ab28892e36d6e89dd418d703e1fa2c46560c7bb1/src/browser_agent_regression/browser_use_deepseek.py)

## A second disagreement tests the scoring boundary

A local lifecycle check documented that the page remained scoreable after Browser Use closed its event bus and that forced cleanup succeeded. A distinct live checkout run at source revision 2e41fa3 then exercised the corrected scoring boundary and JSON Output compatibility.

The checkout DOM passed all three checkpoints, but the agent repeated submission, produced empty or malformed actions, reached step 12, and ended with success=false. The independent result was 1/1. This disagreement has a different cause from the earlier lifecycle bug: the scorer observed the requested outcome while the agent's page representation did not convince it that confirmation was visible.

The later corrected Gate C run at b817b68 passed three tasks and nine checkpoints once. That establishes adapter feasibility under the recorded settings; the retained malformed outputs still matter when assessing trajectory reliability.

| Evidence | Independent result | Interpretation |
| --- | --- | --- |
| Settings smoke at e5b812c | Recorded 0/1 | Invalid performance result due to lifecycle failure |
| Checkout smoke at 2e41fa3 | 1/1 | DOM pass with unsuccessful agent self report |
| Corrected Gate C at b817b68 | 3/3 tasks | One run establishing integration feasibility |

[Checkout disagreement](https://github.com/AlbertXXuu/BrowserAgentRegression/blob/ab28892e36d6e89dd418d703e1fa2c46560c7bb1/docs/evidence/phase0-deepseek-smoke-04.md) · [Corrected three task feasibility run](https://github.com/AlbertXXuu/BrowserAgentRegression/blob/ab28892e36d6e89dd418d703e1fa2c46560c7bb1/docs/evidence/phase0-deepseek-gate-c-02.md)

## What this case supports

This case demonstrates an observable scoring boundary and a concrete harness repair. Single smoke runs cannot estimate repeated model reliability, and a first failed checkpoint does not by itself identify the model's internal cause. The historical false negative remains preserved with its exclusion reason.

BrowserGym provides a broader framework for web task evaluation. It is relevant design context for separating environment observations from agent actions; the measured outcomes here come from the repository's own fixtures, revisions, and reports. The practical lesson is to make the evaluator's lifecycle part of the experiment contract.

[BrowserGym primary repository](https://github.com/ServiceNow/BrowserGym)

## Original evidence

- [Original false negative](https://github.com/AlbertXXuu/BrowserAgentRegression/blob/ab28892e36d6e89dd418d703e1fa2c46560c7bb1/docs/evidence/phase0-deepseek-smoke-02.md)
- [Independent pass and agent disagreement](https://github.com/AlbertXXuu/BrowserAgentRegression/blob/ab28892e36d6e89dd418d703e1fa2c46560c7bb1/docs/evidence/phase0-deepseek-smoke-04.md)
- [Adapter implementation](https://github.com/AlbertXXuu/BrowserAgentRegression/blob/ab28892e36d6e89dd418d703e1fa2c46560c7bb1/src/browser_agent_regression/browser_use_deepseek.py)
- [Gate C evidence](https://github.com/AlbertXXuu/BrowserAgentRegression/blob/ab28892e36d6e89dd418d703e1fa2c46560c7bb1/docs/evidence/phase0-deepseek-gate-c-02.md)
