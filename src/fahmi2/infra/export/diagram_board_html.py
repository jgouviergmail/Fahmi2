"""Rendu de la galerie de schémas en page HTML **pleinement autonome**.

Assemble un fichier HTML unique présentant les diagrammes d'un ``DiagramBoard`` sous
forme de cartes. Les diagrammes « graphe » (flowchart/hierarchy/decision_tree/cycle)
embarquent leur modèle JSON (rendu par Cytoscape, init paresseuse) ; les diagrammes
linéaires (timeline/comparison) sont rendus en **HTML/CSS déterministe** côté serveur.
Libellés d'interface dans la **langue du board** (scripts latins : fr/en/de/es/it).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from html import escape

from fahmi2.domain.enums import DiagramType, Language
from fahmi2.domain.languages import is_rtl
from fahmi2.domain.visuals import GRAPH_DIAGRAM_TYPES, Diagram, DiagramBoard
from fahmi2.infra.export._visuals_assets import read_visuals_asset, vendored_scripts_html

_TEMPLATE = "diagram_board.html.template"
_TOKENS_CSS = "visuals_tokens.css"
_CSS = "diagram_board.css"
_JS = "diagram_board.js"

#: Le board n'utilise que Cytoscape + dagre (pas fcose/expand-collapse) → bundle réduit.
_BOARD_SCRIPTS: tuple[str, ...] = (
    "dagre.min.js",
    "cytoscape.min.js",
    "cytoscape-dagre.js",
)

#: Hauteur (px) du canvas d'un diagramme « graphe », adaptée au nombre de nœuds : un
#: graphe dense a besoin de plus de place pour rester lisible. Calculée **au rendu**
#: (côté serveur) pour éviter tout saut de mise en page (pas de redimensionnement JS
#: après coup). ``height = clamp(BASE + nœuds × PER_NODE, MIN, MAX)``.
_GRAPH_BASE_HEIGHT_PX = 210
_GRAPH_PER_NODE_PX = 52
_GRAPH_MIN_HEIGHT_PX = 300
_GRAPH_MAX_HEIGHT_PX = 560


def _graph_diagram_height_px(node_count: int) -> int:
    """Hauteur (px) du canvas pour un graphe de ``node_count`` nœuds.

    Args:
        node_count: Nombre de nœuds du graphe.

    Returns:
        La hauteur bornée à ``[_GRAPH_MIN_HEIGHT_PX, _GRAPH_MAX_HEIGHT_PX]``.
    """
    raw = _GRAPH_BASE_HEIGHT_PX + node_count * _GRAPH_PER_NODE_PX
    return max(_GRAPH_MIN_HEIGHT_PX, min(_GRAPH_MAX_HEIGHT_PX, raw))


@dataclass(frozen=True)
class _BoardStrings:
    """Libellés d'interface localisés de la galerie de schémas.

    Attributes:
        header: Titre du document (et en-tête).
        crumb_prefix: Préfixe du fil d'Ariane.
        theme: Infobulle de bascule de thème.
        types: ``diagram_type -> libellé`` (chip + badge de carte).
        count_template: Gabarit du compteur (``{n}``).
        empty: Message affiché quand le filtre ne laisse aucune carte.
        excerpt_label: Libellé du dépliant d'extrait source.
        expand_label: Infobulle du bouton « agrandir » (plein écran).
        close_label: Infobulle/texte du bouton de fermeture du plein écran.
    """

    header: str
    crumb_prefix: str
    theme: str
    types: dict[str, str]
    count_template: str
    empty: str
    excerpt_label: str
    expand_label: str
    close_label: str


_STRINGS: dict[Language, _BoardStrings] = {
    Language.FR: _BoardStrings(
        header="Schémas & diagrammes", crumb_prefix="Visualisations",
        theme="Basculer le thème clair/sombre",
        types={"flowchart": "Processus", "timeline": "Chronologie",
               "comparison": "Comparaison", "hierarchy": "Hiérarchie",
               "cycle": "Cycle", "decision_tree": "Arbre de décision"},
        count_template="{n} schémas", empty="Aucun schéma pour ce filtre.",
        excerpt_label="Extrait source",
        expand_label="Agrandir", close_label="Fermer",
    ),
    Language.EN: _BoardStrings(
        header="Diagrams & schematics", crumb_prefix="Visualizations",
        theme="Toggle light/dark theme",
        types={"flowchart": "Flowchart", "timeline": "Timeline",
               "comparison": "Comparison", "hierarchy": "Hierarchy",
               "cycle": "Cycle", "decision_tree": "Decision tree"},
        count_template="{n} diagrams", empty="No diagram for this filter.",
        excerpt_label="Source excerpt",
        expand_label="Enlarge", close_label="Close",
    ),
    Language.DE: _BoardStrings(
        header="Schaubilder & Diagramme", crumb_prefix="Visualisierungen",
        theme="Helles/dunkles Thema umschalten",
        types={"flowchart": "Ablauf", "timeline": "Zeitleiste",
               "comparison": "Vergleich", "hierarchy": "Hierarchie",
               "cycle": "Zyklus", "decision_tree": "Entscheidungsbaum"},
        count_template="{n} Diagramme", empty="Kein Diagramm für diesen Filter.",
        excerpt_label="Quellenauszug",
        expand_label="Vergrößern", close_label="Schließen",
    ),
    Language.ES: _BoardStrings(
        header="Esquemas y diagramas", crumb_prefix="Visualizaciones",
        theme="Cambiar tema claro/oscuro",
        types={"flowchart": "Proceso", "timeline": "Cronología",
               "comparison": "Comparación", "hierarchy": "Jerarquía",
               "cycle": "Ciclo", "decision_tree": "Árbol de decisión"},
        count_template="{n} esquemas", empty="Ningún esquema para este filtro.",
        excerpt_label="Extracto de origen",
        expand_label="Ampliar", close_label="Cerrar",
    ),
    Language.IT: _BoardStrings(
        header="Schemi e diagrammi", crumb_prefix="Visualizzazioni",
        theme="Cambia tema chiaro/scuro",
        types={"flowchart": "Processo", "timeline": "Cronologia",
               "comparison": "Confronto", "hierarchy": "Gerarchia",
               "cycle": "Ciclo", "decision_tree": "Albero decisionale"},
        count_template="{n} schemi", empty="Nessuno schema per questo filtro.",
        excerpt_label="Estratto della fonte",
        expand_label="Ingrandisci", close_label="Chiudi",
    ),
}


def _graph_body(diagram: Diagram) -> str:
    """Rend le corps d'un diagramme « graphe » (conteneur Cytoscape + JSON).

    Args:
        diagram: Diagramme de type graphe.

    Returns:
        Le HTML du conteneur ``cy-diagram`` avec son modèle JSON en ``data-graph``.
    """
    spec = {
        "nodes": [
            {"id": n.id, "label": n.label, "role": n.role or ""} for n in diagram.nodes
        ],
        "links": [
            {"from": link.from_id, "to": link.to_id, "label": link.label or ""}
            for link in diagram.links
        ],
        "cyclic": diagram.diagram_type is DiagramType.CYCLE,
    }
    payload = escape(json.dumps(spec, ensure_ascii=False), quote=True)
    return f'<div class="cy-diagram" data-graph="{payload}"></div>'


def _timeline_body(diagram: Diagram) -> str:
    """Rend une chronologie en HTML/CSS déterministe.

    Args:
        diagram: Diagramme de type ``TIMELINE``.

    Returns:
        Le HTML de la frise chronologique.
    """
    events = "".join(
        f'<div class="ev"><div class="date">{escape(e.date_label)}</div>'
        f"<h4>{escape(e.title)}</h4>"
        f"{f'<p>{escape(e.detail)}</p>' if e.detail else ''}</div>"
        for e in diagram.events
    )
    return f'<div class="timeline">{events}</div>'


def _comparison_body(diagram: Diagram) -> str:
    """Rend une comparaison en tableau HTML déterministe.

    Args:
        diagram: Diagramme de type ``COMPARISON`` (``comparison`` non ``None``).

    Returns:
        Le HTML du tableau (chaîne vide si ``comparison`` absent — par sécurité).
    """
    table = diagram.comparison
    if table is None:
        return ""
    head = "".join(f"<th>{escape(col)}</th>" for col in table.columns)
    body = "".join(
        "<tr>" + "".join(f"<td>{escape(cell)}</td>" for cell in row) + "</tr>"
        for row in table.rows
    )
    return (
        f'<div class="cmp"><table><thead><tr>{head}</tr></thead>'
        f"<tbody>{body}</tbody></table></div>"
    )


def _diagram_body(diagram: Diagram) -> str:
    """Rend le corps d'un diagramme selon son type.

    Args:
        diagram: Diagramme.

    Returns:
        Le HTML du corps (Cytoscape pour les graphes, HTML/CSS pour les linéaires).
    """
    if diagram.diagram_type in GRAPH_DIAGRAM_TYPES:
        return _graph_body(diagram)
    if diagram.diagram_type is DiagramType.TIMELINE:
        return _timeline_body(diagram)
    return _comparison_body(diagram)


def _card(diagram: Diagram, strings: _BoardStrings) -> str:
    """Rend une carte de diagramme (en-tête + corps + légende + extrait).

    Args:
        diagram: Diagramme à présenter.
        strings: Libellés localisés.

    Returns:
        Le HTML de la carte.
    """
    kind = escape(strings.types.get(diagram.diagram_type.value, diagram.diagram_type.value))
    # Hauteur adaptative pour les graphes (lisibilité) ; hauteur CSS par défaut
    # pour les diagrammes linéaires (timeline/comparison, défilables).
    diagram_style = ""
    if diagram.diagram_type in GRAPH_DIAGRAM_TYPES:
        diagram_style = f' style="height:{_graph_diagram_height_px(len(diagram.nodes))}px"'
    expand = escape(strings.expand_label, quote=True)
    parts = [
        f'<article class="card" data-type="{escape(diagram.diagram_type.value)}">',
        f'<header><div class="head-text"><span class="kind">{kind}</span>'
        f"<h3>{escape(diagram.title)}</h3></div>"
        f'<button class="expand" type="button" title="{expand}" '
        f'aria-label="{expand}">⤢</button></header>',
        f'<div class="diagram"{diagram_style}>{_diagram_body(diagram)}</div>',
    ]
    if diagram.caption:
        parts.append(f'<div class="caption">{escape(diagram.caption)}</div>')
    if diagram.excerpts:
        excerpt = diagram.excerpts[0]
        parts.append(
            f'<details class="excerpt"><summary>{escape(strings.excerpt_label)} · § '
            f"{escape(excerpt.chapter_title)}</summary>"
            f"<blockquote>{escape(excerpt.text)}</blockquote></details>"
        )
    parts.append("</article>")
    return "".join(parts)


def _chips(board: DiagramBoard, strings: _BoardStrings) -> str:
    """Rend les puces de filtre (une par type de diagramme présent).

    Args:
        board: Galerie.
        strings: Libellés localisés.

    Returns:
        Le HTML des puces (ordre canonique de ``DiagramType``).
    """
    present = {d.diagram_type for d in board.diagrams}
    chips = [
        f'<span class="chip" data-type="{t.value}">'
        f"{escape(strings.types[t.value])}</span>"
        for t in DiagramType
        if t in present
    ]
    return "".join(chips)


def render_diagram_board_html(board: DiagramBoard) -> str:
    """Rend la galerie de schémas en HTML autonome (fichier unique, hors-ligne).

    Args:
        board: Galerie de diagrammes (langue latine).

    Returns:
        Le document HTML complet (CSS + libs vendorisées + JS + données inlinés).
    """
    strings = _STRINGS[board.language]
    cards = "".join(_card(diagram, strings) for diagram in board.diagrams)
    # Petits libellés (UI) d'abord, puis gros contenus inlinés (assets + cartes
    # générées) EN DERNIER : aucune substitution de libellé ne s'applique ainsi sur
    # du contenu LLM déjà inliné (titre/légende/extrait contenant un littéral
    # ``@@…@@`` ne peut donc plus être corrompu).
    replacements = {
        "@@LANG@@": board.language.value,
        "@@DIR@@": "rtl" if is_rtl(board.language) else "ltr",
        "@@TITLE@@": strings.header,
        "@@CRUMB@@": f"{strings.crumb_prefix} · {board.language.value.upper()}",
        "@@HEADER@@": strings.header,
        "@@THEME@@": strings.theme,
        "@@CHIPS@@": _chips(board, strings),
        "@@COUNT@@": strings.count_template.format(n=len(board.diagrams)),
        "@@EMPTY@@": strings.empty,
        "@@CLOSE@@": strings.close_label,
        "@@APP_CSS@@": f"{read_visuals_asset(_TOKENS_CSS)}\n{read_visuals_asset(_CSS)}",
        "@@APP_JS@@": read_visuals_asset(_JS),
        "@@VENDORED@@": vendored_scripts_html(_BOARD_SCRIPTS),
        "@@CARDS@@": cards,
    }
    html = read_visuals_asset(_TEMPLATE)
    for token, value in replacements.items():
        html = html.replace(token, value)
    return html
