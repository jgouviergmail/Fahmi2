"""Localisation par langue : traduction des libellés + extraits par ``section_path``.

La **structure** (graphe + diagrammes) est extraite une seule fois en langue source ;
cette étape la **localise** vers une langue cible :

- les nœuds ``GLOSSARY_TERM`` reprennent le terme + la définition **localisés** du
  glossaire (``cross_lang``), sans appel LLM ;
- tous les autres textes (libellés/définitions/relations/communautés/rapports +
  titres/légendes/labels de diagrammes) sont **traduits par lot** (un appel LLM, pairage
  par position, repli sur la source si manquant) ;
- les **extraits** sont **re-dérivés** du document consolidé de la langue cible par
  ``section_path`` (invariant), avec l'ancre/le titre de cette langue.
"""

from __future__ import annotations

from dataclasses import replace

from fahmi2.domain.enums import Language, NodeType
from fahmi2.domain.glossary import Term, localize_glossary_terms
from fahmi2.domain.languages import language_label
from fahmi2.domain.visuals import (
    Diagram,
    DiagramBoard,
    DiagramLink,
    DiagramNode,
    GraphNode,
    KnowledgeGraph,
    SourceExcerpt,
    TimelineEvent,
)
from fahmi2.infra.llm.interface import JSON_OBJECT_RESPONSE_FORMAT
from fahmi2.infra.llm.invocation import parse_llm_json
from fahmi2.infra.llm.json_schema import require_list, require_mapping
from fahmi2.visuals._excerpts import SectionIndex, build_section_index
from fahmi2.visuals.extractors._base import VisualsContext, invoke_visuals_llm
from fahmi2.visuals.extractors.graph_extractor import node_id
from fahmi2.visuals.sources import TextUnit

_STAGE = "label_translation"
_TEMPLATE_NAME = "visuals_label_translation"

#: Table de traduction ``texte source -> texte traduit`` (repli sur la source).
TranslationTable = dict[str, str]


def _translate_batch(
    ctx: VisualsContext, strings: set[str], *, target_language: Language
) -> tuple[TranslationTable, float]:
    """Traduit un lot de chaînes vers la langue cible (un appel LLM, pairage positionnel).

    Args:
        ctx: Contexte d'exécution.
        strings: Ensemble de chaînes sources à traduire.
        target_language: Langue cible.

    Returns:
        ``(table, coût_usd)`` ; ``table`` mappe chaque source vers sa traduction (repli
        sur la source si la traduction manque ou est vide).
    """
    if not strings:
        return {}, 0.0
    ordered = sorted(strings)
    response = invoke_visuals_llm(
        ctx,
        stage=_STAGE,
        language=target_language,
        user_prompt=ctx.prompts.render(
            _TEMPLATE_NAME,
            texts=ordered,
            target_language_label=language_label(target_language),
        ),
        response_format=JSON_OBJECT_RESPONSE_FORMAT,
    )
    mapping = require_mapping(
        parse_llm_json(
            response.content, context_label=_STAGE, finish_reason=response.finish_reason
        ),
        context_label=_STAGE,
    )
    translations = require_list(mapping, "translations", context_label=_STAGE)
    table: TranslationTable = {}
    for source, translated in zip(ordered, translations, strict=False):
        text = str(translated).strip()
        table[source] = text if text else source
    for source in ordered:
        table.setdefault(source, source)
    return table, response.cost_usd


def _tr(text: str, table: TranslationTable) -> str:
    """Traduit un texte via la table (repli sur la source si absent).

    Args:
        text: Texte source.
        table: Table de traduction.

    Returns:
        La traduction, ou ``text`` si absente.
    """
    return table.get(text, text)


def _relocalize_excerpts(
    excerpts: tuple[SourceExcerpt, ...], index: SectionIndex
) -> tuple[SourceExcerpt, ...]:
    """Re-dérive les extraits dans la langue cible par ``section_path`` (repli si absent).

    Args:
        excerpts: Extraits source (chemins de section invariants).
        index: Index des sections de la langue cible.

    Returns:
        Les extraits de la langue cible (l'extrait source est conservé si la section
        est absente dans la langue cible).
    """
    relocalized: list[SourceExcerpt] = []
    for excerpt in excerpts:
        target = index.excerpt(excerpt.section_path)
        relocalized.append(target if target is not None else excerpt)
    return tuple(relocalized)


def _primary_anchor(
    excerpts: tuple[SourceExcerpt, ...], index: SectionIndex, fallback: str | None
) -> str | None:
    """Ancre (langue cible) du 1ᵉʳ extrait, ou ``fallback`` si indisponible.

    Args:
        excerpts: Extraits source du nœud.
        index: Index des sections de la langue cible.
        fallback: Ancre de repli (langue source).

    Returns:
        L'ancre de la langue cible, ou ``fallback``.
    """
    if not excerpts:
        return fallback
    return index.anchor(excerpts[0].section_path) or fallback


def _collect_graph_strings(graph: KnowledgeGraph) -> set[str]:
    """Rassemble les chaînes du graphe à traduire (hors termes de glossaire).

    Args:
        graph: Graphe source.

    Returns:
        L'ensemble des chaînes traduisibles (libellés/définitions de nœuds non
        glossaire, libellés de relations, libellés/rapports de communautés).
    """
    strings: set[str] = set()
    for node in graph.nodes:
        if node.node_type is NodeType.GLOSSARY_TERM:
            continue
        strings.add(node.label)
        if node.definition:
            strings.add(node.definition)
    for edge in graph.edges:
        if edge.label:
            strings.add(edge.label)
    for community in graph.communities:
        if community.label:
            strings.add(community.label)
        if community.report:
            strings.add(community.report)
    return strings


def _localize_node(
    node: GraphNode,
    *,
    glossary_map: dict[str, tuple[str, str]],
    table: TranslationTable,
    index: SectionIndex,
) -> GraphNode:
    """Localise un nœud (glossaire via ``cross_lang``, sinon via la table).

    Args:
        node: Nœud source.
        glossary_map: ``id de nœud glossaire -> (terme localisé, définition localisée)``.
        table: Table de traduction.
        index: Index des sections de la langue cible.

    Returns:
        Le nœud localisé (libellé, définition, extraits, ancre de chapitre).
    """
    label: str
    definition: str | None
    if node.node_type is NodeType.GLOSSARY_TERM and node.id in glossary_map:
        label, definition = glossary_map[node.id]
    else:
        label = _tr(node.label, table)
        definition = _tr(node.definition, table) if node.definition else None
    return replace(
        node,
        label=label,
        definition=definition,
        excerpts=_relocalize_excerpts(node.excerpts, index),
        chapter_anchor=_primary_anchor(node.excerpts, index, node.chapter_anchor),
    )


def localize_graph(
    ctx: VisualsContext,
    graph: KnowledgeGraph,
    *,
    target_language: Language,
    glossary: tuple[Term, ...],
    target_units: tuple[TextUnit, ...],
) -> tuple[KnowledgeGraph, float]:
    """Localise le graphe entier vers une langue cible.

    Args:
        ctx: Contexte d'exécution.
        graph: Graphe source.
        target_language: Langue cible.
        glossary: Termes du glossaire **source** (localisés via ``cross_lang``).
        target_units: Unités de texte du consolidé **de la langue cible** (extraits).

    Returns:
        ``(graphe_localisé, coût_usd)``.
    """
    index = build_section_index(target_units)
    localized_terms = localize_glossary_terms(glossary, target_language)
    glossary_map = {
        node_id(NodeType.GLOSSARY_TERM, source.term): (localized.term, localized.definition)
        for source, localized in zip(glossary, localized_terms, strict=True)
    }
    table, cost = _translate_batch(
        ctx, _collect_graph_strings(graph), target_language=target_language
    )
    nodes = tuple(
        _localize_node(node, glossary_map=glossary_map, table=table, index=index)
        for node in graph.nodes
    )
    edges = tuple(
        replace(edge, label=_tr(edge.label, table) if edge.label else None)
        for edge in graph.edges
    )
    communities = tuple(
        replace(community, label=_tr(community.label, table), report=_tr(community.report, table))
        for community in graph.communities
    )
    return (
        KnowledgeGraph(
            nodes=nodes, edges=edges, communities=communities, language=target_language
        ),
        cost,
    )


def _diagram_strings(diagram: Diagram) -> set[str]:
    """Chaînes traduisibles d'un diagramme.

    Args:
        diagram: Diagramme source.

    Returns:
        L'ensemble des chaînes (titre, légende, libellés de nœuds/liens, évènements,
        en-têtes et cellules de comparaison).
    """
    strings: set[str] = {diagram.title}
    if diagram.caption:
        strings.add(diagram.caption)
    for node in diagram.nodes:
        strings.add(node.label)
        if node.role:
            strings.add(node.role)
    strings.update(link.label for link in diagram.links if link.label)
    for event in diagram.events:
        strings.add(event.date_label)
        strings.add(event.title)
        if event.detail:
            strings.add(event.detail)
    if diagram.comparison is not None:
        strings.update(diagram.comparison.columns)
        for row in diagram.comparison.rows:
            strings.update(row)
    return strings


def _collect_board_strings(board: DiagramBoard) -> set[str]:
    """Rassemble les chaînes de tous les diagrammes à traduire.

    Args:
        board: Galerie source.

    Returns:
        L'union des chaînes traduisibles de chaque diagramme.
    """
    strings: set[str] = set()
    for diagram in board.diagrams:
        strings |= _diagram_strings(diagram)
    return strings


def _localize_diagram(
    diagram: Diagram, *, table: TranslationTable, index: SectionIndex
) -> Diagram:
    """Localise un diagramme (titre, légende, charge utile typée, extraits).

    Args:
        diagram: Diagramme source.
        table: Table de traduction.
        index: Index des sections de la langue cible.

    Returns:
        Le diagramme localisé.
    """
    comparison = diagram.comparison
    if comparison is not None:
        comparison = replace(
            comparison,
            columns=tuple(_tr(column, table) for column in comparison.columns),
            rows=tuple(
                tuple(_tr(cell, table) for cell in row) for row in comparison.rows
            ),
        )
    return replace(
        diagram,
        title=_tr(diagram.title, table),
        caption=_tr(diagram.caption, table) if diagram.caption else "",
        nodes=tuple(
            DiagramNode(id=n.id, label=_tr(n.label, table),
                        role=_tr(n.role, table) if n.role else None)
            for n in diagram.nodes
        ),
        links=tuple(
            DiagramLink(from_id=link.from_id, to_id=link.to_id,
                        label=_tr(link.label, table) if link.label else None)
            for link in diagram.links
        ),
        events=tuple(
            TimelineEvent(date_label=_tr(e.date_label, table), title=_tr(e.title, table),
                          detail=_tr(e.detail, table) if e.detail else None)
            for e in diagram.events
        ),
        comparison=comparison,
        chapter_anchor=(
            _primary_anchor(diagram.excerpts, index, diagram.chapter_anchor)
            or diagram.chapter_anchor
        ),
        excerpts=_relocalize_excerpts(diagram.excerpts, index),
    )


def localize_board(
    ctx: VisualsContext,
    board: DiagramBoard,
    *,
    target_language: Language,
    target_units: tuple[TextUnit, ...],
) -> tuple[DiagramBoard, float]:
    """Localise la galerie de diagrammes vers une langue cible.

    Args:
        ctx: Contexte d'exécution.
        board: Galerie source.
        target_language: Langue cible.
        target_units: Unités de texte du consolidé **de la langue cible** (extraits).

    Returns:
        ``(galerie_localisée, coût_usd)``.
    """
    index = build_section_index(target_units)
    table, cost = _translate_batch(
        ctx, _collect_board_strings(board), target_language=target_language
    )
    diagrams = tuple(
        _localize_diagram(diagram, table=table, index=index)
        for diagram in board.diagrams
    )
    return DiagramBoard(diagrams=diagrams, language=target_language), cost
