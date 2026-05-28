"""Dialogue ``GenerationSettingsView`` — réglages de la génération.

Présenté en master-detail (composant
:class:`~fahmi2.ui.widgets.settings_view.SettingsView`) à six catégories,
chacune assemblée à partir des briques partagées
(:func:`~fahmi2.ui._components.card`, :func:`~fahmi2.ui._components.page_header`,
:func:`~fahmi2.ui._components.field_hint`).

- *Sources* : dossier d'entrée, vidéos YouTube, langues, ordre et exclusions.
- *Style* : préréglage de style, mode d'assemblage, consignes, traitement des
  documents texte.
- *Transcription* : moteur (local/en ligne), modèle, performance.
- *Génération IA* : modèle, budget, performance.
- *Phases IA* : réglages détaillés par phase LLM.
- *Export* : formats à exporter.

Produit un ``GenerationSettings`` (sans nom ni emplacement, qui relèvent du
``Project``). L'API publique et l'ensemble des attributs privés référencés
par les tests existants sont **strictement préservés** : seule la
présentation change.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
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
from fahmi2.app.input_sources import (
    collect_available_sources_from,
    reconcile_source_order,
)
from fahmi2.core.errors.exceptions import Fahmi2Error
from fahmi2.domain.enums import (
    CloudSttModel,
    ConsolidationMode,
    ExportFormat,
    Language,
    LLMModel,
    LocalSttModel,
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
from fahmi2.ui._components import (
    card,
    dialog_footer,
    field_hint,
    frenchify_button_box,
    page_header,
    settings_form,
    settings_page,
)
from fahmi2.ui._model_labels import (
    CLOUD_STT_MODEL_LABELS,
    LLM_MODEL_LABELS,
    LOCAL_STT_MODEL_LABELS,
    labeled_enum_combo,
)
from fahmi2.ui.pedagogy_labels import EXPORT_LABELS
from fahmi2.ui.widgets.language_selection_view import LanguageSelectionView
from fahmi2.ui.widgets.phase_configs_widget import PhaseConfigsWidget
from fahmi2.ui.widgets.settings_view import SettingsView
from fahmi2.ui.widgets.source_order_view import SourceOrderView

# ---------------------------------------------------------------- dimensions

_DIALOG_WIDTH: Final[int] = 920
_DIALOG_HEIGHT: Final[int] = 680
_DIRECTIVES_HEIGHT_PX: Final[int] = 90
_YOUTUBE_URLS_HEIGHT_PX: Final[int] = 80
_OUTER_MARGIN: Final[int] = 0
_OUTER_SPACING: Final[int] = 12

# ---------------------------------------------------------------- bornes
_COST_CEILING_MAX_USD: Final[float] = 10_000.0

# ---------------------------------------------------------------- titres / catégories

_TITLE_CREATE: Final[str] = "Configurer la génération"
_TITLE_EDIT: Final[str] = "Réglages de la génération"

_CAT_STYLE: Final[str] = "Style"
_CAT_SOURCES: Final[str] = "Sources"
_CAT_TRANSCRIPTION: Final[str] = "Transcription"
_CAT_GENERATION: Final[str] = "Génération IA"
_CAT_PHASES: Final[str] = "Phases IA"
_CAT_EXPORT: Final[str] = "Export"

# ---------------------------------------------------------------- mappings labels

#: Libellés FR du préréglage de style (StylePreset valeurs brutes → français).
_STYLE_PRESET_LABELS: Final[dict[StylePreset, str]] = {
    StylePreset.DECONTRACTE: "Décontracté",
    StylePreset.STANDARD: "Standard",
    StylePreset.PROFESSIONNEL: "Professionnel",
    StylePreset.ACADEMIQUE: "Académique",
}
#: Libellés FR du mode d'assemblage du document consolidé.
_CONSOLIDATION_MODE_LABELS: Final[dict[ConsolidationMode, str]] = {
    ConsolidationMode.ORDERED: "Conserver l'ordre — 1 source = 1 chapitre",
    ConsolidationMode.THEMATIC: "Synthèse thématique — refonte transversale",
}
#: Libellés FR du moteur de transcription.
_STT_PROVIDER_LABELS: Final[dict[SttProvider, str]] = {
    SttProvider.FASTER_WHISPER_LOCAL: "Hors ligne (GPU local, gratuit)",
    SttProvider.OPENAI_CLOUD: "En ligne (OpenAI, payant)",
}

# ---------------------------------------------------------------- libellés de page

_STYLE_PAGE_DESC: Final[str] = (
    "Ton, mise en forme et mode d'assemblage du document consolidé."
)
_SOURCES_PAGE_DESC: Final[str] = (
    "Dossier des fichiers à traiter, vidéos YouTube, langues à produire et ordre "
    "d'apparition des sources dans le document."
)
_TRANSCRIPTION_PAGE_DESC: Final[str] = (
    "Moteur et modèle utilisés pour transcrire les vidéos et fichiers audio."
)
_GENERATION_PAGE_DESC: Final[str] = (
    "Modèle de génération, plafond de budget et nombre de traitements en parallèle."
)
_PHASES_PAGE_DESC: Final[str] = (
    "Réglages fins pour chacune des 7 phases IA du pipeline (thinking, intensité, "
    "température, retries). Laissez les valeurs par défaut sauf cas particulier."
)
_EXPORT_PAGE_DESC: Final[str] = (
    "Formats proposés lors de l'export du document consolidé et du glossaire."
)

# ---------------------------------------------------------------- libellés de carte

_FORMAT_CARD_TITLE: Final[str] = "Mise en forme"
_FORMAT_CARD_DESC: Final[str] = (
    "Préréglage de style, mode d'assemblage des sources et consignes libres pour "
    "orienter l'écriture."
)
_DOCUMENTS_CARD_TITLE: Final[str] = "Documents texte"
_DOCUMENTS_CARD_DESC: Final[str] = (
    "Comportement appliqué aux fichiers PDF, Word, Markdown et texte."
)
_FOLDER_CARD_TITLE: Final[str] = "Dossier des sources"
_FOLDER_CARD_DESC: Final[str] = (
    "Dossier scanné pour les vidéos, audios et documents à traiter."
)
_YOUTUBE_CARD_TITLE: Final[str] = "Vidéos YouTube"
_YOUTUBE_CARD_DESC: Final[str] = (
    "Liens YouTube unitaires (une URL par ligne). La vidéo est téléchargée puis "
    "transcrite comme une vidéo locale."
)
_LANGUAGES_CARD_TITLE: Final[str] = "Langues du document"
_LANGUAGES_CARD_DESC: Final[str] = (
    "Langues à produire pour le document consolidé. La langue « principale » est "
    "l'originale ; les autres en sont des traductions automatiques."
)
_ORDER_CARD_TITLE: Final[str] = "Ordre et exclusions"
_ORDER_CARD_DESC: Final[str] = (
    "Ordre d'apparition des sources dans le document, et exclusions éventuelles."
)
_ENGINE_CARD_TITLE: Final[str] = "Moteur de transcription"
_ENGINE_CARD_DESC: Final[str] = (
    "Mode hors ligne (GPU local, sans coût) ou en ligne (OpenAI, plus précis sur "
    "les longues durées)."
)
_STT_MODEL_CARD_TITLE: Final[str] = "Modèle de transcription"
_STT_MODEL_CARD_DESC: Final[str] = (
    "Choix du modèle ; un seul est actif à la fois, selon le moteur choisi."
)
_STT_PERFORMANCE_CARD_TITLE: Final[str] = "Performance et conservation"
_STT_PERFORMANCE_CARD_DESC: Final[str] = (
    "Parallélisme des transcriptions en ligne et gestion des fichiers audio extraits."
)
_LLM_CARD_TITLE: Final[str] = "Modèle de génération"
_LLM_CARD_DESC: Final[str] = (
    "Modèle DeepSeek utilisé pour les phases de reformulation, structuration, "
    "consolidation, traduction et cohérence."
)
_BUDGET_CARD_TITLE: Final[str] = "Budget"
_BUDGET_CARD_DESC: Final[str] = (
    "Plafond de dépense — la génération s'arrête si le coût l'atteint."
)
_PERFORMANCE_CARD_TITLE: Final[str] = "Performance"
_PERFORMANCE_CARD_DESC: Final[str] = (
    "Nombre d'appels IA simultanés. Plus rapide, n'augmente pas le coût."
)
_PHASES_CARD_TITLE: Final[str] = "Réglages par phase IA"
_PHASES_CARD_DESC: Final[str] = (
    "Pour chaque phase IA, mode raisonnement, intensité, température et tentatives."
)
_EXPORT_CARD_TITLE: Final[str] = "Formats à exporter"

# ---------------------------------------------------------------- étiquettes de champ

_STYLE_LABEL: Final[str] = "Préréglage de style"
_CONSOLIDATION_LABEL: Final[str] = "Mode d'assemblage"
_DIRECTIVES_LABEL: Final[str] = "Consignes de style"
_FOLDER_LABEL: Final[str] = "Dossier"
_BROWSE_LABEL: Final[str] = "Choisir…"
_STT_PROVIDER_LABEL: Final[str] = "Moteur"
_STT_LOCAL_LABEL: Final[str] = "Modèle hors ligne (GPU)"
_STT_CLOUD_LABEL: Final[str] = "Modèle en ligne (OpenAI)"
_STT_WORKERS_LABEL: Final[str] = "Transcriptions simultanées"
_LLM_LABEL: Final[str] = "Modèle"
_BUDGET_FIELD_LABEL: Final[str] = "Budget maximal"
_LLM_WORKERS_LABEL: Final[str] = "Traitements IA simultanés"

# ---------------------------------------------------------------- tooltips

_FOLDER_TOOLTIP: Final[str] = (
    "Dossier scanné en mode automatique : tous les fichiers vidéo, audio et "
    "documents (PDF, Word, Markdown, texte) y sont ramassés."
)
_BROWSE_TOOLTIP: Final[str] = "Choisir le dossier contenant les sources à traiter."
_DIRECTIVES_PLACEHOLDER: Final[str] = (
    "Consignes libres pour orienter la reformulation. Ex. : « ton chaleureux mais "
    "rigoureux, exemples concrets, éviter le jargon inutile »."
)
_YOUTUBE_URLS_PLACEHOLDER: Final[str] = (
    "Une vidéo YouTube par ligne (liens unitaires).\nEx. : https://youtu.be/XXXXXXXXXXX"
)
_KEEP_AUDIO_LABEL: Final[str] = "Conserver les fichiers audio (réécoute / dépannage)"
_KEEP_AUDIO_TOOLTIP: Final[str] = (
    "Si coché, les fichiers .wav extraits des médias (vidéo/audio/YouTube) ne sont "
    "pas supprimés après la transcription."
)
_REFORMULATE_DOCS_LABEL: Final[str] = "Reformuler les documents (PDF, Word, Markdown, texte)"
_REFORMULATE_DOCS_TOOLTIP: Final[str] = (
    "Si coché (défaut), les documents texte passent par la reformulation comme une "
    "transcription orale. Décoché : le texte est inséré tel quel (cours déjà bien rédigé)."
)
_CONSOLIDATION_MODE_TOOLTIP: Final[str] = (
    "Conserver l'ordre : assemble les sources dans l'ordre choisi (contenu recopié "
    "tel quel). Synthèse thématique : l'IA refond tout par thème (l'ordre n'a "
    "alors plus d'effet)."
)
_STYLE_TOOLTIP: Final[str] = (
    "Détermine le ton et le registre du document final (décontracté, standard, "
    "professionnel ou académique)."
)
_STT_PROVIDER_TOOLTIP: Final[str] = (
    "Mode hors ligne : GPU NVIDIA requis, sans coût. Mode en ligne : OpenAI, "
    "facturé à la minute, recommandé pour les longues durées."
)
_STT_WORKERS_TOOLTIP: Final[str] = (
    "Transcriptions cloud simultanées (sans effet en STT local : 1 GPU)."
)
_LLM_WORKERS_TOOLTIP: Final[str] = (
    "Appels IA simultanés (le compte concurrence DeepSeek est élevé)."
)
_BUDGET_TOOLTIP: Final[str] = (
    "Coût maximal en USD. La génération s'arrête si elle s'en approche. Mettez 0 "
    "pour désactiver le plafond."
)
_GPU_REQUIRED_TITLE: Final[str] = "GPU NVIDIA introuvable"
_GPU_REQUIRED_MESSAGE: Final[str] = (
    "Le mode de transcription locale nécessite un GPU NVIDIA compatible CUDA.\n\n"
    "Veuillez utiliser le mode OpenAI en ligne."
)
_VALIDATION_TITLE: Final[str] = "Dossier des sources manquant"
_VALIDATION_MESSAGE: Final[str] = (
    "Veuillez sélectionner le dossier des sources (vidéos, audios, documents)."
)
_BUDGET_SUFFIX: Final[str] = " $"
_BUDGET_SPECIAL_VALUE: Final[str] = "Pas de plafond"


class GenerationSettingsView(QDialog):
    """Dialogue d'édition des réglages de génération (master-detail, cartes)."""

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
        self.resize(_DIALOG_WIDTH, _DIALOG_HEIGHT)
        self._result: GenerationSettings | None = None

        self._build_fields()
        settings_view = SettingsView(
            [
                (_CAT_STYLE, self._build_style_page()),
                (_CAT_SOURCES, self._build_sources_page()),
                (_CAT_TRANSCRIPTION, self._build_transcription_page()),
                (_CAT_GENERATION, self._build_generation_page()),
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
        frenchify_button_box(buttons)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(
            _OUTER_MARGIN, _OUTER_MARGIN, _OUTER_MARGIN, _OUTER_MARGIN
        )
        outer.setSpacing(0)
        outer.addWidget(settings_view, stretch=1)
        # Footer dédié (séparateur top + padding), pas de boutons collés au bord.
        outer.addWidget(dialog_footer(self, buttons))

        # Active la poignée de redimensionnement explicite (par sécurité).
        self.setSizeGripEnabled(True)

        if initial is not None:
            self._populate(initial)
        self._sync_stt_model_enabled()
        self._sync_order_irrelevant()

    def get_generation_settings(self) -> GenerationSettings | None:
        """Retourne les réglages construits, ou ``None`` si annulation/invalide.

        Returns:
            ``GenerationSettings`` ou ``None``.
        """
        return self._result

    # ------------------------------------------------------------------ champs

    def _build_fields(self) -> None:
        """Instancie tous les widgets de champ (avant répartition en pages).

        Décomposé en sous-méthodes par groupe sémantique pour rester lisible.
        """
        self._build_source_fields()
        self._build_style_fields()
        self._build_stt_fields()
        self._build_llm_fields()
        self._build_export_fields()

    def _build_source_fields(self) -> None:
        """Instancie les widgets de saisie des sources (dossier + URLs + ordre)."""
        self._input_folder_input = QLineEdit(self)
        self._input_folder_input.setReadOnly(True)
        self._input_folder_input.setToolTip(_FOLDER_TOOLTIP)
        self._browse_btn = QPushButton(_BROWSE_LABEL, self)
        self._browse_btn.setToolTip(_BROWSE_TOOLTIP)
        self._browse_btn.clicked.connect(self._browse_input_folder)

        self._youtube_urls_input = QTextEdit(self)
        self._youtube_urls_input.setPlaceholderText(_YOUTUBE_URLS_PLACEHOLDER)
        self._youtube_urls_input.setFixedHeight(_YOUTUBE_URLS_HEIGHT_PX)
        self._youtube_urls_input.setAcceptRichText(False)

        self._source_order_view = SourceOrderView(self)
        self._source_order_view.refresh_requested.connect(self._refresh_source_order)

        self._languages_view = LanguageSelectionView(tuple(Language), self)

    def _build_style_fields(self) -> None:
        """Instancie les widgets de la page « Style » (preset, mode, directives)."""
        self._style_combo = QComboBox(self)
        self._style_combo.setToolTip(_STYLE_TOOLTIP)
        for style, label in _STYLE_PRESET_LABELS.items():
            self._style_combo.addItem(label, style)

        self._consolidation_mode_combo = labeled_enum_combo(
            self, _CONSOLIDATION_MODE_LABELS
        )
        self._consolidation_mode_combo.setToolTip(_CONSOLIDATION_MODE_TOOLTIP)
        self._consolidation_mode_combo.currentIndexChanged.connect(
            self._sync_order_irrelevant
        )

        self._style_directives_input = QTextEdit(self)
        self._style_directives_input.setPlaceholderText(_DIRECTIVES_PLACEHOLDER)
        self._style_directives_input.setFixedHeight(_DIRECTIVES_HEIGHT_PX)
        self._style_directives_input.setAcceptRichText(False)

        self._reformulate_documents_checkbox = QCheckBox(_REFORMULATE_DOCS_LABEL, self)
        self._reformulate_documents_checkbox.setToolTip(_REFORMULATE_DOCS_TOOLTIP)
        self._reformulate_documents_checkbox.setChecked(True)

    def _build_stt_fields(self) -> None:
        """Instancie les widgets de la page « Transcription »."""
        self._stt_combo = QComboBox(self)
        self._stt_combo.setToolTip(_STT_PROVIDER_TOOLTIP)
        for provider, label in _STT_PROVIDER_LABELS.items():
            self._stt_combo.addItem(label, provider)
        self._stt_combo.currentIndexChanged.connect(self._on_stt_changed)

        self._stt_local_model_combo = labeled_enum_combo(self, LOCAL_STT_MODEL_LABELS)
        self._stt_cloud_model_combo = labeled_enum_combo(self, CLOUD_STT_MODEL_LABELS)

        self._keep_audio_checkbox = QCheckBox(_KEEP_AUDIO_LABEL, self)
        self._keep_audio_checkbox.setToolTip(_KEEP_AUDIO_TOOLTIP)

        defaults = ParallelismConfig()
        self._stt_workers_input = QSpinBox(self)
        self._stt_workers_input.setRange(1, MAX_STT_CLOUD_WORKERS)
        self._stt_workers_input.setValue(defaults.stt_cloud_workers)
        self._stt_workers_input.setToolTip(_STT_WORKERS_TOOLTIP)

    def _build_llm_fields(self) -> None:
        """Instancie les widgets de la page « Génération IA » + « Phases IA »."""
        self._llm_combo = labeled_enum_combo(self, LLM_MODEL_LABELS)

        self._cost_ceiling_input = QDoubleSpinBox(self)
        self._cost_ceiling_input.setRange(0.0, _COST_CEILING_MAX_USD)
        self._cost_ceiling_input.setDecimals(2)
        self._cost_ceiling_input.setValue(0.0)
        self._cost_ceiling_input.setSuffix(_BUDGET_SUFFIX)
        self._cost_ceiling_input.setSpecialValueText(_BUDGET_SPECIAL_VALUE)
        self._cost_ceiling_input.setToolTip(_BUDGET_TOOLTIP)

        self._phase_configs_widget = PhaseConfigsWidget(self)

        defaults = ParallelismConfig()
        self._llm_workers_input = QSpinBox(self)
        self._llm_workers_input.setRange(1, MAX_LLM_WORKERS)
        self._llm_workers_input.setValue(defaults.llm_workers)
        self._llm_workers_input.setToolTip(_LLM_WORKERS_TOOLTIP)

    def _build_export_fields(self) -> None:
        """Instancie les cases à cocher de formats d'export."""
        self._export_checks: dict[ExportFormat, QCheckBox] = {}
        for fmt in ExportFormat:
            if fmt in GENERATION_EXPORT_FORMATS:
                self._export_checks[fmt] = QCheckBox(EXPORT_LABELS[fmt], self)

    # ------------------------------------------------------------------- pages

    def _build_style_page(self) -> QWidget:
        """Construit la page « Style »."""
        page, layout = settings_page(self)
        layout.addWidget(page_header(page, title=_CAT_STYLE, description=_STYLE_PAGE_DESC))

        format_card, format_layout = card(
            page, title=_FORMAT_CARD_TITLE, description=_FORMAT_CARD_DESC
        )
        form = settings_form()
        form.addRow(_STYLE_LABEL, self._style_combo)
        form.addRow(_CONSOLIDATION_LABEL, self._consolidation_mode_combo)
        format_layout.addLayout(form)
        # Étiquette du textarea (label normal, pas un hint visuel sous-cadré).
        directives_label = QLabel(_DIRECTIVES_LABEL, format_card)
        format_layout.addWidget(directives_label)
        format_layout.addWidget(self._style_directives_input)
        format_layout.addWidget(
            field_hint(
                format_card,
                "Optionnel — laissez vide pour le comportement par défaut.",
            )
        )
        layout.addWidget(format_card)

        docs_card, docs_layout = card(
            page, title=_DOCUMENTS_CARD_TITLE, description=_DOCUMENTS_CARD_DESC
        )
        docs_layout.addWidget(self._reformulate_documents_checkbox)
        docs_layout.addWidget(
            field_hint(
                docs_card,
                "Décochez pour les cours déjà rédigés (insertion telle quelle, coût nul).",
            )
        )
        layout.addWidget(docs_card)

        layout.addStretch(1)
        return page

    def _build_sources_page(self) -> QWidget:
        """Construit la page « Sources » (dossier, YouTube, langues, ordre)."""
        page, layout = settings_page(self)
        layout.addWidget(
            page_header(page, title=_CAT_SOURCES, description=_SOURCES_PAGE_DESC)
        )

        folder_card, folder_layout = card(
            page, title=_FOLDER_CARD_TITLE, description=_FOLDER_CARD_DESC
        )
        folder_row = QHBoxLayout()
        folder_row.addWidget(self._input_folder_input, stretch=1)
        folder_row.addWidget(self._browse_btn)
        folder_layout.addLayout(folder_row)
        layout.addWidget(folder_card)

        youtube_card, youtube_layout = card(
            page, title=_YOUTUBE_CARD_TITLE, description=_YOUTUBE_CARD_DESC
        )
        youtube_layout.addWidget(self._youtube_urls_input)
        layout.addWidget(youtube_card)

        languages_card, languages_layout = card(
            page, title=_LANGUAGES_CARD_TITLE, description=_LANGUAGES_CARD_DESC
        )
        languages_layout.addWidget(self._languages_view)
        layout.addWidget(languages_card)

        order_card, order_layout = card(
            page, title=_ORDER_CARD_TITLE, description=_ORDER_CARD_DESC
        )
        order_layout.addWidget(self._source_order_view)
        layout.addWidget(order_card, stretch=1)
        return page

    def _build_transcription_page(self) -> QWidget:
        """Construit la page « Transcription »."""
        page, layout = settings_page(self)
        layout.addWidget(
            page_header(
                page, title=_CAT_TRANSCRIPTION, description=_TRANSCRIPTION_PAGE_DESC
            )
        )

        engine_card, engine_layout = card(
            page, title=_ENGINE_CARD_TITLE, description=_ENGINE_CARD_DESC
        )
        engine_form = settings_form()
        engine_form.addRow(_STT_PROVIDER_LABEL, self._stt_combo)
        engine_layout.addLayout(engine_form)
        layout.addWidget(engine_card)

        model_card, model_layout = card(
            page, title=_STT_MODEL_CARD_TITLE, description=_STT_MODEL_CARD_DESC
        )
        model_form = settings_form()
        model_form.addRow(_STT_LOCAL_LABEL, self._stt_local_model_combo)
        model_form.addRow(_STT_CLOUD_LABEL, self._stt_cloud_model_combo)
        model_layout.addLayout(model_form)
        layout.addWidget(model_card)

        perf_card, perf_layout = card(
            page,
            title=_STT_PERFORMANCE_CARD_TITLE,
            description=_STT_PERFORMANCE_CARD_DESC,
        )
        perf_form = settings_form()
        perf_form.addRow(_STT_WORKERS_LABEL, self._stt_workers_input)
        perf_layout.addLayout(perf_form)
        perf_layout.addWidget(self._keep_audio_checkbox)
        layout.addWidget(perf_card)

        layout.addStretch(1)
        return page

    def _build_generation_page(self) -> QWidget:
        """Construit la page « Génération IA » (modèle + budget + performance)."""
        page, layout = settings_page(self)
        layout.addWidget(
            page_header(
                page, title=_CAT_GENERATION, description=_GENERATION_PAGE_DESC
            )
        )
        model_card, model_layout = card(
            page, title=_LLM_CARD_TITLE, description=_LLM_CARD_DESC
        )
        model_form = settings_form()
        model_form.addRow(_LLM_LABEL, self._llm_combo)
        model_layout.addLayout(model_form)
        layout.addWidget(model_card)

        budget_card, budget_layout = card(
            page, title=_BUDGET_CARD_TITLE, description=_BUDGET_CARD_DESC
        )
        budget_form = settings_form()
        budget_form.addRow(_BUDGET_FIELD_LABEL, self._cost_ceiling_input)
        budget_layout.addLayout(budget_form)
        layout.addWidget(budget_card)

        perf_card, perf_layout = card(
            page, title=_PERFORMANCE_CARD_TITLE, description=_PERFORMANCE_CARD_DESC
        )
        perf_form = settings_form()
        perf_form.addRow(_LLM_WORKERS_LABEL, self._llm_workers_input)
        perf_layout.addLayout(perf_form)
        layout.addWidget(perf_card)

        layout.addStretch(1)
        return page

    def _build_phases_page(self) -> QWidget:
        """Construit la page « Phases IA » (page_header + widget directement).

        ``PhaseConfigsWidget`` est déjà un ``QGroupBox`` stylé (encadré + titre
        interne) ; on évite la double-tête en n'ajoutant pas de carte autour.
        Le titre interne du QGroupBox est remplacé par une description
        compacte sous le ``page_header``.
        """
        page, layout = settings_page(self)
        layout.addWidget(
            page_header(page, title=_CAT_PHASES, description=_PHASES_PAGE_DESC)
        )
        # On efface le titre interne du QGroupBox pour éviter la redondance.
        self._phase_configs_widget.setTitle("")
        layout.addWidget(self._phase_configs_widget, stretch=1)
        return page

    def _build_export_page(self) -> QWidget:
        """Construit la page « Export »."""
        page, layout = settings_page(self)
        layout.addWidget(
            page_header(page, title=_CAT_EXPORT, description=_EXPORT_PAGE_DESC)
        )
        card_frame, card_layout = card(page, title=_EXPORT_CARD_TITLE)
        for cb in self._export_checks.values():
            card_layout.addWidget(cb)
        layout.addWidget(card_frame)
        layout.addWidget(
            field_hint(
                page,
                "Sans sélection, l'export laissera le choix au moment de l'action.",
            )
        )
        layout.addStretch(1)
        return page

    # ----------------------------------------------------------------- actions

    def _browse_input_folder(self) -> None:
        """Ouvre un sélecteur de dossier d'entrée et rafraîchit la liste."""
        folder = QFileDialog.getExistingDirectory(self, _FOLDER_CARD_TITLE)
        if folder:
            self._input_folder_input.setText(folder)
            self._refresh_source_order()

    def _parse_youtube_urls(self) -> tuple[str, ...]:
        """Extrait les liens YouTube saisis (une URL non vide par ligne, dédupliquée).

        Returns:
            Les URLs non vides, sans doublon, dans l'ordre de saisie
            (``dict.fromkeys`` préserve l'ordre d'insertion).
        """
        lines = (
            line.strip()
            for line in self._youtube_urls_input.toPlainText().splitlines()
        )
        return tuple(dict.fromkeys(line for line in lines if line))

    def _scan_available(self) -> list[InputSource]:
        """Liste les sources disponibles depuis les champs courants (best-effort).

        Returns:
            Les ``InputSource`` du dossier + URLs ; liste vide si le dossier est
            inaccessible et qu'aucune URL n'est saisie.
        """
        folder_text = self._input_folder_input.text().strip()
        folder = Path(folder_text) if folder_text else None
        try:
            return collect_available_sources_from(folder, self._parse_youtube_urls())
        except Fahmi2Error:
            return []

    def _refresh_source_order(
        self,
        source_order: tuple[str, ...] | None = None,
        excluded: tuple[str, ...] | None = None,
    ) -> None:
        """Re-scanne les sources, réconcilie l'ordre/exclusion et repeuple la liste.

        Args:
            source_order: État d'ordre à appliquer (``None`` = état courant).
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
        available = self._scan_available()
        available_keys = [source.order_key() for source in available]
        included, excluded_keys = reconcile_source_order(available_keys, order, excl)
        self._source_order_view.populate(
            available,
            included=included,
            excluded=excluded_keys,
            known=set(order) | set(excl),
        )

    def _on_stt_changed(self, index: int) -> None:
        """Bloque ``faster_whisper_local`` sans GPU CUDA.

        Args:
            index: Index sélectionné dans le combo STT.
        """
        # ``itemData`` peut « dégrader » le StrEnum en str : on recoerce en enum
        # pour que la comparaison d'identité (et l'avertissement GPU) fonctionne.
        provider = SttProvider(self._stt_combo.itemData(index))
        if (
            provider is SttProvider.FASTER_WHISPER_LOCAL
            and not self._hardware.cuda_available
        ):
            QMessageBox.warning(self, _GPU_REQUIRED_TITLE, _GPU_REQUIRED_MESSAGE)
            cloud_index = self._stt_combo.findData(SttProvider.OPENAI_CLOUD)
            if cloud_index >= 0:
                self._stt_combo.setCurrentIndex(cloud_index)
        self._sync_stt_model_enabled()

    def _sync_stt_model_enabled(self) -> None:
        """Active le combo modèle correspondant au provider STT sélectionné."""
        provider = SttProvider(self._stt_combo.currentData())
        self._stt_local_model_combo.setEnabled(
            provider is SttProvider.FASTER_WHISPER_LOCAL
        )
        self._stt_cloud_model_combo.setEnabled(provider is SttProvider.OPENAI_CLOUD)

    def _sync_order_irrelevant(self) -> None:
        """Signale (note UI) que l'ordre des sources est ignoré en mode thématique."""
        mode = ConsolidationMode(self._consolidation_mode_combo.currentData())
        self._source_order_view.set_order_irrelevant(
            mode is ConsolidationMode.THEMATIC
        )

    def _populate(self, generation: GenerationSettings) -> None:
        """Pré-remplit les champs depuis des réglages existants.

        Args:
            generation: Réglages à éditer.
        """
        self._input_folder_input.setText(str(generation.input_folder))
        self._youtube_urls_input.setPlainText("\n".join(generation.youtube_urls))
        self._languages_view.set_selection(
            primary=generation.source_language, outputs=generation.output_languages
        )
        style_idx = self._style_combo.findData(generation.style_preset)
        if style_idx >= 0:
            self._style_combo.setCurrentIndex(style_idx)
        mode_idx = self._consolidation_mode_combo.findData(
            generation.consolidation_mode
        )
        if mode_idx >= 0:
            self._consolidation_mode_combo.setCurrentIndex(mode_idx)
        self._style_directives_input.setPlainText(generation.style_directives)
        self._reformulate_documents_checkbox.setChecked(generation.reformulate_documents)
        stt_idx = self._stt_combo.findData(generation.stt_provider)
        if stt_idx >= 0:
            self._stt_combo.setCurrentIndex(stt_idx)
        local_model_idx = self._stt_local_model_combo.findData(generation.stt_local_model)
        if local_model_idx >= 0:
            self._stt_local_model_combo.setCurrentIndex(local_model_idx)
        cloud_model_idx = self._stt_cloud_model_combo.findData(generation.stt_cloud_model)
        if cloud_model_idx >= 0:
            self._stt_cloud_model_combo.setCurrentIndex(cloud_model_idx)
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
            QMessageBox.warning(self, _VALIDATION_TITLE, _VALIDATION_MESSAGE)
            return
        # Le widget garantit l'invariant du domaine : la principale ∈ langues incluses.
        source_lang = self._languages_view.primary_language()
        output_langs = self._languages_view.output_languages()
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
            style_preset=StylePreset(self._style_combo.currentData()),
            consolidation_mode=ConsolidationMode(
                self._consolidation_mode_combo.currentData()
            ),
            style_directives=self._style_directives_input.toPlainText().strip(),
            stt_provider=SttProvider(self._stt_combo.currentData()),
            stt_local_model=LocalSttModel(self._stt_local_model_combo.currentData()),
            stt_cloud_model=CloudSttModel(self._stt_cloud_model_combo.currentData()),
            llm_model=LLMModel(self._llm_combo.currentData()),
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
