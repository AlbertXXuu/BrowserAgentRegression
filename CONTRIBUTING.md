# Contributing

Browser Agent Regression has a stable v1 protocol. Useful contributions include reproducible
regressions and concrete feedback from developers who maintain browser agents. Use the
[workflow-feedback form](https://github.com/AlbertXXuu/BrowserAgentRegression/issues/new?template=workflow-feedback.yml)
for setup, evidence, and adapter-integration feedback.

## Before opening a change

- Read the scope, non-goals, and gates in [PROJECT.md](PROJECT.md).
- Open an issue before adding a framework, service, dependency, or generic adapter layer.
- Keep synthetic calibration evidence clearly separated from real-agent results.

## Local checks

```bash
python -m pip install -e ".[dev]"
python -m playwright install chromium
python -m ruff check .
python -m pytest
python scripts/check_repository.py
python -m build
```

Install the optional real-agent path with `python -m pip install -e ".[dev,agent]"`. Run the
built-in calibration checks before comparing a paid provider configuration.

When reporting a run, include the operating system, Python version, exact command, and generated
JSON report. Remove credentials and private URLs before attaching evidence.
Run `browser-agent-regression verify --report <path>` before sharing it.
