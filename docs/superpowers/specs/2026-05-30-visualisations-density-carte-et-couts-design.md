# Visualisations — différenciation density de la carte + attribution des coûts par cellule

**Date** : 2026-05-30
**Statut** : conception validée (brainstorming), prêt pour le plan d'implémentation
**Périmètre** : fonctionnalité Visualisations uniquement (carte de connaissances + matrice de progression). Aucun impact sur Génération / Pédagogie / Dialogue.

## 1. Contexte et problèmes

Deux défauts observés sur des projets riches (corpus de 12 cours) :

1. **La « quantité de contenu » (density) ne différencie quasiment pas la carte de
   connaissances.** Le réglage `SupportDensity` (`LIGHT` / `STANDARD` / `DENSE`) ne
   pilote aujourd'hui qu'**un seul levier** : `MAX_SEMANTIC_NODES_PER_UNIT` (4 / 7 / 12),
   le plafond de nœuds **sémantiques par unité de texte**. Or :
   - l'**épine glossaire** (`build_glossary_skeleton`) injecte **tous** les termes du
     glossaire comme nœuds, **sans aucun plafond de density** ;
   - **aucun élagage** n'existe : les termes de glossaire jamais reliés restent comme
     **nœuds isolés** (`community._build_nx_graph` ajoute « tous les nœuds, même isolés ») ;
   - le plafond sémantique est **par unité** (× ~131 unités ici).

   Résultat : sur un document riche, « légère » reste une carte énorme, à peine
   distinguable de « dense ».

2. **La traçabilité des coûts de la matrice de progression est trompeuse.** Le
   viewmodel `VisualsProgressViewModel` met délibérément `cost_usd=None` sur **toutes**
   les cellules (le coût n'est porté que par la tuile « Coût »). Mais le composant
   partagé `build_cost_matrix` calcule malgré tout les totaux par ligne / colonne /
   général (`None` comptant pour 0) → la grille affiche **$0.0000 partout**, en
   contradiction directe avec la tuile « Coût » qui affiche le vrai total (ex. $0.17).

## 2. Objectifs / non-objectifs

**Objectifs**
- Rendre les trois niveaux de density **nettement différents** sur la carte de
  connaissances, « légère » ne gardant que les éléments **forts et structurants**.
- Garantir une **lisibilité absolue** de « légère » même sur des corpus très riches.
- Afficher une **vraie traçabilité des coûts** dans la matrice (par cellule
  livrable × {Structure, langues}), dont le total **concorde** avec la tuile « Coût ».

**Non-objectifs**
- Aucun changement sur la **galerie de diagrammes** (ses plafonds 1 / 2 / 3 par unité
  différencient déjà raisonnablement les niveaux). La density continue de les piloter à
  l'identique.
- Pas de hiérarchie multi-niveaux de communautés (reste hors périmètre, cf. spec V1).
- Pas d'appel LLM supplémentaire pour l'élagage (déterministe, gratuit).

## 3. Décisions validées (issues du brainstorming)

| Sujet | Décision |
|-------|----------|
| Périmètre | **Carte de connaissances uniquement** |
| Critère d'importance | **Connectivité dans le graphe (degré)** — déterministe, gratuit |
| Élagage des isolés | **Supprimés à tous les niveaux** (y compris `dense`) |
| Dimensionnement | **Relatif 25 % / 50 % / 100 %**, **plafonné** (légère/standard) et **planché** |
| `dense` | **100 % du connexe** (non plafonné) = le maximum |
| Coûts | **Attribution réelle par cellule** livrable × colonne (volet 2) |
| Livraison | **Une spec → un plan** couvrant les deux volets |

## 4. Volet 1 — Élagage par degré de la carte de connaissances

### 4.1 Nouvelles constantes (`visuals/_constants.py`)

```python
#: Fraction des nœuds connectés conservés sur la carte, par niveau de densité
#: (les nœuds isolés sont d'abord retirés ; cf. _pruning.prune_knowledge_graph).
MAP_CONNECTED_NODE_RATIO_BY_DENSITY: dict[SupportDensity, float] = {
    SupportDensity.LIGHT: 0.25,
    SupportDensity.STANDARD: 0.50,
    SupportDensity.DENSE: 1.0,
}

#: Plafond absolu de nœuds de la carte par niveau (None = non plafonné).
#: Garantit la lisibilité de « légère » / « standard » sur les corpus très riches.
MAP_NODE_CAP_BY_DENSITY: dict[SupportDensity, int | None] = {
    SupportDensity.LIGHT: 40,
    SupportDensity.STANDARD: 90,
    SupportDensity.DENSE: None,
}

#: Plancher de nœuds de la carte (évite une carte quasi vide sur un petit document).
MAP_MIN_NODES = 12
```

### 4.2 Nouveau module pur `visuals/_pruning.py`

Fonction unique, sans dépendance Qt / réseau / LLM :

```python
def prune_knowledge_graph(
    nodes: tuple[GraphNode, ...],
    edges: tuple[GraphEdge, ...],
    *,
    density: SupportDensity,
) -> tuple[tuple[GraphNode, ...], tuple[GraphEdge, ...]]:
    ...
```

**Algorithme** (déterministe) :

1. **Degré** de chaque nœud = nombre d'arêtes incidentes (chaque `GraphEdge` compte 1
   à chaque extrémité), cohérent avec `idea_chains`.
2. **Garde-fou dégénéré** : s'il n'y a **aucune arête**, retourner `(nodes, edges)`
   inchangés (rien à élaguer par degré ; on ne réduit pas la carte à vide).
3. **Suppression des isolés** : ne garder que les nœuds de degré ≥ 1. Base `N` = leur
   nombre.
4. **Cible** :
   ```
   raw    = ceil(ratio[density] * N)
   floor_ = min(MAP_MIN_NODES, N)
   target = max(raw, floor_)
   cap    = MAP_NODE_CAP_BY_DENSITY[density]
   if cap is not None: target = min(target, cap)
   target = min(target, N)
   ```
5. **Sélection** : trier les nœuds connectés par `(-degré, id)` (départage
   déterministe et invariant par langue, l'`id` étant `type:slug`) ; garder les
   `target` premiers.
6. **Sous-graphe induit** : ne garder que les arêtes dont **les deux** extrémités sont
   conservées.
7. **Passe de connectivité (point fixe)** : retirer itérativement tout nœud devenu
   isolé dans le sous-graphe induit (un *hub* dont tous les voisins ont été élagués),
   en retirant aussi ses arêtes, jusqu'à stabilité. **Invariant final garanti : tout
   nœud conservé porte au moins une arête conservée.**
8. Retourner `(nœuds conservés, arêtes conservées)`.

### 4.3 Point d'insertion (`app/visuals_orchestrator._build_structure`)

Entre `resolve_graph` et `assemble_graph` (une ligne) :

```python
nodes, edges = resolve_graph(...)
# ... agrégation du coût embeddings ...
nodes, edges = prune_knowledge_graph(nodes, edges, density=ctx.settings.density)
graph = assemble_graph(nodes, edges, language=structure_lang)
```

Conséquence : **communautés, rapports de communauté et idea-chains** se construisent
sur le graphe **élagué** → cohérent (lighter = moins de tout) et **moins cher** en
« légère » (moins de communautés à reporter).

### 4.4 Invariants & déterminisme

- La structure est extraite **une seule fois** (langue de structure) puis traduite ;
  l'élagage opère sur le graphe **source**, **avant** traduction → l'**ensemble de
  nœuds élagué est identique dans les 5 langues**.
- Même graphe d'entrée + même density → même sortie (tri stable par `id`).
- Changer la density ré-invalide déjà tout via le **hash de réglages** du manifeste de
  fraîcheur — pas de nouveau souci de cache/reprise.

### 4.5 Effets de bord assumés (documentés)

- L'épine glossaire **ne montre plus tous les termes** : un terme **jamais relié**
  disparaît de la carte (il reste dans le **glossaire exporté**). C'est l'effet
  recherché (« forts et structurants »).
- En conséquence, **même `dense`** est plus petit qu'auparavant (≈ la carte actuelle
  **moins les nœuds isolés**) — voulu (bruit relationnel supprimé).
- L'estimation de coût pré-run (`VisualsCostEstimator`) **reste inchangée** et devient
  **conservatrice** (l'élagage rend « légère » un peu moins cher que l'estimation,
  jamais plus). Pas de modification requise.

## 5. Volet 2 — Attribution réelle des coûts par cellule

### 5.1 Constat : les coûts sont déjà séparables par livrable

- **Structure** (`_build_structure`) : `extraction.total_cost_usd` (graphe) + coût
  embeddings de résolution + `report_cost` + `chain_cost` → **Carte** ;
  `diagrams.total_cost_usd` → **Diagrammes**.
- **Par langue** (`_localize_and_write`) : `graph_cost` (localisation graphe) →
  **Carte** ; `board_cost` (localisation board) → **Diagrammes**.

Ils sont aujourd'hui **sommés dans un scalaire unique** puis perdus.

### 5.2 Changements

**Domaine événements (`visuals/events.py`)** — coûts par livrable :
- `VisualsStructureFinished` : ajout de `map_cost_usd: float` et
  `diagrams_cost_usd: float` (aujourd'hui l'événement ne porte aucun coût).
- `VisualsLanguageFinished` : ajout de `map_cost_usd: float` et
  `diagrams_cost_usd: float` ; `cost_usd` reste le **total** de la langue
  (= somme des deux), pour la tuile.

**Orchestrateur (`app/visuals_orchestrator.py`)** :
- `_build_structure` retourne les coûts de structure **par livrable** (au lieu d'un
  `cost` unique) ; émet `VisualsStructureFinished(map_cost_usd=…, diagrams_cost_usd=…)`.
- `_localize_and_write` retourne `(map_cost, board_cost)` ; `_produce_language` les
  propage dans `VisualsLanguageFinished`.
- L'agrégat total (`cost_state["total"]`, tuile, `run_state.json`) est **inchangé**
  (somme de tous les coûts) — seule la **ventilation** est ajoutée.

**Viewmodel (`ui/viewmodels/visuals_progress.py`)** :
- Stockage : `self._structure_cost: dict[VisualsDeliverable, float | None]` et
  `self._language_cost: dict[tuple[VisualsDeliverable, Language], float | None]`.
- `apply_event` peuple ces dicts depuis `VisualsStructureFinished` /
  `VisualsLanguageFinished` (par livrable).
- `_structure_cell(deliverable)` porte `cost_usd = self._structure_cost[deliverable]`.
- `_cell` devient `_cell(deliverable, language)` et porte
  `cost_usd = self._language_cost[(deliverable, language)]` (statut toujours partagé
  par langue).
- Le **total live** de la tuile inclut désormais aussi le coût de structure (ajouté à
  la réception de `VisualsStructureFinished`), le total **faisant foi** restant celui
  de `VisualsGenerationFinished`.
- Mise à jour de la docstring du module (les cellules **portent** désormais un coût).

### 5.3 Résultat attendu

La grille `build_cost_matrix` calcule alors des totaux **réels** : colonne Structure
(Carte ≈ \$0.10 / Diagrammes ≈ \$0.004), colonnes de langues (Carte / Diagrammes par
langue), **total général concordant avec la tuile** (ex. \$0.17). Cellules SKIPPED
(langue fraîche) = \$0 ; cohérent en reprise partielle.

## 6. Fichiers touchés

**Créés**
- `src/fahmi2/visuals/_pruning.py` — élagage par degré.
- `tests/unit/visuals/test_pruning.py` — tests de l'élagage.

**Modifiés**
- `src/fahmi2/visuals/_constants.py` — 3 constantes (ratios / plafonds / plancher).
- `src/fahmi2/app/visuals_orchestrator.py` — insertion de l'élagage ;
  coûts de structure / langue par livrable ; émission enrichie.
- `src/fahmi2/visuals/events.py` — champs de coût par livrable sur 2 événements.
- `src/fahmi2/ui/viewmodels/visuals_progress.py` — stockage + peuplement des coûts par
  cellule ; signature `_cell` ; docstring.
- Tests existants : `tests/unit/ui/viewmodels/test_visuals_progress.py`,
  `tests/unit/app/test_visuals_orchestrator.py` (coûts par livrable),
  éventuellement `test_graph_extractor`/`test_entity_resolver` si réutilisés.

## 7. Tests

**`test_pruning.py`** (pur, sans Qt) :
- isolés (degré 0) supprimés à tous les niveaux ;
- ratio appliqué (`LIGHT` ≈ 25 %, `STANDARD` ≈ 50 %, `DENSE` = 100 % du connexe) ;
- **plafond** : sur grand graphe, `LIGHT` ≤ 40 et `STANDARD` ≤ 90 ;
- **plancher** : petit graphe → au moins `min(MAP_MIN_NODES, N)` ;
- **passe de connectivité** : un *hub* dont les feuilles sont élaguées est lui-même
  retiré (aucun nœud final isolé) ;
- **arêtes induites** : aucune arête vers un nœud supprimé ;
- **déterminisme** : deux exécutions identiques → sortie identique ;
- **dégénéré** : graphe sans arête → inchangé (pas de carte vide).

**Viewmodel** : cellules portant les coûts attendus par livrable ; total de matrice =
somme = total tuile ; cas SKIPPED = \$0 ; structure RUNNING → coût `None`.

**Orchestrateur** : `_build_structure` / `_produce_language` renvoient les coûts par
livrable ; événements émis avec les bons champs ; total agrégé inchangé.

Vérifications finales obligatoires : `pytest`, `ruff check .`, `mypy --strict src tests`
tous verts (relancer jusqu'à zéro défaut). Re-rendu navigateur d'une carte « légère »
vs « dense » pour confirmer la différence visible (Playwright, dev uniquement, **non
packagé**).

## 8. Documentation à mettre à jour

- `CLAUDE.md` — section Visualisations : la density pilote désormais la **taille de la
  carte** (élagage par degré, isolés retirés) ; la matrice porte des **coûts par
  cellule**.
- `CHANGELOG.md` — nouvelle section `[Unreleased]` (deux entrées : Changed density carte
  + Fixed traçabilité coûts).
- `docs/01-presentation-fonctionnelle.md` / `docs/02-presentation-technique.md` —
  comportement density de la carte + ventilation des coûts.
- Aide du sélecteur de density dans `ui/dialogs/visuals_settings_view.py` (préciser
  l'effet sur la taille de la carte).

## 9. Risques / points ouverts

- **Cardinalité finale < cible** : la passe de connectivité peut retirer quelques
  nœuds supplémentaires (hubs orphelins). Accepté : l'invariant « tout nœud affiché est
  relié » prime sur l'atteinte exacte de la cible.
- **Corpus à très faible connectivité** : si le LLM a extrait peu de relations, la
  carte sera petite même en `dense`. C'est fidèle au contenu réel ; le garde-fou
  dégénéré évite seulement le cas pathologique « zéro arête ».
- **Seuils** (0.25 / 0.50 / 1.0 ; 40 / 90 ; 12) : centralisés dans `_constants.py`,
  ajustables sans changement de logique.
