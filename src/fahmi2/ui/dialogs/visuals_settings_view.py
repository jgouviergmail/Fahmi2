"""Dialogue ``VisualsSettingsView`` — réglages de la fonctionnalité Visualisations.

Présentation : master-detail (composant
:class:`~fahmi2.ui.widgets.settings_view.SettingsView`) à trois catégories (Livrables,
Contenu, Génération IA). Les **langues** ne sont pas choisies ici : les visualisations
sont produites pour toutes les langues latines réellement générées (zh/ar exclus).

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
    QMessageBox,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from fahmi2.domain.enums import (
    DiagramType,
    LLMModel,
    ReasoningEffort,
    SupportDensity,
)
from fahmi2.domain.phase import PhaseConfig
from fahmi2.domain.visuals import (
    DEFAULT_VISUALS_LLM_WORKERS,
    MAX_VISUALS_LLM_WORKERS,
    VisualsSettings,
)
from fahmi2.ui._components import (
    card,
    dialog_footer,
    field_hint,
    localize_button_box,
    page_header,
    settings_form,
    settings_page,
)
from fahmi2.ui._model_labels import (
    labeled_enum_combo,
    llm_model_labels,
    no_reasoning_label,
    reasoning_effort_labels,
)
from fahmi2.ui.pedagogy_labels import density_display_label
from fahmi2.ui.visuals_labels import diagram_type_labels
from fahmi2.ui.widgets.settings_view import SettingsView

_DIALOG_WIDTH: Final[int] = 880
_DIALOG_HEIGHT: Final[int] = 640
_OUTER_MARGIN: Final[int] = 0
_COST_CEILING_MAX_USD: Final[float] = 10_000.0
_TEMPERATURE_MIN: Final[float] = 0.0
_TEMPERATURE_MAX: Final[float] = 2.0
_TEMPERATURE_STEP: Final[float] = 0.1
_DEFAULT_TEMPERATURE: Final[float] = 0.3


class VisualsSettingsView(QDialog):
    """Dialogue d'édition des réglages Visualisations (master-detail, cartes)."""

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        initial: VisualsSettings | None = None,
    ) -> None:
        """Construit le dialogue.

        Args:
            parent: Parent Qt optionnel.
            initial: Réglages existants à pré-remplir (``None`` = configuration).
        """
        super().__init__(parent)
        self._is_edit_mode = initial is not None
        self.setWindowTitle(
            self.tr("Réglages des visualisations") if self._is_edit_mode
            else self.tr("Configurer les visualisations")
        )
        self.resize(_DIALOG_WIDTH, _DIALOG_HEIGHT)
        self._result: VisualsSettings | None = None

        self._build_fields()
        settings_view = SettingsView(
            [
                (self.tr("Livrables"), self._build_deliverables_page()),
                (self.tr("Contenu"), self._build_content_page()),
                (self.tr("Génération IA"), self._build_generation_page()),
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

    def get_visuals_settings(self) -> VisualsSettings | None:
        """Retourne les réglages validés (après accept), ou ``None``."""
        return self._result

    def build_settings(self) -> VisualsSettings | None:
        """Construit les réglages depuis les champs (``None`` si invalide).

        Returns:
            Un ``VisualsSettings`` valide, ou ``None`` si la saisie est incohérente
            (aucun livrable, ou diagrammes activés sans aucun type).
        """
        produce_map = self._knowledge_map_check.isChecked()
        produce_diagrams = self._diagrams_check.isChecked()
        if not (produce_map or produce_diagrams):
            return None
        diagram_types = frozenset(
            kind for kind, cb in self._diagram_type_checks.items() if cb.isChecked()
        )
        if produce_diagrams and not diagram_types:
            return None
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
            return VisualsSettings(
                produce_knowledge_map=produce_map,
                produce_diagrams=produce_diagrams,
                density=SupportDensity(self._density_combo.currentData()),
                diagram_types=diagram_types,
                llm_model=LLMModel(self._llm_combo.currentData()),
                llm_config=PhaseConfig(
                    thinking_enabled=self._thinking_check.isChecked(),
                    reasoning_effort=reasoning_effort,
                    temperature=self._temperature_input.value(),
                ),
                llm_workers=self._workers_input.value(),
                cost_ceiling_usd=ceiling,
            )
        except ValueError:
            return None

    def _build_fields(self) -> None:
        """Instancie tous les widgets de champ."""
        self._knowledge_map_check = QCheckBox(
            self.tr("Carte des connaissances (graphe interactif)"), self
        )
        self._knowledge_map_check.setChecked(True)
        self._knowledge_map_check.setToolTip(
            self.tr(
                "Page HTML autonome présentant un graphe interactif des concepts, "
                "termes du glossaire, idées et exemples, avec leurs relations."
            )
        )
        self._diagrams_check = QCheckBox(
            self.tr("Diagrammes (galerie de schémas)"), self
        )
        self._diagrams_check.setChecked(True)
        self._diagrams_check.setToolTip(
            self.tr(
                "Page HTML autonome présentant des organigrammes, chronologies, "
                "comparaisons, hiérarchies, cycles et arbres de décision générés."
            )
        )

        self._density_combo = QComboBox(self)
        self._density_combo.setToolTip(
            self.tr(
                "Volume des nœuds et diagrammes générés par section "
                "(compact, équilibré, dense)."
            )
        )
        for density in SupportDensity:
            self._density_combo.addItem(density_display_label(density), density)

        self._diagram_type_checks: dict[DiagramType, QCheckBox] = {}
        diagram_lbls = diagram_type_labels()
        for kind in DiagramType:
            self._diagram_type_checks[kind] = QCheckBox(diagram_lbls[kind], self)
            self._diagram_type_checks[kind].setChecked(True)
        self._diagrams_check.toggled.connect(self._sync_diagram_types_enabled)

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
                "Coût maximal en USD. La génération s'arrête si elle s'en approche. "
                "Mettez 0 pour désactiver le plafond."
            )
        )
        self._workers_input = QSpinBox(self)
        self._workers_input.setRange(1, MAX_VISUALS_LLM_WORKERS)
        self._workers_input.setValue(DEFAULT_VISUALS_LLM_WORKERS)
        self._workers_input.setToolTip(
            self.tr(
                "Nombre de langues traitées en parallèle. Augmenter accélère sans "
                "changer le coût (DeepSeek facture au token, pas au temps)."
            )
        )

    def _sync_diagram_types_enabled(self, enabled: bool) -> None:
        """Active/désactive les cases de types de diagramme selon le livrable.

        Args:
            enabled: ``True`` si la galerie de diagrammes est activée.
        """
        for cb in self._diagram_type_checks.values():
            cb.setEnabled(enabled)

    def _build_deliverables_page(self) -> QWidget:
        """Construit la page « Livrables »."""
        page, layout = settings_page(self)
        layout.addWidget(
            page_header(
                page,
                title=self.tr("Livrables"),
                description=self.tr(
                    "Choisissez les pages HTML autonomes à produire. Chaque page est "
                    "complète et hors-ligne (aucune dépendance externe)."
                ),
            )
        )
        card_frame, card_layout = card(page, title=self.tr("Pages à produire"))
        card_layout.addWidget(self._knowledge_map_check)
        card_layout.addWidget(self._diagrams_check)
        layout.addWidget(card_frame)
        layout.addWidget(
            field_hint(
                page,
                self.tr(
                    "Les visualisations sont produites pour chaque langue latine "
                    "générée (français, anglais, allemand, espagnol, italien). "
                    "Le chinois et l'arabe ne sont pas pris en charge."
                ),
            )
        )
        layout.addStretch(1)
        return page

    def _build_content_page(self) -> QWidget:
        """Construit la page « Contenu »."""
        page, layout = settings_page(self)
        layout.addWidget(
            page_header(
                page,
                title=self.tr("Contenu"),
                description=self.tr(
                    "Densité du contenu extrait et types de diagrammes autorisés."
                ),
            )
        )
        density_card, density_layout = card(
            page,
            title=self.tr("Densité"),
            description=self.tr(
                "Volume des nœuds et diagrammes : compact pour l'essentiel, dense "
                "pour creuser."
            ),
        )
        density_form = settings_form()
        density_form.addRow(self.tr("Quantité de contenu"), self._density_combo)
        density_layout.addLayout(density_form)
        layout.addWidget(density_card)

        types_card, types_layout = card(
            page,
            title=self.tr("Types de diagrammes"),
            description=self.tr(
                "Types autorisés dans la galerie. L'IA choisit le type adapté à "
                "chaque contenu parmi ceux cochés."
            ),
        )
        for cb in self._diagram_type_checks.values():
            types_layout.addWidget(cb)
        layout.addWidget(types_card)
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
                "Modèle DeepSeek utilisé pour extraire la structure et traduire les "
                "libellés."
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
                "Active un raisonnement étendu avant l'extraction — meilleure qualité, "
                "coût plus élevé."
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
                "Plafond de dépense (la génération s'arrête si le coût l'atteint) et "
                "nombre de langues traitées en parallèle (plus rapide, n'augmente pas "
                "le coût)."
            ),
        )
        budget_form = settings_form()
        budget_form.addRow(self.tr("Budget maximal"), self._cost_ceiling_input)
        budget_form.addRow(self.tr("Traitements simultanés"), self._workers_input)
        budget_layout.addLayout(budget_form)
        layout.addWidget(budget_card)
        layout.addStretch(1)
        return page

    def _populate(self, visuals: VisualsSettings) -> None:
        """Pré-remplit les champs depuis des réglages existants.

        Args:
            visuals: Réglages à refléter dans les champs.
        """
        self._knowledge_map_check.setChecked(visuals.produce_knowledge_map)
        self._diagrams_check.setChecked(visuals.produce_diagrams)
        _select_combo(self._density_combo, visuals.density)
        for kind, cb in self._diagram_type_checks.items():
            cb.setChecked(kind in visuals.diagram_types)
        self._sync_diagram_types_enabled(visuals.produce_diagrams)
        _select_combo(self._llm_combo, visuals.llm_model)
        self._thinking_check.setChecked(visuals.llm_config.thinking_enabled)
        effort = visuals.llm_config.reasoning_effort
        _select_combo(
            self._reasoning_combo, effort.value if effort is not None else None
        )
        self._temperature_input.setValue(visuals.llm_config.temperature)
        self._cost_ceiling_input.setValue(visuals.cost_ceiling_usd or 0.0)
        self._workers_input.setValue(visuals.llm_workers)

    def _on_accept(self) -> None:
        """Valide la saisie et construit le ``VisualsSettings``."""
        result = self.build_settings()
        if result is None:
            QMessageBox.warning(
                self,
                self.tr("Réglages incomplets"),
                self.tr(
                    "Sélectionnez au moins un livrable. Si les diagrammes sont "
                    "activés, cochez au moins un type de diagramme."
                ),
            )
            return
        self._result = result
        self.accept()


def _select_combo(combo: QComboBox, data: object) -> None:
    """Sélectionne dans ``combo`` l'item dont la donnée vaut ``data``.

    Args:
        combo: Combo cible.
        data: Donnée à sélectionner.
    """
    index = combo.findData(data)
    if index >= 0:
        combo.setCurrentIndex(index)
