"""Tests de CostEstimator."""

import pytest

from fahmi2.app.cost_estimator import CostEstimation, CostEstimator
from fahmi2.domain.enums import LLMModel, SttProvider


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
        stt_usd=1.0, llm_usd=2.0, total_usd=3.0, total_audio_seconds=600.0
    )
    assert est.total_usd == 3.0


def test_empty_videos_returns_zero() -> None:
    estimator = CostEstimator()
    est = estimator.estimate(
        videos_durations_seconds=[],
        stt_provider=SttProvider.OPENAI_CLOUD,
        llm_model=LLMModel.DEEPSEEK_V4_FLASH,
    )
    assert est.total_usd == 0.0
    assert est.total_audio_seconds == 0.0
