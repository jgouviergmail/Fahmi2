# Cohérence des dashboards + coûts granulaires (#3)

- **Date** : 2026-05-21
- **Statut** : design validé (à implémenter directement sur `main`)
- **Origine** : retour d'usage #3 — le dashboard Supports pédagogiques ne reprend pas
  les codes UI du dashboard Génération (tuiles + matrice d'avancement) ; et la
  présentation granulaire des coûts (pédagogie) mérite d'être portée à la Génération.

## 1. Objectif

Aligner les deux dashboards sur un **langage visuel commun** (bande de tuiles +
matrice d'avancement 2D), et exposer le **coût par tâche** (granularité) sur les
deux, y compris une **estimation pré-run granulaire** avec **fourchette**.

## 2. Décisions verrouillées (brainstorming visuel)

1. **Matrice 2D** sur les deux dashboards : génération = `vidéos × phases`
   (existant) ; pédagogie = `supports × langues` (remplace la table plate).
2. **Cellule = statut + coût** : glyphe de statut colorisé **et** coût de la tâche,
   avec **colonne Total** (par ligne), **ligne Total** (par colonne) et **total
   général** (coin). Le coût par cellule est rendu **secondaire** (petit, grisé,
   sous le glyphe) ; les **totaux** sont le **signal de coût principal** (mis en
   avant). Règle **uniforme** aux deux dashboards : reste lisible sur la petite
   grille pédagogie (≤ 8 supports × 2 langues) **comme** sur la grande matrice
   génération (8 phases × N vidéos).
3. **Estimation pré-run granulaire** : décomposition **par phase** (génération) /
   **par support** (pédagogie), **même présentation**.
4. **Fourchette ±33 %** sur le **total** (format : `≈ $X` + sous-info
   `fourchette $low – $high (±33 %)`), **estimations ponctuelles par ligne** (pas de
   fourchette par ligne ; c'est la fourchette du **total** qui porte l'honnêteté).
   Ratio en **constante centralisée**, identique aux deux fonctionnalités.
   **Avertissement** quand le **haut de fourchette dépasse le plafond** de coût.
   Libellé UI **« estimation indicative »** pour signaler le caractère heuristique
   (ce n'est pas un intervalle statistique).
5. **Brique matrice générique partagée** : un composant unique `CostMatrixView`
   (+ viewmodel) utilisé par les deux dashboards ; la `RunMatrixView` existante est
   **migrée** vers ce composant. Brique de **tuile/bande** réutilisable de même.

## 3. Architecture

### 3.1 Brique partagée — matrice de coût générique (Lot 3a)

État existant : `RunMatrixView` est déjà un `QTableView` + `QAbstractTableModel`
piloté par un `MatrixSnapshot` immuable dont les cellules portent **déjà** le coût
(`cost_usd`, aujourd'hui exposé en infobulle seulement). On généralise.

- **Viewmodel** (`ui/viewmodels/cost_matrix.py`, sans Qt, testable) :
  - `CostMatrixCell(status: PhaseStatus, cost_usd: float | None, tooltip: str)`.
  - `CostMatrixSnapshot(row_label_header: str, row_labels: tuple[str, ...],
    column_labels: tuple[str, ...], cells: tuple[tuple[CostMatrixCell, ...], ...],
    row_totals: tuple[float, ...], column_totals: tuple[float, ...],
    grand_total: float)`.
  - Helpers de construction + calcul des totaux (somme des coûts non-`None`).
- **Widget** (`ui/widgets/cost_matrix_view.py`) : `QTableView` + modèle générique.
  Par cellule : **glyphe de statut coloré** (proéminent) + **coût en secondaire**
  (petit, grisé, sous le glyphe). Colonne 0 = libellé de ligne ; dernière colonne =
  **Total** ligne, dernière ligne = **Total** colonne + **total général** — les
  totaux sont **mis en avant** (gras), signal de coût principal. Réutilise les
  couleurs/symboles de statut et le QSS `#runMatrix` (renommé/partagé en
  `#costMatrix`). Infobulle conservée.
- **Cohérence** : les deux dashboards injectent leurs axes (libellés de lignes /
  colonnes) et leurs cellules ; la logique de rendu, colorisation et totaux est
  **unique**.

### 3.2 Brique partagée — tuile / bande de stats (Lot 3a)

- Extraire la carte `_StatCard` de `stats_strip.py` en widget public réutilisable
  (`ui/widgets/stat_card.py` : `StatCard` — icône + titre + valeur + sous-info +
  accent). `StatsStripWidget` (génération) est refactoré pour l'utiliser (zéro
  changement fonctionnel).
- Bande pédagogie : tuiles **Statut** / **Supports** (`x / total`) / **Langues** /
  **Coût** (total + plafond éventuel), pilotée par un snapshot dédié
  (`PedagogyStatsSnapshot`).

### 3.3 Dashboard pédagogie (Lot 3b)

- `PedagogyProgressView` : **bandeau de fraîcheur** (conservé) + **bande de tuiles**
  pédagogie + **`CostMatrixView`** (supports × langues). Remplace la table plate.
- `PedagogyProgressViewModel` : produit un `CostMatrixSnapshot` (lignes = supports
  sélectionnés, colonnes = langues, cellule = statut+coût depuis les `SupportFinished`)
  **et** un `PedagogyStatsSnapshot` (statut global, supports terminés/total, langues,
  coût cumulé). Remplace la liste plate `cells`.

### 3.4 Dashboard génération (Lot 3c)

- `RunMatrixView` migrée vers `CostMatrixView` : affichage **coût par cellule** +
  totaux (le coût est déjà dans le snapshot). En-têtes courts de phases conservés
  (libellés de colonnes injectés).
- `RunMatrixViewModel` : produit un `CostMatrixSnapshot` (lignes = vidéos, colonnes =
  phases, cellule = statut+coût `PhaseExecution.cost_usd`) + totaux. Sur cette grande
  matrice (8 phases × N vidéos), les **totaux** (colonne = coût par phase, ligne =
  coût par vidéo, général) sont le **signal de coût principal** ; le coût par cellule
  reste présent mais **discret**. La tuile **Coût** de `StatsStripWidget` reste le
  total général (cohérent avec le coin de la matrice).

### 3.5 Estimation granulaire + fourchette (Lot 3d)

- **Génération** : `CostEstimator` expose une décomposition **par phase**
  (`CostEstimation.per_phase_usd: dict[PhaseId, float]`) — les `_LOAD_FACTORS` sont
  déjà par phase, on agrège par phase au lieu de seulement STT/LLM.
- **Pédagogie** : `PedagogyCostEstimation.per_support_usd` existe déjà.
- **Fourchette** : les deux estimations gagnent `low_usd` / `high_usd` calculés à
  `total ± ESTIMATE_UNCERTAINTY_RATIO` (constante = `0.33` dans
  `app/_cost_common.py`, partagée). `low = total * (1 - r)`, `high = total * (1 + r)`.
- **Présentation harmonisée** : un rendu commun (helper de formatage) produit la
  **décomposition** (item → coût ponctuel) + le **total avec fourchette** (format A) +
  l'**avertissement plafond** si `high_usd > cost_ceiling_usd`. Les deux dialogues
  « Estimer le coût » l'utilisent.

## 4. Flux de données

Inchangé dans son principe : events / snapshots → **viewmodels** (purs) → **widgets**.
Les viewmodels produisent désormais des `CostMatrixSnapshot` + snapshots de tuiles ;
les estimateurs produisent des décompositions + fourchette. Aucun changement moteur
(pipeline/orchestrateur) ni domaine.

## 5. Découpage (4 lots, chacun vert + commit)

- **3a — briques partagées** : `CostMatrixView` + `cost_matrix` viewmodel ; `StatCard`
  extrait + `StatsStripWidget` refactoré dessus. (Aucun changement visible ; socle.)
- **3b — dashboard pédagogie** : tuiles + matrice 2D (via 3a) ; bandeau conservé ;
  viewmodel pédagogie remanié.
- **3c — dashboard génération** : migration `RunMatrixView` → `CostMatrixView` (coût
  par cellule + totaux).
- **3d — estimation granulaire + fourchette** : par phase (génération), `low/high`
  (±33 %), avertissement plafond, dialogues d'estimation harmonisés.

Ordre : **3a** (socle) → **3b** / **3c** (consommateurs, indépendants entre eux) →
**3d** (transverse estimation). Chaque lot a son propre plan détaillé.

## 6. Tests

- Viewmodels (`cost_matrix`, pédagogie remanié, stats pédagogie) : unitaires **sans
  Qt** — construction de la grille, calcul des totaux, mapping statut+coût.
- Estimateurs : `per_phase_usd` (génération), `low/high` (±33 %), seuil
  d'avertissement plafond — unitaires.
- Widgets (`CostMatrixView`, bandes, dialogues) : smoke `pytest-qt`.
- Non-régression : la matrice génération reste fonctionnelle (mêmes statuts/couleurs).

## 7. Hors périmètre

- Pas de changement du **moteur** (pipeline/orchestrateur), du **domaine**, ni de la
  **persistance**.
- Densité : avec 8 colonnes de phases, le coût par cellule est rendu **discret**
  (petit, grisé) ; les **totaux** (mis en avant) sont l'agrégat de lecture rapide.
  Pas de bascule Statut/Coût en v1 (A1 raffiné : statut proéminent, coût secondaire,
  totaux principaux).
- #6 (workspaces versionnés) reste un sous-chantier distinct.

## 8. Vérifications

Chaque lot se termine **vert** : `pytest`, `ruff check .`, `mypy src tests`.
Documentation mise à jour par lot (`CHANGELOG` ; `docs/02` pour les nouveaux
composants UI partagés ; `CLAUDE.md` si l'inventaire `ui/` évolue).
