"""Chemins et sérialisation des artefacts de supports pédagogiques.

Layout sur disque : ``<pedagogy_dir>/<support>/<lang>/<support>.{json,md}``.
Le JSON porte la représentation structurée (items) ; le ``.md`` le rendu lisible.
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from fahmi2.domain.enums import Language, SupportType
from fahmi2.domain.supports import SupportArtifact, SupportItem

_JSON_EXT = ".json"
_MD_EXT = ".md"


def support_dir(
    pedagogy_dir: Path, support_type: SupportType, language: Language
) -> Path:
    """Dossier d'un support pour une langue.

    Args:
        pedagogy_dir: Dossier ``<emplacement>/pedagogy``.
        support_type: Type de support.
        language: Langue.

    Returns:
        ``<pedagogy_dir>/<support>/<lang>``.
    """
    return pedagogy_dir / support_type.value / language.value


def artifact_json_path(
    pedagogy_dir: Path, support_type: SupportType, language: Language
) -> Path:
    """Chemin du fichier JSON d'un support.

    Args:
        pedagogy_dir: Dossier pédagogie.
        support_type: Type de support.
        language: Langue.

    Returns:
        Le chemin ``…/<support>.json``.
    """
    return (
        support_dir(pedagogy_dir, support_type, language)
        / f"{support_type.value}{_JSON_EXT}"
    )


def artifact_markdown_path(
    pedagogy_dir: Path, support_type: SupportType, language: Language
) -> Path:
    """Chemin du fichier Markdown d'un support.

    Args:
        pedagogy_dir: Dossier pédagogie.
        support_type: Type de support.
        language: Langue.

    Returns:
        Le chemin ``…/<support>.md``.
    """
    return (
        support_dir(pedagogy_dir, support_type, language)
        / f"{support_type.value}{_MD_EXT}"
    )


def serialize_artifact(artifact: SupportArtifact) -> dict[str, Any]:
    """Sérialise un ``SupportArtifact`` en dict JSON-compatible.

    Args:
        artifact: Artefact à sérialiser.

    Returns:
        Dict ``{support_type, language, cost_usd, items: [...]}``.
    """
    return {
        "support_type": artifact.support_type.value,
        "language": artifact.language.value,
        "cost_usd": artifact.cost_usd,
        "items": [_serialize_item(item) for item in artifact.items],
    }


def _serialize_item(item: SupportItem) -> dict[str, Any]:
    """Sérialise un item de support (dataclass plat).

    Args:
        item: Item à sérialiser.

    Returns:
        Dict des champs.
    """
    return asdict(item)
