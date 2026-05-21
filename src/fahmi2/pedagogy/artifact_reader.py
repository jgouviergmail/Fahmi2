"""Lecture/désérialisation des artefacts de supports (inverse du writer).

Reconstruit les entités de support depuis le JSON persisté. Limité aux types
**exportables vers Anki** (Flashcard, ClozeItem, QcmItem) ; les autres types
renvoient ``None`` (ils relèvent de l'export Markdown/PDF, SP3/02).
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fahmi2.domain.enums import Language, SupportType
from fahmi2.domain.supports import ClozeItem, Flashcard, QcmItem, SupportItem

_ENCODING_UTF8 = "utf-8"


@dataclass(frozen=True)
class ParsedArtifact:
    """Artefact désérialisé (sous-ensemble exportable Anki).

    Attributes:
        support_type: Type de support.
        language: Langue.
        items: Entités reconstruites.
    """

    support_type: SupportType
    language: Language
    items: tuple[SupportItem, ...]


def _flashcard(raw: dict[str, Any]) -> Flashcard:
    """Reconstruit une ``Flashcard`` depuis son dict sérialisé."""
    return Flashcard(
        front=str(raw["front"]),
        back=str(raw["back"]),
        source_ref=str(raw["source_ref"]),
        tags=tuple(str(t) for t in raw.get("tags", [])),
    )


def _qcm(raw: dict[str, Any]) -> QcmItem:
    """Reconstruit un ``QcmItem`` depuis son dict sérialisé."""
    return QcmItem(
        question=str(raw["question"]),
        choices=tuple(str(c) for c in raw["choices"]),
        correct_index=int(raw["correct_index"]),
        justification=str(raw["justification"]),
        source_ref=str(raw["source_ref"]),
    )


def _cloze(raw: dict[str, Any]) -> ClozeItem:
    """Reconstruit un ``ClozeItem`` depuis son dict sérialisé."""
    return ClozeItem(
        text=str(raw["text"]),
        answers=tuple(str(a) for a in raw["answers"]),
        source_ref=str(raw["source_ref"]),
    )


#: Désérialiseurs d'items par type de support exportable Anki.
_ITEM_DESERIALIZERS: dict[SupportType, Callable[[dict[str, Any]], SupportItem]] = {
    SupportType.FLASHCARDS_CONCEPTS: _flashcard,
    SupportType.QCM: _qcm,
    SupportType.CLOZE: _cloze,
}


def read_artifact(json_path: Path) -> ParsedArtifact | None:
    """Lit un artefact JSON et reconstruit ses items (si exportable Anki).

    Args:
        json_path: Chemin du fichier ``<support>.json``.

    Returns:
        Le ``ParsedArtifact``, ou ``None`` si le fichier est absent/illisible
        ou si le type de support n'est pas exportable vers Anki.
    """
    if not json_path.exists():
        return None
    try:
        payload = json.loads(json_path.read_text(encoding=_ENCODING_UTF8))
        support_type = SupportType(payload["support_type"])
        language = Language(payload["language"])
        deserializer = _ITEM_DESERIALIZERS.get(support_type)
        if deserializer is None:
            return None
        items = tuple(deserializer(dict(raw)) for raw in payload.get("items", []))
    except (OSError, json.JSONDecodeError, KeyError, ValueError, TypeError):
        # Header *ou* item illisible/invalide (clé manquante, valeur d'enum ou
        # entité hors contrainte) : on ignore l'artefact plutôt que de propager.
        return None
    return ParsedArtifact(support_type=support_type, language=language, items=items)
