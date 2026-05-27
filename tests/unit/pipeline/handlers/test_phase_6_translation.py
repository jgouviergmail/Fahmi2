"""Tests du handler Phase 6 — translation."""

import json
from pathlib import Path
from typing import Any

import pytest

from fahmi2.core.errors.exceptions import StorageError
from fahmi2.domain.enums import Language, PhaseStatus, SourceKind
from fahmi2.domain.ids import SourceId
from fahmi2.domain.source import InputSource, SourceExecution
from fahmi2.infra.llm.interface import LLMResponse
from fahmi2.pipeline.handlers.phase_6_translation import Phase6TranslationHandler
from tests.unit.pipeline.handlers._helpers import build_phase_context


def _localization_response(entries: list[dict[str, str]]) -> LLMResponse:
    return LLMResponse(
        content=json.dumps(entries, ensure_ascii=False),
        thinking_content=None,
        prompt_tokens=100,
        completion_tokens=100,
        cached_prompt_tokens=0,
        cost_usd=0.01,
    )


def test_localize_glossary_matches_by_source_and_falls_back(
    tmp_path: Path, make_generation_settings: Any
) -> None:
    payload = {
        "terms": [
            {"term": "Bilan", "definition": "doc comptable", "acronym": None},
            {"term": "IFRS", "definition": "norme", "acronym": "IFRS"},
        ]
    }
    ctx, _run = build_phase_context(
        tmp_path,
        make_generation_settings,
        llm_response=_localization_response(
            [
                {"source": "Bilan", "term": "Balance sheet", "definition": "accounting doc"},
                # "IFRS" volontairement absent → repli attendu
            ]
        ),
    )
    localized, cost = Phase6TranslationHandler()._localize_glossary(
        ctx, target=Language.EN, payload=payload
    )
    assert localized[0].term == "Balance sheet"
    assert localized[0].definition == "accounting doc"
    assert localized[1].term == "IFRS"  # repli (manquant dans la réponse)
    assert localized[1].definition == "norme"  # repli définition source
    assert cost == pytest.approx(0.01)


def test_localize_glossary_matches_despite_whitespace(
    tmp_path: Path, make_generation_settings: Any
) -> None:
    payload = {"terms": [{"term": "Bilan", "definition": "doc", "acronym": None}]}
    ctx, _run = build_phase_context(
        tmp_path,
        make_generation_settings,
        # Le LLM réémet le terme source avec un espace de bord.
        llm_response=_localization_response(
            [{"source": "  Bilan ", "term": "Balance sheet", "definition": "doc"}]
        ),
    )
    localized, _cost = Phase6TranslationHandler()._localize_glossary(
        ctx, target=Language.EN, payload=payload
    )
    assert localized[0].term == "Balance sheet"  # apparié malgré les espaces


def _seed_workspace(
    workspace: Path,
    *,
    sources: tuple[SourceExecution, ...],
    consolidated_md: str = "# Master\n\n## Intro\n\nTexte source.",
    glossary_terms: list[dict[str, Any]] | None = None,
) -> None:
    structured_dir = workspace / "structured"
    structured_dir.mkdir(parents=True, exist_ok=True)
    for v in sources:
        (structured_dir / f"{v.source_id.value}.md").write_text(
            f"# Vidéo {v.source_id.value}\n\nContenu.", encoding="utf-8"
        )
    (workspace / "consolidated_master.md").write_text(consolidated_md, encoding="utf-8")
    payload = {"terms": glossary_terms or [{"term": "PIB", "definition": "..."}]}
    (workspace / "glossary_master.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )


def test_handler_metadata() -> None:
    handler = Phase6TranslationHandler()
    assert handler.phase_id.value == "phase_6_translation"
    assert handler.is_per_source is False


def test_execute_copies_artifacts_for_source_language(
    tmp_path: Path, make_generation_settings: Any
) -> None:
    video = SourceExecution(
        source_id=SourceId.new(),
        source=InputSource(kind=SourceKind.VIDEO, location=str(tmp_path / "v.mp4")),
    )
    ctx, _ = build_phase_context(
        tmp_path,
        make_generation_settings,
        sources=(video,),
        settings_overrides={
            "source_language": Language.FR,
            "output_languages": (Language.FR,),
        },
    )
    _seed_workspace(ctx.workspace, sources=(video,))
    handler = Phase6TranslationHandler()
    result = handler.execute(ctx, source=None)
    assert result.status is PhaseStatus.SUCCEEDED
    assert (
        ctx.output_dir / "per-video" / "fr" / f"{video.source_id.value}.md"
    ).exists()
    assert (ctx.output_dir / "consolidated.fr.md").exists()
    assert (ctx.output_dir / "glossary.fr.md").exists()
    # Pour la langue source on n'appelle pas le LLM
    assert result.cost_usd == 0.0


def test_execute_translates_for_target_language(
    tmp_path: Path, make_generation_settings: Any
) -> None:
    video = SourceExecution(
        source_id=SourceId.new(),
        source=InputSource(kind=SourceKind.VIDEO, location=str(tmp_path / "v.mp4")),
    )
    # La même réponse sert l'appel de localisation (JSON) et les traductions de docs
    # (le test n'asserte que l'existence des fichiers, pas leur contenu traduit).
    ctx, _ = build_phase_context(
        tmp_path,
        make_generation_settings,
        llm_response=_localization_response(
            [{"source": "PIB", "term": "GDP", "definition": "gross domestic product"}]
        ),
        sources=(video,),
        settings_overrides={
            "source_language": Language.FR,
            "output_languages": (Language.FR, Language.EN),
        },
    )
    _seed_workspace(ctx.workspace, sources=(video,))
    handler = Phase6TranslationHandler()
    result = handler.execute(ctx, source=None)
    assert result.status is PhaseStatus.SUCCEEDED
    # FR : copies
    assert (
        ctx.output_dir / "per-video" / "fr" / f"{video.source_id.value}.md"
    ).exists()
    # EN : traductions
    assert (
        ctx.output_dir / "per-video" / "en" / f"{video.source_id.value}.md"
    ).exists()
    assert (ctx.output_dir / "consolidated.en.md").exists()
    assert (ctx.output_dir / "glossary.en.md").exists()


def test_execute_localizes_glossary_and_persists_cross_lang(
    tmp_path: Path, make_generation_settings: Any
) -> None:
    video = SourceExecution(
        source_id=SourceId.new(),
        source=InputSource(kind=SourceKind.VIDEO, location=str(tmp_path / "v.mp4")),
    )
    ctx, _ = build_phase_context(
        tmp_path,
        make_generation_settings,
        llm_response=_localization_response(
            [{"source": "Bilan", "term": "Balance sheet", "definition": "accounting doc"}]
        ),
        sources=(video,),
        settings_overrides={
            "source_language": Language.FR,
            "output_languages": (Language.FR, Language.EN),
        },
    )
    _seed_workspace(
        ctx.workspace,
        sources=(video,),
        glossary_terms=[{"term": "Bilan", "definition": "doc comptable"}],
    )
    Phase6TranslationHandler().execute(ctx, source=None)

    glossary_en = (ctx.output_dir / "glossary.en.md").read_text(encoding="utf-8")
    assert "Balance sheet" in glossary_en
    assert "Bilan" not in glossary_en
    glossary_fr = (ctx.output_dir / "glossary.fr.md").read_text(encoding="utf-8")
    assert "Bilan" in glossary_fr  # langue source : terme conservé
    master = json.loads(
        (ctx.workspace / "glossary_master.json").read_text(encoding="utf-8")
    )
    assert master["terms"][0]["cross_lang"]["en"] == "Balance sheet"


def test_execute_raises_when_consolidated_master_missing(
    tmp_path: Path, make_generation_settings: Any
) -> None:
    ctx, _ = build_phase_context(tmp_path, make_generation_settings)
    handler = Phase6TranslationHandler()
    with pytest.raises(StorageError) as exc_info:
        handler.execute(ctx, source=None)
    assert exc_info.value.code == "STORAGE.CONSOLIDATED_MISSING"


def test_execute_raises_when_video_provided(
    tmp_path: Path, make_generation_settings: Any
) -> None:
    video = SourceExecution(
        source_id=SourceId.new(),
        source=InputSource(kind=SourceKind.VIDEO, location=str(tmp_path / "v.mp4")),
    )
    ctx, _ = build_phase_context(tmp_path, make_generation_settings, sources=(video,))
    handler = Phase6TranslationHandler()
    with pytest.raises(ValueError, match="batch"):
        handler.execute(ctx, source=video)


def test_execute_accumulates_per_video_translation_cost(
    tmp_path: Path, make_generation_settings: Any
) -> None:
    video = SourceExecution(
        source_id=SourceId.new(),
        source=InputSource(kind=SourceKind.VIDEO, location=str(tmp_path / "v.mp4")),
    )
    ctx, _ = build_phase_context(
        tmp_path,
        make_generation_settings,
        llm_response=_localization_response(  # cost_usd=0.01 par appel
            [{"source": "PIB", "term": "GDP", "definition": "gross domestic product"}]
        ),
        sources=(video,),
        settings_overrides={
            "source_language": Language.FR,
            "output_languages": (Language.FR, Language.EN),
        },
    )
    _seed_workspace(ctx.workspace, sources=(video,))
    handler = Phase6TranslationHandler()
    result = handler.execute(ctx, source=None)
    # FR = source -> copies gratuites. EN -> 3 appels LLM (0.01 chacun) : localisation
    # du glossaire + traduction per-source + traduction consolidé = 0.03.
    assert result.cost_usd == pytest.approx(0.03)
