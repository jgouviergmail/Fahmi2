"""Accès au document consolidé source (chemin, mtime, chapitres).

Le générateur de supports lit le document consolidé produit par la Génération
sous ``<generation_output_dir>/consolidated.{lang}.md``. Ces helpers centralisent
le chemin, l'horodatage de fraîcheur et le parsing en chapitres (réutilisés par
l'orchestrateur, l'estimateur de coût et le calcul de fraîcheur de l'UI).
"""

from __future__ import annotations

import json
from pathlib import Path

from fahmi2.domain.enums import Language
from fahmi2.domain.generation import consolidated_doc_filename
from fahmi2.domain.glossary import Term, parse_glossary_master_terms
from fahmi2.pedagogy.chapters import Chapter, parse_chapters

_ENCODING_UTF8 = "utf-8"
_GLOSSARY_MASTER_FILENAME = "glossary_master.json"


def consolidated_doc_path(generation_output_dir: Path, language: Language) -> Path:
    """Chemin du document consolidé pour une langue.

    Args:
        generation_output_dir: Dossier des livrables de génération.
        language: Langue.

    Returns:
        Le chemin ``…/consolidated.{lang}.md``.
    """
    return generation_output_dir / consolidated_doc_filename(language)


def source_mtime_ns(generation_output_dir: Path, language: Language) -> int | None:
    """mtime (ns) du doc consolidé, ou ``None`` s'il est absent.

    Args:
        generation_output_dir: Dossier des livrables de génération.
        language: Langue.

    Returns:
        Le ``st_mtime_ns``, ou ``None``.
    """
    doc = consolidated_doc_path(generation_output_dir, language)
    if not doc.exists():
        return None
    return doc.stat().st_mtime_ns


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


def load_glossary_master_terms(generation_dir: Path) -> tuple[Term, ...]:
    """Charge le glossaire master (langue source) depuis le disque.

    Lit ``<generation_dir>/glossary_master.json`` produit par la phase 2 — comme
    le pipeline (``load_glossary_master``). Sert l'injection terminologique des
    prompts des générateurs LLM.

    Args:
        generation_dir: Dossier de travail de la génération (contient le master).

    Returns:
        Les termes (tuple vide si le master n'existe pas).
    """
    path = generation_dir / _GLOSSARY_MASTER_FILENAME
    if not path.exists():
        return ()
    payload = json.loads(path.read_text(encoding=_ENCODING_UTF8))
    return parse_glossary_master_terms(payload)
