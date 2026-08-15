import asyncio
from types import SimpleNamespace

import browser_agent_regression.browser_use_deepseek as deepseek_module
from browser_agent_regression.browser_use_deepseek import (
    _bounded_message,
    _NonThinkingClient,
    _scoring_failure_message,
    deepseek_run_identity,
)


def test_provider_errors_redact_the_api_key() -> None:
    secret = "sk-example-secret"

    message = _bounded_message(
        f"Provider rejected Authorization: Bearer {secret}",
        secrets=(secret,),
    )

    assert secret not in message
    assert "[REDACTED]" in message


def test_non_thinking_client_injects_disabled_thinking_mode() -> None:
    class FakeCompletions:
        def __init__(self) -> None:
            self.request: dict[str, object] | None = None

        async def create(self, **kwargs):
            self.request = kwargs
            return kwargs

    completions = FakeCompletions()
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    proxy = _NonThinkingClient(client)

    asyncio.run(
        proxy.chat.completions.create(
            model="deepseek-v4-flash",
            extra_body={"existing": True},
        )
    )

    assert completions.request is not None
    assert completions.request["extra_body"] == {
        "existing": True,
        "thinking": {"type": "disabled"},
    }


def test_scoring_failure_retains_oracle_and_agent_errors_without_key() -> None:
    secret = "sk-example-secret"

    message = _scoring_failure_message(
        RuntimeError(f"page closed while using {secret}"),
        ["model returned malformed AgentOutput"],
        api_key=secret,
    )

    assert message.startswith("Independent checkpoint scoring failed:")
    assert "last agent error: model returned malformed AgentOutput" in message
    assert secret not in message
    assert "[REDACTED]" in message


def test_run_identity_records_browser_display_mode(monkeypatch) -> None:
    monkeypatch.setattr(deepseek_module, "version", lambda _package: "0.13.7")

    headed = deepseek_run_identity(
        model="deepseek-v4-flash",
        max_steps=12,
        headed=True,
    )
    headless = deepseek_run_identity(
        model="deepseek-v4-flash",
        max_steps=12,
        headed=False,
    )

    assert headed["headless"] is False
    assert headless["headless"] is True
