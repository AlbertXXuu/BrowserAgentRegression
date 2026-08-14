import pytest
from playwright.sync_api import sync_playwright

from browser_agent_regression.runner import TASKS, VARIANTS, build_report, run_attempt
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
    }
    regressions = {item["task_id"]: item for item in report["regressions"]}
    assert set(regressions) == set(TASKS)
    assert regressions["checkout.basic.v1"]["failed_checkpoint"] == "checkout.email.accepted"
    assert regressions["catalog.find-and-save.v1"]["failed_checkpoint"] == (
        "catalog.query.applied"
    )
    assert all(item["delta"] == -1.0 for item in regressions.values())
    assert all(item["failure_checkpoint_agreement"] == 1.0 for item in regressions.values())
