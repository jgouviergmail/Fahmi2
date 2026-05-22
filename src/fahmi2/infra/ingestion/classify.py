"""Classification d'une source fichier par extension.

Centralise les ensembles d'extensions reconnues (réexposés par
``supported_file_extensions`` pour le scan du dossier d'entrée). ``YOUTUBE``
n'a pas de fichier (saisi en URL), donc hors de cette classification.
"""

from __future__ import annotations

from pathlib import Path

from fahmi2.domain.enums import SourceKind

#: Extensions vidéo reconnues (minuscules, point initial inclus).
VIDEO_EXTENSIONS: frozenset[str] = frozenset(
    {".mp4", ".m4v", ".mkv", ".mov", ".webm"}
)
#: Extensions audio reconnues (minuscules, point initial inclus).
AUDIO_EXTENSIONS: frozenset[str] = frozenset(
    {".wav", ".mp3", ".m4a", ".flac", ".ogg", ".opus", ".aac"}
)
#: Extensions document reconnues (minuscules, point initial inclus).
DOCUMENT_EXTENSIONS: frozenset[str] = frozenset({".pdf", ".docx", ".md", ".txt"})

_EXTENSION_TO_KIND: dict[str, SourceKind] = {
    **{ext: SourceKind.VIDEO for ext in VIDEO_EXTENSIONS},
    **{ext: SourceKind.AUDIO for ext in AUDIO_EXTENSIONS},
    **{ext: SourceKind.DOCUMENT for ext in DOCUMENT_EXTENSIONS},
}


def classify_file(path: Path) -> SourceKind | None:
    """Détermine le type d'une source fichier d'après son extension.

    Args:
        path: Chemin du fichier.

    Returns:
        Le ``SourceKind`` correspondant, ou ``None`` si l'extension n'est pas
        prise en charge.
    """
    return _EXTENSION_TO_KIND.get(path.suffix.lower())


def supported_file_extensions() -> frozenset[str]:
    """Retourne l'ensemble immuable des extensions fichier reconnues.

    Returns:
        Les extensions (minuscules, point initial inclus) acceptées par le scan.
    """
    return frozenset(_EXTENSION_TO_KIND)
