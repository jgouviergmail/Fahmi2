"""Tests du service GlossaryReconciler."""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fahmi2.app.glossary_reconciler import GlossaryReconciler
from fahmi2.domain.enums import Language, RunStatus
from fahmi2.domain.ids import ProjectId, RunId
from fahmi2.domain.project import Project
from fahmi2.domain.run import Run
from fahmi2.infra.storage.sqlite_state import SqliteState


def _setup_run(tmp_path: Path, make_settings: Any) -> tuple[SqliteState, RunId]:
    settings = make_settings()
    state = SqliteState(tmp_path / "t.db")
    project = Project(
        id=ProjectId.new(), settings=settings, created_at=datetime.now(tz=UTC)
    )
    state.upsert_project(project)
    run = Run(
        id=RunId.new(),
        project_id=project.id,
        started_at=datetime.now(tz=UTC),
        status=RunStatus.RUNNING,
        settings_snapshot=settings,
    )
    state.upsert_run(run)
    return state, run.id


def test_import_master_payload_persists_terms(
    tmp_path: Path, make_settings: Any
) -> None:
    state, run_id = _setup_run(tmp_path, make_settings)
    reconciler = GlossaryReconciler(state)
    payload = {
        "terms": [
            {
                "term": "PIB",
                "definition": "produit intérieur brut",
                "aliases": ["Produit Intérieur Brut"],
                "sources": [],
                "cross_lang": {"en": "GDP"},
            },
            {"term": "Inflation", "definition": "hausse des prix"},
        ]
    }
    n = reconciler.import_master_payload(
        run_id=run_id, language=Language.FR, payload=payload
    )
    assert n == 2
    loaded = reconciler.load_glossary(run_id, Language.FR)
    assert len(loaded) == 2
    pib = loaded.find("PIB")
    assert pib is not None
    assert pib.aliases == ("Produit Intérieur Brut",)
    assert pib.cross_lang[Language.EN] == "GDP"


def test_import_empty_payload_is_noop(
    tmp_path: Path, make_settings: Any
) -> None:
    state, run_id = _setup_run(tmp_path, make_settings)
    reconciler = GlossaryReconciler(state)
    assert reconciler.import_master_payload(
        run_id=run_id, language=Language.FR, payload={"terms": []}
    ) == 0


def test_load_glossary_returns_empty_when_no_data(
    tmp_path: Path, make_settings: Any
) -> None:
    state, run_id = _setup_run(tmp_path, make_settings)
    reconciler = GlossaryReconciler(state)
    glossary = reconciler.load_glossary(run_id, Language.FR)
    assert len(glossary) == 0
    assert glossary.language is Language.FR


def test_render_markdown_includes_all_terms_sorted(
    tmp_path: Path, make_settings: Any
) -> None:
    state, run_id = _setup_run(tmp_path, make_settings)
    reconciler = GlossaryReconciler(state)
    reconciler.import_master_payload(
        run_id=run_id,
        language=Language.FR,
        payload={
            "terms": [
                {"term": "Zorglub", "definition": "z"},
                {"term": "Alpha", "definition": "a"},
                {"term": "Méta", "definition": "m"},
            ]
        },
    )
    md = reconciler.render_markdown(run_id, Language.FR)
    assert md.startswith("# Glossaire")
    # Ordre alphabétique
    pos_alpha = md.index("Alpha")
    pos_meta = md.index("Méta")
    pos_zorglub = md.index("Zorglub")
    assert pos_alpha < pos_meta < pos_zorglub


def test_render_markdown_in_english(tmp_path: Path, make_settings: Any) -> None:
    state, run_id = _setup_run(tmp_path, make_settings)
    reconciler = GlossaryReconciler(state)
    reconciler.import_master_payload(
        run_id=run_id,
        language=Language.EN,
        payload={"terms": [{"term": "GDP", "definition": "Gross domestic product"}]},
    )
    md = reconciler.render_markdown(run_id, Language.EN)
    assert md.startswith("# Glossary")
    assert "**GDP** : Gross domestic product" in md
