import asyncio
from types import SimpleNamespace

from browser_agent_regression.browser_use_deepseek import (
    _bounded_message,
    _NonThinkingClient,
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
