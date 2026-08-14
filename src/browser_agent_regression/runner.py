from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from hashlib import sha256
from importlib.metadata import version
from pathlib import Path
from platform import platform, python_version
from time import perf_counter
from typing import Any, Literal

from playwright.sync_api import Browser
from playwright.sync_api import Error as PlaywrightError

from browser_agent_regression.server import FixtureServer

Variant = Literal["clean", "popup-overlay", "delayed-render", "layout-shift"]
Driver = Literal["reference", "popup-blind"]

VARIANTS: tuple[Variant, ...] = (
    "clean",
    "popup-overlay",
    "delayed-render",
    "layout-shift",
)
CHECKPOINTS = (
    "checkout.email.accepted",
    "checkout.shipping.selected",
    "checkout.confirmed",
)


@dataclass(frozen=True)
class Attempt:
    driver: Driver
    variant: Variant
    passed: bool
    duration_ms: float
    checkpoints: dict[str, bool]
    first_failed_checkpoint: str | None
    error: str | None


def _bounded_error(error: Exception) -> str:
    message = " ".join(str(error).split())
    return message[:500]


def run_checkout_attempt(
    browser: Browser,
    server: FixtureServer,
    *,
    driver: Driver,
    variant: Variant,
    timeout_ms: int = 1_500,
) -> Attempt:
    """Run one isolated calibration attempt and preserve checkpoint evidence."""

    page = browser.new_page()
    page.set_default_timeout(timeout_ms)
    checkpoints = dict.fromkeys(CHECKPOINTS, False)
    started = perf_counter()
    error: str | None = None

    try:
        page.goto(server.url("checkout.html", variant=variant), wait_until="domcontentloaded")

        if driver == "reference" and variant == "popup-overlay":
            page.get_by_role("button", name="Continue to checkout").click()

        email = page.get_by_label("Email")
        email.click()
        email.fill("agent@example.test")
        checkpoints["checkout.email.accepted"] = email.input_value() == "agent@example.test"

        shipping = page.get_by_label("Shipping")
        shipping.select_option("express")
        checkpoints["checkout.shipping.selected"] = shipping.input_value() == "express"

        page.get_by_role("button", name="Complete purchase").click()
        confirmation = page.get_by_role("status")
        confirmation.wait_for(state="visible")
        checkpoints["checkout.confirmed"] = confirmation.text_content() == "Order confirmed"
    except PlaywrightError as exc:
        error = _bounded_error(exc)
    finally:
        duration_ms = round((perf_counter() - started) * 1_000, 3)
        page.close()

    first_failed = next((name for name, passed in checkpoints.items() if not passed), None)
    return Attempt(
        driver=driver,
        variant=variant,
        passed=first_failed is None and error is None,
        duration_ms=duration_ms,
        checkpoints=checkpoints,
        first_failed_checkpoint=first_failed,
        error=error,
    )


def summarize(attempts: list[Attempt]) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    groups = sorted({(attempt.driver, attempt.variant) for attempt in attempts})
    for driver, variant in groups:
        group = [
            attempt
            for attempt in attempts
            if attempt.driver == driver and attempt.variant == variant
        ]
        successes = sum(attempt.passed for attempt in group)
        failures = Counter(
            attempt.first_failed_checkpoint
            for attempt in group
            if attempt.first_failed_checkpoint is not None
        )
        summaries.append(
            {
                "driver": driver,
                "variant": variant,
                "runs": len(group),
                "successes": successes,
                "success_rate": successes / len(group),
                "failure_checkpoints": dict(sorted(failures.items())),
            }
        )
    return summaries


def find_regressions(
    summaries: list[dict[str, Any]],
    *,
    baseline: Driver = "reference",
    candidate: Driver = "popup-blind",
) -> list[dict[str, Any]]:
    indexed = {(item["driver"], item["variant"]): item for item in summaries}
    variants = sorted(
        variant
        for driver, variant in indexed
        if driver == baseline and (candidate, variant) in indexed
    )
    regressions: list[dict[str, Any]] = []
    for variant in variants:
        baseline_item = indexed[(baseline, variant)]
        candidate_item = indexed[(candidate, variant)]
        delta = candidate_item["success_rate"] - baseline_item["success_rate"]
        if delta < 0:
            failure_counts = candidate_item["failure_checkpoints"]
            failed_checkpoint = (
                max(failure_counts, key=failure_counts.get) if failure_counts else None
            )
            total_failures = sum(failure_counts.values())
            checkpoint_agreement = (
                failure_counts[failed_checkpoint] / total_failures
                if failed_checkpoint is not None and total_failures
                else None
            )
            regressions.append(
                {
                    "variant": variant,
                    "baseline_success_rate": baseline_item["success_rate"],
                    "candidate_success_rate": candidate_item["success_rate"],
                    "delta": delta,
                    "failed_checkpoint": failed_checkpoint,
                    "failure_checkpoint_agreement": checkpoint_agreement,
                }
            )
    return regressions


def build_report(
    attempts: list[Attempt],
    *,
    command: str,
    runs: int,
    variants: list[Variant],
    browser_version: str | None = None,
) -> dict[str, Any]:
    summaries = summarize(attempts)
    regressions = find_regressions(summaries) if command == "calibrate" else []
    fixture_directory = Path(__file__).with_name("fixtures")
    fixture_hashes = {
        name: sha256((fixture_directory / name).read_bytes()).hexdigest()
        for name in ("checkout.html", "checkout.json")
    }
    return {
        "schema_version": "0.1",
        "evidence_kind": "synthetic-calibration",
        "created_at": datetime.now(UTC).isoformat(),
        "task_id": "checkout.basic.v1",
        "command": command,
        "environment": {
            "python": python_version(),
            "platform": platform(),
            "playwright": version("playwright"),
            "browser": browser_version,
        },
        "fixture_sha256": fixture_hashes,
        "configuration": {"runs_per_driver_variant": runs, "variants": variants},
        "summaries": summaries,
        "regressions": regressions,
        "attempts": [asdict(attempt) for attempt in attempts],
    }
