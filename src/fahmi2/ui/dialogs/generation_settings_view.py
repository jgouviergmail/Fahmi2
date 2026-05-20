"""Dialogue ``GenerationSettingsView`` — réglages de génération (master-detail).

Réorganise les réglages de la fonctionnalité Génération en catégories (Entrée &
langues, Style, Transcription, Modèle & coût, Phases) via le composant
``SettingsView``. Produit un ``GenerationSettings`` (sans nom ni emplacement, qui
relèvent du ``Project``).
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from fahmi2.app.hardware_probe import HardwareInfo
from fahmi2.domain.enums import Language, LLMModel, SttProvider, StylePreset
from fahmi2.domain.generation import GenerationSettings, ParallelismConfig
from fahmi2.ui.widgets.phase_configs_widget import PhaseConfigsWidget
from fahmi2.ui.widgets.settings_view import SettingsView

_DIALOG_WIDTH_PX = 760
_DIALOG_HEIGHT_PX = 620
_DIRECTIVES_HEIGHT_PX = 90
_COST_CEILING_MAX_USD = 10_000.0

_TITLE_CREATE = "Configurer la génération"
_TITLE_EDIT = "Réglages de la génération"

_CAT_INPUT = "Entrée & langues"
_CAT_STYLE = "Style"
_CAT_STT = "Transcription"
_CAT_MODEL = "Modèle & coût"
_CAT_PHASES = "Phases (1–7)"

_DIRECTIVES_PLACEHOLDER = (
    "Directives libres pour orienter la reformulation. Ex : « ton chaleureux mais "
    "rigoureux, exemples concrets, éviter le jargon inutile »."
)


class GenerationSettingsView(QDialog):
    """Dialogue d'édition des réglages de génération (master-detail)."""

    def __init__(
        self,
        hardware: HardwareInfo,
        parent: QWidget | None = None,
        *,
        initial: GenerationSettings | None = None,
    ) -> None:
        """Construit le dialogue.

        Args:
            hardware: Info matérielle (pour bloquer STT local sans GPU CUDA).
            parent: Parent Qt optionnel.
            initial: Réglages pré-remplis (mode édition) ou ``None`` (création).
        """
        super().__init__(parent)
        self._hardware = hardware
        self._is_edit_mode = initial is not None
        self.setWindowTitle(_TITLE_EDIT if self._is_edit_mode else _TITLE_CREATE)
        self.resize(_DIALOG_WIDTH_PX, _DIALOG_HEIGHT_PX)
        self._result: GenerationSettings | None = None

        self._build_fields()
        settings_view = SettingsView(
            [
                (_CAT_INPUT, self._build_input_page()),
                (_CAT_STYLE, self._build_style_page()),
                (_CAT_STT, self._build_stt_page()),
                (_CAT_MODEL, self._build_model_page()),
                (_CAT_PHASES, self._build_phases_page()),
            ],
            self,
        )

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
        outer.addWidget(settings_view, stretch=1)
        outer.addWidget(buttons)

        if initial is not None:
            self._populate(initial)

    def get_generation_settings(self) -> GenerationSettings | None:
        """Retourne les réglages construits, ou ``None`` si annulation/invalide.

        Returns:
            ``GenerationSettings`` ou ``None``.
        """
        return self._result

    # ------------------------------------------------------------------ champs

    def _build_fields(self) -> None:
        """Instancie tous les widgets de champ (avant répartition en pages)."""
        self._input_folder_input = QLineEdit(self)
        self._input_folder_input.setReadOnly(True)
        self._browse_btn = QPushButton("Parcourir…", self)
        self._browse_btn.clicked.connect(self._browse_input_folder)

        self._source_lang_combo = QComboBox(self)
        for lang in Language:
            self._source_lang_combo.addItem(lang.value, lang)

        self._output_langs: dict[Language, QCheckBox] = {}
        for lang in Language:
            cb = QCheckBox(lang.value, self)
            cb.setChecked(lang is Language.FR)
            self._output_langs[lang] = cb

        self._style_combo = QComboBox(self)
        for style in StylePreset:
            self._style_combo.addItem(style.value, style)

        self._style_directives_input = QTextEdit(self)
        self._style_directives_input.setPlaceholderText(_DIRECTIVES_PLACEHOLDER)
        self._style_directives_input.setFixedHeight(_DIRECTIVES_HEIGHT_PX)
        self._style_directives_input.setAcceptRichText(False)

        self._stt_combo = QComboBox(self)
        for provider in SttProvider:
            self._stt_combo.addItem(provider.value, provider)
        self._stt_combo.currentIndexChanged.connect(self._on_stt_changed)

        self._llm_combo = QComboBox(self)
        for model in LLMModel:
            self._llm_combo.addItem(model.value, model)

        self._cost_ceiling_input = QDoubleSpinBox(self)
        self._cost_ceiling_input.setRange(0.0, _COST_CEILING_MAX_USD)
        self._cost_ceiling_input.setDecimals(2)
        self._cost_ceiling_input.setValue(0.0)
        self._cost_ceiling_input.setSuffix(" $")
        self._cost_ceiling_input.setSpecialValueText("Pas de plafond")

        self._phase_configs_widget = PhaseConfigsWidget(self)

    # ------------------------------------------------------------------- pages

    def _build_input_page(self) -> QWidget:
        """Construit la page « Entrée & langues ».

        Returns:
            Le widget de page.
        """
        page = QWidget(self)
        form = QFormLayout(page)
        folder_row = QHBoxLayout()
        folder_row.addWidget(self._input_folder_input)
        folder_row.addWidget(self._browse_btn)
        form.addRow("Dossier des vidéos :", folder_row)
        form.addRow("Langue source :", self._source_lang_combo)
        langs_row = QHBoxLayout()
        for cb in self._output_langs.values():
            langs_row.addWidget(cb)
        langs_row.addStretch(1)
        form.addRow("Langues de sortie :", langs_row)
        return page

    def _build_style_page(self) -> QWidget:
        """Construit la page « Style ».

        Returns:
            Le widget de page.
        """
        page = QWidget(self)
        form = QFormLayout(page)
        form.addRow("Style :", self._style_combo)
        form.addRow("Directives stylistiques :", self._style_directives_input)
        return page

    def _build_stt_page(self) -> QWidget:
        """Construit la page « Transcription ».

        Returns:
            Le widget de page.
        """
        page = QWidget(self)
        form = QFormLayout(page)
        form.addRow("Provider STT :", self._stt_combo)
        return page

    def _build_model_page(self) -> QWidget:
        """Construit la page « Modèle & coût ».

        Returns:
            Le widget de page.
        """
        page = QWidget(self)
        form = QFormLayout(page)
        form.addRow("Modèle LLM :", self._llm_combo)
        form.addRow("Plafond budget :", self._cost_ceiling_input)
        return page

    def _build_phases_page(self) -> QWidget:
        """Construit la page « Phases (1–7) ».

        Returns:
            Le widget de page.
        """
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.addWidget(self._phase_configs_widget)
        return page

    # ----------------------------------------------------------------- actions

    def _browse_input_folder(self) -> None:
        """Ouvre un sélecteur de dossier des vidéos."""
        folder = QFileDialog.getExistingDirectory(self, "Dossier des vidéos")
        if folder:
            self._input_folder_input.setText(folder)

    def _on_stt_changed(self, index: int) -> None:
        """Bloque ``faster_whisper_local`` sans GPU CUDA.

        Args:
            index: Index sélectionné dans le combo STT.
        """
        provider = self._stt_combo.itemData(index)
        if (
            provider is SttProvider.FASTER_WHISPER_LOCAL
            and not self._hardware.cuda_available
        ):
            QMessageBox.warning(
                self,
                "GPU NVIDIA introuvable",
                "Le mode de transcription locale nécessite un GPU NVIDIA "
                "compatible CUDA.\n\nVeuillez utiliser le mode OpenAI cloud.",
            )
            cloud_index = self._stt_combo.findData(SttProvider.OPENAI_CLOUD)
            if cloud_index >= 0:
                self._stt_combo.setCurrentIndex(cloud_index)

    def _populate(self, generation: GenerationSettings) -> None:
        """Pré-remplit les champs depuis des réglages existants.

        Args:
            generation: Réglages à éditer.
        """
        self._input_folder_input.setText(str(generation.input_folder))
        src_idx = self._source_lang_combo.findData(generation.source_language)
        if src_idx >= 0:
            self._source_lang_combo.setCurrentIndex(src_idx)
        for lang, cb in self._output_langs.items():
            cb.setChecked(lang in generation.output_languages)
        style_idx = self._style_combo.findData(generation.style_preset)
        if style_idx >= 0:
            self._style_combo.setCurrentIndex(style_idx)
        self._style_directives_input.setPlainText(generation.style_directives)
        stt_idx = self._stt_combo.findData(generation.stt_provider)
        if stt_idx >= 0:
            self._stt_combo.setCurrentIndex(stt_idx)
        llm_idx = self._llm_combo.findData(generation.llm_model)
        if llm_idx >= 0:
            self._llm_combo.setCurrentIndex(llm_idx)
        self._cost_ceiling_input.setValue(generation.cost_ceiling_usd or 0.0)
        self._phase_configs_widget.set_phase_configs(generation.phases_config)

    def _on_accept(self) -> None:
        """Valide la saisie et construit le ``GenerationSettings``."""
        input_folder_text = self._input_folder_input.text().strip()
        if not input_folder_text:
            QMessageBox.warning(
                self,
                "Dossier des vidéos manquant",
                "Veuillez sélectionner le dossier contenant les vidéos.",
            )
            return
        source_lang: Language = self._source_lang_combo.currentData()
        output_langs = tuple(
            lang for lang, cb in self._output_langs.items() if cb.isChecked()
        )
        if source_lang not in output_langs:
            output_langs = (source_lang, *output_langs)
        cost_ceiling = (
            self._cost_ceiling_input.value()
            if self._cost_ceiling_input.value() > 0
            else None
        )
        self._result = GenerationSettings(
            input_folder=Path(input_folder_text),
            source_language=source_lang,
            output_languages=output_langs,
            style_preset=self._style_combo.currentData(),
            style_directives=self._style_directives_input.toPlainText().strip(),
            stt_provider=self._stt_combo.currentData(),
            llm_model=self._llm_combo.currentData(),
            phases_config=self._phase_configs_widget.get_phase_configs(),
            cost_ceiling_usd=cost_ceiling,
            parallelism=ParallelismConfig(),
            delete_audio_after_stt=True,
        )
        self.accept()
