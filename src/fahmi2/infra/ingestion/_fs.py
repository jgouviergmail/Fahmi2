"""Utilitaires de système de fichiers internes à la couche d'ingestion.

Regroupe les helpers fichier partagés par les ingesteurs (``MediaIngestor``,
``YoutubeIngestor``) pour éviter la duplication de la suppression best-effort
des artefacts intermédiaires.
"""

from __future__ import annotations

from pathlib import Path


def safe_delete(path: Path) -> None:
    """Supprime ``path`` s'il existe, sans lever en cas d'échec (best-effort).

    Utilisé pour nettoyer les fichiers intermédiaires (WAV extrait, audio
    YouTube téléchargé) : un échec de suppression ne doit jamais masquer le
    résultat de l'ingestion.

    Args:
        path: Fichier à supprimer.
    """
    if path.exists():
        try:
            path.unlink()
        except OSError:
            pass
