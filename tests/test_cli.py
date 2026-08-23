import json
from unittest.mock import Mock

import pytest
from playwright.sync_api import Error as PlaywrightError

import browser_agent_regression.cli as cli_module
from browser_agent_regression.cli import _masked_windows_input, build_parser


def test_masked_windows_input_shows_feedback_and_supports_backspace(capsys) -> None:
    characters = iter(["s", "k", "x", "\b", "y", "\r"])

    result = _masked_windows_input("Key: ", read_character=lambda: next(characters))

    assert result == "sky"
    assert capsys.readouterr().out == "Key: ***\b \b*\n"


def test_demo_defaults_to_a_short_local_report() -> None:
    args = build_parser().parse_args(["demo"])

    assert args.runs == 1
    assert args.output.as_posix() == "runs/demo-report.json"
    assert args.task is None
    assert args.headed is False


def test_version_is_exposed(capsys) -> None:
    with pytest.raises(SystemExit) as exc_info:
        build_parser().parse_args(["--version"])

    assert exc_info.value.code == 0
    assert "1.0.0" in capsys.readouterr().out


@pytest.mark.browser
def test_demo_runs_without_resolving_a_provider_key(tmp_path, monkeypatch, capsys) -> None:
    key_resolver = Mock(side_effect=AssertionError("demo must not resolve an API key"))
    monkeypatch.setattr(cli_module, "_resolve_deepseek_api_key", key_resolver)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    output = tmp_path / "demo.json"

    result = cli_module.main(
        [
            "demo",
            "--runs",
            "1",
            "--task",
            "preferences.notifications.v1",
            "--output",
            str(output),
        ]
    )

    key_resolver.assert_not_called()
    assert result == 0
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["command"] == "demo"
    assert report["evidence_kind"] == "synthetic-calibration"
    assert report["configuration"]["runs_per_driver_task_variant"] == 1
    assert len(report["attempts"]) == 4
    assert report["regressions"][0]["task_id"] == "preferences.notifications.v1"
    assert "api_key" not in json.dumps(report).casefold()
    rendered = capsys.readouterr().out
    assert "no API key" in rendered
    assert "Demo result: PASS" in rendered
    assert "not a model or browser-agent benchmark result" in rendered

    assert cli_module.main(["verify", "--report", str(output)]) == 0


@pytest.mark.browser
def test_doctor_confirms_browser_and_fixtures(capsys) -> None:
    assert cli_module.main(["doctor"]) == 0
    rendered = capsys.readouterr().out
    assert "browser-agent-regression=1.0.0" in rendered
    assert "chromium=ready" in rendered


def test_missing_browser_error_is_actionable(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        cli_module,
        "_run_matrix",
        Mock(side_effect=PlaywrightError("BrowserType.launch: Executable doesn't exist")),
    )

    assert cli_module.main(["demo", "--task", "checkout.basic.v1"]) == 2
    assert "python -m playwright install chromium" in capsys.readouterr().err
