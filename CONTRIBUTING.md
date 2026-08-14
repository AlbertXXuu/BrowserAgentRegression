# Contributing

Browser Agent Regression is in a time-boxed Phase 0. The most valuable contributions are
reproducible runs and concrete feedback from developers who maintain browser agents.

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

When reporting a run, include the operating system, Python version, exact command, and generated
JSON report. Remove credentials and private URLs before attaching evidence.
