"""Dialogue ``GlobalSettingsDialog`` — gestion des clés API et de l'apparence."""

from __future__ import annotations

from typing import Final

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from fahmi2.app.secrets_service import SecretsService
from fahmi2.app.theme_controller import ThemeController
from fahmi2.ui._components import frenchify_button_box
from fahmi2.ui.theme import ThemeMode

#: Libellés FR des modes d'apparence (affichés dans la combo « Thème »).
_THEME_MODE_LABELS: Final[dict[ThemeMode, str]] = {
    ThemeMode.SYSTEM: "Système",
    ThemeMode.LIGHT: "Clair",
    ThemeMode.DARK: "Sombre",
}


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
        self.setWindowTitle("Paramètres globaux")
        self._secrets_service = secrets_service
        self._theme_controller = theme_controller

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self._openai_input = QLineEdit(self)
        self._openai_input.setEchoMode(QLineEdit.EchoMode.Password)
        existing_openai = secrets_service.get_openai_api_key()
        if existing_openai:
            self._openai_input.setText(existing_openai)
        form.addRow("Clé OpenAI :", self._openai_input)

        self._deepseek_input = QLineEdit(self)
        self._deepseek_input.setEchoMode(QLineEdit.EchoMode.Password)
        existing_deepseek = secrets_service.get_deepseek_api_key()
        if existing_deepseek:
            self._deepseek_input.setText(existing_deepseek)
        form.addRow("Clé DeepSeek :", self._deepseek_input)

        self._theme_combo = QComboBox(self)
        for mode, label in _THEME_MODE_LABELS.items():
            # On stocke la valeur (str) du membre StrEnum : ``QComboBox`` ne
            # préserve pas le type de l'enum, et on reconverti à la lecture
            # via ``ThemeMode(combo.currentData())`` (cohérent avec les autres
            # combos d'enum de l'app, cf. ``ui/_model_labels.labeled_enum_combo``).
            self._theme_combo.addItem(label, mode.value)
        current_idx = self._theme_combo.findData(theme_controller.mode.value)
        if current_idx >= 0:
            self._theme_combo.setCurrentIndex(current_idx)
        form.addRow("Thème :", self._theme_combo)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        frenchify_button_box(buttons)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

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
