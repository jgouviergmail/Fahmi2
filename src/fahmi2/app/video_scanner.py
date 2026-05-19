"""Scanner de vidéos dans un dossier d'entrée.

Identifie les fichiers vidéo supportés (extensions configurées) et produit
les ``VideoExecution`` initiaux pour un ``Run``.
"""

from __future__ import annotations

from pathlib import Path

from fahmi2.core.errors.exceptions import ConfigError, StorageError
from fahmi2.core.errors.severity import Severity
from fahmi2.domain.ids import VideoId
from fahmi2.domain.video import VideoExecution

_SUPPORTED_EXTENSIONS: frozenset[str] = frozenset(
    {".mp4", ".m4v", ".mkv", ".mov", ".webm"}
)


def supported_extensions() -> frozenset[str]:
    """Retourne le set des extensions vidéo supportées.

    Returns:
        Set immuable d'extensions (en minuscules, avec ``.`` initial).
    """
    return _SUPPORTED_EXTENSIONS


def scan_input_folder(input_folder: Path) -> list[VideoExecution]:
    """Liste les vidéos supportées dans ``input_folder``.

    Args:
        input_folder: Dossier à scanner.

    Returns:
        Liste des ``VideoExecution`` initiaux (status PENDING implicite),
        triés par nom de fichier.

    Raises:
        StorageError: Si ``input_folder`` est inaccessible.
        ConfigError: Si aucun fichier vidéo supporté n'est trouvé.
    """
    if not input_folder.exists() or not input_folder.is_dir():
        raise StorageError(
            code="STORAGE.READ_DENIED",
            user_message=(
                f"Le dossier d'entrée est introuvable ou inaccessible : {input_folder}"
            ),
            severity=Severity.ERROR,
            technical_details={"input_folder": str(input_folder)},
        )

    candidates = sorted(
        (
            p
            for p in input_folder.iterdir()
            if p.is_file() and p.suffix.lower() in _SUPPORTED_EXTENSIONS
        ),
        key=lambda p: p.name.casefold(),
    )

    if not candidates:
        raise ConfigError(
            code="CONFIG.INPUT_FOLDER_EMPTY",
            user_message=(
                "Le dossier d'entrée ne contient aucune vidéo prise en charge "
                f"({', '.join(sorted(_SUPPORTED_EXTENSIONS))})."
            ),
            severity=Severity.ERROR,
            technical_details={
                "input_folder": str(input_folder),
                "supported": sorted(_SUPPORTED_EXTENSIONS),
            },
        )

    return [VideoExecution(video_id=VideoId.new(), source_path=p) for p in candidates]
