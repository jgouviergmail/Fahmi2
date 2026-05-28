"""Sous-module ``theme`` — feuille de style globale + bascule clair/sombre.

Expose :

- ``ThemeMode`` : mode d'apparence (système, clair, sombre).
- ``load_theme_qss`` : retourne la chaîne QSS **claire** (back-compat).
- ``load_theme_qss_for`` : retourne le QSS d'un mode résolu.
- ``resolve_mode`` : résout ``SYSTEM`` en mode effectif via ``QStyleHints``.
- ``apply_theme`` : applique le QSS à un ``QApplication`` + met à jour la
  palette active + ré-installe les ombres des cartes existantes.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from fahmi2.ui.theme._tokens import (
    ThemeMode,
    palette_for,
    set_current_palette,
)

_LIGHT_QSS_FILENAME = "light_fluent.qss"
_DARK_QSS_FILENAME = "dark_fluent.qss"


def _qss_path(filename: str) -> Path:
    """Construit le chemin absolu d'un fichier QSS embarqué dans ce sous-module.

    Args:
        filename: Nom du fichier (``light_fluent.qss`` ou ``dark_fluent.qss``).

    Returns:
        Le ``Path`` absolu.
    """
    return Path(__file__).with_name(filename)


def load_theme_qss() -> str:
    """Charge la feuille de style **claire** (back-compat historique).

    Returns:
        Le contenu QSS clair, prêt à être passé à ``QApplication.setStyleSheet``.
    """
    return _qss_path(_LIGHT_QSS_FILENAME).read_text(encoding="utf-8")


def load_theme_qss_for(mode: ThemeMode) -> str:
    """Charge le QSS correspondant à un mode résolu (clair ou sombre).

    Args:
        mode: Mode résolu (``LIGHT`` ou ``DARK`` ; ``SYSTEM`` doit avoir été
            résolu en amont par ``resolve_mode``).

    Returns:
        Le contenu QSS.

    Raises:
        ValueError: Si ``mode`` est ``SYSTEM`` (non résolu) ou inconnu.
    """
    if mode is ThemeMode.LIGHT:
        return _qss_path(_LIGHT_QSS_FILENAME).read_text(encoding="utf-8")
    if mode is ThemeMode.DARK:
        return _qss_path(_DARK_QSS_FILENAME).read_text(encoding="utf-8")
    raise ValueError(f"load_theme_qss_for: mode non résolu : {mode!r}")


def resolve_mode(
    mode: ThemeMode, app: QApplication | None = None
) -> ThemeMode:
    """Résout ``SYSTEM`` en mode effectif via ``QStyleHints.colorScheme``.

    Args:
        mode: Mode demandé.
        app: ``QApplication`` à interroger (défaut : instance courante).

    Returns:
        ``LIGHT`` ou ``DARK`` (jamais ``SYSTEM``). En l'absence d'info système
        exploitable, repli sur ``LIGHT``.
    """
    if mode is not ThemeMode.SYSTEM:
        return mode
    inst = app or QApplication.instance()
    # ``QCoreApplication.instance()`` peut retourner un ``QCoreApplication``
    # sans ``styleHints`` (cas hors-GUI) ; on n'utilise l'API GUI que si on
    # a bien une ``QApplication`` (ou sous-classe).
    if not isinstance(inst, QApplication):
        return ThemeMode.LIGHT
    if inst.styleHints().colorScheme() is Qt.ColorScheme.Dark:
        return ThemeMode.DARK
    return ThemeMode.LIGHT


def apply_theme(
    app: QApplication, mode: ThemeMode = ThemeMode.SYSTEM
) -> None:
    """Applique le thème (clair, sombre, ou suivi du système) à l'``QApplication``.

    Met à jour la palette active (lue par ``install_shadow`` pour la couleur
    d'ombre adaptée), applique le QSS — ce qui déclenche automatiquement le
    re-polish de tous les widgets — et ré-installe les ombres des cartes
    existantes (l'ombre étant portée par un effet Python, pas par le QSS).

    Args:
        app: Application Qt cible.
        mode: Mode demandé (défaut : ``SYSTEM`` — préserve la signature
            historique ``apply_theme(app)``).
    """
    resolved = resolve_mode(mode, app=app)
    set_current_palette(palette_for(resolved))
    app.setStyleSheet(load_theme_qss_for(resolved))
    # Ré-installation des ombres des cartes après changement de thème.
    # Import local pour éviter toute dépendance circulaire à l'initialisation
    # du module ``theme`` (``_components`` importe ``theme._tokens``).
    from fahmi2.ui._components import reapply_card_shadows  # noqa: PLC0415

    reapply_card_shadows(app)


__all__ = [
    "ThemeMode",
    "apply_theme",
    "load_theme_qss",
    "load_theme_qss_for",
    "resolve_mode",
]
