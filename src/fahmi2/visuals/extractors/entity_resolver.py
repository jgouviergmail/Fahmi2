"""Résolution d'entités : graphe brut → nœuds canoniques + arêtes (langue source).

Les entités brutes (désignées par libellé) sont résolues en nœuds uniques :

- celles correspondant à un **terme du glossaire** (libellé/alias normalisés) sont
  rattachées au nœud ``GLOSSARY_TERM`` correspondant (qui hérite de leurs extraits) ;
- les autres (concepts / idées / exemples « libres ») sont **regroupées par similarité
  d'embeddings** (seuil cosinus) ou, sans fournisseur d'embeddings, **par libellé
  normalisé** (fallback AUTO). Chaque groupe donne un nœud canonique (libellé le plus
  fréquent, type majoritaire, 1ʳᵉ définition non vide, extraits unionnés).

Les relations brutes (libellé→libellé) sont résolues en arêtes (id→id) ; les extrémités
non résolues, les boucles et les doublons sont écartés. Le graphe produit est en
**langue source** (extraits remplis depuis les unités) — sa localisation par langue
relève de la phase suivante.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import replace

from fahmi2.core.slugify import slugify_anchor
from fahmi2.domain.enums import NodeType
from fahmi2.domain.glossary import Term
from fahmi2.domain.visuals import GraphEdge, GraphNode, SourceExcerpt
from fahmi2.infra.embeddings.interface import EmbeddingProvider
from fahmi2.visuals._constants import ENTITY_MERGE_COSINE_THRESHOLD
from fahmi2.visuals._excerpts import SectionIndex, build_section_index
from fahmi2.visuals.extractors.graph_extractor import (
    GraphExtraction,
    RawEntity,
    RawRelation,
    node_id,
)
from fahmi2.visuals.sources import TextUnit

_Path = tuple[int, ...]


def _glossary_slug_index(glossary: tuple[Term, ...]) -> dict[str, str]:
    """Indexe les termes du glossaire (slug du libellé + alias) vers leur id de nœud.

    Args:
        glossary: Termes du glossaire.

    Returns:
        Un mapping ``slug -> id de nœud GLOSSARY_TERM`` (1ᵉʳ gagnant en cas de collision).
    """
    index: dict[str, str] = {}
    for term in glossary:
        ident = node_id(NodeType.GLOSSARY_TERM, term.term)
        index.setdefault(slugify_anchor(term.term), ident)
        for alias in term.aliases:
            index.setdefault(slugify_anchor(alias), ident)
    return index


def _cosine(left: list[float], right: list[float]) -> float:
    """Similarité cosinus de deux vecteurs (0 si l'un est nul).

    Args:
        left: Premier vecteur.
        right: Second vecteur (même dimension).

    Returns:
        Le cosinus dans ``[-1, 1]`` (0 si une norme est nulle).
    """
    dot = sum(x * y for x, y in zip(left, right, strict=True))
    norm_left = math.sqrt(sum(x * x for x in left))
    norm_right = math.sqrt(sum(y * y for y in right))
    if norm_left == 0.0 or norm_right == 0.0:
        return 0.0
    return dot / (norm_left * norm_right)


def _embed_text(entity: RawEntity) -> str:
    """Texte encodé pour l'embedding d'une entité (libellé + définition éventuelle).

    Args:
        entity: Entité brute.

    Returns:
        ``"<label> <definition>"`` (définition omise si absente), sans ponctuation
        artificielle ajoutée.
    """
    parts = [entity.label]
    if entity.definition:
        parts.append(entity.definition)
    return " ".join(parts)


def _cluster_free_entities(
    free: list[RawEntity], embedding_provider: EmbeddingProvider | None
) -> list[list[RawEntity]]:
    """Regroupe les entités libres par similarité (embeddings) ou par libellé (fallback).

    Args:
        free: Entités libres (hors glossaire).
        embedding_provider: Fournisseur d'embeddings, ou ``None`` (fallback AUTO par
            libellé normalisé).

    Returns:
        La liste des groupes (chacun une liste de ``RawEntity``).
    """
    if not free:
        return []
    if embedding_provider is None:
        by_slug: dict[str, list[RawEntity]] = {}
        for entity in free:
            by_slug.setdefault(slugify_anchor(entity.label), []).append(entity)
        return list(by_slug.values())
    vectors = embedding_provider.embed_documents(
        [_embed_text(entity) for entity in free]
    )
    clusters: list[list[RawEntity]] = []
    centroids: list[list[float]] = []
    for entity, vector in zip(free, vectors, strict=True):
        best_index = -1
        best_similarity = ENTITY_MERGE_COSINE_THRESHOLD
        for index, centroid in enumerate(centroids):
            similarity = _cosine(vector, centroid)
            if similarity >= best_similarity:
                best_similarity = similarity
                best_index = index
        if best_index == -1:
            clusters.append([entity])
            centroids.append(vector)
        else:
            clusters[best_index].append(entity)
            # Centroïde mis à jour par moyenne incrémentale : les entités suivantes
            # sont comparées au barycentre réel du cluster (et non au seul fondateur).
            size = len(clusters[best_index])
            centroids[best_index] = [
                (c * (size - 1) + v) / size
                for c, v in zip(centroids[best_index], vector, strict=True)
            ]
    return clusters


def _ordered_unique_paths(members: list[RawEntity]) -> list[_Path]:
    """Chemins de section distincts des membres, dans l'ordre d'apparition.

    Args:
        members: Entités d'un groupe.

    Returns:
        Les ``section_path`` distincts, ordre préservé.
    """
    paths: list[_Path] = []
    seen: set[_Path] = set()
    for member in members:
        if member.section_path not in seen:
            seen.add(member.section_path)
            paths.append(member.section_path)
    return paths


def _canonical_node(members: list[RawEntity], index: SectionIndex) -> GraphNode:
    """Construit le nœud canonique d'un groupe d'entités libres.

    Le libellé canonique est le plus fréquent (départage : plus court, puis
    alphabétique) ; le type est le type majoritaire ; la définition est la première
    non vide ; les extraits sont l'union (par section) des provenances.

    Args:
        members: Entités du groupe (non vide).
        index: Index des sections (pour les extraits).

    Returns:
        Le ``GraphNode`` canonique (``community_path`` vide).
    """
    label_counts = Counter(member.label for member in members)
    canonical_label = sorted(
        label_counts, key=lambda label: (-label_counts[label], len(label), label)
    )[0]
    type_counts = Counter(member.node_type for member in members)
    node_type = sorted(
        type_counts, key=lambda node: (-type_counts[node], node.value)
    )[0]
    definition = next(
        (member.definition for member in members if member.definition), None
    )
    paths = _ordered_unique_paths(members)
    excerpts = tuple(
        excerpt for excerpt in (index.excerpt(path) for path in paths) if excerpt
    )
    chapter_anchor = index.anchor(paths[0]) if paths else None
    return GraphNode(
        id=node_id(node_type, canonical_label),
        label=canonical_label,
        node_type=node_type,
        definition=definition,
        excerpts=excerpts,
        chapter_anchor=chapter_anchor,
        community_path=(),
    )


def _merge_excerpts(
    left: tuple[SourceExcerpt, ...], right: tuple[SourceExcerpt, ...]
) -> tuple[SourceExcerpt, ...]:
    """Fusionne deux tuples d'extraits en dédoublonnant par chemin de section.

    Args:
        left: Extraits existants.
        right: Extraits à ajouter.

    Returns:
        L'union ordonnée (1ᵉʳ extrait gagnant par section).
    """
    merged: list[SourceExcerpt] = list(left)
    seen = {excerpt.section_path for excerpt in left}
    for excerpt in right:
        if excerpt.section_path not in seen:
            seen.add(excerpt.section_path)
            merged.append(excerpt)
    return tuple(merged)


def _attach_glossary_matches(
    raw_entities: tuple[RawEntity, ...],
    *,
    glossary_index: dict[str, str],
    index: SectionIndex,
    nodes_by_id: dict[str, GraphNode],
) -> list[RawEntity]:
    """Rattache aux nœuds de glossaire les entités qui en sont (par libellé/alias).

    Mute ``nodes_by_id`` (enrichit les nœuds de glossaire de leurs extraits).

    Args:
        raw_entities: Entités brutes.
        glossary_index: Index ``slug -> id de nœud glossaire``.
        index: Index des sections (extraits).
        nodes_by_id: Nœuds en cours d'assemblage (muté).

    Returns:
        Les entités **libres** (non rattachées au glossaire).
    """
    glossary_paths: dict[str, list[_Path]] = {}
    free: list[RawEntity] = []
    for entity in raw_entities:
        glossary_id = glossary_index.get(slugify_anchor(entity.label))
        if glossary_id is None:
            free.append(entity)
            continue
        paths = glossary_paths.setdefault(glossary_id, [])
        if entity.section_path not in paths:
            paths.append(entity.section_path)
    for glossary_id, paths in glossary_paths.items():
        base = nodes_by_id.get(glossary_id)
        if base is None:
            continue
        excerpts = tuple(
            excerpt for excerpt in (index.excerpt(path) for path in paths) if excerpt
        )
        nodes_by_id[glossary_id] = replace(
            base,
            excerpts=_merge_excerpts(base.excerpts, excerpts),
            chapter_anchor=base.chapter_anchor or index.anchor(paths[0]),
        )
    return free


def _add_free_clusters(
    free: list[RawEntity],
    *,
    embedding_provider: EmbeddingProvider | None,
    index: SectionIndex,
    nodes_by_id: dict[str, GraphNode],
    slug_to_id: dict[str, str],
) -> None:
    """Regroupe les entités libres en nœuds canoniques (mute nœuds + index de slugs).

    Args:
        free: Entités libres.
        embedding_provider: Fournisseur d'embeddings, ou ``None`` (fallback AUTO).
        index: Index des sections (extraits).
        nodes_by_id: Nœuds en cours d'assemblage (muté).
        slug_to_id: Index ``slug -> id`` pour la résolution des relations (muté).
    """
    for cluster in _cluster_free_entities(free, embedding_provider):
        node = _canonical_node(cluster, index)
        existing = nodes_by_id.get(node.id)
        if existing is None:
            nodes_by_id[node.id] = node
        else:
            nodes_by_id[node.id] = replace(
                existing,
                excerpts=_merge_excerpts(existing.excerpts, node.excerpts),
                chapter_anchor=existing.chapter_anchor or node.chapter_anchor,
            )
        for member in cluster:
            slug_to_id[slugify_anchor(member.label)] = node.id
        slug_to_id[slugify_anchor(node.label)] = node.id


def _resolve_relations(
    raw_relations: tuple[RawRelation, ...], slug_to_id: dict[str, str]
) -> tuple[GraphEdge, ...]:
    """Résout les relations brutes en arêtes (id→id), sans boucle ni doublon.

    Args:
        raw_relations: Relations brutes (libellé→libellé).
        slug_to_id: Index ``slug -> id``.

    Returns:
        Les arêtes résolues et dédoublonnées.
    """
    edges: list[GraphEdge] = []
    seen_edges: set[tuple[str, str, str]] = set()
    for relation in raw_relations:
        source_id = slug_to_id.get(slugify_anchor(relation.source_label))
        target_id = slug_to_id.get(slugify_anchor(relation.target_label))
        if source_id is None or target_id is None or source_id == target_id:
            continue
        key = (source_id, target_id, relation.edge_type.value)
        if key in seen_edges:
            continue
        seen_edges.add(key)
        edges.append(
            GraphEdge(
                source_id=source_id,
                target_id=target_id,
                edge_type=relation.edge_type,
                label=relation.label,
            )
        )
    return tuple(edges)


def resolve_graph(
    extraction: GraphExtraction,
    *,
    glossary: tuple[Term, ...],
    units: tuple[TextUnit, ...],
    embedding_provider: EmbeddingProvider | None,
) -> tuple[tuple[GraphNode, ...], tuple[GraphEdge, ...]]:
    """Résout le graphe brut en nœuds canoniques + arêtes (langue source).

    Args:
        extraction: Graphe brut (squelette glossaire + entités/relations brutes).
        glossary: Termes du glossaire (pour le rattachement par libellé/alias).
        units: Unités de texte (pour les extraits source).
        embedding_provider: Fournisseur d'embeddings, ou ``None`` (fallback AUTO).

    Returns:
        ``(nœuds, arêtes)`` : nœuds uniques par id (glossaire enrichi d'extraits +
        nœuds sémantiques canoniques), arêtes id→id dédoublonnées, sans boucle.
    """
    index = build_section_index(units)
    glossary_index = _glossary_slug_index(glossary)
    nodes_by_id: dict[str, GraphNode] = {
        node.id: node for node in extraction.glossary_nodes
    }
    slug_to_id: dict[str, str] = dict(glossary_index)
    free = _attach_glossary_matches(
        extraction.raw_entities,
        glossary_index=glossary_index,
        index=index,
        nodes_by_id=nodes_by_id,
    )
    _add_free_clusters(
        free,
        embedding_provider=embedding_provider,
        index=index,
        nodes_by_id=nodes_by_id,
        slug_to_id=slug_to_id,
    )
    edges = _resolve_relations(extraction.raw_relations, slug_to_id)
    return tuple(nodes_by_id.values()), edges
