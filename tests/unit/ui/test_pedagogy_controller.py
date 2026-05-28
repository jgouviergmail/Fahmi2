"""Tests du PedagogyController (logique testable + worker synchrone)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QInputDialog,
    QMessageBox,
    QWidget,
)
from pytestqt.qtbot import QtBot

from fahmi2.app.project_service import ProjectService
from fahmi2.app.secrets_service import SecretsService
from fahmi2.app.supports_orchestrator import SupportsOrchestrator
from fahmi2.core.config.paths import AppPaths
from fahmi2.core.retry.policy import RetryPolicy
from fahmi2.domain.enums import (
    ExportFormat,
    Language,
    PhaseStatus,
    RunStatus,
    SupportType,
)
from fahmi2.domain.generation import (
    GENERATION_OUTPUT_SUBDIR,
    GENERATION_WORKSPACE_SUBDIR,
    consolidated_doc_filename,
)
from fahmi2.domain.glossary import Term
from fahmi2.domain.ids import RunId
from fahmi2.domain.run import Run
from fahmi2.domain.supports import Flashcard, SupportArtifact
from fahmi2.infra.llm._fakes import FakeLLMProvider
from fahmi2.infra.prompts.loader import PromptLoader
from fahmi2.infra.secrets.interface import InMemorySecretsStore
from fahmi2.infra.storage.fs_artifacts import FsArtifactStore
from fahmi2.infra.storage.sqlite_state import SqliteState
from fahmi2.pedagogy.artifact_writer import (
    artifact_json_path,
    artifact_markdown_path,
    serialize_artifact,
)
from fahmi2.pedagogy.chapters import Chapter
from fahmi2.pedagogy.events import (
    SupportFinished,
    SupportGenerationFinished,
    SupportStarted,
)
from fahmi2.pedagogy.support_generator import SupportContext, SupportGenerator
from fahmi2.pedagogy.support_registry import SupportGeneratorRegistry
from fahmi2.pipeline.pause_token import PauseToken
from fahmi2.ui import pedagogy_controller as pc_module
from fahmi2.ui.pedagogy_controller import (
    PedagogyController,
    _pedagogy_event_to_log,
    _PedagogyWorker,
)
from fahmi2.ui.pedagogy_labels import export_labels
from fahmi2.ui.qt_event_bus import PedagogyQtEventBus
from fahmi2.ui.viewmodels.pedagogy_state import PedagogyState
from fahmi2.ui.widgets.logs_dock import LogsDock
from fahmi2.ui.widgets.pedagogy_progress_view import PedagogyProgressView
from fahmi2.ui.widgets.project_header_bar import ProjectHeaderBar

# Snapshot des libellés au moment de l'import (langue active = source FR).
EXPORT_LABELS = export_labels()


def _app_paths(tmp_path: Path) -> AppPaths:
    return AppPaths(appdata=tmp_path / "appdata", localappdata=tmp_path / "local")


class _StubGen(SupportGenerator):
    """Générateur déterministe sans LLM (artefact trivial) pour les tests."""

    def __init__(self, support_type: SupportType) -> None:
        self._support_type = support_type

    @property
    def support_type(self) -> SupportType:
        return self._support_type

    @property
    def uses_llm(self) -> bool:
        return False

    def generate(
        self,
        ctx: SupportContext,
        *,
        language: Language,
        chapters: tuple[Chapter, ...],
        glossary: tuple[Term, ...],
    ) -> SupportArtifact:
        del ctx, chapters, glossary
        return SupportArtifact(
            support_type=self._support_type,
            language=language,
            items=(),
            rendered_markdown="# Stub\n",
            cost_usd=0.0,
        )


def _make_controller(
    qtbot: QtBot, tmp_path: Path, *, with_key: bool = True
) -> tuple[PedagogyController, ProjectService, SqliteState]:
    state = SqliteState(tmp_path / "t.db")
    project_service = ProjectService(state)
    secrets_service = SecretsService(InMemorySecretsStore())
    if with_key:
        secrets_service.set_deepseek_api_key("test-key-1234")
    window = QWidget()
    qtbot.addWidget(window)
    header = ProjectHeaderBar()
    qtbot.addWidget(header)
    progress = PedagogyProgressView()
    qtbot.addWidget(progress)
    logs = LogsDock()
    qtbot.addWidget(logs)
    controller = PedagogyController(
        header_bar=header,
        progress_view=progress,
        logs_dock=logs,
        window=window,
        project_service=project_service,
        secrets_service=secrets_service,
        state=state,
        app_paths=_app_paths(tmp_path),
        registry=SupportGeneratorRegistry([_StubGen(SupportType.FLASHCARDS_CONCEPTS)]),
    )
    return controller, project_service, state


def test_on_project_selected_generation_required(
    qtbot: QtBot, tmp_path: Path, make_generation_settings: Any, make_pedagogy_settings: Any
) -> None:
    controller, project_service, _ = _make_controller(qtbot, tmp_path)
    project = project_service.create_project(
        name="P",
        workspace_folder=tmp_path / "ws",
        generation=make_generation_settings(),
        pedagogy=make_pedagogy_settings(),
    )
    controller.on_project_selected(project.id)
    assert "Génération requise" in controller._progress_view.banner_text()  # noqa: SLF001


def test_open_settings_persists_and_preserves_generation(
    qtbot: QtBot,
    tmp_path: Path,
    monkeypatch: Any,
    make_generation_settings: Any,
    make_pedagogy_settings: Any,
) -> None:
    controller, project_service, _ = _make_controller(qtbot, tmp_path)
    project = project_service.create_project(
        name="P",
        workspace_folder=tmp_path / "ws",
        generation=make_generation_settings(),
    )
    controller.on_project_selected(project.id)
    chosen = make_pedagogy_settings(
        selected_supports=frozenset({SupportType.KEY_POINTS})
    )

    class _FakeDialog:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            del args, kwargs

        def exec(self) -> int:
            return QDialog.DialogCode.Accepted

        def get_pedagogy_settings(self) -> Any:
            return chosen

    monkeypatch.setattr(pc_module, "PedagogySettingsView", _FakeDialog)
    controller.open_pedagogy_settings()

    reloaded = project_service.get_project(project.id)
    assert reloaded is not None
    assert reloaded.pedagogy is not None
    assert reloaded.pedagogy.selected_supports == frozenset({SupportType.KEY_POINTS})
    assert reloaded.generation is not None  # généré préservé


def test_event_to_log_mapping() -> None:
    now = datetime.now(tz=UTC)
    started = _pedagogy_event_to_log(
        SupportStarted(timestamp=now, support_type=SupportType.QCM, language=Language.FR)
    )
    assert started.code == "PEDAGOGY_SUPPORT_STARTED"
    finished = _pedagogy_event_to_log(
        SupportFinished(
            timestamp=now,
            support_type=SupportType.QCM,
            language=Language.FR,
            status=PhaseStatus.SUCCEEDED,
            cost_usd=0.1,
            error=None,
        )
    )
    assert finished.code == "PEDAGOGY_SUPPORT_FINISHED"
    overall = _pedagogy_event_to_log(
        SupportGenerationFinished(
            timestamp=now, status=RunStatus.COMPLETED, total_cost_usd=0.1
        )
    )
    assert overall.code == "PEDAGOGY_FINISHED"


def test_state_viewmodel_ready_after_source(
    qtbot: QtBot, tmp_path: Path, make_generation_settings: Any, make_pedagogy_settings: Any
) -> None:
    controller, project_service, state = _make_controller(qtbot, tmp_path)
    ws = tmp_path / "ws"
    project = project_service.create_project(
        name="P",
        workspace_folder=ws,
        generation=make_generation_settings(),
        pedagogy=make_pedagogy_settings(languages=(Language.FR,)),
    )
    _seed_completed_run(state, project.id, make_generation_settings())
    _write_consolidated(ws, Language.FR)
    controller.on_project_selected(project.id)
    info = controller._state_vm.compute(project)  # noqa: SLF001
    assert info.state is PedagogyState.READY


def test_export_apkg_writes_file(
    qtbot: QtBot,
    tmp_path: Path,
    monkeypatch: Any,
    make_generation_settings: Any,
    make_pedagogy_settings: Any,
) -> None:
    controller, project_service, _ = _make_controller(qtbot, tmp_path)
    ws = tmp_path / "ws"
    project = project_service.create_project(
        name="P",
        workspace_folder=ws,
        generation=make_generation_settings(),
        pedagogy=make_pedagogy_settings(),
    )
    controller.on_project_selected(project.id)
    FsArtifactStore().write_json_atomic(
        artifact_json_path(
            ws / "pedagogy", SupportType.FLASHCARDS_CONCEPTS, Language.FR
        ),
        serialize_artifact(
            SupportArtifact(
                support_type=SupportType.FLASHCARDS_CONCEPTS,
                language=Language.FR,
                items=(Flashcard(front="PIB", back="def", source_ref="PIB"),),
                rendered_markdown="x",
            )
        ),
    )
    out = tmp_path / "deck.apkg"
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", lambda *args, **kwargs: (str(out), "")
    )
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
    controller.export_apkg()
    assert out.exists()


def test_on_export_requested_markdown_writes_per_support_files(
    qtbot: QtBot,
    tmp_path: Path,
    monkeypatch: Any,
    make_generation_settings: Any,
    make_pedagogy_settings: Any,
) -> None:
    controller, project_service, _ = _make_controller(qtbot, tmp_path)
    ws = tmp_path / "ws"
    project = project_service.create_project(
        name="P",
        workspace_folder=ws,
        generation=make_generation_settings(),
        pedagogy=make_pedagogy_settings(
            export_formats=frozenset({ExportFormat.MARKDOWN})
        ),
    )
    controller.on_project_selected(project.id)
    FsArtifactStore().write_text_atomic(
        artifact_markdown_path(
            ws / "pedagogy", SupportType.FLASHCARDS_CONCEPTS, Language.FR
        ),
        "# Flashcards — Glossaire (fr)\n\n### PIB\n\ndéf\n",
    )
    out_dir = tmp_path / "export"
    monkeypatch.setattr(
        QInputDialog,
        "getItem",
        lambda *args, **kwargs: (EXPORT_LABELS[ExportFormat.MARKDOWN], True),
    )
    monkeypatch.setattr(
        QFileDialog, "getExistingDirectory", lambda *args, **kwargs: str(out_dir)
    )
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
    controller._on_export_requested()  # noqa: SLF001
    # Un fichier par support (plus d'agrégat ``supports.fr.md``).
    assert (out_dir / "flashcards_concepts.fr.md").exists()
    assert not (out_dir / "supports.fr.md").exists()


def test_on_export_requested_routes_apkg(
    qtbot: QtBot,
    tmp_path: Path,
    monkeypatch: Any,
    make_generation_settings: Any,
    make_pedagogy_settings: Any,
) -> None:
    controller, project_service, _ = _make_controller(qtbot, tmp_path)
    project = project_service.create_project(
        name="P",
        workspace_folder=tmp_path / "ws",
        generation=make_generation_settings(),
        pedagogy=make_pedagogy_settings(
            export_formats=frozenset({ExportFormat.APKG})
        ),
    )
    controller.on_project_selected(project.id)
    called: list[str] = []
    monkeypatch.setattr(controller, "export_apkg", lambda: called.append("apkg"))
    monkeypatch.setattr(
        QInputDialog,
        "getItem",
        lambda *args, **kwargs: (EXPORT_LABELS[ExportFormat.APKG], True),
    )
    controller._on_export_requested()  # noqa: SLF001
    assert called == ["apkg"]


def test_export_labels_cover_all_formats() -> None:
    """Tout ``ExportFormat`` doit avoir un libellé (sinon KeyError au choix)."""
    assert set(EXPORT_LABELS) == set(ExportFormat)


def test_on_export_requested_only_offers_configured_formats(
    qtbot: QtBot,
    tmp_path: Path,
    monkeypatch: Any,
    make_generation_settings: Any,
    make_pedagogy_settings: Any,
) -> None:
    controller, project_service, _ = _make_controller(qtbot, tmp_path)
    project = project_service.create_project(
        name="P",
        workspace_folder=tmp_path / "ws",
        generation=make_generation_settings(),
        pedagogy=make_pedagogy_settings(
            export_formats=frozenset({ExportFormat.PDF})
        ),
    )
    controller.on_project_selected(project.id)
    offered: list[list[str]] = []

    def _capture(*args: Any, **kwargs: Any) -> tuple[str, bool]:
        del kwargs
        offered.append(list(args[3]))  # items
        return "", False  # annule

    monkeypatch.setattr(QInputDialog, "getItem", _capture)
    controller._on_export_requested()  # noqa: SLF001
    assert offered == [[EXPORT_LABELS[ExportFormat.PDF]]]


def test_on_export_requested_no_configured_format(
    qtbot: QtBot,
    tmp_path: Path,
    monkeypatch: Any,
    make_generation_settings: Any,
    make_pedagogy_settings: Any,
) -> None:
    controller, project_service, _ = _make_controller(qtbot, tmp_path)
    project = project_service.create_project(
        name="P",
        workspace_folder=tmp_path / "ws",
        generation=make_generation_settings(),
        pedagogy=make_pedagogy_settings(export_formats=frozenset()),
    )
    controller.on_project_selected(project.id)
    shown: list[str] = []
    monkeypatch.setattr(
        QMessageBox, "information", lambda *a, **k: shown.append(a[1])
    )
    monkeypatch.setattr(
        QInputDialog,
        "getItem",
        lambda *a, **k: pytest.fail("ne doit pas proposer de format"),
    )
    controller._on_export_requested()  # noqa: SLF001
    assert shown  # un message d'information a été affiché


def test_clear_current_project_resets_cockpit(
    qtbot: QtBot,
    tmp_path: Path,
    make_generation_settings: Any,
    make_pedagogy_settings: Any,
) -> None:
    controller, project_service, _ = _make_controller(qtbot, tmp_path)
    project = project_service.create_project(
        name="P",
        workspace_folder=tmp_path / "ws",
        generation=make_generation_settings(),
        pedagogy=make_pedagogy_settings(),
    )
    controller.on_project_selected(project.id)
    assert controller.current_project_id == project.id
    controller.clear_current_project()
    assert controller._progress_view.banner_text() == ""  # noqa: SLF001
    assert controller._progress_view.row_count() == 0  # noqa: SLF001
    assert controller.current_project_id is None


def test_worker_runs_orchestrator(
    qtbot: QtBot, tmp_path: Path, make_generation_settings: Any, make_pedagogy_settings: Any
) -> None:
    state = SqliteState(tmp_path / "t.db")
    project_service = ProjectService(state)
    ws = tmp_path / "ws"
    project = project_service.create_project(
        name="P",
        workspace_folder=ws,
        generation=make_generation_settings(),
        pedagogy=make_pedagogy_settings(languages=(Language.FR,)),
    )
    _seed_completed_run_with_glossary(state, project, make_generation_settings())
    orchestrator = SupportsOrchestrator(
        registry=SupportGeneratorRegistry([_StubGen(SupportType.FLASHCARDS_CONCEPTS)]),
        artifacts=FsArtifactStore(),
        llm_provider=FakeLLMProvider(),
        prompts=PromptLoader(),
        retry_policy=RetryPolicy(jitter=False),
    )
    bus = PedagogyQtEventBus()
    worker = _PedagogyWorker(
        orchestrator=orchestrator,
        project=project,
        pause_token=PauseToken(),
        event_bus=bus,
    )
    statuses: list[object] = []
    worker.finished.connect(statuses.append)
    worker.run_generation()
    assert statuses == [RunStatus.COMPLETED]


def test_available_languages_offers_all(
    qtbot: QtBot,
    tmp_path: Path,
    make_generation_settings: Any,
    make_pedagogy_settings: Any,
) -> None:
    controller, project_service, _ = _make_controller(qtbot, tmp_path)
    project = project_service.create_project(
        name="P",
        workspace_folder=tmp_path / "ws",
        generation=make_generation_settings(),
        pedagogy=make_pedagogy_settings(),
    )
    langs = controller._available_languages(project)  # noqa: SLF001
    assert set(langs) == set(Language)


def test_reset_pedagogy_removes_dir_and_refreshes(
    qtbot: QtBot,
    tmp_path: Path,
    monkeypatch: Any,
    make_generation_settings: Any,
    make_pedagogy_settings: Any,
) -> None:
    controller, project_service, _ = _make_controller(qtbot, tmp_path)
    project = project_service.create_project(
        name="P",
        workspace_folder=tmp_path / "ws",
        generation=make_generation_settings(),
        pedagogy=make_pedagogy_settings(),
    )
    controller.on_project_selected(project.id)
    ped_dir = tmp_path / "ws" / "pedagogy"
    ped_dir.mkdir(parents=True, exist_ok=True)
    (ped_dir / "qcm").mkdir()
    (ped_dir / "manifest.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *a, **k: QMessageBox.StandardButton.Yes,
    )
    emitted: list[int] = []
    controller.run_state_changed.connect(lambda: emitted.append(1))

    controller.reset_pedagogy()

    assert not ped_dir.exists()
    assert emitted  # la sidebar est notifiée du changement de statut


def test_reset_pedagogy_cancelled_keeps_dir(
    qtbot: QtBot,
    tmp_path: Path,
    monkeypatch: Any,
    make_generation_settings: Any,
    make_pedagogy_settings: Any,
) -> None:
    controller, project_service, _ = _make_controller(qtbot, tmp_path)
    project = project_service.create_project(
        name="P",
        workspace_folder=tmp_path / "ws",
        generation=make_generation_settings(),
        pedagogy=make_pedagogy_settings(),
    )
    controller.on_project_selected(project.id)
    ped_dir = tmp_path / "ws" / "pedagogy"
    ped_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(
        QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.No
    )
    controller.reset_pedagogy()
    # Annulation : le dossier est conservé.
    assert ped_dir.exists()


def test_on_project_selected_shows_preview(
    qtbot: QtBot,
    tmp_path: Path,
    make_generation_settings: Any,
    make_pedagogy_settings: Any,
) -> None:
    controller, project_service, _ = _make_controller(qtbot, tmp_path)
    project = project_service.create_project(
        name="P",
        workspace_folder=tmp_path / "ws",
        generation=make_generation_settings(),
        pedagogy=make_pedagogy_settings(
            selected_supports=frozenset(
                {SupportType.QCM, SupportType.KEY_POINTS}
            ),
        ),
    )
    controller.on_project_selected(project.id)
    # Prévisualisation : une ligne par support sélectionné (pas une grille vide),
    # comme le dashboard Génération affiche les vidéos détectées avant le 1er run.
    assert controller._progress_view.row_count() == 2  # noqa: SLF001


def _seed_completed_run(state: SqliteState, project_id: Any, settings: Any) -> None:
    state.upsert_run(
        Run(
            id=RunId.new(),
            project_id=project_id,
            started_at=datetime.now(tz=UTC),
            status=RunStatus.COMPLETED,
            settings_snapshot=settings,
        )
    )


def _seed_completed_run_with_glossary(
    state: SqliteState, project: Any, settings: Any
) -> None:
    state.upsert_run(
        Run(
            id=RunId.new(),
            project_id=project.id,
            started_at=datetime.now(tz=UTC),
            status=RunStatus.COMPLETED,
            settings_snapshot=settings,
        )
    )
    FsArtifactStore().write_json_atomic(
        project.workspace_folder / GENERATION_WORKSPACE_SUBDIR / "glossary_master.json",
        {"terms": [{"term": "PIB", "definition": "Produit intérieur brut"}]},
    )


def _write_consolidated(ws: Path, language: Language) -> None:
    doc = (
        ws
        / GENERATION_WORKSPACE_SUBDIR
        / GENERATION_OUTPUT_SUBDIR
        / consolidated_doc_filename(language)
    )
    FsArtifactStore().write_text_atomic(doc, "# Cours\n\n# 1. Bases\n\nContenu.\n")
