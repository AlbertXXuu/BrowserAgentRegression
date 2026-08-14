# Project Charter — Browser Agent Regression

**Status:** Phase 0 validation<br>
**Decision date:** 2026-08-15<br>
**Time box:** 5–7 days<br>
**Owner:** AlbertXXuu

## 1. Decision

Build a lightweight, local-first regression fixture runner for browser agents, but approve
only Phase 0. Work stops or the direction changes if the gates below do not pass.

This is not a commitment to build a platform. Phase 0 exists to test two assumptions:

1. Controlled browser tasks can produce stable and diagnostically useful regression evidence.
2. At least two target developers care enough to clone and run that evidence workflow.

## 2. Target user and job

The initial target user is a developer who maintains or upgrades a browser agent and needs to
decide whether a model, harness, prompt, tool schema, framework, or policy change is safe to
merge.

Their job is:

> Run the same controlled workflows before and after a change, detect a statistically obvious
> regression, and identify the first failed checkpoint without operating hosted infrastructure.

Phase 0 does not claim that this is already a validated market. External runs are a required
gate precisely because current evidence is insufficient.

## 3. Product hypothesis

The longer-term research object is **agent-system regression**:

```text
agent system = model + harness + tools + environment
```

Browser is the first controlled environment, not a claim that the project already evaluates
every kind of agent system. During Phase 0, `reference` and `popup-blind` remain explicitly
synthetic calibration drivers. A generic model/harness/prompt/tool run identity is deferred
until one real integration and external users demonstrate which fields are actually required.

Given deterministic local tasks and semantic-preserving UI perturbations, a small repeated-run
harness can reveal browser-agent regressions more reliably than one-off demos and with less
setup than a hosted benchmark platform.

The strongest competing explanation is that agent teams already have internal eval harnesses
or prefer existing browser benchmarks. Two independent external runs are therefore necessary;
technical success alone is not a GO decision.

## 4. Phase 0 scope

### Required

- Three distinct local browser tasks with isolated resettable state.
- Three controlled perturbation classes: popup overlay, delayed rendering, and layout shift.
- Explicit task goals and checkpoint oracles.
- Repeated-run baseline/candidate comparison.
- Machine-readable JSON evidence with the first failed checkpoint.
- One real browser-agent integration after the deterministic calibration is trustworthy.
- Two target developers who independently clone and run the project.

### Current executable slice

- Three tasks: checkout, catalog find-and-save, and notification preferences.
- All three perturbation classes on all three tasks.
- A deterministic reference oracle.
- A deliberately degraded calibration candidate.
- CLI commands for serving, selecting tasks, oracle stability runs, and paired calibration.
- One concrete optional Browser Use + DeepSeek command with hidden credential input and
  independent DOM checkpoint scoring.
- Evidence schema `0.2`, which adds task identity to attempts, summaries, and regressions.

Gate A and Gate B pass on the third local slice: the reference oracle completed 360/360
attempts, and the synthetic candidate produced three correctly localized popup regressions.
The Gate C adapter is implemented and locally exercised without a provider call, but Gate C
remains pending until one authenticated run completes all three goals. Gate D also remains
pending.

The calibration drivers are controls for the harness. They are not evidence about the quality
of any model or browser-agent framework.

## 5. Non-goals

Phase 0 will not include:

- a hosted service, dashboard, account system, database, or telemetry pipeline;
- a new browser agent, autonomous planner, or model-training code;
- a plugin marketplace or speculative universal adapter API;
- a universal harness benchmark or a generic agent-system ontology;
- production trace replay, video analysis, or chain-of-thought capture;
- a leaderboard or claims of broad agent ranking;
- arbitrary websites whose state cannot be reset deterministically;
- more tasks or perturbations after the acceptance matrix is satisfied;
- branding work beyond a functional README and a restrained Ailumetra attribution.

## 6. Acceptance gates

All gates are conjunctive. Missing one means **NO-GO / continue validation**, not “almost
passed.”

### Gate A — Fixture determinism

- Exactly three task workflows are included in Phase 0.
- Every task has a documented goal, reset mechanism, and checkpoint sequence.
- The reference oracle passes 30/30 runs for every required task-condition pair.
- A failed run preserves its condition, checkpoint, duration, and bounded error message.

### Gate B — Regression sensitivity

- Baseline and candidate each run at least 10 times on the target condition.
- They have equal success on the clean condition.
- The deliberately degraded candidate loses at least 30 percentage points on one controlled
  perturbation while the reference baseline remains stable.
- At least 80% of candidate failures agree on the first failed checkpoint.
- The JSON report identifies that regression without manual log reading.

### Gate C — Real-agent feasibility

- One current browser-agent implementation can execute all three task goals through a thin,
  repository-local adapter.
- Credentials are optional for the deterministic test suite and never stored in evidence.
- Repeated results can be compared without changing the fixture or report schema.

This gate proves integration feasibility, not market demand and not state-of-the-art quality.

### Gate D — External demand

- Two target developers independently clone the repository and run the documented command on
  their own machines.
- Each run produces either a shared report, a reproducible issue, or concrete workflow
  feedback.
- Stars, page views, compliments, and the owner's own second machine do not count.

## 7. Stop and adjustment rules

- Stop Phase 0 after day 7 if fixture nondeterminism prevents Gate A after two focused fixes.
- Do not start v0.1 while either Gate B or Gate D is unpassed.
- If real-agent integration requires framework-specific changes throughout the core, narrow to
  one named agent ecosystem instead of inventing a universal abstraction.
- If external users understand the problem but cannot complete setup, prioritize installation
  friction before adding capabilities.
- If target developers report that existing internal or open-source tools already solve the
  job, document the comparison and stop rather than differentiating cosmetically.

## 8. Architecture boundary

Phase 0 has four responsibilities:

```text
task manifest + local fixture
            ↓
     agent/driver attempt
            ↓
     checkpoint evidence
            ↓
 baseline/candidate report
```

- **Fixture:** deterministic local HTML and reset-by-reload state.
- **Attempt runner:** opens an isolated page and records checkpoint outcomes.
- **Comparison:** aggregates repeated attempts and reports negative success-rate deltas.
- **CLI:** exposes the experiment without adding a service layer.

The repository intentionally has no generic adapter interface yet. The first real-agent
integration will reveal the minimum boundary based on evidence rather than prediction.

## 9. Evidence policy

- Generated reports include a schema version and explicit configuration.
- Synthetic calibration results are labelled `synthetic`; real results must name the agent,
  model, harness, prompt/tool configuration when relevant, date, and run count.
- No result is described as a benchmark unless the task set and methodology justify that word.
- Failures and instability remain visible; unsuccessful experiments are not deleted from the
  project record.

## 10. Brand architecture

- Functional project name: **Browser Agent Regression**.
- Repository: `BrowserAgentRegression`.
- Python distribution and CLI: `browser-agent-regression`.
- Series attribution: **Ailumetra**, secondary only.
- Series standard: **AOS-0.1**, tracked in
  [`docs/ailumetra-conformance.md`](docs/ailumetra-conformance.md).

This lets developers discover the repository by its function while preserving the option for
Ailumetra to become a future studio or open-source series.
