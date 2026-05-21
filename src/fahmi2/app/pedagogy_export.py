"""Services d'export des supports pédagogiques (Anki, Markdown, PDF).

Scanne le dossier ``pedagogy/`` d'un projet et produit des livrables :

- **Anki `.apkg`** : désérialise les artefacts exportables (flashcards, cloze, QCM)
  et délègue à l'adapter ``GenankiExporter``.
- **Markdown / PDF** : réutilise le Markdown **déjà rendu** (`<support>.md` /
  `<support>.corrige.md`), agrège par langue (sujet / corrigé séparés) et écrit les
  fichiers (PDF via ``infra/export/markdown_pdf``).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from fahmi2.domain.enums import Language
from fahmi2.domain.pedagogy import PEDAGOGY_WORKSPACE_SUBDIR
from fahmi2.domain.project import Project
from fahmi2.infra.anki.genanki_exporter import AnkiExportResult, GenankiExporter
from fahmi2.infra.export.markdown_pdf import assemble_markdown, render_markdown_to_pdf
from fahmi2.infra.storage.fs_artifacts import FsArtifactStore
from fahmi2.pedagogy.artifact_reader import ParsedArtifact, read_artifact
from fahmi2.pedagogy.artifact_writer import (
    artifact_correction_markdown_path,
    artifact_markdown_path,
)
from fahmi2.pedagogy.labels import language_label
from fahmi2.pedagogy.support_registry import SupportGeneratorRegistry

#: Glob des artefacts JSON : ``<support>/<lang>/<support>.json`` (profondeur 3).
#: Exclut ``pedagogy/manifest.json`` (profondeur 1).
_ARTIFACT_JSON_GLOB = "*/*/*.json"

_ENCODING_UTF8 = "utf-8"
_SUBJECT_STEM = "supports.{lang}"
_CORRECTION_STEM = "supports.{lang}.corrige"
_MD_EXT = ".md"
_PDF_EXT = ".pdf"
_SUBJECT_TITLE = "Supports de révision — {lang}"
_CORRECTION_TITLE = "Supports de révision (corrigé) — {lang}"


def export_pedagogy_to_apkg(project: Project, *, output_path: Path) -> AnkiExportResult:
    """Scanne ``pedagogy/`` et exporte les supports exportables vers un ``.apkg``.

    Args:
        project: Projet (nom = racine de deck ; pédagogie pour la difficulté).
        output_path: Chemin du fichier ``.apkg`` à écrire.

    Returns:
        ``AnkiExportResult`` (chemin + nb de notes + nb de decks).
    """
    pedagogy_dir = project.workspace_folder / PEDAGOGY_WORKSPACE_SUBDIR
    artifacts: list[ParsedArtifact] = []
    if pedagogy_dir.exists():
        for json_path in sorted(pedagogy_dir.glob(_ARTIFACT_JSON_GLOB)):
            parsed = read_artifact(json_path)
            if parsed is not None and parsed.items:
                artifacts.append(parsed)
    difficulty = (
        project.pedagogy.target_audience.value if project.pedagogy is not None else ""
    )
    return GenankiExporter().export_to_file(
        artifacts,
        deck_root=project.name,
        difficulty=difficulty,
        output_path=output_path,
    )


@dataclass(frozen=True)
class DocumentExportResult:
    """Résultat d'un export Markdown ou PDF.

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


def export_pedagogy_to_markdown(
    project: Project, *, output_dir: Path
) -> DocumentExportResult:
    """Agrège les supports rendus en documents Markdown (sujet / corrigé).

    Args:
        project: Projet.
        output_dir: Dossier de destination.

    Returns:
        ``DocumentExportResult`` (chemins des ``.md`` écrits).
    """
    artifacts = FsArtifactStore()
    paths: list[Path] = []
    for stem, markdown_text in _build_documents(project):
        path = output_dir / f"{stem}{_MD_EXT}"
        artifacts.write_text_atomic(path, markdown_text)
        paths.append(path)
    return DocumentExportResult(output_paths=tuple(paths))


def export_pedagogy_to_pdf(
    project: Project, *, output_dir: Path
) -> DocumentExportResult:
    """Agrège les supports rendus en documents PDF (sujet / corrigé).

    Args:
        project: Projet.
        output_dir: Dossier de destination.

    Returns:
        ``DocumentExportResult`` (chemins des ``.pdf`` écrits).

    Raises:
        ConfigError: ``EXPORT.NO_PDF_FONT`` si aucune police Unicode n'est résolue.
    """
    paths: list[Path] = []
    for stem, markdown_text in _build_documents(project):
        path = output_dir / f"{stem}{_PDF_EXT}"
        render_markdown_to_pdf(markdown_text, path)
        paths.append(path)
    return DocumentExportResult(output_paths=tuple(paths))


def _build_documents(project: Project) -> list[tuple[str, str]]:
    """Construit les documents agrégés (sujet/corrigé) par langue.

    Lit les Markdown rendus (`<support>.md` / `<support>.corrige.md`) dans l'ordre
    canonique des supports.

    Args:
        project: Projet.

    Returns:
        Liste de ``(nom_sans_extension, markdown_agrégé)``.
    """
    pedagogy_dir = project.workspace_folder / PEDAGOGY_WORKSPACE_SUBDIR
    documents: list[tuple[str, str]] = []
    for language in Language:
        subjects: list[str] = []
        corrections: list[str] = []
        for support in SupportGeneratorRegistry.canonical_order():
            subject_path = artifact_markdown_path(pedagogy_dir, support, language)
            if subject_path.exists():
                subjects.append(subject_path.read_text(encoding=_ENCODING_UTF8))
            correction_path = artifact_correction_markdown_path(
                pedagogy_dir, support, language
            )
            if correction_path.exists():
                corrections.append(
                    correction_path.read_text(encoding=_ENCODING_UTF8)
                )
        label = language_label(language)
        if subjects:
            documents.append(
                (
                    _SUBJECT_STEM.format(lang=language.value),
                    assemble_markdown(
                        _SUBJECT_TITLE.format(lang=label), tuple(subjects)
                    ),
                )
            )
        if corrections:
            documents.append(
                (
                    _CORRECTION_STEM.format(lang=language.value),
                    assemble_markdown(
                        _CORRECTION_TITLE.format(lang=label), tuple(corrections)
                    ),
                )
            )
    return documents
