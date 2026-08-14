from browser_agent_regression.browser_use_deepseek import _bounded_message


def test_provider_errors_redact_the_api_key() -> None:
    secret = "sk-example-secret"

    message = _bounded_message(
        f"Provider rejected Authorization: Bearer {secret}",
        secrets=(secret,),
    )

    assert secret not in message
    assert "[REDACTED]" in message
