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

from playwright.sync_api import Browser, Page
from playwright.sync_api import Error as PlaywrightError

from browser_agent_regression import __version__
from browser_agent_regression.server import FixtureServer

SCHEMA_VERSION = "1.0"
PROTOCOL_ID = "browser-agent-regression-controlled-ui-v1"

Variant = Literal["clean", "popup-overlay", "delayed-render", "layout-shift"]
Driver = Literal[
    "reference",
    "popup-blind",
    "browser-use/deepseek-v4-flash",
    "browser-use/deepseek-v4-pro",
]
TaskId = Literal[
    "checkout.basic.v1",
    "catalog.find-and-save.v1",
    "preferences.notifications.v1",
]

VARIANTS: tuple[Variant, ...] = (
    "clean",
    "popup-overlay",
    "delayed-render",
    "layout-shift",
)
TASKS: tuple[TaskId, ...] = (
    "checkout.basic.v1",
    "catalog.find-and-save.v1",
    "preferences.notifications.v1",
)
TASK_FIXTURES: dict[TaskId, str] = {
    "checkout.basic.v1": "checkout.html",
    "catalog.find-and-save.v1": "catalog.html",
    "preferences.notifications.v1": "preferences.html",
}
TASK_CHECKPOINTS: dict[TaskId, tuple[str, ...]] = {
    "checkout.basic.v1": (
        "checkout.email.accepted",
        "checkout.shipping.selected",
        "checkout.confirmed",
    ),
    "catalog.find-and-save.v1": (
        "catalog.query.applied",
        "catalog.product.opened",
        "catalog.product.saved",
    ),
    "preferences.notifications.v1": (
        "preferences.product_updates.disabled",
        "preferences.security_alerts.enabled",
        "preferences.saved",
    ),
}


@dataclass(frozen=True)
class Attempt:
    task_id: TaskId
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


def _complete_checkout(page: Page, checkpoints: dict[str, bool]) -> None:
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


def _complete_catalog(page: Page, checkpoints: dict[str, bool]) -> None:
    search = page.get_by_label("Search products")
    search.click()
    search.fill("trail camera")
    page.get_by_role("button", name="Search catalog").click()
    result_status = page.locator("#result-status")
    checkpoints["catalog.query.applied"] = result_status.text_content() == "1 product found"

    page.get_by_role("button", name="View Northstar Trail Camera").click()
    details = page.get_by_role("region", name="Product details")
    details.wait_for(state="visible")
    checkpoints["catalog.product.opened"] = (
        details.get_by_role("heading").text_content() == "Northstar Trail Camera"
    )

    page.get_by_role("button", name="Save Northstar Trail Camera").click()
    saved_status = page.locator("#saved-status")
    saved_status.wait_for(state="visible")
    checkpoints["catalog.product.saved"] = (
        saved_status.text_content() == "Northstar Trail Camera saved to shortlist"
    )


def _complete_preferences(page: Page, checkpoints: dict[str, bool]) -> None:
    product_updates = page.get_by_label("Product updates")
    product_updates.uncheck()
    checkpoints["preferences.product_updates.disabled"] = not product_updates.is_checked()

    security_alerts = page.get_by_label("Security alerts")
    security_alerts.check()
    checkpoints["preferences.security_alerts.enabled"] = security_alerts.is_checked()

    page.get_by_role("button", name="Save preferences").click()
    saved_status = page.get_by_role("status")
    saved_status.wait_for(state="visible")
    checkpoints["preferences.saved"] = saved_status.text_content() == "Preferences saved"


def run_attempt(
    browser: Browser,
    server: FixtureServer,
    *,
    task_id: TaskId,
    driver: Driver,
    variant: Variant,
    timeout_ms: int = 1_500,
) -> Attempt:
    """Run one isolated task attempt and preserve checkpoint evidence."""

    page = browser.new_page()
    page.set_default_timeout(timeout_ms)
    checkpoints = dict.fromkeys(TASK_CHECKPOINTS[task_id], False)
    started = perf_counter()
    error: str | None = None

    try:
        page.goto(
            server.url(TASK_FIXTURES[task_id], variant=variant),
            wait_until="domcontentloaded",
        )

        if driver == "reference" and variant == "popup-overlay":
            page.get_by_role("dialog").get_by_role("button").click()

        if task_id == "checkout.basic.v1":
            _complete_checkout(page, checkpoints)
        elif task_id == "catalog.find-and-save.v1":
            _complete_catalog(page, checkpoints)
        else:
            _complete_preferences(page, checkpoints)
    except PlaywrightError as exc:
        error = _bounded_error(exc)
    finally:
        duration_ms = round((perf_counter() - started) * 1_000, 3)
        page.close()

    first_failed = next((name for name, passed in checkpoints.items() if not passed), None)
    return Attempt(
        task_id=task_id,
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
    groups = sorted({(attempt.task_id, attempt.driver, attempt.variant) for attempt in attempts})
    for task_id, driver, variant in groups:
        group = [
            attempt
            for attempt in attempts
            if attempt.task_id == task_id
            and attempt.driver == driver
            and attempt.variant == variant
        ]
        successes = sum(attempt.passed for attempt in group)
        failures = Counter(
            attempt.first_failed_checkpoint
            for attempt in group
            if attempt.first_failed_checkpoint is not None
        )
        summaries.append(
            {
                "task_id": task_id,
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
    indexed = {
        (item["task_id"], item["driver"], item["variant"]): item for item in summaries
    }
    conditions = sorted(
        (task_id, variant)
        for task_id, driver, variant in indexed
        if driver == baseline and (task_id, candidate, variant) in indexed
    )
    regressions: list[dict[str, Any]] = []
    for task_id, variant in conditions:
        baseline_item = indexed[(task_id, baseline, variant)]
        candidate_item = indexed[(task_id, candidate, variant)]
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
                    "task_id": task_id,
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
    tasks: list[TaskId],
    variants: list[Variant],
    browser_version: str | None = None,
    evidence_kind: str = "synthetic-calibration",
    run_identity: dict[str, Any] | None = None,
) -> dict[str, Any]:
    summaries = summarize(attempts)
    regressions = find_regressions(summaries) if command in {"calibrate", "demo"} else []
    fixture_directory = Path(__file__).with_name("fixtures")
    fixture_names = {
        name
        for task_id in tasks
        for name in (
            TASK_FIXTURES[task_id],
            Path(TASK_FIXTURES[task_id]).with_suffix(".json").name,
        )
    }
    fixture_hashes = {
        name: sha256((fixture_directory / name).read_bytes()).hexdigest()
        for name in sorted(fixture_names)
    }
    configuration: dict[str, Any] = {
        "runs_per_driver_task_variant": runs,
        "tasks": tasks,
        "variants": variants,
    }
    if run_identity is not None:
        configuration["run_identity"] = run_identity

    return {
        "schema_version": SCHEMA_VERSION,
        "protocol_id": PROTOCOL_ID,
        "tool_version": __version__,
        "evidence_kind": evidence_kind,
        "created_at": datetime.now(UTC).isoformat(),
        "task_ids": tasks,
        "command": command,
        "environment": {
            "python": python_version(),
            "platform": platform(),
            "playwright": version("playwright"),
            "browser": browser_version,
        },
        "fixture_sha256": fixture_hashes,
        "configuration": configuration,
        "summaries": summaries,
        "regressions": regressions,
        "attempts": [asdict(attempt) for attempt in attempts],
    }


def validate_report(report: dict[str, Any]) -> None:
    """Validate v1 evidence and retained 0.2 Phase 0 evidence.

    Validation checks the report's internal accounting and binds it to the
    packaged fixture bytes. Durations, timestamps, and browser versions are
    evidence, but are intentionally not expected to be reproducible byte for byte.
    """

    def require(condition: bool, message: str) -> None:
        if not condition:
            raise ValueError(message)

    schema = report.get("schema_version")
    require(schema in {"0.2", SCHEMA_VERSION}, f"unsupported schema version: {schema}")
    if schema == SCHEMA_VERSION:
        require(report.get("protocol_id") == PROTOCOL_ID, "protocol identifier mismatch")
        require(isinstance(report.get("tool_version"), str), "tool version is missing")
    require(
        report.get("command") in {"demo", "oracle", "calibrate", "deepseek"},
        "unknown report command",
    )
    require(
        report.get("evidence_kind") in {"synthetic-calibration", "real-agent"},
        "unknown evidence kind",
    )
    created_at = report.get("created_at")
    require(isinstance(created_at, str), "created_at must be an ISO timestamp")
    try:
        datetime.fromisoformat(created_at)
    except ValueError as exc:
        raise ValueError("created_at must be an ISO timestamp") from exc
    environment = report.get("environment")
    require(isinstance(environment, dict), "environment must be an object")
    require(
        {"python", "platform", "playwright", "browser"}.issubset(environment),
        "environment fields are incomplete",
    )

    tasks = report.get("task_ids")
    require(isinstance(tasks, list) and bool(tasks), "task_ids must be a non-empty list")
    require(all(task in TASKS for task in tasks), "report contains an unknown task")
    require(len(tasks) == len(set(tasks)), "task_ids contains duplicates")

    configuration = report.get("configuration")
    require(isinstance(configuration, dict), "configuration must be an object")
    require(configuration.get("tasks") == tasks, "configuration tasks do not match task_ids")
    variants = configuration.get("variants")
    require(isinstance(variants, list) and bool(variants), "configuration variants are missing")
    require(all(variant in VARIANTS for variant in variants), "report contains an unknown variant")
    require(len(variants) == len(set(variants)), "configuration variants contains duplicates")
    runs = configuration.get("runs_per_driver_task_variant")
    require(isinstance(runs, int) and runs >= 1, "run count must be a positive integer")

    raw_attempts = report.get("attempts")
    require(isinstance(raw_attempts, list) and bool(raw_attempts), "attempts must be non-empty")
    attempts: list[Attempt] = []
    for index, raw in enumerate(raw_attempts):
        require(isinstance(raw, dict), f"attempt {index} must be an object")
        try:
            attempt = Attempt(**raw)
        except TypeError as exc:
            raise ValueError(f"attempt {index} has an invalid shape: {exc}") from exc
        require(attempt.task_id in tasks, f"attempt {index} references an undeclared task")
        require(attempt.variant in variants, f"attempt {index} references an undeclared variant")
        require(attempt.duration_ms >= 0.0, f"attempt {index} has a negative duration")
        require(
            attempt.driver
            in {
                "reference",
                "popup-blind",
                "browser-use/deepseek-v4-flash",
                "browser-use/deepseek-v4-pro",
            },
            f"attempt {index} references an unknown driver",
        )
        require(
            tuple(attempt.checkpoints) == TASK_CHECKPOINTS[attempt.task_id],
            f"attempt {index} checkpoint contract mismatch",
        )
        first_failed = next(
            (name for name, passed in attempt.checkpoints.items() if not passed), None
        )
        require(
            attempt.first_failed_checkpoint == first_failed,
            f"attempt {index} first-failure checkpoint mismatch",
        )
        require(
            attempt.passed == (first_failed is None and attempt.error is None),
            f"attempt {index} pass flag is inconsistent",
        )
        attempts.append(attempt)

    require(report.get("summaries") == summarize(attempts), "summary accounting mismatch")
    expected_regressions = (
        find_regressions(summarize(attempts))
        if report.get("command") in {"calibrate", "demo"}
        else []
    )
    require(report.get("regressions") == expected_regressions, "regression accounting mismatch")

    fixture_directory = Path(__file__).with_name("fixtures")
    fixture_names = {
        name
        for task_id in tasks
        for name in (
            TASK_FIXTURES[task_id],
            Path(TASK_FIXTURES[task_id]).with_suffix(".json").name,
        )
    }
    expected_hashes = {
        name: sha256((fixture_directory / name).read_bytes()).hexdigest()
        for name in sorted(fixture_names)
    }
    require(report.get("fixture_sha256") == expected_hashes, "fixture hash mismatch")

    def sensitive_keys(value: Any) -> list[str]:
        if isinstance(value, dict):
            found = [
                str(key)
                for key in value
                if str(key).casefold() in {"api_key", "authorization", "token"}
            ]
            return found + [item for child in value.values() for item in sensitive_keys(child)]
        if isinstance(value, list):
            return [item for child in value for item in sensitive_keys(child)]
        return []

    require(not sensitive_keys(report), "report contains a credential-shaped field")
