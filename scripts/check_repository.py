"""Validate release-critical repository and evidence invariants."""

from __future__ import annotations

import json
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import browser_agent_regression  # noqa: E402
from browser_agent_regression.runner import validate_report  # noqa: E402

REQUIRED = (
    "README.md",
    "README.zh-CN.md",
    "LICENSE",
    "NOTICE",
    "CHANGELOG.md",
    "CITATION.cff",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "PROJECT.md",
    "MANIFEST.in",
    "pyproject.toml",
    ".github/workflows/ci.yml",
    "docs/evidence-schema.md",
    "docs/studio.md",
    "src/browser_agent_regression/assets/brand/alvenx-wordmark.svg",
    "src/browser_agent_regression/assets/brand/alvenx-monogram.svg",
    "src/browser_agent_regression/assets/evidence/studio-v1.json",
    "src/browser_agent_regression/assets/fonts/InstrumentSans-wdth-wght.woff2",
    "docs/evidence/v1.0.0-oracle.json",
    "docs/evidence/v1.0.0-calibration.json",
)
EVIDENCE_TO_VALIDATE = (
    "docs/evidence/v1.0.0-oracle.json",
    "docs/evidence/v1.0.0-calibration.json",
    "docs/evidence/phase0-slice-03-oracle.json",
    "docs/evidence/phase0-slice-03-calibration.json",
    "docs/evidence/phase0-deepseek-gate-c-02.json",
)
FORBIDDEN_PARTS = {
    ".playwright-cli",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "runs",
}


def main() -> int:
    errors: list[str] = []
    for relative in REQUIRED:
        if not (ROOT / relative).is_file():
            errors.append(f"missing required file: {relative}")

    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    declared = metadata["project"]["version"]
    if declared != browser_agent_regression.__version__:
        errors.append(
            f"version mismatch: pyproject={declared}, "
            f"package={browser_agent_regression.__version__}"
        )

    try:
        tracked_output = subprocess.run(
            ["git", "ls-files"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        tracked = [Path(line) for line in tracked_output.splitlines()]
    except (OSError, subprocess.CalledProcessError) as exc:
        tracked = []
        errors.append(f"cannot inspect tracked files: {exc}")
    for path in tracked:
        if FORBIDDEN_PARTS.intersection(path.parts):
            errors.append(f"generated path is tracked: {path.as_posix()}")

    for relative in EVIDENCE_TO_VALIDATE:
        path = ROOT / relative
        if not path.is_file():
            continue
        try:
            validate_report(json.loads(path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, ValueError) as exc:
            errors.append(f"invalid evidence {relative}: {exc}")

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(
        f"repository=PASS version={declared} tracked_files={len(tracked)} "
        f"validated_evidence={len(EVIDENCE_TO_VALIDATE)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
