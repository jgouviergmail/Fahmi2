"""Dialogue ``GlobalSettingsDialog`` — gestion des clés API et préférences."""

from __future__ import annotations

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


class GlobalSettingsDialog(QDialog):
    """Dialogue de configuration globale (clés API, thème)."""

    def __init__(
        self,
        secrets_service: SecretsService,
        parent: QWidget | None = None,
    ) -> None:
        """Construit le dialogue.

        Args:
            secrets_service: Service de gestion des clés.
            parent: Parent Qt optionnel.
        """
        super().__init__(parent)
        self.setWindowTitle("Paramètres globaux")
        self._secrets_service = secrets_service

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
        for label in ("system", "light", "dark"):
            self._theme_combo.addItem(label)
        form.addRow("Thème :", self._theme_combo)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_accept(self) -> None:
        """Persiste les clés saisies et clôt le dialogue."""
        openai_key = self._openai_input.text().strip()
        deepseek_key = self._deepseek_input.text().strip()
        if openai_key:
            self._secrets_service.set_openai_api_key(openai_key)
        if deepseek_key:
            self._secrets_service.set_deepseek_api_key(deepseek_key)
        self.accept()
