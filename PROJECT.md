# Project Charter — Browser Agent Regression

**Status:** v1 technical release; current focus is setup, evidence readability, and adapter integration<br>
**Decision date:** 2026-08-15<br>
**Time box:** 5–7 days<br>
**Owner:** AlbertXXuu

## v1 decision update — 2026-08-24

The deterministic fixtures, synthetic regression calibration, evidence contract, package, and one
optional real-agent feasibility path have passed their technical gates. The owner authorized a v1
engineering release. v1 freezes the tool and its evidence protocol while independent adoption
measurement is deferred.

## 1. Decision

Build a lightweight regression fixture runner for browser agents. Phase 0 tested the technical
assumption below; a separate adoption signal was defined for possible later use:

1. Controlled browser tasks can produce stable and diagnostically useful regression evidence.

## 2. Target user and job

The initial target user is a developer who maintains or upgrades a browser agent and needs to
decide whether a model, harness, prompt, tool schema, framework, or policy change is safe to
merge.

Their job is:

> Run the same controlled workflows before and after a change, detect a statistically obvious
> regression, and identify the first failed checkpoint from durable evidence.

Phase 0 establishes technical feasibility. Developer feedback now informs setup, report clarity,
and concrete adapter integrations.

## 3. Product hypothesis

The longer-term research object is **agent-system regression**:

```text
agent system = model + harness + tools + environment
```

Browser is the first controlled environment. During Phase 0, `reference` and `popup-blind` are
explicitly synthetic calibration drivers. Real integrations record model, harness, prompt, tool,
and run identity fields required by their evidence.

Given deterministic local tasks and semantic-preserving UI perturbations, a small repeated-run
harness can reveal browser-agent regressions more reliably than one-off demos and with less
setup than a hosted benchmark platform.

The strongest competing explanation is that agent teams already have internal eval harnesses
or prefer existing browser benchmarks. Future scope decisions should therefore use observed
integration needs and developer feedback in addition to technical evidence.

## 4. Phase 0 scope

### Required

- Three distinct local browser tasks with isolated resettable state.
- Three controlled perturbation classes: popup overlay, delayed rendering, and layout shift.
- Explicit task goals and checkpoint oracles.
- Repeated-run baseline/candidate comparison.
- Machine-readable JSON evidence with the first failed checkpoint.
- One real browser-agent integration after the deterministic calibration is trustworthy.

### Current executable slice

- Three tasks: checkout, catalog find-and-save, and notification preferences.
- All three perturbation classes on all three tasks.
- A deterministic reference oracle.
- A deliberately degraded calibration candidate.
- A one-command deterministic calibration demo that saves a clearly labelled synthetic report.
- CLI commands for serving, selecting tasks, oracle stability runs, and paired calibration.
- One concrete optional Browser Use + DeepSeek command with hidden credential input and
  independent DOM checkpoint scoring.
- Evidence schema `0.2`, which adds task identity to attempts, summaries, and regressions.

Gate A and Gate B pass on the third local slice: the reference oracle completed 360/360
attempts, and the synthetic candidate produced three correctly localized popup regressions.
Gate C passes on revision `b817b68`: one authenticated Browser Use + `deepseek-v4-flash` run
completed all three clean goals and passed all nine independent DOM checkpoints. The run proves
integration feasibility and retained transient model-output instability. Its evidence covers one run;
the optional adoption signal remains deferred.

The calibration drivers are controls for the harness. Model-quality evidence requires named
model-backed runs and an appropriate repetition protocol.

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
- branding work beyond a functional README and a restrained AlvenX attribution.

## 6. Acceptance gates

Gates A–C define the completed technical acceptance. The adoption signal is recorded separately
for use if the owner resumes that measurement.

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
- The deterministic suite uses the built-in reference driver; real-agent credentials stay outside evidence.
- Repeated results can be compared without changing the fixture or report schema.

This gate records integration feasibility for the named agent, model, fixture, and run count.

### Deferred adoption signal

- Two target developers independently clone the repository and run the documented command on
  their own machines.
- Each run produces either a shared report, a reproducible issue, or concrete workflow
  feedback.
- Stars, page views, compliments, and the owner's own second machine do not count.

## 7. Stop and adjustment rules

- Stop Phase 0 after day 7 if fixture nondeterminism prevents Gate A after two focused fixes.
- Do not extend the task or perturbation set until a concrete integration or research need is observed.
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

The adapter surface grows from concrete real-agent integrations and their evidence requirements.

## 9. Evidence policy

- Generated reports include a schema version and explicit configuration.
- Synthetic calibration results are labelled `synthetic`; real results must name the agent,
  model, harness, prompt/tool configuration when relevant, date, and run count.
- Use the term `benchmark` only when the task set and methodology justify it.
- Failures and instability remain visible; unsuccessful experiments are not deleted from the
  project record.

## 10. Brand architecture

- Functional project name: **Browser Agent Regression**.
- Repository: `BrowserAgentRegression`.
- Python distribution and CLI: `browser-agent-regression`.
- Series attribution: **AlvenX**, secondary only.
- Series standard: **AOS-0.1**, tracked in
  [`docs/alvenx-conformance.md`](docs/alvenx-conformance.md).

This lets developers discover the repository by its function while preserving the option for
AlvenX to become a future studio or open-source series.
