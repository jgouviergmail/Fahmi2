"""Tests des invariants de ``GenerationSettings``."""

from __future__ import annotations

from pathlib import Path

import pytest

from fahmi2.domain.enums import (
    ExportFormat,
    Language,
    LLMModel,
    PhaseId,
    SttProvider,
    StylePreset,
)
from fahmi2.domain.generation import (
    GENERATION_WORKSPACE_SUBDIR,
    MAX_LLM_WORKERS,
    MAX_STT_CLOUD_WORKERS,
    GenerationSettings,
    ParallelismConfig,
    glossary_doc_filename,
)
from fahmi2.domain.phase import PhaseConfig


def _valid_phases() -> dict[PhaseId, PhaseConfig]:
    return {pid: PhaseConfig() for pid in PhaseId if pid is not PhaseId.STT}


def _make(**overrides: object) -> GenerationSettings:
    base: dict[str, object] = {
        "input_folder": Path("./input"),
        "source_language": Language.FR,
        "output_languages": (Language.FR,),
        "style_preset": StylePreset.STANDARD,
        "style_directives": "",
        "stt_provider": SttProvider.OPENAI_CLOUD,
        "llm_model": LLMModel.DEEPSEEK_V4_FLASH,
        "phases_config": _valid_phases(),
        "cost_ceiling_usd": None,
        "parallelism": ParallelismConfig(),
        "delete_audio_after_stt": True,
    }
    base.update(overrides)
    return GenerationSettings(**base)  # type: ignore[arg-type]


def test_generation_subdir_constant() -> None:
    assert GENERATION_WORKSPACE_SUBDIR == "generation"


def test_valid_settings_construct() -> None:
    settings = _make()
    assert settings.source_language is Language.FR


def test_source_language_must_be_in_outputs() -> None:
    with pytest.raises(ValueError, match="source_language"):
        _make(source_language=Language.EN, output_languages=(Language.FR,))


def test_phases_config_must_cover_llm_phases() -> None:
    incomplete = {PhaseId.REFORMULATION: PhaseConfig()}
    with pytest.raises(ValueError, match="phases_config"):
        _make(phases_config=incomplete)


def test_negative_ceiling_rejected() -> None:
    with pytest.raises(ValueError, match="cost_ceiling_usd"):
        _make(cost_ceiling_usd=-1.0)


def test_cost_ceiling_zero_is_valid() -> None:
    assert _make(cost_ceiling_usd=0.0).cost_ceiling_usd == 0.0


def test_glossary_doc_filename() -> None:
    assert glossary_doc_filename(Language.FR) == "glossary.fr.md"
    assert glossary_doc_filename(Language.EN) == "glossary.en.md"


def test_export_formats_defaults_empty() -> None:
    assert _make().export_formats == frozenset()


def test_export_formats_rejects_apkg() -> None:
    with pytest.raises(ValueError, match="subset"):
        _make(export_formats=frozenset({ExportFormat.APKG}))


def test_export_formats_accepts_doc_formats() -> None:
    out = _make(export_formats=frozenset({ExportFormat.PDF, ExportFormat.HTML}))
    assert out.export_formats == frozenset({ExportFormat.PDF, ExportFormat.HTML})


def test_requires_at_least_one_output_language() -> None:
    with pytest.raises(ValueError, match="output_languages"):
        _make(output_languages=())


def test_must_not_configure_stt_phase() -> None:
    invalid = {pid: PhaseConfig() for pid in PhaseId}
    with pytest.raises(ValueError, match="phases_config"):
        _make(phases_config=invalid)


def test_parallelism_config_defaults() -> None:
    parallelism = ParallelismConfig()
    assert parallelism.stt_cloud_workers == 3
    assert parallelism.llm_workers == 16


def test_parallelism_ui_bounds_exposed() -> None:
    assert MAX_STT_CLOUD_WORKERS == 8
    assert MAX_LLM_WORKERS == 64


def test_parallelism_config_validates_positive() -> None:
    with pytest.raises(ValueError, match="stt_cloud_workers"):
        ParallelismConfig(stt_cloud_workers=0)
    with pytest.raises(ValueError, match="llm_workers"):
        ParallelismConfig(llm_workers=-1)
