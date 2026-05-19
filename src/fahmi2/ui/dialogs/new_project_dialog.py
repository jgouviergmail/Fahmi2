"""Dialogue ``NewProjectDialog`` — création d'un projet.

Assistant 1-page pour saisir : nom, dossier d'entrée, langues, style,
directives stylistiques (multi-ligne), providers, modèle LLM, plafond
budget, et configuration détaillée des 7 phases LLM.
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
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from fahmi2.app.hardware_probe import HardwareInfo
from fahmi2.domain.enums import (
    Language,
    LLMModel,
    SttProvider,
    StylePreset,
)
from fahmi2.domain.project import ParallelismConfig, ProjectSettings
from fahmi2.ui.widgets.phase_configs_widget import PhaseConfigsWidget

_DEFAULT_DIRECTIVES_HEIGHT_PX = 90
_DIALOG_INITIAL_HEIGHT_PX = 700
_DIALOG_INITIAL_WIDTH_PX = 720


class NewProjectDialog(QDialog):
    """Assistant 1-page pour créer un Projet."""

    def __init__(  # noqa: PLR0915
        self,
        hardware: HardwareInfo,
        parent: QWidget | None = None,
    ) -> None:
        """Construit le dialogue.

        Args:
            hardware: Info matérielle (pour bloquer STT local si pas CUDA).
            parent: Parent Qt optionnel.
        """
        super().__init__(parent)
        self.setWindowTitle("Nouveau projet")
        self.resize(_DIALOG_INITIAL_WIDTH_PX, _DIALOG_INITIAL_HEIGHT_PX)
        self._hardware = hardware
        self._result_settings: ProjectSettings | None = None

        outer_layout = QVBoxLayout(self)

        # Zone scrollable pour le formulaire (gère les petits écrans)
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll_content = QWidget(scroll)
        scroll.setWidget(scroll_content)
        outer_layout.addWidget(scroll, stretch=1)

        form = QFormLayout(scroll_content)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        self._name_input = QLineEdit(self)
        form.addRow("Nom :", self._name_input)

        self._input_folder_input = QLineEdit(self)
        self._input_folder_input.setReadOnly(True)
        browse_btn = QPushButton("Parcourir…", self)
        browse_btn.clicked.connect(self._browse_input_folder)
        folder_row = QHBoxLayout()
        folder_row.addWidget(self._input_folder_input)
        folder_row.addWidget(browse_btn)
        form.addRow("Dossier d'entrée :", folder_row)

        self._source_lang_combo = QComboBox(self)
        for lang in Language:
            self._source_lang_combo.addItem(lang.value, lang)
        form.addRow("Langue source :", self._source_lang_combo)

        self._output_langs: dict[Language, QCheckBox] = {}
        langs_row = QHBoxLayout()
        for lang in Language:
            cb = QCheckBox(lang.value, self)
            cb.setChecked(lang is Language.FR)
            self._output_langs[lang] = cb
            langs_row.addWidget(cb)
        langs_row.addStretch(1)
        form.addRow("Langues de sortie :", langs_row)

        self._style_combo = QComboBox(self)
        for style in StylePreset:
            self._style_combo.addItem(style.value, style)
        form.addRow("Style :", self._style_combo)

        # Champ multi-ligne pour les directives stylistiques (saisie confortable)
        self._style_directives_input = QTextEdit(self)
        self._style_directives_input.setPlaceholderText(
            "Directives libres pour orienter la reformulation. Ex : « ton "
            "chaleureux mais rigoureux, exemples concrets, éviter le jargon "
            "inutile, conserver la voix professorale »."
        )
        self._style_directives_input.setFixedHeight(_DEFAULT_DIRECTIVES_HEIGHT_PX)
        self._style_directives_input.setAcceptRichText(False)
        form.addRow("Directives stylistiques :", self._style_directives_input)

        self._stt_combo = QComboBox(self)
        for provider in SttProvider:
            self._stt_combo.addItem(provider.value, provider)
        self._stt_combo.currentIndexChanged.connect(self._on_stt_changed)
        form.addRow("Provider STT :", self._stt_combo)

        self._llm_combo = QComboBox(self)
        for model in LLMModel:
            self._llm_combo.addItem(model.value, model)
        form.addRow("Modèle LLM :", self._llm_combo)

        self._cost_ceiling_input = QDoubleSpinBox(self)
        self._cost_ceiling_input.setRange(0.0, 10_000.0)
        self._cost_ceiling_input.setDecimals(2)
        self._cost_ceiling_input.setValue(0.0)
        self._cost_ceiling_input.setSuffix(" $")
        self._cost_ceiling_input.setSpecialValueText("Pas de plafond")
        form.addRow("Plafond budget :", self._cost_ceiling_input)

        # Config détaillée par phase
        self._phase_configs_widget = PhaseConfigsWidget(self)
        form.addRow(self._phase_configs_widget)

        # Boutons OK / Annuler (hors zone scrollable)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        outer_layout.addWidget(buttons)

    def get_settings(self) -> ProjectSettings | None:
        """Retourne les settings construits, ou ``None`` si annulation.

        Returns:
            ``ProjectSettings`` ou ``None``.
        """
        return self._result_settings

    def _browse_input_folder(self) -> None:
        """Ouvre un sélecteur de dossier d'entrée."""
        folder = QFileDialog.getExistingDirectory(self, "Dossier d'entrée")
        if folder:
            self._input_folder_input.setText(folder)

    def _on_stt_changed(self, index: int) -> None:
        """Bloque la sélection ``faster_whisper_local`` sans GPU.

        Args:
            index: Index du combo.
        """
        provider = self._stt_combo.itemData(index)
        if provider is SttProvider.FASTER_WHISPER_LOCAL and not self._hardware.cuda_available:
            QMessageBox.warning(
                self,
                "GPU NVIDIA introuvable",
                "Le mode de transcription locale nécessite un GPU NVIDIA "
                "compatible CUDA.\n\nVeuillez utiliser le mode OpenAI cloud.",
            )
            cloud_index = self._stt_combo.findData(SttProvider.OPENAI_CLOUD)
            if cloud_index >= 0:
                self._stt_combo.setCurrentIndex(cloud_index)

    def _on_accept(self) -> None:
        """Construit les settings depuis les widgets et clôt le dialogue."""
        name = self._name_input.text().strip()
        input_folder_text = self._input_folder_input.text().strip()
        if not name or not input_folder_text:
            QMessageBox.warning(
                self,
                "Champs manquants",
                "Veuillez renseigner le nom et le dossier d'entrée.",
            )
            return
        source_lang = self._source_lang_combo.currentData()
        output_langs = tuple(
            lang for lang, cb in self._output_langs.items() if cb.isChecked()
        )
        if source_lang not in output_langs:
            output_langs = (source_lang, *output_langs)
        style = self._style_combo.currentData()
        stt_provider = self._stt_combo.currentData()
        llm_model = self._llm_combo.currentData()
        cost_ceiling = (
            self._cost_ceiling_input.value()
            if self._cost_ceiling_input.value() > 0
            else None
        )
        directives = self._style_directives_input.toPlainText().strip()

        self._result_settings = ProjectSettings(
            name=name,
            input_folder=Path(input_folder_text),
            workspace_folder=Path(input_folder_text) / ".fahmi2",
            source_language=source_lang,
            output_languages=output_langs,
            style_preset=style,
            style_directives=directives,
            stt_provider=stt_provider,
            llm_model=llm_model,
            phases_config=self._phase_configs_widget.get_phase_configs(),
            cost_ceiling_usd=cost_ceiling,
            parallelism=ParallelismConfig(),
            delete_audio_after_stt=True,
        )
        self.accept()
