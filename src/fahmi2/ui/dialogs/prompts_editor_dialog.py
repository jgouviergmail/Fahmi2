"""Dialogue ``PromptsEditorDialog`` — édition des prompts LLM par phase.

Permet à l'utilisateur de personnaliser les templates Jinja2 utilisés par
chaque phase LLM, sans toucher au code de l'application. Les surcouches sont
stockées dans ``%APPDATA%/Fahmi2/prompts/`` et chargées prioritairement par
:py:class:`~fahmi2.infra.prompts.loader.PromptLoader` au prochain lancement
de phase.

Layout :

- Liste à gauche : un item par template (phases 1 à 7 + sous-prompt 5a).
  Un astérisque ``*`` indique qu'un override est actif pour cette phase.
- Zone à droite : description courte + éditeur Markdown/Jinja2 monospace.
- Boutons bas : ``Enregistrer``, ``Réinitialiser au défaut``, ``Fermer``.
"""

from __future__ import annotations

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
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from fahmi2.app.prompts_service import PromptsService, PromptTemplateMeta
from fahmi2.core.errors.exceptions import Fahmi2Error

_DIALOG_INITIAL_WIDTH_PX = 1000
_DIALOG_INITIAL_HEIGHT_PX = 700
_TEMPLATE_NAME_ROLE = Qt.ItemDataRole.UserRole
_OVERRIDE_MARKER = " *"


class PromptsEditorDialog(QDialog):
    """Éditeur des prompts LLM par phase (overrides ``%APPDATA%/Fahmi2/prompts``)."""

    def __init__(  # noqa: PLR0915
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
        self.setWindowTitle("Modifier les prompts")
        self.resize(_DIALOG_INITIAL_WIDTH_PX, _DIALOG_INITIAL_HEIGHT_PX)
        self._service = prompts_service
        self._current_name: str | None = None
        # Trace les sources actuellement chargées pour détecter les
        # modifications non sauvegardées avant un changement de sélection.
        self._loaded_source: str = ""

        layout = QVBoxLayout(self)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        layout.addWidget(splitter, stretch=1)

        # Sidebar : liste des templates
        self._list_widget = QListWidget(splitter)
        self._list_widget.setMinimumWidth(280)
        for meta in self._service.list_templates():
            item = QListWidgetItem(_format_item_label(meta, self._service))
            item.setData(_TEMPLATE_NAME_ROLE, meta.name)
            self._list_widget.addItem(item)
        self._list_widget.currentRowChanged.connect(self._on_selection_changed)
        splitter.addWidget(self._list_widget)

        # Panneau de droite : description + éditeur
        right_panel = QWidget(splitter)
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(8, 0, 0, 0)

        self._description_label = QLabel(right_panel)
        self._description_label.setWordWrap(True)
        right_layout.addWidget(self._description_label)

        self._status_label = QLabel(right_panel)
        self._status_label.setObjectName("promptsEditorStatus")
        right_layout.addWidget(self._status_label)

        self._editor = QPlainTextEdit(right_panel)
        self._editor.setObjectName("promptsEditorTextArea")
        editor_font = QFont("Consolas")
        editor_font.setStyleHint(QFont.StyleHint.Monospace)
        editor_font.setPointSize(10)
        self._editor.setFont(editor_font)
        right_layout.addWidget(self._editor, stretch=1)

        # Actions
        actions_row = QHBoxLayout()
        self._save_button = QPushButton("💾  Enregistrer", right_panel)
        self._reset_button = QPushButton(
            "↩  Réinitialiser au défaut", right_panel
        )
        self._save_button.clicked.connect(self._on_save)
        self._reset_button.clicked.connect(self._on_reset)
        actions_row.addWidget(self._save_button)
        actions_row.addWidget(self._reset_button)
        actions_row.addStretch(1)
        right_layout.addLayout(actions_row)

        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([280, _DIALOG_INITIAL_WIDTH_PX - 280])

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Close, parent=self
        )
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        # Sélectionne le premier template par défaut.
        if self._list_widget.count() > 0:
            self._list_widget.setCurrentRow(0)

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
                "Template invalide",
                f"{exc.code}\n\n{exc.user_message}",
            )
            return
        self._loaded_source = content
        self._refresh_item_label(self._current_name)
        self._refresh_status_label()
        QMessageBox.information(
            self,
            "Prompt enregistré",
            "L'override est actif au prochain lancement de phase.",
        )

    def _on_reset(self) -> None:
        """Slot : supprime l'override courant après confirmation."""
        if self._current_name is None:
            return
        if not self._service.has_override(self._current_name):
            QMessageBox.information(
                self,
                "Aucun override actif",
                "Ce template n'a pas d'override personnalisé.",
            )
            return
        reply = QMessageBox.question(
            self,
            "Réinitialiser au défaut ?",
            (
                "Supprimer l'override personnalisé et restaurer le prompt "
                "par défaut bundlé avec l'application ?"
            ),
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
            self._status_label.setText(
                "✏️ <i>Override personnalisé actif</i>"
            )
        else:
            self._status_label.setText(
                "📦 <i>Prompt par défaut (aucun override)</i>"
            )

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
            "Abandonner les modifications ?",
            (
                "Vous avez des modifications non enregistrées sur ce prompt. "
                "Les abandonner pour changer de phase ?"
            ),
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


def _find_meta(
    service: PromptsService, name: str
) -> PromptTemplateMeta | None:
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
