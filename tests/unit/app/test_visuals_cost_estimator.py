"""Tests de VisualsCostEstimator."""

from __future__ import annotations

from fahmi2.app.visuals_cost_estimator import VisualsCostEstimator
from fahmi2.domain.visuals import VisualsSettings
from fahmi2.visuals.sources import TextUnit


def _units(n: int) -> tuple[TextUnit, ...]:
    return tuple(
        TextUnit(
            section_path=(i,),
            title=f"S{i}",
            anchor=f"{i}-s",
            text="mot " * 200,
            part=0,
        )
        for i in range(1, n + 1)
    )


def test_full_estimation_is_positive() -> None:
    est = VisualsCostEstimator().estimate(
        visuals=VisualsSettings(), structure_units=_units(3), language_count=1
    )
    assert est.total_usd > 0.0
    assert est.units_total == 3
    assert est.knowledge_map_usd > 0.0
    assert est.diagrams_usd > 0.0
    assert est.translation_usd == 0.0  # une seule langue → pas de traduction


def test_more_units_costs_more() -> None:
    small = VisualsCostEstimator().estimate(
        visuals=VisualsSettings(), structure_units=_units(1), language_count=1
    )
    big = VisualsCostEstimator().estimate(
        visuals=VisualsSettings(), structure_units=_units(6), language_count=1
    )
    assert big.total_usd > small.total_usd


def test_extra_languages_add_translation_cost() -> None:
    one = VisualsCostEstimator().estimate(
        visuals=VisualsSettings(), structure_units=_units(4), language_count=1
    )
    three = VisualsCostEstimator().estimate(
        visuals=VisualsSettings(), structure_units=_units(4), language_count=3
    )
    assert three.translation_usd > 0.0
    assert one.translation_usd == 0.0
    assert three.total_usd > one.total_usd


def test_knowledge_map_only_excludes_diagrams() -> None:
    est = VisualsCostEstimator().estimate(
        visuals=VisualsSettings(produce_diagrams=False),
        structure_units=_units(3),
        language_count=2,
    )
    assert est.diagrams_usd == 0.0
    assert est.knowledge_map_usd > 0.0


def test_diagrams_only_excludes_knowledge_map() -> None:
    est = VisualsCostEstimator().estimate(
        visuals=VisualsSettings(produce_knowledge_map=False),
        structure_units=_units(3),
        language_count=2,
    )
    assert est.knowledge_map_usd == 0.0
    assert est.diagrams_usd > 0.0


def test_estimation_has_range() -> None:
    est = VisualsCostEstimator().estimate(
        visuals=VisualsSettings(), structure_units=_units(3), language_count=2
    )
    assert est.low_usd < est.total_usd < est.high_usd


def test_no_units_costs_nothing() -> None:
    est = VisualsCostEstimator().estimate(
        visuals=VisualsSettings(), structure_units=(), language_count=0
    )
    assert est.total_usd == 0.0
    assert est.units_total == 0
