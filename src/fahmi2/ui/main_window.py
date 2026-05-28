"""``MainWindow`` — cockpit principal (sidebar projets + onglets de fonctionnalité).

Layout :

- Sidebar gauche : liste des projets (transverse à toutes les fonctionnalités).
- Centre : ``QTabWidget`` peuplé par un ``FeatureRegistry`` (Génération, Supports
  pédagogiques, …).
- Dock bas : ``LogsDock`` partagé.
- Menus : Fichier, Édition, Affichage, ?.

La sélection d'un projet dans la sidebar est **dispatchée** à chaque onglet
(``FeatureTab.on_project_selected``).
"""

from __future__ import annotations

from collections.abc import Callable
from importlib.metadata import PackageNotFoundError, version

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QMainWindow,
    QMessageBox,
    QSplitter,
    QTabWidget,
    QWidget,
)

from fahmi2.domain.ids import ProjectId
from fahmi2.ui.features.registry import FeatureRegistry
from fahmi2.ui.widgets.logs_dock import LogsDock
from fahmi2.ui.widgets.projects_sidebar import ProjectsSidebar

_WINDOW_TITLE = "Fahmi2"
#: Largeur initiale de la sidebar projets (px). Suffisamment large pour
#: accueillir des noms de projet de taille moyenne sans tronquer le
#: sous-libellé « Génération ... · Supports ... ». Reste redimensionnable
#: via le QSplitter (l'utilisateur peut élargir ou réduire à sa convenance).
_SIDEBAR_WIDTH_PX = 280
#: Largeur minimale absolue de la sidebar (empêche de la réduire à rien).
_SIDEBAR_MIN_WIDTH_PX = 220
_CENTRAL_WIDTH_PX = 920
_PACKAGE_NAME = "fahmi2"
_VERSION_UNKNOWN = "dev"
_ABOUT_TITLE = "À propos de Fahmi2"
_ABOUT_TEXT = (
    "<b>Fahmi2</b> — version {version}<br><br>"
    "Transforme un dossier de sources de cours en documents Markdown consolidés "
    "et en supports de révision (flashcards, QCM, examens blancs…)."
)


class MainWindow(QMainWindow):
    """Fenêtre principale (sidebar projets + onglets de fonctionnalité)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Construit la fenêtre (onglets ajoutés ensuite via ``set_feature_tabs``).

        Args:
            parent: Parent Qt optionnel.
        """
        super().__init__(parent)
        self.setWindowTitle(_WINDOW_TITLE)
        self.resize(1200, 800)

        self._feature_registry: FeatureRegistry | None = None

        self._projects_sidebar = ProjectsSidebar(self)
        self._projects_sidebar.set_on_project_selected(self._dispatch_project_selected)
        # Empêche la sidebar de devenir trop étroite (les noms de projets
        # seraient tronqués). Reste élargissable au-delà via le splitter.
        self._projects_sidebar.setMinimumWidth(_SIDEBAR_MIN_WIDTH_PX)

        self._tabs = QTabWidget(self)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.addWidget(self._projects_sidebar)
        splitter.addWidget(self._tabs)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([_SIDEBAR_WIDTH_PX, _CENTRAL_WIDTH_PX])
        self.setCentralWidget(splitter)

        self._logs_dock = LogsDock(self)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self._logs_dock)

        self._build_menus()

    def set_feature_tabs(self, registry: FeatureRegistry) -> None:
        """Peuple la zone centrale avec les onglets de fonctionnalité.

        Args:
            registry: Registre ordonné des onglets à afficher.
        """
        self._feature_registry = registry
        self._tabs.clear()
        for tab in registry.ordered():
            self._tabs.addTab(tab.widget, tab.title)

    @property
    def projects_sidebar(self) -> ProjectsSidebar:
        """Accès à la sidebar projets (lecture seule).

        Returns:
            La sidebar.
        """
        return self._projects_sidebar

    @property
    def logs_dock(self) -> LogsDock:
        """Accès au dock logs partagé.

        Returns:
            Le dock.
        """
        return self._logs_dock

    def _dispatch_project_selected(self, project_id: ProjectId) -> None:
        """Notifie chaque onglet de la sélection d'un projet.

        Args:
            project_id: Projet sélectionné dans la sidebar.
        """
        if self._feature_registry is None:
            return
        for tab in self._feature_registry.ordered():
            tab.on_project_selected(project_id)

    def notify_project_deleted(self, project_id: ProjectId) -> None:
        """Notifie **tous** les onglets de la suppression d'un projet.

        Chaque onglet réinitialise son état s'il affichait ce projet, évitant
        toute référence obsolète (et toute résurrection involontaire en base).

        Args:
            project_id: Projet supprimé.
        """
        if self._feature_registry is None:
            return
        for tab in self._feature_registry.ordered():
            tab.on_project_deleted(project_id)

    def set_on_open_settings(self, callback: Callable[[], None]) -> None:
        """Définit le callback du menu Édition > Paramètres globaux.

        Args:
            callback: Fonction sans argument.
        """
        self._open_settings_action.triggered.connect(callback)

    def set_on_open_prompts_editor(self, callback: Callable[[], None]) -> None:
        """Définit le callback du menu Édition > Modifier les prompts.

        Args:
            callback: Fonction sans argument.
        """
        self._open_prompts_action.triggered.connect(callback)

    def set_on_new_project(self, callback: Callable[[], None]) -> None:
        """Définit le callback du menu Fichier > Nouveau projet.

        Args:
            callback: Fonction sans argument.
        """
        self._new_project_action.triggered.connect(callback)

    def _build_menus(self) -> None:
        """Construit les menus principaux."""
        menubar = self.menuBar()
        assert menubar is not None

        file_menu = menubar.addMenu("Fichier")
        assert file_menu is not None
        self._new_project_action = QAction("Nouveau projet…", self)
        file_menu.addAction(self._new_project_action)
        file_menu.addSeparator()
        quit_action = QAction("Quitter", self)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        edit_menu = menubar.addMenu("Édition")
        assert edit_menu is not None
        self._open_settings_action = QAction("Paramètres globaux…", self)
        edit_menu.addAction(self._open_settings_action)
        self._open_prompts_action = QAction("Modifier les prompts…", self)
        edit_menu.addAction(self._open_prompts_action)

        help_menu = menubar.addMenu("Aide")
        assert help_menu is not None
        about_action = QAction("À propos", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _show_about(self) -> None:
        """Affiche la boîte de dialogue « À propos » (nom + version)."""
        try:
            app_version = version(_PACKAGE_NAME)
        except PackageNotFoundError:
            app_version = _VERSION_UNKNOWN
        QMessageBox.about(self, _ABOUT_TITLE, _ABOUT_TEXT.format(version=app_version))
