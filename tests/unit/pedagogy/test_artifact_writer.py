"""Tests de la sérialisation et des chemins d'artefacts de supports."""

from __future__ import annotations

from pathlib import Path

from fahmi2.domain.enums import Language, SupportType
from fahmi2.domain.supports import Flashcard, SupportArtifact
from fahmi2.pedagogy.artifact_writer import (
    artifact_json_path,
    artifact_markdown_path,
    serialize_artifact,
)


def test_paths_layout() -> None:
    base = Path("/ws/pedagogy")
    st, lang = SupportType.FLASHCARDS_GLOSSARY, Language.FR
    assert artifact_json_path(base, st, lang) == (
        base / "flashcards_glossary" / "fr" / "flashcards_glossary.json"
    )
    assert artifact_markdown_path(base, st, lang) == (
        base / "flashcards_glossary" / "fr" / "flashcards_glossary.md"
    )


def test_serialize_artifact() -> None:
    artifact = SupportArtifact(
        support_type=SupportType.FLASHCARDS_GLOSSARY,
        language=Language.FR,
        items=(Flashcard(front="PIB", back="def", source_ref="PIB", tags=("a", "b")),),
        rendered_markdown="# x",
        cost_usd=0.0,
    )
    payload = serialize_artifact(artifact)
    assert payload["support_type"] == "flashcards_glossary"
    assert payload["language"] == "fr"
    assert payload["cost_usd"] == 0.0
    assert payload["items"] == [
        {"front": "PIB", "back": "def", "source_ref": "PIB", "tags": ("a", "b")}
    ]
