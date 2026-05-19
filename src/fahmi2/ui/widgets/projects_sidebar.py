"""Widget ``ProjectsSidebar`` — liste latérale des projets."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QListWidget, QListWidgetItem, QWidget

from fahmi2.domain.ids import ProjectId
from fahmi2.domain.project import Project

_PROJECT_ID_ROLE = Qt.ItemDataRole.UserRole


class ProjectsSidebar(QListWidget):
    """Liste latérale des projets du utilisateur."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Construit la sidebar.

        Args:
            parent: Parent Qt optionnel.
        """
        super().__init__(parent)
        self._on_select: Callable[[ProjectId], None] | None = None
        self.currentItemChanged.connect(self._on_selection_changed)

    def set_on_project_selected(
        self, callback: Callable[[ProjectId], None]
    ) -> None:
        """Définit le callback à appeler quand la sélection change.

        Args:
            callback: Reçoit le ``ProjectId`` sélectionné.
        """
        self._on_select = callback

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

    def _on_selection_changed(
        self, current: QListWidgetItem | None, previous: QListWidgetItem | None
    ) -> None:
        del previous
        if current is None or self._on_select is None:
            return
        value = current.data(_PROJECT_ID_ROLE)
        if isinstance(value, str):
            self._on_select(ProjectId(value=value))
