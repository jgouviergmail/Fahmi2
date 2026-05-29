"""Rapports de communauté : un libellé + une synthèse courte par communauté (LLM).

Pour chaque communauté détectée, un appel LLM produit un **libellé lisible** (titre
court) et un **rapport** (1-2 phrases de synthèse + idée-clé) à partir des libellés de
ses membres. Ces rapports ont un **double usage** : étiquette de la communauté dans
l'UI **et** unité de raisonnement pour les enchaînements inter-communautés (idea-chains).
"""

from __future__ import annotations

from dataclasses import replace

from fahmi2.domain.enums import Language
from fahmi2.domain.visuals import Community, KnowledgeGraph
from fahmi2.infra.llm.interface import JSON_OBJECT_RESPONSE_FORMAT
from fahmi2.infra.llm.invocation import parse_llm_json
from fahmi2.infra.llm.json_schema import require_mapping, require_str
from fahmi2.visuals.events import VisualsStructureStep
from fahmi2.visuals.extractors._base import (
    VisualsContext,
    invoke_visuals_llm,
    map_units_with_progress,
)

_STAGE = "community_report"
_TEMPLATE_NAME = "visuals_community_report"


def generate_community_reports(
    ctx: VisualsContext, graph: KnowledgeGraph, *, language: Language
) -> tuple[KnowledgeGraph, float]:
    """Renseigne le libellé et le rapport de chaque communauté du graphe.

    Args:
        ctx: Contexte d'exécution (provider, prompts, retry, bus, pause).
        graph: Graphe dont les communautés ont des libellés/rapports vides.
        language: Langue du contenu (pour les événements ; le LLM répond dans la
            langue des libellés fournis).

    Returns:
        ``(graphe_mis_à_jour, coût_usd)`` : communautés enrichies de ``label``/``report``.
    """
    if not graph.communities:
        return graph, 0.0
    label_by_id = {node.id: node.label for node in graph.nodes}
    # Communautés traitées en parallèle (borné par llm_workers), ordre préservé.
    results = map_units_with_progress(
        ctx,
        graph.communities,
        lambda community: _report_community(
            ctx, community, language=language, label_by_id=label_by_id
        ),
        step=VisualsStructureStep.COMMUNITY_REPORTS,
    )
    reported = [community for community, _ in results]
    total_cost = sum(cost for _, cost in results)
    return replace(graph, communities=tuple(reported)), total_cost


def _report_community(
    ctx: VisualsContext,
    community: Community,
    *,
    language: Language,
    label_by_id: dict[str, str],
) -> tuple[Community, float]:
    """Produit le libellé + rapport d'une **seule** communauté.

    Args:
        ctx: Contexte d'exécution.
        community: Communauté à étiqueter.
        language: Langue du contenu (événements ; le LLM répond dans la langue des
            libellés fournis).
        label_by_id: Index ``id de nœud -> libellé`` (membres de la communauté).

    Returns:
        ``(communauté enrichie de label/report, coût)``.
    """
    member_labels = [
        label_by_id[member_id]
        for member_id in community.member_ids
        if member_id in label_by_id
    ]
    user_prompt = ctx.prompts.render(_TEMPLATE_NAME, member_labels=member_labels)
    response = invoke_visuals_llm(
        ctx,
        stage=_STAGE,
        language=language,
        user_prompt=user_prompt,
        response_format=JSON_OBJECT_RESPONSE_FORMAT,
    )
    context_label = f"{_STAGE}:{community.id}"
    mapping = require_mapping(
        parse_llm_json(
            response.content,
            context_label=context_label,
            finish_reason=response.finish_reason,
        ),
        context_label=context_label,
    )
    return (
        replace(
            community,
            label=require_str(mapping, "label", context_label=context_label),
            report=require_str(mapping, "report", context_label=context_label),
        ),
        response.cost_usd,
    )
