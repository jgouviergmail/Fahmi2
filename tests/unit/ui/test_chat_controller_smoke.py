"""Smoke tests du ChatController (pytest-qt, provider LLM injecté)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from PySide6.QtWidgets import QMessageBox
from pytestqt.qtbot import QtBot

from fahmi2.app.project_service import ProjectService
from fahmi2.app.secrets_service import SecretsService
from fahmi2.core.config.paths import AppPaths
from fahmi2.domain.chat import ChatMessage, ChatSettings
from fahmi2.domain.enums import ChatTabState, Language
from fahmi2.domain.ids import ProjectId
from fahmi2.infra.llm._fakes import FakeLLMProvider
from fahmi2.infra.llm.interface import LLMResponse
from fahmi2.infra.secrets.interface import InMemorySecretsStore
from fahmi2.infra.storage.sqlite_state import SqliteState
from fahmi2.pedagogy.sources import consolidated_doc_path
from fahmi2.ui.chat_controller import ChatController
from fahmi2.ui.widgets.chat_view import ChatView

_DOC = "# Cours\n\n# 1. Bases\n\nLe produit intérieur brut mesure la richesse.\n"


def _make_controller(
    tmp_path: Path, *, with_corpus: bool, qtbot: QtBot
) -> tuple[ChatController, ChatView, ProjectId]:
    state = SqliteState(tmp_path / "state.db")
    project_service = ProjectService(state)
    secrets = SecretsService(InMemorySecretsStore())
    secrets.set_deepseek_api_key("dummy-key")
    workspace = tmp_path / "ws"
    workspace.mkdir()
    project = project_service.create_project(
        name="P",
        workspace_folder=workspace,
        chat=ChatSettings(query_expansion_enabled=False),
    )
    if with_corpus:
        out_dir = workspace / "generation" / "output"
        out_dir.mkdir(parents=True)
        consolidated_doc_path(out_dir, Language.FR).write_text(_DOC, encoding="utf-8")
    view = ChatView()
    qtbot.addWidget(view)
    fake = FakeLLMProvider(
        default_response=LLMResponse(
            content="Le PIB mesure la richesse [§1].",
            thinking_content=None,
            prompt_tokens=10,
            completion_tokens=5,
            cached_prompt_tokens=0,
            cost_usd=0.01,
        )
    )
    controller = ChatController(
        view=view,
        window=view,
        project_service=project_service,
        secrets_service=secrets,
        app_paths=AppPaths.default(),
        llm_provider_factory=lambda _key: fake,
    )
    controller.on_project_selected(project.id)
    return controller, view, project.id


def test_refresh_corpus_if_stale_picks_up_regenerated_doc(
    qtbot: QtBot, tmp_path: Path
) -> None:
    # Reproduit le bug constaté : après régénération du consolidé, le Dialogue
    # doit citer le NOUVEAU document, pas celui chargé à la sélection du projet.
    controller, _view, _pid = _make_controller(tmp_path, with_corpus=True, qtbot=qtbot)
    assert {c.chapter_title for c in controller._chunks} == {"Bases"}  # noqa: SLF001

    doc_path = (
        tmp_path / "ws" / "generation" / "output" / "consolidated.fr.md"
    )
    doc_path.write_text(
        "# Cours\n\n# 1. Avancé\n\nLa politique monétaire pilote l'inflation.\n",
        encoding="utf-8",
    )
    # mtime strictement postérieur (déterministe, indépendant de la granularité FS).
    future = doc_path.stat().st_mtime_ns + 1_000_000_000
    os.utime(doc_path, ns=(future, future))

    controller.refresh_corpus_if_stale()
    assert {c.chapter_title for c in controller._chunks} == {"Avancé"}  # noqa: SLF001


def test_refresh_corpus_noop_when_unchanged(qtbot: QtBot, tmp_path: Path) -> None:
    controller, _view, _pid = _make_controller(tmp_path, with_corpus=True, qtbot=qtbot)
    before = controller._chunks  # noqa: SLF001
    controller.refresh_corpus_if_stale()  # rien n'a changé sur disque
    assert controller._chunks is before  # noqa: SLF001 — pas de re-dérivation inutile


def test_new_conversation_in_other_language_switches_corpus(
    qtbot: QtBot, tmp_path: Path
) -> None:
    # Une conversation créée dans une autre langue lit le document de CETTE langue
    # (corpus + langue de réponse), pas celui de la langue source.
    controller, _view, _pid = _make_controller(tmp_path, with_corpus=True, qtbot=qtbot)
    out_dir = tmp_path / "ws" / "generation" / "output"
    consolidated_doc_path(out_dir, Language.EN).write_text(
        "# Course\n\n# 1. Basics\n\nGDP measures wealth.\n", encoding="utf-8"
    )
    controller.new_conversation("en")
    assert controller._conversation is not None  # noqa: SLF001
    assert controller._conversation.language is Language.EN  # noqa: SLF001
    assert controller._content_language is Language.EN  # noqa: SLF001
    assert {c.chapter_title for c in controller._chunks} == {"Basics"}  # noqa: SLF001


def test_language_selector_populated_with_produced_languages(
    qtbot: QtBot, tmp_path: Path
) -> None:
    controller, view, pid = _make_controller(tmp_path, with_corpus=True, qtbot=qtbot)
    out_dir = tmp_path / "ws" / "generation" / "output"
    consolidated_doc_path(out_dir, Language.EN).write_text(_DOC, encoding="utf-8")
    controller.on_project_selected(pid)  # re-sélection → re-peuple le sélecteur
    assert not view._language_combo.isHidden()  # noqa: SLF001 — 2 langues → visible
    codes = {
        view._language_combo.itemData(i)  # noqa: SLF001
        for i in range(view._language_combo.count())  # noqa: SLF001
    }
    assert codes == {"fr", "en"}


def test_no_corpus_state(qtbot: QtBot, tmp_path: Path) -> None:
    _ctrl, view, _pid = _make_controller(tmp_path, with_corpus=False, qtbot=qtbot)
    assert not view._input.isEnabled()  # noqa: SLF001 — NO_CORPUS désactive la saisie
    assert not view._banner.isHidden()  # noqa: SLF001


def test_submit_question_streams_and_finalizes(qtbot: QtBot, tmp_path: Path) -> None:
    controller, view, _pid = _make_controller(tmp_path, with_corpus=True, qtbot=qtbot)
    view.set_state(ChatTabState.READY)
    with qtbot.waitSignal(controller.answer_completed, timeout=3000):
        controller.submit_question("Qu'est-ce que le PIB ?")
    plain = view._thread.toPlainText()  # noqa: SLF001 — smoke d'assemblage
    assert "Le PIB mesure la richesse" in plain


def test_answer_persisted_to_answering_project_despite_display_change(
    qtbot: QtBot, tmp_path: Path
) -> None:
    # Si l'utilisateur change de projet pendant le streaming, la réponse doit être
    # persistée sur le projet RÉPONDU (contexte figé), pas sur l'affichage courant.
    controller, _view, pid = _make_controller(tmp_path, with_corpus=True, qtbot=qtbot)
    store = controller._store  # noqa: SLF001
    assert store is not None and controller._conversation is not None  # noqa: SLF001
    conv = controller._vm.append_user(  # noqa: SLF001
        controller._conversation, "Question sur le projet A"  # noqa: SLF001
    )
    # Fige le contexte de réponse (comme submit_question).
    controller._answering_conversation = conv  # noqa: SLF001
    controller._answering_store = store  # noqa: SLF001
    controller._answering_project_id = pid  # noqa: SLF001
    # L'affichage a changé entre-temps (autre projet / aucun).
    controller._project = None  # noqa: SLF001
    controller._on_completed(  # noqa: SLF001
        ChatMessage(role="assistant", content="Réponse A", cost_usd=0.01)
    )
    saved = store.load(conv.conversation_id)
    assert saved is not None
    assert any(m.content == "Réponse A" for m in saved.messages)


def test_delete_conversation_removes_file(
    qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    controller, _view, _pid = _make_controller(tmp_path, with_corpus=True, qtbot=qtbot)
    monkeypatch.setattr(
        "fahmi2.ui.chat_controller.QMessageBox.question",
        lambda *a, **k: QMessageBox.StandardButton.Yes,
    )
    store = controller._store  # noqa: SLF001
    assert store is not None
    conv = controller._vm.start_conversation(Language.FR)  # noqa: SLF001
    store.save(conv)
    controller.delete_conversation(conv.conversation_id.value)
    assert store.load(conv.conversation_id) is None


def test_delete_conversation_cancelled_keeps_file(
    qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    controller, _view, _pid = _make_controller(tmp_path, with_corpus=True, qtbot=qtbot)
    monkeypatch.setattr(
        "fahmi2.ui.chat_controller.QMessageBox.question",
        lambda *a, **k: QMessageBox.StandardButton.No,
    )
    store = controller._store  # noqa: SLF001
    assert store is not None
    conv = controller._vm.start_conversation(Language.FR)  # noqa: SLF001
    store.save(conv)
    controller.delete_conversation(conv.conversation_id.value)
    assert store.load(conv.conversation_id) is not None  # annulation → conservé


def test_delete_current_conversation_resets_to_new(
    qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    controller, _view, _pid = _make_controller(tmp_path, with_corpus=True, qtbot=qtbot)
    monkeypatch.setattr(
        "fahmi2.ui.chat_controller.QMessageBox.question",
        lambda *a, **k: QMessageBox.StandardButton.Yes,
    )
    store = controller._store  # noqa: SLF001
    assert store is not None
    current = controller._conversation  # noqa: SLF001 — conversation affichée
    assert current is not None
    store.save(current)
    controller.delete_conversation(current.conversation_id.value)
    # La conversation supprimée n'est plus courante : une nouvelle l'a remplacée.
    new_current = controller._conversation  # noqa: SLF001
    assert new_current is not None
    assert new_current.conversation_id.value != current.conversation_id.value
