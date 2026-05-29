"""Widget ``ProjectsSidebar`` — liste latérale des projets (statuts lisibles).

Chaque entrée affiche le projet avec un rendu deux-lignes moderne :

- **pastille colorée** à gauche (vert / bleu / orange / rouge / gris selon le
  pire des statuts génération / pédagogie) ;
- **nom du projet** en titre ;
- **sous-libellé** en clair (« Génération en cours · Supports à jour »).

Le rendu est porté par un :class:`_ProjectListItem` (``QWidget`` posé via
``setItemWidget``) plutôt qu'un délégué pour rester simple à styler en QSS et
testable. Expose un menu contextuel (clic droit) avec deux actions
*Modifier…* et *Supprimer…*.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Final

from PySide6.QtCore import QCoreApplication, QPoint, QSize, Qt
from PySide6.QtGui import QAction, QContextMenuEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QVBoxLayout,
    QWidget,
)

from fahmi2.domain.enums import RunStatus
from fahmi2.domain.ids import ProjectId
from fahmi2.domain.project import Project
from fahmi2.ui.status_labels import (
    ACCENT_NEUTRAL,
    run_status_accent,
    run_status_label,
)

#: Rôle Qt portant la valeur de ``ProjectId`` dans chaque ``QListWidgetItem``.
_PROJECT_ID_ROLE: Final[int] = int(Qt.ItemDataRole.UserRole)

#: Glyphe Unicode utilisé comme pastille de statut (cercle plein).
_STATUS_DOT: Final[str] = "●"

#: Hauteur fixe (px) d'une ligne — assez d'air pour nom + sous-libellé.
_ITEM_HEIGHT_PX: Final[int] = 56
#: Marges et espacements internes de la ligne.
_ITEM_PADDING_LEFT: Final[int] = 12
_ITEM_PADDING_TOP: Final[int] = 8
_ITEM_PADDING_RIGHT: Final[int] = 12
_ITEM_PADDING_BOTTOM: Final[int] = 8
_ITEM_H_SPACING: Final[int] = 10
_ITEM_TEXT_V_SPACING: Final[int] = 2

#: ``objectName`` de la pastille (stylé via QSS avec la même mécanique
#: ``accent="success"/"running"/...`` que les valeurs des tuiles de stats).
_DOT_OBJECT_NAME: Final[str] = "projectListDot"
#: ``objectName`` du nom du projet (titre bold).
_NAME_OBJECT_NAME: Final[str] = "projectListName"
#: ``objectName`` du sous-libellé (statuts en clair, gris).
_SUBTITLE_OBJECT_NAME: Final[str] = "projectListSubtitle"


@dataclass(frozen=True)
class ProjectListEntry:
    """Projet + statuts à afficher dans la sidebar.

    Attributes:
        project: Projet.
        generation_status: Statut du dernier run de génération.
        pedagogy_status: Statut de la dernière exécution pédagogie.
        visuals_status: Statut de la dernière exécution des visualisations.
    """

    project: Project
    generation_status: RunStatus
    pedagogy_status: RunStatus
    visuals_status: RunStatus = RunStatus.CREATED


#: Priorité des accents pour la pastille agrégée. Le plus haut « gagne » :
#: si au moins une fonctionnalité est en cours / en pause / en erreur,
#: la pastille reflète cet état plutôt qu'un statut neutre/succès.
_ACCENT_PRIORITY: Final[dict[str, int]] = {
    "danger": 4,
    "warning": 3,
    "running": 2,
    "success": 1,
    ACCENT_NEUTRAL: 0,
}


def _aggregated_accent(entry: ProjectListEntry) -> str:
    """Retourne l'accent de pastille à afficher (pire des deux statuts).

    Args:
        entry: Entrée à évaluer.

    Returns:
        L'identifiant d'accent (``"running"``/``"success"``/...) à passer à
        la propriété QSS ``accent`` de la pastille.
    """
    accents = (
        run_status_accent(entry.generation_status),
        run_status_accent(entry.pedagogy_status),
        run_status_accent(entry.visuals_status),
    )
    return max(accents, key=lambda accent: _ACCENT_PRIORITY[accent])


def _entry_subtitle(entry: ProjectListEntry) -> str:
    """Sous-libellé d'une entrée (statuts en clair, séparés par un ·).

    Les statuts (``en cours``, ``à jour``…) sont récupérés via
    :func:`run_status_label` qui passe par ``QCoreApplication.translate`` —
    le sous-libellé est ainsi composé dans la langue active.

    Args:
        entry: Entrée à formater.

    Returns:
        Texte du sous-libellé (ex. « Génération en cours · Supports à jour »).
    """
    gen_label = run_status_label(entry.generation_status)
    ped_label = run_status_label(entry.pedagogy_status)
    vis_label = run_status_label(entry.visuals_status)
    # ``{gen}`` / ``{ped}`` / ``{vis}`` sont des placeholders nommés (Qt + Python
    # ``str.format`` les conservent à travers la traduction). Les
    # traducteurs ne doivent pas les renommer.
    return QCoreApplication.translate(
        "ProjectsSidebar", "Génération {gen} · Supports {ped} · Visuels {vis}"
    ).format(
        gen=gen_label.lower(), ped=ped_label.lower(), vis=vis_label.lower()
    )


def _entry_tooltip(entry: ProjectListEntry) -> str:
    """Infobulle détaillant les deux statuts en clair (multi-lignes).

    Args:
        entry: Entrée à formater.

    Returns:
        Texte d'infobulle.
    """
    return QCoreApplication.translate(
        "ProjectsSidebar", "Génération : {gen}\nSupports : {ped}\nVisuels : {vis}"
    ).format(
        gen=run_status_label(entry.generation_status),
        ped=run_status_label(entry.pedagogy_status),
        vis=run_status_label(entry.visuals_status),
    )


class _ProjectListItem(QWidget):
    """Widget custom posé sur chaque ligne (pastille + nom + sous-libellé)."""

    def __init__(self, entry: ProjectListEntry, parent: QWidget | None = None) -> None:
        """Construit le widget pour ``entry``.

        Args:
            entry: Entrée à afficher.
            parent: Parent Qt optionnel.
        """
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(
            _ITEM_PADDING_LEFT,
            _ITEM_PADDING_TOP,
            _ITEM_PADDING_RIGHT,
            _ITEM_PADDING_BOTTOM,
        )
        layout.setSpacing(_ITEM_H_SPACING)

        self._dot = QLabel(_STATUS_DOT, self)
        self._dot.setObjectName(_DOT_OBJECT_NAME)
        self._dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._dot)

        text_block = QVBoxLayout()
        text_block.setContentsMargins(0, 0, 0, 0)
        text_block.setSpacing(_ITEM_TEXT_V_SPACING)
        self._name = QLabel(entry.project.name, self)
        self._name.setObjectName(_NAME_OBJECT_NAME)
        self._subtitle = QLabel(_entry_subtitle(entry), self)
        self._subtitle.setObjectName(_SUBTITLE_OBJECT_NAME)
        text_block.addWidget(self._name)
        text_block.addWidget(self._subtitle)
        layout.addLayout(text_block, stretch=1)

        self.update_entry(entry)

    def update_entry(self, entry: ProjectListEntry) -> None:
        """Met à jour le contenu (nom + sous-libellé + accent de pastille).

        Args:
            entry: Nouvelle entrée à refléter.
        """
        self._name.setText(entry.project.name)
        self._subtitle.setText(_entry_subtitle(entry))
        self._dot.setProperty("accent", _aggregated_accent(entry))
        # Force le re-polish de la pastille pour que le changement d'accent
        # soit pris en compte par le QSS dynamique.
        style = self._dot.style()
        if style is not None:
            style.unpolish(self._dot)
            style.polish(self._dot)


class ProjectsSidebar(QListWidget):
    """Liste latérale des projets de l'utilisateur (statuts lisibles)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Construit la sidebar.

        Args:
            parent: Parent Qt optionnel.
        """
        super().__init__(parent)
        self.setObjectName("projectsSidebar")
        self._on_select: Callable[[ProjectId], None] | None = None
        self._on_edit: Callable[[ProjectId], None] | None = None
        self._on_delete: Callable[[ProjectId], None] | None = None
        # Mapping clé = ProjectId.value, valeur = widget custom de la ligne,
        # pour permettre les mises à jour live (``update_statuses``) sans
        # reconstruire la liste (préserve la sélection).
        self._row_widgets: dict[str, _ProjectListItem] = {}
        self.currentItemChanged.connect(self._on_selection_changed)

    def set_on_project_selected(
        self, callback: Callable[[ProjectId], None]
    ) -> None:
        """Définit le callback à appeler quand la sélection change."""
        self._on_select = callback

    def set_on_edit_requested(
        self, callback: Callable[[ProjectId], None]
    ) -> None:
        """Définit le callback appelé pour l'action « Modifier… »."""
        self._on_edit = callback

    def set_on_delete_requested(
        self, callback: Callable[[ProjectId], None]
    ) -> None:
        """Définit le callback appelé pour l'action « Supprimer… »."""
        self._on_delete = callback

    def set_projects(self, entries: Iterable[ProjectListEntry]) -> None:
        """Remplit la sidebar (reconstruction complète : ajout/suppression).

        Args:
            entries: Entrées (projet + statuts) à afficher.
        """
        self.clear()
        self._row_widgets.clear()
        for entry in entries:
            item = QListWidgetItem(self)
            item.setData(_PROJECT_ID_ROLE, entry.project.id.value)
            item.setToolTip(_entry_tooltip(entry))
            item.setSizeHint(QSize(0, _ITEM_HEIGHT_PX))
            widget = _ProjectListItem(entry, self)
            self.addItem(item)
            self.setItemWidget(item, widget)
            self._row_widgets[entry.project.id.value] = widget

    def update_statuses(self, entries: Iterable[ProjectListEntry]) -> None:
        """Met à jour les statuts des items existants, sans reconstruire.

        Préserve la sélection courante (pas de ``clear``). Les entrées dont
        le projet n'est pas dans la liste sont ignorées.

        Args:
            entries: Entrées (projet + statuts) à refléter.
        """
        for entry in entries:
            widget = self._row_widgets.get(entry.project.id.value)
            if widget is not None:
                widget.update_entry(entry)
            # Met également à jour l'infobulle attachée à l'item.
            for i in range(self.count()):
                item = self.item(i)
                if item.data(_PROJECT_ID_ROLE) == entry.project.id.value:
                    item.setToolTip(_entry_tooltip(entry))
                    break

    def current_project_id(self) -> ProjectId | None:
        """Identifiant du projet actuellement sélectionné, ou ``None``."""
        row = self.currentRow()
        if row < 0:
            return None
        value = self.item(row).data(_PROJECT_ID_ROLE)
        return ProjectId(value=value) if isinstance(value, str) else None

    def select_project(self, project_id: ProjectId) -> None:
        """Sélectionne le projet ``project_id`` dans la liste (idempotent).

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

        ``QListWidget.itemAt`` attend des coordonnées du viewport interne,
        pas du widget complet : on convertit donc explicitement la position
        globale du clic avant de chercher l'item ciblé, pour rester
        insensible au padding éventuel posé par la feuille de style.

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
        edit_action = QAction(self.tr("Modifier…"), menu)
        delete_action = QAction(self.tr("Supprimer…"), menu)
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
        """Slot interne : propage la sélection au callback enregistré."""
        del previous
        if current is None or self._on_select is None:
            return
        value = current.data(_PROJECT_ID_ROLE)
        if isinstance(value, str):
            self._on_select(ProjectId(value=value))
