"""Extraction du graphe brut : squelette glossaire (déterministe) + couche LLM.

Le **squelette** (nœuds ``GLOSSARY_TERM``) est construit sans LLM depuis le glossaire
réconcilié. La **couche sémantique** (concepts / idées / exemples + relations typées)
est extraite par unité de texte via le LLM, avec une passe de *gleaning* (rappel). La
sortie est **brute** (entités/relations désignées par leur libellé, doublons possibles
entre unités) : la résolution d'entités et l'assemblage du ``KnowledgeGraph`` final
relèvent de la phase suivante.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fahmi2.core.slugify import slugify_anchor
from fahmi2.domain.enums import EdgeType, Language, NodeType
from fahmi2.domain.glossary import Term
from fahmi2.domain.visuals import GraphNode
from fahmi2.infra.llm.interface import JSON_OBJECT_RESPONSE_FORMAT
from fahmi2.infra.llm.invocation import parse_llm_json
from fahmi2.infra.llm.json_schema import require_list, require_mapping, require_str
from fahmi2.visuals._constants import GLEANING_ROUNDS, MAX_SEMANTIC_NODES_PER_UNIT
from fahmi2.visuals.events import VisualsStructureStep
from fahmi2.visuals.extractors._base import (
    VisualsContext,
    invoke_visuals_llm,
    map_units_with_progress,
)
from fahmi2.visuals.sources import TextUnit

_STAGE = "graph_extraction"
_TEMPLATE_NAME = "visuals_graph_extraction"

#: Types de nœuds que le LLM est autorisé à produire (le glossaire est déterministe).
_SEMANTIC_NODE_TYPES: frozenset[NodeType] = frozenset(
    {NodeType.CONCEPT, NodeType.IDEA, NodeType.EXAMPLE}
)


def node_id(node_type: NodeType, label: str) -> str:
    """Identifiant canonique d'un nœud (``type:slug``).

    Args:
        node_type: Type du nœud.
        label: Libellé du nœud.

    Returns:
        L'identifiant ``f"{node_type}:{slug}"`` (slug via ``slugify_anchor``).
    """
    return f"{node_type.value}:{slugify_anchor(label)}"


@dataclass(frozen=True)
class RawEntity:
    """Entité sémantique brute extraite d'une unité (avant résolution).

    Attributes:
        label: Libellé tel que produit par le LLM.
        node_type: Type sémantique (``CONCEPT`` / ``IDEA`` / ``EXAMPLE``).
        definition: Définition/glose éventuelle, sinon ``None``.
        section_path: Chemin structurel de l'unité source (invariant par langue).
        chapter_title: Titre de l'unité source.
        anchor: Ancre GFM de l'unité source (langue du document lu).
    """

    label: str
    node_type: NodeType
    definition: str | None
    section_path: tuple[int, ...]
    chapter_title: str
    anchor: str


@dataclass(frozen=True)
class RawRelation:
    """Relation typée brute entre deux libellés (avant résolution en ids).

    Attributes:
        source_label: Libellé de l'entité source.
        target_label: Libellé de l'entité cible.
        edge_type: Type de relation.
        label: Libellé d'arête éventuel, sinon ``None``.
    """

    source_label: str
    target_label: str
    edge_type: EdgeType
    label: str | None


@dataclass(frozen=True)
class GraphExtraction:
    """Résultat brut de l'extraction du graphe pour une langue.

    Attributes:
        glossary_nodes: Nœuds ``GLOSSARY_TERM`` (squelette déterministe).
        raw_entities: Entités sémantiques brutes (doublons inter-unités possibles).
        raw_relations: Relations brutes (désignées par libellé).
        total_cost_usd: Coût LLM cumulé de l'extraction.
    """

    glossary_nodes: tuple[GraphNode, ...]
    raw_entities: tuple[RawEntity, ...]
    raw_relations: tuple[RawRelation, ...]
    total_cost_usd: float


def build_glossary_skeleton(glossary: tuple[Term, ...]) -> tuple[GraphNode, ...]:
    """Construit les nœuds ``GLOSSARY_TERM`` depuis le glossaire (sans LLM).

    Args:
        glossary: Termes du glossaire (langue de contenu).

    Returns:
        Les nœuds de type ``GLOSSARY_TERM``, dédoublonnés par identifiant.
    """
    nodes: list[GraphNode] = []
    seen: set[str] = set()
    for term in glossary:
        ident = node_id(NodeType.GLOSSARY_TERM, term.term)
        if ident in seen:
            continue
        seen.add(ident)
        nodes.append(
            GraphNode(
                id=ident,
                label=term.term,
                node_type=NodeType.GLOSSARY_TERM,
                definition=term.definition,
                excerpts=(),
                chapter_anchor=None,
                community_path=(),
            )
        )
    return tuple(nodes)


def _parse_entities(
    mapping: dict[str, Any], *, unit: TextUnit, context_label: str
) -> list[RawEntity]:
    """Parse la liste ``entities`` d'une réponse LLM en ``RawEntity``.

    Les types inconnus ou non sémantiques (ex. ``glossary_term``) sont ignorés.

    Args:
        mapping: Objet JSON de la réponse.
        unit: Unité de texte source (provenance des entités).
        context_label: Libellé de contexte pour les erreurs de schéma.

    Returns:
        Les entités sémantiques valides.
    """
    entities: list[RawEntity] = []
    for index, raw in enumerate(require_list(mapping, "entities", context_label=context_label)):
        item = require_mapping(raw, context_label=f"{context_label}.entities[{index}]")
        type_str = require_str(item, "type", context_label=f"{context_label}.entities[{index}]")
        try:
            node_type = NodeType(type_str)
        except ValueError:
            continue
        if node_type not in _SEMANTIC_NODE_TYPES:
            continue
        label = require_str(item, "label", context_label=f"{context_label}.entities[{index}]")
        raw_def = item.get("definition")
        definition = raw_def.strip() if isinstance(raw_def, str) and raw_def.strip() else None
        entities.append(
            RawEntity(
                label=label,
                node_type=node_type,
                definition=definition,
                section_path=unit.section_path,
                chapter_title=unit.title,
                anchor=unit.anchor,
            )
        )
    return entities


def _parse_relations(
    mapping: dict[str, Any], *, context_label: str
) -> list[RawRelation]:
    """Parse la liste ``relations`` d'une réponse LLM en ``RawRelation``.

    Les types de relation inconnus sont ignorés.

    Args:
        mapping: Objet JSON de la réponse.
        context_label: Libellé de contexte pour les erreurs de schéma.

    Returns:
        Les relations valides.
    """
    relations: list[RawRelation] = []
    for index, raw in enumerate(require_list(mapping, "relations", context_label=context_label)):
        item = require_mapping(raw, context_label=f"{context_label}.relations[{index}]")
        type_str = require_str(item, "type", context_label=f"{context_label}.relations[{index}]")
        try:
            edge_type = EdgeType(type_str)
        except ValueError:
            continue
        source = require_str(item, "source", context_label=f"{context_label}.relations[{index}]")
        target = require_str(item, "target", context_label=f"{context_label}.relations[{index}]")
        raw_label = item.get("label")
        label = raw_label.strip() if isinstance(raw_label, str) and raw_label.strip() else None
        relations.append(
            RawRelation(
                source_label=source,
                target_label=target,
                edge_type=edge_type,
                label=label,
            )
        )
    return relations


def _extract_unit_once(
    ctx: VisualsContext,
    *,
    language: Language,
    unit: TextUnit,
    max_entities: int,
    gleaning: bool,
    already_found: tuple[str, ...],
) -> tuple[list[RawEntity], list[RawRelation], float]:
    """Un appel d'extraction LLM pour une unité (initial ou gleaning).

    Args:
        ctx: Contexte d'exécution.
        language: Langue du document.
        unit: Unité de texte.
        max_entities: Plafond d'entités sémantiques pour cette unité.
        gleaning: ``True`` pour une passe de rappel (réutilise ``already_found``).
        already_found: Libellés déjà extraits (passe de gleaning).

    Returns:
        ``(entités, relations, coût_usd)`` de cet appel.
    """
    user_prompt = ctx.prompts.render(
        _TEMPLATE_NAME,
        section_title=unit.title,
        section_markdown=unit.text,
        max_entities=max_entities,
        gleaning=gleaning,
        already_found=list(already_found),
    )
    response = invoke_visuals_llm(
        ctx,
        stage=_STAGE,
        language=language,
        user_prompt=user_prompt,
        response_format=JSON_OBJECT_RESPONSE_FORMAT,
    )
    context_label = f"{_STAGE}:{'.'.join(str(p) for p in unit.section_path)}"
    payload = parse_llm_json(
        response.content,
        context_label=context_label,
        finish_reason=response.finish_reason,
    )
    mapping = require_mapping(payload, context_label=context_label)
    entities = _parse_entities(mapping, unit=unit, context_label=context_label)
    relations = _parse_relations(mapping, context_label=context_label)
    return entities, relations, response.cost_usd


def _absorb(
    entities: list[RawEntity],
    relations: list[RawRelation],
    *,
    unit_entities: list[RawEntity],
    unit_relations: list[RawRelation],
    seen_labels: set[str],
    max_entities: int,
) -> None:
    """Fusionne le résultat d'un appel dans les accumulateurs d'une unité.

    Dédoublonne les entités par libellé et respecte le plafond ``max_entities`` ;
    les relations sont toutes conservées (résolues/filtrées en phase suivante).

    Args:
        entities: Entités issues d'un appel (initial ou gleaning).
        relations: Relations issues du même appel.
        unit_entities: Accumulateur d'entités de l'unité (muté).
        unit_relations: Accumulateur de relations de l'unité (muté).
        seen_labels: Libellés déjà retenus pour l'unité (muté).
        max_entities: Plafond d'entités sémantiques pour l'unité.
    """
    for entity in entities:
        if len(unit_entities) >= max_entities:
            break
        if entity.label in seen_labels:
            continue
        seen_labels.add(entity.label)
        unit_entities.append(entity)
    unit_relations.extend(relations)


def extract_graph(
    ctx: VisualsContext,
    *,
    language: Language,
    units: tuple[TextUnit, ...],
    glossary: tuple[Term, ...],
) -> GraphExtraction:
    """Extrait le graphe brut (squelette glossaire + couche sémantique LLM).

    Pour chaque unité : une extraction initiale puis ``GLEANING_ROUNDS`` passe(s) de
    rappel. Les entités d'une même unité sont dédoublonnées par libellé et plafonnées
    selon la densité.

    Args:
        ctx: Contexte d'exécution (réglages, provider, prompts, retry, bus, pause).
        language: Langue du document lu.
        units: Unités de texte du document consolidé.
        glossary: Termes du glossaire (langue de contenu).

    Returns:
        Le ``GraphExtraction`` brut (à résoudre/assembler en phase suivante).
    """
    glossary_nodes = build_glossary_skeleton(glossary)
    max_entities = MAX_SEMANTIC_NODES_PER_UNIT[ctx.settings.density]
    # Unités traitées en parallèle (borné par llm_workers), ordre préservé →
    # assemblage déterministe. Progression émise par unité terminée.
    results = map_units_with_progress(
        ctx,
        units,
        lambda unit: _extract_unit(
            ctx, language=language, unit=unit, max_entities=max_entities
        ),
        step=VisualsStructureStep.GRAPH,
    )
    all_entities: list[RawEntity] = []
    all_relations: list[RawRelation] = []
    total_cost = 0.0
    for unit_entities, unit_relations, cost in results:
        all_entities.extend(unit_entities)
        all_relations.extend(unit_relations)
        total_cost += cost
    return GraphExtraction(
        glossary_nodes=glossary_nodes,
        raw_entities=tuple(all_entities),
        raw_relations=tuple(all_relations),
        total_cost_usd=total_cost,
    )


def _extract_unit(
    ctx: VisualsContext,
    *,
    language: Language,
    unit: TextUnit,
    max_entities: int,
) -> tuple[list[RawEntity], list[RawRelation], float]:
    """Extrait les entités/relations d'une **seule** unité (initial + gleaning).

    Args:
        ctx: Contexte d'exécution.
        language: Langue du document lu.
        unit: Unité de texte à traiter.
        max_entities: Plafond d'entités sémantiques pour l'unité (densité).

    Returns:
        ``(entités, relations, coût)`` de l'unité (dédoublonnées, plafonnées).
    """
    unit_entities: list[RawEntity] = []
    unit_relations: list[RawRelation] = []
    seen_labels: set[str] = set()
    entities, relations, cost = _extract_unit_once(
        ctx,
        language=language,
        unit=unit,
        max_entities=max_entities,
        gleaning=False,
        already_found=(),
    )
    total_cost = cost
    _absorb(
        entities,
        relations,
        unit_entities=unit_entities,
        unit_relations=unit_relations,
        seen_labels=seen_labels,
        max_entities=max_entities,
    )
    for _ in range(GLEANING_ROUNDS):
        if len(unit_entities) >= max_entities:
            break
        entities, relations, cost = _extract_unit_once(
            ctx,
            language=language,
            unit=unit,
            max_entities=max_entities,
            gleaning=True,
            already_found=tuple(seen_labels),
        )
        total_cost += cost
        _absorb(
            entities,
            relations,
            unit_entities=unit_entities,
            unit_relations=unit_relations,
            seen_labels=seen_labels,
            max_entities=max_entities,
        )
    return unit_entities, unit_relations, total_cost
