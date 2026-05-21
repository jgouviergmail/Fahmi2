"""Widget ``ProjectsSidebar`` — liste latérale des projets.

Chaque entrée préfixe le nom du projet par deux icônes de statut — génération puis
pédagogie — sous la forme ``G ✓ / P ▶  Nom`` (statut du dernier run de chaque
fonctionnalité). Expose un menu contextuel (clic droit) avec deux actions :

- **Modifier…** : déclenche le callback d'édition pour le projet ciblé.
- **Supprimer…** : déclenche le callback de suppression pour le projet ciblé.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QAction, QContextMenuEvent
from PySide6.QtWidgets import QListWidget, QListWidgetItem, QMenu, QWidget

from fahmi2.domain.enums import RunStatus
from fahmi2.domain.ids import ProjectId
from fahmi2.domain.project import Project
from fahmi2.ui.status_labels import run_status_icon, run_status_label

_PROJECT_ID_ROLE = Qt.ItemDataRole.UserRole


@dataclass(frozen=True)
class ProjectListEntry:
    """Projet + statuts à afficher dans la sidebar.

    Attributes:
        project: Projet.
        generation_status: Statut du dernier run de génération.
        pedagogy_status: Statut de la dernière exécution pédagogie.
    """

    project: Project
    generation_status: RunStatus
    pedagogy_status: RunStatus


def _entry_label(entry: ProjectListEntry) -> str:
    """Libellé d'une entrée : ``G <icône> / P <icône>  <nom>``.

    Args:
        entry: Entrée à formater.

    Returns:
        Le libellé affiché dans la liste.
    """
    gen = run_status_icon(entry.generation_status)
    ped = run_status_icon(entry.pedagogy_status)
    return f"G {gen} / P {ped}   {entry.project.name}"


def _entry_tooltip(entry: ProjectListEntry) -> str:
    """Infobulle détaillant les statuts en clair.

    Args:
        entry: Entrée à formater.

    Returns:
        Texte d'infobulle.
    """
    return (
        f"Génération : {run_status_label(entry.generation_status)}\n"
        f"Pédagogie : {run_status_label(entry.pedagogy_status)}"
    )


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

    def set_projects(self, entries: Iterable[ProjectListEntry]) -> None:
        """Remplit la sidebar (reconstruction complète : ajout/suppression).

        Args:
            entries: Entrées (projet + statuts) à afficher.
        """
        self.clear()
        for entry in entries:
            item = QListWidgetItem(_entry_label(entry))
            item.setData(_PROJECT_ID_ROLE, entry.project.id.value)
            item.setToolTip(_entry_tooltip(entry))
            self.addItem(item)

    def update_statuses(self, entries: Iterable[ProjectListEntry]) -> None:
        """Met à jour les icônes de statut des items existants, sans reconstruire.

        Préserve la sélection courante (pas de ``clear``). Les entrées dont le
        projet n'est pas dans la liste sont ignorées (un ajout/suppression passe
        par ``set_projects``).

        Args:
            entries: Entrées (projet + statuts) à refléter.
        """
        by_id = {entry.project.id.value: entry for entry in entries}
        for i in range(self.count()):
            item = self.item(i)
            value = item.data(_PROJECT_ID_ROLE)
            entry = by_id.get(value) if isinstance(value, str) else None
            if entry is not None:
                item.setText(_entry_label(entry))
                item.setToolTip(_entry_tooltip(entry))

    def current_project_id(self) -> ProjectId | None:
        """Identifiant du projet actuellement sélectionné, ou ``None``.

        Returns:
            Le ``ProjectId`` sélectionné, ou ``None`` si aucune sélection.
        """
        row = self.currentRow()
        if row < 0:
            return None
        value = self.item(row).data(_PROJECT_ID_ROLE)
        return ProjectId(value=value) if isinstance(value, str) else None

    def select_project(self, project_id: ProjectId) -> None:
        """Sélectionne le projet correspondant à ``project_id`` dans la liste.

        Idempotent : si l'item n'existe pas (sidebar pas encore peuplée),
        ne fait rien. Le callback ``on_project_selected`` est déclenché
        normalement par le signal Qt ``currentItemChanged``.

        Args:
            project_id: Identifiant du projet à mettre en sélection.
        """
        for i in range(self.count()):
            item = self.item(i)
            value = item.data(_PROJECT_ID_ROLE)
            if isinstance(value, str) and value == project_id.value:
                self.setCurrentRow(i)
                return

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
