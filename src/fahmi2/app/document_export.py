"""Cœur d'écriture générique des exports documentaires (Markdown / PDF / HTML).

Contrat partagé par les fonctionnalités (génération, pédagogie) : un collecteur
fournit une liste ``(stem, markdown)`` ; ``write_documents`` écrit un fichier par
couple, à l'extension du format demandé. Le **dispatch** par format vit ici (couche
app) ; ``infra/export/markdown_pdf`` reste un pur *renderer*.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

from fahmi2.domain.enums import ExportFormat
from fahmi2.domain.project import Project
from fahmi2.infra.export.markdown_pdf import (
    EXTENSION_BY_FORMAT,
    render_markdown_to_html,
    render_markdown_to_pdf,
)
from fahmi2.infra.storage.fs_artifacts import FsArtifactStore

#: Signature d'un collecteur : ``(project) -> [(stem, markdown), …]`` (stem sans
#: extension). Contrat « prêt-pour-C » : un futur ``DocumentSource.collect()``
#: n'aurait qu'à envelopper une telle fonction.
DocumentCollector = Callable[[Project], list[tuple[str, str]]]


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
    documents: Iterable[tuple[str, str]],
    *,
    output_dir: Path,
    fmt: ExportFormat,
) -> DocumentExportResult:
    """Écrit un fichier par ``(stem, markdown)`` à l'extension du format.

    Args:
        documents: Couples ``(stem, markdown)`` (stem sans extension).
        output_dir: Dossier de destination.
        fmt: Format documentaire (``MARKDOWN``, ``PDF`` ou ``HTML``).

    Returns:
        ``DocumentExportResult`` (chemins écrits, ordre d'entrée préservé).

    Raises:
        ValueError: Si ``fmt`` n'est pas un format documentaire (ex. ``APKG``).
        ConfigError: ``EXPORT.NO_PDF_FONT`` en PDF sans police Unicode.
    """
    if fmt not in EXTENSION_BY_FORMAT:
        raise ValueError(f"Format non documentaire : {fmt}")
    extension = EXTENSION_BY_FORMAT[fmt]
    store = FsArtifactStore()
    paths: list[Path] = []
    for stem, markdown_text in documents:
        path = output_dir / f"{stem}{extension}"
        if fmt is ExportFormat.MARKDOWN:
            store.write_text_atomic(path, markdown_text)
        elif fmt is ExportFormat.PDF:
            render_markdown_to_pdf(markdown_text, path)
        else:  # HTML (seul format documentaire restant après la garde)
            render_markdown_to_html(markdown_text, path)
        paths.append(path)
    return DocumentExportResult(output_paths=tuple(paths))
