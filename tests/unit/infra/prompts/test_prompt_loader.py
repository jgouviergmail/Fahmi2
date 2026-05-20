"""Tests du PromptLoader."""

from pathlib import Path

import pytest

from fahmi2.core.errors.exceptions import ConfigError
from fahmi2.infra.prompts.loader import PromptLoader


def test_render_default_template_phase_1() -> None:
    loader = PromptLoader()
    rendered = loader.render(
        "phase_1_term_extraction",
        source_language_label="français",
        style_label="standard",
        style_directives="",
        transcription_text="bonjour le monde",
    )
    assert "glossaire" in rendered.lower()
    assert "bonjour le monde" in rendered


def test_render_unknown_template_raises_config_error() -> None:
    loader = PromptLoader()
    with pytest.raises(ConfigError) as exc_info:
        loader.render("does_not_exist", x=1)
    assert exc_info.value.code == "PROMPT.NOT_FOUND"


def test_override_replaces_default(tmp_path: Path) -> None:
    override = tmp_path / "phase_1_term_extraction.j2"
    override.write_text("OVERRIDE {{ transcription_text }}", encoding="utf-8")
    loader = PromptLoader(override_dir=tmp_path)
    rendered = loader.render(
        "phase_1_term_extraction",
        source_language_label="x",
        style_label="x",
        style_directives="",
        transcription_text="hello",
    )
    assert rendered.strip() == "OVERRIDE hello"


def test_invalid_override_falls_back_to_default(tmp_path: Path) -> None:
    override = tmp_path / "phase_1_term_extraction.j2"
    override.write_text("OVERRIDE {{ bad syntax", encoding="utf-8")
    loader = PromptLoader(override_dir=tmp_path)
    rendered = loader.render(
        "phase_1_term_extraction",
        source_language_label="français",
        style_label="standard",
        style_directives="",
        transcription_text="hello",
    )
    # Le défaut est utilisé : on retrouve les mots-clés du défaut.
    assert "glossaire" in rendered.lower()


def test_missing_override_dir_uses_default(tmp_path: Path) -> None:
    # override_dir inexistant
    loader = PromptLoader(override_dir=tmp_path / "missing")
    rendered = loader.render(
        "phase_1_term_extraction",
        source_language_label="français",
        style_label="standard",
        style_directives="",
        transcription_text="hello",
    )
    assert "glossaire" in rendered.lower()


def test_render_phase_5_consolidation_requests_summary() -> None:
    loader = PromptLoader()
    rendered = loader.render(
        "phase_5_consolidation",
        output_language_label="français",
        style_label="standard",
        style_directives="",
        summaries_json="[]",
    )
    # Le champ de sortie JSON est demandé
    assert "summary_markdown" in rendered
    # La consigne de résumé exécutif est présente
    assert "Résumé exécutif" in rendered
    # La phrase de routage du fake e2e est préservée
    assert "rédige les méta-éléments" in rendered


def test_render_phase_7_coherence_mentions_summary() -> None:
    loader = PromptLoader()
    rendered = loader.render(
        "phase_7_coherence",
        output_language_label="français",
        style_label="standard",
        style_directives="",
        glossary_terms=[],
        consolidated_markdown="# t",
    )
    # Le résumé exécutif fait partie des méta-éléments à relire
    assert "résumé exécutif" in rendered.lower()
    # La phrase de routage du fake e2e est préservée
    assert "passe de cohérence" in rendered.lower()


def test_all_phase_templates_are_loadable() -> None:
    """Smoke test : les 7 templates bundlés se chargent sans erreur."""
    loader = PromptLoader()
    # Phase 1
    loader.render(
        "phase_1_term_extraction",
        source_language_label="fr",
        style_label="standard",
        style_directives="",
        transcription_text="t",
    )
    # Phase 2
    loader.render(
        "phase_2_glossary_reconciliation",
        source_language_label="fr",
        style_label="standard",
        style_directives="",
        candidates_json="[]",
    )
    # Phase 3
    loader.render(
        "phase_3_reformulation",
        output_language_label="fr",
        style_label="standard",
        style_directives="",
        glossary_terms=[],
        transcription_text="t",
    )
    # Phase 4
    loader.render(
        "phase_4_structuration",
        output_language_label="fr",
        style_label="standard",
        style_directives="",
        glossary_terms=[],
        reformulated_text="r",
    )
    # Phase 5 main
    loader.render(
        "phase_5_consolidation",
        output_language_label="fr",
        style_label="standard",
        style_directives="",
        summaries_json="[]",
    )
    # Phase 5 video summary
    loader.render(
        "phase_5_video_summary",
        output_language_label="fr",
        structured_markdown="# t",
    )
    # Phase 6
    loader.render(
        "phase_6_translation",
        source_language_label="fr",
        target_language_label="en",
        style_label="standard",
        style_directives="",
        glossary_terms=[],
        source_markdown="# t",
    )
    # Phase 7
    loader.render(
        "phase_7_coherence",
        output_language_label="fr",
        style_label="standard",
        style_directives="",
        glossary_terms=[],
        consolidated_markdown="# t",
    )
