"""Tests des énumérations du domaine."""

import pytest

from fahmi2.domain.enums import (
    Language,
    LLMModel,
    PhaseId,
    PhaseStatus,
    RunStatus,
    SttProvider,
    StylePreset,
)


def test_language_values() -> None:
    assert {lang.value for lang in Language} == {"fr", "en"}


def test_style_preset_values() -> None:
    assert {s.value for s in StylePreset} == {
        "decontracte",
        "standard",
        "professionnel",
        "academique",
    }


def test_phase_id_has_eight_phases() -> None:
    assert len(list(PhaseId)) == 8


def test_phase_id_values_are_namespaced() -> None:
    for pid in PhaseId:
        assert pid.value.startswith("phase_")


def test_run_status_values() -> None:
    assert {s.value for s in RunStatus} == {
        "created",
        "running",
        "paused",
        "cancelled",
        "completed",
        "failed",
    }


def test_phase_status_values() -> None:
    assert {s.value for s in PhaseStatus} == {
        "pending",
        "running",
        "succeeded",
        "failed",
        "skipped",
    }


def test_stt_provider_values() -> None:
    assert {p.value for p in SttProvider} == {"faster_whisper_local", "openai_cloud"}


def test_llm_model_values() -> None:
    assert {m.value for m in LLMModel} == {"deepseek-v4-flash", "deepseek-v4-pro"}


def test_enum_from_str() -> None:
    assert Language("fr") is Language.FR
    assert RunStatus("running") is RunStatus.RUNNING


def test_enum_rejects_unknown() -> None:
    with pytest.raises(ValueError):
        Language("de")
