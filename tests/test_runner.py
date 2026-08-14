import pytest
from playwright.sync_api import sync_playwright

from browser_agent_regression.runner import build_report, run_checkout_attempt
from browser_agent_regression.server import FixtureServer


@pytest.mark.browser
def test_reference_oracle_survives_all_variants() -> None:
    with FixtureServer() as server, sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            attempts = [
                run_checkout_attempt(browser, server, driver="reference", variant=variant)
                for variant in (
                    "clean",
                    "popup-overlay",
                    "delayed-render",
                    "layout-shift",
                )
            ]
        finally:
            browser.close()

    assert all(attempt.passed for attempt in attempts)


@pytest.mark.browser
def test_calibration_detects_popup_regression_only() -> None:
    with FixtureServer() as server, sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            attempts = [
                run_checkout_attempt(browser, server, driver=driver, variant=variant)
                for driver in ("reference", "popup-blind")
                for variant in ("clean", "popup-overlay")
            ]
        finally:
            browser.close()

    report = build_report(
        attempts,
        command="calibrate",
        runs=1,
        variants=["clean", "popup-overlay"],
    )

    assert report["regressions"] == [
        {
            "variant": "popup-overlay",
            "baseline_success_rate": 1.0,
            "candidate_success_rate": 0.0,
            "delta": -1.0,
            "failed_checkpoint": "checkout.email.accepted",
            "failure_checkpoint_agreement": 1.0,
        }
    ]
