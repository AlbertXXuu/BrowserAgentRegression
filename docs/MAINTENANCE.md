# Maintenance policy

Current public release: `v1.1.1`
Research/evidence baseline: immutable `v1.0.0`
Development mode: maintenance; no new research claim

## Frozen release surface

The `v1.0.0` tag and GitHub Release are immutable. The v1 compatibility promise covers:

- CLI commands and documented exit codes;
- the three task IDs, four variant IDs and ordered checkpoint contracts;
- evidence schema `1.0` and protocol `browser-agent-regression-controlled-ui-v1`;
- fixture identities and SHA-256 values;
- committed oracle and synthetic-calibration evidence, summaries and first failures;
- the published distinction between synthetic harness calibration and real-agent evidence.

Published evidence is not regenerated to match later code. Corrections are appended and clearly
separated.

## Accepted maintenance

- correctness, security, portability, CI and dependency-compatibility fixes;
- setup, evidence readability, validation and reproduction improvements;
- contributor experience and narrowly scoped named-agent integrations backed by a concrete need;
- documentation or research notes that preserve the v1 protocol boundary.

New behavior requires tests. Model-backed results must name the agent, model, harness, prompt/tool
configuration, date, repetitions and independent DOM outcome.

## Expansion gate

Additional tasks, mutations, generic adapters, UI surfaces, dependencies or schemas require a
reproducible Issue, experiment failure, user need or registered hypothesis. New Agent-facing
behavioral compatibility work belongs in the workspace incubator until its kill gates pass; it does
not automatically become BAR v2 or change the frozen 3×4 protocol.

## Stop and escalation

Pause proposals that rewrite v1 evidence, blur synthetic and real-agent claims, require framework
changes throughout the core, or duplicate an established benchmark/debugging platform. A frozen
interface change requires an explicit versioning decision and release plan.
