# Browser-agent failure taxonomy

Snapshot date: `2026-08-28`

This taxonomy interprets Browser Agent Regression evidence without turning an
ordered DOM checkpoint into an unsupported claim about an agent's internal
cause. It is a research and diagnosis guide, not a change to evidence schema
`1.0` or the frozen three-task/four-variant protocol.

## Outcome localization is not causal localization

The v1 oracle records the first expected task checkpoint that is false, a
bounded error if one was raised, and the final pass flag. That is enough to say
where the task contract first became unsatisfied. It does not record the agent's
observations, reasoning, tool calls, target choices, retries, navigation history
or self-report.

Therefore, `first_failed_checkpoint` is an **outcome location**. A causal label
below is justified only when a retained error or trajectory directly supports
it. Otherwise the correct label is `task outcome failure; cause unknown`.

## Failure states

| Failure state | Definition and observable symptom | Is the v1 DOM oracle sufficient? | Trajectory evidence needed | Honest repository example |
| --- | --- | --- | --- | --- |
| Observation failure | The required page state never enters, or is materially wrong in, the agent's observation. The run may omit a relevant action, describe absent UI, or act from stale content before a checkpoint remains false. | **Outcome only.** Checkpoints can show the task failed, but cannot show what the agent received. | Observation payloads or hashes, screenshot/DOM/accessibility snapshot supplied to the agent, page identity and timestamp. | No schema-1.0 causal example. Historical [DeepSeek smoke 04](../evidence/phase0-deepseek-smoke-04.md) passed the DOM goal while the agent reported failure; this is compatible with failure to recognize the confirmed state, but one run does not prove the internal cause. |
| Identification failure | The agent observes the relevant content but assigns the wrong semantic identity, such as confusing the requested product, field meaning or state value. A plausible but wrong entity is used and a task checkpoint fails. | **No causal distinction.** A checkpoint may expose the wrong final entity only when the contract checks it. | Observation plus the agent's parsed entity/value, selected candidate set and decision before action. | No committed v1 example. The catalog contract checks the exact product, but all v1 failures stop before `catalog.query.applied`; they do not demonstrate misidentification. |
| Target-selection failure | The intended operation is correct, but the chosen actionable element, index, frame or tab is wrong. A neighboring control may change while the intended checkpoint stays false. | **Outcome only.** The v1 report contains no chosen locator or element identity. | Validated tool arguments, resolved element/frame identity, element snapshot and before/after checkpoint state. | No committed v1 example. |
| Action-dispatch failure | A planned action is not emitted, has invalid arguments, is rejected by the tool/provider, or is blocked before reaching its target. The observable symptom is a tool/provider error and no expected state change. | **Partial.** A retained `error` can directly show rejection or pointer interception; checkpoints confirm the missing outcome. | Tool call request/result, provider response, resolved target and dispatch timestamp are needed when the bounded error is ambiguous. | In the schema-1.0 [popup-blind calibration](../evidence/v1.0.0-calibration.json), the dismissible overlay intercepts the first pointer action, Playwright times out, and each task fails its first checkpoint. Historical [Gate C 01](../evidence/phase0-deepseek-gate-c-01.md) separately records malformed `AgentOutput` arguments before browser action. |
| Action no-op | A tool call returns without a decisive error, but the intended application state does not change. The same relevant DOM/app value remains after the action. | **Detection can be sufficient; cause is not.** A covered post-action checkpoint detects unchanged state, but v1 cannot prove the action was correctly dispatched. | Tool result plus state snapshots immediately before and after the action, including application state when DOM text is insufficient. | No committed v1 example; popup-overlay failures contain explicit interception timeouts, not silent no-ops. |
| Timing failure | Correct behavior occurs at the wrong time: the agent reads before bounded rendering completes, acts on stale UI, times out too early, or races a transition. Symptoms include transient absence, stale target errors or outcome changes under wait policy. | **Partial at best.** Duration and a bounded error may expose a timeout, but v1 has no event-level timing sequence. | Monotonic timestamps for observations, render/navigation events, waits, actions, tool results and checkpoint samples. | No failing v1 example. `delayed-render` is an honest stress condition in the [checkout](../../src/browser_agent_regression/fixtures/checkout.json), [catalog](../../src/browser_agent_regression/fixtures/catalog.json) and [preferences](../../src/browser_agent_regression/fixtures/preferences.json) manifests, and the v1 reference oracle passes it; that pass must not be relabelled as a timing failure. |
| State-transition failure | A correctly delivered action fails to produce the required application transition, or produces the wrong state. A post-action checkpoint is false even though dispatch succeeded against the intended target. | **Yes for a covered outcome, no for cause.** Ordered checkpoints can detect the missing transition but do not establish correct dispatch. | Successful dispatch evidence and DOM/localStorage/backend state before and after the action. | No direct v1 application-side example. The popup calibration blocks actions before delivery, so it is not evidence of a broken application transition. |
| Navigation failure | The run moves to the wrong route, document, frame, tab or history state, or fails to navigate when the task requires it. Downstream controls are absent or belong to another context. | **No.** v1 evidence does not retain URL/frame/tab history; false checkpoints only show the downstream outcome. | Page/frame identifiers, URL and navigation events, opener/tab changes, redirects and checkpoint state per context. | No committed v1 example. |
| Recovery failure | A recoverable obstacle or transient error occurs, but the system does not adapt, repeats an ineffective action, exhausts its budget or terminates prematurely. | **Final outcome only.** v1 cannot distinguish no recovery attempt from repeated failed recovery. | Ordered failures, retry decisions, repeated actions, remaining budget and the state after each recovery attempt. | The popup-blind driver is a synthetic v1 example of not dismissing a recoverable overlay before timing out. Historical [Gate C 02](../evidence/phase0-deepseek-gate-c-02.md) is the opposite outcome: malformed outputs occurred, yet all three tasks eventually passed; it shows why recovery needs trajectory evidence. |
| False success | The agent or harness claims completion while an independent goal checkpoint or safety invariant is false. | **Not by itself.** v1 trusts DOM checkpoints for pass/fail but schema `1.0` does not store an agent self-report to compare. | Final self-report, independent final-state/safety evidence and timestamps proving they refer to the same attempt. | No committed false-success example. Historical [DeepSeek smoke 04](../evidence/phase0-deepseek-smoke-04.md) is the inverse—DOM pass with an unsuccessful self-report—and must not be cited as false success. |
| Safety failure | A forbidden side effect occurs, a protected invariant is violated, or an unsafe action is attempted, whether or not the goal later passes. | **No.** The frozen v1 task contracts contain positive checkpoints but no forbidden-action or side-effect oracle. | Complete action log plus explicit forbidden actions, state invariants, backend/audit events and redacted sensitive-data handling. | No v1 example and no v1 safety claim. The current [evidence protocol](../evidence-schema.md) only rejects credential-shaped fields in reports; that is evidence hygiene, not agent-action safety evaluation. |
| Harness/runtime failure | The fixture server, browser, provider transport, adapter, scorer, validator or environment fails, making the attempt invalid or mis-scored independently of agent capability. | **No as an outcome oracle.** Report errors, environment fields, validation and exit code can diagnose some cases, but false scoring can corrupt checkpoints themselves. | Lifecycle logs, provider/tool errors, browser/server health, scorer timing, fixture hashes and cleanup events. | No schema-1.0 v1 failure is committed. Historical [smoke 01](../evidence/phase0-deepseek-smoke-01.md) records provider HTTP 400 before browser action; [smoke 02](../evidence/phase0-deepseek-smoke-02.md) records a runner false negative after the browser closed before scoring. |

## Minimum trajectory extension for causal diagnosis

A future trajectory artifact should add only evidence needed to distinguish the
states above while keeping the v1 report as the outcome source of truth:

1. attempt, step, page/frame and observation identities with content hashes;
2. ordered, timestamped agent outputs, validated tool calls and bounded results;
3. resolved target identity and navigation context;
4. independent checkpoint and relevant application-state snapshots before and
   after actions;
5. retry/recovery decisions, remaining step/time budget and termination reason;
6. the agent's final self-report stored separately from independent outcome;
7. forbidden-action/invariant evidence for any experiment making safety claims;
8. provider, browser, fixture-server and scorer lifecycle errors.

Credentials, cookies, private page content, personal paths and unnecessary model
reasoning must be omitted or redacted. Hashes and bounded structured fields are
preferred over retaining raw pages.

## Classification procedure

1. Validate the report, fixture hashes and runtime boundary first. A known
   harness/runtime failure prevents an agent-performance interpretation.
2. Record `passed` and `first_failed_checkpoint` exactly as outcome evidence.
3. Check safety evidence independently; goal success cannot erase a forbidden
   side effect.
4. Use retained trajectory facts to assign the earliest supported causal state.
   Later cascades may be secondary labels.
5. If evidence cannot distinguish observation, identification, selection,
   dispatch, no-op, timing or transition, keep the cause `unknown` rather than
   choosing the most plausible story.

This taxonomy preserves the v1 result: the synthetic popup calibration reliably
detects and localizes three designed regressions. It does not retroactively turn
those regressions into evidence that every internal browser-agent failure stage
is already observable.
