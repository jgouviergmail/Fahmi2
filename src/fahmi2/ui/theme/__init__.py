"""Sous-module ``theme`` — feuille de style globale de l'application.

Expose :

- ``load_theme_qss`` : retourne la chaîne QSS à appliquer sur le
  ``QApplication``.
- ``apply_theme`` : helper pour appliquer la feuille de style en une ligne.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QApplication

_QSS_FILENAME = "light_fluent.qss"


def load_theme_qss() -> str:
    """Charge la feuille de style ``light_fluent.qss``.

    Returns:
        Le contenu QSS prêt à être passé à ``QApplication.setStyleSheet``.
    """
    qss_path = Path(__file__).with_name(_QSS_FILENAME)
    return qss_path.read_text(encoding="utf-8")


def apply_theme(app: QApplication) -> None:
    """Applique la feuille de style à un ``QApplication``.

    Args:
        app: Application Qt cible.
    """
    app.setStyleSheet(load_theme_qss())


__all__ = ["apply_theme", "load_theme_qss"]
