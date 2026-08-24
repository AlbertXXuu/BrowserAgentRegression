# Changelog

All notable changes are documented here. Releases use semantic versioning.

## [Unreleased]

### Added

- Added a dependency-free, loopback-only `studio` command with the AlvenX product design language,
  preserved v1 evidence visualization, and an in-memory zero-key demo control.
- Bundled integrity-checked AlvenX masters, Instrument Sans, and a compact evidence fallback so the
  Studio remains functional from an installed wheel.

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
[Unreleased]: https://github.com/AlbertXXuu/BrowserAgentRegression/compare/v1.0.0...HEAD
