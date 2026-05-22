"""Tests du ChatViewModel (logique sans Qt)."""

from __future__ import annotations

from fahmi2.domain.chat import ChatMessage
from fahmi2.domain.enums import ChatTabState, Language
from fahmi2.ui.viewmodels.chat_view_model import ChatViewModel


def test_resolve_state_transitions() -> None:
    vm = ChatViewModel()
    assert (
        vm.resolve_state(
            has_project=False, has_corpus=False, is_answering=False, has_error=False
        )
        is ChatTabState.NO_PROJECT
    )
    assert (
        vm.resolve_state(
            has_project=True, has_corpus=False, is_answering=False, has_error=False
        )
        is ChatTabState.NO_CORPUS
    )
    assert (
        vm.resolve_state(
            has_project=True, has_corpus=True, is_answering=False, has_error=False
        )
        is ChatTabState.READY
    )
    assert (
        vm.resolve_state(
            has_project=True, has_corpus=True, is_answering=True, has_error=False
        )
        is ChatTabState.ANSWERING
    )
    assert (
        vm.resolve_state(
            has_project=True, has_corpus=True, is_answering=False, has_error=True
        )
        is ChatTabState.ERROR
    )


def test_first_user_message_sets_title() -> None:
    vm = ChatViewModel()
    conv = vm.start_conversation(Language.FR)
    conv = vm.append_user(conv, "Qu'est-ce que le PIB exactement ?")
    assert conv.title.startswith("Qu'est-ce que le PIB")
    assert conv.messages[-1].role == "user"


def test_append_assistant_keeps_title() -> None:
    vm = ChatViewModel()
    conv = vm.start_conversation(Language.FR)
    conv = vm.append_user(conv, "Question ?")
    conv = vm.append_assistant(
        conv, ChatMessage(role="assistant", content="Réponse.")
    )
    assert conv.title == "Question ?"
    assert len(conv.messages) == 2


def test_derive_title_truncates_long_question() -> None:
    vm = ChatViewModel()
    title = vm.derive_title("a" * 200)
    assert title.endswith("…")
    assert len(title) <= 61  # 60 + ellipsis
