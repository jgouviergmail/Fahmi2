"""Tests du rendu HTML autonome de la galerie de schémas (chemin de données)."""

from __future__ import annotations

import json
import re
from typing import Any

from fahmi2.domain.enums import DiagramType, Language
from fahmi2.domain.visuals import (
    ComparisonTable,
    Diagram,
    DiagramBoard,
    DiagramLink,
    DiagramNode,
    SourceExcerpt,
    TimelineEvent,
)
from fahmi2.infra.export.diagram_board_html import render_diagram_board_html

_EXCERPT = SourceExcerpt(
    text="Passage source du chapitre.", section_path=(2, 1),
    chapter_title="Le bilan", anchor="21-le-bilan",
)


def _board() -> DiagramBoard:
    flow = Diagram(
        id="d1", title="Grille en 3 étapes", diagram_type=DiagramType.FLOWCHART,
        nodes=(DiagramNode("a", "Étape 1", "start"), DiagramNode("b", "Étape 2", None)),
        links=(DiagramLink("a", "b", "puis"),), events=(), comparison=None,
        caption="Le processus.", chapter_anchor="21-le-bilan", excerpts=(_EXCERPT,),
    )
    timeline = Diagram(
        id="d2", title="Chute d'Enron", diagram_type=DiagramType.TIMELINE,
        nodes=(), links=(),
        events=(TimelineEvent("2000", "Apogée", None),
                TimelineEvent("2001", "Faillite", "Scandale comptable.")),
        comparison=None, caption="", chapter_anchor="23-enron", excerpts=(),
    )
    comparison = Diagram(
        id="d3", title="Bilan vs CR", diagram_type=DiagramType.COMPARISON,
        nodes=(), links=(), events=(),
        comparison=ComparisonTable(columns=("Critère", "Bilan", "Compte de résultat"),
                                   rows=(("Période", "Date", "Exercice"),)),
        caption="", chapter_anchor="21-le-bilan", excerpts=(_EXCERPT,),
    )
    return DiagramBoard(diagrams=(flow, timeline, comparison), language=Language.FR)


def _graph_specs(html: str) -> list[Any]:
    specs = []
    for raw in re.findall(r'data-graph="([^"]*)"', html):
        unescaped = (
            raw.replace("&quot;", '"').replace("&lt;", "<")
            .replace("&gt;", ">").replace("&amp;", "&")
        )
        specs.append(json.loads(unescaped))
    return specs


def test_document_complet_et_tokens_remplaces() -> None:
    html = render_diagram_board_html(_board())
    assert html.startswith("<!DOCTYPE html>")
    assert 'lang="fr"' in html
    assert re.search(r"@@[A-Z_]+@@", html) is None
    assert "Schémas &amp; diagrammes" in html or "Schémas & diagrammes" in html


def test_cartes_par_type_et_chips() -> None:
    html = render_diagram_board_html(_board())
    assert 'data-type="flowchart"' in html
    assert 'data-type="timeline"' in html
    assert 'data-type="comparison"' in html
    assert "Processus" in html and "Chronologie" in html and "Comparaison" in html


def test_graphe_embarque_modele_json() -> None:
    specs = _graph_specs(render_diagram_board_html(_board()))
    assert len(specs) == 1  # seul le flowchart est un diagramme « graphe »
    spec = specs[0]
    assert [n["label"] for n in spec["nodes"]] == ["Étape 1", "Étape 2"]
    assert spec["links"][0]["label"] == "puis"
    assert spec["cyclic"] is False


def test_timeline_et_comparison_rendus_en_html() -> None:
    html = render_diagram_board_html(_board())
    assert '<div class="timeline">' in html
    assert "Faillite" in html and "Scandale comptable." in html
    assert "<table>" in html
    assert "<th>Critère</th>" in html


def test_autonomie_et_bundle_reduit() -> None:
    html = render_diagram_board_html(_board())
    assert 'src="http' not in html and 'href="http' not in html
    assert "vendored: cytoscape.min.js" in html
    assert "vendored: dagre.min.js" in html
    # le board n'embarque pas fcose / expand-collapse (non utilisés).
    assert "vendored: cytoscape-fcose.js" not in html
    assert "vendored: cytoscape-expand-collapse.js" not in html


def test_extrait_source_present() -> None:
    html = render_diagram_board_html(_board())
    assert "Extrait source · § Le bilan" in html
    assert "Passage source du chapitre." in html


def test_graphe_hauteur_adaptative_au_nombre_de_noeuds() -> None:
    # Un graphe « graphe » reçoit une hauteur inline ; un graphe plus dense est plus
    # haut (lisibilité), borné au plafond.
    def _flow(n: int) -> Diagram:
        nodes = tuple(DiagramNode(f"n{i}", f"Étape {i}", None) for i in range(n))
        links = tuple(DiagramLink(f"n{i}", f"n{i + 1}", "") for i in range(n - 1))
        return Diagram(
            id=f"f{n}", title=f"Flux {n}", diagram_type=DiagramType.FLOWCHART,
            nodes=nodes, links=links, events=(), comparison=None, caption="",
            chapter_anchor="1-x", excerpts=(),
        )

    small = render_diagram_board_html(DiagramBoard(diagrams=(_flow(3),), language=Language.FR))
    big = render_diagram_board_html(DiagramBoard(diagrams=(_flow(8),), language=Language.FR))

    def _height(html: str) -> int:
        match = re.search(r'class="diagram" style="height:(\d+)px"', html)
        assert match is not None
        return int(match.group(1))

    assert _height(big) > _height(small)
    assert _height(big) <= 560  # borné au plafond


def test_comparison_sans_hauteur_inline() -> None:
    # Les diagrammes linéaires gardent la hauteur CSS par défaut (pas de style inline).
    html = render_diagram_board_html(_board())
    assert '<div class="diagram"><div class="cmp">' in html
    assert '<div class="diagram"><div class="timeline">' in html
