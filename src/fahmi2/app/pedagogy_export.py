"""Services d'export des supports pédagogiques (Anki, Markdown, PDF, HTML).

Scanne le dossier ``pedagogy/`` d'un projet et produit des livrables :

- **Anki `.apkg`** : désérialise les artefacts exportables (flashcards, cloze, QCM)
  et délègue à l'adapter ``GenankiExporter``.
- **Markdown / PDF / HTML** : réutilise le Markdown **déjà rendu** (`<support>.md` /
  `<support>.corrige.md`) et produit **un fichier par support** (et par corrigé),
  via ``app.document_export.write_documents``.
"""

from __future__ import annotations

from pathlib import Path

from fahmi2.app.document_export import (
    DocumentExportResult,
    ExportDocument,
    write_documents,
)
from fahmi2.domain.enums import ExportFormat, Language, SupportType
from fahmi2.domain.pedagogy import PEDAGOGY_WORKSPACE_SUBDIR
from fahmi2.domain.project import Project
from fahmi2.infra.anki.genanki_exporter import AnkiExportResult, GenankiExporter
from fahmi2.pedagogy.artifact_reader import ParsedArtifact, read_artifact
from fahmi2.pedagogy.artifact_writer import (
    artifact_correction_markdown_path,
    artifact_markdown_path,
)

#: Ordre **pédagogique** des supports dans les fichiers exportés : d'abord les
#: supports d'apprentissage du plus général au plus précis (fiche → points clés →
#: flashcards), puis les exercices du plus précis au plus général (cloze →
#: vrai/faux → QCM → questions ouvertes → examen blanc). Donne un ordre
#: déterministe aux fichiers produits. Distinct de l'ordre canonique du registre.
_EXPORT_SUPPORT_ORDER: tuple[SupportType, ...] = (
    SupportType.REVISION_SHEET,
    SupportType.KEY_POINTS,
    SupportType.FLASHCARDS_CONCEPTS,
    SupportType.CLOZE,
    SupportType.TRUE_FALSE,
    SupportType.QCM,
    SupportType.OPEN_QUESTIONS,
    SupportType.MOCK_EXAM,
)

#: Glob des artefacts JSON : ``<support>/<lang>/<support>.json`` (profondeur 3).
#: Exclut ``pedagogy/manifest.json`` (profondeur 1).
_ARTIFACT_JSON_GLOB = "*/*/*.json"

_ENCODING_UTF8 = "utf-8"
#: Suffixe de stem d'un corrigé (cohérent avec ``<support>.corrige.md`` sur disque).
_CORRECTION_SUFFIX = ".corrige"


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


def collect_pedagogy_documents(project: Project) -> list[ExportDocument]:
    """Collecte un document par support et par corrigé présents (ordre déterministe).

    Lit les Markdown rendus (`<support>.md` / `<support>.corrige.md`) dans l'ordre
    **pédagogique d'export** (``_EXPORT_SUPPORT_ORDER``). Tous en portrait (les
    supports n'ont pas de tableaux larges).

    Args:
        project: Projet.

    Returns:
        Liste d'``ExportDocument`` : ``<support>.<lang>`` (sujet) et
        ``<support>.<lang>.corrige`` (corrigé) pour chaque fichier présent.
    """
    pedagogy_dir = project.workspace_folder / PEDAGOGY_WORKSPACE_SUBDIR
    documents: list[ExportDocument] = []
    for language in Language:
        for support in _EXPORT_SUPPORT_ORDER:
            subject_path = artifact_markdown_path(pedagogy_dir, support, language)
            if subject_path.exists():
                documents.append(
                    ExportDocument(
                        stem=f"{support.value}.{language.value}",
                        markdown=subject_path.read_text(encoding=_ENCODING_UTF8),
                        language=language,
                    )
                )
            correction_path = artifact_correction_markdown_path(
                pedagogy_dir, support, language
            )
            if correction_path.exists():
                documents.append(
                    ExportDocument(
                        stem=f"{support.value}.{language.value}{_CORRECTION_SUFFIX}",
                        markdown=correction_path.read_text(encoding=_ENCODING_UTF8),
                        language=language,
                    )
                )
    return documents


def export_pedagogy_documents(
    project: Project, *, output_dir: Path, fmt: ExportFormat
) -> DocumentExportResult:
    """Exporte les supports rendus, **un fichier par support / corrigé**.

    Args:
        project: Projet.
        output_dir: Dossier de destination.
        fmt: Format documentaire (``MARKDOWN`` / ``PDF`` / ``HTML`` / ``DOCX``).

    Returns:
        ``DocumentExportResult``.

    Raises:
        ValueError: Si ``fmt`` n'est pas documentaire.
        ConfigError: ``EXPORT.NO_PDF_FONT`` en PDF sans police Unicode.
    """
    return write_documents(
        collect_pedagogy_documents(project), output_dir=output_dir, fmt=fmt
    )
