# BrowserAgentRegression v1.1.0 final release audit

- Status: **CANDIDATE — Linux CI required before PASS**
- Audit date: `2026-08-30` (`Asia/Shanghai`)
- Audited source commit: `80059998d22f2bedd92174366d0e39779a3b332a`
- Target release: `v1.1.0`

## Release meaning

`v1.1.0` is the presentation and maintenance closure release built on the unchanged `v1.0.0`
research/evidence baseline. It adds the evidence-driven Studio presentation, shared AlvenX brand,
documentation, packaging, responsive/accessibility work, and explicit version identity. It does
not add an agent, task, variant, mutation system, benchmark, or research conclusion.

## Environment and method

The source commit was cloned into a separate local directory and audited with its source path
explicitly selected. Windows validation used Windows NT `10.0.26200.0`, PowerShell `7.6.4`, Python
`3.11.0`, Playwright `1.62.0`, and Chromium `151.0.7922.34`. Built distributions were installed in
two new isolated environments, one from the wheel and one from the source distribution.

Linux is not inferred from the Windows result. This audit remains a candidate until the complete
pull-request head passes the repository's GitHub Actions matrix on Ubuntu.

## Readiness checklist

| Surface | Result | Evidence |
| --- | --- | --- |
| Separate fresh clone | PASS | Clone HEAD exactly matched `80059998d22f2bedd92174366d0e39779a3b332a`; worktree was clean before ignored build output. |
| Package/runtime identity | PASS | Project/import metadata, `browser-agent-regression --version`, Studio, README files, and changelog identify software `1.1.0`; calibration remains evidence `v1.0.0`. |
| Source distribution | PASS | Built and installed in a new environment with dependencies; metadata and CLI both reported `1.1.0`. |
| Wheel | PASS | Built and installed in a new environment; `pip check`, CLI identity, browser doctor, installed-package demo, and frozen-report verification passed. |
| Windows/local tests | PASS | `29` pytest tests passed, including the browser-marked path. Ruff passed. |
| Repository checker | PASS | Version `1.1.0`, `81` tracked files, and `5` committed evidence records validated. |
| Deterministic core action | PASS | Installed wheel completed `12` controlled attempts and detected/localized `3/3` induced regressions; frozen calibration verification passed `36` attempts. |
| Linux CI | PENDING | Required on the complete `closure/v1.1.0` pull-request head before this audit may become PASS. |
| README / README.zh-CN | PASS | Both are present, coherent with the `1.1.0` candidate identity, and preserve the frozen protocol/reproduction boundary. |
| CHANGELOG / MAINTENANCE | PASS | `CHANGELOG.md` and `docs/MAINTENANCE.md` are present and define the bounded closure release plus maintenance-only follow-up. |
| PORTFOLIO | PASS | Problem, original decisions, hardest bugs, results, evidence limits, negative findings, and individual contribution are recorded. |
| LICENSE / SECURITY / CITATION | PASS | `LICENSE`, `NOTICE`, `SECURITY.md`, and `CITATION.cff` are present and packaged where applicable. |
| Studio | PASS | Evidence, Tasks, and Method remain reachable; the hero uses committed checkpoint pass rates and names the first failed checkpoint rather than showing a decorative orbit. |
| Responsive/accessibility | PASS | Chromium at 900/1024/1280/1440/1600 px found no page overflow; critical targets are at least 44 px, keyboard focus is visible, and shared header geometry/styles match. |
| Version labels | PASS | `Studio v1.1.0` and `Evidence v1.0.0` are deliberately separate. |
| Evidence and documentation links | PASS | Repository-local links passed the checker; dated README/portfolio external links returned HTTP 200. |
| Historical v1 integrity | PASS | Annotated tag, peeled commit, frozen calibration/oracle blobs, and schema blob match the closure baseline below. |
| Website links | PASS with publication sequencing | `https://alvenx.com` and repository links return HTTP 200; the local production website candidate's project route and repository links passed its P9 browser audit and are deployed in P11. |
| OG/social | PASS | GitHub exposes the custom 1280×640 repository image; fetched SHA-256 `db1f3e2a8708337368db52db93bed6d4f07da8ee5c2ef76d25a890c863182eda`. |

## Distribution artifacts

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| `browser_agent_regression-1.1.0-py3-none-any.whl` | 137,954 | `4f3198f955ff7d1cea8e4accf85ba9b86214591659a50a68d6d2f337a094e5ab` |
| `browser_agent_regression-1.1.0.tar.gz` | 5,398,283 | `805aed55a20dce1cac873977399b8dce8ef2aac4040450fae107a1ef7f98b4bd` |

Archive inspection confirmed Python source, CLI entry point, LICENSE/NOTICE, and packaged Studio
brand/font/evidence assets. The source archive also contains all five Studio screenshots and their
viewport audit, avoiding an incomplete screenshot manifest.

## Frozen v1.0.0 anchors

| Anchor | Expected and observed object ID |
| --- | --- |
| Annotated `refs/tags/v1.0.0` | `f307d4be918c5893cbf275c11701d17f353cd13a` |
| Peeled v1.0.0 commit | `2949c56fe4d68ee7150f7ab819cef461f5116d3d` |
| Calibration blob | `44e22b2e64d1776514441312d6660ad3aa535675` |
| Oracle blob | `ccb83fa552ecd4a6811a634352a5c94da567b832` |
| Evidence-schema blob | `7b7d5fb8129aef99dc0caa765a818cf471ceb7c7` |

All expected IDs equal the objects reachable from the audited candidate. No historical ref,
protocol artifact, or frozen evidence object changed.

## Findings and disposition

- **P0 blockers:** `0` locally; final count is contingent on Linux CI.
- **P1 blockers:** `0` locally; final count is contingent on Linux CI.
- **P2 accepted:** the old concept-hero selectors remain as unreachable declarations inside the
  existing minified CSS literal, but the corresponding DOM and animation are absent. Removing
  isolated tokens from that large generated-like literal immediately before release carries more
  regression risk than value and cannot affect runtime behavior.
- **P2 accepted:** sdist creation prints normal `MANIFEST.in` exclusions for bytecode and
  `__pycache__`; neither file class enters the archive.

## Gate decision

Local release readiness is **PASS**. Overall P10 readiness remains **PENDING** until the exact
pull-request head passes every Linux CI job. No tag or release may be created from this candidate
before that evidence exists.
