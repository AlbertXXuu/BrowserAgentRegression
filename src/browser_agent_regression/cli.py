from __future__ import annotations

import argparse
import json
from pathlib import Path
from threading import Event
from typing import cast

from playwright.sync_api import sync_playwright

from browser_agent_regression.runner import (
    TASK_FIXTURES,
    TASKS,
    VARIANTS,
    Attempt,
    Driver,
    TaskId,
    Variant,
    build_report,
    run_attempt,
)
from browser_agent_regression.server import FixtureServer


def _variants(values: list[str] | None) -> list[Variant]:
    return cast(list[Variant], list(dict.fromkeys(values or VARIANTS)))


def _tasks(values: list[str] | None) -> list[TaskId]:
    return cast(list[TaskId], list(dict.fromkeys(values or TASKS)))


def _write_report(report: dict[str, object], output: Path | None) -> None:
    rendered = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if output is None:
        print(rendered, end="")
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8", newline="\n")
    print(f"Wrote {output}")


def _run_matrix(
    *,
    drivers: list[Driver],
    tasks: list[TaskId],
    variants: list[Variant],
    runs: int,
    headed: bool,
) -> tuple[list[Attempt], str]:
    attempts: list[Attempt] = []
    with FixtureServer() as server, sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=not headed)
        browser_version = browser.version
        try:
            for driver in drivers:
                for task_id in tasks:
                    for variant in variants:
                        for _ in range(runs):
                            attempts.append(
                                run_attempt(
                                    browser,
                                    server,
                                    task_id=task_id,
                                    driver=driver,
                                    variant=variant,
                                )
                            )
        finally:
            browser.close()
    return attempts, browser_version


def _oracle(args: argparse.Namespace) -> int:
    tasks = _tasks(args.task)
    variants = _variants(args.variant)
    attempts, browser_version = _run_matrix(
        drivers=["reference"],
        tasks=tasks,
        variants=variants,
        runs=args.runs,
        headed=args.headed,
    )
    report = build_report(
        attempts,
        command="oracle",
        runs=args.runs,
        tasks=tasks,
        variants=variants,
        browser_version=browser_version,
    )
    _write_report(report, args.output)
    return 0 if all(attempt.passed for attempt in attempts) else 1


def _calibrate(args: argparse.Namespace) -> int:
    tasks = _tasks(args.task)
    variants = _variants(args.variant or ["clean", "popup-overlay"])
    attempts, browser_version = _run_matrix(
        drivers=["reference", "popup-blind"],
        tasks=tasks,
        variants=variants,
        runs=args.runs,
        headed=args.headed,
    )
    report = build_report(
        attempts,
        command="calibrate",
        runs=args.runs,
        tasks=tasks,
        variants=variants,
        browser_version=browser_version,
    )
    _write_report(report, args.output)

    summaries = {
        (summary["task_id"], summary["driver"], summary["variant"]): summary
        for summary in report["summaries"]
    }
    clean_parity = all(
        summaries[(task_id, "reference", "clean")]["success_rate"]
        == summaries[(task_id, "popup-blind", "clean")]["success_rate"]
        for task_id in tasks
    )
    target_regression = any(
        regression["variant"] == "popup-overlay"
        and regression["baseline_success_rate"] == 1.0
        and regression["delta"] <= -0.30
        and regression["failure_checkpoint_agreement"] >= 0.80
        for regression in report["regressions"]
    )
    return 0 if target_regression and clean_parity else 1


def _serve(args: argparse.Namespace) -> int:
    with FixtureServer(port=args.port) as server:
        print("Fixture server is ready. Press Ctrl+C to stop.")
        for task_id in TASKS:
            for variant in VARIANTS:
                print(
                    f"{task_id:26} {variant:16} "
                    f"{server.url(TASK_FIXTURES[task_id], variant=variant)}"
                )
        try:
            Event().wait()
        except KeyboardInterrupt:
            return 0
    return 0


def _add_run_arguments(parser: argparse.ArgumentParser, *, default_runs: int) -> None:
    parser.add_argument("--runs", type=int, default=default_runs)
    parser.add_argument("--task", action="append", choices=TASKS)
    parser.add_argument("--variant", action="append", choices=VARIANTS)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--headed", action="store_true")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="browser-agent-regression",
        description="Run local regression fixtures for browser agents.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    oracle = subparsers.add_parser("oracle", help="Check deterministic fixture stability.")
    _add_run_arguments(oracle, default_runs=30)
    oracle.set_defaults(handler=_oracle)

    calibrate = subparsers.add_parser(
        "calibrate", help="Prove that the harness detects a synthetic regression."
    )
    _add_run_arguments(calibrate, default_runs=5)
    calibrate.set_defaults(handler=_calibrate)

    serve = subparsers.add_parser("serve", help="Serve fixtures for manual inspection.")
    serve.add_argument("--port", type=int, default=8765)
    serve.set_defaults(handler=_serve)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "runs", 1) < 1:
        parser.error("--runs must be at least 1")
    if args.command == "calibrate" and args.variant is not None:
        required_variants = {"clean", "popup-overlay"}
        if not required_variants.issubset(args.variant):
            parser.error("calibrate --variant must include clean and popup-overlay")
    return int(args.handler(args))
