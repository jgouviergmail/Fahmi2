"""Service d'export des supports pédagogiques vers Anki (.apkg).

Scanne le dossier ``pedagogy/`` d'un projet, désérialise les artefacts
exportables (flashcards, cloze, QCM) et délègue à l'adapter ``GenankiExporter``.
"""

from __future__ import annotations

from pathlib import Path

from fahmi2.domain.pedagogy import PEDAGOGY_WORKSPACE_SUBDIR
from fahmi2.domain.project import Project
from fahmi2.infra.anki.genanki_exporter import AnkiExportResult, GenankiExporter
from fahmi2.pedagogy.artifact_reader import ParsedArtifact, read_artifact

#: Glob des artefacts JSON : ``<support>/<lang>/<support>.json`` (profondeur 3).
#: Exclut ``pedagogy/manifest.json`` (profondeur 1).
_ARTIFACT_JSON_GLOB = "*/*/*.json"


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
