# Vision chapeau — Plateforme multi-fonctionnalités & supports de révision

- **Date** : 2026-05-20
- **Statut** : **réalisé** (SP1 + SP2 + SP3 livrés ; cf. matrice §4 et clôture)
- **Portée** : document *chapeau* (contrat d'architecture + traçabilité). Ne décrit
  aucune implémentation en détail — chaque sous-projet a sa propre spec qui
  référence ce document.

## 1. Objectif

Faire évoluer Fahmi2 d'une application **mono-fonction** (dossier de vidéos →
document Markdown consolidé) vers une **plateforme multi-fonctionnalités** organisée
par onglets, puis y ajouter un **générateur de supports de révision** (flashcards,
QCM, vrai/faux, textes à trous, questions ouvertes, fiches, points clés, examen
blanc) avec **export Anki (`.apkg`)** et Markdown/PDF.

Cible utilisateur : **l'étudiant qui révise**. Pivot inspiré des fonctionnalités
étudiantes de NotebookLM (flashcards/quiz).

## 2. Principes d'architecture (le contrat que toutes les sous-specs honorent)

1. **`Project` = identité minimale** : un nom + un emplacement (le *workspace*),
   **fixé à la création et immuable ensuite**. Tout autre paramétrage est
   **spécifique à une fonctionnalité**, jamais porté par le `Project` lui-même au
   sens « réglage métier ».
2. **Navigation par onglets horizontaux** dans la zone projet ; la **sidebar des
   projets reste inchangée**. Le `LogsDock` reste partagé et reflète l'onglet actif.
3. **Abstraction « fonctionnalité » générique** : ajouter une fonctionnalité =
   enregistrer un onglet (`FeatureTab`) + un type de réglages, **sans modifier**
   `MainWindow` ni l'entité `Project`.
4. **Workspace = un répertoire par fonctionnalité** (`generation/`, `pedagogy/`, …).
5. **Réglages = composant master-detail réutilisable** (liste de catégories à
   gauche, détail à droite), hébergé dans une vue de réglages dédiée par
   fonctionnalité, pour éviter toute fenêtre surchargée quand les fonctionnalités
   se multiplient.
6. **Chaque sous-projet se termine vert et livrable** : `pytest`, `ruff check .`,
   `mypy src tests` au vert, génération fonctionnellement non régressée. Jamais de
   tronc cassé entre deux lots.

## 3. Découpage en sous-projets

| Sous-projet | Contenu | Livrable |
|-------------|---------|----------|
| **SP1 — Coquille multi-fonctionnalités** | Refonte du modèle `Project` + `GenerationSettings`, abstraction onglets, migration des projets, onglet pédagogique *stub* | App à onglets ; génération **inchangée fonctionnellement** |
| **SP2 — Générateur de supports** | Réglages + onglet pédagogique réels, orchestrateur léger, prompts, 9 types de supports, corrigés optionnels, estimation de coût | Génération des supports en fichiers (Markdown/JSON) |
| **SP3 — Exports** | Adaptateur `.apkg` (genanki : GUID stables, sous-decks, tags) + rendu Markdown/PDF | Export Anki et documents imprimables |

Chaque sous-projet suit le cycle **spec → plan → implémentation** et référence ce
chapeau. Au sein du SP2/SP3, on privilégie une **tranche verticale** (un type de
support mené de bout en bout jusqu'à l'export) avant d'élargir, pour garder des
incréments fonctionnels.

## 4. Matrice de traçabilité des exigences

| # | Exigence | Sous-projet | Statut |
|---|----------|-------------|--------|
| R1 | Navigation : onglets horizontaux dans la zone projet | SP1 | Fait (SP1) |
| R2 | `Project` = nom + emplacement uniquement | SP1 | Fait (SP1) |
| R3 | `GenerationSettings` séparés ; génération inchangée | SP1 | Fait (SP1) |
| R4 | Migration des projets existants (« repartir propre ») | SP1 | Fait (SP1) |
| R5 | Abstraction « fonctionnalité/onglet » + stub pédagogique | SP1 | Fait (SP1) |
| R6 | Workspace : un répertoire par fonctionnalité | SP1 | Fait (SP1) |
| R7 | Composant de réglages master-detail réutilisable | SP1 | Fait (SP1) |
| R8 | Onglet pédagogique avec réglages propres | SP2 | Fait (SP2/04) |
| R9 | 9 types de supports | SP2 | Fait (SP2/02–03) |
| R10 | Corrigé séparé optionnel, par support évaluatif | SP2 | Fait (SP2/03 ; `SupportArtifact.correction_markdown` + `<support>.corrige.md`) |
| R11 | Public cible (requis) + Bloom (Auto + 3 regroupements) + directives | SP2 | Fait (SP2/03–04) |
| R12 | Langues = réglage de l'onglet (défaut = langues produites) | SP2 | Fait (SP2/04 ; langues proposées = celles ayant un `consolidated.{lang}.md`) |
| R13 | Périmètre = tout, par chapitre (+ sélection de chapitres) | SP2 | **Partiel (v1)** : tout le document, **par chapitre** → Fait. **Sélection d'un sous-ensemble de chapitres : non retenue en v1** (absente de `PedagogySettings`). |
| R14 | Densité (léger / standard / dense) | SP2 | Fait (SP2/03–04) |
| R15 | Flashcards glossaire sans LLM + estimation de coût | SP2 | Fait (SP2/02 + `PedagogyCostEstimator` SP2/04) |
| R16 | Curation = fichiers éditables (pas d'éditeur intégré en v1) | SP2/SP3 | Fait (artefacts `.md`/`.json` éditables sous `pedagogy/`) |
| R17 | Export `.apkg` (genanki) : GUID stables, sous-decks, tags | SP3 | Fait (SP3/01) |
| R18 | Export Markdown / PDF (fiches, sujets, corrigés, examen blanc) | SP3 | Fait (SP3/02 ; sujet/corrigé séparés par langue) |
| R19 | Fraîcheur des supports : régénérer la génération périme les supports (détection + avertissement de régénération) | SP2 | Fait (manifeste SP2/02 + bandeau d'état SP2/04) |

> À la clôture de chaque sous-projet, mettre à jour la colonne **Statut** : c'est la
> preuve d'exhaustivité (aucune exigence silencieusement abandonnée).

> **Clôture (2026-05-21)** : SP1 + SP2 + SP3 livrés. Toutes les exigences sont **Fait**,
> sauf **R13** dont le sous-besoin « sélection d'un sous-ensemble de chapitres » est
> **explicitement reporté hors v1** (la génération couvre tout le document, par chapitre).
> **Orientation technique SP2** (§5) : c'est la piste **(b) orchestrateur dédié léger**
> (`SupportsOrchestrator`) qui a été retenue et verrouillée par le design SP2/SP3 (§2.1) —
> et non la piste (a) « favorite » du chapeau — la reprise restant assurée par le
> **manifeste de fraîcheur** (reprise *coarse*) plutôt que par le checkpoint SQLite du
> `PipelineEngine`.

## 5. Décisions produit verrouillées (synthèse du brainstorming)

- **Navigation** : onglets horizontaux.
- **Supports (cible)** : flashcards (glossaire & concepts), QCM, vrai/faux, textes à
  trous (Cloze), questions ouvertes, fiches de révision, points clés, examen blanc.
- **Corrigé** : optionnel **par support évaluatif** ; quand activé, **sujet et
  corrigé séparés** (deux documents). Flashcards/fiches/points clés : réponse
  intrinsèque, pas de corrigé séparé.
- **Difficulté/public** : **Public cible** (requis) + **objectif Bloom** (défaut
  *Auto*, sinon *Restituer* / *Comprendre & Appliquer* / *Analyser & au-delà*) +
  **directives pédagogiques libres**. Le public cible pose la base ; Bloom force
  l'angle s'il n'est pas *Auto* ; les directives se superposent.
- **Langues des supports** : réglage de l'onglet pédagogique, défaut = langues
  effectivement produites par la génération (réutilise `cross_lang` du glossaire).
- **Périmètre** : tout le document consolidé, **structuré par chapitre** ; sélection
  d'un sous-ensemble de chapitres possible.
- **Densité** : léger / standard / dense (contrôle volume & coût).
- **Curation v1** : **fichiers éditables** (pas d'éditeur intégré ; Anki édite après
  import).
- **Export** : `.apkg` + Markdown/PDF en v1 ; CSV/TSV (Quizlet) et GIFT (Moodle)
  envisagés plus tard.
- **Orientation technique SP2** *(à comparer, non pré-tranchée)* : deux pistes —
  **(a)** réutiliser le `PipelineEngine` (les phases batch sont déjà supportées
  avec `video=None` → reprise, coût et events **gratuits**, au prix d'une
  généralisation modeste de `Run`/`PhaseContext`) ; **(b)** un orchestrateur dédié
  léger réutilisant `invoke_llm` / `with_retry` / `EventBus` / l'override de
  prompts. La **reprise** ayant de la valeur (génération de supports longue et
  coûteuse : 9 supports × chapitres × langues), la piste **(a)** part favorite —
  mais la décision est **verrouillée dans la spec du SP2** après comparaison
  explicite.
- **Migration** : **« repartir propre »** — remodelage du blob de réglages à la
  lecture, sans déplacement de fichiers ; les anciens artefacts à la racine du
  workspace deviennent orphelins (non lus).
