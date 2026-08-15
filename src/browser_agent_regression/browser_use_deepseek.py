from __future__ import annotations

import asyncio
import json
import os
from importlib.metadata import version
from pathlib import Path
from time import perf_counter
from typing import Any, cast

from browser_agent_regression.runner import (
    TASK_CHECKPOINTS,
    TASK_FIXTURES,
    Attempt,
    Driver,
    TaskId,
    Variant,
)
from browser_agent_regression.server import FixtureServer

_FIXTURE_DIRECTORY = Path(__file__).with_name("fixtures")

_CHECKPOINT_SCRIPTS: dict[TaskId, str] = {
    "checkout.basic.v1": """() => ({
        "checkout.email.accepted": document.querySelector("#email")?.value === "agent@example.test",
        "checkout.shipping.selected": document.querySelector("#shipping")?.value === "express",
        "checkout.confirmed": !document.querySelector('[role="status"]')?.hidden
            && document.querySelector('[role="status"]')?.textContent === "Order confirmed"
    })""",
    "catalog.find-and-save.v1": """() => ({
        "catalog.query.applied": document.querySelector("#result-status")?.textContent === "1 product found",
        "catalog.product.opened": !document.querySelector('[aria-label="Product details"]')?.hidden
            && document.querySelector("#detail-name")?.textContent === "Northstar Trail Camera",
        "catalog.product.saved": !document.querySelector("#saved-status")?.hidden
            && document.querySelector("#saved-status")?.textContent
                === "Northstar Trail Camera saved to shortlist"
    })""",
    "preferences.notifications.v1": """() => ({
        "preferences.product_updates.disabled": !document.querySelector("#product-updates")?.checked,
        "preferences.security_alerts.enabled": document.querySelector("#security-alerts")?.checked === true,
        "preferences.saved": !document.querySelector('[role="status"]')?.hidden
            && document.querySelector('[role="status"]')?.textContent === "Preferences saved"
    })""",
}


class _NonThinkingCompletions:
    def __init__(self, completions: Any) -> None:
        self._completions = completions

    async def create(self, *args: Any, **kwargs: Any) -> Any:
        extra_body = dict(kwargs.get("extra_body") or {})
        extra_body["thinking"] = {"type": "disabled"}
        kwargs["extra_body"] = extra_body
        return await self._completions.create(*args, **kwargs)


class _NonThinkingChat:
    def __init__(self, chat: Any) -> None:
        self._chat = chat
        self.completions = _NonThinkingCompletions(chat.completions)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._chat, name)


class _NonThinkingClient:
    def __init__(self, client: Any) -> None:
        self._client = client
        self.chat = _NonThinkingChat(client.chat)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._client, name)


def _bounded_message(
    error: BaseException | str,
    *,
    secrets: tuple[str, ...] = (),
) -> str:
    message = " ".join(str(error).split())
    for secret in secrets:
        if secret:
            message = message.replace(secret, "[REDACTED]")
    return message[:500]


def _task_goal(task_id: TaskId) -> str:
    manifest_name = Path(TASK_FIXTURES[task_id]).with_suffix(".json")
    manifest = json.loads((_FIXTURE_DIRECTORY / manifest_name).read_text(encoding="utf-8"))
    return str(manifest["goal"])


async def _score_page(page: Any, task_id: TaskId) -> dict[str, bool]:
    raw_result = await page.evaluate(_CHECKPOINT_SCRIPTS[task_id])
    result = json.loads(raw_result)
    expected = TASK_CHECKPOINTS[task_id]
    if set(result) != set(expected):
        raise RuntimeError("The real-agent oracle returned an unexpected checkpoint set.")
    return {checkpoint: bool(result[checkpoint]) for checkpoint in expected}


async def _run_attempt(
    server: FixtureServer,
    *,
    api_key: str,
    model: str,
    task_id: TaskId,
    variant: Variant,
    headed: bool,
    max_steps: int,
) -> Attempt:
    os.environ["ANONYMIZED_TELEMETRY"] = "False"
    os.environ["BROWSER_USE_CLOUD_SYNC"] = "False"

    try:
        from browser_use import Agent, Browser
        from browser_use.llm import ChatDeepSeek
    except ImportError as exc:
        raise RuntimeError(
            'Browser Use is not installed. Run: python -m pip install -e ".[agent]"'
        ) from exc

    class NonThinkingChatDeepSeek(ChatDeepSeek):
        def _client(self) -> Any:
            return _NonThinkingClient(super()._client())

    driver = cast(Driver, f"browser-use/{model}")
    browser = Browser(
        headless=not headed,
        allowed_domains=["http://127.0.0.1"],
        enable_default_extensions=False,
        keep_alive=False,
    )
    checkpoints = dict.fromkeys(TASK_CHECKPOINTS[task_id], False)
    started = perf_counter()
    error: str | None = None

    try:
        await browser.start()
        page = await browser.must_get_current_page()
        await page.goto(server.url(TASK_FIXTURES[task_id], variant=variant))
        await asyncio.sleep(0.25)

        llm = NonThinkingChatDeepSeek(
            model=model,
            api_key=api_key,
            base_url="https://api.deepseek.com",
            temperature=0.0,
        )
        agent = Agent(
            task=(
                "You are on a controlled local test page. Complete exactly this goal: "
                f"{_task_goal(task_id)} Use only the current tab and do not navigate away. "
                "Finish only after the requested state is visibly confirmed."
            ),
            llm=llm,
            browser=browser,
            use_vision=False,
            use_judge=False,
            use_thinking=False,
            max_actions_per_step=3,
            max_failures=3,
            directly_open_url=False,
            generate_gif=False,
            enable_signal_handler=False,
            source="browser-agent-regression",
        )
        history = await agent.run(max_steps=max_steps)
        history_errors = [item for item in history.errors() if item]
        try:
            checkpoints = await _score_page(page, task_id)
        except Exception as scoring_error:
            retained_error: BaseException | str = (
                history_errors[-1] if history_errors else scoring_error
            )
            error = _bounded_message(retained_error, secrets=(api_key,))

        if not all(checkpoints.values()) and history_errors and error is None:
            error = _bounded_message(history_errors[-1], secrets=(api_key,))
    except Exception as exc:  # The report must retain provider and agent failures.
        error = _bounded_message(exc, secrets=(api_key,))
    finally:
        try:
            await browser.kill()
        except Exception as exc:
            if error is None:
                error = _bounded_message(exc, secrets=(api_key,))

    duration_ms = round((perf_counter() - started) * 1_000, 3)
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


async def run_deepseek_matrix(
    *,
    api_key: str,
    model: str,
    tasks: list[TaskId],
    variants: list[Variant],
    runs: int,
    headed: bool,
    max_steps: int,
) -> list[Attempt]:
    attempts: list[Attempt] = []
    with FixtureServer() as server:
        for task_id in tasks:
            for variant in variants:
                for _ in range(runs):
                    attempts.append(
                        await _run_attempt(
                            server,
                            api_key=api_key,
                            model=model,
                            task_id=task_id,
                            variant=variant,
                            headed=headed,
                            max_steps=max_steps,
                        )
                    )
    return attempts


def deepseek_run_identity(*, model: str, max_steps: int) -> dict[str, object]:
    return {
        "agent": "browser-use",
        "agent_version": version("browser-use"),
        "provider": "deepseek",
        "model": model,
        "use_vision": False,
        "use_judge": False,
        "temperature": 0.0,
        "thinking": "disabled",
        "max_steps": max_steps,
        "max_actions_per_step": 3,
        "prompt_strategy": "manifest goal with current-tab and visible-confirmation constraints",
        "tools": "browser-use default browser tools",
        "browser_use_telemetry": False,
        "credential_input": "environment or hidden interactive prompt",
    }
