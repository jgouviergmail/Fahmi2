"""Lecture/désérialisation des artefacts de supports (inverse du writer).

Reconstruit les entités de support depuis le JSON persisté. Limité aux types
**exportables vers Anki** (Flashcard, ClozeItem, QcmItem) ; les autres types
renvoient ``None`` (ils relèvent de l'export Markdown/PDF, SP3/02).
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fahmi2.domain.enums import Language, SupportType
from fahmi2.domain.supports import ClozeItem, Flashcard, QcmItem, SupportItem
from fahmi2.pedagogy.artifact_writer import artifact_json_path

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


def read_artifact_cost(json_path: Path) -> float | None:
    """Lit le coût de génération d'un artefact (tous types de supports).

    Contrairement à ``read_artifact`` (limité aux types exportables Anki), lit
    seulement le coût — utilisable pour **tout** support afin de reconstruire
    l'état/coût des supports déjà générés (dashboard à la sélection d'un projet).

    Args:
        json_path: Chemin du fichier ``<support>.json``.

    Returns:
        Le coût USD, ou ``None`` si le fichier est absent ou illisible.
    """
    if not json_path.exists():
        return None
    try:
        payload = json.loads(json_path.read_text(encoding=_ENCODING_UTF8))
        return float(payload["cost_usd"])
    except (OSError, json.JSONDecodeError, KeyError, ValueError, TypeError):
        return None


def read_generated_costs(
    pedagogy_dir: Path,
    supports: Iterable[SupportType],
    languages: Iterable[Language],
) -> dict[tuple[SupportType, Language], float]:
    """Lit le coût des supports déjà générés présents sur disque.

    Pour chaque ``(support, langue)`` dont l'artefact JSON existe, lit son coût.
    Sert à reconstruire l'état du dashboard à la sélection d'un projet (supports
    déjà générés affichés « terminés » avec leur coût), à parité avec la Génération.

    Args:
        pedagogy_dir: Dossier ``<emplacement>/pedagogy``.
        supports: Supports à considérer (sélection courante).
        languages: Langues à considérer (sélection courante).

    Returns:
        Le coût USD par ``(support, langue)`` généré (les absents sont omis).
    """
    costs: dict[tuple[SupportType, Language], float] = {}
    for language in languages:
        for support in supports:
            cost = read_artifact_cost(
                artifact_json_path(pedagogy_dir, support, language)
            )
            if cost is not None:
                costs[(support, language)] = cost
    return costs
