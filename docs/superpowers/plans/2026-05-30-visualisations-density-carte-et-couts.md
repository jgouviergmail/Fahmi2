# Plan — Visualisations : différenciation density de la carte + attribution des coûts par cellule

> **Pour l'exécutant :** plan exécuté **inline** (skill `executing-plans`). Étapes en
> cases à cocher (`- [ ]`). TDD : test rouge → implémentation → test vert → commit.

**Objectif :** rendre les 3 niveaux de density nettement différents sur la carte de
connaissances (élagage par degré, sélection par arêtes) et afficher une traçabilité
réelle des coûts par cellule dans la matrice de progression.

**Architecture :** un module pur `visuals/_pruning.py` (sélection par arêtes,
déterministe) inséré entre `resolve_graph` et `assemble_graph` ; les coûts déjà
calculés par livrable remontent via 2 champs ajoutés sur 2 événements, peuplés
cellule par cellule dans `VisualsProgressViewModel`.

**Stack :** Python 3.12, dataclasses gelées, pytest, ruff, mypy --strict. Aucun
nouvel ajout de dépendance.

**Spec :** `docs/superpowers/specs/2026-05-30-visualisations-density-carte-et-couts-design.md`

---

## Découpage en phases

- **Phase 1 — Élagage par degré de la carte (Volet 1)** : constantes + `_pruning.py`
  + tests + câblage orchestrateur. *Détaillée ci-dessous.*
- **Phase 2 — Attribution des coûts par cellule (Volet 2)** : champs d'événements +
  coûts par livrable dans l'orchestrateur + viewmodel + tests. *Détaillée au début de
  la phase.*
- **Phase 3 — Docs transverses + vérification** : CLAUDE.md, CHANGELOG, docs/01,
  docs/02, aide UI ; vérification navigateur légère vs dense. *Détaillée au début de la
  phase.*
- **Final — Revue exhaustive de toute la branche.**

---

## Phase 1 — Élagage par degré de la carte de connaissances

### Task 1.1 : Constantes de density de la carte

**Fichiers :**
- Modifier : `src/fahmi2/visuals/_constants.py`

- [ ] **Step 1 : Ajouter les 3 constantes** après `MAX_SEMANTIC_NODES_PER_UNIT`
  (le bloc `import SupportDensity` existe déjà en tête de fichier) :

```python
#: Fraction des nœuds **connectés** conservés sur la carte de connaissances, par
#: niveau de densité (les nœuds isolés sont d'abord retirés ; cf.
#: ``_pruning.prune_knowledge_graph``). ``DENSE`` = tout le connexe.
MAP_CONNECTED_NODE_RATIO_BY_DENSITY: dict[SupportDensity, float] = {
    SupportDensity.LIGHT: 0.25,
    SupportDensity.STANDARD: 0.50,
    SupportDensity.DENSE: 1.0,
}

#: Plafond absolu de nœuds de la carte par niveau (``None`` = non plafonné). Garantit la
#: lisibilité de « légère » / « standard » sur les corpus très riches.
MAP_NODE_CAP_BY_DENSITY: dict[SupportDensity, int | None] = {
    SupportDensity.LIGHT: 40,
    SupportDensity.STANDARD: 90,
    SupportDensity.DENSE: None,
}

#: Plancher de nœuds de la carte (évite une carte quasi vide sur un petit document).
MAP_MIN_NODES = 12
```

- [ ] **Step 2 : Vérifier le typage** : `mypy src/fahmi2/visuals/_constants.py` → vert.

- [ ] **Step 3 : Commit**

```
git add src/fahmi2/visuals/_constants.py
git commit -m "feat(visuals): constantes density de la carte (ratios/plafonds/plancher)"
```

### Task 1.2 : Module `_pruning.py` (TDD)

**Fichiers :**
- Créer : `tests/unit/visuals/test_pruning.py`
- Créer : `src/fahmi2/visuals/_pruning.py`

- [ ] **Step 1 : Écrire les tests (rouges)** dans `tests/unit/visuals/test_pruning.py`.
  Helpers `_node`/`_edge` recopiés du pattern de `test_community.py` (mêmes signatures —
  ils sont locaux à chaque fichier de test, pas de module partagé existant) :

```python
"""Tests de l'élagage de la carte par densité (sélection par arêtes)."""

from __future__ import annotations

from fahmi2.domain.enums import EdgeType, NodeType, SupportDensity
from fahmi2.domain.visuals import GraphEdge, GraphNode
from fahmi2.visuals._constants import MAP_MIN_NODES, MAP_NODE_CAP_BY_DENSITY
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
    nodes = (*_path_graph(5)[0], _node("iso1"), _node("iso2"))
    edges = _path_graph(5)[1]
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
    kept_nodes, _ = prune_knowledge_graph(
        nodes, edges, density=SupportDensity.LIGHT
    )
    assert len(kept_nodes) == MAP_NODE_CAP_BY_DENSITY[SupportDensity.LIGHT]


def test_standard_applique_le_plafond() -> None:
    nodes, edges = _path_graph(300)
    kept_nodes, _ = prune_knowledge_graph(
        nodes, edges, density=SupportDensity.STANDARD
    )
    assert len(kept_nodes) == MAP_NODE_CAP_BY_DENSITY[SupportDensity.STANDARD]


def test_ratio_applique_sous_le_plafond() -> None:
    # 100 connectés, 25 % = 25 (< plafond 40, > plancher 12).
    nodes, edges = _path_graph(100)
    kept_nodes, _ = prune_knowledge_graph(
        nodes, edges, density=SupportDensity.LIGHT
    )
    assert len(kept_nodes) == 25


def test_plancher_applique() -> None:
    # 8 connectés : 25 % = 2 → relevé au plancher min(MAP_MIN_NODES, 8) = 8.
    nodes, edges = _path_graph(8)
    kept_nodes, _ = prune_knowledge_graph(
        nodes, edges, density=SupportDensity.LIGHT
    )
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


def test_graphe_sans_arete_inchange() -> None:
    nodes = (_node("a"), _node("b"), _node("c"))
    kept_nodes, kept_edges = prune_knowledge_graph(
        nodes, (), density=SupportDensity.LIGHT
    )
    assert kept_nodes == nodes
    assert kept_edges == ()
```

- [ ] **Step 2 : Lancer les tests → ils échouent** (module absent) :
  `.venv\Scripts\python.exe -m pytest tests/unit/visuals/test_pruning.py -q`
  Attendu : `ModuleNotFoundError: fahmi2.visuals._pruning`.

- [ ] **Step 3 : Implémenter** `src/fahmi2/visuals/_pruning.py` :

```python
"""Élagage de la carte de connaissances par densité (sélection par arêtes).

Réduit le graphe résolu aux nœuds les plus **structurants** (les mieux connectés)
selon le niveau de densité. La **sélection par arêtes** (classées par somme des degrés
de leurs extrémités, accumulées jusqu'au budget de nœuds) garantit **par construction**
qu'aucun nœud conservé n'est isolé — jamais de carte vide tant qu'il existe une arête.
Module pur (sans Qt / réseau / LLM), déterministe.
"""

from __future__ import annotations

import math

from fahmi2.domain.enums import SupportDensity
from fahmi2.domain.visuals import GraphEdge, GraphNode
from fahmi2.visuals._constants import (
    MAP_CONNECTED_NODE_RATIO_BY_DENSITY,
    MAP_MIN_NODES,
    MAP_NODE_CAP_BY_DENSITY,
)


def _node_degrees(
    nodes: tuple[GraphNode, ...], edges: tuple[GraphEdge, ...]
) -> dict[str, int]:
    """Degré (nombre d'arêtes incidentes) de chaque nœud.

    Args:
        nodes: Nœuds du graphe.
        edges: Arêtes du graphe.

    Returns:
        Un mapping ``id de nœud -> degré`` (0 pour un nœud isolé).
    """
    degree = {node.id: 0 for node in nodes}
    for edge in edges:
        if edge.source_id in degree:
            degree[edge.source_id] += 1
        if edge.target_id in degree:
            degree[edge.target_id] += 1
    return degree


def _target_node_count(connected_count: int, density: SupportDensity) -> int:
    """Nombre cible de nœuds conservés (ratio borné par plancher et plafond).

    Args:
        connected_count: Nombre de nœuds connectés (degré ≥ 1).
        density: Niveau de densité.

    Returns:
        La cible ``clamp(ceil(ratio * N), min(MAP_MIN_NODES, N), plafond, N)``.
    """
    ratio = MAP_CONNECTED_NODE_RATIO_BY_DENSITY[density]
    target = max(math.ceil(ratio * connected_count), min(MAP_MIN_NODES, connected_count))
    cap = MAP_NODE_CAP_BY_DENSITY[density]
    if cap is not None:
        target = min(target, cap)
    return min(target, connected_count)


def prune_knowledge_graph(
    nodes: tuple[GraphNode, ...],
    edges: tuple[GraphEdge, ...],
    *,
    density: SupportDensity,
) -> tuple[tuple[GraphNode, ...], tuple[GraphEdge, ...]]:
    """Élague la carte aux nœuds les plus connectés (sélection par arêtes).

    Retire d'abord les nœuds isolés, puis conserve les arêtes les plus « fortes »
    (somme des degrés des extrémités) en accumulant leurs nœuds jusqu'au budget de
    densité ; les arêtes finales sont le sous-graphe induit sur les nœuds retenus.

    Args:
        nodes: Nœuds résolus du graphe (langue de structure).
        edges: Arêtes résolues du graphe.
        density: Niveau de densité pilotant la taille conservée.

    Returns:
        ``(nœuds conservés, arêtes induites)``. Invariant : tout nœud conservé porte au
        moins une arête conservée. Garde-fou : un graphe **sans arête** est retourné
        inchangé (pas de carte vide).
    """
    if not edges:
        return nodes, edges
    degree = _node_degrees(nodes, edges)
    connected_count = sum(1 for value in degree.values() if value > 0)
    if connected_count == 0:
        return nodes, edges
    target = _target_node_count(connected_count, density)
    ranked_edges = sorted(
        edges,
        key=lambda edge: (
            -(degree[edge.source_id] + degree[edge.target_id]),
            min(edge.source_id, edge.target_id),
            max(edge.source_id, edge.target_id),
        ),
    )
    kept_ids: set[str] = set()
    for edge in ranked_edges:
        if len(kept_ids) >= target:
            break
        new_ids = {edge.source_id, edge.target_id} - kept_ids
        if len(kept_ids) + len(new_ids) <= target:
            kept_ids |= new_ids
    kept_nodes = tuple(node for node in nodes if node.id in kept_ids)
    kept_edges = tuple(
        edge
        for edge in edges
        if edge.source_id in kept_ids and edge.target_id in kept_ids
    )
    return kept_nodes, kept_edges
```

- [ ] **Step 4 : Lancer les tests → verts** :
  `.venv\Scripts\python.exe -m pytest tests/unit/visuals/test_pruning.py -q` → 10 passed.

- [ ] **Step 5 : Qualité** : `ruff check src/fahmi2/visuals/_pruning.py tests/unit/visuals/test_pruning.py`
  + `mypy src/fahmi2/visuals/_pruning.py` → verts.

- [ ] **Step 6 : Commit**

```
git add src/fahmi2/visuals/_pruning.py tests/unit/visuals/test_pruning.py
git commit -m "feat(visuals): élagage de la carte par degré (sélection par arêtes)"
```

### Task 1.3 : Câblage dans l'orchestrateur

**Fichiers :**
- Modifier : `src/fahmi2/app/visuals_orchestrator.py` (import + `_build_structure`,
  entre `resolve_graph` et `assemble_graph`, ~L410-420)
- Test : `tests/unit/app/test_visuals_orchestrator.py` (vérifie l'élagage appliqué)

- [ ] **Step 1 : Ajouter l'import** près des autres imports `visuals` :

```python
from fahmi2.visuals._pruning import prune_knowledge_graph
```

- [ ] **Step 2 : Insérer l'élagage** dans `_build_structure`, juste après l'agrégation
  du coût des embeddings et **avant** `assemble_graph` :

```python
            nodes, edges = prune_knowledge_graph(
                nodes, edges, density=ctx.settings.density
            )
            graph = assemble_graph(nodes, edges, language=structure_lang)
```

- [ ] **Step 3 : Confirmer la non-régression des tests d'orchestrateur existants.**
  Pas de nouveau test d'intégration dédié (YAGNI) : l'élagage est déjà couvert
  exhaustivement par `test_pruning.py` et validé sur données réelles, et le fake
  `_StageLLM` de `test_visuals_orchestrator.py` ne produit que **2 nœuds connectés** —
  le **plancher** (`min(MAP_MIN_NODES, 2) = 2`) les conserve à tous les niveaux, donc
  les assertions existantes (`"Bilan" in km and "Cas Enron" in km`) restent vraies. Un
  test de réduction au niveau orchestrateur exigerait de réécrire un gros fake (>12
  nœuds connectés) pour un gain nul vs l'unitaire → écarté.
  Lancer : `.venv\Scripts\python.exe -m pytest tests/unit/app/test_visuals_orchestrator.py -q`
  → tous verts (aucune adaptation attendue).

- [ ] **Step 4 : Suite + qualité ciblées** :
  `.venv\Scripts\python.exe -m pytest tests/unit/visuals tests/unit/app/test_visuals_orchestrator.py -q`
  + `ruff check .` + `mypy src tests` → verts.

- [ ] **Step 5 : Commit**

```
git add src/fahmi2/app/visuals_orchestrator.py tests/unit/app/test_visuals_orchestrator.py
git commit -m "feat(visuals): applique l'élagage density dans l'extraction de structure"
```

### Fin de Phase 1 — Revue de code approfondie

Revue selon la checklist complète (complétude du plan, constantes centralisées,
conformité aux patterns, Google style + docstrings Args/Returns/Raises, cohérence de
nommage, DRY/YAGNI/KISS/SRP/SoC/Boy Scout/Composition, généricité). Repasses
`pytest` (×3) / `ruff` / `mypy --strict` jusqu'à zéro défaut. Corriger inline tout
constat avant de passer à la Phase 2.

---

## Phase 2 — Attribution des coûts par cellule

### Task 2.1 : Champs de coût par livrable sur les événements

**Fichiers :**
- Modifier : `src/fahmi2/visuals/events.py`

- [ ] **Step 1 : `VisualsStructureFinished`** — ajouter 2 champs **à défaut `0.0`**
  (en fin de classe, après `timestamp` hérité) :

```python
@dataclass(frozen=True)
class VisualsStructureFinished(VisualsEvent):
    """Fin de l'extraction de structure (avant la production par langue).

    Attributes:
        map_cost_usd: Coût LLM de la structure imputé à la **carte** (graphe +
            résolution d'entités + rapports de communauté + idea-chains).
        diagrams_cost_usd: Coût LLM de la structure imputé aux **diagrammes**.
    """

    map_cost_usd: float = 0.0
    diagrams_cost_usd: float = 0.0
```

- [ ] **Step 2 : `VisualsLanguageFinished`** — ajouter 2 champs **à défaut `0.0`**
  (après `error`) et compléter la docstring :

```python
    language: Language
    status: PhaseStatus
    cost_usd: float
    error: ErrorInfo | None
    map_cost_usd: float = 0.0
    diagrams_cost_usd: float = 0.0
```

  Docstring : ajouter `map_cost_usd` (localisation de la **carte**) et
  `diagrams_cost_usd` (localisation des **diagrammes**) ; `cost_usd` reste leur somme.

- [ ] **Step 3 : Vérifier** `mypy src/fahmi2/visuals/events.py` → vert (les défauts
  viennent après les champs sans défaut → ordre dataclass valide).

- [ ] **Step 4 : Commit**

```
git add src/fahmi2/visuals/events.py
git commit -m "feat(visuals): coûts par livrable sur les événements structure/langue"
```

### Task 2.2 : Coûts par livrable dans l'orchestrateur

**Fichiers :**
- Modifier : `src/fahmi2/app/visuals_orchestrator.py`

- [ ] **Step 1 : `_build_structure`** — renvoyer un **4-tuple**
  `(graph, board, map_cost, diagrams_cost)`. Remplacer la signature
  `-> tuple[KnowledgeGraph | None, DiagramBoard | None, float]` par
  `-> tuple[KnowledgeGraph | None, DiagramBoard | None, float, float]`, et le corps :

```python
        graph: KnowledgeGraph | None = None
        board: DiagramBoard | None = None
        map_cost = 0.0
        diagrams_cost = 0.0
        if ctx.settings.produce_knowledge_map:
            extraction = extract_graph(
                ctx, language=structure_lang, units=units, glossary=glossary_struct
            )
            map_cost += extraction.total_cost_usd
            nodes, edges = resolve_graph(
                extraction, glossary=glossary_struct, units=units,
                embedding_provider=self._embedding_provider,
            )
            if self._embedding_provider is not None:
                map_cost += self._embedding_provider.consumed_cost_usd()
            nodes, edges = prune_knowledge_graph(
                nodes, edges, density=ctx.settings.density
            )
            graph = assemble_graph(nodes, edges, language=structure_lang)
            graph, report_cost = generate_community_reports(
                ctx, graph, language=structure_lang
            )
            graph, chain_cost = generate_idea_chains(ctx, graph, language=structure_lang)
            map_cost += report_cost + chain_cost
        if ctx.settings.produce_diagrams:
            diagrams = extract_diagrams(ctx, language=structure_lang, units=units)
            board = DiagramBoard(diagrams=diagrams.diagrams, language=structure_lang)
            diagrams_cost += diagrams.total_cost_usd
        return graph, board, map_cost, diagrams_cost
```

  Mettre à jour la section `Returns:` de la docstring (4-tuple, coûts par livrable).

- [ ] **Step 2 : Site d'appel + émission `VisualsStructureFinished`** dans `generate` :

```python
            graph_source, board_source, map_struct_cost, diagrams_struct_cost = (
                self._build_structure(ctx, structure_lang, output_dir, glossary)
            )
```

  puis :

```python
        event_bus.publish(
            VisualsStructureFinished(
                timestamp=_now(),
                map_cost_usd=map_struct_cost,
                diagrams_cost_usd=diagrams_struct_cost,
            )
        )
        return self._run_languages(
            ...
            total_cost=base_cost + map_struct_cost + diagrams_struct_cost,
        )
```

- [ ] **Step 3 : `_localize_and_write`** — renvoyer `(map_cost, board_cost)`.
  Signature `-> float` → `-> tuple[float, float]` ; corps :

```python
        units = load_text_units(output_dir, language)
        map_cost = 0.0
        board_cost = 0.0
        if graph_source is not None:
            if language == structure_lang:
                graph = graph_source
            else:
                graph, map_cost = localize_graph(
                    ctx, graph_source, target_language=language,
                    glossary=glossary, target_units=units,
                )
            self._artifacts.write_text_atomic(
                out_dir / knowledge_map_filename(language),
                render_knowledge_map_html(graph),
            )
        if board_source is not None:
            if language == structure_lang:
                board = board_source
            else:
                board, board_cost = localize_board(
                    ctx, board_source, target_language=language, target_units=units
                )
            self._artifacts.write_text_atomic(
                out_dir / diagrams_filename(language),
                render_diagram_board_html(board),
            )
        return map_cost, board_cost
```

  Mettre à jour la docstring `Returns:` (couple `(coût carte, coût diagrammes)`).

- [ ] **Step 4 : `_produce_language`** — consommer le couple, émettre les coûts par
  livrable, renvoyer le total. Branche succès :

```python
            map_cost, board_cost = self._localize_and_write(
                ctx, language, structure_lang=structure_lang,
                graph_source=graph_source, board_source=board_source,
                glossary=glossary, output_dir=output_dir, out_dir=out_dir,
            )
            with manifest_lock:
                manifest.record(...)
                write_manifest(self._artifacts, visuals_dir, manifest)
            ctx.event_bus.publish(
                VisualsLanguageFinished(
                    timestamp=_now(), language=language,
                    status=PhaseStatus.SUCCEEDED, cost_usd=map_cost + board_cost,
                    error=None, map_cost_usd=map_cost, diagrams_cost_usd=board_cost,
                )
            )
            return map_cost + board_cost, False
```

  (Les branches SKIPPED / FAILED gardent `cost_usd=0.0` ; `map_cost_usd` /
  `diagrams_cost_usd` valent leur défaut `0.0`.)

- [ ] **Step 5 : Tests d'orchestrateur** :
  `.venv\Scripts\python.exe -m pytest tests/unit/app/test_visuals_orchestrator.py -q`
  → verts (les événements gagnent des champs à défaut, rien ne casse). Ajouter une
  assertion à `test_genere_les_deux_html_et_etat` vérifiant qu'un
  `VisualsLanguageFinished` non nul porte `cost_usd == map_cost_usd + diagrams_cost_usd` :

```python
    finished = [e for e in events if isinstance(e, VisualsLanguageFinished)]
    assert finished
    for e in finished:
        assert e.cost_usd == e.map_cost_usd + e.diagrams_cost_usd
```

- [ ] **Step 6 : Commit**

```
git add src/fahmi2/app/visuals_orchestrator.py tests/unit/app/test_visuals_orchestrator.py
git commit -m "feat(visuals): ventile les coûts de structure et de langue par livrable"
```

### Task 2.3 : Peuplement des coûts par cellule dans le viewmodel (TDD)

**Fichiers :**
- Modifier : `src/fahmi2/ui/viewmodels/visuals_progress.py`
- Modifier : `tests/unit/ui/viewmodels/test_visuals_progress.py`

- [ ] **Step 1 : Mettre à jour le test impacté** `test_language_lifecycle_updates_status_and_cost`
  (la cellule porte désormais un coût) + **ajouter** un test de ventilation. Remplacer
  l'assertion `assert matrix.cells[0][_COL_FR].cost_usd is None` et enrichir
  l'événement :

```python
    vm.apply_event(
        VisualsLanguageFinished(
            timestamp=_ts(), language=Language.FR, status=PhaseStatus.SUCCEEDED,
            cost_usd=0.4, error=None, map_cost_usd=0.3, diagrams_cost_usd=0.1,
        )
    )
    matrix = vm.cost_matrix_snapshot()
    assert matrix.cells[0][_COL_FR].status is PhaseStatus.SUCCEEDED
    assert matrix.cells[0][_COL_FR].cost_usd == 0.3   # Carte
    assert matrix.cells[1][_COL_FR].cost_usd == 0.1   # Diagrammes
```

  Nouveau test (à ajouter, avec `import pytest` en tête de fichier) :

```python
def test_costs_populate_cells_structure_and_total() -> None:
    vm = _vm()
    vm.apply_event(VisualsGenerationStarted(timestamp=_ts()))
    vm.apply_event(VisualsStructureStarted(timestamp=_ts()))
    vm.apply_event(
        VisualsStructureFinished(
            timestamp=_ts(), map_cost_usd=0.10, diagrams_cost_usd=0.02
        )
    )
    vm.apply_event(VisualsLanguageStarted(timestamp=_ts(), language=Language.FR))
    vm.apply_event(
        VisualsLanguageFinished(
            timestamp=_ts(), language=Language.FR, status=PhaseStatus.SUCCEEDED,
            cost_usd=0.03, error=None, map_cost_usd=0.02, diagrams_cost_usd=0.01,
        )
    )
    matrix = vm.cost_matrix_snapshot()
    assert matrix.cells[0][_COL_STRUCTURE].cost_usd == pytest.approx(0.10)
    assert matrix.cells[1][_COL_STRUCTURE].cost_usd == pytest.approx(0.02)
    assert matrix.cells[0][_COL_FR].cost_usd == pytest.approx(0.02)
    assert matrix.cells[1][_COL_FR].cost_usd == pytest.approx(0.01)
    assert matrix.grand_total == pytest.approx(0.15)
    assert vm.stats_snapshot().total_cost_usd == pytest.approx(0.15)
```

- [ ] **Step 2 : Lancer → rouge** (cellules à `None`, total sans structure).

- [ ] **Step 3 : Implémenter le viewmodel.** Helper module-level + stockage + peuplement :

```python
def _cost_by_deliverable(
    map_cost_usd: float, diagrams_cost_usd: float
) -> dict[VisualsDeliverable, float]:
    """Coût par livrable depuis les coûts carte/diagrammes d'un événement."""
    return {
        VisualsDeliverable.KNOWLEDGE_MAP: map_cost_usd,
        VisualsDeliverable.DIAGRAMS: diagrams_cost_usd,
    }
```

  Dans `__init__` : initialiser les deux dicts à vide. Dans `reset` :

```python
        self._structure_cost = {deliverable: None for deliverable in deliverables}
        self._language_cost = {
            (deliverable, language): None
            for deliverable in deliverables
            for language in languages
        }
```

  (types : `dict[VisualsDeliverable, float | None]` et
  `dict[tuple[VisualsDeliverable, Language], float | None]`.)

  Dans `apply_event`, brancher l'enregistrement des coûts :

```python
        elif isinstance(
            event,
            VisualsStructureStarted | VisualsStructureProgress | VisualsStructureFinished,
        ):
            self._apply_structure_event(event)
            if isinstance(event, VisualsStructureFinished):
                self._record_structure_cost(event)
        elif isinstance(event, VisualsLanguageStarted):
            self._status[event.language] = PhaseStatus.RUNNING
        elif isinstance(event, VisualsLanguageFinished):
            self._status[event.language] = event.status
            self._total_cost_usd += event.cost_usd
            self._record_language_cost(event)
```

  Méthodes :

```python
    def _record_structure_cost(self, event: VisualsStructureFinished) -> None:
        """Impute le coût de structure aux cellules Structure + total live."""
        cost = _cost_by_deliverable(event.map_cost_usd, event.diagrams_cost_usd)
        for deliverable in self._deliverables:
            self._structure_cost[deliverable] = cost[deliverable]
        self._total_cost_usd += event.map_cost_usd + event.diagrams_cost_usd

    def _record_language_cost(self, event: VisualsLanguageFinished) -> None:
        """Impute le coût de localisation d'une langue à ses cellules par livrable."""
        cost = _cost_by_deliverable(event.map_cost_usd, event.diagrams_cost_usd)
        for deliverable in self._deliverables:
            self._language_cost[(deliverable, event.language)] = cost[deliverable]
```

  `_structure_cell` et `_cell` portent le coût :

```python
    def _structure_cell(self, deliverable: VisualsDeliverable) -> CostMatrixCell:
        status = self._structure_status.get(deliverable)
        return CostMatrixCell(
            status=status or PhaseStatus.PENDING,
            cost_usd=self._structure_cost.get(deliverable),
            tooltip=self._structure_detail.get(deliverable, ""),
        )

    def _cell(
        self, deliverable: VisualsDeliverable, language: Language
    ) -> CostMatrixCell:
        status = self._status.get(language)
        return CostMatrixCell(
            status=status or PhaseStatus.PENDING,
            cost_usd=self._language_cost.get((deliverable, language)),
            tooltip="",
        )
```

  `cost_matrix_snapshot` passe le livrable à `_cell` :

```python
                (
                    self._structure_cell(deliverable),
                    *(self._cell(deliverable, lang) for lang in self._languages),
                ),
```

  Mettre à jour la **docstring du module** (les cellules portent désormais un coût par
  livrable ; le total des tuiles inclut la structure).

- [ ] **Step 4 : Lancer → vert** :
  `.venv\Scripts\python.exe -m pytest tests/unit/ui/viewmodels/test_visuals_progress.py -q`.

- [ ] **Step 5 : Suite + qualité** :
  `.venv\Scripts\python.exe -m pytest -q` + `ruff check .` + `mypy src tests` → verts.

- [ ] **Step 6 : Commit**

```
git add src/fahmi2/ui/viewmodels/visuals_progress.py tests/unit/ui/viewmodels/test_visuals_progress.py
git commit -m "feat(visuals): peuple les coûts par cellule dans la matrice de progression"
```

### Fin de Phase 2 — Revue de code approfondie

Checklist complète (constantes, conformité, Google style, nommage, DRY/SRP, etc.) ×
repasses `pytest`/`ruff`/`mypy --strict` jusqu'à zéro défaut. Vérifier en particulier :
non double-comptage du total (structure ajoutée une fois, langue cumulée, total faisant
foi réécrit à la fin) ; cellules SKIPPED à 0 ; `load_persisted` laisse les cellules à
`None` (pas de breakdown persisté) sans incohérence.

## Phase 3 — Documentation transverse + vérification

### Task 3.1 : Documentation

**Fichiers :** `CLAUDE.md`, `CHANGELOG.md`, `docs/01-presentation-fonctionnelle.md`,
`docs/02-presentation-technique.md`, `src/fahmi2/ui/dialogs/visuals_settings_view.py`.

- [ ] **Step 1 : `CHANGELOG.md`** — ajouter une section `## [Unreleased]` **au-dessus**
  de `## [1.6.0] — 2026-05-30`, avec :
  - `### Changed — Visualizations: density now controls knowledge-map size` (élagage par
    degré, sélection par arêtes, ratios 25/50/100 % plafonnés/planchés, isolés retirés ;
    « light » = nœuds forts et structurants ; mesures 388→40/90/355 sur un corpus réel).
  - `### Fixed — Visualizations: cost traceability in the progress matrix` (coûts par
    cellule livrable × {Structure, langues} ; total concordant avec la tuile, fin du
    `$0.0000` trompeur).

- [ ] **Step 2 : `CLAUDE.md`** — dans la puce Visualizations, préciser que la **density
  pilote la taille de la carte** via l'élagage par degré (`visuals/_pruning.py`,
  sélection par arêtes, isolés retirés, constantes `MAP_*` dans `_constants.py`) et que
  la **matrice de progression porte des coûts par cellule** (ventilation structure /
  langues par livrable). Mentionner `_pruning` dans la liste des modules `visuals/`.

- [ ] **Step 3 : `docs/01-presentation-fonctionnelle.md`** — dans la section
  Visualisations, documenter l'effet **désormais notable** des 3 niveaux de quantité de
  contenu sur la carte (légère = épure structurante, dense = graphe connexe complet).

- [ ] **Step 4 : `docs/02-presentation-technique.md`** — documenter `visuals/_pruning.py`
  (sélection par arêtes, invariant de connectivité, constantes) dans le pipeline
  `visuals/`, et l'attribution des coûts par cellule (champs d'événements + viewmodel).
  Mettre à jour le compte de tests (1362 → 1374).

- [ ] **Step 5 : Hint UI** — mettre à jour le tooltip du sélecteur de density
  (`visuals_settings_view.py`, ~L197) :

```python
        self._density_combo.setToolTip(
            self.tr(
                "Quantité de contenu : pilote la taille de la carte de connaissances "
                "(légère = éléments forts et structurants ; dense = graphe complet) et "
                "le nombre de diagrammes par section."
            )
        )
```

  *(Re-extraire/compiler l'i18n n'est pas requis pour les tests ; la chaîne EN sera
  régénérée au prochain `i18n_extract`/`i18n_compile` — noter dans le commit.)*

- [ ] **Step 6 : Commit** `docs(visuals): density carte + traçabilité coûts`.

### Task 3.2 : Vérification navigateur (offline, sans coût LLM)

- [ ] **Step 1 : Script de vérification** (`_verif_pruning_render.py`, **temporaire**,
  supprimé après) : lit `knowledge_map.fr.html` du projet réel, extrait le JSON
  `km-data`, reconstruit `GraphNode`/`GraphEdge`, applique `prune_knowledge_graph` pour
  `LIGHT` et `DENSE`, ré-assemble (`assemble_graph`) et rend via
  `render_knowledge_map_html` dans `dist/verif_light.html` / `dist/verif_dense.html`.

- [ ] **Step 2 : Contrôles** : compter les nœuds du `km-data` rendu (légère ≈ 40,
  dense ≈ 355) ; ouvrir les deux fichiers au navigateur (Playwright, **dev only, non
  packagé**) ; confirmer que la carte « légère » est lisible (≈ 40 nœuds connectés,
  aucun isolé) et que « dense » montre le graphe connexe complet.

- [ ] **Step 3 : Nettoyage** : supprimer `_verif_pruning_render.py` et les HTML de
  vérification (`dist/` est gitignoré).

### Fin de Phase 3 — Revue

Checklist docs (cohérence, complétude, cross-cutting) + `pytest`/`ruff`/`mypy` verts.

## Phase 4 — Persister la ventilation des coûts (vue persistée)

**Problème** : la ventilation par cellule n'est correcte qu'en vue live ; à la
ré-ouverture d'un projet terminé (`load_persisted`), les cellules retombent à `None`
→ totaux `$0.0000`. **Pattern à suivre** (directive utilisateur) : comme Génération
(coûts en SQLite) et Pédagogie (coûts dans l'artefact, relus par `read_generated_costs`
→ `load_persisted(generated_costs=...)`). Analogue Visuals : stocker les coûts dans le
**manifeste** (enregistrement de production, visuals-spécifique).

### Task 4.1 : Manifeste porte les coûts

**Fichiers :** `src/fahmi2/visuals/manifest.py`, `tests/unit/visuals/test_manifest.py`
(ou le test existant du manifeste).

- [ ] Constantes `_KEY_MAP_COST="map_cost_usd"`, `_KEY_DIAGRAMS_COST="diagrams_cost_usd"`,
  `_KEY_STRUCTURE_COSTS="structure_costs"` ; bump `_MANIFEST_VERSION=2`.
- [ ] `__init__` : `self._structure_costs: tuple[float, float] = (0.0, 0.0)`.
- [ ] `record(...)` : 2 params `map_cost_usd=0.0, diagrams_cost_usd=0.0` stockés dans
  l'entrée (n'affectent **pas** `is_fresh`).
- [ ] `record_structure_cost(map_cost_usd, diagrams_cost_usd)` → set `_structure_costs`.
- [ ] Accesseurs `structure_costs() -> tuple[float, float]` et
  `language_costs() -> dict[Language, tuple[float, float]]` (depuis les entrées,
  `float(entry.get(..., 0.0))`).
- [ ] `to_dict` : ajoute `_KEY_STRUCTURE_COSTS: list(self._structure_costs)` ; `from_dict`
  lenient (structure costs défaut `(0.0, 0.0)` ; `record(...)` lit les clés de coût des
  entrées avec défaut `0.0` → **rétro-compatible v1**).
- [ ] Test : round-trip `to_dict`/`from_dict` préserve structure + per-langue ; un
  manifeste v1 (sans coûts) charge avec coûts `0.0` ; `is_fresh` insensible aux coûts.

### Task 4.2 : Orchestrateur enregistre les coûts

**Fichiers :** `src/fahmi2/app/visuals_orchestrator.py`

- [ ] Dans `generate`, après l'émission de `VisualsStructureFinished` et **avant**
  `_run_languages` : `manifest.record_structure_cost(map_struct_cost,
  diagrams_struct_cost)` puis `write_manifest(self._artifacts, visuals_dir, manifest)`
  (garantit la persistance même si toutes les langues cappent/skippent).
- [ ] Dans `_produce_language` (branche succès) : `manifest.record(language, ...,
  map_cost_usd=map_cost, diagrams_cost_usd=board_cost)`.
- [ ] Tests d'orchestrateur : après un run, `read_manifest(...).structure_costs()` et
  `.language_costs()` sont non nuls et cohérents.

### Task 4.3 : Viewmodel + contrôleur reconstruisent les cellules

**Fichiers :** `src/fahmi2/ui/viewmodels/visuals_progress.py`,
`src/fahmi2/ui/visuals_controller.py`, tests associés.

- [ ] `load_persisted(...)` gagne `structure_costs: tuple[float, float] = (0.0, 0.0)` et
  `language_costs: Mapping[Language, tuple[float, float]] | None = None` ; après `reset`,
  peuple `_structure_cost` et `_language_cost` via le helper **`_cost_by_deliverable`**
  (DRY) :

```python
        smap, sdiag = structure_costs
        scost = _cost_by_deliverable(smap, sdiag)
        for deliverable in self._deliverables:
            self._structure_cost[deliverable] = scost[deliverable]
        for language, (lmap, ldiag) in (language_costs or {}).items():
            lcost = _cost_by_deliverable(lmap, ldiag)
            for deliverable in self._deliverables:
                self._language_cost[(deliverable, language)] = lcost[deliverable]
```

- [ ] Contrôleur `_load_persisted_progress` : `manifest = read_manifest(visuals_dir)` →
  `vm.load_persisted(..., structure_costs=manifest.structure_costs(),
  language_costs=manifest.language_costs())`.
- [ ] Test viewmodel : `load_persisted` avec coûts → cellules peuplées + `grand_total`
  cohérent.

### Fin de Phase 4 — Revue + vérification

Checklist complète ; `pytest` ×3 / `ruff` / `mypy --strict` verts. Vérification offline :
relire le manifeste réel après un run et confirmer que `load_persisted` reproduit la
ventilation (ou test d'intégration équivalent).

## Final — Revue exhaustive de toute la branche

Checklist complète × repasses jusqu'à conviction ; `pytest` ×3 / `ruff` / `mypy --strict`
verts ; documentation à jour.
