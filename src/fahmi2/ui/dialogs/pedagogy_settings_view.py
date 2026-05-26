"""Dialogue ``PedagogySettingsView`` — réglages des supports pédagogiques.

Réorganise les réglages en catégories (Supports, Difficulté, Langues, Modèle &
coût) via le composant ``SettingsView``. Produit un ``PedagogySettings`` (sans nom
ni emplacement, qui relèvent du ``Project``).
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QLabel,
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
from fahmi2.domain.pedagogy import (
    DEFAULT_PEDAGOGY_LLM_WORKERS,
    EVALUATIVE_SUPPORTS,
    MAX_PEDAGOGY_LLM_WORKERS,
    PedagogySettings,
)
from fahmi2.domain.phase import PhaseConfig
from fahmi2.pedagogy.labels import audience_label, bloom_label, density_label
from fahmi2.ui._model_labels import LLM_MODEL_LABELS, labeled_enum_combo
from fahmi2.ui.pedagogy_labels import EXPORT_LABELS, SUPPORT_LABELS
from fahmi2.ui.widgets.settings_view import SettingsView

_DIALOG_WIDTH_PX = 720
_DIALOG_HEIGHT_PX = 600
_DIRECTIVES_HEIGHT_PX = 90
_COST_CEILING_MAX_USD = 10_000.0
_TEMPERATURE_MIN = 0.0
_TEMPERATURE_MAX = 2.0
_TEMPERATURE_STEP = 0.1
_DEFAULT_TEMPERATURE = 0.3

_TITLE_CREATE = "Configurer les supports pédagogiques"
_TITLE_EDIT = "Réglages des supports pédagogiques"

_CAT_SUPPORTS = "Supports"
_CAT_DIFFICULTY = "Difficulté"
_CAT_LANGUAGES = "Langues"
_CAT_MODEL = "Modèle & coût"
_CAT_EXPORT = "Export"

_SEPARATE_CORRECTION_LABEL = "corrigé séparé"
_EXPORT_FORMATS_LABEL = "Formats d'export proposés :"
_EXPORT_HINT = (
    "Formats proposés lors de l'export des supports générés (le bouton « Exporter » "
    "laisse choisir parmi les formats cochés)."
)
_LANGUAGES_HINT = (
    "Les supports sont rédigés dans la langue choisie, même si le document source "
    "est dans une autre langue."
)
_REASONING_DEFAULT_LABEL = "Défaut serveur"
_DIRECTIVES_PLACEHOLDER = (
    "Directives pédagogiques libres. Ex : « privilégier des exemples concrets, "
    "éviter les pièges trop subtils, varier les formulations »."
)


class PedagogySettingsView(QDialog):
    """Dialogue d'édition des réglages pédagogie (master-detail)."""

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
        self.resize(_DIALOG_WIDTH_PX, _DIALOG_HEIGHT_PX)
        self._available_languages = available_languages
        self._result: PedagogySettings | None = None

        self._build_fields()
        settings_view = SettingsView(
            [
                (_CAT_SUPPORTS, self._build_supports_page()),
                (_CAT_DIFFICULTY, self._build_difficulty_page()),
                (_CAT_LANGUAGES, self._build_languages_page()),
                (_CAT_MODEL, self._build_model_page()),
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

    # --------------------------------------------------------------- public API

    def get_pedagogy_settings(self) -> PedagogySettings | None:
        """Retourne les réglages validés (après accept), ou ``None``.

        Returns:
            ``PedagogySettings`` ou ``None``.
        """
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
            lang
            for lang, cb in self._language_checks.items()
            if cb.isChecked()
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
        """Coche/décoche un support (helper de test/UI).

        Args:
            support: Support.
            selected: État de la case.
        """
        self._support_checks[support].setChecked(selected)

    def select_language(self, language: Language, *, selected: bool) -> None:
        """Coche/décoche une langue (helper de test/UI).

        Args:
            language: Langue.
            selected: État de la case.
        """
        if language in self._language_checks:
            self._language_checks[language].setChecked(selected)

    # ------------------------------------------------------------------ champs

    def _build_fields(self) -> None:
        """Instancie tous les widgets de champ (avant répartition en pages)."""
        self._support_checks: dict[SupportType, QCheckBox] = {}
        self._separate_checks: dict[SupportType, QCheckBox] = {}
        for support in SupportType:
            self._support_checks[support] = QCheckBox(SUPPORT_LABELS[support], self)
            if support in EVALUATIVE_SUPPORTS:
                self._separate_checks[support] = QCheckBox(
                    _SEPARATE_CORRECTION_LABEL, self
                )

        self._audience_combo = QComboBox(self)
        for audience in TargetAudience:
            self._audience_combo.addItem(audience_label(audience), audience)
        self._bloom_combo = QComboBox(self)
        for bloom in BloomObjective:
            self._bloom_combo.addItem(bloom_label(bloom), bloom)
        self._density_combo = QComboBox(self)
        for density in SupportDensity:
            self._density_combo.addItem(density_label(density), density)
        self._directives_input = QTextEdit(self)
        self._directives_input.setPlaceholderText(_DIRECTIVES_PLACEHOLDER)
        self._directives_input.setFixedHeight(_DIRECTIVES_HEIGHT_PX)
        self._directives_input.setAcceptRichText(False)

        self._language_checks: dict[Language, QCheckBox] = {}
        for lang in self._available_languages:
            self._language_checks[lang] = QCheckBox(lang.value, self)

        self._llm_combo = labeled_enum_combo(self, LLM_MODEL_LABELS)
        self._thinking_check = QCheckBox("Mode raisonnement (thinking)", self)
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
        self._cost_ceiling_input.setSuffix(" $")
        self._cost_ceiling_input.setSpecialValueText("Pas de plafond")
        self._workers_input = QSpinBox(self)
        self._workers_input.setRange(1, MAX_PEDAGOGY_LLM_WORKERS)
        self._workers_input.setValue(DEFAULT_PEDAGOGY_LLM_WORKERS)
        self._export_checks: dict[ExportFormat, QCheckBox] = {}
        for fmt in ExportFormat:
            self._export_checks[fmt] = QCheckBox(EXPORT_LABELS[fmt], self)

    # ------------------------------------------------------------------- pages

    def _build_supports_page(self) -> QWidget:
        """Construit la page « Supports » (grille + corrigés séparés).

        Returns:
            Le widget de page.
        """
        page = QWidget(self)
        grid = QGridLayout(page)
        for row, support in enumerate(SupportType):
            grid.addWidget(self._support_checks[support], row, 0)
            if support in self._separate_checks:
                grid.addWidget(self._separate_checks[support], row, 1)
        grid.setRowStretch(len(SupportType), 1)
        return page

    def _build_difficulty_page(self) -> QWidget:
        """Construit la page « Difficulté ».

        Returns:
            Le widget de page.
        """
        page = QWidget(self)
        outer = QVBoxLayout(page)
        form = QFormLayout()
        form.addRow("Public cible :", self._audience_combo)
        form.addRow("Objectif (Bloom) :", self._bloom_combo)
        form.addRow("Densité :", self._density_combo)
        form.addRow("Directives :", self._directives_input)
        outer.addLayout(form)
        outer.addStretch(1)
        return page

    def _build_languages_page(self) -> QWidget:
        """Construit la page « Langues ».

        Returns:
            Le widget de page.
        """
        page = QWidget(self)
        outer = QVBoxLayout(page)
        hint = QLabel(_LANGUAGES_HINT, page)
        hint.setWordWrap(True)
        outer.addWidget(hint)
        for cb in self._language_checks.values():
            outer.addWidget(cb)
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
        form.addRow("Raisonnement :", self._thinking_check)
        form.addRow("Niveau d'effort :", self._reasoning_combo)
        form.addRow("Température :", self._temperature_input)
        form.addRow("Plafond budget :", self._cost_ceiling_input)
        form.addRow("Tâches en parallèle :", self._workers_input)
        outer.addLayout(form)
        outer.addStretch(1)
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

    def _populate(self, pedagogy: PedagogySettings) -> None:
        """Pré-remplit les champs depuis des réglages existants.

        Args:
            pedagogy: Réglages à éditer.
        """
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
            QMessageBox.warning(
                self,
                "Réglages incomplets",
                "Sélectionnez au moins un support et au moins une langue.",
            )
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
