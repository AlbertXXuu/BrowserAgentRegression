from browser_agent_regression.cli import _masked_windows_input


def test_masked_windows_input_shows_feedback_and_supports_backspace(capsys) -> None:
    characters = iter(["s", "k", "x", "\b", "y", "\r"])

    result = _masked_windows_input("Key: ", read_character=lambda: next(characters))

    assert result == "sky"
    assert capsys.readouterr().out == "Key: ***\b \b*\n"
