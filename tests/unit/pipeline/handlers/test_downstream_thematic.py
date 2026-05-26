"""Non-régression : les phases 6/7 traitent un consolidé **thématique**.

Le document thématique a des chapitres qui **ne correspondent pas aux sources**
(la correspondance 1 source = 1 chapitre n'existe plus). Ces tests vérifient
qu'aucune hypothèse de l'aval (traduction, cohérence) ne casse pour autant : le
consolidé est traité **comme un tout** opaque.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fahmi2.domain.enums import Language, PhaseStatus, SourceKind
from fahmi2.domain.ids import SourceId
from fahmi2.domain.source import InputSource, SourceExecution
from fahmi2.infra.llm.interface import LLMResponse
from fahmi2.pipeline.handlers.phase_6_translation import Phase6TranslationHandler
from fahmi2.pipeline.handlers.phase_7_coherence import Phase7CoherenceHandler
from tests.unit.pipeline.handlers._helpers import build_phase_context

# Consolidé thématique : un chapitre transversal, sans lien avec les sources.
_THEMATIC_DOC = (
    "# Cours consolidé\n\n"
    "## Sommaire\n\n"
    "1. [Thème transversal](#1-theme-transversal)\n\n"
    "# 1. Thème transversal\n\n"
    "## 1.1 Sous-thème\n\n"
    "Contenu fusionné issu de plusieurs sources.\n"
)


def _two_sources(tmp_path: Path) -> tuple[SourceExecution, ...]:
    return tuple(
        SourceExecution(
            source_id=SourceId.new(),
            source=InputSource(
                kind=SourceKind.VIDEO, location=str(tmp_path / f"v{i}.mp4")
            ),
        )
        for i in range(2)
    )


def _seed(workspace: Path, sources: tuple[SourceExecution, ...]) -> None:
    structured_dir = workspace / "structured"
    structured_dir.mkdir(parents=True, exist_ok=True)
    for s in sources:
        (structured_dir / f"{s.source_id.value}.md").write_text(
            f"# Source {s.source_id.value}\n\nContenu.", encoding="utf-8"
        )
    (workspace / "consolidated_master.md").write_text(_THEMATIC_DOC, encoding="utf-8")
    (workspace / "glossary_master.json").write_text(
        json.dumps({"terms": [{"term": "PIB", "definition": "..."}]}),
        encoding="utf-8",
    )


def test_phase6_source_language_copies_thematic_doc_verbatim(
    tmp_path: Path, make_generation_settings: Any
) -> None:
    sources = _two_sources(tmp_path)
    ctx, _ = build_phase_context(
        tmp_path,
        make_generation_settings,
        sources=sources,
        settings_overrides={
            "source_language": Language.FR,
            "output_languages": (Language.FR,),
        },
    )
    _seed(ctx.workspace, sources)
    result = Phase6TranslationHandler().execute(ctx, source=None)
    assert result.status is PhaseStatus.SUCCEEDED
    # Le consolidé thématique est copié tel quel (aucune hypothèse 1 source = 1 chap.).
    copied = (ctx.output_dir / "consolidated.fr.md").read_text(encoding="utf-8")
    assert copied == _THEMATIC_DOC
    assert result.cost_usd == 0.0


def test_phase7_polishes_thematic_doc(
    tmp_path: Path, make_generation_settings: Any
) -> None:
    polished = LLMResponse(
        content="# Cours consolidé (poli)",
        thinking_content=None,
        prompt_tokens=500,
        completion_tokens=500,
        cached_prompt_tokens=0,
        cost_usd=0.02,
    )
    ctx, _ = build_phase_context(
        tmp_path,
        make_generation_settings,
        llm_response=polished,
        settings_overrides={
            "source_language": Language.FR,
            "output_languages": (Language.FR,),
        },
    )
    ctx.output_dir.mkdir(parents=True, exist_ok=True)
    (ctx.output_dir / "consolidated.fr.md").write_text(_THEMATIC_DOC, encoding="utf-8")
    ctx.workspace.mkdir(parents=True, exist_ok=True)
    (ctx.workspace / "glossary_master.json").write_text(
        json.dumps({"terms": [{"term": "PIB", "definition": "..."}]}),
        encoding="utf-8",
    )
    result = Phase7CoherenceHandler().execute(ctx, source=None)
    assert result.status is PhaseStatus.SUCCEEDED
    assert (ctx.output_dir / "consolidated.fr.md").read_text(
        encoding="utf-8"
    ) == "# Cours consolidé (poli)"
