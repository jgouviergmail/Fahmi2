"""Dialogue ``PedagogySettingsView`` — réglages des supports pédagogiques.

Présentation : master-detail (composant
:class:`~fahmi2.ui.widgets.settings_view.SettingsView`) à cinq catégories,
chacune assemblée à partir des briques partagées
(:func:`~fahmi2.ui._components.card`, :func:`~fahmi2.ui._components.page_header`,
:func:`~fahmi2.ui._components.field_hint`).

- *Supports* : grille des 8 types de supports + option « Corrigé dans un
  document séparé » (pour les supports évaluatifs).
- *Difficulté* : public visé, objectif pédagogique (Bloom), quantité de
  contenu, consignes libres.
- *Langues* : langues à produire (parmi celles produites par la génération).
- *Génération IA* : modèle, réflexion approfondie, budget et performance.
- *Export* : formats proposés à l'export.

L'API publique (``get_pedagogy_settings``, ``build_settings``,
``select_support``, ``select_language``) et les attributs privés référencés
par les tests existants sont **strictement préservés** : seule la
présentation change.
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
    frenchify_button_box,
    page_header,
    section_label,
    settings_form,
    settings_page,
)
from fahmi2.ui._model_labels import LLM_MODEL_LABELS, labeled_enum_combo
from fahmi2.ui.pedagogy_labels import EXPORT_LABELS, SUPPORT_LABELS
from fahmi2.ui.widgets.settings_view import SettingsView

# ---------------------------------------------------------------- dimensions

_DIALOG_WIDTH: Final[int] = 880
_DIALOG_HEIGHT: Final[int] = 640
_DIRECTIVES_HEIGHT_PX: Final[int] = 90
_OUTER_MARGIN: Final[int] = 0
_OUTER_SPACING: Final[int] = 12

# ---------------------------------------------------------------- bornes
_COST_CEILING_MAX_USD: Final[float] = 10_000.0
_TEMPERATURE_MIN: Final[float] = 0.0
_TEMPERATURE_MAX: Final[float] = 2.0
_TEMPERATURE_STEP: Final[float] = 0.1
_DEFAULT_TEMPERATURE: Final[float] = 0.3

# ---------------------------------------------------------------- titres / catégories

_TITLE_CREATE: Final[str] = "Configurer les supports pédagogiques"
_TITLE_EDIT: Final[str] = "Réglages des supports pédagogiques"

_CAT_SUPPORTS: Final[str] = "Supports"
_CAT_DIFFICULTY: Final[str] = "Difficulté"
_CAT_LANGUAGES: Final[str] = "Langues"
_CAT_GENERATION: Final[str] = "Génération IA"
_CAT_EXPORT: Final[str] = "Export"

# ---------------------------------------------------------------- libellés

_SEPARATE_CORRECTION_COLUMN_HEADER: Final[str] = "Corrigé séparé"
_SEPARATE_CORRECTION_TOOLTIP: Final[str] = (
    "Si coché, le corrigé est généré dans un document distinct du sujet "
    "(utile pour les examens blancs)."
)
_SUPPORT_TYPE_COLUMN_HEADER: Final[str] = "Type de support"
_REASONING_DEFAULT_LABEL: Final[str] = "Automatique (serveur)"
_VALIDATION_TITLE: Final[str] = "Réglages incomplets"
_VALIDATION_MESSAGE: Final[str] = (
    "Sélectionnez au moins un support et au moins une langue."
)
_DIRECTIVES_PLACEHOLDER: Final[str] = (
    "Consignes libres pour l'IA. Ex. : « privilégier des exemples concrets, "
    "éviter les pièges trop subtils, varier les formulations »."
)

# Pages — descriptions affichées sous le titre.
_SUPPORTS_PAGE_DESC: Final[str] = (
    "Sélectionnez les supports de révision à générer. Pour les supports évaluatifs, "
    "cochez « Corrigé séparé » pour générer un sujet sans réponses et un corrigé "
    "dans un document distinct."
)
_DIFFICULTY_PAGE_DESC: Final[str] = (
    "Public visé, objectif pédagogique et quantité de contenu — orientent le ton, "
    "la difficulté et le volume."
)
_LANGUAGES_PAGE_DESC: Final[str] = (
    "Les supports sont rédigés dans les langues choisies, même si le document "
    "source est dans une autre langue."
)
_GENERATION_PAGE_DESC: Final[str] = (
    "Modèle de génération, intensité de réflexion, budget et performance."
)
_EXPORT_PAGE_DESC: Final[str] = (
    "Formats proposés lors de l'export depuis l'onglet « Supports pédagogiques »."
)

# Cartes — titres et descriptions.
_SUPPORTS_CARD_TITLE: Final[str] = "Types de supports"
_AUDIENCE_CARD_TITLE: Final[str] = "Public et objectif"
_AUDIENCE_CARD_DESC: Final[str] = (
    "À qui les supports sont-ils destinés, et quel niveau d'apprentissage visent-ils ?"
)
_DENSITY_CARD_TITLE: Final[str] = "Densité"
_DENSITY_CARD_DESC: Final[str] = (
    "Volume des supports générés : compact pour réviser vite, dense pour creuser."
)
_DIRECTIVES_CARD_TITLE: Final[str] = "Consignes pédagogiques"
_DIRECTIVES_CARD_DESC: Final[str] = (
    "Optionnel. Indiquez à l'IA toute orientation spécifique."
)
_LANGUAGES_CARD_TITLE: Final[str] = "Langues à produire"
_MODEL_CARD_TITLE: Final[str] = "Modèle de génération"
_MODEL_CARD_DESC: Final[str] = (
    "Modèle DeepSeek utilisé pour rédiger les supports. « Pro » coûte plus mais "
    "donne des supports de meilleure qualité."
)
_THINKING_CARD_TITLE: Final[str] = "Réflexion approfondie"
_THINKING_CARD_DESC: Final[str] = (
    "Active un raisonnement étendu avant la génération — meilleure qualité, "
    "coût plus élevé. Recommandé pour les examens blancs."
)
_BUDGET_CARD_TITLE: Final[str] = "Budget et performance"
_BUDGET_CARD_DESC: Final[str] = (
    "Plafond de dépense (la génération s'arrête si le coût l'atteint) et nombre "
    "de tâches IA traitées en parallèle (plus rapide, n'augmente pas le coût)."
)
_EXPORT_CARD_TITLE: Final[str] = "Formats à exporter"

# Étiquettes de champs (sans « : »).
_AUDIENCE_LABEL: Final[str] = "Public visé"
_BLOOM_LABEL: Final[str] = "Objectif pédagogique (Bloom)"
_DENSITY_LABEL: Final[str] = "Quantité de contenu"
_LLM_LABEL: Final[str] = "Modèle"
_TEMPERATURE_LABEL: Final[str] = "Température"
_THINKING_LABEL: Final[str] = "Activer la réflexion approfondie"
_REASONING_LABEL: Final[str] = "Intensité de réflexion"
_BUDGET_LABEL: Final[str] = "Budget maximal"
_WORKERS_LABEL: Final[str] = "Traitements simultanés"
_BUDGET_SUFFIX: Final[str] = " $"
_BUDGET_SPECIAL_VALUE: Final[str] = "Pas de plafond"

# Tooltips.
_AUDIENCE_TOOLTIP: Final[str] = (
    "Niveau d'études supposé du lecteur. Le ton et le vocabulaire s'adaptent."
)
_BLOOM_TOOLTIP: Final[str] = (
    "Niveau de la taxonomie de Bloom : comprendre, appliquer, analyser, etc."
)
_DENSITY_TOOLTIP: Final[str] = "Volume final des supports (compact, équilibré, dense)."
_BUDGET_TOOLTIP: Final[str] = (
    "Coût maximal en USD. La génération s'arrête si elle s'en approche. Mettez 0 "
    "pour désactiver le plafond."
)
_WORKERS_TOOLTIP: Final[str] = (
    "Nombre de générations IA exécutées en parallèle. Augmenter accélère sans "
    "changer le coût (DeepSeek facture au token, pas au temps)."
)


class PedagogySettingsView(QDialog):
    """Dialogue d'édition des réglages pédagogie (master-detail, cartes)."""

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        available_languages: tuple[Language, ...],
        initial: PedagogySettings | None = None,
    ) -> None:
        """Construit le dialogue.

        Args:
            parent: Parent Qt optionnel.
            available_languages: Langues proposées (produites par la génération).
            initial: Réglages pré-remplis (édition) ou ``None`` (création).
        """
        super().__init__(parent)
        self._is_edit_mode = initial is not None
        self.setWindowTitle(_TITLE_EDIT if self._is_edit_mode else _TITLE_CREATE)
        self.resize(_DIALOG_WIDTH, _DIALOG_HEIGHT)
        self._available_languages = available_languages
        self._result: PedagogySettings | None = None

        self._build_fields()
        settings_view = SettingsView(
            [
                (_CAT_SUPPORTS, self._build_supports_page()),
                (_CAT_DIFFICULTY, self._build_difficulty_page()),
                (_CAT_LANGUAGES, self._build_languages_page()),
                (_CAT_GENERATION, self._build_generation_page()),
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
        outer.addWidget(dialog_footer(self, buttons))

        self.setSizeGripEnabled(True)

        if initial is not None:
            self._populate(initial)

    # --------------------------------------------------------------- public API

    def get_pedagogy_settings(self) -> PedagogySettings | None:
        """Retourne les réglages validés (après accept), ou ``None``."""
        return self._result

    def build_settings(self) -> PedagogySettings | None:
        """Construit les réglages depuis les champs (``None`` si invalide).

        Ne déclenche aucun dialogue : utilisable directement dans les tests.

        Returns:
            ``PedagogySettings`` valide, ou ``None`` si la saisie est invalide.
        """
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
        # Qt stocke les ``StrEnum`` (sous-classes de ``str``) comme texte : on
        # recoerce explicitement vers le type enum attendu.
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

    # -------------------------------------------------------------- champs

    def _build_fields(self) -> None:
        """Instancie tous les widgets de champ (avant répartition en pages)."""
        self._support_checks: dict[SupportType, QCheckBox] = {}
        self._separate_checks: dict[SupportType, QCheckBox] = {}
        for support in SupportType:
            self._support_checks[support] = QCheckBox(SUPPORT_LABELS[support], self)
            if support in EVALUATIVE_SUPPORTS:
                # Case sans libellé répété : la colonne porte un en-tête unique
                # « Corrigé séparé » (voir ``_build_supports_page``), avec un
                # tooltip explicite pour chaque case.
                self._separate_checks[support] = QCheckBox("", self)
                self._separate_checks[support].setToolTip(
                    _SEPARATE_CORRECTION_TOOLTIP
                )

        self._audience_combo = QComboBox(self)
        self._audience_combo.setToolTip(_AUDIENCE_TOOLTIP)
        for audience in TargetAudience:
            self._audience_combo.addItem(audience_label(audience), audience)
        self._bloom_combo = QComboBox(self)
        self._bloom_combo.setToolTip(_BLOOM_TOOLTIP)
        for bloom in BloomObjective:
            self._bloom_combo.addItem(bloom_label(bloom), bloom)
        self._density_combo = QComboBox(self)
        self._density_combo.setToolTip(_DENSITY_TOOLTIP)
        for density in SupportDensity:
            self._density_combo.addItem(density_label(density), density)
        self._directives_input = QTextEdit(self)
        self._directives_input.setPlaceholderText(_DIRECTIVES_PLACEHOLDER)
        self._directives_input.setFixedHeight(_DIRECTIVES_HEIGHT_PX)
        self._directives_input.setAcceptRichText(False)

        self._language_checks: dict[Language, QCheckBox] = {}
        for lang in self._available_languages:
            self._language_checks[lang] = QCheckBox(language_display_label(lang), self)

        self._llm_combo = labeled_enum_combo(self, LLM_MODEL_LABELS)
        self._thinking_check = QCheckBox(_THINKING_LABEL, self)
        self._reasoning_combo = QComboBox(self)
        self._reasoning_combo.addItem(_REASONING_DEFAULT_LABEL, None)
        for effort in ReasoningEffort:
            self._reasoning_combo.addItem(effort.value, effort)
        self._temperature_input = QDoubleSpinBox(self)
        self._temperature_input.setRange(_TEMPERATURE_MIN, _TEMPERATURE_MAX)
        self._temperature_input.setSingleStep(_TEMPERATURE_STEP)
        self._temperature_input.setValue(_DEFAULT_TEMPERATURE)
        self._cost_ceiling_input = QDoubleSpinBox(self)
        self._cost_ceiling_input.setRange(0.0, _COST_CEILING_MAX_USD)
        self._cost_ceiling_input.setDecimals(2)
        self._cost_ceiling_input.setValue(0.0)
        self._cost_ceiling_input.setSuffix(_BUDGET_SUFFIX)
        self._cost_ceiling_input.setSpecialValueText(_BUDGET_SPECIAL_VALUE)
        self._cost_ceiling_input.setToolTip(_BUDGET_TOOLTIP)
        self._workers_input = QSpinBox(self)
        self._workers_input.setRange(1, MAX_PEDAGOGY_LLM_WORKERS)
        self._workers_input.setValue(DEFAULT_PEDAGOGY_LLM_WORKERS)
        self._workers_input.setToolTip(_WORKERS_TOOLTIP)
        self._export_checks: dict[ExportFormat, QCheckBox] = {}
        for fmt in ExportFormat:
            self._export_checks[fmt] = QCheckBox(EXPORT_LABELS[fmt], self)

    # --------------------------------------------------------------- pages

    def _build_supports_page(self) -> QWidget:
        """Construit la page « Supports » (grille des types + corrigés séparés).

        La grille a deux colonnes : « Type de support » et « Corrigé séparé »
        (la 2ᵉ colonne ne contient des cases qu'en face des supports évaluatifs).
        Les cases de la 2ᵉ colonne portent un libellé vide ; le sens est porté
        par l'en-tête de colonne unique + un tooltip sur chaque case.
        """
        page, layout = settings_page(self)
        layout.addWidget(
            page_header(
                page, title=_CAT_SUPPORTS, description=_SUPPORTS_PAGE_DESC
            )
        )
        card_frame, card_layout = card(page, title=_SUPPORTS_CARD_TITLE)
        grid = QGridLayout()
        # Ligne 0 : en-têtes de colonne (micro-labels en majuscules, gris).
        type_header = section_label(card_frame, _SUPPORT_TYPE_COLUMN_HEADER)
        separate_header = section_label(card_frame, _SEPARATE_CORRECTION_COLUMN_HEADER)
        separate_header.setToolTip(_SEPARATE_CORRECTION_TOOLTIP)
        grid.addWidget(type_header, 0, 0)
        grid.addWidget(separate_header, 0, 1)
        # Lignes suivantes : un support par ligne.
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
        """Construit la page « Difficulté » (3 cartes : audience+bloom, densité, consignes)."""
        page, layout = settings_page(self)
        layout.addWidget(
            page_header(
                page, title=_CAT_DIFFICULTY, description=_DIFFICULTY_PAGE_DESC
            )
        )
        audience_card, audience_layout = card(
            page, title=_AUDIENCE_CARD_TITLE, description=_AUDIENCE_CARD_DESC
        )
        audience_form = settings_form()
        audience_form.addRow(_AUDIENCE_LABEL, self._audience_combo)
        audience_form.addRow(_BLOOM_LABEL, self._bloom_combo)
        audience_layout.addLayout(audience_form)
        layout.addWidget(audience_card)

        density_card, density_layout = card(
            page, title=_DENSITY_CARD_TITLE, description=_DENSITY_CARD_DESC
        )
        density_form = settings_form()
        density_form.addRow(_DENSITY_LABEL, self._density_combo)
        density_layout.addLayout(density_form)
        layout.addWidget(density_card)

        directives_card, directives_layout = card(
            page, title=_DIRECTIVES_CARD_TITLE, description=_DIRECTIVES_CARD_DESC
        )
        directives_layout.addWidget(self._directives_input)
        layout.addWidget(directives_card)

        layout.addStretch(1)
        return page

    def _build_languages_page(self) -> QWidget:
        """Construit la page « Langues » (carte avec checkboxes par langue)."""
        page, layout = settings_page(self)
        layout.addWidget(
            page_header(
                page, title=_CAT_LANGUAGES, description=_LANGUAGES_PAGE_DESC
            )
        )
        card_frame, card_layout = card(page, title=_LANGUAGES_CARD_TITLE)
        for cb in self._language_checks.values():
            card_layout.addWidget(cb)
        layout.addWidget(card_frame)
        layout.addStretch(1)
        return page

    def _build_generation_page(self) -> QWidget:
        """Construit la page « Génération IA » (modèle + réflexion + budget)."""
        page, layout = settings_page(self)
        layout.addWidget(
            page_header(
                page, title=_CAT_GENERATION, description=_GENERATION_PAGE_DESC
            )
        )

        model_card, model_layout = card(
            page, title=_MODEL_CARD_TITLE, description=_MODEL_CARD_DESC
        )
        model_form = settings_form()
        model_form.addRow(_LLM_LABEL, self._llm_combo)
        model_form.addRow(_TEMPERATURE_LABEL, self._temperature_input)
        model_layout.addLayout(model_form)
        layout.addWidget(model_card)

        thinking_card, thinking_layout = card(
            page, title=_THINKING_CARD_TITLE, description=_THINKING_CARD_DESC
        )
        thinking_layout.addWidget(self._thinking_check)
        thinking_form = settings_form()
        thinking_form.addRow(_REASONING_LABEL, self._reasoning_combo)
        thinking_layout.addLayout(thinking_form)
        layout.addWidget(thinking_card)

        budget_card, budget_layout = card(
            page, title=_BUDGET_CARD_TITLE, description=_BUDGET_CARD_DESC
        )
        budget_form = settings_form()
        budget_form.addRow(_BUDGET_LABEL, self._cost_ceiling_input)
        budget_form.addRow(_WORKERS_LABEL, self._workers_input)
        budget_layout.addLayout(budget_form)
        layout.addWidget(budget_card)

        layout.addStretch(1)
        return page

    def _build_export_page(self) -> QWidget:
        """Construit la page « Export » (carte unique avec les formats)."""
        page, layout = settings_page(self)
        layout.addWidget(
            page_header(
                page, title=_CAT_EXPORT, description=_EXPORT_PAGE_DESC
            )
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
        _select_combo(self._reasoning_combo, pedagogy.llm_config.reasoning_effort)
        self._temperature_input.setValue(pedagogy.llm_config.temperature)
        self._cost_ceiling_input.setValue(pedagogy.cost_ceiling_usd or 0.0)
        self._workers_input.setValue(pedagogy.llm_workers)
        for fmt, cb in self._export_checks.items():
            cb.setChecked(fmt in pedagogy.export_formats)

    def _on_accept(self) -> None:
        """Valide la saisie et construit le ``PedagogySettings``."""
        result = self.build_settings()
        if result is None:
            QMessageBox.warning(self, _VALIDATION_TITLE, _VALIDATION_MESSAGE)
            return
        self._result = result
        self.accept()


def _select_combo(combo: QComboBox, data: object) -> None:
    """Sélectionne dans ``combo`` l'item dont la donnée vaut ``data``.

    Args:
        combo: Combo à régler.
        data: Donnée recherchée (``itemData``).
    """
    index = combo.findData(data)
    if index >= 0:
        combo.setCurrentIndex(index)
