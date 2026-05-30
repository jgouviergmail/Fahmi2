"""Rendu de la carte de connaissances en page HTML **pleinement autonome**.

Sérialise un ``KnowledgeGraph`` en données JSON inline, puis assemble un fichier HTML
unique (CSS + bibliothèques JS vendorisées + JS applicatif + données, tout inliné) à
partir d'un template et des assets de ``_assets/visuals``. Les libellés d'interface
sont fournis dans la **langue du graphe** (scripts latins : fr/en/de/es/it).
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from fahmi2.domain.enums import Language
from fahmi2.domain.languages import is_rtl
from fahmi2.domain.visuals import KnowledgeGraph
from fahmi2.infra.export._visuals_assets import (
    LAYOUT_STORE_JS,
    VISUALS_TOKENS_CSS,
    build_storage_key,
    read_visuals_asset,
    vendored_scripts_html,
)

_TEMPLATE = "knowledge_map.html.template"
_CSS = "knowledge_map.css"
_JS = "knowledge_map.js"

#: Préfixe namespacé de la clé localStorage de persistance des positions de la carte
#: (le format complet — langue + hash + version — est assemblé par ``build_storage_key``).
_STORAGE_KEY_PREFIX = "fahmi2:visuals:knowledge_map"


def _storage_key(graph: KnowledgeGraph) -> str:
    """Clé localStorage de la carte (namespace + langue + hash des ids de nœuds).

    Args:
        graph: Graphe rendu.

    Returns:
        ``fahmi2:visuals:knowledge_map:<langue>:<hash8>:v1`` — le hash change si
        l'ensemble des nœuds change (régénération), invalidant les positions périmées.
    """
    hash_source = "\n".join(sorted(node.id for node in graph.nodes))
    return build_storage_key(_STORAGE_KEY_PREFIX, graph.language.value, hash_source)


@dataclass(frozen=True)
class _KmStrings:
    """Libellés d'interface localisés de la carte de connaissances.

    Attributes:
        header: Titre du document (et de l'en-tête).
        crumb_prefix: Préfixe du fil d'Ariane (« Visualisations »…).
        search_ph: Placeholder du champ de recherche.
        network: Libellé du mode réseau.
        tree: Libellé du mode arbre.
        theme: Infobulle de bascule de thème.
        types: ``node_type -> libellé`` (puces de filtre + badge du panneau).
        edges: ``edge_type -> libellé`` (relations).
        ui: Libellés du panneau (``definition``/``excerpt``/``relations``/``focus``).
        zoom: Libellés des boutons de zoom (``out``/``fit``/``in``, pour ``aria-label``).
        count_template: Gabarit du compteur (``{c}``/``{n}``/``{e}``).
        reset_layout: Infobulle du bouton « Réinitialiser la disposition ».
    """

    header: str
    crumb_prefix: str
    search_ph: str
    network: str
    tree: str
    theme: str
    types: dict[str, str]
    edges: dict[str, str]
    ui: dict[str, str]
    zoom: dict[str, str]
    count_template: str
    reset_layout: str


_STRINGS: dict[Language, _KmStrings] = {
    Language.FR: _KmStrings(
        header="Carte de connaissances",
        crumb_prefix="Visualisations",
        search_ph="Rechercher un concept, un terme, un exemple…",
        network="Réseau", tree="Arbre", theme="Basculer le thème clair/sombre",
        types={"concept": "Concept", "glossary_term": "Terme",
               "example": "Exemple", "idea": "Idée"},
        edges={"leads_to": "mène à", "prerequisite": "prérequis",
               "illustrates": "illustre", "contrasts_with": "s'oppose à",
               "part_of": "composé de", "related": "lié à"},
        ui={"definition": "Définition", "excerpt": "Extrait source",
            "relations": "Relations", "focus": "Recentrer (mode arbre) →"},
        zoom={"out": "Dézoomer", "fit": "Ajuster à l'écran", "in": "Zoomer"},
        count_template="{c} communautés · {n} nœuds · {e} liens",
        reset_layout="Réinitialiser la disposition",
    ),
    Language.EN: _KmStrings(
        header="Knowledge map",
        crumb_prefix="Visualizations",
        search_ph="Search a concept, term, example…",
        network="Network", tree="Tree", theme="Toggle light/dark theme",
        types={"concept": "Concept", "glossary_term": "Term",
               "example": "Example", "idea": "Idea"},
        edges={"leads_to": "leads to", "prerequisite": "prerequisite",
               "illustrates": "illustrates", "contrasts_with": "contrasts with",
               "part_of": "part of", "related": "related"},
        ui={"definition": "Definition", "excerpt": "Source excerpt",
            "relations": "Relations", "focus": "Focus (tree mode) →"},
        zoom={"out": "Zoom out", "fit": "Fit to screen", "in": "Zoom in"},
        count_template="{c} communities · {n} nodes · {e} links",
        reset_layout="Reset layout",
    ),
    Language.DE: _KmStrings(
        header="Wissenslandkarte",
        crumb_prefix="Visualisierungen",
        search_ph="Begriff, Konzept oder Beispiel suchen…",
        network="Netzwerk", tree="Baum", theme="Helles/dunkles Thema umschalten",
        types={"concept": "Konzept", "glossary_term": "Begriff",
               "example": "Beispiel", "idea": "Idee"},
        edges={"leads_to": "führt zu", "prerequisite": "Voraussetzung",
               "illustrates": "veranschaulicht", "contrasts_with": "steht im Gegensatz zu",
               "part_of": "Teil von", "related": "verwandt mit"},
        ui={"definition": "Definition", "excerpt": "Quellenauszug",
            "relations": "Beziehungen", "focus": "Fokus (Baummodus) →"},
        zoom={"out": "Verkleinern", "fit": "An Bildschirm anpassen", "in": "Vergrößern"},
        count_template="{c} Gemeinschaften · {n} Knoten · {e} Kanten",
        reset_layout="Layout zurücksetzen",
    ),
    Language.ES: _KmStrings(
        header="Mapa de conocimientos",
        crumb_prefix="Visualizaciones",
        search_ph="Buscar un concepto, término, ejemplo…",
        network="Red", tree="Árbol", theme="Cambiar tema claro/oscuro",
        types={"concept": "Concepto", "glossary_term": "Término",
               "example": "Ejemplo", "idea": "Idea"},
        edges={"leads_to": "lleva a", "prerequisite": "requisito previo",
               "illustrates": "ilustra", "contrasts_with": "se opone a",
               "part_of": "parte de", "related": "relacionado con"},
        ui={"definition": "Definición", "excerpt": "Extracto de origen",
            "relations": "Relaciones", "focus": "Centrar (modo árbol) →"},
        zoom={"out": "Alejar", "fit": "Ajustar a la pantalla", "in": "Acercar"},
        count_template="{c} comunidades · {n} nodos · {e} enlaces",
        reset_layout="Restablecer disposición",
    ),
    Language.IT: _KmStrings(
        header="Mappa delle conoscenze",
        crumb_prefix="Visualizzazioni",
        search_ph="Cerca un concetto, un termine, un esempio…",
        network="Rete", tree="Albero", theme="Cambia tema chiaro/scuro",
        types={"concept": "Concetto", "glossary_term": "Termine",
               "example": "Esempio", "idea": "Idea"},
        edges={"leads_to": "porta a", "prerequisite": "prerequisito",
               "illustrates": "illustra", "contrasts_with": "si oppone a",
               "part_of": "parte di", "related": "collegato a"},
        ui={"definition": "Definizione", "excerpt": "Estratto della fonte",
            "relations": "Relazioni", "focus": "Centra (modalità albero) →"},
        zoom={"out": "Rimpicciolisci", "fit": "Adatta allo schermo", "in": "Ingrandisci"},
        count_template="{c} comunità · {n} nodi · {e} collegamenti",
        reset_layout="Reimposta disposizione",
    ),
}


def _graph_to_json(graph: KnowledgeGraph, strings: _KmStrings) -> dict[str, object]:
    """Sérialise le graphe + les libellés JS en données JSON inline.

    Args:
        graph: Graphe à sérialiser.
        strings: Libellés localisés (injectés dans ``i18n`` pour le JS).

    Returns:
        Un dictionnaire JSON-sérialisable (nodes/edges/communities/i18n).
    """
    return {
        "language": graph.language.value,
        "communities": [
            {"id": c.id, "label": c.label, "report": c.report}
            for c in graph.communities
        ],
        "nodes": [
            {
                "id": n.id,
                "label": n.label,
                "type": n.node_type.value,
                "definition": n.definition,
                "community": n.community_path[0] if n.community_path else None,
                "chapterAnchor": n.chapter_anchor,
                "excerpts": [
                    {"text": e.text, "anchor": e.anchor, "chapter": e.chapter_title}
                    for e in n.excerpts
                ],
            }
            for n in graph.nodes
        ],
        "edges": [
            {
                "id": f"e{index}",
                "source": e.source_id,
                "target": e.target_id,
                "type": e.edge_type.value,
                "label": e.label,
            }
            for index, e in enumerate(graph.edges)
        ],
        "i18n": {"typeLabels": strings.types, "edgeLabels": strings.edges, "ui": strings.ui},
    }


def render_knowledge_map_html(graph: KnowledgeGraph) -> str:
    """Rend la carte de connaissances en HTML autonome (fichier unique, hors-ligne).

    Args:
        graph: Graphe de connaissances (langue latine).

    Returns:
        Le document HTML complet (CSS + libs JS vendorisées + JS + données inlinés).
    """
    strings = _STRINGS[graph.language]
    payload = _graph_to_json(graph, strings)
    payload["storageKey"] = _storage_key(graph)
    data_json = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    # Les petits libellés (UI) d'abord, puis les gros contenus inlinés (assets +
    # JSON LLM) EN DERNIER : aucune substitution de libellé ne s'applique ainsi sur
    # du contenu déjà inliné (un libellé/définition LLM contenant un littéral
    # ``@@…@@`` ne peut donc plus être corrompu).
    replacements = {
        "@@LANG@@": graph.language.value,
        "@@DIR@@": "rtl" if is_rtl(graph.language) else "ltr",
        "@@TITLE@@": strings.header,
        "@@CRUMB@@": f"{strings.crumb_prefix} · {graph.language.value.upper()}",
        "@@HEADER@@": strings.header,
        "@@SEARCH_PH@@": strings.search_ph,
        "@@NETWORK@@": strings.network,
        "@@TREE@@": strings.tree,
        "@@THEME@@": strings.theme,
        "@@ZOOM_OUT@@": strings.zoom["out"],
        "@@ZOOM_FIT@@": strings.zoom["fit"],
        "@@ZOOM_IN@@": strings.zoom["in"],
        "@@CONCEPT@@": strings.types["concept"],
        "@@TERM@@": strings.types["glossary_term"],
        "@@EXAMPLE@@": strings.types["example"],
        "@@IDEA@@": strings.types["idea"],
        "@@COUNT@@": strings.count_template.format(
            c=len(graph.communities), n=len(graph.nodes), e=len(graph.edges)
        ),
        "@@RESET_LAYOUT@@": strings.reset_layout,
        "@@APP_CSS@@": f"{read_visuals_asset(VISUALS_TOKENS_CSS)}\n{read_visuals_asset(_CSS)}",
        "@@LAYOUT_STORE@@": read_visuals_asset(LAYOUT_STORE_JS),
        "@@APP_JS@@": read_visuals_asset(_JS),
        "@@VENDORED@@": vendored_scripts_html(),
        "@@DATA_JSON@@": data_json,
    }
    html = read_visuals_asset(_TEMPLATE)
    for token, value in replacements.items():
        html = html.replace(token, value)
    return html
