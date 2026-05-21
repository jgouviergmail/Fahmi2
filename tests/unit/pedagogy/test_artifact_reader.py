"""Tests de la désérialisation des artefacts de supports."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fahmi2.domain.enums import Language, SupportType
from fahmi2.domain.supports import ClozeItem, Flashcard, QcmItem, SupportArtifact
from fahmi2.infra.storage.fs_artifacts import FsArtifactStore
from fahmi2.pedagogy.artifact_reader import read_artifact
from fahmi2.pedagogy.artifact_writer import artifact_json_path, serialize_artifact


def _write(tmp_path: Path, artifact: SupportArtifact) -> Path:
    path = artifact_json_path(tmp_path, artifact.support_type, artifact.language)
    FsArtifactStore().write_json_atomic(path, serialize_artifact(artifact))
    return path


def test_read_flashcards(tmp_path: Path) -> None:
    artifact = SupportArtifact(
        support_type=SupportType.FLASHCARDS_GLOSSARY,
        language=Language.FR,
        items=(Flashcard(front="PIB", back="def", source_ref="PIB", tags=("t",)),),
        rendered_markdown="x",
    )
    parsed = read_artifact(_write(tmp_path, artifact))
    assert parsed is not None
    assert parsed.support_type is SupportType.FLASHCARDS_GLOSSARY
    assert parsed.language is Language.FR
    card = parsed.items[0]
    assert isinstance(card, Flashcard)
    assert card.front == "PIB"
    assert card.tags == ("t",)


def test_read_qcm(tmp_path: Path) -> None:
    artifact = SupportArtifact(
        support_type=SupportType.QCM,
        language=Language.FR,
        items=(
            QcmItem(
                question="Q",
                choices=("a", "b"),
                correct_index=1,
                justification="j",
                source_ref="1-c",
            ),
        ),
        rendered_markdown="x",
    )
    parsed = read_artifact(_write(tmp_path, artifact))
    assert parsed is not None
    item = parsed.items[0]
    assert isinstance(item, QcmItem)
    assert item.correct_index == 1
    assert item.choices == ("a", "b")


def test_read_cloze(tmp_path: Path) -> None:
    artifact = SupportArtifact(
        support_type=SupportType.CLOZE,
        language=Language.FR,
        items=(ClozeItem(text="a ___", answers=("x",), source_ref="1-c"),),
        rendered_markdown="x",
    )
    parsed = read_artifact(_write(tmp_path, artifact))
    assert parsed is not None
    assert isinstance(parsed.items[0], ClozeItem)


def test_read_unexportable_returns_none(tmp_path: Path) -> None:
    artifact = SupportArtifact(
        support_type=SupportType.KEY_POINTS,
        language=Language.FR,
        items=(),
        rendered_markdown="x",
    )
    assert read_artifact(_write(tmp_path, artifact)) is None


def test_read_missing_file_returns_none(tmp_path: Path) -> None:
    assert read_artifact(tmp_path / "absent.json") is None


def _write_raw(tmp_path: Path, support: SupportType, payload: dict[str, Any]) -> Path:
    path = artifact_json_path(tmp_path, support, Language.FR)
    FsArtifactStore().write_json_atomic(path, payload)
    return path


def test_read_item_with_invalid_qcm_returns_none(tmp_path: Path) -> None:
    """Un QCM dont l'item viole une contrainte domaine n'est plus propagé."""
    path = _write_raw(
        tmp_path,
        SupportType.QCM,
        {
            "support_type": SupportType.QCM.value,
            "language": Language.FR.value,
            "items": [
                {
                    "question": "Q",
                    "choices": ["a", "b"],
                    "correct_index": 5,  # hors borne
                    "justification": "j",
                    "source_ref": "1-c",
                }
            ],
        },
    )
    assert read_artifact(path) is None


def test_read_item_with_missing_key_returns_none(tmp_path: Path) -> None:
    """Une clé d'item manquante n'est plus propagée (KeyError attrapé)."""
    path = _write_raw(
        tmp_path,
        SupportType.FLASHCARDS_GLOSSARY,
        {
            "support_type": SupportType.FLASHCARDS_GLOSSARY.value,
            "language": Language.FR.value,
            "items": [{"front": "PIB"}],  # 'back'/'source_ref' manquants
        },
    )
    assert read_artifact(path) is None
