"""Élagage de la carte de connaissances par densité (sélection par arêtes).

Réduit le graphe résolu aux nœuds les plus **structurants** (les mieux connectés)
selon le niveau de densité. La **sélection par arêtes** (classées par somme des degrés
de leurs extrémités, accumulées jusqu'au budget de nœuds) garantit **par construction**
qu'aucun nœud conservé n'est isolé — jamais de carte vide tant qu'il existe une arête.
Module pur (sans Qt / réseau / LLM), déterministe.
"""

from __future__ import annotations

import math
from collections import Counter

from fahmi2.domain.enums import SupportDensity
from fahmi2.domain.visuals import GraphEdge, GraphNode
from fahmi2.visuals._constants import (
    MAP_CONNECTED_NODE_RATIO_BY_DENSITY,
    MAP_MIN_NODES,
    MAP_NODE_CAP_BY_DENSITY,
)


def _node_degrees(edges: tuple[GraphEdge, ...]) -> Counter[str]:
    """Degré (nombre d'arêtes incidentes) de chaque nœud **connecté**.

    Les nœuds isolés (absents de toute arête) n'apparaissent pas dans le résultat ;
    le nombre de nœuds connectés est donc ``len(...)``.

    Args:
        edges: Arêtes du graphe.

    Returns:
        Un ``Counter`` ``id de nœud -> degré`` restreint aux nœuds connectés.
    """
    degree: Counter[str] = Counter()
    for edge in edges:
        degree[edge.source_id] += 1
        degree[edge.target_id] += 1
    return degree


def _target_node_count(connected_count: int, density: SupportDensity) -> int:
    """Nombre cible de nœuds conservés (ratio borné par plancher et plafond).

    Args:
        connected_count: Nombre de nœuds connectés (degré ≥ 1).
        density: Niveau de densité.

    Returns:
        La cible ``clamp(ceil(ratio * N), min(MAP_MIN_NODES, N), plafond, N)``.
    """
    ratio = MAP_CONNECTED_NODE_RATIO_BY_DENSITY[density]
    floor = min(MAP_MIN_NODES, connected_count)
    target = max(math.ceil(ratio * connected_count), floor)
    cap = MAP_NODE_CAP_BY_DENSITY[density]
    if cap is not None:
        target = min(target, cap)
    return min(target, connected_count)


def prune_knowledge_graph(
    nodes: tuple[GraphNode, ...],
    edges: tuple[GraphEdge, ...],
    *,
    density: SupportDensity,
) -> tuple[tuple[GraphNode, ...], tuple[GraphEdge, ...]]:
    """Élague la carte aux nœuds les plus connectés (sélection par arêtes).

    Retire d'abord les nœuds isolés, puis conserve les arêtes les plus « fortes »
    (somme des degrés des extrémités) en accumulant leurs nœuds jusqu'au budget de
    densité ; les arêtes finales sont le sous-graphe induit sur les nœuds retenus.

    Args:
        nodes: Nœuds résolus du graphe (langue de structure).
        edges: Arêtes résolues du graphe.
        density: Niveau de densité pilotant la taille conservée.

    Returns:
        ``(nœuds conservés, arêtes induites)``. Invariant : tout nœud conservé porte au
        moins une arête conservée. Garde-fou : un graphe **sans arête** est retourné
        inchangé (pas de carte vide).
    """
    if not edges:
        return nodes, edges
    degree = _node_degrees(edges)
    connected_count = len(degree)
    target = _target_node_count(connected_count, density)
    ranked_edges = sorted(
        edges,
        key=lambda edge: (
            -(degree[edge.source_id] + degree[edge.target_id]),
            min(edge.source_id, edge.target_id),
            max(edge.source_id, edge.target_id),
        ),
    )
    kept_ids: set[str] = set()
    for edge in ranked_edges:
        if len(kept_ids) >= target:
            break
        new_ids = {edge.source_id, edge.target_id} - kept_ids
        if len(kept_ids) + len(new_ids) <= target:
            kept_ids |= new_ids
    kept_nodes = tuple(node for node in nodes if node.id in kept_ids)
    kept_edges = tuple(
        edge
        for edge in edges
        if edge.source_id in kept_ids and edge.target_id in kept_ids
    )
    return kept_nodes, kept_edges
