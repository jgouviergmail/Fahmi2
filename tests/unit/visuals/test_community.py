"""Tests de la détection de communautés (Louvain) et de l'assemblage du graphe."""

from __future__ import annotations

from fahmi2.domain.enums import EdgeType, Language, NodeType
from fahmi2.domain.visuals import GraphEdge, GraphNode
from fahmi2.visuals.community import assemble_graph, detect_communities


def _node(node_id: str) -> GraphNode:
    return GraphNode(
        id=node_id,
        label=node_id,
        node_type=NodeType.CONCEPT,
        definition=None,
        excerpts=(),
        chapter_anchor=None,
        community_path=(),
    )


def _edge(source: str, target: str) -> GraphEdge:
    return GraphEdge(
        source_id=source, target_id=target, edge_type=EdgeType.RELATED, label=None
    )


def _two_triangles() -> tuple[tuple[GraphNode, ...], tuple[GraphEdge, ...]]:
    nodes = tuple(_node(n) for n in ("a1", "a2", "a3", "b1", "b2", "b3"))
    edges = (
        _edge("a1", "a2"),
        _edge("a2", "a3"),
        _edge("a1", "a3"),
        _edge("b1", "b2"),
        _edge("b2", "b3"),
        _edge("b1", "b3"),
    )
    return nodes, edges


def test_detect_communities_vide() -> None:
    assert detect_communities((), ()) == ((), ())


def test_detect_communities_separe_deux_clusters() -> None:
    nodes, edges = _two_triangles()
    updated, communities = detect_communities(nodes, edges)
    assert len(communities) == 2
    # chaque nœud a un community_path de longueur 1.
    assert all(len(n.community_path) == 1 for n in updated)
    # les deux triangles tombent dans deux communautés distinctes.
    path_of = {n.id: n.community_path[0] for n in updated}
    assert path_of["a1"] == path_of["a2"] == path_of["a3"]
    assert path_of["b1"] == path_of["b2"] == path_of["b3"]
    assert path_of["a1"] != path_of["b1"]
    # les member_ids couvrent l'ensemble des nœuds, sans recouvrement.
    members = [m for c in communities for m in c.member_ids]
    assert sorted(members) == ["a1", "a2", "a3", "b1", "b2", "b3"]


def test_detect_communities_deterministe() -> None:
    nodes, edges = _two_triangles()
    first, _ = detect_communities(nodes, edges)
    second, _ = detect_communities(nodes, edges)
    assert [n.community_path for n in first] == [n.community_path for n in second]


def test_assemble_graph_produit_un_knowledge_graph_valide() -> None:
    nodes, edges = _two_triangles()
    graph = assemble_graph(nodes, edges, language=Language.FR)
    assert graph.language is Language.FR
    assert len(graph.nodes) == 6
    assert len(graph.communities) == 2
    assert len(graph.edges) == 6
