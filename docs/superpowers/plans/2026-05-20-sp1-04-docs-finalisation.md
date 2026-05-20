# SP1 · Plan 04 — Documentation & finalisation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (exécution
> inline). Plan **documentaire** : aucun changement de code de production. Steps use
> checkbox (`- [ ]`) syntax.

**Goal:** Mettre la documentation à jour avec la nouvelle architecture (onglets,
`Project` minimal + `GenerationSettings`, `generation_controller`, workspace
`generation/`, création minimale + réglages via onglet), clôturer la matrice de
traçabilité du chapeau (R1–R7 → faits), et passer les vérifications finales.

**Architecture:** Édits ciblés dans `CLAUDE.md`, `README.md`, `docs/01/02/04/05/07`,
`CHANGELOG.md`, et le chapeau. Les specs/plans `superpowers/` et le design
`2026-05-19` sont des **archives datées** : on n'y touche pas. Les descriptions des
*livrables* (fichiers `consolidated.*.md`, glossaire…) sont inchangées ; seuls les
**chemins parents** (désormais sous `generation/`) et le **flux de création/réglages**
évoluent.

**Tech Stack:** Markdown ; vérifs `pytest` / `ruff` / `mypy`.

**Rappels directives :** orthographe FR parfaite, cohérence terminologique, ne pas
réécrire l'historique du CHANGELOG (ajouter une entrée).

---

## Task 1 : `CLAUDE.md`

**Files:** Modify `CLAUDE.md`

- [ ] **Step 1 : Intro `## Projet`** — ajouter une phrase sur la coquille multi-fonctionnalités.

Après la 1ʳᵉ phrase du paragraphe `## Projet` (… « 7 phases LLM DeepSeek. »), insérer :

```markdown
L'app est organisée en **onglets de fonctionnalité** (Génération aujourd'hui ;
Supports pédagogiques à venir) : un `Project` ne porte que son nom + son
emplacement, les réglages métier vivant par fonctionnalité (`GenerationSettings`).
```

- [ ] **Step 2 : Bullet `domain/`** — remplacer

```markdown
- `domain/` — entités pures immuables (`Project`, `Run`, `VideoExecution`,
  `PhaseExecution`, `Term`, `Glossary`, `ProjectSettings`), enums, IDs ULID
  typés, et **machines d'état** (`state_machine.py`) qui valident les transitions
  Run et Phase.
```

par

```markdown
- `domain/` — entités pures immuables (`Project` [identité minimale : nom +
  emplacement + réglages par fonctionnalité], `GenerationSettings`, `Run`,
  `VideoExecution`, `PhaseExecution`, `Term`, `Glossary`), enums, IDs ULID
  typés, et **machines d'état** (`state_machine.py`) qui valident les transitions
  Run et Phase.
```

- [ ] **Step 3 : Bullet `ui/`** — remplacer

```markdown
- `ui/` — PySide6 : `viewmodels/` (logique testable **sans Qt**), `widgets/`,
  `dialogs/`, `theme/` (QSS Clair Fluent), `main_window`, `run_controller`,
  `qt_event_bus`, `app_main` (point d'entrée + DI complet).
```

par

```markdown
- `ui/` — PySide6 : `features/` (abstraction onglet : `FeatureId`, `FeatureTab`,
  `FeatureRegistry`, `GenerationTab`, `PedagogyTab`-stub), `viewmodels/` (logique
  testable **sans Qt**), `widgets/` (dont `SettingsView` master-detail réutilisable),
  `dialogs/` (dont `GenerationSettingsView`), `theme/` (QSS Clair Fluent),
  `main_window` (sidebar + `QTabWidget`), `generation_controller`, `qt_event_bus`,
  `app_main` (point d'entrée + DI complet).
```

- [ ] **Step 4 : Nouveau mécanisme transverse** — insérer en tête de la liste
  `## Mécanismes transverses`, avant le bullet « Checkpoint / reprise » :

```markdown
- **Coquille multi-fonctionnalités** : la zone projet est une `QTabWidget` peuplée
  par un `FeatureRegistry` (calqué sur `PhaseRegistry`). Un `Project` ne porte que
  nom + emplacement (immuable après création) ; les réglages métier sont par
  fonctionnalité (`GenerationSettings`, `None` = « à configurer »). Le workspace a un
  dossier par fonctionnalité (`<emplacement>/generation/…`). Le blob
  `projects.settings_json` est en **v2** (`{version, workspace_folder, generation,
  pedagogy}`) avec migration *lenient* v1→v2 à la lecture. Ajouter une fonctionnalité
  = enregistrer un `FeatureTab`, sans toucher `MainWindow` ni `Project`.
```

- [ ] **Step 5 : Erreurs → UI** — remplacer `run_controller._to_log_event` par
  `generation_controller._to_log_event` (bullet « Erreurs → UI »).

- [ ] **Step 6 : UI threading** — dans le bullet « UI threading & projet affiché »,
  remplacer `Le \`RunController\` distingue` par
  `Le \`GenerationController\` (découplé du \`MainWindow\` : il reçoit
  header/stats/matrice/logs) distingue`.

- [ ] **Step 7 : Tests** — remplacer

```markdown
Fixture clé : `make_settings` (dans `tests/conftest.py`) fabrique des
`ProjectSettings` valides ; passer des kwargs pour surcharger.
```

par

```markdown
Fixtures clés (dans `tests/conftest.py`) : `make_generation_settings` fabrique des
`GenerationSettings` valides, `make_project` un `Project` minimal ; passer des kwargs
pour surcharger.
```

---

## Task 2 : `README.md`

**Files:** Modify `README.md`

- [ ] **Step 1 : Démarrage rapide (étapes 6–8)** — remplacer

```markdown
6. **Fichier → Nouveau projet** : choisir le dossier contenant vos vidéos,
   les langues, le style, valider.
7. (Optionnel) Cliquer sur **💵 Estimer le coût** pour voir le budget
   avant le lancement.
8. Cliquer sur **▶ Lancer**. Récupérer les livrables Markdown à la fin
   via le bouton **📂 Dossier de sortie** (ou dans
   `<dossier_entrée>/.fahmi2/output/`).
```

par

```markdown
6. **Fichier → Nouveau projet** : donner un nom + choisir l'emplacement du
   projet, valider.
7. Onglet **Génération → ⚙ Réglages** : choisir le dossier des vidéos, les
   langues, le style, le modèle ; valider.
8. (Optionnel) Cliquer sur **💵 Estimer le coût** pour voir le budget
   avant le lancement.
9. Cliquer sur **▶ Lancer**. Récupérer les livrables Markdown à la fin
   via le bouton **📂 Dossier de sortie** (ou dans
   `<emplacement>/generation/output/`).
```

- [ ] **Step 2 : Diagramme d'architecture (ligne `ui/`)** — remplacer

```markdown
└── ui/           PySide6 (MainWindow, widgets, dialogues, QtEventBus)
```

par

```markdown
└── ui/           PySide6 (MainWindow à onglets, features/, widgets, dialogues)
```

- [ ] **Step 3 : Statut** — remplacer la dernière ligne

```markdown
445+ tests passants, `mypy --strict` et `ruff` propres sur 186+ fichiers.
```

par

```markdown
Interface réorganisée en **onglets de fonctionnalité** (Génération + Supports
pédagogiques à venir) ; identité projet réduite à nom + emplacement, réglages par
fonctionnalité.

498 tests passants, `mypy --strict` et `ruff` propres sur 202 fichiers.
```

---

## Task 3 : `docs/02-presentation-technique.md`

**Files:** Modify `docs/02-presentation-technique.md`

- [ ] **Step 1 : Entités** — remplacer

```markdown
- Entités : `Term`, `Glossary`, `PhaseConfig`, `PhaseExecution`,
  `VideoExecution`, `Run`, `Project`, `ProjectSettings`,
  `ParallelismConfig`.
```

par

```markdown
- Entités : `Term`, `Glossary`, `PhaseConfig`, `PhaseExecution`,
  `VideoExecution`, `Run`, `Project` (identité minimale : nom + emplacement +
  réglages par fonctionnalité), `GenerationSettings`, `ParallelismConfig`.
```

- [ ] **Step 2 : `ui/dialogs/`** — remplacer

```markdown
- `ui/dialogs/` — `NewProjectDialog`, `GlobalSettingsDialog`,
```

par

```markdown
- `ui/dialogs/` — `NewProjectDialog` (minimal : nom + emplacement),
  `GenerationSettingsView` (réglages génération en master-detail),
  `GlobalSettingsDialog`,
```

- [ ] **Step 3 : `ui/main_window.py`** — remplacer

```markdown
- `ui/main_window.py` — cockpit dense + menu Édition → *Paramètres
  globaux…* / *Modifier les prompts…*.
```

par

```markdown
- `ui/main_window.py` — sidebar projets + `QTabWidget` d'onglets de
  fonctionnalité (peuplé par un `FeatureRegistry`) + menu Édition → *Paramètres
  globaux…* / *Modifier les prompts…*.
```

- [ ] **Step 4 : `ui/run_controller.py`** — remplacer

```markdown
- `ui/run_controller.py` — orchestre le lifecycle Run depuis l'UI
  (worker QThread, pause/resume/cancel via `PauseToken`, slot
  **`estimate_cost`** qui scanne le dossier, probe ffprobe et appelle
  `CostEstimator` avec `settings.phases_config`).
```

par

```markdown
- `ui/generation_controller.py` — orchestre le lifecycle Run de l'onglet
  Génération (découplé du `MainWindow` : reçoit header/stats/matrice/logs ;
  worker QThread, pause/resume/cancel via `PauseToken`, slots **`estimate_cost`**
  et **`open_generation_settings`**).
- `ui/features/` — abstraction onglet : `FeatureId`, `FeatureTab`,
  `FeatureRegistry`, `GenerationTab` (cockpit + contrôleur), `PedagogyTab` (stub).
```

- [ ] **Step 5 : `ui/app_main.py`** — remplacer

```markdown
- `ui/app_main.py` — point d'entrée + DI complet (apply_theme,
  RunController, PromptsService).
```

par

```markdown
- `ui/app_main.py` — point d'entrée + DI complet (apply_theme, onglets de
  fonctionnalité via `FeatureRegistry`, PromptsService).
```

---

## Task 4 : `docs/04-parametrage.md`

**Files:** Modify `docs/04-parametrage.md`

- [ ] **Step 1 : Intro §2** — remplacer

```markdown
## 2. Paramètres d'un projet

Accès : menu **Fichier → Nouveau projet** (ou édition d'un projet existant).
```

par

```markdown
## 2. Paramètres d'un projet

L'**identité** du projet (nom + emplacement) se définit via **Fichier → Nouveau
projet** (renommage via *Éditer* dans la sidebar ; l'emplacement est immuable
après création). Tous les autres paramètres ci-dessous sont les **réglages de
génération**, édités depuis l'onglet **Génération → ⚙ Réglages** (vue
master-detail) ; ils incluent le **dossier des vidéos**.
```

- [ ] **Step 2 : §2.1 Identification** — remplacer

```markdown
| **Nom** | Libre, sert d'étiquette dans la sidebar. Ex: « Cours macroéconomie L3 ». |
| **Dossier d'entrée** | Dossier contenant les vidéos source. Doit exister et être accessible en lecture. |
```

par

```markdown
| **Nom** | Libre, sert d'étiquette dans la sidebar. Ex: « Cours macroéconomie L3 ». |
| **Emplacement** | Dossier de travail du projet (artefacts + livrables). Immuable après création. |
```

- [ ] **Step 3 : §2.1bis — dossier des vidéos** — ajouter, juste après le tableau §2.1 :

```markdown
> Le **dossier des vidéos** (source) est un réglage de génération : il se choisit
> dans l'onglet **Génération → ⚙ Réglages → Entrée & langues**.
```

- [ ] **Step 4 : §2.7 Workspace folder** — remplacer la ligne

```markdown
| **Workspace folder** | Dossier de travail (artefacts intermédiaires) | `<input_folder>/.fahmi2/` |
```

par

```markdown
| **Emplacement (workspace)** | Dossier de travail choisi à la création. Les artefacts de génération vont sous `<emplacement>/generation/` (livrables sous `<emplacement>/generation/output/`). | choisi à la création |
```

---

## Task 5 : `docs/01-presentation-fonctionnelle.md`

**Files:** Modify `docs/01-presentation-fonctionnelle.md`

- [ ] **Step 1 : §4.1 Gestion des projets** — remplacer

```markdown
Un **Projet** dans Fahmi2 = un dossier d'entrée avec ses vidéos + un jeu de
paramètres + un historique de runs (exécutions du pipeline).

- Création d'un projet via un **assistant en une page** ;
- **Historique** complet des runs visibles dans la sidebar ;
- Possibilité de **rouvrir** un projet ancien, voir son rapport, ou le
  relancer.
```

par

```markdown
Un **Projet** dans Fahmi2 = une **identité minimale** (nom + emplacement) à
laquelle s'attachent des réglages **par fonctionnalité** + un historique de runs.
L'application est organisée en **onglets de fonctionnalité** : **Génération**
(vidéos → documents) aujourd'hui, **Supports pédagogiques** à venir.

- Création d'un projet via un **dialogue minimal** (nom + emplacement) ; les
  réglages de génération se configurent ensuite depuis l'onglet **Génération →
  ⚙ Réglages** ;
- **Historique** complet des runs visibles dans la sidebar ;
- Possibilité de **rouvrir** un projet ancien, voir son rapport, ou le
  relancer.
```

---

## Task 6 : `docs/05-exploitation.md`

**Files:** Modify `docs/05-exploitation.md`

- [ ] **Step 1 : §1.1 pré-requis** — remplacer

```markdown
2. **Projet créé** : *Fichier → Nouveau projet* (voir
   [04-parametrage.md](04-parametrage.md)).
3. **Vidéos présentes** : le dossier d'entrée du projet doit contenir au
```

par

```markdown
2. **Projet créé et génération configurée** : *Fichier → Nouveau projet*
   (nom + emplacement), puis onglet **Génération → ⚙ Réglages** (voir
   [04-parametrage.md](04-parametrage.md)).
3. **Vidéos présentes** : le dossier des vidéos (réglages de génération) doit
   contenir au
```

- [ ] **Step 2 : §4 arborescence de sortie** — remplacer

```markdown
<workspace_folder>/output/
```

par

```markdown
<emplacement>/generation/output/
```

- [ ] **Step 3 : §4 note chemin par défaut** — remplacer

```markdown
Par défaut `<workspace_folder>` = `<input_folder>/.fahmi2/`.
```

par

```markdown
L'`<emplacement>` (workspace) est choisi à la création du projet ; les artefacts
de génération vivent sous `<emplacement>/generation/`.
```

- [ ] **Step 4 : §6.1 purge des artefacts** — remplacer

```markdown
Le dossier `workspace/` contient les artefacts intermédiaires (audio
extraits, transcriptions, fichiers reformulés, etc.). Une fois les
livrables finaux récupérés, vous pouvez supprimer ce dossier pour
récupérer de l'espace.

**Attention** : sans le dossier `workspace/`, vous ne pourrez plus
```

par

```markdown
Le dossier `<emplacement>/generation/` contient les artefacts intermédiaires
(audio extraits, transcriptions, fichiers reformulés, etc.) et les livrables
(`output/`). Une fois les livrables finaux récupérés, vous pouvez supprimer les
artefacts intermédiaires pour récupérer de l'espace.

**Attention** : sans ces artefacts intermédiaires, vous ne pourrez plus
```

---

## Task 7 : `docs/07-guide-utilisateur.md`

**Files:** Modify `docs/07-guide-utilisateur.md`

- [ ] **Step 1 : §4 Créer un projet** — remplacer tout le bloc (de
  « Menu **Fichier → Nouveau projet**. Remplissez : » jusqu'à
  « Cliquez sur **OK**. Le projet apparaît dans la liste à gauche. ») par :

```markdown
**Fichier → Nouveau projet** : donnez un **nom** et choisissez un **emplacement**
(dossier de travail du projet), puis cliquez sur **OK**. Le projet apparaît dans
la liste à gauche.

Sélectionnez-le, puis dans l'onglet **Génération** cliquez sur **⚙ Réglages** pour
configurer la génération (vue à 5 catégories) :

| Catégorie | Champs |
|-----------|--------|
| **Entrée & langues** | Dossier des vidéos · Langue source · Langues de sortie |
| **Style** | Style (`décontracté`/`standard`/`professionnel`/`académique`) · Directives libres |
| **Transcription** | Provider STT (`openai_cloud` sans GPU, sinon `faster_whisper_local`) |
| **Modèle & coût** | Modèle LLM (`deepseek-v4-flash` pour démarrer) · Plafond budget |
| **Phases (1–7)** | Thinking, effort, température, retries par phase (avancé) |

Validez : l'aperçu des vidéos détectées s'affiche dans le cockpit.
```

- [ ] **Step 2 : §5 — mention des onglets** — après « 1. Sélectionnez votre projet
  dans la liste à gauche. », insérer :

```markdown
   L'application présente deux onglets : **Génération** (le cockpit ci-dessous) et
   **Supports pédagogiques** (à venir).
```

- [ ] **Step 3 : §7 chemin de sortie** — remplacer

```markdown
.fahmi2/output/
```

par

```markdown
<emplacement>/generation/output/
```

- [ ] **Step 4 : §7 dépannage GPU** — remplacer

```markdown
Vous avez sélectionné le mode local sans avoir de GPU NVIDIA. Allez dans
les paramètres du projet et basculez sur `openai_cloud`.
```

par

```markdown
Vous avez sélectionné le mode local sans avoir de GPU NVIDIA. Ouvrez l'onglet
**Génération → ⚙ Réglages → Transcription** et basculez sur `openai_cloud`.
```

- [ ] **Step 5 : §10 « Conserver les artefacts »** — remplacer

```markdown
Le dossier `.fahmi2/workspace/` contient les fichiers de travail. Si vous
```

par

```markdown
Le dossier `<emplacement>/generation/` contient les fichiers de travail. Si vous
```

- [ ] **Step 6 : §10 « Style du rendu »** — remplacer

```markdown
champ **Directives stylistiques** dans les paramètres du projet et relancez.
```

par

```markdown
champ **Directives stylistiques** dans l'onglet **Génération → ⚙ Réglages → Style**
et relancez.
```

---

## Task 8 : `CHANGELOG.md` + clôture de la matrice de traçabilité

**Files:** Modify `CHANGELOG.md`,
`docs/superpowers/specs/2026-05-20-supports-revision-vision-chapeau.md`

- [ ] **Step 1 : Entrée CHANGELOG** — insérer juste après l'en-tête (avant
  `## [0.2.0] — 2026-05-19`) :

```markdown
## [Non publié]

### Modifié — Coquille multi-fonctionnalités (SP1)

- **Interface à onglets** : la zone projet est désormais une `QTabWidget` peuplée
  par un `FeatureRegistry` — onglet **Génération** (cockpit existant) + onglet
  **Supports pédagogiques** (*stub*, à implémenter).
- **`Project` réduit à l'identité** (nom + emplacement, immuable) ; les paramètres
  métier vivent dans `GenerationSettings` (extrait de l'ancien `ProjectSettings`).
- **Création de projet minimale** (nom + emplacement) ; réglages de génération
  édités depuis l'onglet **Génération → ⚙ Réglages** (vue master-detail réutilisable
  `SettingsView`).
- **Workspace par fonctionnalité** : les artefacts de génération vivent sous
  `<emplacement>/generation/` (livrables sous `…/generation/output/`).
- **Persistance** : blob `projects.settings_json` en **v2**
  (`{version, workspace_folder, generation, pedagogy}`) avec migration *lenient*
  v1→v2 à la lecture (aucun déplacement de fichier).
- **Interne** : `RunController` → `GenerationController` (découplé du `MainWindow`) ;
  nouveau package `ui/features/`.

```

- [ ] **Step 2 : Clôture de la matrice de traçabilité** — dans le chapeau, mettre
  à jour la colonne **Statut** des lignes R1–R7 : remplacer chaque
  `À faire (SP1)` (R1 à R7) par `Fait (SP1)`. (R8–R19 inchangés : *Ultérieur*.)

---

## Task 9 : Vérifications finales + commit + clôture de branche

- [ ] **Step 1 : Cohérence docs** — vérifier qu'aucune référence obsolète ne subsiste
  hors archives.

Run: `rg -n "run_controller|RunController|ProjectSettings" README.md CLAUDE.md CHANGELOG.md docs/0*.md`
Expected: aucune occurrence (hors `docs/superpowers/` archivé). Corriger sinon.

- [ ] **Step 2 : Qualité (non-régression)** — le code n'a pas changé, mais on
  reconfirme :

Run: `.venv\Scripts\python.exe -m pytest -q`
Expected: PASS (498).
Run: `.venv\Scripts\python.exe -m ruff check .`
Expected: `All checks passed!`
Run: `.venv\Scripts\python.exe -m mypy src tests`
Expected: `Success`.

- [ ] **Step 3 : Commit**

```bash
git add -A
git commit -m "docs: actualiser la documentation pour la coquille multi-fonctionnalites (SP1/04)"
```

- [ ] **Step 4 : Clôture de la branche** — invoquer la skill
  `superpowers:finishing-a-development-branch` pour présenter les options
  d'intégration (merge `main` / PR) du SP1 complet (plans 01–04).

---

## Self-review (couverture)

- Toutes les références `run_controller`/`RunController`/`ProjectSettings` des docs
  non archivées → mises à jour (Tasks 1–7, vérifiées Task 9 Step 1).
- Flux création/réglages, onglets, chemins `generation/` → reflétés dans README +
  docs 01/04/05/07.
- Architecture développeur (CLAUDE.md, docs/02) → à jour (entités, modules ui,
  mécanisme coquille).
- Traçabilité SP1 (R1–R7) → clôturée (Task 8). Le SP1 est alors **terminé** ; SP2
  (générateur de supports) et SP3 (exports) restent à faire, avec leur propre cycle
  spec → plan → implémentation référençant le chapeau.
