"""Enchaînements inter-communautés (idea-chains) : reduce LLM sur les *community reports*.

À partir des rapports de communautés (unités de raisonnement), un appel LLM propose des
**relations typées de haut niveau entre communautés**. Chaque relation est matérialisée
par une arête entre les **nœuds représentatifs** des communautés concernées (le nœud le
plus connecté de chaque communauté). C'est l'étape *global map-reduce* de GraphRAG :
elle capte les enchaînements transverses que l'extraction par unité ne voit pas.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import replace
from typing import Any

from fahmi2.domain.enums import EdgeType, Language
from fahmi2.domain.visuals import GraphEdge, KnowledgeGraph
from fahmi2.infra.llm.interface import JSON_OBJECT_RESPONSE_FORMAT
from fahmi2.infra.llm.invocation import parse_llm_json
from fahmi2.infra.llm.json_schema import (
    require_int,
    require_list,
    require_mapping,
    require_str,
)
from fahmi2.visuals._constants import MIN_COMMUNITIES_FOR_IDEA_CHAINS
from fahmi2.visuals.extractors._base import VisualsContext, invoke_visuals_llm

_STAGE = "idea_chains"
_TEMPLATE_NAME = "visuals_idea_chains"


def _representatives(graph: KnowledgeGraph) -> dict[int, str]:
    """Choisit le nœud représentatif (le plus connecté) de chaque communauté.

    Args:
        graph: Graphe (communautés + arêtes).

    Returns:
        Un mapping ``id de communauté -> id du nœud représentatif`` (degré max,
        départage par id).
    """
    degree: Counter[str] = Counter()
    for edge in graph.edges:
        degree[edge.source_id] += 1
        degree[edge.target_id] += 1
    representatives: dict[int, str] = {}
    for community in graph.communities:
        if not community.member_ids:
            continue
        representatives[community.id] = max(
            community.member_ids, key=lambda member_id: (degree[member_id], member_id)
        )
    return representatives


def _chain_edge(
    item: dict[str, Any],
    *,
    representatives: dict[int, str],
    context_label: str,
) -> GraphEdge | None:
    """Convertit une relation inter-communautés JSON en arête entre représentants.

    Args:
        item: Objet ``{source, target, type, label?}`` (ids de communautés).
        representatives: Mapping communauté → nœud représentatif.
        context_label: Libellé de contexte pour les erreurs de schéma.

    Returns:
        L'``GraphEdge`` correspondante, ou ``None`` si type inconnu, communauté
        inconnue, ou boucle.
    """
    type_str = require_str(item, "type", context_label=context_label)
    try:
        edge_type = EdgeType(type_str)
    except ValueError:
        return None
    source_id = representatives.get(require_int(item, "source", context_label=context_label))
    target_id = representatives.get(require_int(item, "target", context_label=context_label))
    if source_id is None or target_id is None or source_id == target_id:
        return None
    raw_label = item.get("label")
    label = raw_label.strip() if isinstance(raw_label, str) and raw_label.strip() else None
    return GraphEdge(
        source_id=source_id, target_id=target_id, edge_type=edge_type, label=label
    )


def generate_idea_chains(
    ctx: VisualsContext, graph: KnowledgeGraph, *, language: Language
) -> tuple[KnowledgeGraph, float]:
    """Ajoute au graphe les arêtes d'enchaînements inter-communautés (reduce LLM).

    Args:
        ctx: Contexte d'exécution.
        graph: Graphe dont les communautés ont un libellé/rapport.
        language: Langue du contenu (événements).

    Returns:
        ``(graphe_enrichi, coût_usd)``. Inchangé (coût 0) si moins de 2 communautés.
    """
    if len(graph.communities) < MIN_COMMUNITIES_FOR_IDEA_CHAINS:
        return graph, 0.0
    representatives = _representatives(graph)
    communities_payload = [
        {"id": community.id, "label": community.label, "report": community.report}
        for community in graph.communities
    ]
    response = invoke_visuals_llm(
        ctx,
        stage=_STAGE,
        language=language,
        user_prompt=ctx.prompts.render(_TEMPLATE_NAME, communities=communities_payload),
        response_format=JSON_OBJECT_RESPONSE_FORMAT,
    )
    mapping = require_mapping(
        parse_llm_json(
            response.content, context_label=_STAGE, finish_reason=response.finish_reason
        ),
        context_label=_STAGE,
    )
    existing = {(e.source_id, e.target_id, e.edge_type.value) for e in graph.edges}
    new_edges: list[GraphEdge] = []
    for index, raw in enumerate(
        require_list(mapping, "relations", context_label=_STAGE)
    ):
        item = require_mapping(raw, context_label=f"{_STAGE}.relations[{index}]")
        edge = _chain_edge(
            item,
            representatives=representatives,
            context_label=f"{_STAGE}.relations[{index}]",
        )
        if edge is None:
            continue
        key = (edge.source_id, edge.target_id, edge.edge_type.value)
        if key in existing:
            continue
        existing.add(key)
        new_edges.append(edge)
    return replace(graph, edges=graph.edges + tuple(new_edges)), response.cost_usd
