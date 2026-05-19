"""Widget ``ProjectsSidebar`` — liste latérale des projets.

Expose un menu contextuel (clic droit) avec deux actions :

- **Modifier…** : déclenche le callback d'édition pour le projet ciblé.
- **Supprimer…** : déclenche le callback de suppression pour le projet ciblé.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QAction, QContextMenuEvent
from PySide6.QtWidgets import QListWidget, QListWidgetItem, QMenu, QWidget

from fahmi2.domain.ids import ProjectId
from fahmi2.domain.project import Project

_PROJECT_ID_ROLE = Qt.ItemDataRole.UserRole


class ProjectsSidebar(QListWidget):
    """Liste latérale des projets de l'utilisateur."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Construit la sidebar.

        Args:
            parent: Parent Qt optionnel.
        """
        super().__init__(parent)
        self._on_select: Callable[[ProjectId], None] | None = None
        self._on_edit: Callable[[ProjectId], None] | None = None
        self._on_delete: Callable[[ProjectId], None] | None = None
        self.currentItemChanged.connect(self._on_selection_changed)

    def set_on_project_selected(
        self, callback: Callable[[ProjectId], None]
    ) -> None:
        """Définit le callback à appeler quand la sélection change.

        Args:
            callback: Reçoit le ``ProjectId`` sélectionné.
        """
        self._on_select = callback

    def set_on_edit_requested(
        self, callback: Callable[[ProjectId], None]
    ) -> None:
        """Définit le callback appelé pour l'action « Modifier… ».

        Args:
            callback: Reçoit le ``ProjectId`` du projet à modifier.
        """
        self._on_edit = callback

    def set_on_delete_requested(
        self, callback: Callable[[ProjectId], None]
    ) -> None:
        """Définit le callback appelé pour l'action « Supprimer… ».

        Args:
            callback: Reçoit le ``ProjectId`` du projet à supprimer.
        """
        self._on_delete = callback

    def set_projects(self, projects: list[Project]) -> None:
        """Remplit la sidebar avec une liste de projets.

        Args:
            projects: Projets à afficher.
        """
        self.clear()
        for project in projects:
            item = QListWidgetItem(project.settings.name)
            item.setData(_PROJECT_ID_ROLE, project.id.value)
            self.addItem(item)

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:  # noqa: N802
        """Affiche le menu contextuel (Modifier / Supprimer) sur clic droit.

        ``QListWidget.itemAt`` attend des coordonnées du viewport interne, pas
        du widget complet : on convertit donc explicitement la position globale
        du clic avant de chercher l'item ciblé, pour rester insensible au
        padding éventuel posé par la feuille de style.

        Args:
            event: Événement Qt (sa position globale est utilisée pour
                identifier l'item visé).
        """
        viewport_pos: QPoint = self.viewport().mapFromGlobal(event.globalPos())
        item = self.itemAt(viewport_pos)
        if item is None:
            return
        value = item.data(_PROJECT_ID_ROLE)
        if not isinstance(value, str):
            return
        project_id = ProjectId(value=value)

        menu = QMenu(self)
        edit_action = QAction("Modifier…", menu)
        delete_action = QAction("Supprimer…", menu)
        menu.addAction(edit_action)
        menu.addSeparator()
        menu.addAction(delete_action)

        edit_action.setEnabled(self._on_edit is not None)
        delete_action.setEnabled(self._on_delete is not None)

        chosen = menu.exec(event.globalPos())
        if chosen is edit_action and self._on_edit is not None:
            self._on_edit(project_id)
        elif chosen is delete_action and self._on_delete is not None:
            self._on_delete(project_id)

    def _on_selection_changed(
        self, current: QListWidgetItem | None, previous: QListWidgetItem | None
    ) -> None:
        del previous
        if current is None or self._on_select is None:
            return
        value = current.data(_PROJECT_ID_ROLE)
        if isinstance(value, str):
            self._on_select(ProjectId(value=value))
