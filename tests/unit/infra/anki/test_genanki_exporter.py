"""Tests de l'exportateur Anki (genanki)."""

from __future__ import annotations

import zipfile
from pathlib import Path

from fahmi2.domain.enums import Language, SupportType
from fahmi2.domain.supports import ClozeItem, Flashcard, QcmItem
from fahmi2.infra.anki.genanki_exporter import (
    GenankiExporter,
    _sanitize_tag,
    _to_anki_cloze,
)
from fahmi2.pedagogy.artifact_reader import ParsedArtifact


def test_to_anki_cloze() -> None:
    assert _to_anki_cloze("a ___ b ___", ("x", "y")) == "a {{c1::x}} b {{c2::y}}"


def test_sanitize_tag_replaces_whitespace() -> None:
    assert _sanitize_tag("Intelligence artificielle") == "Intelligence_artificielle"
    assert _sanitize_tag("master expert") == "master_expert"
    assert _sanitize_tag("  multi   espaces ") == "multi_espaces"


def test_export_multiword_glossary_term_does_not_raise(tmp_path: Path) -> None:
    """Un terme de glossaire multi-mots (tag avec espace) ne fait plus échouer."""
    artifacts = [
        ParsedArtifact(
            support_type=SupportType.FLASHCARDS_GLOSSARY,
            language=Language.FR,
            items=(
                Flashcard(
                    front="Intelligence artificielle",
                    back="def",
                    source_ref="Intelligence artificielle",
                ),
            ),
        ),
    ]
    out = tmp_path / "deck.apkg"
    result = GenankiExporter().export_to_file(
        artifacts,
        deck_root="Projet",
        difficulty="master expert",
        output_path=out,
    )
    assert result.note_count == 1
    assert out.exists()


def test_to_anki_cloze_more_blanks_than_answers() -> None:
    assert _to_anki_cloze("a ___ b ___", ("x",)) == "a {{c1::x}} b ___"


def _artifacts() -> list[ParsedArtifact]:
    return [
        ParsedArtifact(
            support_type=SupportType.FLASHCARDS_GLOSSARY,
            language=Language.FR,
            items=(Flashcard(front="PIB", back="def", source_ref="PIB"),),
        ),
        ParsedArtifact(
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
        ),
        ParsedArtifact(
            support_type=SupportType.CLOZE,
            language=Language.FR,
            items=(ClozeItem(text="a ___", answers=("x",), source_ref="1-c"),),
        ),
    ]


def test_export_writes_apkg(tmp_path: Path) -> None:
    out = tmp_path / "deck.apkg"
    result = GenankiExporter().export_to_file(
        _artifacts(), deck_root="Projet", difficulty="licence", output_path=out
    )
    assert out.exists()
    assert out.stat().st_size > 0
    assert result.note_count == 3
    assert result.deck_count == 3
    # Le .apkg est un zip contenant la collection SQLite.
    assert zipfile.is_zipfile(out)


def test_export_empty_writes_valid_package(tmp_path: Path) -> None:
    out = tmp_path / "empty.apkg"
    result = GenankiExporter().export_to_file(
        [], deck_root="Projet", difficulty="licence", output_path=out
    )
    assert result.note_count == 0
    assert out.exists()


def test_guid_is_stable() -> None:
    artifact = ParsedArtifact(
        support_type=SupportType.FLASHCARDS_GLOSSARY,
        language=Language.FR,
        items=(Flashcard(front="PIB", back="def", source_ref="PIB"),),
    )
    exporter = GenankiExporter()
    g1 = exporter._note_guid(artifact, "PIB")  # noqa: SLF001
    g2 = exporter._note_guid(artifact, "PIB")  # noqa: SLF001
    assert g1 == g2
