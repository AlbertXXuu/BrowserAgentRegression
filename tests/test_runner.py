import json
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

from browser_agent_regression.runner import (
    PROTOCOL_ID,
    TASK_CHECKPOINTS,
    TASKS,
    VARIANTS,
    Attempt,
    build_report,
    find_regressions,
    run_attempt,
    summarize,
    validate_report,
)
from browser_agent_regression.server import FixtureServer


@pytest.mark.browser
def test_reference_oracle_survives_all_variants() -> None:
    with FixtureServer() as server, sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            attempts = [
                run_attempt(
                    browser,
                    server,
                    task_id=task_id,
                    driver="reference",
                    variant=variant,
                )
                for task_id in TASKS
                for variant in VARIANTS
            ]
        finally:
            browser.close()

    assert all(attempt.passed for attempt in attempts)


@pytest.mark.browser
def test_catalog_fixture_preserves_the_selected_product() -> None:
    with FixtureServer() as server, sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        try:
            page.goto(server.url("catalog.html"))
            page.get_by_label("Search products").fill("desk lamp")
            page.get_by_role("button", name="Search catalog").click()
            page.get_by_role("button", name="View Harbor Desk Lamp").click()
            page.get_by_role("button", name="Save Harbor Desk Lamp").click()

            assert page.locator("#saved-status").text_content() == (
                "Harbor Desk Lamp saved to shortlist"
            )
        finally:
            browser.close()


@pytest.mark.browser
def test_preferences_fixture_preserves_the_untouched_setting() -> None:
    with FixtureServer() as server, sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        try:
            page.goto(server.url("preferences.html"))
            page.get_by_label("Product updates").uncheck()
            page.get_by_label("Security alerts").check()
            page.get_by_role("button", name="Save preferences").click()

            assert page.get_by_label("Weekly summary").is_checked()
            assert page.get_by_role("status").text_content() == "Preferences saved"
        finally:
            browser.close()


@pytest.mark.browser
def test_calibration_detects_popup_regression_only() -> None:
    with FixtureServer() as server, sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            attempts = [
                run_attempt(
                    browser,
                    server,
                    task_id=task_id,
                    driver=driver,
                    variant=variant,
                )
                for task_id in TASKS
                for driver in ("reference", "popup-blind")
                for variant in ("clean", "popup-overlay")
            ]
        finally:
            browser.close()

    report = build_report(
        attempts,
        command="calibrate",
        runs=1,
        tasks=list(TASKS),
        variants=["clean", "popup-overlay"],
    )

    assert report["schema_version"] == "1.0"
    assert report["protocol_id"] == PROTOCOL_ID
    assert report["tool_version"] == "1.1.3"
    assert report["task_ids"] == list(TASKS)
    assert set(report["fixture_sha256"]) == {
        "catalog.html",
        "catalog.json",
        "checkout.html",
        "checkout.json",
        "preferences.html",
        "preferences.json",
    }
    regressions = {item["task_id"]: item for item in report["regressions"]}
    assert set(regressions) == set(TASKS)
    assert regressions["checkout.basic.v1"]["failed_checkpoint"] == "checkout.email.accepted"
    assert regressions["catalog.find-and-save.v1"]["failed_checkpoint"] == (
        "catalog.query.applied"
    )
    assert regressions["preferences.notifications.v1"]["failed_checkpoint"] == (
        "preferences.product_updates.disabled"
    )
    assert all(item["delta"] == -1.0 for item in regressions.values())
    assert all(item["failure_checkpoint_agreement"] == 1.0 for item in regressions.values())


@pytest.mark.parametrize("model", ["deepseek-v4-flash", "deepseek-v4-pro"])
def test_real_agent_report_preserves_identity_without_credentials(model) -> None:
    attempt = Attempt(
        task_id="preferences.notifications.v1",
        driver=f"browser-use/{model}",
        variant="clean",
        passed=True,
        duration_ms=100.0,
        checkpoints={
            "preferences.product_updates.disabled": True,
            "preferences.security_alerts.enabled": True,
            "preferences.saved": True,
        },
        first_failed_checkpoint=None,
        error=None,
    )
    report = build_report(
        [attempt],
        command="deepseek",
        runs=1,
        tasks=["preferences.notifications.v1"],
        variants=["clean"],
        evidence_kind="real-agent",
        run_identity={
            "agent": "browser-use",
            "model": model,
            "credential_source": "hidden interactive prompt",
        },
    )

    assert report["schema_version"] == "1.0"
    assert report["evidence_kind"] == "real-agent"
    assert report["configuration"]["run_identity"]["agent"] == "browser-use"
    assert "api_key" not in json.dumps(report).lower()
    validate_report(report)


def _single_success_report() -> dict[str, object]:
    attempt = Attempt(
        task_id="checkout.basic.v1",
        driver="reference",
        variant="clean",
        passed=True,
        duration_ms=10.0,
        checkpoints={name: True for name in TASK_CHECKPOINTS["checkout.basic.v1"]},
        first_failed_checkpoint=None,
        error=None,
    )
    return build_report(
        [attempt],
        command="oracle",
        runs=1,
        tasks=["checkout.basic.v1"],
        variants=["clean"],
    )


def test_report_validator_accepts_a_consistent_report() -> None:
    validate_report(_single_success_report())


def test_report_validator_rejects_tampered_summary() -> None:
    report = _single_success_report()
    report["summaries"][0]["successes"] = 0

    with pytest.raises(ValueError, match="summary accounting"):
        validate_report(report)


def _frozen_report(name="v1.0.0-calibration.json"):
    path = Path(__file__).resolve().parents[1] / "docs" / "evidence" / name
    return json.loads(path.read_text(encoding="utf-8"))


def _recompute_accounting(report) -> None:
    attempts = [Attempt(**raw) for raw in report["attempts"]]
    report["summaries"] = summarize(attempts)
    report["regressions"] = (
        find_regressions(report["summaries"])
        if report["command"] in {"calibrate", "demo"}
        else []
    )


@pytest.mark.parametrize("runs", [0, -1, 1.0, True, False])
def test_report_validator_requires_an_integer_run_count(runs) -> None:
    report = _single_success_report()
    report["configuration"]["runs_per_driver_task_variant"] = runs

    with pytest.raises(ValueError, match="run count must be a positive integer"):
        validate_report(report)


def test_report_validator_rejects_inflated_repeat_count() -> None:
    report = _frozen_report()
    report["configuration"]["runs_per_driver_task_variant"] = 1000

    with pytest.raises(ValueError, match="attempt coverage mismatch"):
        validate_report(report)


@pytest.mark.parametrize(
    "mutation",
    [
        "drop-failed",
        "drop-driver",
        "drop-task",
        "drop-variant",
        "drop-cell",
        "extra-attempt",
        "balanced-replacement",
    ],
)
def test_report_validator_rejects_incomplete_or_overfilled_cells(mutation) -> None:
    report = _frozen_report()
    original = report["attempts"]
    first = original[0]
    if mutation == "drop-failed":
        report["attempts"] = [raw for raw in original if raw["passed"]]
    elif mutation == "drop-driver":
        report["attempts"] = [raw for raw in original if raw["driver"] != "popup-blind"]
    elif mutation == "drop-task":
        report["attempts"] = [raw for raw in original if raw["task_id"] != first["task_id"]]
    elif mutation == "drop-variant":
        report["attempts"] = [raw for raw in original if raw["variant"] != first["variant"]]
    elif mutation == "drop-cell":
        report["attempts"] = original[3:]
    elif mutation == "extra-attempt":
        report["attempts"] = [*original, first.copy()]
    else:
        report["attempts"] = original.copy()
        report["attempts"][-1] = first.copy()
        assert len(report["attempts"]) == len(original)
    _recompute_accounting(report)

    with pytest.raises(ValueError, match="attempt coverage mismatch"):
        validate_report(report)


@pytest.mark.parametrize("dimension", ["tasks", "variants"])
def test_report_validator_rejects_declared_but_unexecuted_conditions(dimension) -> None:
    report = _single_success_report()
    report["configuration"][dimension].append(
        "catalog.find-and-save.v1" if dimension == "tasks" else "layout-shift"
    )

    with pytest.raises(ValueError, match="attempt coverage mismatch"):
        validate_report(report)


@pytest.mark.parametrize("command", ["demo", "calibrate", "deepseek"])
def test_report_validator_rejects_a_driver_from_another_command(command) -> None:
    report = _single_success_report()
    report["command"] = command
    if command == "deepseek":
        report["evidence_kind"] = "real-agent"
        report["configuration"]["run_identity"] = {
            "agent": "browser-use",
            "model": "deepseek-v4-flash",
        }
    else:
        report["attempts"][0]["driver"] = "browser-use/deepseek-v4-flash"
    _recompute_accounting(report)

    with pytest.raises(ValueError, match="driver.*command"):
        validate_report(report)


@pytest.mark.parametrize("command", ["oracle", "calibrate", "demo", "deepseek"])
def test_report_validator_rejects_mislabeled_evidence(command) -> None:
    report = _single_success_report()
    report["command"] = command
    report["evidence_kind"] = "synthetic-calibration" if command == "deepseek" else "real-agent"

    with pytest.raises(ValueError, match="evidence kind.*command"):
        validate_report(report)


@pytest.mark.parametrize(
    "identity",
    [
        None,
        [],
        {},
        {"agent": "other", "model": "deepseek-v4-flash"},
        {"agent": "browser-use", "model": "unknown"},
    ],
)
def test_report_validator_rejects_an_invalid_real_agent_identity(identity) -> None:
    report = _frozen_report("phase0-deepseek-gate-c-02.json")
    report["configuration"]["run_identity"] = identity

    with pytest.raises(ValueError, match="run identity|agent|model"):
        validate_report(report)


def test_report_validator_binds_real_agent_driver_to_declared_model() -> None:
    report = _frozen_report("phase0-deepseek-gate-c-02.json")
    report["attempts"][0]["driver"] = "browser-use/deepseek-v4-pro"
    _recompute_accounting(report)

    with pytest.raises(ValueError, match="driver.*command"):
        validate_report(report)


def test_report_validator_accepts_reordered_attempts() -> None:
    report = _frozen_report()
    report["attempts"].reverse()

    validate_report(report)


@pytest.mark.parametrize(
    "name",
    sorted(
        path.name
        for path in (Path(__file__).resolve().parents[1] / "docs" / "evidence").glob("*.json")
        if json.loads(path.read_text(encoding="utf-8")).get("schema_version") in {"0.2", "1.0"}
    ),
)
def test_report_validator_accepts_retained_evidence(name) -> None:
    if name in {"phase0-slice-02-calibration.json", "phase0-slice-02-oracle.json"}:
        # These earlier fixtures already differed from the currently packaged bytes.
        with pytest.raises(ValueError, match="fixture hash mismatch"):
            validate_report(_frozen_report(name))
    else:
        validate_report(_frozen_report(name))
