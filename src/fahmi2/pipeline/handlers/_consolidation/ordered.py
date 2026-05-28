"""Stratégie de consolidation ``ORDERED`` (comportement historique).

Opère en deux sous-étapes internes :

1. **Pré-consolidation** : pour chaque source, le LLM produit un résumé condensé
   (titre, plan, idées-clés) via ``phase_5_video_summary`` — carte mentale pour le
   rédacteur en chef, non insérée dans le document final.
2. **Consolidation globale** : un unique appel ``phase_5_consolidation`` produit les
   *méta-éléments* (titre, résumé exécutif, introduction, conclusion).

Le document final assemble ces méta-éléments **plus** les contenus structurés de
chaque source **recopiés tels quels** (aucune perte de fidélité), 1 source =
1 chapitre, dans l'ordre des sources. La renumérotation et le sommaire sont
déterministes (cf. ``_base``).
"""

from __future__ import annotations

import json
from typing import Any

from fahmi2.core.concurrency import map_bounded
from fahmi2.domain.enums import PhaseId
from fahmi2.infra.llm.interface import JSON_OBJECT_RESPONSE_FORMAT
from fahmi2.pipeline.handlers._base import (
    invoke_llm,
    language_label,
    parse_json_response,
    style_label,
)
from fahmi2.pipeline.handlers._consolidation._base import (
    ConsolidationResult,
    ConsolidationStrategy,
    _Chapter,
    assemble_document,
    demote_chapter_h1,
    renumber_subheadings,
    strip_existing_numbering,
)
from fahmi2.pipeline.phase_handler import PhaseContext

TEMPLATE_VIDEO_SUMMARY = "phase_5_video_summary"
TEMPLATE_CONSOLIDATION = "phase_5_consolidation"


class OrderedConsolidationStrategy(ConsolidationStrategy):
    """Mode ORDERED : 1 source = 1 chapitre, contenu recopié dans l'ordre."""

    def consolidate(
        self, ctx: PhaseContext, structured_by_source: dict[str, str]
    ) -> ConsolidationResult:
        """Consolide en préservant l'ordre des sources.

        Args:
            ctx: Contexte d'exécution.
            structured_by_source: Markdown structuré par ``source_id`` (ordre
                des sources du run).

        Returns:
            ``ConsolidationResult`` (markdown + coût cumulé).
        """
        # Les résumés par source sont indépendants : exécution parallèle bornée
        # (ordre des résultats préservé → assemblage déterministe).
        summary_results = map_bounded(
            lambda kv: self._summarize_one(ctx, kv),
            list(structured_by_source.items()),
            max_workers=ctx.settings.parallelism.llm_workers,
            pause_token=ctx.pause_token,
        )
        summaries = [summary for summary, _ in summary_results]
        total_cost = sum(cost for _, cost in summary_results)

        meta, meta_cost = self._produce_meta(ctx, summaries)
        total_cost += meta_cost

        titles_by_source = {
            s.get("source_id", ""): s.get("title", "") for s in summaries
        }
        chapters = build_chapters(structured_by_source, titles_by_source)
        markdown = assemble_document(meta, chapters)
        return ConsolidationResult(consolidated_markdown=markdown, cost_usd=total_cost)

    def _summarize_one(
        self, ctx: PhaseContext, item: tuple[str, str]
    ) -> tuple[dict[str, Any], float]:
        """Résume une source (clé = ``source_id``), pour exécution parallèle.

        Args:
            ctx: Contexte.
            item: Couple ``(source_id, structured_markdown)``.

        Returns:
            ``(summary_avec_source_id, cost_usd)``.
        """
        source_id, structured_md = item
        summary, cost = self._summarize_source(ctx, structured_md)
        summary["source_id"] = source_id
        return summary, cost

    def _summarize_source(
        self, ctx: PhaseContext, structured_md: str
    ) -> tuple[dict[str, Any], float]:
        """Produit le résumé condensé d'une source via le LLM.

        Args:
            ctx: Contexte.
            structured_md: Document Markdown structuré de la source.

        Returns:
            ``(payload_dict, cost_usd)``.
        """
        prompt = ctx.prompts.render(
            TEMPLATE_VIDEO_SUMMARY,
            output_language_label=language_label(ctx.settings.source_language),
            structured_markdown=structured_md,
        )
        response = invoke_llm(
            ctx,
            phase_id=PhaseId.CONSOLIDATION,
            system_prompt=None,
            user_prompt=prompt,
            response_format=JSON_OBJECT_RESPONSE_FORMAT,
        )
        payload = parse_json_response(
            response.content,
            phase_id=PhaseId.CONSOLIDATION,
            finish_reason=response.finish_reason,
        )
        return dict(payload), response.cost_usd

    def _produce_meta(
        self, ctx: PhaseContext, summaries: list[dict[str, Any]]
    ) -> tuple[dict[str, Any], float]:
        """Produit les méta-éléments du document consolidé.

        Args:
            ctx: Contexte.
            summaries: Résumés par source.

        Returns:
            ``(meta_dict, cost_usd)``.
        """
        prompt = ctx.prompts.render(
            TEMPLATE_CONSOLIDATION,
            output_language_label=language_label(ctx.settings.source_language),
            style_label=style_label(ctx.settings.style_preset),
            style_directives=ctx.settings.style_directives,
            summaries_json=json.dumps(summaries, ensure_ascii=False, indent=2),
        )
        response = invoke_llm(
            ctx,
            phase_id=PhaseId.CONSOLIDATION,
            system_prompt=None,
            user_prompt=prompt,
            response_format=JSON_OBJECT_RESPONSE_FORMAT,
        )
        payload = parse_json_response(
            response.content,
            phase_id=PhaseId.CONSOLIDATION,
            finish_reason=response.finish_reason,
        )
        return dict(payload), response.cost_usd


def build_chapters(
    structured_by_source: dict[str, str],
    titles_by_source: dict[str, Any],
) -> list[_Chapter]:
    """Construit la liste ordonnée des chapitres consolidés et renumérotés.

    Args:
        structured_by_source: Markdown structuré par source (ordre préservé).
        titles_by_source: Titres extraits des résumés (clé = source_id).

    Returns:
        Liste de ``_Chapter`` prêts à être sérialisés.
    """
    chapters: list[_Chapter] = []
    for index, (source_id, structured) in enumerate(
        structured_by_source.items(), start=1
    ):
        raw_title = str(titles_by_source.get(source_id, "")).strip()
        title = strip_existing_numbering(raw_title) or f"Chapitre {index}"
        demoted = demote_chapter_h1(structured)
        renumbered_body, subheadings = renumber_subheadings(demoted, index)
        chapters.append(
            _Chapter(
                index=index,
                title=title,
                body=renumbered_body,
                subheadings=tuple(subheadings),
            )
        )
    return chapters
