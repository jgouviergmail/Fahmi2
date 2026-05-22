"""Smoke tests du ChatController (pytest-qt, provider LLM injecté)."""

from __future__ import annotations

from pathlib import Path

from pytestqt.qtbot import QtBot

from fahmi2.app.project_service import ProjectService
from fahmi2.app.secrets_service import SecretsService
from fahmi2.core.config.paths import AppPaths
from fahmi2.domain.chat import ChatSettings
from fahmi2.domain.enums import ChatTabState, Language
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
) -> tuple[ChatController, ChatView, object]:
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
