"""Tests de PedagogyCostEstimator."""

from __future__ import annotations

from typing import Any

from fahmi2.app.pedagogy_cost_estimator import PedagogyCostEstimator
from fahmi2.core.corpus import Chapter
from fahmi2.domain.enums import Language, SupportType


def _chapters(n: int) -> tuple[Chapter, ...]:
    return tuple(
        Chapter(index=i, title=f"C{i}", anchor=f"{i}-c", body_markdown="mot " * 200)
        for i in range(1, n + 1)
    )


def test_llm_support_reports_chapter_count(make_pedagogy_settings: Any) -> None:
    ped = make_pedagogy_settings(
        selected_supports=frozenset({SupportType.FLASHCARDS_CONCEPTS})
    )
    est = PedagogyCostEstimator().estimate(
        pedagogy=ped, chapters_by_language={Language.FR: _chapters(3)}
    )
    assert est.total_usd > 0.0
    assert est.chapters_total == 3


def test_llm_support_has_positive_cost(make_pedagogy_settings: Any) -> None:
    ped = make_pedagogy_settings(
        selected_supports=frozenset({SupportType.QCM}),
        separate_correction=frozenset(),
    )
    est = PedagogyCostEstimator().estimate(
        pedagogy=ped, chapters_by_language={Language.FR: _chapters(3)}
    )
    assert est.total_usd > 0.0
    assert est.per_support_usd[SupportType.QCM] > 0.0


def test_more_chapters_costs_more(make_pedagogy_settings: Any) -> None:
    ped = make_pedagogy_settings(selected_supports=frozenset({SupportType.QCM}))
    small = PedagogyCostEstimator().estimate(
        pedagogy=ped, chapters_by_language={Language.FR: _chapters(1)}
    )
    big = PedagogyCostEstimator().estimate(
        pedagogy=ped, chapters_by_language={Language.FR: _chapters(5)}
    )
    assert big.total_usd > small.total_usd


def test_estimation_has_range(make_pedagogy_settings: Any) -> None:
    ped = make_pedagogy_settings(selected_supports=frozenset({SupportType.QCM}))
    est = PedagogyCostEstimator().estimate(
        pedagogy=ped, chapters_by_language={Language.FR: _chapters(3)}
    )
    assert est.low_usd < est.total_usd < est.high_usd


def test_mock_exam_is_estimated(make_pedagogy_settings: Any) -> None:
    ped = make_pedagogy_settings(
        selected_supports=frozenset({SupportType.MOCK_EXAM}),
        separate_correction=frozenset(),
    )
    est = PedagogyCostEstimator().estimate(
        pedagogy=ped, chapters_by_language={Language.FR: _chapters(2)}
    )
    assert est.per_support_usd[SupportType.MOCK_EXAM] > 0.0
