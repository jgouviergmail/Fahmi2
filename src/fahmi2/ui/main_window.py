"""``MainWindow`` — cockpit principal de l'application (layout dense).

Layout :

- Sidebar gauche : liste des projets.
- Centre : ``ProjectHeaderBar`` (titre + actions) + ``StatsStripWidget``
  + ``RunMatrixView``.
- Dock bas : ``LogsDock`` (filtrable).
- Menus : Fichier, Édition, Affichage, ?.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QMainWindow,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from fahmi2.ui.widgets.logs_dock import LogsDock
from fahmi2.ui.widgets.project_header_bar import ProjectHeaderBar
from fahmi2.ui.widgets.projects_sidebar import ProjectsSidebar
from fahmi2.ui.widgets.run_matrix_view import RunMatrixView
from fahmi2.ui.widgets.stats_strip import StatsStripWidget

_WINDOW_TITLE = "Fahmi2"


class MainWindow(QMainWindow):
    """Fenêtre principale (cockpit dense)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Construit la fenêtre.

        Args:
            parent: Parent Qt optionnel.
        """
        super().__init__(parent)
        self.setWindowTitle(_WINDOW_TITLE)
        self.resize(1200, 800)

        # Sidebar projets
        self._projects_sidebar = ProjectsSidebar(self)

        # Zone centrale
        central = QWidget(self)
        central_layout = QVBoxLayout(central)
        central_layout.setContentsMargins(0, 0, 0, 0)

        self._header_bar = ProjectHeaderBar(self)
        self._stats_strip = StatsStripWidget(self)
        self._run_matrix = RunMatrixView(parent=self)
        central_layout.addWidget(self._header_bar)
        central_layout.addWidget(self._stats_strip)
        central_layout.addWidget(self._run_matrix, stretch=1)

        # Splitter horizontal
        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.addWidget(self._projects_sidebar)
        splitter.addWidget(central)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([220, 980])
        self.setCentralWidget(splitter)

        # Dock logs
        self._logs_dock = LogsDock(self)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self._logs_dock)

        self._build_menus()

    @property
    def projects_sidebar(self) -> ProjectsSidebar:
        """Accès à la sidebar projets (lecture seule).

        Returns:
            La sidebar.
        """
        return self._projects_sidebar

    @property
    def header_bar(self) -> ProjectHeaderBar:
        """Accès à la barre titre du Run.

        Returns:
            La header bar.
        """
        return self._header_bar

    @property
    def stats_strip(self) -> StatsStripWidget:
        """Accès au widget stats.

        Returns:
            Le widget.
        """
        return self._stats_strip

    @property
    def run_matrix(self) -> RunMatrixView:
        """Accès à la matrice vidéos × phases.

        Returns:
            La vue matrice.
        """
        return self._run_matrix

    @property
    def logs_dock(self) -> LogsDock:
        """Accès au dock logs.

        Returns:
            Le dock.
        """
        return self._logs_dock

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

        help_menu = menubar.addMenu("?")
        assert help_menu is not None
        about_action = QAction("À propos", self)
        help_menu.addAction(about_action)
