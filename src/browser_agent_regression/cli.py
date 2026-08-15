from __future__ import annotations

import argparse
import asyncio
import getpass
import json
import os
import sys
from collections.abc import Callable
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


def _resolve_deepseek_api_key() -> str:
    api_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if api_key:
        return api_key
    if not sys.stdin.isatty():
        raise RuntimeError(
            "DEEPSEEK_API_KEY is missing and hidden input is unavailable. "
            "Set it in the current process or CI secret store."
        )

    print("No DEEPSEEK_API_KEY was found.")
    print("Create or copy a key at https://platform.deepseek.com/api_keys")
    if os.name == "nt":
        api_key = _masked_windows_input(
            "DeepSeek API key (masked with *; not stored): "
        ).strip()
    else:
        api_key = getpass.getpass("DeepSeek API key (hidden; not stored): ").strip()
    if not api_key:
        raise RuntimeError("A DeepSeek API key is required for this command.")
    return api_key


def _masked_windows_input(
    prompt: str,
    *,
    read_character: Callable[[], str] | None = None,
) -> str:
    if read_character is None:
        import msvcrt

        read_character = msvcrt.getwch

    print(prompt, end="", flush=True)
    characters: list[str] = []
    while True:
        character = read_character()
        if character in {"\r", "\n"}:
            print()
            return "".join(characters)
        if character == "\x03":
            raise KeyboardInterrupt
        if character == "\b":
            if characters:
                characters.pop()
                print("\b \b", end="", flush=True)
            continue
        if character in {"\x00", "\xe0"}:
            read_character()
            continue
        if character.isprintable():
            characters.append(character)
            print("*", end="", flush=True)


def _deepseek(args: argparse.Namespace) -> int:
    try:
        api_key = _resolve_deepseek_api_key()
        from browser_agent_regression.browser_use_deepseek import (
            deepseek_run_identity,
            run_deepseek_matrix,
        )

        tasks = _tasks(args.task)
        variants = _variants(args.variant or ["clean"])
        attempt_count = len(tasks) * len(variants) * args.runs
        print(
            f"Running Browser Use + {args.model}: {attempt_count} agent "
            f"attempt{'s' if attempt_count != 1 else ''}. "
            "Each attempt may make multiple paid API requests."
        )
        attempts = asyncio.run(
            run_deepseek_matrix(
                api_key=api_key,
                model=args.model,
                tasks=tasks,
                variants=variants,
                runs=args.runs,
                headed=args.headed,
                max_steps=args.max_steps,
            )
        )
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    report = build_report(
        attempts,
        command="deepseek",
        runs=args.runs,
        tasks=tasks,
        variants=variants,
        evidence_kind="real-agent",
        run_identity=deepseek_run_identity(model=args.model, max_steps=args.max_steps),
    )
    _write_report(report, args.output)
    passed = sum(attempt.passed for attempt in attempts)
    print(f"Real-agent result: {passed}/{len(attempts)} attempts passed independent checks.")
    for attempt in attempts:
        if not attempt.passed:
            print(
                f"FAILED {attempt.task_id} [{attempt.variant}] first checkpoint: "
                f"{attempt.first_failed_checkpoint or 'agent/runtime error'}"
            )
    return 0 if all(attempt.passed for attempt in attempts) else 1


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

    deepseek = subparsers.add_parser(
        "deepseek", help="Run Browser Use with DeepSeek against the local fixtures."
    )
    _add_run_arguments(deepseek, default_runs=1)
    deepseek.add_argument(
        "--model",
        choices=("deepseek-v4-flash", "deepseek-v4-pro"),
        default="deepseek-v4-flash",
    )
    deepseek.add_argument("--max-steps", type=int, default=12)
    deepseek.set_defaults(handler=_deepseek)

    serve = subparsers.add_parser("serve", help="Serve fixtures for manual inspection.")
    serve.add_argument("--port", type=int, default=8765)
    serve.set_defaults(handler=_serve)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "runs", 1) < 1:
        parser.error("--runs must be at least 1")
    if getattr(args, "max_steps", 1) < 1:
        parser.error("--max-steps must be at least 1")
    if args.command == "calibrate" and args.variant is not None:
        required_variants = {"clean", "popup-overlay"}
        if not required_variants.issubset(args.variant):
            parser.error("calibrate --variant must include clean and popup-overlay")
    return int(args.handler(args))
