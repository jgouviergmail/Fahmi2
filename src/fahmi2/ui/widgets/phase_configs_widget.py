"""Widget de configuration par phase LLM (thinking, température, retries).

Présenté sous forme de grille : une ligne par phase LLM (1 à 7), 3 colonnes
de paramètres. Permet à l'utilisateur de régler indépendamment chaque phase
sans surcharger ``NewProjectDialog`` d'un formulaire plat de 21 champs.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QGridLayout,
    QGroupBox,
    QLabel,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from fahmi2.domain.enums import PhaseId
from fahmi2.domain.phase import PhaseConfig

_LLM_PHASES_ORDER: tuple[PhaseId, ...] = (
    PhaseId.TERM_EXTRACTION,
    PhaseId.GLOSSARY_RECONCILIATION,
    PhaseId.REFORMULATION,
    PhaseId.STRUCTURATION,
    PhaseId.CONSOLIDATION,
    PhaseId.TRANSLATION,
    PhaseId.COHERENCE,
)

_PHASE_LABELS: dict[PhaseId, str] = {
    PhaseId.TERM_EXTRACTION: "1. Extraction des termes",
    PhaseId.GLOSSARY_RECONCILIATION: "2. Réconciliation glossaire",
    PhaseId.REFORMULATION: "3. Reformulation",
    PhaseId.STRUCTURATION: "4. Structuration",
    PhaseId.CONSOLIDATION: "5. Consolidation",
    PhaseId.TRANSLATION: "6. Traduction",
    PhaseId.COHERENCE: "7. Cohérence finale",
}

_DEFAULT_TEMPERATURE = 0.3
_DEFAULT_MAX_RETRIES = 5
_TEMPERATURE_MIN = 0.0
_TEMPERATURE_MAX = 2.0
_TEMPERATURE_STEP = 0.05
_MAX_RETRIES_RANGE = 20


class PhaseConfigsWidget(QGroupBox):
    """Section configurable pour les 7 phases LLM du pipeline."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Construit le widget.

        Args:
            parent: Parent Qt optionnel.
        """
        super().__init__("Configuration des phases LLM", parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 12, 8, 8)

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(4)

        grid.addWidget(QLabel("<b>Phase</b>"), 0, 0)
        grid.addWidget(QLabel("<b>Thinking</b>"), 0, 1)
        grid.addWidget(QLabel("<b>Température</b>"), 0, 2)
        grid.addWidget(QLabel("<b>Max retries</b>"), 0, 3)

        self._rows: dict[PhaseId, tuple[QCheckBox, QDoubleSpinBox, QSpinBox]] = {}
        for row_idx, phase_id in enumerate(_LLM_PHASES_ORDER, start=1):
            grid.addWidget(QLabel(_PHASE_LABELS[phase_id]), row_idx, 0)

            thinking_cb = QCheckBox(self)
            thinking_cb.setToolTip(
                "Active le mode raisonnement DeepSeek pour cette phase "
                "(qualité supérieure, coût ~3× plus élevé en moyenne)."
            )
            grid.addWidget(thinking_cb, row_idx, 1)

            temp_sb = QDoubleSpinBox(self)
            temp_sb.setRange(_TEMPERATURE_MIN, _TEMPERATURE_MAX)
            temp_sb.setSingleStep(_TEMPERATURE_STEP)
            temp_sb.setDecimals(2)
            temp_sb.setValue(_DEFAULT_TEMPERATURE)
            temp_sb.setToolTip(
                "Température LLM : 0.0 = déterministe, 2.0 = très créatif. "
                "0.2-0.4 pour structuration/reformulation, 0.0-0.2 pour "
                "traduction, 0.4-0.6 pour idées créatives."
            )
            grid.addWidget(temp_sb, row_idx, 2)

            retries_sb = QSpinBox(self)
            retries_sb.setRange(0, _MAX_RETRIES_RANGE)
            retries_sb.setValue(_DEFAULT_MAX_RETRIES)
            retries_sb.setToolTip(
                "Nombre de tentatives en cas d'erreur transitoire "
                "(rate limit, serveur indisponible)."
            )
            grid.addWidget(retries_sb, row_idx, 3)

            self._rows[phase_id] = (thinking_cb, temp_sb, retries_sb)

        outer.addLayout(grid)

    def get_phase_configs(self) -> dict[PhaseId, PhaseConfig]:
        """Retourne le mapping ``PhaseId → PhaseConfig`` des valeurs saisies.

        Returns:
            Dictionnaire complet sur les 7 phases LLM, prêt à être passé à
            ``ProjectSettings.phases_config``.
        """
        return {
            phase_id: PhaseConfig(
                enabled_thinking=cb.isChecked(),
                temperature=temp.value(),
                max_retries=retries.value(),
            )
            for phase_id, (cb, temp, retries) in self._rows.items()
        }
