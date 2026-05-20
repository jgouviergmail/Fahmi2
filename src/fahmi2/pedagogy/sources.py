"""Accès au document consolidé source (chemin, mtime, chapitres).

Le générateur de supports lit le document consolidé produit par la Génération
sous ``<generation_output_dir>/consolidated.{lang}.md``. Ces helpers centralisent
le chemin, l'horodatage de fraîcheur et le parsing en chapitres (réutilisés par
l'orchestrateur, l'estimateur de coût et le calcul de fraîcheur de l'UI).
"""

from __future__ import annotations

from pathlib import Path

from fahmi2.domain.enums import Language
from fahmi2.domain.generation import consolidated_doc_filename
from fahmi2.pedagogy.chapters import Chapter, parse_chapters

_ENCODING_UTF8 = "utf-8"


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
