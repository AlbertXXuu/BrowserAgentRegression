# Research landscape: web-agent regression evidence

Search date: **2026-08-28**

This audit asks which parts of browser-agent regression are already supplied by adjacent research
and tools. It uses author publications, official documentation and official repositories. Repository
claims are pinned to the inspected commit. Popularity, repository activity and vendor language are
not treated as evidence of adoption or effectiveness.

Two terms are intentionally narrow:

- **First-failure localization** means identifying the earliest causally supported failing step in
  an execution trajectory. A first unmet outcome checkpoint or first text diff is useful evidence,
  but is not automatically a causal diagnosis.
- **Minimization** means rerunning subsets of a compound software change until a verified smaller
  failure-inducing change remains. Generating mutations, showing a diff or shortening a trajectory
  does not by itself meet this definition.

“Not established” below means the reviewed primary source did not document the capability. It is
not a claim that no unreviewed version, extension or private feature has it.

## Primary-source snapshot

| Work | Dated primary source inspected |
| --- | --- |
| WAREX | [Microsoft Research publication](https://www.microsoft.com/en-us/research/publication/warex-web-agent-reliability-evaluation-on-existing-benchmarks/), TMLR, April 2026 |
| BrowserGym | [paper v4](https://arxiv.org/abs/2412.05467), 2025-02-28; [official repository at `9e779f0`](https://github.com/ServiceNow/BrowserGym/tree/9e779f087de9a65668b6974d11f9ce9816026e96) |
| WebArena | [paper v4](https://arxiv.org/abs/2307.13854), 2024-04-16; [canonical repository at `dce0468`](https://github.com/web-arena-x/webarena/tree/dce04686a56253aefba7b18a4fa0937cf1dc987b) |
| agent-browser | [official repository at `fbd046c`](https://github.com/vercel-labs/agent-browser/tree/fbd046c23a2c1156891bda294aaaee715c23b3f1), inspected 2026-08-28 |
| Playwright ARIA snapshots | [official documentation](https://playwright.dev/docs/aria-snapshots), inspected 2026-08-28; [repository at `9a450a2`](https://github.com/microsoft/playwright/tree/9a450a2ff5f939fed4fb0e6aed3a7e3292db7b8f) |
| LangSmith | [official complex-agent evaluation tutorial](https://docs.langchain.com/langsmith/evaluate-complex-agent), inspected 2026-08-28 |
| Promptfoo | [official assertion documentation](https://www.promptfoo.dev/docs/configuration/expected-outputs/), [CI documentation](https://www.promptfoo.dev/docs/integrations/ci-cd/) and [repository at `2c45764`](https://github.com/promptfoo/promptfoo/tree/2c45764ca1daf4587c83d68b940ba0eb14cb7ac4), inspected 2026-08-28 |
| DeepEval | [official task-completion documentation](https://deepeval.com/docs/metrics-task-completion) and [repository at `9404fb2`](https://github.com/confident-ai/deepeval/tree/9404fb2d47fd3b0f87b25de9e46fe89bc0b922a7), inspected 2026-08-28 |
| AgentRx | [paper v1](https://arxiv.org/abs/2602.02475), 2026-02-02; [official repository at `f228165`](https://github.com/microsoft/AgentRx/tree/f228165bfec60a801fd5fedd9d8ffe0f9de0c69d) |
| WebMCP testing | [`@webmcpregistry/testing` repository at `c6ecda0`](https://github.com/Skopaq-AI/webmcpregistry/tree/c6ecda04048ca6537789f7de641b735a8fae8ed5), inspected 2026-08-28 |

The final row audits the concrete third-party WebMCP Registry testing package, not the WebMCP draft
API in general. Its repository calls a 12-scenario package a “W3C conformance suite”; this audit does
not treat that wording as W3C certification.

## Source facts

| Work | Problem and evidence exposed by the source | Change focus | First-failure localization | Verified change minimization |
| --- | --- | --- | --- | --- |
| **WAREX** | Adds a plug-and-play proxy to existing WebArena, WebVoyager and REAL tasks, injects client, server, network, site-modification and XSS conditions, and reports task-success degradation and failure-recovery data. | Directly varies the environment/software conditions; the same harness can compare agents. Task semantics and success evaluation come from the host benchmark. | Failure/recovery trajectories are an output, but automatic causal first-step localization is not established by the reviewed publication. | Not established. |
| **BrowserGym** | Provides a unified Gym-like observation/action interface and experiment layer across multiple web benchmarks. Tasks return rewards/results, and the ecosystem publishes experiment traces. Its paper compares six models across six benchmarks. | Primarily agent/model comparison on benchmark environments; callers can implement new tasks and environments. | Trace collection and benchmark outcomes are established; a general cross-version causal localizer is not. | Not established. |
| **WebArena** | Supplies self-hosted, functional websites and 812 long-horizon tasks evaluated for functional correctness. The canonical repository contains an evaluation harness and publishes execution trajectories. | Primarily agent comparison on a reset fixed environment, not baseline/candidate application versions. | Trajectories are available, but the source does not establish automatic causal first-failure attribution. | Not established. |
| **agent-browser `diff`** | Compares current/saved accessibility snapshots, screenshots, or two URLs; it can scope diffs by selector and can record browser traces. | Direct software/URL comparison; an LLM agent is optional. Task success and application-state meaning are caller supplied. | It localizes structural or pixel differences and records traces, not the earliest causally supported task failure. | Not established. |
| **Playwright ARIA snapshots** | `toMatchAriaSnapshot` compares a page or locator accessibility tree with a YAML template. Matching is order-sensitive; snapshot updates can emit reviewable patches. | Direct software-change regression testing; no agent is required. | It identifies an accessibility-tree mismatch. Task-trajectory cause and external state transitions require additional tests. | Not established. |
| **LangSmith** | Documents final-response, trajectory and isolated single-step evaluators over datasets and agent runs, including expected tool-call paths. | Compares agent/application configurations; web state semantics are encoded by caller evaluators. | A caller can test a specific step or trajectory. Automatic causal first-failure localization is not established by the reviewed tutorial. | Not established. |
| **Promptfoo** | Runs declarative evaluations with deterministic, custom and model-graded assertions, supports trace evidence and generated red-team cases, and provides CI exit/report workflows. | Compares prompts, providers, agents and application targets. A web application state oracle is caller supplied. | Trace assertions can expose failed spans or actions; a general causal first-failure localizer is not established. | Test generation is established; software-version change minimization is not. |
| **DeepEval** | Its documented Task Completion metric uses an LLM judge over the full trace to score alignment between a task and outcome; the docs also expose trajectory and component-level evaluation families. | Primarily agent/application evaluation; deterministic external web state must be supplied separately. | The reviewed metric scores a whole-run outcome and reason. It does not establish deterministic causal first-step localization. | Not established. |
| **AgentRx** | Normalizes failed trajectories, synthesizes invariants, checks them stepwise, and uses an LLM judge plus an auditable validation log to identify a critical step and a grounded failure category. The paper evaluates 115 annotated failed trajectories across three domains. | Diagnoses agent-run failures across domains; it does not generate paired web-application versions. | **Established**, subject to its invariant synthesis, retained trace and LLM-judge assumptions. | Structural minimization of a software change is not established. |
| **WebMCP testing** | Generates schema-derived inputs; snapshots and diffs tool contracts; marks specified removals/schema/safety changes as breaking; generates schema mutations; and runs conformance scenarios without LLM calls. | Direct agent-facing software-contract testing at WebMCP tool/schema level; separate eval tooling can assess tool selection. | Contract rules identify the changed tool/schema field, not a causal point in an agent execution trajectory. | Mutation generation and mutation score are established; verified subset minimization of a compound application change is not. |

## Interpretation for Browser Agent Regression

The statements in this section are **inferences from the sources**, not source-reported results.

| Neighbour | What BAR should reuse or treat as a baseline | Boundary the comparison leaves open |
| --- | --- | --- |
| WAREX | Treat it as the strongest end-to-end perturbation benchmark and reuse its causal experimental framing. | Whether developer-owned version pairs and task/state contracts add value beyond benchmark-owned tasks. |
| BrowserGym and WebArena | Reuse them for broad agent execution and functional outcome precedents; do not build another benchmark runtime. | They do not establish a lightweight release gate for a developer's application change. |
| agent-browser and Playwright ARIA | Treat URL/snapshot diff and ARIA assertions as the cheapest baselines. | Whether a task/state oracle improves precision enough to justify additional authoring and runtime cost. |
| LangSmith, Promptfoo and DeepEval | Reuse generic datasets, traces, assertions, reporting and CI integration where appropriate; do not build another general eval platform. | They leave web-version fixtures, deterministic state/side-effect semantics and controlled UI mutations to the caller. |
| AgentRx | Treat it as the first-failure diagnosis baseline; BAR must not claim that trajectory localization is missing from prior work. | Whether deterministic task contracts can localize a version-induced failure without making an LLM judge the final oracle. |
| WebMCP testing | Reuse schema contract, generated-input and mutation machinery for optional WebMCP surfaces; do not reimplement it. | Tool/schema compatibility is narrower than an end-user task that may cross ordinary UI, backend state and optional tools. |

## BAR v1 factual boundary

The frozen v1 evidence compares two deterministic drivers on three packaged tasks and four controlled
UI variants. It independently checks ordered DOM outcomes and records `first_failed_checkpoint`.
The [failure taxonomy](failure-taxonomy.md) makes the limit explicit: this field localizes the first
unmet **outcome**, not the causal agent step.

v1 does not provide an arbitrary developer application-version pair, retained event-level agent
trajectory, compound-change minimizer, general mutation generator, WebMCP contract diff or evidence
that unfamiliar developers can author useful task contracts. None of those capabilities may be
presented as a current BAR feature.

## Remaining gap is a hypothesis, not a novelty claim

The reviewed sources do not establish one workflow that combines all of the following:

1. a developer-authored task contract spanning goal state, protected invariants and forbidden side
   effects across baseline and candidate versions of the developer's own application;
2. an independent reference executor that separates application unreachability from agent
   regression;
3. the same labelled cases evaluated by deterministic ARIA/WebMCP baselines and agent runs;
4. trajectory evidence sufficient for causal first-failure attribution; and
5. rerun-backed reduction of a compound software change to a smaller failure-inducing mutation set.

This conjunction is an **unverified research gap**. Search coverage is finite, capabilities can have
changed after 2026-08-28, and some systems may support the combination through user code or private
features. The audit supplies no demand evidence and no proof that combining the pieces is useful,
novel or publishable.

The next falsifiable question is therefore not “can BAR implement these features?” It is:

> On preregistered version-change cases, does a task-contract detector add enough correct
> compatibility decisions and actionable localization over Playwright ARIA plus ordinary end-to-end
> tests to justify its authoring, execution and maintenance cost?

If the simpler baseline is sufficient, WebMCP testing already covers the relevant interface, a
re-audit finds an equivalent end-to-end workflow, or unfamiliar developers cannot author and use the
contract, the proposed line should be merged into existing tooling or stopped.
