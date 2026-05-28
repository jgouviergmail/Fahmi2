"""Contrôleur du thème UI (apparence claire / sombre / système).

Orchestre le cycle de vie de la préférence d'apparence :

- lit la préférence sur disque au démarrage (parsing *lenient* — repli sur les
  défauts si le fichier est absent ou corrompu) ;
- applique le thème correspondant à l'``QApplication`` ;
- écoute les changements du thème système (``QStyleHints.colorSchemeChanged``)
  pour suivre l'OS quand l'utilisateur est en mode ``SYSTEM`` ;
- expose :py:meth:`ThemeController.set_mode` pour les écrans de réglages
  (application immédiate + persistance best-effort).

Dépendance unique vers l'UI : le module ``fahmi2.ui.theme`` (qui n'importe
ni le domaine ni les services). C'est un service applicatif (`app/`) pur
côté lecture/écriture de préférence + orchestration.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from fahmi2.app.ui_preferences import (
    UiPreferences,
    read_ui_preferences,
    write_ui_preferences,
)
from fahmi2.ui.theme import ThemeMode, apply_theme


class ThemeController:
    """Pilote l'apparence de l'application.

    Le contrôleur est instancié une fois au démarrage de l'application (cf.
    ``fahmi2.ui.app_main``). Les écrans de réglages reçoivent l'instance par
    injection et appellent :py:meth:`set_mode` pour changer l'apparence.
    """

    def __init__(self, app: QApplication, prefs_path: Path) -> None:
        """Initialise le contrôleur, applique le thème et installe le listener.

        Args:
            app: ``QApplication`` cible.
            prefs_path: Chemin du fichier ``ui_prefs.json``.
        """
        self._app = app
        self._prefs_path = prefs_path
        self._mode = read_ui_preferences(prefs_path).theme_mode
        apply_theme(app, self._mode)
        style_hints = app.styleHints()
        if style_hints is not None:
            style_hints.colorSchemeChanged.connect(
                self._on_system_color_scheme_changed
            )

    @property
    def mode(self) -> ThemeMode:
        """Mode d'apparence courant (tel que stocké en préférence).

        Returns:
            ``ThemeMode.SYSTEM``, ``ThemeMode.LIGHT`` ou ``ThemeMode.DARK``.
        """
        return self._mode

    def set_mode(self, mode: ThemeMode) -> None:
        """Change le mode, l'applique immédiatement et persiste la préférence.

        Idempotent : si ``mode`` est déjà actif, ne fait rien (évite un
        re-polish global inutile).

        Args:
            mode: Nouveau mode demandé.
        """
        if mode is self._mode:
            return
        self._mode = mode
        apply_theme(self._app, mode)
        # Persistance best-effort : une erreur disque ne doit pas casser
        # l'expérience utilisateur (le thème reste appliqué pour la session).
        try:
            write_ui_preferences(self._prefs_path, UiPreferences(theme_mode=mode))
        except OSError:
            pass

    def _on_system_color_scheme_changed(self, _scheme: Qt.ColorScheme) -> None:
        """Re-applique le thème si l'utilisateur est en mode ``SYSTEM``.

        ``apply_theme`` ré-interroge ``QStyleHints.colorScheme()`` à chaque
        appel : on n'a donc pas besoin de regarder ``_scheme`` ici.

        Args:
            _scheme: Nouveau ``Qt.ColorScheme`` (paramètre du signal Qt).
        """
        if self._mode is ThemeMode.SYSTEM:
            apply_theme(self._app, ThemeMode.SYSTEM)


__all__ = ["ThemeController"]
