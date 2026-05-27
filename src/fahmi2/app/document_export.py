"""Cœur d'écriture générique des exports documentaires (Markdown / PDF / HTML / DOCX).

Contrat partagé par les fonctionnalités (génération, pédagogie) : un collecteur
fournit une liste d'``ExportDocument`` (nom + Markdown + options de rendu + langue) ;
``write_documents`` écrit un fichier par document, à l'extension du format demandé.
Le **dispatch** par format vit ici (couche app) ; ``infra/export/markdown_pdf`` et
``markdown_docx`` restent de purs *renderers*.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

from fahmi2.domain.enums import ExportFormat, Language
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
    """Un document à exporter : nom de fichier + Markdown + options de rendu.

    ``landscape`` oriente le **PDF et le DOCX** ; ``pdf_column_widths`` n'affecte que
    le PDF ; ``language`` pilote police et direction des rendus **PDF, HTML et DOCX**
    (sans effet sur le Markdown brut).

    Attributes:
        stem: Nom de fichier sans extension.
        markdown: Contenu Markdown (déjà rendu par la fonctionnalité).
        landscape: Orientation paysage du PDF **et** du DOCX (ex: glossaire large).
        pdf_column_widths: Largeurs CSS par colonne pour les tableaux PDF
            (ex: glossaire) ; ``None`` = largeurs automatiques.
        language: Langue du contenu ; pilote police et direction PDF/HTML/DOCX
            (chinois → police CJK ; arabe → RTL, y compris en DOCX). Défaut ``FR``.
    """

    stem: str
    markdown: str
    landscape: bool = False
    pdf_column_widths: tuple[str, ...] | None = None
    language: Language = Language.FR


#: Signature d'un collecteur : ``(project) -> [ExportDocument, …]``. Contrat
#: « prêt-pour-C » : un futur ``DocumentSource.collect()`` n'aurait qu'à envelopper
#: une telle fonction.
DocumentCollector = Callable[[Project], list[ExportDocument]]


@dataclass(frozen=True)
class DocumentExportResult:
    """Résultat d'un export documentaire (Markdown / PDF / HTML / DOCX).

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
        documents: Documents à écrire (nom + Markdown + options de rendu + langue).
        output_dir: Dossier de destination.
        fmt: Format documentaire (``MARKDOWN``, ``PDF``, ``HTML`` ou ``DOCX``).

    Returns:
        ``DocumentExportResult`` (chemins écrits, ordre d'entrée préservé).

    Raises:
        ValueError: Si ``fmt`` n'est pas un format documentaire (ex. ``APKG``).
        ConfigError: en PDF, ``EXPORT.NO_PDF_FONT`` (Arial absente),
            ``EXPORT.NO_CJK_FONT`` (police chinoise absente, langue ZH) ou
            ``EXPORT.PDF_RENDER_FAILED`` (échec du moteur de rendu).
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
                landscape=document.landscape,
                table_column_widths=document.pdf_column_widths,
                language=document.language,
            )
        elif fmt is ExportFormat.DOCX:
            render_markdown_to_docx(
                document.markdown,
                path,
                landscape=document.landscape,
                language=document.language,
            )
        else:  # HTML (seul format documentaire restant après la garde)
            render_markdown_to_html(document.markdown, path, language=document.language)
        paths.append(path)
    return DocumentExportResult(output_paths=tuple(paths))
