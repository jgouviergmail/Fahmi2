"""Tests de la résolution d'entités (glossaire + clustering + relations + extraits)."""

from __future__ import annotations

from fahmi2.domain.enums import EdgeType, NodeType
from fahmi2.domain.glossary import Term, parse_glossary_master_terms
from fahmi2.infra.embeddings._fakes import FakeEmbeddingProvider
from fahmi2.visuals._constants import EXCERPT_MAX_CHARS
from fahmi2.visuals.extractors.entity_resolver import resolve_graph
from fahmi2.visuals.extractors.graph_extractor import (
    GraphExtraction,
    RawEntity,
    RawRelation,
    build_glossary_skeleton,
    node_id,
)
from fahmi2.visuals.sources import TextUnit

_PATH = (1, 1)


def _glossary() -> tuple[Term, ...]:
    return parse_glossary_master_terms(
        {
            "terms": [
                {"term": "Actif", "definition": "Biens.", "aliases": ["emplois"],
                 "sources": []},
            ]
        }
    )


def _unit(text: str = "Le bilan oppose l'actif au passif.") -> TextUnit:
    return TextUnit(
        section_path=_PATH, title="Le bilan", anchor="11-le-bilan", text=text, part=0
    )


def _entity(label: str, node_type: NodeType, *, definition: str | None = None) -> RawEntity:
    return RawEntity(
        label=label,
        node_type=node_type,
        definition=definition,
        section_path=_PATH,
        chapter_title="Le bilan",
        anchor="11-le-bilan",
    )


def test_resolution_glossaire_alias_clustering_et_relations() -> None:
    glossary = _glossary()
    extraction = GraphExtraction(
        glossary_nodes=build_glossary_skeleton(glossary),
        raw_entities=(
            _entity("Actif", NodeType.CONCEPT),       # match terme glossaire
            _entity("emplois", NodeType.CONCEPT),     # match alias → même nœud
            _entity("Bilan comptable", NodeType.CONCEPT, definition="État."),
            _entity("Comptable bilan", NodeType.CONCEPT, definition="État."),  # fusion
            _entity("Cas Enron", NodeType.EXAMPLE),   # distinct
        ),
        raw_relations=(
            RawRelation("Cas Enron", "Bilan comptable", EdgeType.ILLUSTRATES, None),
            RawRelation("Bilan comptable", "Actif", EdgeType.PART_OF, "compose"),
            RawRelation("Inconnu", "Autre", EdgeType.RELATED, None),  # écartée
            RawRelation("Cas Enron", "Cas Enron", EdgeType.RELATED, None),  # boucle
        ),
        total_cost_usd=0.0,
    )

    nodes, edges = resolve_graph(
        extraction,
        glossary=glossary,
        units=(_unit(),),
        embedding_provider=FakeEmbeddingProvider(),
    )

    by_id = {n.id: n for n in nodes}
    actif_id = node_id(NodeType.GLOSSARY_TERM, "Actif")
    bilan_id = node_id(NodeType.CONCEPT, "Bilan comptable")
    enron_id = node_id(NodeType.EXAMPLE, "Cas Enron")
    # glossaire (1) + cluster bilan (1) + enron (1) = 3 nœuds.
    assert set(by_id) == {actif_id, bilan_id, enron_id}
    # le nœud glossaire a hérité d'un extrait (sections où il est détecté).
    assert by_id[actif_id].excerpts and by_id[actif_id].excerpts[0].section_path == _PATH
    # cluster fusionné : libellé canonique « Bilan comptable », définition conservée.
    assert by_id[bilan_id].label == "Bilan comptable"
    assert by_id[bilan_id].definition == "État."
    # relations résolues : illustrate + part_of (vers le nœud glossaire).
    pairs = {(e.source_id, e.target_id, e.edge_type) for e in edges}
    assert (enron_id, bilan_id, EdgeType.ILLUSTRATES) in pairs
    assert (bilan_id, actif_id, EdgeType.PART_OF) in pairs
    # relation inconnue + boucle écartées → exactement 2 arêtes.
    assert len(edges) == 2


def test_fallback_sans_embeddings_regroupe_par_libelle_normalise() -> None:
    extraction = GraphExtraction(
        glossary_nodes=(),
        raw_entities=(
            _entity("Bilan comptable", NodeType.CONCEPT),
            _entity("bilan  comptable", NodeType.CONCEPT),  # même slug
        ),
        raw_relations=(),
        total_cost_usd=0.0,
    )
    nodes, _ = resolve_graph(
        extraction, glossary=(), units=(_unit(),), embedding_provider=None
    )
    assert len(nodes) == 1


def test_extrait_tronque_a_la_constante() -> None:
    long_text = "mot " * 400  # bien au-delà de EXCERPT_MAX_CHARS
    extraction = GraphExtraction(
        glossary_nodes=(),
        raw_entities=(_entity("Concept", NodeType.CONCEPT),),
        raw_relations=(),
        total_cost_usd=0.0,
    )
    nodes, _ = resolve_graph(
        extraction, glossary=(), units=(_unit(long_text),), embedding_provider=None
    )
    excerpt = nodes[0].excerpts[0]
    assert len(excerpt.text) <= EXCERPT_MAX_CHARS + 1  # +1 pour l'ellipse
    assert excerpt.text.endswith("…")
