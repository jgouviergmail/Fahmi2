"""Cœur d'écriture générique des exports documentaires (Markdown / PDF / HTML).

Contrat partagé par les fonctionnalités (génération, pédagogie) : un collecteur
fournit une liste d'``ExportDocument`` (nom + Markdown + options de rendu PDF) ;
``write_documents`` écrit un fichier par document, à l'extension du format demandé.
Le **dispatch** par format vit ici (couche app) ; ``infra/export/markdown_pdf``
reste un pur *renderer*.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

from fahmi2.domain.enums import ExportFormat
from fahmi2.domain.project import Project
from fahmi2.infra.export.markdown_docx import render_markdown_to_docx
from fahmi2.infra.export.markdown_pdf import (
    EXTENSION_BY_FORMAT,
    render_markdown_to_html,
    render_markdown_to_pdf,
)
from fahmi2.infra.storage.fs_artifacts import FsArtifactStore


@dataclass(frozen=True)
class ExportDocument:
    """Un document à exporter : nom de fichier + Markdown + options de rendu PDF.

    Les options PDF n'affectent que le rendu PDF (ignorées en Markdown/HTML).

    Attributes:
        stem: Nom de fichier sans extension.
        markdown: Contenu Markdown (déjà rendu par la fonctionnalité).
        pdf_landscape: Orientation paysage du PDF (ex: glossaire large).
        pdf_column_widths: Largeurs CSS par colonne pour les tableaux PDF
            (ex: glossaire) ; ``None`` = largeurs automatiques.
    """

    stem: str
    markdown: str
    pdf_landscape: bool = False
    pdf_column_widths: tuple[str, ...] | None = None


#: Signature d'un collecteur : ``(project) -> [ExportDocument, …]``. Contrat
#: « prêt-pour-C » : un futur ``DocumentSource.collect()`` n'aurait qu'à envelopper
#: une telle fonction.
DocumentCollector = Callable[[Project], list[ExportDocument]]


@dataclass(frozen=True)
class DocumentExportResult:
    """Résultat d'un export documentaire (Markdown / PDF / HTML).

    Attributes:
        output_paths: Chemins des documents écrits.
    """

    output_paths: tuple[Path, ...]

    @property
    def document_count(self) -> int:
        """Nombre de documents écrits.

        Returns:
            Le nombre de fichiers produits.
        """
        return len(self.output_paths)


def write_documents(
    documents: Iterable[ExportDocument],
    *,
    output_dir: Path,
    fmt: ExportFormat,
) -> DocumentExportResult:
    """Écrit un fichier par ``ExportDocument`` à l'extension du format.

    Args:
        documents: Documents à écrire (nom + Markdown + options PDF).
        output_dir: Dossier de destination.
        fmt: Format documentaire (``MARKDOWN``, ``PDF``, ``HTML`` ou ``DOCX``).

    Returns:
        ``DocumentExportResult`` (chemins écrits, ordre d'entrée préservé).

    Raises:
        ValueError: Si ``fmt`` n'est pas un format documentaire (ex. ``APKG``).
        ConfigError: ``EXPORT.NO_PDF_FONT`` / ``EXPORT.PDF_RENDER_FAILED`` en PDF.
    """
    if fmt not in EXTENSION_BY_FORMAT:
        raise ValueError(f"Format non documentaire : {fmt}")
    extension = EXTENSION_BY_FORMAT[fmt]
    store = FsArtifactStore()
    paths: list[Path] = []
    for document in documents:
        path = output_dir / f"{document.stem}{extension}"
        if fmt is ExportFormat.MARKDOWN:
            store.write_text_atomic(path, document.markdown)
        elif fmt is ExportFormat.PDF:
            render_markdown_to_pdf(
                document.markdown,
                path,
                landscape=document.pdf_landscape,
                table_column_widths=document.pdf_column_widths,
            )
        elif fmt is ExportFormat.DOCX:
            render_markdown_to_docx(document.markdown, path)
        else:  # HTML (seul format documentaire restant après la garde)
            render_markdown_to_html(document.markdown, path)
        paths.append(path)
    return DocumentExportResult(output_paths=tuple(paths))
