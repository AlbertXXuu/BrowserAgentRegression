import asyncio
import json
from types import SimpleNamespace

import browser_agent_regression.browser_use_deepseek as deepseek_module
from browser_agent_regression.browser_use_deepseek import (
    _bounded_message,
    _deepseek_json_output_completion,
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


def test_json_output_transport_avoids_forced_tool_calling() -> None:
    class FakeOutput:
        @staticmethod
        def model_validate_json(content: str):
            return json.loads(content)

    class FakeCompletions:
        def __init__(self) -> None:
            self.request: dict[str, object] | None = None

        async def create(self, **kwargs):
            self.request = kwargs
            message = SimpleNamespace(
                content='{"action": [{"input_text": {"index": 3, "text": "value"}}]}'
            )
            return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    completions = FakeCompletions()
    base_client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    client = _NonThinkingClient(base_client)

    result = asyncio.run(
        _deepseek_json_output_completion(
            client,
            model="deepseek-v4-flash",
            messages=[{"role": "system", "content": "Return JSON."}],
            output_format=FakeOutput,
            request_options={"temperature": 0.0},
        )
    )

    assert result["action"][0]["input_text"]["index"] == 3
    assert completions.request is not None
    assert completions.request["response_format"] == {"type": "json_object"}
    assert completions.request["extra_body"] == {"thinking": {"type": "disabled"}}
    assert "tools" not in completions.request
    assert "tool_choice" not in completions.request


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
