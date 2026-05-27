"""Smoke tests du widget ChatView (pytest-qt)."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fahmi2.domain.chat import ChatMessage, Citation
from fahmi2.domain.enums import ChatTabState
from fahmi2.ui.widgets.chat_view import ChatView, _citations_html, _message_html


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
                    number=1,
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


def test_citation_link_carries_snippet_tooltip() -> None:
    # L'extrait (snippet) du passage cité devient l'infobulle (title) du lien source,
    # aplati sur une ligne.
    citations = (
        Citation(
            number=1,
            chapter_title="Éco",
            section_title="PIB",
            anchor="pib",
            snippet="Le produit intérieur brut\nmesure la richesse produite.",
        ),
    )
    html_out = _citations_html(citations)
    assert 'title="Le produit intérieur brut mesure la richesse produite."' in html_out
    assert 'href="pib"' in html_out


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


def test_language_selector_visibility_and_signal(qtbot: QtBot) -> None:
    view = ChatView()
    qtbot.addWidget(view)
    # Une seule langue produite → combo masqué (comportement mono-langue inchangé).
    view.set_languages([("fr", "Français")], "fr")
    assert view._language_combo.isHidden()  # noqa: SLF001
    # Plusieurs langues → combo visible, langue présélectionnée.
    view.set_languages([("fr", "Français"), ("en", "Anglais")], "en")
    assert not view._language_combo.isHidden()  # noqa: SLF001
    assert view._language_combo.currentData() == "en"  # noqa: SLF001
    # Le clic « Nouvelle conversation » émet le code de la langue sélectionnée.
    with qtbot.waitSignal(view.new_conversation_requested, timeout=1000) as blocker:
        view._on_new_conversation()  # noqa: SLF001 — smoke d'assemblage
    assert blocker.args == ["en"]


def test_answering_freezes_conversation_controls(qtbot: QtBot) -> None:
    # Pendant le streaming, les contrôles de conversation sont gelés (le rechargement
    # de corpus est ignoré côté contrôleur → on le rend visible, pas silencieux).
    view = ChatView()
    qtbot.addWidget(view)
    view.set_state(ChatTabState.ANSWERING)
    assert not view._new_button.isEnabled()  # noqa: SLF001
    assert not view._language_combo.isEnabled()  # noqa: SLF001
    assert not view._conversations.isEnabled()  # noqa: SLF001
    view.set_state(ChatTabState.READY)
    assert view._new_button.isEnabled()  # noqa: SLF001
    assert view._language_combo.isEnabled()  # noqa: SLF001
    assert view._conversations.isEnabled()  # noqa: SLF001


def test_error_state_keeps_input_active_for_retry(qtbot: QtBot) -> None:
    view = ChatView()
    qtbot.addWidget(view)
    view.set_state(ChatTabState.ERROR)
    assert view._input.isEnabled()  # noqa: SLF001 — relance possible après erreur
    view.set_state(ChatTabState.ANSWERING)
    assert not view._input.isEnabled()  # noqa: SLF001 — verrouillé pendant la réponse


def test_citations_list_is_numbered_not_paragraph_sign() -> None:
    # La liste « Sources » est préfixée par [K] (relié au marqueur du corps),
    # le pied-de-mouche § ayant disparu.
    citations = (
        Citation(
            number=1,
            chapter_title="Éco",
            section_title="PIB",
            anchor="pib",
            snippet="…",
        ),
    )
    html_out = _citations_html(citations)
    assert "[1] Éco › PIB" in html_out
    assert "§" not in html_out


def test_assistant_inline_marker_is_clickable_link() -> None:
    # Le contenu réécrit [[K]](ancre) est rendu en lien cliquable par le moteur
    # Markdown (clic câblé sur citation_clicked, inchangé).
    message = ChatMessage(
        role="assistant",
        content="Le PIB [[1]](pib) mesure la richesse.",
        citations=(
            Citation(
                number=1,
                chapter_title="Éco",
                section_title="PIB",
                anchor="pib",
                snippet="…",
            ),
        ),
    )
    html_out = _message_html(message)
    assert '<a href="pib">[1]</a>' in html_out
