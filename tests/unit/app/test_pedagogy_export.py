"""Tests du service d'export pédagogie vers Anki."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fahmi2.app.pedagogy_export import export_pedagogy_to_apkg
from fahmi2.domain.enums import Language, SupportType
from fahmi2.domain.ids import ProjectId
from fahmi2.domain.pedagogy import PEDAGOGY_WORKSPACE_SUBDIR
from fahmi2.domain.project import Project
from fahmi2.domain.supports import Flashcard, QcmItem, SupportArtifact
from fahmi2.infra.storage.fs_artifacts import FsArtifactStore
from fahmi2.pedagogy.artifact_writer import artifact_json_path, serialize_artifact


def _project(tmp_path: Path, make_pedagogy_settings: Any) -> Project:
    return Project(
        id=ProjectId.new(),
        name="Mon Cours",
        workspace_folder=tmp_path / "ws",
        created_at=datetime.now(tz=UTC),
        pedagogy=make_pedagogy_settings(),
    )


def _write_artifact(pedagogy_dir: Path, artifact: SupportArtifact) -> None:
    FsArtifactStore().write_json_atomic(
        artifact_json_path(pedagogy_dir, artifact.support_type, artifact.language),
        serialize_artifact(artifact),
    )


def test_export_collects_artifacts(
    tmp_path: Path, make_pedagogy_settings: Any
) -> None:
    project = _project(tmp_path, make_pedagogy_settings)
    pedagogy_dir = project.workspace_folder / PEDAGOGY_WORKSPACE_SUBDIR
    _write_artifact(
        pedagogy_dir,
        SupportArtifact(
            support_type=SupportType.FLASHCARDS_GLOSSARY,
            language=Language.FR,
            items=(Flashcard(front="PIB", back="def", source_ref="PIB"),),
            rendered_markdown="x",
        ),
    )
    _write_artifact(
        pedagogy_dir,
        SupportArtifact(
            support_type=SupportType.QCM,
            language=Language.FR,
            items=(
                QcmItem(
                    question="Q",
                    choices=("a", "b"),
                    correct_index=0,
                    justification="j",
                    source_ref="1-c",
                ),
            ),
            rendered_markdown="x",
        ),
    )
    out = tmp_path / "deck.apkg"
    result = export_pedagogy_to_apkg(project, output_path=out)
    assert out.exists()
    assert result.note_count == 2


def test_export_no_artifacts_is_empty(
    tmp_path: Path, make_pedagogy_settings: Any
) -> None:
    project = _project(tmp_path, make_pedagogy_settings)
    out = tmp_path / "deck.apkg"
    result = export_pedagogy_to_apkg(project, output_path=out)
    assert result.note_count == 0
    assert out.exists()
