"""Dialogue ``PromptsEditorDialog`` — édition des prompts LLM par phase.

Permet à l'utilisateur de personnaliser les templates Jinja2 utilisés par
chaque phase LLM, sans toucher au code de l'application. Les surcouches sont
stockées dans ``%APPDATA%/Fahmi2/prompts/`` et chargées prioritairement par
:py:class:`~fahmi2.infra.prompts.loader.PromptLoader` au prochain lancement
de phase.

Layout :

- Liste à gauche : un item par template. Un astérisque ``*`` indique qu'un
  override est actif pour cette phase.
- Panneau de droite : en-tête de page (nom du template + description),
  pastille de statut (override actif / défaut), éditeur Markdown/Jinja2
  monospace, boutons d'action.
- Bas du dialogue : bouton « Fermer ».
"""

from __future__ import annotations

from typing import Final

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from fahmi2.app.prompts_service import PromptsService, PromptTemplateMeta
from fahmi2.core.errors.exceptions import Fahmi2Error
from fahmi2.ui._buttons import (
    BUTTON_ROLE_DEFAULT,
    BUTTON_ROLE_PRIMARY,
    make_role_button,
)
from fahmi2.ui._components import frenchify_button_box, page_header

# ---------------------------------------------------------------- dimensions

_DIALOG_INITIAL_WIDTH_PX: Final[int] = 1040
_DIALOG_INITIAL_HEIGHT_PX: Final[int] = 720
_LIST_MIN_WIDTH_PX: Final[int] = 300
_OUTER_MARGIN_HORIZONTAL: Final[int] = 22
_OUTER_MARGIN_TOP: Final[int] = 22
_OUTER_MARGIN_BOTTOM: Final[int] = 18
_OUTER_SPACING: Final[int] = 14
_RIGHT_PANEL_LEFT_MARGIN: Final[int] = 18
_RIGHT_PANEL_SPACING: Final[int] = 12
_ACTIONS_ROW_SPACING: Final[int] = 8
_EDITOR_FONT_POINT_SIZE: Final[int] = 10

# ---------------------------------------------------------------- libellés

_DIALOG_TITLE: Final[str] = "Modifier les prompts"
_PAGE_TITLE: Final[str] = "Éditeur de prompts"
_PAGE_DESC: Final[str] = (
    "Personnalisez les prompts Jinja2 utilisés par les phases IA. Vos overrides "
    "sont stockés dans %APPDATA%/Fahmi2/prompts et chargés prioritairement au "
    "prochain lancement."
)
_TEMPLATE_NAME_ROLE: Final[int] = int(Qt.ItemDataRole.UserRole)
_OVERRIDE_MARKER: Final[str] = " *"

_SAVE_LABEL: Final[str] = "💾  Enregistrer"
_RESET_LABEL: Final[str] = "↩  Réinitialiser au défaut"

_STATUS_OVERRIDE_ACTIVE: Final[str] = "✏️ <i>Override personnalisé actif</i>"
_STATUS_DEFAULT: Final[str] = "📦 <i>Prompt par défaut (aucun override)</i>"

_TEMPLATE_INVALID_TITLE: Final[str] = "Template invalide"
_PROMPT_SAVED_TITLE: Final[str] = "Prompt enregistré"
_PROMPT_SAVED_MESSAGE: Final[str] = "L'override est actif au prochain lancement de phase."
_NO_OVERRIDE_TITLE: Final[str] = "Aucun override actif"
_NO_OVERRIDE_MESSAGE: Final[str] = "Ce template n'a pas d'override personnalisé."
_RESET_CONFIRM_TITLE: Final[str] = "Réinitialiser au défaut ?"
_RESET_CONFIRM_MESSAGE: Final[str] = (
    "Supprimer l'override personnalisé et restaurer le prompt par défaut bundlé "
    "avec l'application ?"
)
_DISCARD_TITLE: Final[str] = "Abandonner les modifications ?"
_DISCARD_MESSAGE: Final[str] = (
    "Vous avez des modifications non enregistrées sur ce prompt. Les abandonner "
    "pour changer de phase ?"
)

#: Police monospace utilisée par l'éditeur (cohérent avec ``#logsDockArea``).
_EDITOR_FONT_FAMILY: Final[str] = "Consolas"

#: ``objectName`` du label de statut (stylé via QSS : ``#promptsEditorStatus``).
_STATUS_OBJECT_NAME: Final[str] = "promptsEditorStatus"
#: ``objectName`` de la zone d'édition (stylé via QSS : ``#promptsEditorTextArea``).
_EDITOR_OBJECT_NAME: Final[str] = "promptsEditorTextArea"


class PromptsEditorDialog(QDialog):
    """Éditeur des prompts LLM par phase (overrides ``%APPDATA%/Fahmi2/prompts``)."""

    def __init__(
        self,
        prompts_service: PromptsService,
        parent: QWidget | None = None,
    ) -> None:
        """Construit le dialogue.

        Args:
            prompts_service: Service applicatif de gestion des prompts.
            parent: Parent Qt optionnel.
        """
        super().__init__(parent)
        self.setWindowTitle(_DIALOG_TITLE)
        self.resize(_DIALOG_INITIAL_WIDTH_PX, _DIALOG_INITIAL_HEIGHT_PX)
        self._service = prompts_service
        self._current_name: str | None = None
        # Trace les sources actuellement chargées pour détecter les
        # modifications non sauvegardées avant un changement de sélection.
        self._loaded_source: str = ""

        outer = QVBoxLayout(self)
        outer.setContentsMargins(
            _OUTER_MARGIN_HORIZONTAL,
            _OUTER_MARGIN_TOP,
            _OUTER_MARGIN_HORIZONTAL,
            _OUTER_MARGIN_BOTTOM,
        )
        outer.setSpacing(_OUTER_SPACING)
        outer.addWidget(
            page_header(self, title=_PAGE_TITLE, description=_PAGE_DESC)
        )

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self._list_widget = self._build_left_list(splitter)
        right_panel = self._build_right_panel(splitter)
        splitter.addWidget(self._list_widget)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes(
            [_LIST_MIN_WIDTH_PX, _DIALOG_INITIAL_WIDTH_PX - _LIST_MIN_WIDTH_PX]
        )
        outer.addWidget(splitter, stretch=1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Close, parent=self
        )
        frenchify_button_box(buttons)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

        # Sélectionne le premier template par défaut.
        if self._list_widget.count() > 0:
            self._list_widget.setCurrentRow(0)

    def _build_left_list(self, parent: QWidget) -> QListWidget:
        """Construit la liste des templates (sidebar gauche du splitter).

        Args:
            parent: Parent Qt (typiquement le splitter).

        Returns:
            Le ``QListWidget`` peuplé avec un item par template.
        """
        list_widget = QListWidget(parent)
        list_widget.setMinimumWidth(_LIST_MIN_WIDTH_PX)
        for meta in self._service.list_templates():
            item = QListWidgetItem(_format_item_label(meta, self._service))
            item.setData(_TEMPLATE_NAME_ROLE, meta.name)
            list_widget.addItem(item)
        list_widget.currentRowChanged.connect(self._on_selection_changed)
        return list_widget

    def _build_right_panel(self, parent: QWidget) -> QWidget:
        """Construit le panneau de droite (description + statut + éditeur + actions).

        Args:
            parent: Parent Qt (typiquement le splitter).

        Returns:
            Le widget assemblé.
        """
        right_panel = QWidget(parent)
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(_RIGHT_PANEL_LEFT_MARGIN, 0, 0, 0)
        right_layout.setSpacing(_RIGHT_PANEL_SPACING)

        # Description dynamique du template (titre + description mis à jour à
        # chaque ``_load_template``). ``QLabel`` direct avec HTML simple plutôt
        # qu'un ``page_header`` statique, car le contenu varie par sélection.
        self._description_label = QLabel(right_panel)
        self._description_label.setWordWrap(True)
        right_layout.addWidget(self._description_label)

        self._status_label = QLabel(right_panel)
        self._status_label.setObjectName(_STATUS_OBJECT_NAME)
        right_layout.addWidget(self._status_label)

        self._editor = QPlainTextEdit(right_panel)
        self._editor.setObjectName(_EDITOR_OBJECT_NAME)
        editor_font = QFont(_EDITOR_FONT_FAMILY)
        editor_font.setStyleHint(QFont.StyleHint.Monospace)
        editor_font.setPointSize(_EDITOR_FONT_POINT_SIZE)
        self._editor.setFont(editor_font)
        right_layout.addWidget(self._editor, stretch=1)

        actions_row = QHBoxLayout()
        actions_row.setSpacing(_ACTIONS_ROW_SPACING)
        self._save_button = make_role_button(
            right_panel, _SAVE_LABEL, role=BUTTON_ROLE_PRIMARY
        )
        self._reset_button = make_role_button(
            right_panel, _RESET_LABEL, role=BUTTON_ROLE_DEFAULT
        )
        self._save_button.clicked.connect(self._on_save)
        self._reset_button.clicked.connect(self._on_reset)
        actions_row.addWidget(self._save_button)
        actions_row.addWidget(self._reset_button)
        actions_row.addStretch(1)
        right_layout.addLayout(actions_row)

        return right_panel

    # ------------------------------------------------------------------ events

    def _on_selection_changed(self, row: int) -> None:
        """Slot : charge le template sélectionné dans l'éditeur.

        Demande confirmation si l'utilisateur a des modifications non
        sauvegardées sur l'item précédent.

        Args:
            row: Index sélectionné dans la liste (-1 si vide).
        """
        if row < 0:
            return
        if self._has_unsaved_changes() and not self._confirm_discard_changes():
            # Reverte la sélection sur l'item précédent — bloquer le signal
            # pour ne pas relancer ce slot.
            self._restore_previous_selection()
            return
        item = self._list_widget.item(row)
        name = item.data(_TEMPLATE_NAME_ROLE)
        if not isinstance(name, str):
            return
        self._load_template(name)

    def _on_save(self) -> None:
        """Slot : enregistre l'override courant après validation Jinja2."""
        if self._current_name is None:
            return
        content = self._editor.toPlainText()
        try:
            self._service.save_override(self._current_name, content)
        except Fahmi2Error as exc:
            QMessageBox.critical(
                self,
                _TEMPLATE_INVALID_TITLE,
                f"{exc.code}\n\n{exc.user_message}",
            )
            return
        self._loaded_source = content
        self._refresh_item_label(self._current_name)
        self._refresh_status_label()
        QMessageBox.information(
            self, _PROMPT_SAVED_TITLE, _PROMPT_SAVED_MESSAGE
        )

    def _on_reset(self) -> None:
        """Slot : supprime l'override courant après confirmation."""
        if self._current_name is None:
            return
        if not self._service.has_override(self._current_name):
            QMessageBox.information(
                self, _NO_OVERRIDE_TITLE, _NO_OVERRIDE_MESSAGE
            )
            return
        reply = QMessageBox.question(
            self,
            _RESET_CONFIRM_TITLE,
            _RESET_CONFIRM_MESSAGE,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._service.reset_override(self._current_name)
        self._load_template(self._current_name)
        self._refresh_item_label(self._current_name)

    # --------------------------------------------------------------- helpers

    def _load_template(self, name: str) -> None:
        """Charge un template dans l'éditeur (override si présent, sinon défaut).

        Args:
            name: Nom du template (sans extension).
        """
        self._current_name = name
        meta = _find_meta(self._service, name)
        if meta is not None:
            self._description_label.setText(
                f"<b>{meta.display_name}</b><br>{meta.description}"
            )
        source = self._service.load_active(name)
        self._loaded_source = source
        # Bloquer les signaux pour ne pas déclencher modificationChanged
        # pendant le pré-remplissage.
        self._editor.blockSignals(True)
        self._editor.setPlainText(source)
        self._editor.blockSignals(False)
        self._refresh_status_label()

    def _refresh_item_label(self, name: str) -> None:
        """Met à jour le libellé d'un item (astérisque si override actif).

        Args:
            name: Nom du template à rafraîchir.
        """
        for i in range(self._list_widget.count()):
            item = self._list_widget.item(i)
            if item.data(_TEMPLATE_NAME_ROLE) != name:
                continue
            meta = _find_meta(self._service, name)
            if meta is None:
                continue
            item.setText(_format_item_label(meta, self._service))
            return

    def _refresh_status_label(self) -> None:
        """Met à jour le bandeau de statut (override actif / défaut)."""
        if self._current_name is None:
            self._status_label.setText("")
            return
        if self._service.has_override(self._current_name):
            self._status_label.setText(_STATUS_OVERRIDE_ACTIVE)
        else:
            self._status_label.setText(_STATUS_DEFAULT)

    def _has_unsaved_changes(self) -> bool:
        """Indique si l'éditeur diffère du source initialement chargé."""
        return self._editor.toPlainText() != self._loaded_source

    def _confirm_discard_changes(self) -> bool:
        """Demande confirmation pour abandonner les modifications en cours.

        Returns:
            ``True`` si l'utilisateur accepte de perdre ses changements.
        """
        reply = QMessageBox.question(
            self,
            _DISCARD_TITLE,
            _DISCARD_MESSAGE,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return reply == QMessageBox.StandardButton.Yes

    def _restore_previous_selection(self) -> None:
        """Revient sur l'item correspondant à ``_current_name`` sans signaler."""
        if self._current_name is None:
            return
        for i in range(self._list_widget.count()):
            item = self._list_widget.item(i)
            if item.data(_TEMPLATE_NAME_ROLE) == self._current_name:
                self._list_widget.blockSignals(True)
                self._list_widget.setCurrentRow(i)
                self._list_widget.blockSignals(False)
                return


def _format_item_label(meta: PromptTemplateMeta, service: PromptsService) -> str:
    """Compose le libellé affiché dans la sidebar (avec marqueur d'override).

    Args:
        meta: Métadonnées du template.
        service: Service (consulté pour savoir s'il y a un override).

    Returns:
        Le libellé prêt à l'affichage.
    """
    marker = _OVERRIDE_MARKER if service.has_override(meta.name) else ""
    return f"{meta.display_name}{marker}"


def _find_meta(service: PromptsService, name: str) -> PromptTemplateMeta | None:
    """Retourne les métadonnées d'un template par son nom.

    Args:
        service: Service.
        name: Nom recherché.

    Returns:
        ``PromptTemplateMeta`` ou ``None``.
    """
    for meta in service.list_templates():
        if meta.name == name:
            return meta
    return None
