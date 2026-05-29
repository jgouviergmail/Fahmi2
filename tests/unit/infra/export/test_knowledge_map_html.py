"""Tests du rendu HTML autonome de la carte de connaissances (chemin de données)."""

from __future__ import annotations

import json
import re
from typing import Any

from fahmi2.domain.enums import EdgeType, Language, NodeType
from fahmi2.domain.visuals import GraphEdge, GraphNode, KnowledgeGraph, SourceExcerpt
from fahmi2.infra.export.knowledge_map_html import render_knowledge_map_html
from fahmi2.visuals.community import assemble_graph


def _graph() -> KnowledgeGraph:
    nodes = (
        GraphNode(
            id="concept:bilan", label="Bilan", node_type=NodeType.CONCEPT,
            definition="Photo du patrimoine.",
            excerpts=(SourceExcerpt(text="Le bilan oppose actif et passif.",
                                    section_path=(2, 1), chapter_title="Le bilan",
                                    anchor="21-le-bilan"),),
            chapter_anchor="21-le-bilan", community_path=(),
        ),
        GraphNode(
            id="glossary_term:actif", label="Actif", node_type=NodeType.GLOSSARY_TERM,
            definition="Biens.", excerpts=(), chapter_anchor=None, community_path=(),
        ),
    )
    edges = (GraphEdge("concept:bilan", "glossary_term:actif", EdgeType.PART_OF, None),)
    return assemble_graph(nodes, edges, language=Language.FR)


def _embedded_data(html: str) -> Any:  # noqa: ANN401
    match = re.search(
        r'<script id="km-data" type="application/json">(.*?)</script>', html, re.DOTALL
    )
    assert match is not None
    return json.loads(match.group(1).replace("<\\/", "</"))


def test_rendu_document_complet_et_tokens_remplaces() -> None:
    html = render_knowledge_map_html(_graph())
    assert html.startswith("<!DOCTYPE html>")
    assert 'lang="fr"' in html
    # aucun token de template (``@@MAJUSCULES@@``) non remplacé (le JS vendorisé
    # peut contenir « @@iterator » en minuscules, qui ne matche pas).
    assert re.search(r"@@[A-Z_]+@@", html) is None
    assert "Carte de connaissances" in html
    assert "Concept" in html and "Terme" in html  # libellés FR des filtres


def test_donnees_embarquees_valides() -> None:
    data = _embedded_data(render_knowledge_map_html(_graph()))
    labels = {n["label"] for n in data["nodes"]}
    assert labels == {"Bilan", "Actif"}
    assert data["i18n"]["edgeLabels"]["part_of"] == "composé de"
    assert len(data["communities"]) >= 1


def test_autonomie_aucune_reference_externe() -> None:
    html = render_knowledge_map_html(_graph())
    assert 'src="http' not in html
    assert 'href="http' not in html
    # bibliothèques inlinées.
    assert "vendored: cytoscape.min.js" in html


def test_design_system_clair_et_sombre() -> None:
    html = render_knowledge_map_html(_graph())
    assert 'data-theme="dark"' in html  # palette sombre présente dans le CSS
    assert "--concept" in html and "--idea" in html


def test_langue_anglaise() -> None:
    graph = assemble_graph(
        (GraphNode(id="concept:x", label="X", node_type=NodeType.CONCEPT,
                   definition=None, excerpts=(), chapter_anchor=None, community_path=()),),
        (),
        language=Language.EN,
    )
    html = render_knowledge_map_html(graph)
    assert 'lang="en"' in html
    assert "Knowledge map" in html
