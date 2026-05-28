"""Dialogue ``GlobalSettingsDialog`` — clés API + apparence + langue.

Présenté en trois cartes :

- *Clés API* : OpenAI et DeepSeek (saisies masquées, stockage DPAPI Windows).
- *Apparence* : combo de sélection du thème (Système / Clair / Sombre),
  câblée à un :class:`~fahmi2.app.theme_controller.ThemeController` qui
  applique le thème immédiatement et persiste la préférence.
- *Langue* : combo de sélection de la langue d'interface (Français /
  English), câblée à un :class:`~fahmi2.app.language_controller.LanguageController`
  qui persiste la préférence ; un message d'information indique qu'un
  redémarrage est nécessaire pour appliquer le changement à toute l'UI.

i18n : tous les libellés passent par :py:meth:`QObject.tr` à l'usage dans
les méthodes ``_build_*`` (rendu dans la langue active à la construction).
"""

from __future__ import annotations

from typing import Final

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from fahmi2.app.language_controller import LanguageController
from fahmi2.app.secrets_service import SecretsService
from fahmi2.app.theme_controller import ThemeController
from fahmi2.i18n import LANGUAGE_LABELS, AppLanguage
from fahmi2.ui._components import card, field_hint, localize_button_box, settings_form
from fahmi2.ui.theme import ThemeMode

#: Largeur minimale du dialogue (px).
_DIALOG_MIN_WIDTH: Final[int] = 560
#: Marges externes du dialogue.
_OUTER_MARGIN_HORIZONTAL: Final[int] = 28
_OUTER_MARGIN_TOP: Final[int] = 24
_OUTER_MARGIN_BOTTOM: Final[int] = 18
_OUTER_SPACING: Final[int] = 16
#: Largeur min/max de la colonne centrale.
_COLUMN_MIN_WIDTH: Final[int] = 460
_COLUMN_MAX_WIDTH: Final[int] = 560


class GlobalSettingsDialog(QDialog):
    """Dialogue de configuration globale (clés API, apparence, langue)."""

    def __init__(
        self,
        secrets_service: SecretsService,
        *,
        theme_controller: ThemeController,
        language_controller: LanguageController,
        parent: QWidget | None = None,
    ) -> None:
        """Construit le dialogue.

        Args:
            secrets_service: Service de gestion des clés API (DPAPI).
            theme_controller: Contrôleur du thème (apparence) — l'apparence
                choisie est appliquée et persistée à la validation.
            language_controller: Contrôleur de la langue d'interface — la
                langue choisie est persistée à la validation (effective au
                prochain démarrage).
            parent: Parent Qt optionnel.
        """
        super().__init__(parent)
        self.setWindowTitle(self.tr("Paramètres globaux"))
        self.setMinimumWidth(_DIALOG_MIN_WIDTH)
        self._secrets_service = secrets_service
        self._theme_controller = theme_controller
        self._language_controller = language_controller

        keys_card = self._build_keys_card()
        appearance_card = self._build_appearance_card()
        language_card = self._build_language_card()
        column = self._build_centered_column(
            keys_card, appearance_card, language_card
        )
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

    def _theme_mode_labels(self) -> dict[ThemeMode, str]:
        """Mapping ``ThemeMode`` → libellé traduit (utilisé dans la combo).

        Construit à l'usage (et non comme constante de module) pour suivre
        la langue active au moment où la combo est peuplée.
        """
        return {
            ThemeMode.SYSTEM: self.tr("Système"),
            ThemeMode.LIGHT: self.tr("Clair"),
            ThemeMode.DARK: self.tr("Sombre"),
        }

    def _build_keys_card(self) -> QWidget:
        """Construit la carte « Clés API » (OpenAI + DeepSeek, masquées).

        Returns:
            Le widget de carte (avec ses deux champs prêts à être lus).
        """
        keys_card, keys_layout = card(
            self,
            title=self.tr("Clés API"),
            description=self.tr(
                "Les clés sont chiffrées localement (Windows DPAPI) et ne quittent jamais "
                "votre ordinateur en clair."
            ),
        )
        keys_form = settings_form()
        self._openai_input = QLineEdit(keys_card)
        self._openai_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._openai_input.setToolTip(
            self.tr(
                "Clé personnelle OpenAI utilisée pour la transcription en ligne et la "
                "recherche sémantique du Dialogue."
            )
        )
        existing_openai = self._secrets_service.get_openai_api_key()
        if existing_openai:
            self._openai_input.setText(existing_openai)
        keys_form.addRow(self.tr("Clé API OpenAI"), self._openai_input)

        self._deepseek_input = QLineEdit(keys_card)
        self._deepseek_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._deepseek_input.setToolTip(
            self.tr(
                "Clé personnelle DeepSeek utilisée pour la reformulation, les supports "
                "pédagogiques et les réponses du Dialogue."
            )
        )
        existing_deepseek = self._secrets_service.get_deepseek_api_key()
        if existing_deepseek:
            self._deepseek_input.setText(existing_deepseek)
        keys_form.addRow(self.tr("Clé API DeepSeek"), self._deepseek_input)
        keys_layout.addLayout(keys_form)
        return keys_card

    def _build_appearance_card(self) -> QWidget:
        """Construit la carte « Apparence » (combo de thème + hint).

        Returns:
            Le widget de carte (combo prêt à être lu à la validation).
        """
        appearance_card, appearance_layout = card(
            self,
            title=self.tr("Apparence"),
            description=self.tr(
                "Choisissez un mode clair, sombre, ou laissez Fahmi2 suivre le thème "
                "de votre système (Windows)."
            ),
        )
        appearance_form = settings_form()
        self._theme_combo = QComboBox(appearance_card)
        self._theme_combo.setToolTip(
            self.tr(
                "« Système » suit automatiquement le thème de Windows. « Clair » ou "
                "« Sombre » force l'apparence indépendamment du système."
            )
        )
        for mode, label in self._theme_mode_labels().items():
            # ``QComboBox`` ne préserve pas le type ``StrEnum`` : on stocke
            # ``mode.value`` et on reconverti à la lecture via ``ThemeMode(...)``.
            self._theme_combo.addItem(label, mode.value)
        current_idx = self._theme_combo.findData(self._theme_controller.mode.value)
        if current_idx >= 0:
            self._theme_combo.setCurrentIndex(current_idx)
        appearance_form.addRow(self.tr("Thème de l'interface"), self._theme_combo)
        appearance_layout.addLayout(appearance_form)
        appearance_layout.addWidget(
            field_hint(
                appearance_card,
                self.tr(
                    "Le changement s'applique immédiatement à toute l'application."
                ),
            )
        )
        return appearance_card

    def _build_language_card(self) -> QWidget:
        """Construit la carte « Langue » (combo de langue + hint redémarrage).

        Returns:
            Le widget de carte (combo prêt à être lu à la validation).
        """
        language_card, language_layout = card(
            self,
            title=self.tr("Langue"),
            description=self.tr(
                "Choisissez la langue de l'interface. Le changement s'applique au "
                "prochain démarrage de Fahmi2."
            ),
        )
        language_form = settings_form()
        self._language_combo = QComboBox(language_card)
        self._language_combo.setToolTip(
            self.tr(
                "Sélectionne la langue d'affichage des menus, boutons et libellés. "
                "N'affecte ni le contenu des projets, ni les langues de sortie du "
                "pipeline (qui se règlent par projet)."
            )
        )
        for lang, label in LANGUAGE_LABELS.items():
            # Les libellés des langues sont **dans la langue elle-même** par
            # convention universelle (« English », « Français »…) — pas
            # traduits par ``self.tr``.
            self._language_combo.addItem(label, lang.value)
        current_idx = self._language_combo.findData(
            self._language_controller.language.value
        )
        if current_idx >= 0:
            self._language_combo.setCurrentIndex(current_idx)
        language_form.addRow(self.tr("Langue de l'interface"), self._language_combo)
        language_layout.addLayout(language_form)
        language_layout.addWidget(
            field_hint(
                language_card,
                self.tr(
                    "Le changement de langue s'applique au prochain démarrage de Fahmi2."
                ),
            )
        )
        return language_card

    def _build_centered_column(self, *cards: QWidget) -> QWidget:
        """Englobe les cartes ``cards`` dans une colonne cadrée en largeur.

        Args:
            *cards: Cartes à empiler verticalement.

        Returns:
            Le widget colonne (à ajouter au layout externe).
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
        """Construit la barre de boutons « Enregistrer / Annuler »."""
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        localize_button_box(buttons)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        return buttons

    def _on_accept(self) -> None:
        """Persiste les clés saisies + l'apparence + la langue, et clôt le dialogue.

        Le changement de langue n'est appliqué qu'au prochain démarrage : si
        une nouvelle langue a effectivement été retenue, on en informe
        l'utilisateur via une ``QMessageBox`` avant de fermer le dialogue.
        """
        openai_key = self._openai_input.text().strip()
        deepseek_key = self._deepseek_input.text().strip()
        if openai_key:
            self._secrets_service.set_openai_api_key(openai_key)
        if deepseek_key:
            self._secrets_service.set_deepseek_api_key(deepseek_key)
        selected = self._theme_combo.currentData()
        if isinstance(selected, str):
            self._theme_controller.set_mode(ThemeMode(selected))
        selected_lang = self._language_combo.currentData()
        if isinstance(selected_lang, str):
            try:
                language = AppLanguage(selected_lang)
            except ValueError:
                language = self._language_controller.language
            if self._language_controller.set_language(language):
                # ``self.tr()`` rend le message dans la langue **actuellement
                # active** (avant redémarrage) — l'utilisateur comprend la
                # confirmation, et lit la nouvelle langue après relance.
                QMessageBox.information(
                    self,
                    self.tr("Redémarrage requis"),
                    self.tr(
                        "La langue de l'interface a été enregistrée. "
                        "Elle sera appliquée au prochain démarrage de Fahmi2."
                    ),
                )
        self.accept()
