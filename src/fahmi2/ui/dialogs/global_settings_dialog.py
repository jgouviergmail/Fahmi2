"""Dialogue ``GlobalSettingsDialog`` — clés API + apparence.

Présenté en deux cartes :

- *Clés API* : OpenAI et DeepSeek (saisies masquées, stockage DPAPI Windows).
- *Apparence* : combo de sélection du thème (Système / Clair / Sombre),
  câblée à un :class:`~fahmi2.app.theme_controller.ThemeController` qui
  applique le thème immédiatement et persiste la préférence.

Boutons standard Qt traduits en français via
:func:`fahmi2.ui._components.frenchify_button_box`.
"""

from __future__ import annotations

from typing import Final

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from fahmi2.app.secrets_service import SecretsService
from fahmi2.app.theme_controller import ThemeController
from fahmi2.ui._components import card, field_hint, frenchify_button_box, settings_form
from fahmi2.ui.theme import ThemeMode

#: Libellés FR des modes d'apparence (affichés dans la combo « Thème »).
_THEME_MODE_LABELS: Final[dict[ThemeMode, str]] = {
    ThemeMode.SYSTEM: "Système",
    ThemeMode.LIGHT: "Clair",
    ThemeMode.DARK: "Sombre",
}

#: Titre de la fenêtre.
_WINDOW_TITLE: Final[str] = "Paramètres globaux"
#: Largeur minimale du dialogue (px).
_DIALOG_MIN_WIDTH: Final[int] = 560
#: Marges externes du dialogue.
_OUTER_MARGIN_HORIZONTAL: Final[int] = 28
_OUTER_MARGIN_TOP: Final[int] = 24
_OUTER_MARGIN_BOTTOM: Final[int] = 18
_OUTER_SPACING: Final[int] = 16
#: Largeur min/max de la colonne centrale (donne aux champs assez de place
#: pour afficher une clé API complète tout en restant centré).
_COLUMN_MIN_WIDTH: Final[int] = 460
_COLUMN_MAX_WIDTH: Final[int] = 560

# ---------------------------------------------------------------- libellés
_KEYS_CARD_TITLE: Final[str] = "Clés API"
_KEYS_CARD_DESC: Final[str] = (
    "Les clés sont chiffrées localement (Windows DPAPI) et ne quittent jamais "
    "votre ordinateur en clair."
)
_KEY_OPENAI_LABEL: Final[str] = "Clé API OpenAI"
_KEY_DEEPSEEK_LABEL: Final[str] = "Clé API DeepSeek"
_KEY_OPENAI_TOOLTIP: Final[str] = (
    "Clé personnelle OpenAI utilisée pour la transcription en ligne et la "
    "recherche sémantique du Dialogue."
)
_KEY_DEEPSEEK_TOOLTIP: Final[str] = (
    "Clé personnelle DeepSeek utilisée pour la reformulation, les supports "
    "pédagogiques et les réponses du Dialogue."
)

_APPEARANCE_CARD_TITLE: Final[str] = "Apparence"
_APPEARANCE_CARD_DESC: Final[str] = (
    "Choisissez un mode clair, sombre, ou laissez Fahmi2 suivre le thème "
    "de votre système (Windows)."
)
_THEME_LABEL: Final[str] = "Thème de l'interface"
_THEME_TOOLTIP: Final[str] = (
    "« Système » suit automatiquement le thème de Windows. « Clair » ou "
    "« Sombre » force l'apparence indépendamment du système."
)


class GlobalSettingsDialog(QDialog):
    """Dialogue de configuration globale (clés API, apparence)."""

    def __init__(
        self,
        secrets_service: SecretsService,
        *,
        theme_controller: ThemeController,
        parent: QWidget | None = None,
    ) -> None:
        """Construit le dialogue.

        Args:
            secrets_service: Service de gestion des clés API (DPAPI).
            theme_controller: Contrôleur du thème (apparence) — l'apparence
                choisie est appliquée et persistée à la validation.
            parent: Parent Qt optionnel.
        """
        super().__init__(parent)
        self.setWindowTitle(_WINDOW_TITLE)
        self.setMinimumWidth(_DIALOG_MIN_WIDTH)
        self._secrets_service = secrets_service
        self._theme_controller = theme_controller

        keys_card = self._build_keys_card()
        appearance_card = self._build_appearance_card()
        column = self._build_centered_column(keys_card, appearance_card)
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

    def _build_keys_card(self) -> QWidget:
        """Construit la carte « Clés API » (OpenAI + DeepSeek, masquées).

        Returns:
            Le widget de carte (avec ses deux champs prêts à être lus).
        """
        keys_card, keys_layout = card(
            self, title=_KEYS_CARD_TITLE, description=_KEYS_CARD_DESC
        )
        keys_form = settings_form()
        self._openai_input = QLineEdit(keys_card)
        self._openai_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._openai_input.setToolTip(_KEY_OPENAI_TOOLTIP)
        existing_openai = self._secrets_service.get_openai_api_key()
        if existing_openai:
            self._openai_input.setText(existing_openai)
        keys_form.addRow(_KEY_OPENAI_LABEL, self._openai_input)

        self._deepseek_input = QLineEdit(keys_card)
        self._deepseek_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._deepseek_input.setToolTip(_KEY_DEEPSEEK_TOOLTIP)
        existing_deepseek = self._secrets_service.get_deepseek_api_key()
        if existing_deepseek:
            self._deepseek_input.setText(existing_deepseek)
        keys_form.addRow(_KEY_DEEPSEEK_LABEL, self._deepseek_input)
        keys_layout.addLayout(keys_form)
        return keys_card

    def _build_appearance_card(self) -> QWidget:
        """Construit la carte « Apparence » (combo de thème + hint).

        Returns:
            Le widget de carte (combo prêt à être lu à la validation).
        """
        appearance_card, appearance_layout = card(
            self, title=_APPEARANCE_CARD_TITLE, description=_APPEARANCE_CARD_DESC
        )
        appearance_form = settings_form()
        self._theme_combo = QComboBox(appearance_card)
        self._theme_combo.setToolTip(_THEME_TOOLTIP)
        for mode, label in _THEME_MODE_LABELS.items():
            # ``QComboBox`` ne préserve pas le type ``StrEnum`` : on stocke
            # ``mode.value`` et on reconverti à la lecture via ``ThemeMode(...)``
            # — cohérent avec les autres combos d'enum de l'application.
            self._theme_combo.addItem(label, mode.value)
        current_idx = self._theme_combo.findData(self._theme_controller.mode.value)
        if current_idx >= 0:
            self._theme_combo.setCurrentIndex(current_idx)
        appearance_form.addRow(_THEME_LABEL, self._theme_combo)
        appearance_layout.addLayout(appearance_form)
        appearance_layout.addWidget(
            field_hint(
                appearance_card,
                "Le changement s'applique immédiatement à toute l'application.",
            )
        )
        return appearance_card

    def _build_centered_column(self, *cards: QWidget) -> QWidget:
        """Englobe les cartes ``cards`` dans une colonne cadrée en largeur.

        Args:
            *cards: Cartes à empiler verticalement.

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
        for one_card in cards:
            column_layout.addWidget(one_card)
        return column

    def _build_button_box(self) -> QDialogButtonBox:
        """Construit la barre de boutons « Enregistrer / Annuler » (FR).

        Returns:
            Le ``QDialogButtonBox`` câblé sur ``_on_accept`` / ``reject``.
        """
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        frenchify_button_box(buttons)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        return buttons

    def _on_accept(self) -> None:
        """Persiste les clés saisies + l'apparence, et clôt le dialogue."""
        openai_key = self._openai_input.text().strip()
        deepseek_key = self._deepseek_input.text().strip()
        if openai_key:
            self._secrets_service.set_openai_api_key(openai_key)
        if deepseek_key:
            self._secrets_service.set_deepseek_api_key(deepseek_key)
        selected = self._theme_combo.currentData()
        if isinstance(selected, str):
            self._theme_controller.set_mode(ThemeMode(selected))
        self.accept()
