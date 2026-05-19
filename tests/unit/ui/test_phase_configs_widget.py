"""Tests du PhaseConfigsWidget (round-trip get/set)."""

from pytestqt.qtbot import QtBot

from fahmi2.domain.enums import PhaseId, ReasoningEffort
from fahmi2.domain.phase import PhaseConfig
from fahmi2.ui.widgets.phase_configs_widget import PhaseConfigsWidget


def _full_phase_configs(
    overrides: dict[PhaseId, PhaseConfig] | None = None,
) -> dict[PhaseId, PhaseConfig]:
    """Construit un mapping complet des phases LLM avec overrides."""
    base: dict[PhaseId, PhaseConfig] = {
        pid: PhaseConfig() for pid in PhaseId if pid is not PhaseId.STT
    }
    if overrides:
        base.update(overrides)
    return base


def test_default_configs_match_default_phase_config(qtbot: QtBot) -> None:
    widget = PhaseConfigsWidget()
    qtbot.addWidget(widget)
    result = widget.get_phase_configs()
    for cfg in result.values():
        assert cfg.thinking_enabled is False
        assert cfg.reasoning_effort is None
        assert cfg.temperature == PhaseConfig().temperature
        assert cfg.max_retries == PhaseConfig().max_retries


def test_set_then_get_round_trip(qtbot: QtBot) -> None:
    widget = PhaseConfigsWidget()
    qtbot.addWidget(widget)
    initial = _full_phase_configs(
        {
            PhaseId.REFORMULATION: PhaseConfig(
                thinking_enabled=True,
                reasoning_effort=ReasoningEffort.MAX,
                temperature=0.75,
                max_retries=8,
            )
        }
    )
    widget.set_phase_configs(initial)
    result = widget.get_phase_configs()
    refor = result[PhaseId.REFORMULATION]
    assert refor.thinking_enabled is True
    assert refor.reasoning_effort is ReasoningEffort.MAX
    assert refor.temperature == 0.75
    assert refor.max_retries == 8


def test_set_effort_none_keeps_combo_on_default(qtbot: QtBot) -> None:
    widget = PhaseConfigsWidget()
    qtbot.addWidget(widget)
    initial = _full_phase_configs(
        {
            PhaseId.CONSOLIDATION: PhaseConfig(
                thinking_enabled=True,
                reasoning_effort=None,
                temperature=0.4,
                max_retries=5,
            )
        }
    )
    widget.set_phase_configs(initial)
    result = widget.get_phase_configs()
    conso = result[PhaseId.CONSOLIDATION]
    assert conso.thinking_enabled is True
    assert conso.reasoning_effort is None


def test_set_thinking_off_returns_effort_none(qtbot: QtBot) -> None:
    widget = PhaseConfigsWidget()
    qtbot.addWidget(widget)
    # Si thinking_enabled est False, reasoning_effort doit etre force a None
    # meme si le combo serait sur une autre valeur.
    initial = _full_phase_configs(
        {
            PhaseId.STRUCTURATION: PhaseConfig(
                thinking_enabled=False,
                reasoning_effort=ReasoningEffort.HIGH,
                temperature=0.3,
                max_retries=5,
            )
        }
    )
    widget.set_phase_configs(initial)
    result = widget.get_phase_configs()
    structuration = result[PhaseId.STRUCTURATION]
    assert structuration.thinking_enabled is False
    assert structuration.reasoning_effort is None
