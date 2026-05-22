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
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from fahmi2.app.hardware_probe import HardwareInfo
from fahmi2.app.input_sources import collect_available_sources_from
from fahmi2.core.errors.exceptions import Fahmi2Error
from fahmi2.domain.enums import (
    ExportFormat,
    Language,
    LLMModel,
    SttProvider,
    StylePreset,
)
from fahmi2.domain.generation import (
    GENERATION_EXPORT_FORMATS,
    MAX_LLM_WORKERS,
    MAX_STT_CLOUD_WORKERS,
    GenerationSettings,
    ParallelismConfig,
)
from fahmi2.domain.source import InputSource
from fahmi2.ui.pedagogy_labels import EXPORT_LABELS
from fahmi2.ui.widgets.phase_configs_widget import PhaseConfigsWidget
from fahmi2.ui.widgets.settings_view import SettingsView
from fahmi2.ui.widgets.source_order_view import SourceOrderView

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
_CAT_PHASES = "Phases"
_CAT_EXPORT = "Export"
_EXPORT_HINT = (
    "Formats proposés lors de l'export des livrables de la génération (le bouton "
    "« Exporter » liste les formats cochés). Sans sélection, l'export invite à en "
    "choisir ici."
)
_EXPORT_FORMATS_LABEL = "Formats d'export :"

_DIRECTIVES_PLACEHOLDER = (
    "Directives libres pour orienter la reformulation. Ex : « ton chaleureux mais "
    "rigoureux, exemples concrets, éviter le jargon inutile »."
)

_KEEP_AUDIO_LABEL = "Conserver les fichiers audio extraits"
_KEEP_AUDIO_TOOLTIP = (
    "Si coché, les fichiers .wav extraits des vidéos ne sont pas supprimés "
    "après la transcription (utile pour réécouter / déboguer)."
)

_REFORMULATE_DOCS_LABEL = "Reformuler les documents texte"
_REFORMULATE_DOCS_TOOLTIP = (
    "Si coché (défaut), les documents (PDF, Word, Markdown, texte) passent par "
    "la reformulation comme une transcription orale. Décoché : le texte est "
    "inséré tel quel (utile pour un cours déjà bien rédigé)."
)

_FOLDER_LABEL = "Dossier d'entrée :"
_YOUTUBE_URLS_LABEL = "Liens YouTube :"
_YOUTUBE_URLS_HEIGHT_PX = 70
_YOUTUBE_URLS_PLACEHOLDER = (
    "Un lien YouTube par ligne (vidéos unitaires).\n"
    "Ex : https://youtu.be/XXXXXXXXXXX"
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
                (_CAT_EXPORT, self._build_export_page()),
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

        self._build_source_fields()

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

        self._keep_audio_checkbox = QCheckBox(_KEEP_AUDIO_LABEL, self)
        self._keep_audio_checkbox.setToolTip(_KEEP_AUDIO_TOOLTIP)

        self._reformulate_documents_checkbox = QCheckBox(_REFORMULATE_DOCS_LABEL, self)
        self._reformulate_documents_checkbox.setToolTip(_REFORMULATE_DOCS_TOOLTIP)
        self._reformulate_documents_checkbox.setChecked(True)

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

        defaults = ParallelismConfig()
        self._stt_workers_input = QSpinBox(self)
        self._stt_workers_input.setRange(1, MAX_STT_CLOUD_WORKERS)
        self._stt_workers_input.setValue(defaults.stt_cloud_workers)
        self._stt_workers_input.setToolTip(
            "Transcriptions cloud simultanées (sans effet en STT local : 1 GPU)."
        )
        self._llm_workers_input = QSpinBox(self)
        self._llm_workers_input.setRange(1, MAX_LLM_WORKERS)
        self._llm_workers_input.setValue(defaults.llm_workers)
        self._llm_workers_input.setToolTip(
            "Appels LLM simultanés (limite DeepSeek par concurrence, très haute)."
        )

        self._export_checks: dict[ExportFormat, QCheckBox] = {}
        for fmt in ExportFormat:
            if fmt in GENERATION_EXPORT_FORMATS:
                self._export_checks[fmt] = QCheckBox(EXPORT_LABELS[fmt], self)

    def _build_source_fields(self) -> None:
        """Instancie les widgets de saisie des sources (URLs + ordre/exclusion)."""
        self._youtube_urls_input = QTextEdit(self)
        self._youtube_urls_input.setPlaceholderText(_YOUTUBE_URLS_PLACEHOLDER)
        self._youtube_urls_input.setFixedHeight(_YOUTUBE_URLS_HEIGHT_PX)
        self._youtube_urls_input.setAcceptRichText(False)

        self._source_order_view = SourceOrderView(self)
        self._source_order_view.refresh_requested.connect(self._refresh_source_order)

    # ------------------------------------------------------------------- pages

    def _build_input_page(self) -> QWidget:
        """Construit la page « Entrée & langues ».

        Returns:
            Le widget de page.
        """
        page = QWidget(self)
        outer = QVBoxLayout(page)
        form = QFormLayout()
        folder_row = QHBoxLayout()
        folder_row.addWidget(self._input_folder_input)
        folder_row.addWidget(self._browse_btn)
        form.addRow(_FOLDER_LABEL, folder_row)
        form.addRow(_YOUTUBE_URLS_LABEL, self._youtube_urls_input)
        form.addRow(self._source_order_view)
        form.addRow("Langue source :", self._source_lang_combo)
        langs_row = QHBoxLayout()
        for cb in self._output_langs.values():
            langs_row.addWidget(cb)
        langs_row.addStretch(1)
        form.addRow("Langues de sortie :", langs_row)
        outer.addLayout(form)
        outer.addStretch(1)
        return page

    def _build_style_page(self) -> QWidget:
        """Construit la page « Style ».

        Returns:
            Le widget de page.
        """
        page = QWidget(self)
        outer = QVBoxLayout(page)
        form = QFormLayout()
        form.addRow("Style :", self._style_combo)
        form.addRow("Directives stylistiques :", self._style_directives_input)
        form.addRow(self._reformulate_documents_checkbox)
        outer.addLayout(form)
        outer.addStretch(1)
        return page

    def _build_stt_page(self) -> QWidget:
        """Construit la page « Transcription ».

        Returns:
            Le widget de page.
        """
        page = QWidget(self)
        outer = QVBoxLayout(page)
        form = QFormLayout()
        form.addRow("Provider STT :", self._stt_combo)
        form.addRow(self._keep_audio_checkbox)
        form.addRow("Transcriptions en parallèle :", self._stt_workers_input)
        outer.addLayout(form)
        outer.addStretch(1)
        return page

    def _build_model_page(self) -> QWidget:
        """Construit la page « Modèle & coût ».

        Returns:
            Le widget de page.
        """
        page = QWidget(self)
        outer = QVBoxLayout(page)
        form = QFormLayout()
        form.addRow("Modèle LLM :", self._llm_combo)
        form.addRow("Plafond budget :", self._cost_ceiling_input)
        form.addRow("Appels LLM en parallèle :", self._llm_workers_input)
        outer.addLayout(form)
        outer.addStretch(1)
        return page

    def _build_phases_page(self) -> QWidget:
        """Construit la page « Phases (1–7) ».

        Returns:
            Le widget de page.
        """
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.addWidget(self._phase_configs_widget)
        layout.addStretch(1)
        return page

    def _build_export_page(self) -> QWidget:
        """Construit la page « Export » (formats d'export proposés).

        Returns:
            Le widget de page.
        """
        page = QWidget(self)
        outer = QVBoxLayout(page)
        hint = QLabel(_EXPORT_HINT, page)
        hint.setWordWrap(True)
        outer.addWidget(hint)
        outer.addWidget(QLabel(_EXPORT_FORMATS_LABEL, page))
        for cb in self._export_checks.values():
            outer.addWidget(cb)
        outer.addStretch(1)
        return page

    # ----------------------------------------------------------------- actions

    def _browse_input_folder(self) -> None:
        """Ouvre un sélecteur de dossier d'entrée et rafraîchit la liste."""
        folder = QFileDialog.getExistingDirectory(self, "Dossier d'entrée")
        if folder:
            self._input_folder_input.setText(folder)
            self._refresh_source_order()

    def _parse_youtube_urls(self) -> tuple[str, ...]:
        """Extrait les liens YouTube saisis (une URL non vide par ligne)."""
        return tuple(
            line.strip()
            for line in self._youtube_urls_input.toPlainText().splitlines()
            if line.strip()
        )

    def _scan_available(self) -> list[InputSource]:
        """Liste les sources disponibles depuis les champs courants (best-effort).

        Returns:
            Les ``InputSource`` du dossier + URLs ; liste vide si le dossier est
            inaccessible et qu'aucune URL n'est saisie.
        """
        folder_text = self._input_folder_input.text().strip()
        urls = self._parse_youtube_urls()
        folder = Path(folder_text) if folder_text else Path("__inexistant__")
        try:
            return collect_available_sources_from(folder, urls)
        except Fahmi2Error:
            return []

    def _refresh_source_order(
        self,
        source_order: tuple[str, ...] | None = None,
        excluded: tuple[str, ...] | None = None,
    ) -> None:
        """Re-scanne les sources et repeuple la double liste.

        Args:
            source_order: État d'ordre à appliquer (``None`` = état courant du
                widget — utilisé par le bouton « Rafraîchir » qui conserve les
                exclusions).
            excluded: État d'exclusion à appliquer (``None`` = état courant).
        """
        order = (
            source_order
            if source_order is not None
            else self._source_order_view.source_order()
        )
        excl = (
            excluded
            if excluded is not None
            else self._source_order_view.excluded_sources()
        )
        self._source_order_view.populate(self._scan_available(), order, excl)

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
        self._youtube_urls_input.setPlainText("\n".join(generation.youtube_urls))
        src_idx = self._source_lang_combo.findData(generation.source_language)
        if src_idx >= 0:
            self._source_lang_combo.setCurrentIndex(src_idx)
        for lang, cb in self._output_langs.items():
            cb.setChecked(lang in generation.output_languages)
        style_idx = self._style_combo.findData(generation.style_preset)
        if style_idx >= 0:
            self._style_combo.setCurrentIndex(style_idx)
        self._style_directives_input.setPlainText(generation.style_directives)
        self._reformulate_documents_checkbox.setChecked(generation.reformulate_documents)
        stt_idx = self._stt_combo.findData(generation.stt_provider)
        if stt_idx >= 0:
            self._stt_combo.setCurrentIndex(stt_idx)
        self._keep_audio_checkbox.setChecked(not generation.delete_audio_after_stt)
        llm_idx = self._llm_combo.findData(generation.llm_model)
        if llm_idx >= 0:
            self._llm_combo.setCurrentIndex(llm_idx)
        self._cost_ceiling_input.setValue(generation.cost_ceiling_usd or 0.0)
        self._stt_workers_input.setValue(generation.parallelism.stt_cloud_workers)
        self._llm_workers_input.setValue(generation.parallelism.llm_workers)
        self._phase_configs_widget.set_phase_configs(generation.phases_config)
        for fmt, cb in self._export_checks.items():
            cb.setChecked(fmt in generation.export_formats)
        self._refresh_source_order(
            generation.source_order, generation.excluded_sources
        )

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
        export_formats = frozenset(
            fmt for fmt, cb in self._export_checks.items() if cb.isChecked()
        )
        youtube_urls = self._parse_youtube_urls()
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
            parallelism=ParallelismConfig(
                stt_cloud_workers=self._stt_workers_input.value(),
                llm_workers=self._llm_workers_input.value(),
            ),
            delete_audio_after_stt=not self._keep_audio_checkbox.isChecked(),
            export_formats=export_formats,
            reformulate_documents=self._reformulate_documents_checkbox.isChecked(),
            youtube_urls=youtube_urls,
            source_order=self._source_order_view.source_order(),
            excluded_sources=self._source_order_view.excluded_sources(),
        )
        self.accept()
