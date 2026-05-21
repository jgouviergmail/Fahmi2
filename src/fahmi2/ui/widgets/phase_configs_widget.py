"""Widget de configuration par phase LLM.

Présenté sous forme de grille : une ligne par phase LLM (1 à 7), 4 colonnes
de paramètres :

- **Thinking** (checkbox) — active ``{"thinking": {"type": "enabled"}}``.
- **Effort de raisonnement** (combo) — actif si Thinking est coché.
  Envoie ``{"reasoning_effort": <valeur>}``.
- **Température** (spinbox float 0.0..2.0).
- **Max retries** (spinbox int 0..20).
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QGridLayout,
    QGroupBox,
    QLabel,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from fahmi2.domain.enums import PhaseId, ReasoningEffort
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

_REASONING_EFFORT_LEVELS: tuple[ReasoningEffort, ...] = (
    ReasoningEffort.HIGH,
    ReasoningEffort.MAX,
)

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
        grid.addWidget(QLabel("<b>Effort</b>"), 0, 2)
        grid.addWidget(QLabel("<b>Température</b>"), 0, 3)
        grid.addWidget(QLabel("<b>Max retries</b>"), 0, 4)

        self._rows: dict[
            PhaseId,
            tuple[QCheckBox, QComboBox, QDoubleSpinBox, QSpinBox],
        ] = {}
        for row_idx, phase_id in enumerate(_LLM_PHASES_ORDER, start=1):
            grid.addWidget(QLabel(_PHASE_LABELS[phase_id]), row_idx, 0)

            thinking_cb = QCheckBox(self)
            thinking_cb.setToolTip(
                "Active le mode raisonnement DeepSeek pour cette phase "
                '(envoie {"thinking": {"type": "enabled"}}). Qualité '
                "supérieure, coût plus élevé."
            )
            grid.addWidget(thinking_cb, row_idx, 1)

            effort_combo = QComboBox(self)
            effort_combo.addItem("(défaut serveur)", None)
            for level in _REASONING_EFFORT_LEVELS:
                effort_combo.addItem(level.value, level)
            effort_combo.setToolTip(
                "Niveau d'effort de raisonnement (envoie "
                '{"reasoning_effort": "<valeur>"}). Pris en compte '
                "uniquement si Thinking est activé."
            )
            effort_combo.setEnabled(False)
            grid.addWidget(effort_combo, row_idx, 2)

            # Désactive le combo si Thinking est décoché
            thinking_cb.toggled.connect(effort_combo.setEnabled)

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
            grid.addWidget(temp_sb, row_idx, 3)

            retries_sb = QSpinBox(self)
            retries_sb.setRange(0, _MAX_RETRIES_RANGE)
            retries_sb.setValue(_DEFAULT_MAX_RETRIES)
            retries_sb.setToolTip(
                "Nombre de tentatives en cas d'erreur transitoire "
                "(rate limit, serveur indisponible)."
            )
            grid.addWidget(retries_sb, row_idx, 4)

            self._rows[phase_id] = (thinking_cb, effort_combo, temp_sb, retries_sb)

        outer.addLayout(grid)
        outer.addStretch(1)

    def get_phase_configs(self) -> dict[PhaseId, PhaseConfig]:
        """Retourne le mapping ``PhaseId → PhaseConfig`` des valeurs saisies.

        Returns:
            Dictionnaire complet sur les 7 phases LLM, prêt à être passé à
            ``GenerationSettings.phases_config``.
        """
        result: dict[PhaseId, PhaseConfig] = {}
        for phase_id, (cb, effort_combo, temp_sb, retries_sb) in self._rows.items():
            thinking = cb.isChecked()
            raw_effort = effort_combo.currentData() if thinking else None
            effort_value = _coerce_reasoning_effort(raw_effort)
            result[phase_id] = PhaseConfig(
                thinking_enabled=thinking,
                reasoning_effort=effort_value,
                temperature=temp_sb.value(),
                max_retries=retries_sb.value(),
            )
        return result

    def set_phase_configs(self, configs: dict[PhaseId, PhaseConfig]) -> None:
        """Pré-remplit le widget à partir d'un mapping ``PhaseId → PhaseConfig``.

        Args:
            configs: Configurations existantes (typiquement issues d'un projet
                à éditer). Les phases absentes du mapping conservent les
                valeurs courantes du widget.
        """
        for phase_id, cfg in configs.items():
            row = self._rows.get(phase_id)
            if row is None:
                continue
            cb, effort_combo, temp_sb, retries_sb = row
            cb.setChecked(cfg.thinking_enabled)
            effort_combo.setEnabled(cfg.thinking_enabled)
            target_index = effort_combo.findData(cfg.reasoning_effort)
            if target_index >= 0:
                effort_combo.setCurrentIndex(target_index)
            else:
                # Repasser sur "(défaut serveur)"
                effort_combo.setCurrentIndex(0)
            temp_sb.setValue(cfg.temperature)
            retries_sb.setValue(cfg.max_retries)


def _coerce_reasoning_effort(value: object) -> ReasoningEffort | None:
    """Convertit la valeur sortie de ``QComboBox.currentData()`` en enum.

    Qt peut « dégrader » un ``StrEnum`` en ``str`` lors du stockage interne
    de la valeur d'un item. On restaure le type pour que les dataclasses
    consomment toujours un ``ReasoningEffort`` propre.

    Args:
        value: Valeur brute issue de ``currentData()``.

    Returns:
        Le ``ReasoningEffort`` correspondant, ou ``None`` si valeur absente
        ou non reconnue.
    """
    if value is None:
        return None
    if isinstance(value, ReasoningEffort):
        return value
    if isinstance(value, str):
        try:
            return ReasoningEffort(value)
        except ValueError:
            return None
    return None
