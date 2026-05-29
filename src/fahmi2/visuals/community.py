"""Détection de communautés (Louvain) et assemblage du ``KnowledgeGraph``.

Regroupe les nœuds en **communautés thématiques** par modularité (algorithme de
Louvain, ``networkx``, **déterministe** via une graine fixe). Chaque nœud reçoit son
``community_path`` et l'on construit les ``Community`` (libellés/rapports remplis par
l'étape suivante). Aucun appel LLM ici : le clustering est purement structurel.
"""

from __future__ import annotations

from dataclasses import replace

import networkx as nx
from networkx.algorithms.community import louvain_communities

from fahmi2.domain.enums import Language
from fahmi2.domain.visuals import Community, GraphEdge, GraphNode, KnowledgeGraph
from fahmi2.visuals._constants import LOUVAIN_SEED

_WEIGHT = "weight"


def _build_nx_graph(
    nodes: tuple[GraphNode, ...], edges: tuple[GraphEdge, ...]
) -> nx.Graph:
    """Construit un graphe ``networkx`` non orienté pondéré depuis nœuds + arêtes.

    Args:
        nodes: Nœuds (tous ajoutés, même isolés).
        edges: Arêtes (le poids agrège les relations multiples entre deux nœuds).

    Returns:
        Le graphe ``networkx``.
    """
    graph = nx.Graph()
    for node in nodes:
        graph.add_node(node.id)
    for edge in edges:
        if graph.has_edge(edge.source_id, edge.target_id):
            graph[edge.source_id][edge.target_id][_WEIGHT] += 1.0
        else:
            graph.add_edge(edge.source_id, edge.target_id, **{_WEIGHT: 1.0})
    return graph


def detect_communities(
    nodes: tuple[GraphNode, ...], edges: tuple[GraphEdge, ...]
) -> tuple[tuple[GraphNode, ...], tuple[Community, ...]]:
    """Détecte les communautés (Louvain) et renseigne le ``community_path`` des nœuds.

    Args:
        nodes: Nœuds du graphe.
        edges: Arêtes du graphe.

    Returns:
        ``(nœuds_mis_à_jour, communautés)`` ; les ``Community`` portent ``label`` et
        ``report`` vides (remplis par l'étape de reporting). ``((), ())`` si aucun nœud.
    """
    if not nodes:
        return (), ()
    graph = _build_nx_graph(nodes, edges)
    # Choix V1 **assumé** : partition **plate** (un seul niveau) via
    # ``louvain_communities`` — toutes les ``Community`` ont ``level=0`` /
    # ``parent_id=None`` et un ``community_path`` à un seul entier. La spec évoquait un
    # dendrogramme multi-niveaux (``louvain_partitions``) ; cette hiérarchie est
    # **volontairement non livrée** (rendu plus simple, pas de besoin avéré). Les champs
    # ``level``/``parent_id`` du domaine restent en place (compatibilité ascendante si
    # la hiérarchie est introduite plus tard).
    partition = louvain_communities(graph, seed=LOUVAIN_SEED, weight=_WEIGHT)
    community_of: dict[str, int] = {}
    communities: list[Community] = []
    for index, members in enumerate(partition):
        for member_id in members:
            community_of[member_id] = index
        communities.append(
            Community(
                id=index,
                label="",
                report="",
                level=0,
                member_ids=tuple(sorted(members)),
                parent_id=None,
            )
        )
    updated_nodes = tuple(
        replace(node, community_path=(community_of[node.id],)) for node in nodes
    )
    return updated_nodes, tuple(communities)


def assemble_graph(
    nodes: tuple[GraphNode, ...],
    edges: tuple[GraphEdge, ...],
    *,
    language: Language,
) -> KnowledgeGraph:
    """Assemble le ``KnowledgeGraph`` final (communautés détectées incluses).

    Args:
        nodes: Nœuds résolus.
        edges: Arêtes résolues.
        language: Langue du graphe.

    Returns:
        Le ``KnowledgeGraph`` (nœuds avec ``community_path`` + communautés).
    """
    updated_nodes, communities = detect_communities(nodes, edges)
    return KnowledgeGraph(
        nodes=updated_nodes,
        edges=edges,
        communities=communities,
        language=language,
    )
