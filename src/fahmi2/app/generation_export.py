"""Export documentaire des livrables de la Génération (consolidé + glossaire).

Lit sur disque les documents finaux de la génération (``consolidated.{lang}.md`` et
``glossary.{lang}.md`` par langue) et délègue à ``app.document_export.write_documents``
pour produire un fichier par document et par langue, dans le format demandé.
"""

from __future__ import annotations

from pathlib import Path

from fahmi2.app.document_export import DocumentExportResult, write_documents
from fahmi2.domain.enums import ExportFormat, Language
from fahmi2.domain.generation import (
    GENERATION_OUTPUT_SUBDIR,
    GENERATION_WORKSPACE_SUBDIR,
    consolidated_doc_filename,
    glossary_doc_filename,
)
from fahmi2.domain.project import Project

_MD_EXT = ".md"
_ENCODING_UTF8 = "utf-8"


def collect_generation_documents(project: Project) -> list[tuple[str, str]]:
    """Collecte les documents de génération présents sur disque (par langue).

    Itère toutes les langues (robuste : ne dépend pas de ``project.generation``,
    qui peut être ``None``) et retient les fichiers réellement présents.

    Args:
        project: Projet (résout le dossier de sortie de génération).

    Returns:
        Liste de ``(stem, markdown)`` : pour chaque langue, le consolidé puis le
        glossaire s'ils existent. ``stem`` = nom de fichier privé de ``.md``.
    """
    output_dir = (
        project.workspace_folder
        / GENERATION_WORKSPACE_SUBDIR
        / GENERATION_OUTPUT_SUBDIR
    )
    documents: list[tuple[str, str]] = []
    for language in Language:
        for filename in (
            consolidated_doc_filename(language),
            glossary_doc_filename(language),
        ):
            path = output_dir / filename
            if path.exists():
                stem = filename[: -len(_MD_EXT)]
                documents.append((stem, path.read_text(encoding=_ENCODING_UTF8)))
    return documents


def export_generation_documents(
    project: Project, *, output_dir: Path, fmt: ExportFormat
) -> DocumentExportResult:
    """Exporte les documents de génération dans le format demandé.

    Args:
        project: Projet.
        output_dir: Dossier de destination choisi par l'utilisateur (distinct du
            dossier de sortie de génération).
        fmt: Format documentaire (``MARKDOWN`` / ``PDF`` / ``HTML``).

    Returns:
        ``DocumentExportResult``.

    Raises:
        ValueError: Si ``fmt`` n'est pas documentaire.
        ConfigError: ``EXPORT.NO_PDF_FONT`` en PDF sans police Unicode.
    """
    return write_documents(
        collect_generation_documents(project), output_dir=output_dir, fmt=fmt
    )
