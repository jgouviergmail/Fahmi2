"""Tests des énumérations du domaine."""

import pytest

from fahmi2.domain.enums import (
    ConsolidationMode,
    ExportFormat,
    Language,
    LLMModel,
    PhaseId,
    PhaseStatus,
    ReasoningEffort,
    RunStatus,
    SourceKind,
    SttProvider,
    StylePreset,
)


def test_export_format_values() -> None:
    assert {f.value for f in ExportFormat} == {
        "apkg",
        "markdown",
        "pdf",
        "html",
        "docx",
    }


def test_language_values() -> None:
    assert {lang.value for lang in Language} == {
        "fr",
        "en",
        "de",
        "es",
        "it",
        "zh",
        "ar",
    }
    # FR reste en première position (défaut d'affichage et d'ordre).
    assert next(iter(Language)) is Language.FR


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


def test_reasoning_effort_values() -> None:
    assert {e.value for e in ReasoningEffort} == {"high", "max"}


def test_source_kind_values() -> None:
    assert {k.value for k in SourceKind} == {"video", "audio", "document", "youtube"}


def test_consolidation_mode_values() -> None:
    assert {m.value for m in ConsolidationMode} == {"ordered", "thematic"}


def test_consolidation_mode_from_str() -> None:
    assert ConsolidationMode("ordered") is ConsolidationMode.ORDERED
    assert ConsolidationMode("thematic") is ConsolidationMode.THEMATIC


def test_enum_from_str() -> None:
    assert Language("fr") is Language.FR
    assert RunStatus("running") is RunStatus.RUNNING


def test_enum_rejects_unknown() -> None:
    with pytest.raises(ValueError):
        Language("xx")
