"""Contrôleur de la langue d'interface (i18n).

Pendant strict de :class:`~fahmi2.app.theme_controller.ThemeController` :

- lit la préférence ``language`` sur disque au démarrage (parsing *lenient*) ;
- installe le ``QTranslator`` correspondant sur l'``QApplication`` ;
- expose :py:meth:`LanguageController.set_language` pour les écrans de
  réglages (persistance immédiate ; **le changement est appliqué au prochain
  démarrage** — Qt ne propage pas ``LanguageChange`` aux chaînes déjà rendues
  via ``self.tr()`` au moment de la construction des widgets, et reconstruire
  tout l'arbre serait fragile vu la complexité de l'UI).

Dépendance unique vers l'UI : le module ``fahmi2.i18n`` (qui n'importe ni le
domaine ni les services). C'est un service applicatif (`app/`) pur côté
lecture/écriture de préférence + orchestration.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QApplication

from fahmi2.app.ui_preferences import (
    UiPreferences,
    read_ui_preferences,
    write_ui_preferences,
)
from fahmi2.i18n import AppLanguage, bundled_translations_dir, install_translator


class LanguageController:
    """Pilote la langue d'interface de l'application.

    Le contrôleur est instancié une fois au démarrage (cf.
    ``fahmi2.ui.app_main``). Les écrans de réglages reçoivent l'instance par
    injection et appellent :py:meth:`set_language` pour changer la préférence.
    """

    def __init__(self, app: QApplication, prefs_path: Path) -> None:
        """Initialise le contrôleur, installe le traducteur et charge la préférence.

        Args:
            app: ``QApplication`` cible.
            prefs_path: Chemin du fichier ``ui_prefs.json``.
        """
        self._app = app
        self._prefs_path = prefs_path
        self._language = read_ui_preferences(prefs_path).language
        install_translator(app, self._language, bundled_translations_dir())

    @property
    def language(self) -> AppLanguage:
        """Langue courante (telle que stockée en préférence).

        Returns:
            La langue d'interface active.
        """
        return self._language

    def set_language(self, language: AppLanguage) -> bool:
        """Change la langue persistée. Retourne ``True`` si un changement a eu lieu.

        Idempotent : si ``language`` est déjà active, retourne ``False`` sans
        rien faire.

        L'appelant (typiquement le dialogue des réglages) doit informer
        l'utilisateur qu'un redémarrage est nécessaire pour appliquer le
        changement à l'ensemble de l'UI.

        Args:
            language: Nouvelle langue demandée.

        Returns:
            ``True`` si la langue a changé et a été persistée, ``False`` si
            elle était déjà active.
        """
        if language is self._language:
            return False
        # Lit l'état complet pour préserver les autres préférences (apparence)
        # — on ne réécrit pas un dataclass partiel.
        current = read_ui_preferences(self._prefs_path)
        try:
            write_ui_preferences(
                self._prefs_path,
                UiPreferences(theme_mode=current.theme_mode, language=language),
            )
        except OSError:
            # Best-effort : une erreur disque ne doit pas crasher l'UI ; on
            # n'enregistre pas le changement en mémoire pour rester cohérent.
            return False
        self._language = language
        return True


__all__ = ["LanguageController"]
