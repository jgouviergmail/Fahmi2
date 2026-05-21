"""Tests des invariants de ``PedagogySettings``."""

from __future__ import annotations

import pytest

from fahmi2.domain.enums import (
    BloomObjective,
    ExportFormat,
    Language,
    LLMModel,
    SupportDensity,
    SupportType,
    TargetAudience,
)
from fahmi2.domain.pedagogy import (
    DEFAULT_PEDAGOGY_LLM_WORKERS,
    EVALUATIVE_SUPPORTS,
    NO_LLM_SUPPORTS,
    PEDAGOGY_WORKSPACE_SUBDIR,
    PedagogySettings,
)
from fahmi2.domain.phase import PhaseConfig
from fahmi2.pedagogy.manifest import compute_settings_hash


def _make(**overrides: object) -> PedagogySettings:
    base: dict[str, object] = {
        "selected_supports": frozenset({SupportType.FLASHCARDS_CONCEPTS}),
        "separate_correction": frozenset(),
        "target_audience": TargetAudience.LICENCE,
        "bloom_objective": BloomObjective.AUTO,
        "pedagogy_directives": "",
        "languages": (Language.FR,),
        "density": SupportDensity.STANDARD,
        "llm_model": LLMModel.DEEPSEEK_V4_FLASH,
        "llm_config": PhaseConfig(),
        "cost_ceiling_usd": None,
        "export_formats": frozenset({ExportFormat.APKG}),
    }
    base.update(overrides)
    return PedagogySettings(**base)  # type: ignore[arg-type]


def test_constants() -> None:
    assert PEDAGOGY_WORKSPACE_SUBDIR == "pedagogy"
    assert SupportType.QCM in EVALUATIVE_SUPPORTS
    assert NO_LLM_SUPPORTS == frozenset()


def test_valid_construct() -> None:
    assert _make().target_audience is TargetAudience.LICENCE


def test_selected_supports_must_be_non_empty() -> None:
    with pytest.raises(ValueError, match="selected_supports"):
        _make(selected_supports=frozenset())


def test_languages_must_be_non_empty() -> None:
    with pytest.raises(ValueError, match="languages"):
        _make(languages=())


def test_separate_correction_subset_of_evaluative_selected() -> None:
    with pytest.raises(ValueError, match="separate_correction"):
        _make(
            selected_supports=frozenset({SupportType.FLASHCARDS_CONCEPTS}),
            separate_correction=frozenset({SupportType.QCM}),
        )


def test_negative_ceiling_rejected() -> None:
    with pytest.raises(ValueError, match="cost_ceiling_usd"):
        _make(cost_ceiling_usd=-1.0)


def test_llm_workers_defaults_to_16() -> None:
    assert _make().llm_workers == DEFAULT_PEDAGOGY_LLM_WORKERS
    assert DEFAULT_PEDAGOGY_LLM_WORKERS == 16


def test_llm_workers_must_be_positive() -> None:
    with pytest.raises(ValueError, match="llm_workers"):
        _make(llm_workers=0)


def test_llm_workers_not_in_settings_hash() -> None:
    a = compute_settings_hash(_make(llm_workers=4))
    b = compute_settings_hash(_make(llm_workers=32))
    assert a == b
