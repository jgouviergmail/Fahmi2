"""Tests du service PromptsService."""

from pathlib import Path

import pytest

from fahmi2.app.prompts_service import PromptsService
from fahmi2.core.errors.exceptions import ConfigError


def test_list_templates_covers_all_llm_phases(tmp_path: Path) -> None:
    service = PromptsService(override_dir=tmp_path)
    names = {meta.name for meta in service.list_templates()}
    expected = {
        "phase_1_term_extraction",
        "phase_2_glossary_reconciliation",
        "phase_3_reformulation",
        "phase_4_structuration",
        "phase_5_video_summary",
        "phase_5_consolidation",
        "phase_6_translation",
        "phase_7_coherence",
    }
    assert names == expected


def test_load_default_returns_bundled_source(tmp_path: Path) -> None:
    service = PromptsService(override_dir=tmp_path)
    source = service.load_default("phase_1_term_extraction")
    assert "glossaire" in source.lower()


def test_load_default_raises_on_unknown_template(tmp_path: Path) -> None:
    service = PromptsService(override_dir=tmp_path)
    with pytest.raises(ConfigError) as exc_info:
        service.load_default("phase_42_unknown")
    assert exc_info.value.code == "PROMPT.NOT_FOUND"


def test_load_active_falls_back_to_default_when_no_override(tmp_path: Path) -> None:
    service = PromptsService(override_dir=tmp_path)
    default = service.load_default("phase_1_term_extraction")
    active = service.load_active("phase_1_term_extraction")
    assert active == default
    assert service.has_override("phase_1_term_extraction") is False


def test_save_and_load_override_round_trip(tmp_path: Path) -> None:
    service = PromptsService(override_dir=tmp_path)
    custom = "Custom prompt {{ variable }}."
    service.save_override("phase_1_term_extraction", custom)
    assert service.has_override("phase_1_term_extraction") is True
    assert service.load_override("phase_1_term_extraction") == custom
    assert service.load_active("phase_1_term_extraction") == custom


def test_save_override_rejects_invalid_jinja(tmp_path: Path) -> None:
    service = PromptsService(override_dir=tmp_path)
    with pytest.raises(ConfigError) as exc_info:
        service.save_override("phase_1_term_extraction", "Broken {% if %}")
    assert exc_info.value.code == "PROMPT.INVALID_TEMPLATE"
    # Et aucun fichier ne doit avoir ete cree.
    assert service.has_override("phase_1_term_extraction") is False


def test_reset_override_restores_default(tmp_path: Path) -> None:
    service = PromptsService(override_dir=tmp_path)
    service.save_override("phase_1_term_extraction", "Custom {{ x }}.")
    assert service.has_override("phase_1_term_extraction") is True
    service.reset_override("phase_1_term_extraction")
    assert service.has_override("phase_1_term_extraction") is False
    # load_active retombe sur le defaut
    assert service.load_active("phase_1_term_extraction") == service.load_default(
        "phase_1_term_extraction"
    )


def test_reset_override_is_idempotent(tmp_path: Path) -> None:
    service = PromptsService(override_dir=tmp_path)
    # Aucun override -> ne leve pas
    service.reset_override("phase_1_term_extraction")
    assert service.has_override("phase_1_term_extraction") is False
