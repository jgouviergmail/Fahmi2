"""Tests de CostEstimator."""

import pytest

from fahmi2.app.cost_estimator import CostEstimation, CostEstimator
from fahmi2.domain.enums import LLMModel, PhaseId, ReasoningEffort, SttProvider
from fahmi2.domain.phase import PhaseConfig


def _all_phases_thinking(effort: ReasoningEffort | None) -> dict[PhaseId, PhaseConfig]:
    """Construit un mapping de PhaseConfig avec thinking actif sur toutes les phases LLM."""
    phases = (
        PhaseId.TERM_EXTRACTION,
        PhaseId.GLOSSARY_RECONCILIATION,
        PhaseId.REFORMULATION,
        PhaseId.STRUCTURATION,
        PhaseId.CONSOLIDATION,
        PhaseId.TRANSLATION,
        PhaseId.COHERENCE,
    )
    return {
        pid: PhaseConfig(thinking_enabled=True, reasoning_effort=effort)
        for pid in phases
    }


def test_stt_local_is_free() -> None:
    estimator = CostEstimator()
    est = estimator.estimate(
        videos_durations_seconds=[600.0, 600.0],
        stt_provider=SttProvider.FASTER_WHISPER_LOCAL,
        llm_model=LLMModel.DEEPSEEK_V4_FLASH,
    )
    assert est.stt_usd == 0.0


def test_stt_cloud_charges_per_minute() -> None:
    estimator = CostEstimator()
    est = estimator.estimate(
        videos_durations_seconds=[60.0],
        stt_provider=SttProvider.OPENAI_CLOUD,
        llm_model=LLMModel.DEEPSEEK_V4_FLASH,
    )
    assert est.stt_usd == pytest.approx(0.006)


def test_total_combines_stt_and_llm() -> None:
    estimator = CostEstimator()
    est = estimator.estimate(
        videos_durations_seconds=[600.0],
        stt_provider=SttProvider.OPENAI_CLOUD,
        llm_model=LLMModel.DEEPSEEK_V4_FLASH,
    )
    assert est.total_usd == pytest.approx(est.stt_usd + est.llm_usd)


def test_total_audio_seconds_is_sum() -> None:
    estimator = CostEstimator()
    est = estimator.estimate(
        videos_durations_seconds=[60.0, 120.0, 180.0],
        stt_provider=SttProvider.FASTER_WHISPER_LOCAL,
        llm_model=LLMModel.DEEPSEEK_V4_FLASH,
    )
    assert est.total_audio_seconds == 360.0


def test_pro_costs_more_than_flash() -> None:
    estimator = CostEstimator()
    est_flash = estimator.estimate(
        videos_durations_seconds=[600.0],
        stt_provider=SttProvider.FASTER_WHISPER_LOCAL,
        llm_model=LLMModel.DEEPSEEK_V4_FLASH,
    )
    est_pro = estimator.estimate(
        videos_durations_seconds=[600.0],
        stt_provider=SttProvider.FASTER_WHISPER_LOCAL,
        llm_model=LLMModel.DEEPSEEK_V4_PRO,
    )
    assert est_pro.llm_usd > est_flash.llm_usd


def test_translation_increases_cost_with_target_languages() -> None:
    estimator = CostEstimator()
    est_single = estimator.estimate(
        videos_durations_seconds=[600.0],
        stt_provider=SttProvider.FASTER_WHISPER_LOCAL,
        llm_model=LLMModel.DEEPSEEK_V4_FLASH,
        active_target_languages_count=1,
        translation_languages_count=0,
    )
    est_multi = estimator.estimate(
        videos_durations_seconds=[600.0],
        stt_provider=SttProvider.FASTER_WHISPER_LOCAL,
        llm_model=LLMModel.DEEPSEEK_V4_FLASH,
        active_target_languages_count=2,
        translation_languages_count=1,
    )
    assert est_multi.llm_usd > est_single.llm_usd


def test_estimation_is_dataclass() -> None:
    est = CostEstimation(
        stt_usd=1.0,
        llm_usd=2.0,
        total_usd=3.0,
        total_audio_seconds=600.0,
        per_phase_usd={PhaseId.STT: 1.0},
        low_usd=2.0,
        high_usd=4.0,
    )
    assert est.total_usd == 3.0


def test_per_phase_breakdown_sums_to_total() -> None:
    est = CostEstimator().estimate(
        videos_durations_seconds=[600.0, 600.0],
        stt_provider=SttProvider.OPENAI_CLOUD,
        llm_model=LLMModel.DEEPSEEK_V4_FLASH,
        active_target_languages_count=1,
        translation_languages_count=0,
    )
    assert PhaseId.STT in est.per_phase_usd
    assert sum(est.per_phase_usd.values()) == pytest.approx(est.total_usd)
    assert est.per_phase_usd[PhaseId.STT] == pytest.approx(est.stt_usd)


def test_estimation_has_range() -> None:
    est = CostEstimator().estimate(
        videos_durations_seconds=[600.0],
        stt_provider=SttProvider.OPENAI_CLOUD,
        llm_model=LLMModel.DEEPSEEK_V4_FLASH,
    )
    assert est.low_usd < est.total_usd < est.high_usd


def test_empty_videos_returns_zero() -> None:
    estimator = CostEstimator()
    est = estimator.estimate(
        videos_durations_seconds=[],
        stt_provider=SttProvider.OPENAI_CLOUD,
        llm_model=LLMModel.DEEPSEEK_V4_FLASH,
    )
    assert est.total_usd == 0.0
    assert est.total_audio_seconds == 0.0


# --- Prise en compte du mode thinking ---------------------------------------


def test_thinking_off_matches_no_phases_config() -> None:
    """Un mapping vide ou un thinking off doivent donner le même résultat."""
    estimator = CostEstimator()
    base = estimator.estimate(
        videos_durations_seconds=[600.0],
        stt_provider=SttProvider.FASTER_WHISPER_LOCAL,
        llm_model=LLMModel.DEEPSEEK_V4_FLASH,
    )
    with_off_config = estimator.estimate(
        videos_durations_seconds=[600.0],
        stt_provider=SttProvider.FASTER_WHISPER_LOCAL,
        llm_model=LLMModel.DEEPSEEK_V4_FLASH,
        phases_config={
            PhaseId.REFORMULATION: PhaseConfig(thinking_enabled=False),
        },
    )
    assert with_off_config.llm_usd == pytest.approx(base.llm_usd)


def test_thinking_enabled_increases_cost() -> None:
    estimator = CostEstimator()
    no_thinking = estimator.estimate(
        videos_durations_seconds=[600.0],
        stt_provider=SttProvider.FASTER_WHISPER_LOCAL,
        llm_model=LLMModel.DEEPSEEK_V4_FLASH,
    )
    with_thinking = estimator.estimate(
        videos_durations_seconds=[600.0],
        stt_provider=SttProvider.FASTER_WHISPER_LOCAL,
        llm_model=LLMModel.DEEPSEEK_V4_FLASH,
        phases_config=_all_phases_thinking(None),
    )
    assert with_thinking.llm_usd > no_thinking.llm_usd


def test_thinking_high_costs_more_than_default() -> None:
    estimator = CostEstimator()
    default_effort = estimator.estimate(
        videos_durations_seconds=[600.0],
        stt_provider=SttProvider.FASTER_WHISPER_LOCAL,
        llm_model=LLMModel.DEEPSEEK_V4_FLASH,
        phases_config=_all_phases_thinking(None),
    )
    high_effort = estimator.estimate(
        videos_durations_seconds=[600.0],
        stt_provider=SttProvider.FASTER_WHISPER_LOCAL,
        llm_model=LLMModel.DEEPSEEK_V4_FLASH,
        phases_config=_all_phases_thinking(ReasoningEffort.HIGH),
    )
    assert high_effort.llm_usd > default_effort.llm_usd


def test_thinking_max_costs_more_than_high() -> None:
    estimator = CostEstimator()
    high_effort = estimator.estimate(
        videos_durations_seconds=[600.0],
        stt_provider=SttProvider.FASTER_WHISPER_LOCAL,
        llm_model=LLMModel.DEEPSEEK_V4_FLASH,
        phases_config=_all_phases_thinking(ReasoningEffort.HIGH),
    )
    max_effort = estimator.estimate(
        videos_durations_seconds=[600.0],
        stt_provider=SttProvider.FASTER_WHISPER_LOCAL,
        llm_model=LLMModel.DEEPSEEK_V4_FLASH,
        phases_config=_all_phases_thinking(ReasoningEffort.MAX),
    )
    assert max_effort.llm_usd > high_effort.llm_usd


def test_thinking_only_on_one_phase_partially_increases_cost() -> None:
    """Activer thinking sur une seule phase ne doit augmenter le coût que de
    cette phase, pas autant que sur toutes les phases."""
    estimator = CostEstimator()
    no_thinking = estimator.estimate(
        videos_durations_seconds=[600.0],
        stt_provider=SttProvider.FASTER_WHISPER_LOCAL,
        llm_model=LLMModel.DEEPSEEK_V4_FLASH,
    )
    one_phase = estimator.estimate(
        videos_durations_seconds=[600.0],
        stt_provider=SttProvider.FASTER_WHISPER_LOCAL,
        llm_model=LLMModel.DEEPSEEK_V4_FLASH,
        phases_config={
            PhaseId.REFORMULATION: PhaseConfig(
                thinking_enabled=True,
                reasoning_effort=ReasoningEffort.HIGH,
            ),
        },
    )
    all_phases = estimator.estimate(
        videos_durations_seconds=[600.0],
        stt_provider=SttProvider.FASTER_WHISPER_LOCAL,
        llm_model=LLMModel.DEEPSEEK_V4_FLASH,
        phases_config=_all_phases_thinking(ReasoningEffort.HIGH),
    )
    assert no_thinking.llm_usd < one_phase.llm_usd < all_phases.llm_usd
