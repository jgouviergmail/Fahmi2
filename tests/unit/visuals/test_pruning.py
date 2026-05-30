"""Tests de l'élagage de la carte par densité (sélection par arêtes)."""

from __future__ import annotations

from fahmi2.domain.enums import EdgeType, NodeType, SupportDensity
from fahmi2.domain.visuals import GraphEdge, GraphNode
from fahmi2.visuals._constants import MAP_NODE_CAP_BY_DENSITY
from fahmi2.visuals._pruning import prune_knowledge_graph


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


def _path_graph(n: int) -> tuple[tuple[GraphNode, ...], tuple[GraphEdge, ...]]:
    """Chaîne n0-n1-...-n(n-1) : tous connectés, degrés 1/2."""
    nodes = tuple(_node(f"n{i}") for i in range(n))
    edges = tuple(_edge(f"n{i}", f"n{i + 1}") for i in range(n - 1))
    return nodes, edges


def _residual_isolated(
    nodes: tuple[GraphNode, ...], edges: tuple[GraphEdge, ...]
) -> int:
    degree = {node.id: 0 for node in nodes}
    for edge in edges:
        degree[edge.source_id] += 1
        degree[edge.target_id] += 1
    return sum(1 for value in degree.values() if value == 0)


def test_isoles_supprimes_a_tous_les_niveaux() -> None:
    path_nodes, edges = _path_graph(5)
    nodes = (*path_nodes, _node("iso1"), _node("iso2"))
    for density in SupportDensity:
        kept_nodes, _ = prune_knowledge_graph(nodes, edges, density=density)
        kept_ids = {node.id for node in kept_nodes}
        assert "iso1" not in kept_ids
        assert "iso2" not in kept_ids


def test_dense_garde_tout_le_connexe() -> None:
    nodes, edges = _path_graph(20)
    kept_nodes, kept_edges = prune_knowledge_graph(
        nodes, edges, density=SupportDensity.DENSE
    )
    assert len(kept_nodes) == 20
    assert len(kept_edges) == 19


def test_light_applique_le_plafond() -> None:
    nodes, edges = _path_graph(300)
    kept_nodes, _ = prune_knowledge_graph(nodes, edges, density=SupportDensity.LIGHT)
    assert len(kept_nodes) == MAP_NODE_CAP_BY_DENSITY[SupportDensity.LIGHT]


def test_standard_applique_le_plafond() -> None:
    nodes, edges = _path_graph(300)
    kept_nodes, _ = prune_knowledge_graph(nodes, edges, density=SupportDensity.STANDARD)
    assert len(kept_nodes) == MAP_NODE_CAP_BY_DENSITY[SupportDensity.STANDARD]


def test_ratio_applique_sous_le_plafond() -> None:
    # 100 connectés, 25 % = 25 (< plafond 40, > plancher 12).
    nodes, edges = _path_graph(100)
    kept_nodes, _ = prune_knowledge_graph(nodes, edges, density=SupportDensity.LIGHT)
    assert len(kept_nodes) == 25


def test_plancher_applique() -> None:
    # 8 connectés : 25 % = 2 → relevé au plancher min(MAP_MIN_NODES, 8) = 8.
    nodes, edges = _path_graph(8)
    kept_nodes, _ = prune_knowledge_graph(nodes, edges, density=SupportDensity.LIGHT)
    assert len(kept_nodes) == 8


def test_aucun_isole_residuel_foret_d_etoiles() -> None:
    # 3 hubs (degré 4) non interconnectés, chacun 4 feuilles (degré 1).
    nodes_list = [_node(f"h{h}") for h in range(3)]
    edges_list = []
    for h in range(3):
        for leaf in range(4):
            nodes_list.append(_node(f"h{h}_l{leaf}"))
            edges_list.append(_edge(f"h{h}", f"h{h}_l{leaf}"))
    nodes, edges = tuple(nodes_list), tuple(edges_list)
    kept_nodes, kept_edges = prune_knowledge_graph(
        nodes, edges, density=SupportDensity.LIGHT
    )
    assert len(kept_nodes) > 0  # jamais vide
    assert _residual_isolated(kept_nodes, kept_edges) == 0


def test_aretes_induites_uniquement() -> None:
    nodes, edges = _path_graph(100)
    kept_nodes, kept_edges = prune_knowledge_graph(
        nodes, edges, density=SupportDensity.LIGHT
    )
    kept_ids = {node.id for node in kept_nodes}
    for edge in kept_edges:
        assert edge.source_id in kept_ids
        assert edge.target_id in kept_ids


def test_deterministe() -> None:
    nodes, edges = _path_graph(120)
    first = prune_knowledge_graph(nodes, edges, density=SupportDensity.LIGHT)
    second = prune_knowledge_graph(nodes, edges, density=SupportDensity.LIGHT)
    assert [n.id for n in first[0]] == [n.id for n in second[0]]
    assert [(e.source_id, e.target_id) for e in first[1]] == [
        (e.source_id, e.target_id) for e in second[1]
    ]


def test_petit_graphe_connexe_jamais_vide() -> None:
    # 2 nœuds, 1 arête : connected = 2 → plancher 2 → les deux conservés (le budget
    # ne peut pas tomber à 1 puisqu'une arête relie 2 nœuds distincts) ; jamais vide.
    nodes, edges = _path_graph(2)
    for density in SupportDensity:
        kept_nodes, kept_edges = prune_knowledge_graph(nodes, edges, density=density)
        assert len(kept_nodes) == 2
        assert len(kept_edges) == 1


def test_graphe_sans_arete_inchange() -> None:
    nodes = (_node("a"), _node("b"), _node("c"))
    kept_nodes, kept_edges = prune_knowledge_graph(
        nodes, (), density=SupportDensity.LIGHT
    )
    assert kept_nodes == nodes
    assert kept_edges == ()
