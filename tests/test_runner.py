import json

import pytest
from playwright.sync_api import sync_playwright

from browser_agent_regression.runner import TASKS, VARIANTS, Attempt, build_report, run_attempt
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

    assert report["schema_version"] == "0.2"
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


def test_real_agent_report_preserves_identity_without_credentials() -> None:
    attempt = Attempt(
        task_id="preferences.notifications.v1",
        driver="browser-use/deepseek-v4-flash",
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
            "model": "deepseek-v4-flash",
            "credential_source": "hidden interactive prompt",
        },
    )

    assert report["schema_version"] == "0.2"
    assert report["evidence_kind"] == "real-agent"
    assert report["configuration"]["run_identity"]["agent"] == "browser-use"
    assert "api_key" not in json.dumps(report).lower()
