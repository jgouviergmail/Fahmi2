# SP1 — Coquille multi-fonctionnalités (design détaillé)

- **Date** : 2026-05-20
- **Statut** : validé (brainstorming), prêt pour le plan d'implémentation
- **Chapeau de référence** :
  [`2026-05-20-supports-revision-vision-chapeau.md`](./2026-05-20-supports-revision-vision-chapeau.md)
- **Portée** : refonte du modèle `Project`, abstraction des onglets de
  fonctionnalité, migration des projets, organisation des réglages, mise en place
  d'un onglet pédagogique *stub*. **La génération reste fonctionnellement
  inchangée.**

## 1. Résultat attendu (definition of done)

- L'application affiche, dans la zone projet, des **onglets horizontaux** :
  **Génération** (le cockpit actuel, déplacé tel quel) et **Supports pédagogiques**
  (*stub* « Bientôt disponible »). La **sidebar des projets est inchangée**.
- Un `Project` ne porte que **nom + emplacement** ; les réglages de génération sont
  un bloc **`GenerationSettings`** dédié, édité depuis l'onglet Génération via une
  vue de réglages **master-detail** réutilisable.
- Les projets existants se **chargent** sans erreur (migration du blob de réglages à
  la lecture). Les **artefacts** des anciens runs ne sont pas déplacés (« repartir
  propre ») : la génération écrit désormais sous `generation/`.
- Ajouter une future fonctionnalité = enregistrer un `FeatureTab` + un type de
  réglages, **sans toucher** `MainWindow` ni `Project`.
- `pytest`, `ruff check .`, `mypy src tests` au vert ; non-régression de la
  génération vérifiée par les tests pipeline existants (adaptés).

## 2. Modèle de domaine

### 2.1 `GenerationSettings` (extrait de `ProjectSettings`)

Nouveau `@dataclass(frozen=True)` = l'actuel `ProjectSettings` **moins** `name` et
`workspace_folder` :

```
GenerationSettings(
    input_folder, source_language, output_languages,
    style_preset, style_directives, stt_provider, llm_model,
    phases_config, cost_ceiling_usd, parallelism, delete_audio_after_stt,
)
```

Le `__post_init__` **conserve** l'invariant « `phases_config` couvre exactement les
phases LLM 1..7 » et les validations de langues/plafond actuelles.

### 2.2 `Project` (identité minimale + réglages par fonctionnalité)

```
Project(
    id: ProjectId,
    name: str,
    workspace_folder: Path,            # l'emplacement transverse
    created_at: datetime,
    last_run_at: datetime | None = None,
    runs: tuple[RunId, ...] = (),
    generation: GenerationSettings | None = None,   # None = à configurer
)
```

- **Flux retenu** : (1) on crée le projet = **nom + emplacement uniquement** ;
  (2) chaque fonctionnalité se configure ensuite **depuis son propre onglet**,
  indépendamment. `generation` est donc **optionnel** : un projet neuf a
  `generation = None`.
- L'état « **fonctionnalité pas encore configurée** » est traité comme un **patron
  réutilisable de première classe** (pas une verrue) : chaque onglet sait rendre son
  état vide. La Pédagogie (SP2) en aura besoin elle aussi (non configurée au départ,
  et dépendante d'un doc consolidé existant). En SP1, l'onglet Génération affiche cet
  état « à configurer » (Lancer/estimer désactivés tant que le bloc n'est pas
  renseigné).
- **`workspace_folder` est fixé à la création et immuable** : ni la vue de réglages
  Génération ni aucun autre écran ne l'expose en édition après création. C'est ce qui
  rend sûre la dérivation du workspace par le contexte d'exécution (cf. §2.3, §4).
- Le champ typé `pedagogy: PedagogySettings | None` **n'est pas introduit ici**
  (YAGNI) ; il arrivera au SP2. En revanche le **format de persistance réserve déjà
  la clé** `"pedagogy": null` (cf. §3) pour que l'ajout SP2 soit purement additif.

### 2.3 `Run`

`Run.settings_snapshot` est **retypé `GenerationSettings`** (en SP1, seule la
génération produit des `Run`). L'emplacement n'est plus dans le snapshot : le
contexte d'exécution dérive le workspace du `Project` courant (cf. §4). **C'est sûr
parce que `workspace_folder` est immuable après création** (cf. §2.2) : il ne peut
changer ni pendant un run ni entre deux runs (reprise). Inutile donc de dupliquer le
chemin dans le `Run` — l'invariant d'immuabilité du snapshot reste respecté.

## 3. Persistance & migration

Rappel : les réglages sont stockés en **blob JSON** (`projects.settings_json`,
`runs.settings_snapshot_json`) — la refonte est donc un **remodelage de
(dé)sérialisation**, sans `ALTER TABLE`.

### 3.1 Format v2 du blob `projects.settings_json`

```json
{
  "version": 2,
  "workspace_folder": "D:/Cours/Macro/.fahmi2",
  "generation": { "input_folder": "...", "source_language": "fr", "...": "..." },
  "pedagogy": null
}
```

La colonne `projects.name` reste la source de vérité du nom (inchangée).

### 3.2 Migration « repartir propre »

- **Côté base (toujours appliquée)** : à la lecture, un blob **sans clé
  `"version"`** est reconnu comme **v1 (à plat)** et **enveloppé** en v2 :
  `name`/`workspace_folder` extraits, le reste regroupé sous `generation`,
  `pedagogy = null`. Idempotent. Même tolérance pour
  `runs.settings_snapshot_json` (on retire `name`/`workspace_folder` pour obtenir un
  `GenerationSettings`). Objectif : **aucun projet/run existant ne fait crasher** le
  chargement.
- **Côté disque (rien)** : on ne déplace **aucun** artefact. La génération écrit
  désormais sous `generation/` ; les anciens artefacts à la racine du workspace
  deviennent **orphelins** (non lus). La reprise d'un *ancien* run inachevé n'est
  pas garantie — acceptable (contexte mono-utilisateur, artefacts régénérables).
- `_apply_soft_migrations` reste le point d'entrée des migrations idempotentes ;
  ici la logique vit surtout dans la (dé)sérialisation lenient. Bump éventuel d'une
  clé `meta` `schema_version` pour la traçabilité.

### 3.3 Robustesse

Un blob **illisible/corrompu** (ni v1 ni v2 valides) lève une `Fahmi2Error` typée
(`StorageError`/`ConfigError`) avec message FR — **jamais** un crash non géré ni un
`KeyError` nu.

## 4. Workspace & chemins

- **Un répertoire par fonctionnalité** sous l'emplacement du projet :
  `generation/` (et `pedagogy/` réservé au SP2).
- Le `GenerationController` (cf. §5) construit le `PhaseContext` avec
  `workspace = project.workspace_folder / "generation"` et
  `output_dir = workspace / "output"`.
- Les handlers de phase **devraient** rester inchangés : ils écrivent sous
  `ctx.workspace` / `ctx.output_dir` (donc automatiquement sous `generation/`).
  **À vérifier au plan** : auditer les 8 handlers (0–7) pour confirmer qu'aucun
  n'écrit hors de `ctx.workspace`/`ctx.output_dir` ni n'utilise de chemin en dur.
  *(Phase 5 confirmée ; phases 0,1,2,3,4,6,7 restent à auditer.)*
- « Ouvrir le dossier de sortie » pointe vers `…/generation/output`.

## 5. Couche application & UI

### 5.1 Abstraction « fonctionnalité » (la couture forward-compatible)

Nouveau package `ui/features/` :

- `FeatureId` (`StrEnum` : `GENERATION`, `PEDAGOGY`).
- `FeatureTab` (ABC) : `feature_id`, `title`, `build_widget(parent) -> QWidget`,
  `on_project_selected(project: Project | None)`. Chaque onglet possède son propre
  contrôleur.
- `FeatureRegistry` : ordre canonique des onglets, instanciation à la construction
  de la fenêtre.

### 5.2 `MainWindow`

- La zone centrale devient un **`QTabWidget`** peuplé depuis le `FeatureRegistry`.
- La **`ProjectsSidebar` est inchangée** ; le `LogsDock` reste un dock bas
  **partagé** (alimenté par le contrôleur de l'onglet actif).
- Les menus (Fichier/Édition/?) sont conservés. « Paramètres globaux » (clés API)
  et « Modifier les prompts » restent **globaux** (non rattachés à une
  fonctionnalité).

### 5.3 Onglet Génération

- Widget = l'actuel cockpit (`ProjectHeaderBar` + `StatsStripWidget` +
  `RunMatrixView`), **déplacé sans changement de comportement**.
- `RunController` est **renommé `GenerationController`** ; sa logique est
  identique, à ceci près qu'il lit `project.generation` (au lieu de
  `project.settings`) et calcule le workspace sous `generation/` (cf. §4). Gère
  proprement `generation is None` (état « à configurer »).

### 5.4 Onglet Supports pédagogiques (*stub*)

Widget statique « Bientôt disponible » + (optionnel) un rappel des prérequis
(« nécessite un document consolidé généré »). Aucun réglage, aucune logique. Sert à
**prouver la coquille de bout en bout avec deux onglets réels**.

### 5.5 Réglages : composant master-detail réutilisable

- Nouveau composant `SettingsView` générique : **`QListWidget`** (catégories) +
  **`QStackedWidget`** (détail). Réutilisable par toutes les fonctionnalités.
- `NewProjectDialog` est **scindé** :
  - **`NewProjectDialog` (minimal)** : `nom` + `emplacement` uniquement. Crée un
    `Project` avec `generation = None`.
  - **`GenerationSettingsView`** : le formulaire actuel **moins** nom/emplacement,
    réorganisé en catégories master-detail (Entrée & langues · Style · Transcription
    · Modèle & coût · Configuration par phase). Réutilise `PhaseConfigsWidget`.
    Ouvert depuis l'onglet Génération ; crée/édite le `GenerationSettings`.

### 5.6 `app_main`

Câble le `FeatureRegistry`, le `QTabWidget`, les contrôleurs par onglet, et les
nouveaux flux « Nouveau projet (minimal) » + « Éditer les réglages de génération ».

## 6. Gestion d'erreurs

- Désérialisation : blob inconnu → `Fahmi2Error` typée + message FR (cf. §3.3).
- `generation = None` au lancement : message clair « Configurez d'abord la
  génération » ; pas d'exception.
- Conservation du contrat existant : toute exception d'un handler reste une
  `Fahmi2Error` convertie en `ErrorInfo` et exposée dans le `LogsDock`.

## 7. Tests

- **Domaine** : invariants de `GenerationSettings` (phases 1..7, langues, plafond) ;
  `Project` minimal.
- **Persistance/migration** : round-trip sérialisation v2 ; chargement d'un blob
  **v1 connu** → `Project` + `GenerationSettings` corrects ; blob corrompu →
  `Fahmi2Error` ; idempotence (relire un v2 ne le re-migre pas).
- **Pipeline** : tests existants adaptés au workspace `generation/` (les chemins
  relatifs restent identiques sous `ctx.workspace`).
- **UI** : logique du `FeatureRegistry` et du `GenerationController` testée **sans
  Qt** ; *smoke tests* `pytest-qt` pour `MainWindow` (2 onglets), `SettingsView`,
  `GenerationSettingsView`, `NewProjectDialog` minimal.
- **Fixtures** : `make_settings` (conftest) devient `make_generation_settings`
  (+ helper `make_project`). Tous les sites d'appel mis à jour.
- **Qualité** : `ruff check .` et `mypy src tests` (mode strict) au vert.

## 8. Séquencement de build (détaillé dans le plan)

1. Domaine : `GenerationSettings`, `Project` minimal, `Run` retypé.
2. Persistance : (dé)sérialisation v2 + migration lenient (projects + runs),
   `project_service`, robustesse.
3. Chemins workspace `generation/` (contexte, `output_dir`, ouverture dossier).
4. Coquille UI : `ui/features/`, `FeatureRegistry`, `GenerationTab`, `PedagogyTab`
   *stub*, `MainWindow` en `QTabWidget`.
5. Réglages : `SettingsView` master-detail ; scission `NewProjectDialog` +
   `GenerationSettingsView`.
6. Câblage `app_main` + renommage `RunController` → `GenerationController`.
7. Tests + fixtures + qualité.
8. Docs (`docs/`, `README.md`, `CLAUDE.md` si nécessaire).

## 9. Hors périmètre (YAGNI — relève d'autres sous-projets)

- Tout contenu réel de l'onglet pédagogique, les réglages pédagogiques, les
  générateurs de supports (SP2).
- Les exports `.apkg`/Markdown/PDF (SP3).
- Tout déplacement d'artefacts sur disque (décision « repartir propre »).
- Le champ domaine typé `pedagogy` (introduit au SP2 ; seule la clé JSON est
  réservée ici).

## 10. Risques & vigilance

- **Surface large** : le renommage `ProjectSettings` → `GenerationSettings` et la
  scission `Project` touchent de nombreux fichiers (domaine, persistance, services,
  UI, conftest). Changement surtout **mécanique** ; le séquencement §8 limite les
  ruptures intermédiaires.
- **Non-régression génération** : risque principal. Les tests pipeline existants
  sont le filet ; les faire passer **inchangés sur le fond** (seuls chemins/typage
  évoluent) est le critère d'acceptation.
- **État `generation = None`** : nouveaux chemins UI à couvrir (aperçu/lancement
  désactivés) pour ne pas régresser l'expérience de prévisualisation actuelle.
