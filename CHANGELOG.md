# Changelog

All notable changes are documented here. Releases use semantic versioning.

## [1.1.2] - 2026-08-31

### Fixed

- Keep all three checkpoint nodes in each Studio row equal in height and align their marker,
  percentage, and annotation tracks across the supported desktop viewport range.
- Allow long checkpoint IDs and the first-divergence annotation to wrap inside their own grid cells
  without overlap or horizontal overflow.

## [1.1.1] - 2026-08-31

### Fixed

- Correct the current-software quick start to clone `v1.1.1`, where the documented Studio exists,
  while retaining `v1.0.0` as the immutable research and evidence reproduction baseline.

## [1.1.0] - 2026-08-31

### Added

- Added a dependency-free, loopback-only `studio` command with the AlvenX product design language,
  preserved v1 evidence visualization, and an in-memory zero-key demo control.
- Bundled integrity-checked AlvenX masters, Instrument Sans, and a compact evidence fallback so the
  Studio remains functional from an installed wheel.

### Changed

- Normalize current software, runtime, Studio, and documentation identity as the `v1.1.0`
  presentation and maintenance closure release while preserving the unchanged `v1.0.0`
  research/evidence baseline.

## [1.0.0] - 2026-08-24

### Added

- Stable evidence schema `1.0` and protocol identifier.
- `verify` command for internal accounting, checkpoint, fixture-hash, and credential-field checks.
- `doctor` command that verifies the matching Chromium build and a live packaged fixture.
- Actionable exit code `2` when Playwright is installed without its matching browser binary.
- Python 3.11–3.13 unit CI, browser integration CI, evidence checks, and installed-wheel smoke tests.
- Versioned deterministic v1 oracle and calibration evidence.

### Changed

- Declared the tested local harness and CLI as v1 while retaining the unvalidated external-adoption
  question as an explicit project boundary.
- Updated packaging metadata, bilingual quick start, release documentation, and repository checks.

### Compatibility

- Phase 0 schema `0.2` evidence remains accepted by `verify`.
- Phase 0 schema `0.1` files remain historical artifacts but are outside the v1 compatibility promise.

[1.0.0]: https://github.com/AlbertXXuu/BrowserAgentRegression/releases/tag/v1.0.0
[1.1.0]: https://github.com/AlbertXXuu/BrowserAgentRegression/releases/tag/v1.1.0
[1.1.1]: https://github.com/AlbertXXuu/BrowserAgentRegression/releases/tag/v1.1.1
[1.1.2]: https://github.com/AlbertXXuu/BrowserAgentRegression/compare/v1.1.1...v1.1.2
