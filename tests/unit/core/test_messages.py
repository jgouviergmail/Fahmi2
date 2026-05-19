"""Tests du registre de messages utilisateurs."""

from fahmi2.core.errors.messages import (
    UserFacingMessage,
    get_message,
    has_message,
    register_message,
    reset_registry_for_tests,
)


def test_get_known_code_returns_message() -> None:
    msg = get_message("LLM.AUTH_INVALID")
    assert isinstance(msg, UserFacingMessage)
    assert "DeepSeek" in msg.title or "clé" in msg.title.lower()
    assert msg.body


def test_get_unknown_code_returns_fallback() -> None:
    msg = get_message("DOES.NOT.EXIST")
    assert msg.title
    assert "DOES.NOT.EXIST" in msg.body


def test_has_message_distinguishes_known_unknown() -> None:
    assert has_message("LLM.AUTH_INVALID")
    assert not has_message("DOES.NOT.EXIST")


def test_register_message_adds_new_code() -> None:
    try:
        register_message(
            "TEST.CUSTOM",
            UserFacingMessage(title="Custom", body="body", actions=()),
        )
        assert has_message("TEST.CUSTOM")
        assert get_message("TEST.CUSTOM").title == "Custom"
    finally:
        reset_registry_for_tests()


def test_reset_registry_keeps_built_in_messages() -> None:
    register_message(
        "TEMP.X",
        UserFacingMessage(title="X", body="x", actions=()),
    )
    reset_registry_for_tests()
    assert not has_message("TEMP.X")
    assert has_message("LLM.AUTH_INVALID")  # toujours présent
