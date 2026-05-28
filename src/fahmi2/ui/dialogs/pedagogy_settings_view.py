"""Dialogue ``PedagogySettingsView`` — réglages des supports pédagogiques.

Présentation : master-detail (composant
:class:`~fahmi2.ui.widgets.settings_view.SettingsView`) à cinq catégories.

i18n : tous les libellés passent par :py:meth:`QObject.tr` à l'usage.
"""

from __future__ import annotations

from typing import Final

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QGridLayout,
    QMessageBox,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from fahmi2.domain.enums import (
    BloomObjective,
    ExportFormat,
    Language,
    LLMModel,
    ReasoningEffort,
    SupportDensity,
    SupportType,
    TargetAudience,
)
from fahmi2.domain.languages import language_display_label
from fahmi2.domain.pedagogy import (
    DEFAULT_PEDAGOGY_LLM_WORKERS,
    EVALUATIVE_SUPPORTS,
    MAX_PEDAGOGY_LLM_WORKERS,
    PedagogySettings,
)
from fahmi2.domain.phase import PhaseConfig
from fahmi2.pedagogy.labels import audience_label, bloom_label, density_label
from fahmi2.ui._components import (
    card,
    dialog_footer,
    field_hint,
    localize_button_box,
    page_header,
    section_label,
    settings_form,
    settings_page,
)
from fahmi2.ui._model_labels import (
    labeled_enum_combo,
    llm_model_labels,
    no_reasoning_label,
    reasoning_effort_labels,
)
from fahmi2.ui.pedagogy_labels import export_labels, support_labels
from fahmi2.ui.widgets.settings_view import SettingsView

_DIALOG_WIDTH: Final[int] = 880
_DIALOG_HEIGHT: Final[int] = 640
_DIRECTIVES_HEIGHT_PX: Final[int] = 90
_OUTER_MARGIN: Final[int] = 0
_COST_CEILING_MAX_USD: Final[float] = 10_000.0
_TEMPERATURE_MIN: Final[float] = 0.0
_TEMPERATURE_MAX: Final[float] = 2.0
_TEMPERATURE_STEP: Final[float] = 0.1
_DEFAULT_TEMPERATURE: Final[float] = 0.3


class PedagogySettingsView(QDialog):
    """Dialogue d'édition des réglages pédagogie (master-detail, cartes)."""

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        available_languages: tuple[Language, ...],
        initial: PedagogySettings | None = None,
    ) -> None:
        """Construit le dialogue."""
        super().__init__(parent)
        self._is_edit_mode = initial is not None
        self.setWindowTitle(
            self.tr("Réglages des supports pédagogiques") if self._is_edit_mode
            else self.tr("Configurer les supports pédagogiques")
        )
        self.resize(_DIALOG_WIDTH, _DIALOG_HEIGHT)
        self._available_languages = available_languages
        self._result: PedagogySettings | None = None

        self._build_fields()
        settings_view = SettingsView(
            [
                (self.tr("Supports"), self._build_supports_page()),
                (self.tr("Difficulté"), self._build_difficulty_page()),
                (self.tr("Langues"), self._build_languages_page()),
                (self.tr("Génération IA"), self._build_generation_page()),
                (self.tr("Export"), self._build_export_page()),
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
        localize_button_box(buttons)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(
            _OUTER_MARGIN, _OUTER_MARGIN, _OUTER_MARGIN, _OUTER_MARGIN
        )
        outer.setSpacing(0)
        outer.addWidget(settings_view, stretch=1)
        outer.addWidget(dialog_footer(self, buttons))

        self.setSizeGripEnabled(True)

        if initial is not None:
            self._populate(initial)

    def get_pedagogy_settings(self) -> PedagogySettings | None:
        """Retourne les réglages validés (après accept), ou ``None``."""
        return self._result

    def build_settings(self) -> PedagogySettings | None:
        """Construit les réglages depuis les champs (``None`` si invalide)."""
        selected = frozenset(
            support
            for support, cb in self._support_checks.items()
            if cb.isChecked()
        )
        separate = frozenset(
            support
            for support, cb in self._separate_checks.items()
            if support in selected and cb.isChecked()
        )
        languages = tuple(
            lang for lang, cb in self._language_checks.items() if cb.isChecked()
        )
        export_formats = frozenset(
            fmt for fmt, cb in self._export_checks.items() if cb.isChecked()
        )
        ceiling = (
            self._cost_ceiling_input.value()
            if self._cost_ceiling_input.value() > 0
            else None
        )
        reasoning_raw = self._reasoning_combo.currentData()
        reasoning_effort = (
            ReasoningEffort(reasoning_raw) if reasoning_raw is not None else None
        )
        try:
            return PedagogySettings(
                selected_supports=selected,
                separate_correction=separate,
                target_audience=TargetAudience(self._audience_combo.currentData()),
                bloom_objective=BloomObjective(self._bloom_combo.currentData()),
                pedagogy_directives=self._directives_input.toPlainText().strip(),
                languages=languages,
                density=SupportDensity(self._density_combo.currentData()),
                llm_model=LLMModel(self._llm_combo.currentData()),
                llm_config=PhaseConfig(
                    thinking_enabled=self._thinking_check.isChecked(),
                    reasoning_effort=reasoning_effort,
                    temperature=self._temperature_input.value(),
                ),
                cost_ceiling_usd=ceiling,
                export_formats=export_formats,
                llm_workers=self._workers_input.value(),
            )
        except ValueError:
            return None

    def select_support(self, support: SupportType, *, selected: bool) -> None:
        """Coche/décoche un support (helper de test/UI)."""
        self._support_checks[support].setChecked(selected)

    def select_language(self, language: Language, *, selected: bool) -> None:
        """Coche/décoche une langue (helper de test/UI)."""
        if language in self._language_checks:
            self._language_checks[language].setChecked(selected)

    def _build_fields(self) -> None:
        """Instancie tous les widgets de champ."""
        self._support_checks: dict[SupportType, QCheckBox] = {}
        self._separate_checks: dict[SupportType, QCheckBox] = {}
        sep_tooltip = self.tr(
            "Si coché, le corrigé est généré dans un document distinct du sujet "
            "(utile pour les examens blancs)."
        )
        support_lbls = support_labels()
        for support in SupportType:
            self._support_checks[support] = QCheckBox(support_lbls[support], self)
            if support in EVALUATIVE_SUPPORTS:
                self._separate_checks[support] = QCheckBox("", self)
                self._separate_checks[support].setToolTip(sep_tooltip)

        self._audience_combo = QComboBox(self)
        self._audience_combo.setToolTip(
            self.tr(
                "Niveau d'études supposé du lecteur. Le ton et le vocabulaire s'adaptent."
            )
        )
        for audience in TargetAudience:
            self._audience_combo.addItem(audience_label(audience), audience)
        self._bloom_combo = QComboBox(self)
        self._bloom_combo.setToolTip(
            self.tr(
                "Niveau de la taxonomie de Bloom : comprendre, appliquer, analyser, etc."
            )
        )
        for bloom in BloomObjective:
            self._bloom_combo.addItem(bloom_label(bloom), bloom)
        self._density_combo = QComboBox(self)
        self._density_combo.setToolTip(
            self.tr("Volume final des supports (compact, équilibré, dense).")
        )
        for density in SupportDensity:
            self._density_combo.addItem(density_label(density), density)
        self._directives_input = QTextEdit(self)
        self._directives_input.setPlaceholderText(
            self.tr(
                "Consignes libres pour l'IA. Ex. : « privilégier des exemples concrets, "
                "éviter les pièges trop subtils, varier les formulations »."
            )
        )
        self._directives_input.setFixedHeight(_DIRECTIVES_HEIGHT_PX)
        self._directives_input.setAcceptRichText(False)

        self._language_checks: dict[Language, QCheckBox] = {}
        for lang in self._available_languages:
            self._language_checks[lang] = QCheckBox(language_display_label(lang), self)

        self._llm_combo = labeled_enum_combo(self, llm_model_labels())
        self._thinking_check = QCheckBox(
            self.tr("Activer la réflexion approfondie"), self
        )
        self._reasoning_combo = QComboBox(self)
        self._reasoning_combo.addItem(no_reasoning_label(), None)
        for effort, label in reasoning_effort_labels().items():
            self._reasoning_combo.addItem(label, effort.value)
        self._thinking_check.toggled.connect(self._reasoning_combo.setEnabled)
        self._reasoning_combo.setEnabled(self._thinking_check.isChecked())
        self._temperature_input = QDoubleSpinBox(self)
        self._temperature_input.setRange(_TEMPERATURE_MIN, _TEMPERATURE_MAX)
        self._temperature_input.setSingleStep(_TEMPERATURE_STEP)
        self._temperature_input.setValue(_DEFAULT_TEMPERATURE)
        self._cost_ceiling_input = QDoubleSpinBox(self)
        self._cost_ceiling_input.setRange(0.0, _COST_CEILING_MAX_USD)
        self._cost_ceiling_input.setDecimals(2)
        self._cost_ceiling_input.setValue(0.0)
        self._cost_ceiling_input.setSuffix(" $")
        self._cost_ceiling_input.setSpecialValueText(self.tr("Pas de plafond"))
        self._cost_ceiling_input.setToolTip(
            self.tr(
                "Coût maximal en USD. La génération s'arrête si elle s'en approche. Mettez 0 "
                "pour désactiver le plafond."
            )
        )
        self._workers_input = QSpinBox(self)
        self._workers_input.setRange(1, MAX_PEDAGOGY_LLM_WORKERS)
        self._workers_input.setValue(DEFAULT_PEDAGOGY_LLM_WORKERS)
        self._workers_input.setToolTip(
            self.tr(
                "Nombre de générations IA exécutées en parallèle. Augmenter accélère sans "
                "changer le coût (DeepSeek facture au token, pas au temps)."
            )
        )
        self._export_checks: dict[ExportFormat, QCheckBox] = {}
        export_lbls = export_labels()
        for fmt in ExportFormat:
            self._export_checks[fmt] = QCheckBox(export_lbls[fmt], self)

    def _build_supports_page(self) -> QWidget:
        """Construit la page « Supports »."""
        page, layout = settings_page(self)
        layout.addWidget(
            page_header(
                page,
                title=self.tr("Supports"),
                description=self.tr(
                    "Sélectionnez les supports de révision à générer. Pour les supports "
                    "évaluatifs, cochez « Corrigé séparé » pour générer un sujet sans "
                    "réponses et un corrigé dans un document distinct."
                ),
            )
        )
        card_frame, card_layout = card(page, title=self.tr("Types de supports"))
        grid = QGridLayout()
        type_header = section_label(card_frame, self.tr("Type de support"))
        separate_header = section_label(card_frame, self.tr("Corrigé séparé"))
        separate_header.setToolTip(
            self.tr(
                "Si coché, le corrigé est généré dans un document distinct du sujet "
                "(utile pour les examens blancs)."
            )
        )
        grid.addWidget(type_header, 0, 0)
        grid.addWidget(separate_header, 0, 1)
        for row, support in enumerate(SupportType, start=1):
            grid.addWidget(self._support_checks[support], row, 0)
            if support in self._separate_checks:
                grid.addWidget(self._separate_checks[support], row, 1)
        grid.setColumnStretch(2, 1)
        card_layout.addLayout(grid)
        layout.addWidget(card_frame)
        layout.addStretch(1)
        return page

    def _build_difficulty_page(self) -> QWidget:
        """Construit la page « Difficulté »."""
        page, layout = settings_page(self)
        layout.addWidget(
            page_header(
                page,
                title=self.tr("Difficulté"),
                description=self.tr(
                    "Public visé, objectif pédagogique et quantité de contenu — orientent le ton, "
                    "la difficulté et le volume."
                ),
            )
        )
        audience_card, audience_layout = card(
            page,
            title=self.tr("Public et objectif"),
            description=self.tr(
                "À qui les supports sont-ils destinés, et quel niveau d'apprentissage visent-ils ?"
            ),
        )
        audience_form = settings_form()
        audience_form.addRow(self.tr("Public visé"), self._audience_combo)
        audience_form.addRow(self.tr("Objectif pédagogique (Bloom)"), self._bloom_combo)
        audience_layout.addLayout(audience_form)
        layout.addWidget(audience_card)

        density_card, density_layout = card(
            page,
            title=self.tr("Densité"),
            description=self.tr(
                "Volume des supports générés : compact pour réviser vite, dense pour creuser."
            ),
        )
        density_form = settings_form()
        density_form.addRow(self.tr("Quantité de contenu"), self._density_combo)
        density_layout.addLayout(density_form)
        layout.addWidget(density_card)

        directives_card, directives_layout = card(
            page,
            title=self.tr("Consignes pédagogiques"),
            description=self.tr(
                "Optionnel. Indiquez à l'IA toute orientation spécifique."
            ),
        )
        directives_layout.addWidget(self._directives_input)
        layout.addWidget(directives_card)

        layout.addStretch(1)
        return page

    def _build_languages_page(self) -> QWidget:
        """Construit la page « Langues »."""
        page, layout = settings_page(self)
        layout.addWidget(
            page_header(
                page,
                title=self.tr("Langues"),
                description=self.tr(
                    "Les supports sont rédigés dans les langues choisies, même si le document "
                    "source est dans une autre langue."
                ),
            )
        )
        card_frame, card_layout = card(page, title=self.tr("Langues à produire"))
        for cb in self._language_checks.values():
            card_layout.addWidget(cb)
        layout.addWidget(card_frame)
        layout.addStretch(1)
        return page

    def _build_generation_page(self) -> QWidget:
        """Construit la page « Génération IA »."""
        page, layout = settings_page(self)
        layout.addWidget(
            page_header(
                page,
                title=self.tr("Génération IA"),
                description=self.tr(
                    "Modèle de génération, intensité de réflexion, budget et performance."
                ),
            )
        )

        model_card, model_layout = card(
            page,
            title=self.tr("Modèle de génération"),
            description=self.tr(
                "Modèle DeepSeek utilisé pour rédiger les supports. « Pro » coûte plus mais "
                "donne des supports de meilleure qualité."
            ),
        )
        model_form = settings_form()
        model_form.addRow(self.tr("Modèle"), self._llm_combo)
        model_form.addRow(self.tr("Température"), self._temperature_input)
        model_layout.addLayout(model_form)
        layout.addWidget(model_card)

        thinking_card, thinking_layout = card(
            page,
            title=self.tr("Réflexion approfondie"),
            description=self.tr(
                "Active un raisonnement étendu avant la génération — meilleure qualité, "
                "coût plus élevé. Recommandé pour les examens blancs."
            ),
        )
        thinking_layout.addWidget(self._thinking_check)
        thinking_form = settings_form()
        thinking_form.addRow(self.tr("Intensité de réflexion"), self._reasoning_combo)
        thinking_layout.addLayout(thinking_form)
        layout.addWidget(thinking_card)

        budget_card, budget_layout = card(
            page,
            title=self.tr("Budget et performance"),
            description=self.tr(
                "Plafond de dépense (la génération s'arrête si le coût l'atteint) et nombre "
                "de tâches IA traitées en parallèle (plus rapide, n'augmente pas le coût)."
            ),
        )
        budget_form = settings_form()
        budget_form.addRow(self.tr("Budget maximal"), self._cost_ceiling_input)
        budget_form.addRow(self.tr("Traitements simultanés"), self._workers_input)
        budget_layout.addLayout(budget_form)
        layout.addWidget(budget_card)

        layout.addStretch(1)
        return page

    def _build_export_page(self) -> QWidget:
        """Construit la page « Export »."""
        page, layout = settings_page(self)
        layout.addWidget(
            page_header(
                page,
                title=self.tr("Export"),
                description=self.tr(
                    "Formats proposés lors de l'export depuis l'onglet « Supports pédagogiques »."
                ),
            )
        )
        card_frame, card_layout = card(page, title=self.tr("Formats à exporter"))
        for cb in self._export_checks.values():
            card_layout.addWidget(cb)
        layout.addWidget(card_frame)
        layout.addWidget(
            field_hint(
                page,
                self.tr(
                    "Sans sélection, l'export laissera le choix au moment de l'action."
                ),
            )
        )
        layout.addStretch(1)
        return page

    def _populate(self, pedagogy: PedagogySettings) -> None:
        """Pré-remplit les champs depuis des réglages existants."""
        for support, cb in self._support_checks.items():
            cb.setChecked(support in pedagogy.selected_supports)
        for support, cb in self._separate_checks.items():
            cb.setChecked(support in pedagogy.separate_correction)
        _select_combo(self._audience_combo, pedagogy.target_audience)
        _select_combo(self._bloom_combo, pedagogy.bloom_objective)
        _select_combo(self._density_combo, pedagogy.density)
        self._directives_input.setPlainText(pedagogy.pedagogy_directives)
        for lang, cb in self._language_checks.items():
            cb.setChecked(lang in pedagogy.languages)
        _select_combo(self._llm_combo, pedagogy.llm_model)
        self._thinking_check.setChecked(pedagogy.llm_config.thinking_enabled)
        effort = pedagogy.llm_config.reasoning_effort
        _select_combo(
            self._reasoning_combo,
            effort.value if effort is not None else None,
        )
        self._temperature_input.setValue(pedagogy.llm_config.temperature)
        self._cost_ceiling_input.setValue(pedagogy.cost_ceiling_usd or 0.0)
        self._workers_input.setValue(pedagogy.llm_workers)
        for fmt, cb in self._export_checks.items():
            cb.setChecked(fmt in pedagogy.export_formats)

    def _on_accept(self) -> None:
        """Valide la saisie et construit le ``PedagogySettings``."""
        result = self.build_settings()
        if result is None:
            QMessageBox.warning(
                self,
                self.tr("Réglages incomplets"),
                self.tr("Sélectionnez au moins un support et au moins une langue."),
            )
            return
        self._result = result
        self.accept()


def _select_combo(combo: QComboBox, data: object) -> None:
    """Sélectionne dans ``combo`` l'item dont la donnée vaut ``data``."""
    index = combo.findData(data)
    if index >= 0:
        combo.setCurrentIndex(index)
