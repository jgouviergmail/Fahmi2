"""Dialogue ``NewProjectDialog`` — création/renommage minimal d'un projet.

Ne porte que l'**identité** du projet : nom + emplacement (``workspace_folder``).
Les réglages de génération s'éditent depuis l'onglet Génération
(``GenerationSettingsView``). En mode édition, l'emplacement est en lecture
seule (immuable après création) et le bouton de sélection est désactivé.

Présentation : une seule carte centrée (identité du projet) avec un texte
d'aide expliquant l'immutabilité du dossier. Boutons standard Qt traduits
en français (``Annuler`` / ``Créer`` ou ``Enregistrer``).
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from fahmi2.ui._components import (
    card,
    field_hint,
    frenchify_button_box,
    settings_form,
)

#: Largeur minimale (px) du dialogue (donne assez de place à la carte centrée).
_DIALOG_WIDTH_PX: Final[int] = 560
#: Marges externes du dialogue.
_OUTER_MARGIN_HORIZONTAL: Final[int] = 28
_OUTER_MARGIN_TOP: Final[int] = 24
_OUTER_MARGIN_BOTTOM: Final[int] = 18
_OUTER_SPACING: Final[int] = 14
#: Largeur min/max de la colonne contenant la carte (centrée).
_COLUMN_MIN_WIDTH: Final[int] = 460
_COLUMN_MAX_WIDTH: Final[int] = 560

_TITLE_CREATE: Final[str] = "Nouveau projet"
_TITLE_EDIT: Final[str] = "Renommer le projet"

_CARD_TITLE: Final[str] = "Identité du projet"
_CARD_DESC: Final[str] = (
    "Nom du projet et dossier de travail. Le dossier est défini une seule fois "
    "à la création et ne peut plus être déplacé ensuite."
)
_NAME_LABEL: Final[str] = "Nom du projet"
_WORKSPACE_LABEL: Final[str] = "Dossier du projet"
_BROWSE_LABEL: Final[str] = "Choisir…"
_BROWSE_DIALOG_TITLE: Final[str] = "Emplacement du projet"
_WORKSPACE_HINT_CREATE: Final[str] = (
    "Ce dossier contiendra le document consolidé, le glossaire et les supports "
    "générés. Choisissez un emplacement où vous gardez vos travaux."
)
_WORKSPACE_HINT_EDIT: Final[str] = (
    "Le dossier du projet est fixé à la création et ne peut plus être modifié."
)
_NAME_TOOLTIP: Final[str] = (
    "Nom court et reconnaissable affiché dans la liste des projets."
)
_BROWSE_TOOLTIP: Final[str] = (
    "Choisissez le dossier qui contiendra les livrables du projet."
)
_VALIDATION_TITLE: Final[str] = "Champs manquants"
_VALIDATION_MESSAGE: Final[str] = (
    "Veuillez renseigner le nom et l'emplacement du projet."
)
_CREATE_BUTTON_TEXT: Final[str] = "Créer le projet"



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

        self._name_input = QLineEdit(self)
        self._name_input.setToolTip(_NAME_TOOLTIP)
        self._workspace_input = QLineEdit(self)
        self._workspace_input.setReadOnly(True)
        self._browse_btn = QPushButton(_BROWSE_LABEL, self)
        self._browse_btn.setToolTip(_BROWSE_TOOLTIP)
        self._browse_btn.clicked.connect(self._browse_workspace)

        card_frame = self._build_identity_card()
        column = self._build_centered_column(card_frame)
        buttons = self._build_button_box()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(
            _OUTER_MARGIN_HORIZONTAL,
            _OUTER_MARGIN_TOP,
            _OUTER_MARGIN_HORIZONTAL,
            _OUTER_MARGIN_BOTTOM,
        )
        outer.setSpacing(_OUTER_SPACING)
        outer.addWidget(column, alignment=Qt.AlignmentFlag.AlignHCenter)
        outer.addStretch(1)
        outer.addWidget(buttons)

        if initial_name is not None:
            self._name_input.setText(initial_name)
        if initial_workspace is not None:
            self._workspace_input.setText(str(initial_workspace))
        if self._is_edit_mode:
            # Emplacement immuable après création : on désactive sa modification.
            self._browse_btn.setEnabled(False)

    def _build_identity_card(self) -> QWidget:
        """Construit la carte « Identité du projet » (nom + dossier + hint).

        Returns:
            Le widget de carte prêt à être placé dans la colonne centrale.
        """
        card_frame, card_layout = card(
            self, title=_CARD_TITLE, description=_CARD_DESC
        )
        form = settings_form()
        form.addRow(_NAME_LABEL, self._name_input)
        ws_row = QHBoxLayout()
        # ``stretch=1`` : la ligne d'entrée prend toute la largeur disponible,
        # le bouton « Choisir… » garde sa taille naturelle à droite.
        ws_row.addWidget(self._workspace_input, stretch=1)
        ws_row.addWidget(self._browse_btn)
        form.addRow(_WORKSPACE_LABEL, ws_row)
        card_layout.addLayout(form)
        hint_text = (
            _WORKSPACE_HINT_EDIT if self._is_edit_mode else _WORKSPACE_HINT_CREATE
        )
        card_layout.addWidget(field_hint(card_frame, hint_text))
        return card_frame

    def _build_centered_column(self, card_frame: QWidget) -> QWidget:
        """Englobe ``card_frame`` dans une colonne cadrée en largeur (centrée).

        Args:
            card_frame: La carte à placer dans la colonne.

        Returns:
            Le widget colonne (à ajouter au layout externe avec alignement
            ``AlignHCenter``).
        """
        column = QWidget(self)
        column.setMinimumWidth(_COLUMN_MIN_WIDTH)
        column.setMaximumWidth(_COLUMN_MAX_WIDTH)
        column_layout = QVBoxLayout(column)
        column_layout.setContentsMargins(0, 0, 0, 0)
        column_layout.setSpacing(_OUTER_SPACING)
        column_layout.addWidget(card_frame)
        return column

    def _build_button_box(self) -> QDialogButtonBox:
        """Construit la barre de boutons (« Annuler » + Créer/Enregistrer).

        Returns:
            Le ``QDialogButtonBox`` câblé sur ``_on_accept`` / ``reject``.
        """
        primary_std_button = (
            QDialogButtonBox.StandardButton.Save
            if self._is_edit_mode
            else QDialogButtonBox.StandardButton.Ok
        )
        buttons = QDialogButtonBox(
            primary_std_button | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        frenchify_button_box(buttons)
        if not self._is_edit_mode:
            ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
            if ok_button is not None:
                ok_button.setText(_CREATE_BUTTON_TEXT)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        return buttons

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
        folder = QFileDialog.getExistingDirectory(self, _BROWSE_DIALOG_TITLE)
        if folder:
            self._workspace_input.setText(folder)

    def _on_accept(self) -> None:
        """Valide la saisie (nom + emplacement) et clôt le dialogue."""
        name = self._name_input.text().strip()
        workspace_text = self._workspace_input.text().strip()
        if not name or not workspace_text:
            QMessageBox.warning(self, _VALIDATION_TITLE, _VALIDATION_MESSAGE)
            return
        self._result_name = name
        self._result_workspace = Path(workspace_text)
        self.accept()
