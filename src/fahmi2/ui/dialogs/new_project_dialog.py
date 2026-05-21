"""Dialogue ``NewProjectDialog`` — création/renommage minimal d'un projet.

Ne porte que l'**identité** du projet : nom + emplacement (``workspace_folder``).
Les réglages de génération s'éditent depuis l'onglet Génération
(``GenerationSettingsView``). En mode édition, l'emplacement est en lecture seule
(immuable après création).
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

_DIALOG_WIDTH_PX = 520
_TITLE_CREATE = "Nouveau projet"
_TITLE_EDIT = "Renommer le projet"


class NewProjectDialog(QDialog):
    """Dialogue minimal : nom + emplacement du projet."""

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        initial_name: str | None = None,
        initial_workspace: Path | None = None,
    ) -> None:
        """Construit le dialogue.

        Args:
            parent: Parent Qt optionnel.
            initial_name: Nom pré-rempli (mode édition).
            initial_workspace: Emplacement pré-rempli (mode édition, lecture seule).
        """
        super().__init__(parent)
        self._is_edit_mode = initial_name is not None
        self.setWindowTitle(_TITLE_EDIT if self._is_edit_mode else _TITLE_CREATE)
        self.setMinimumWidth(_DIALOG_WIDTH_PX)
        self._result_name: str | None = None
        self._result_workspace: Path | None = None

        form = QFormLayout()
        self._name_input = QLineEdit(self)
        form.addRow("Nom :", self._name_input)

        self._workspace_input = QLineEdit(self)
        self._workspace_input.setReadOnly(True)
        self._browse_btn = QPushButton("Parcourir…", self)
        self._browse_btn.clicked.connect(self._browse_workspace)
        ws_row = QHBoxLayout()
        ws_row.addWidget(self._workspace_input)
        ws_row.addWidget(self._browse_btn)
        form.addRow("Emplacement :", ws_row)

        button_label = (
            QDialogButtonBox.StandardButton.Save
            if self._is_edit_mode
            else QDialogButtonBox.StandardButton.Ok
        )
        buttons = QDialogButtonBox(
            button_label | QDialogButtonBox.StandardButton.Cancel, parent=self
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)

        outer = QVBoxLayout(self)
        outer.addLayout(form)
        outer.addWidget(buttons)

        if initial_name is not None:
            self._name_input.setText(initial_name)
        if initial_workspace is not None:
            self._workspace_input.setText(str(initial_workspace))
        if self._is_edit_mode:
            # Emplacement immuable après création : on désactive sa modification.
            self._browse_btn.setEnabled(False)

    def get_name(self) -> str | None:
        """Retourne le nom saisi, ou ``None`` si annulation/invalide.

        Returns:
            Le nom du projet, ou ``None``.
        """
        return self._result_name

    def get_workspace_folder(self) -> Path | None:
        """Retourne l'emplacement, ou ``None`` si annulation/invalide.

        Returns:
            Le ``workspace_folder``, ou ``None``.
        """
        return self._result_workspace

    def _browse_workspace(self) -> None:
        """Ouvre un sélecteur de dossier d'emplacement."""
        folder = QFileDialog.getExistingDirectory(self, "Emplacement du projet")
        if folder:
            self._workspace_input.setText(folder)

    def _on_accept(self) -> None:
        """Valide la saisie (nom + emplacement) et clôt le dialogue."""
        name = self._name_input.text().strip()
        workspace_text = self._workspace_input.text().strip()
        if not name or not workspace_text:
            QMessageBox.warning(
                self,
                "Champs manquants",
                "Veuillez renseigner le nom et l'emplacement du projet.",
            )
            return
        self._result_name = name
        self._result_workspace = Path(workspace_text)
        self.accept()
