"""Export documentaire des livrables de la Génération (consolidé + glossaire).

Lit sur disque les documents finaux de la génération (``consolidated.{lang}.md`` et
``glossary.{lang}.md`` par langue) et délègue à ``app.document_export.write_documents``
pour produire un fichier par document et par langue, dans le format demandé.
"""

from __future__ import annotations

from pathlib import Path

from fahmi2.app.document_export import (
    DocumentExportResult,
    ExportDocument,
    write_documents,
)
from fahmi2.domain.enums import ExportFormat, Language
from fahmi2.domain.generation import (
    GENERATION_OUTPUT_SUBDIR,
    GENERATION_WORKSPACE_SUBDIR,
    consolidated_doc_filename,
    glossary_doc_filename,
)
from fahmi2.domain.project import Project

_ENCODING_UTF8 = "utf-8"

#: Le glossaire (tableau Terme / Acronyme / Signification / Définition, dont les 2
#: colonnes du milieu sont souvent vides) est exporté en **paysage** avec des
#: largeurs de colonnes dédiées (sinon les définitions sont écrasées et illisibles).
_GLOSSARY_PDF_COLUMN_WIDTHS: tuple[str, ...] = ("20%", "12%", "23%", "45%")


def collect_generation_documents(project: Project) -> list[ExportDocument]:
    """Collecte les documents de génération présents sur disque (par langue).

    Itère toutes les langues (robuste : ne dépend pas de ``project.generation``,
    qui peut être ``None``) et retient les fichiers réellement présents. Le
    consolidé est en portrait ; le **glossaire** en paysage avec largeurs de
    colonnes dédiées.

    Args:
        project: Projet (résout le dossier de sortie de génération).

    Returns:
        Liste d'``ExportDocument`` : pour chaque langue, le consolidé puis le
        glossaire s'ils existent. ``stem`` = nom de fichier privé de ``.md``.
    """
    output_dir = (
        project.workspace_folder
        / GENERATION_WORKSPACE_SUBDIR
        / GENERATION_OUTPUT_SUBDIR
    )
    documents: list[ExportDocument] = []
    for language in Language:
        consolidated = output_dir / consolidated_doc_filename(language)
        if consolidated.exists():
            documents.append(
                ExportDocument(
                    stem=consolidated.stem,
                    markdown=consolidated.read_text(encoding=_ENCODING_UTF8),
                )
            )
        glossary = output_dir / glossary_doc_filename(language)
        if glossary.exists():
            documents.append(
                ExportDocument(
                    stem=glossary.stem,
                    markdown=glossary.read_text(encoding=_ENCODING_UTF8),
                    pdf_landscape=True,
                    pdf_column_widths=_GLOSSARY_PDF_COLUMN_WIDTHS,
                )
            )
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
