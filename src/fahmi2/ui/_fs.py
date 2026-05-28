"""Helpers système de fichiers pour l'UI (suppression de dossiers de sortie).

Mutualisé entre les contrôleurs Génération et Pédagogie pour la
« Réinitialisation » : suppression récursive idempotente d'un dossier de
livrables, avec isolation et journalisation des erreurs d'I/O.
"""

from __future__ import annotations

import shutil
from datetime import UTC, datetime
from pathlib import Path

from PySide6.QtCore import QCoreApplication

from fahmi2.core.errors.severity import Severity
from fahmi2.core.logging.event import LogEvent
from fahmi2.ui.widgets.logs_dock import LogsDock

_RESET_DIR_FAILED_CODE = "RESET_DIR_FAILED"


def remove_feature_dir(logs_dock: LogsDock, path: Path, *, label: str) -> None:
    """Supprime récursivement un dossier de fonctionnalité (idempotent).

    Ne fait rien si le dossier n'existe pas. Toute erreur d'I/O est isolée et
    journalisée en avertissement (sans interrompre la réinitialisation du cockpit).

    Args:
        logs_dock: Dock de logs pour journaliser un éventuel échec.
        path: Dossier à supprimer.
        label: Libellé de la fonctionnalité (messages de log).
    """
    if not path.exists():
        return
    try:
        shutil.rmtree(path)
    except OSError as exc:
        logs_dock.append_event(
            LogEvent(
                timestamp=datetime.now(tz=UTC),
                severity=Severity.WARNING,
                code=_RESET_DIR_FAILED_CODE,
                message=QCoreApplication.translate(
                    "FsHelpers",
                    "Échec de la suppression du dossier {label} : {path} ({exc})",
                ).format(label=label, path=path, exc=exc),
            )
        )
