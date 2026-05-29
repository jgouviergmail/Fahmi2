"""Accès au document consolidé source (chemin, mtime, chapitres).

Le générateur de supports lit le document consolidé produit par la Génération
sous ``<generation_output_dir>/consolidated.{lang}.md``. Ces helpers centralisent
le chemin, l'horodatage de fraîcheur et le parsing en chapitres (réutilisés par
l'orchestrateur, l'estimateur de coût et le calcul de fraîcheur de l'UI).
"""

from __future__ import annotations

from pathlib import Path

from fahmi2.core.corpus import Chapter, parse_chapters
from fahmi2.domain.enums import Language
from fahmi2.pipeline.generation_outputs import (
    consolidated_doc_path,
    glossary_master_mtime_ns,
    load_glossary_master_terms,
    source_mtime_ns,
)

#: Helpers de lecture des livrables de génération **partagés** (source unique dans
#: ``pipeline/generation_outputs``), ré-exportés pour compatibilité des appelants.
__all__ = [
    "available_content_languages",
    "consolidated_doc_path",
    "glossary_master_mtime_ns",
    "load_chapters",
    "load_glossary_master_terms",
    "resolve_content_language",
    "source_mtime_ns",
]

_ENCODING_UTF8 = "utf-8"


def load_chapters(
    generation_output_dir: Path, language: Language
) -> tuple[Chapter, ...]:
    """Charge et parse les chapitres du doc consolidé (vide si absent).

    Args:
        generation_output_dir: Dossier des livrables de génération.
        language: Langue.

    Returns:
        Les chapitres (vide si le fichier n'existe pas).
    """
    doc = consolidated_doc_path(generation_output_dir, language)
    if not doc.exists():
        return ()
    return parse_chapters(doc.read_text(encoding=_ENCODING_UTF8))


def resolve_content_language(
    generation_output_dir: Path,
    target: Language,
    source_language: Language | None,
) -> Language | None:
    """Choisit la langue du document de **contenu** pour une langue cible.

    Préfère le doc de la langue cible (meilleure fidélité, pas de re-traduction par
    le LLM) ; sinon la langue source de la génération si son doc existe ; sinon la
    première langue produite disponible. Le support est de toute façon rédigé dans
    la **langue cible** par le générateur LLM — la génération n'a donc pas besoin
    d'avoir produit la langue cible.

    Args:
        generation_output_dir: Dossier des livrables de génération.
        target: Langue cible du support.
        source_language: Langue source de la génération (``None`` si inconnue).

    Returns:
        La langue de contenu, ou ``None`` si aucun doc consolidé n'existe.
    """
    if consolidated_doc_path(generation_output_dir, target).exists():
        return target
    if source_language is not None and consolidated_doc_path(
        generation_output_dir, source_language
    ).exists():
        return source_language
    for language in Language:
        if consolidated_doc_path(generation_output_dir, language).exists():
            return language
    return None


def available_content_languages(generation_output_dir: Path) -> list[Language]:
    """Langues dont un document consolidé existe sur disque (ordre de l'enum).

    Sert à peupler le sélecteur de langue du Dialogue : on ne propose que les langues
    **réellement produites** par la génération.

    Args:
        generation_output_dir: Dossier des livrables de génération.

    Returns:
        Liste des ``Language`` ayant un ``consolidated.{lang}.md`` (vide si aucun).
    """
    return [
        language
        for language in Language
        if consolidated_doc_path(generation_output_dir, language).exists()
    ]
