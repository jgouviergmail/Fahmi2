"""Ouverture d'un dossier dans l'explorateur de fichiers natif.

Helper UI partagé par les contrôleurs (Génération, Supports pédagogiques) pour
révéler un dossier de sortie. Isolé dans son module pour éviter qu'un contrôleur
importe un symbole privé d'un autre.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices


def open_in_file_explorer(path: Path) -> None:
    """Ouvre ``path`` dans l'explorateur de fichiers natif.

    Sur Windows, utilise ``explorer.exe`` qui est non bloquant. Sur les autres
    plateformes, fallback sur ``QDesktopServices.openUrl(file://)``.

    Args:
        path: Chemin du dossier à ouvrir.
    """
    if sys.platform == "win32":
        explorer = shutil.which("explorer.exe") or "explorer.exe"
        subprocess.Popen(  # noqa: S603
            [explorer, str(path)], close_fds=True
        )
        return
    QDesktopServices.openUrl(  # type: ignore[unreachable]
        QUrl.fromLocalFile(str(path))
    )
