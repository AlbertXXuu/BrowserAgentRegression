# Browser Agent Regression Studio

The Studio is the local visual surface for the v1 evidence contract. It presents the committed
calibration, runs the same deterministic matrix in memory, and uses the CLI's scoring path.

```bash
python -m pip install -e .
python -m playwright install chromium
browser-agent-regression studio
```

The interface opens at `http://127.0.0.1:7870/`. Use `--no-open` when you want to select the browser
yourself, or `--port 0` to let the operating system choose a free loopback port.

The initial view reduces `docs/evidence/v1.0.0-calibration.json` into four reviewable signals:

- clean reference/candidate parity;
- popup-overlay success-rate delta;
- first failed checkpoint;
- checkpoint agreement across repetitions.

**Run local demo** executes the same public, synthetic `demo` matrix in memory: one repetition,
three tasks, two drivers, and two variants (12 attempts). Use the CLI `demo --output ...` command
when you want a durable new report.

The listener rejects non-loopback hosts. Responses set a same-origin content security policy, the
bundled Instrument Sans font and AlvenX masters are served locally, and the method panel explains
how deterministic calibration relates to model-backed experiments.
