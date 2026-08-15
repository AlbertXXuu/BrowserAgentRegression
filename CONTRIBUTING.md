# Contributing

Browser Agent Regression is in a time-boxed Phase 0. The most valuable contributions are
reproducible runs and concrete feedback from developers who maintain browser agents.
Use the
[Phase 0 independent-run form](https://github.com/AlbertXXuu/BrowserAgentRegression/issues/new?template=phase0-run.yml)
for a clean-environment result or blocker.

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
```

The optional real-agent path is installed separately with
`python -m pip install -e ".[dev,agent]"`. Never use a paid provider run as a substitute for the
offline checks above.

When reporting a run, include the operating system, Python version, exact command, and generated
JSON report. Remove credentials and private URLs before attaching evidence.
