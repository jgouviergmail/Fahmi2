"""Génération des diagrammes : modèles typés produits par le LLM, par unité de texte.

Pour chaque unité, le LLM choisit les types pertinents **parmi ceux autorisés** et
émet un **modèle JSON typé** (jamais de DSL de rendu). Chaque diagramme est converti en
``Diagram`` du domaine ; un diagramme malformé est **ignoré** (robustesse) plutôt que
de faire échouer la génération. Le nombre de diagrammes par unité est borné par la
densité. Sortie en **langue source** ; localisation par langue en phase suivante.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fahmi2.core.errors.exceptions import Fahmi2Error
from fahmi2.domain.enums import DiagramType, Language
from fahmi2.domain.visuals import (
    GRAPH_DIAGRAM_TYPES,
    ComparisonTable,
    Diagram,
    DiagramLink,
    DiagramNode,
    SourceExcerpt,
    TimelineEvent,
)
from fahmi2.infra.llm.interface import JSON_OBJECT_RESPONSE_FORMAT
from fahmi2.infra.llm.invocation import parse_llm_json
from fahmi2.infra.llm.json_schema import (
    optional_str,
    require_list,
    require_mapping,
    require_str,
)
from fahmi2.visuals._constants import MAX_DIAGRAMS_PER_UNIT
from fahmi2.visuals._excerpts import build_section_index
from fahmi2.visuals.extractors._base import VisualsContext, invoke_visuals_llm
from fahmi2.visuals.sources import TextUnit

_STAGE = "diagram_authoring"
_TEMPLATE_NAME = "visuals_diagram_authoring"


@dataclass(frozen=True)
class DiagramExtraction:
    """Résultat de la génération des diagrammes pour une langue.

    Attributes:
        diagrams: Diagrammes produits (langue source).
        total_cost_usd: Coût LLM cumulé.
    """

    diagrams: tuple[Diagram, ...]
    total_cost_usd: float


def _as_list(value: Any) -> list[Any]:  # noqa: ANN401
    """Retourne ``value`` si c'est une liste, sinon une liste vide.

    Args:
        value: Valeur JSON éventuelle.

    Returns:
        La liste, ou ``[]`` si ``value`` n'est pas une liste.
    """
    return value if isinstance(value, list) else []


def _parse_graph_payload(
    item: dict[str, Any], *, context_label: str
) -> tuple[tuple[DiagramNode, ...], tuple[DiagramLink, ...]]:
    """Parse les ``nodes``/``links`` d'un diagramme « graphe ».

    Args:
        item: Objet JSON du diagramme.
        context_label: Libellé de contexte.

    Returns:
        ``(nodes, links)`` typés.

    Raises:
        LLMError: Si un champ requis (``id``/``label``/``from``/``to``) manque.
    """
    nodes = tuple(
        DiagramNode(
            id=require_str(node, "id", context_label=context_label),
            label=require_str(node, "label", context_label=context_label),
            role=optional_str(node, "role"),
        )
        for node in (
            require_mapping(raw, context_label=context_label)
            for raw in require_list(item, "nodes", context_label=context_label)
        )
    )
    links = tuple(
        DiagramLink(
            from_id=require_str(link, "from", context_label=context_label),
            to_id=require_str(link, "to", context_label=context_label),
            label=optional_str(link, "label"),
        )
        for link in (
            require_mapping(raw, context_label=context_label)
            for raw in require_list(item, "links", context_label=context_label)
        )
    )
    return nodes, links


def _parse_timeline_payload(
    item: dict[str, Any], *, context_label: str
) -> tuple[TimelineEvent, ...]:
    """Parse les ``events`` d'une chronologie.

    Args:
        item: Objet JSON du diagramme.
        context_label: Libellé de contexte.

    Returns:
        Le tuple d'``TimelineEvent``.

    Raises:
        LLMError: Si un champ requis (``date``/``title``) manque.
    """
    return tuple(
        TimelineEvent(
            date_label=require_str(event, "date", context_label=context_label),
            title=require_str(event, "title", context_label=context_label),
            detail=optional_str(event, "detail"),
        )
        for event in (
            require_mapping(raw, context_label=context_label)
            for raw in require_list(item, "events", context_label=context_label)
        )
    )


def _parse_comparison_payload(
    item: dict[str, Any], *, context_label: str
) -> ComparisonTable:
    """Parse le tableau d'une comparaison (``columns``/``rows``).

    Args:
        item: Objet JSON du diagramme.
        context_label: Libellé de contexte.

    Returns:
        Le ``ComparisonTable`` (validé : lignes de largeur cohérente).

    Raises:
        LLMError: Si ``columns`` n'est pas une liste de chaînes.
        ValueError: Si une ligne n'a pas la largeur des colonnes (``ComparisonTable``).
    """
    columns = tuple(
        str(column)
        for column in require_list(item, "columns", context_label=context_label)
    )
    rows = tuple(
        tuple(str(cell) for cell in _as_list(raw))
        for raw in require_list(item, "rows", context_label=context_label)
    )
    return ComparisonTable(columns=columns, rows=rows)


def _build_diagram(
    item: dict[str, Any],
    *,
    diagram_type: DiagramType,
    diagram_id: str,
    excerpts: tuple[SourceExcerpt, ...],
    chapter_anchor: str,
    context_label: str,
) -> Diagram | None:
    """Construit un ``Diagram`` typé depuis un objet JSON, ou ``None`` si malformé.

    Args:
        item: Objet JSON du diagramme.
        diagram_type: Type résolu (autorisé).
        diagram_id: Identifiant stable du diagramme.
        excerpts: Extraits source de l'unité.
        chapter_anchor: Ancre du chapitre d'origine.
        context_label: Libellé de contexte.

    Returns:
        Le ``Diagram`` ou ``None`` (charge utile invalide → ignoré).
    """
    try:
        title = require_str(item, "title", context_label=context_label)
        caption = optional_str(item, "caption") or ""
        if diagram_type in GRAPH_DIAGRAM_TYPES:
            nodes, links = _parse_graph_payload(item, context_label=context_label)
            return Diagram(
                id=diagram_id, title=title, diagram_type=diagram_type, nodes=nodes,
                links=links, events=(), comparison=None, caption=caption,
                chapter_anchor=chapter_anchor, excerpts=excerpts,
            )
        if diagram_type is DiagramType.TIMELINE:
            return Diagram(
                id=diagram_id, title=title, diagram_type=diagram_type, nodes=(),
                links=(), events=_parse_timeline_payload(item, context_label=context_label),
                comparison=None, caption=caption, chapter_anchor=chapter_anchor,
                excerpts=excerpts,
            )
        return Diagram(
            id=diagram_id, title=title, diagram_type=diagram_type, nodes=(), links=(),
            events=(), comparison=_parse_comparison_payload(item, context_label=context_label),
            caption=caption, chapter_anchor=chapter_anchor, excerpts=excerpts,
        )
    except (Fahmi2Error, ValueError):
        return None


def _diagrams_for_unit(
    item_list: list[Any],
    *,
    allowed: frozenset[DiagramType],
    unit: TextUnit,
    excerpts: tuple[SourceExcerpt, ...],
    max_diagrams: int,
    context_label: str,
) -> list[Diagram]:
    """Construit les diagrammes valides d'une unité (types autorisés, borné par densité).

    Args:
        item_list: Liste JSON des diagrammes proposés.
        allowed: Types de diagrammes autorisés.
        unit: Unité de texte source.
        excerpts: Extraits source de l'unité.
        max_diagrams: Plafond de diagrammes pour l'unité.
        context_label: Libellé de contexte.

    Returns:
        Les ``Diagram`` valides (au plus ``max_diagrams``).
    """
    diagrams: list[Diagram] = []
    section_key = "-".join(str(part) for part in unit.section_path)
    for index, raw in enumerate(item_list):
        if len(diagrams) >= max_diagrams:
            break
        try:
            item = require_mapping(raw, context_label=f"{context_label}[{index}]")
            diagram_type = DiagramType(require_str(item, "type", context_label=context_label))
        except (Fahmi2Error, ValueError):
            continue
        if diagram_type not in allowed:
            continue
        diagram = _build_diagram(
            item,
            diagram_type=diagram_type,
            diagram_id=f"diagram:{section_key}:{index}",
            excerpts=excerpts,
            chapter_anchor=unit.anchor,
            context_label=f"{context_label}[{index}]",
        )
        if diagram is not None:
            diagrams.append(diagram)
    return diagrams


def extract_diagrams(
    ctx: VisualsContext, *, language: Language, units: tuple[TextUnit, ...]
) -> DiagramExtraction:
    """Génère les diagrammes du corpus (langue source), par unité de texte.

    Args:
        ctx: Contexte d'exécution (réglages : types autorisés + densité).
        language: Langue du document lu.
        units: Unités de texte du document consolidé.

    Returns:
        Le ``DiagramExtraction`` (diagrammes + coût). Vide si aucun type autorisé.
    """
    allowed = ctx.settings.diagram_types
    if not allowed:
        return DiagramExtraction(diagrams=(), total_cost_usd=0.0)
    index = build_section_index(units)
    max_diagrams = MAX_DIAGRAMS_PER_UNIT[ctx.settings.density]
    allowed_values = sorted(diagram_type.value for diagram_type in allowed)
    diagrams: list[Diagram] = []
    total_cost = 0.0
    for unit in units:
        ctx.pause_token.wait_if_paused()
        ctx.pause_token.raise_if_cancelled()
        user_prompt = ctx.prompts.render(
            _TEMPLATE_NAME,
            section_title=unit.title,
            section_markdown=unit.text,
            allowed_types=allowed_values,
            max_diagrams=max_diagrams,
        )
        response = invoke_visuals_llm(
            ctx,
            stage=_STAGE,
            language=language,
            user_prompt=user_prompt,
            response_format=JSON_OBJECT_RESPONSE_FORMAT,
        )
        total_cost += response.cost_usd
        context_label = f"{_STAGE}:{'.'.join(str(p) for p in unit.section_path)}"
        mapping = require_mapping(
            parse_llm_json(
                response.content,
                context_label=context_label,
                finish_reason=response.finish_reason,
            ),
            context_label=context_label,
        )
        excerpt = index.excerpt(unit.section_path)
        diagrams.extend(
            _diagrams_for_unit(
                require_list(mapping, "diagrams", context_label=context_label),
                allowed=allowed,
                unit=unit,
                excerpts=(excerpt,) if excerpt else (),
                max_diagrams=max_diagrams,
                context_label=f"{context_label}.diagrams",
            )
        )
    return DiagramExtraction(diagrams=tuple(diagrams), total_cost_usd=total_cost)
