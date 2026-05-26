"""Smoke tests du widget ChatView (pytest-qt)."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fahmi2.domain.chat import ChatMessage, Citation
from fahmi2.domain.enums import ChatTabState
from fahmi2.ui.widgets.chat_view import ChatView


def test_streaming_then_finalize(qtbot: QtBot) -> None:
    view = ChatView()
    qtbot.addWidget(view)
    view.add_user_message("Qu'est-ce que le PIB ?")
    view.start_assistant_bubble()
    view.append_delta("Le PIB ")
    view.append_delta("mesure la richesse.")
    view.finalize_message(
        ChatMessage(
            role="assistant",
            content="Le PIB mesure la richesse.",
            citations=(
                Citation(
                    chapter_title="Éco",
                    section_title="PIB",
                    anchor="pib",
                    snippet="…",
                ),
            ),
        )
    )
    plain = view._thread.toPlainText()  # noqa: SLF001 — smoke d'assemblage
    assert "Le PIB mesure la richesse." in plain
    assert "Sources" in plain


def test_question_submitted_signal(qtbot: QtBot) -> None:
    view = ChatView()
    qtbot.addWidget(view)
    view.set_state(ChatTabState.READY)
    view._input.setText("Ma question")  # noqa: SLF001 — smoke d'assemblage
    with qtbot.waitSignal(view.question_submitted, timeout=1000) as blocker:
        view._on_send()  # noqa: SLF001 — smoke d'assemblage
    assert blocker.args == ["Ma question"]


def test_assistant_markdown_is_rendered(qtbot: QtBot) -> None:
    view = ChatView()
    qtbot.addWidget(view)
    view.show_conversation(
        (ChatMessage(role="assistant", content="Texte en **gras** ici."),)
    )
    plain = view._thread.toPlainText()  # noqa: SLF001 — smoke d'assemblage
    assert "gras" in plain
    assert "**" not in plain  # Markdown interprété, pas affiché brut


def test_send_button_is_primary(qtbot: QtBot) -> None:
    view = ChatView()
    qtbot.addWidget(view)
    assert view._send_button.property("role") == "primary"  # noqa: SLF001


def test_no_corpus_disables_input(qtbot: QtBot) -> None:
    view = ChatView()
    qtbot.addWidget(view)
    view.set_state(ChatTabState.NO_CORPUS)
    assert not view._input.isEnabled()  # noqa: SLF001 — smoke d'assemblage
    assert not view._banner.isHidden()  # noqa: SLF001 — visible (widget non monté)


def test_error_state_keeps_input_active_for_retry(qtbot: QtBot) -> None:
    view = ChatView()
    qtbot.addWidget(view)
    view.set_state(ChatTabState.ERROR)
    assert view._input.isEnabled()  # noqa: SLF001 — relance possible après erreur
    view.set_state(ChatTabState.ANSWERING)
    assert not view._input.isEnabled()  # noqa: SLF001 — verrouillé pendant la réponse
