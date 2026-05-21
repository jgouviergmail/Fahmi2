# Changelog

Toutes les évolutions notables du projet Fahmi2.

Le format suit [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/),
et le projet adhère à [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Non publié]

### Supprimé — Pédagogie (Lot 1c)

- **Support `flashcards_glossary` retiré** : c'était le glossaire reformaté en
  cartes (valeur de transformation quasi nulle). La pédagogie compte désormais
  **8 types de supports** (tous LLM). Le glossaire reste un document de référence
  et alimente l'injection terminologique des prompts. Les réglages persistés
  référant l'ancien support sont tolérés (type inconnu ignoré à la lecture).

### Modifié — Pédagogie (Lot 1c)

- **Langues des supports découplées de la génération (#4)** : l'onglet propose
  **toutes** les langues supportées ; les supports sont rédigés par le LLM dans la
  langue choisie même si le document source est dans une autre langue.
  L'orchestrateur résout une langue de contenu (doc consolidé existant : la cible,
  sinon la langue source, sinon la première produite) distincte de la langue cible.

### Corrigé — Glossaire homogène (Lot 1b)

- **Flashcards de glossaire vides / injection terminologique vide** : la pédagogie
  lit désormais le glossaire **sur disque** (`glossary_master.json`), exactement
  comme le pipeline (`load_glossary_master`), au lieu d'une table SQLite jamais
  peuplée. Les générateurs LLM reçoivent à nouveau les termes dans leurs prompts.

### Supprimé — Glossaire homogène (Lot 1b)

- **Anomalie de persistance du glossaire** : suppression de la table SQLite
  `glossary_terms` (migration `DROP TABLE` idempotente), des méthodes
  `upsert_glossary_term` / `list_glossary_terms`, et du service mort
  `GlossaryReconciler`. Le parsing du glossaire master et le rendu Markdown
  (`parse_glossary_master_terms`, `render_glossary_markdown_table`) remontent dans
  `domain/glossary.py` (réutilisés par pipeline et pédagogie). Aucun document
  généré n'a de table de contenu en DB : le glossaire suit le même traitement
  (artefact disque + `PhaseExecution`).

### Ajouté — Finitions UI (Lot 1a)

- **Conserver l'audio** : nouvelle case « Conserver les fichiers audio extraits »
  dans Réglages → Transcription (décochée par défaut = suppression après STT,
  comportement inchangé ; cocher conserve les `.wav`). Câblée sur le champ existant
  `GenerationSettings.delete_audio_after_stt`.

### Corrigé — Finitions UI (Lot 1a)

- **Visibilité des onglets** : la barre d'onglets de fonctionnalité (Génération /
  Supports pédagogiques) est désormais stylée (QSS) — l'onglet inactif est
  distinct (fond gris clair), l'onglet sélectionné est blanc avec un soulignement
  accent. Auparavant les onglets inactifs se fondaient dans le fond.

### Corrigé — Revue de code (SP1–SP3)

- **Export Anki** : les tags sont désormais assainis (les espaces deviennent `_`).
  Un terme de glossaire multi-mots (« Intelligence artificielle ») ne fait plus
  échouer l'export `.apkg` (`genanki` refuse les tags contenant un espace).
- **Suppression d'un projet** : tous les onglets sont notifiés
  (`MainWindow.notify_project_deleted`) — l'onglet Supports pédagogiques ne
  conserve plus une référence au projet supprimé (qui pouvait le **ressusciter**
  en base lors d'un enregistrement de réglages).
- **Réglages de génération** : modifier la génération ne **perd plus** les réglages
  Supports pédagogiques (reconstruction du `Project` via `with_generation`).
- **Formats d'export** : le menu « 📦 Exporter » ne propose plus que les formats
  **réellement cochés** dans les réglages (`PedagogySettings.export_formats`).
- **Robustesse parsing LLM** : un QCM/cloze de schéma invalide (index hors borne,
  trop de propositions, réponses vides) lève une `LLMError` typée au lieu d'une
  exception non gérée ; `read_artifact` ignore proprement un artefact d'item
  corrompu (retourne `None`).
- **Plafond de coût pédagogie** : le statut `PAUSED` est désormais documenté et le
  journal indique explicitement « plafond de coût atteint ».
- **Divers** : menu « ? → À propos » fonctionnel (nom + version) ; libellé
  « Formats d'export » dans les réglages ; helper d'ouverture de dossier mutualisé
  (`ui/_file_explorer`) ; suppression de magic numbers (estimateur de coût).

### Ajouté — Export Markdown / PDF (SP3/02)

- **Export Markdown et PDF** des supports depuis l'onglet pédagogique : le bouton
  « 📦 Exporter » propose désormais 3 formats (Anki / Markdown / PDF).
- Documents **agrégés par langue**, **sujet / corrigé séparés** (`supports.{lang}.md`,
  `supports.{lang}.corrige.md`, et variantes `.pdf`).
- Rendu PDF pur-python (`markdown` → HTML → `fpdf2`) avec police Unicode système ; repli
  Markdown si aucune police n'est résolue. Nouvelles dépendances **`markdown`**, **`fpdf2`**.

### Ajouté — Export Anki `.apkg` (SP3/01)

- **Export Anki** depuis l'onglet pédagogique (bouton « 📦 Exporter ») : les supports
  générés sont convertis en paquet `.apkg` (genanki) — flashcards (glossaire + concepts)
  → note **Basic**, textes à trous → note **Cloze**, QCM → note **custom**.
- **GUID stables** (ré-import sans doublon), **sous-decks par support**
  (`<Projet>::<support>`), **tags** (support, langue, niveau, chapitre).
- Adapter `infra/anki/genanki_exporter.py`, désérialisation `pedagogy/artifact_reader.py`,
  service `app/pedagogy_export.py`. Nouvelle dépendance **`genanki`**.

### Ajouté — Onglet Supports pédagogiques (SP2/04)

- **Onglet pédagogique réel** (remplace le stub) : barre d'actions (Réglages,
  Estimer, Générer, Pause/Reprendre/Annuler, Ouvrir le dossier), **bandeau d'état**
  (non configuré / génération requise / prêt / à jour / périmé) et **table de
  progression** (support × langue, statut, coût).
- **Réglages master-detail** (`PedagogySettingsView`) : Supports (+ corrigé séparé),
  Difficulté (public, Bloom, densité, directives), Langues (produites), Modèle & coût
  (modèle, thinking, température, plafond, formats d'export).
- **Estimation de coût** (`PedagogyCostEstimator`) par support × langue × chapitre
  selon densité et thinking ; **plafond de coût** appliqué par l'orchestrateur
  (arrêt propre à la frontière sûre).
- **`PedagogyController`** (worker `QThread`, pause/annulation) + **`PedagogyQtEventBus`**
  bridgeant les événements vers la table de progression et le panneau de logs.
- Viewmodels testables sans Qt (`PedagogyProgressViewModel`, `PedagogyStateViewModel`),
  helpers `pedagogy/sources.py` + heuristiques de coût partagées `app/_cost_common.py`.

### Corrigé

- L'édition d'un projet (renommage) n'efface plus les réglages **Supports
  pédagogiques** (`Project.pedagogy`).

### Ajouté — Générateurs de supports LLM (SP2/03)

- **8 générateurs LLM** : flashcards concepts, QCM, vrai/faux, cloze, questions
  ouvertes, fiche de révision, points clés (par chapitre) et examen blanc
  (document entier). Chacun parse une réponse **JSON typée** vers les entités de
  `domain/supports.py` et rend du Markdown.
- **8 prompts `pedagogy_*.j2` éditables** via « Édition → Modifier les prompts »
  (catalogue `PromptsService`), paramétrés par public cible, objectif Bloom,
  densité, directives et glossaire.
- **Corrigés séparés** : les supports évaluatifs marqués « corrigé séparé »
  produisent un fichier `<support>.corrige.md` distinct du sujet.
- **Dé-biaisage QCM** déterministe (répartition de la position de la bonne
  réponse sur l'ensemble des questions).
- **Retry LLM** mutualisé avec le pipeline : `default_classify` remonté dans
  `core/retry/classification.py` ; événement `SupportRetryAttempt`.
- Socle `pedagogy/generators/_base.py` (bases génériques par chapitre + mixin
  évaluatif), factory `build_default_support_registry()` (9 générateurs).

### Ajouté — Générateur de supports de révision (SP2/02)

- **Socle pédagogie** (`pedagogy/`) : `SupportGenerator` (ABC) + `SupportContext` (DI),
  `SupportGeneratorRegistry` (ordre canonique des 9 supports), parseur de chapitres du
  document consolidé, events pédagogie, **manifeste de fraîcheur** (`pedagogy/manifest.json`)
  et sérialisation d'artefacts.
- **Orchestrateur dédié léger** `SupportsOrchestrator` (`app/`) : génération par
  langue × support, écriture JSON + Markdown sous `<emplacement>/pedagogy/`, events,
  **reprise coarse** (skip des supports frais), pause/annulation.
- **Première tranche verticale** : générateur **flashcards glossaire** (sans LLM,
  recto = terme/acronyme, verso = définition), depuis le glossaire du dernier run
  *COMPLETED*.
- **Helpers LLM/JSON généralisés** (`infra/llm/invocation.py`) réutilisés par les
  handlers de phase ; `EventBus` rendu **générique** (`EventBus[E]`) pour porter aussi
  les événements pédagogie.
- `ProjectService.get_last_completed_run` + `create_project(pedagogy=…)` ; constantes
  de chemins centralisées (`GENERATION_OUTPUT_SUBDIR`, `consolidated_doc_filename`).

### Corrigé

- Un run de **génération** n'efface plus les réglages **Supports pédagogiques**
  (`Project.pedagogy`) à sa fin (régression introduite par SP2/01).

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

## [0.2.0] — 2026-05-19

Itération majeure UI + qualité de rendu du document consolidé + édition
des prompts + précision de l'estimation de coût.

### Ajouté

#### UI — thème et cockpit
- **Thème Clair Fluent** (Windows 11) : feuille de style QSS globale
  cohérente (palette accent `#0078d4`, surfaces blanches sur fond
  `#f5f7fb`), `QCheckBox::indicator` stylisé avec glyphe ✓ SVG inline.
- **StatsStrip refondu en 5 cartes** : Statut, Vidéos, Phases, Durée,
  Coût. Chaque carte = icône + titre + valeur en grand + sous-info. La
  carte **Durée** est mise à jour en direct chaque seconde par un
  `QTimer` interne tant que le Run est `RUNNING` ou `PAUSED`.
- **Run matrix colorée** : pastilles colorées par `PhaseStatus` (vert
  ✓, bleu ▶, gris ·, rouge ✗, indigo ↷), en-têtes courts lisibles
  (STT, Termes, Glossaire, Reformul., Structur., Consolid., Traduction,
  Cohérence), alignement centré.
- **Logs colorés par sévérité** (INFO gris, WARN orange, ERREUR rouge,
  FATAL rouge gras), heure compacte `HH:MM:SS`, monospace.
- **ProjectHeaderBar** : titre projet 17 px gras, boutons typés
  primary / default / danger avec hover et curseur pointer.

#### Document consolidé — élégance et navigation
- **Numérotation hiérarchique** : `# 1. Titre`, `## 1.1 Section`,
  `### 1.1.1 Sous-section`. Les numérotations LLM existantes
  (`1. `, `1.2 `, `1.2.3 - `, `1) `) sont décapées avant réécriture.
  Les blocs ``` ``` ``` sont préservés.
- **Sommaire automatique** complet (chapitres + `##` + `###`) avec
  ancres GFM cliquables et indentation hiérarchique.
- **Admonitions élégantes** : `[!NOTE]` / `[!TIP]` / `[!IMPORTANT]`
  remplacés par blockquote + emoji (📝 Remarque, 💡 Exemple, 📖
  Définition, 🎯 Exercice).

#### Glossaire — colonne expansion d'acronyme
- **Format tableau Markdown** : `| Terme | Acronyme | Signification |
  Définition |` (FR) / `| Term | Acronym | Meaning | Definition |`
  (EN).
- **Colonne `Signification`** : expansion littérale de l'acronyme
  dans sa langue d'origine (ex. *ROI* → *Return On Investment*,
  *PIB* → *Produit Intérieur Brut*). **Jamais traduite** : un
  glossaire FR contiendra `Return On Investment` pour ROI, et un
  glossaire EN contiendra `Produit Intérieur Brut` pour PIB.
- Nouveau champ `acronym_expansion` sur le domain `Term`, persisté en
  SQLite via soft migration `ALTER TABLE`.

#### Estimation de coût — prise en compte du thinking
- **Bouton « 💵 Estimer le coût »** dans le header bar. Au clic :
  scan du dossier d'entrée, probe ffprobe de chaque vidéo, popup
  détaillé (vidéos, durée totale, coût STT, coût LLM, total, plafond
  avec marge ou dépassement coloré).
- **`CostEstimator` revu** : accepte `phases_config` et applique un
  multiplicateur empirique sur les `completion_tokens` selon le
  `reasoning_effort` :
  - thinking off → ×1.0
  - thinking on (sans effort) → ×2.5
  - thinking on, **HIGH** → ×3.5
  - thinking on, **MAX** → ×6.0
- Calibrage validé sur cas réel : 2 vidéos × 19 min 27 s en HIGH sur
  toutes les phases → estimation $0.0304 vs coût réel observé ~$0.03.

#### Édition des prompts depuis l'UI
- **Menu Édition → Modifier les prompts…** ouvre `PromptsEditorDialog`
  (splitter sidebar + éditeur monospace).
- Liste des 8 templates LLM (phases 1-7 + sous-prompt 5a) avec
  astérisque ` *` si override actif.
- Boutons **Enregistrer** (validation Jinja2 obligatoire — refus si
  syntaxe invalide) et **Réinitialiser au défaut** (suppression de
  l'override avec confirmation).
- Protection contre la perte de modifications : confirmation au
  changement de phase si des modifications ne sont pas sauvegardées.
- Nouveau service `PromptsService` (app/) qui sert d'API stable pour
  le dialogue.

### Modifié

- **`SqliteState.upsert_phase_execution`** : gère explicitement le cas
  `video_id IS NULL` (phases batch) via `DELETE + INSERT`. SQLite
  traite `NULL` comme distinct dans une contrainte `UNIQUE`, donc le
  `ON CONFLICT(run_id, phase_id, video_id)` ne se déclenchait jamais
  pour les phases batch — des doublons s'accumulaient et la matrice
  pouvait afficher RUNNING même après SUCCEEDED. Migration soft
  nettoyante des doublons existants au démarrage.
- **`RunController._refresh_views_with_last_run`** : reset des vues
  (snapshots vides) si le projet sélectionné n'a pas encore de Run,
  pour éviter d'afficher l'état d'un Run appartenant à un autre
  projet.
- **`ProjectsSidebar.contextMenuEvent`** : utilise
  `viewport().mapFromGlobal(event.globalPos())` pour rester insensible
  au padding QSS sur `QListWidget` (cause : le menu contextuel
  Modifier / Supprimer ne s'affichait plus après l'application du
  thème).
- **`StatsSnapshot`** : ajout des champs `started_at`, `finished_at`,
  `elapsed_seconds` (driver de la carte Durée live).

### Corrigé

- Confirmation de suppression de projet jamais valide (utilisait `is`
  au lieu de `==` pour comparer un retour `QMessageBox.StandardButton`).
- Doublons accumulés dans `phase_executions` pour les phases batch sur
  les DBs préexistantes (voir migration soft ci-dessus).
- Estimation de coût massivement sous-estimée quand le mode thinking
  était activé (facteur 2 à 6 d'écart).

### Métriques

- 445+ tests passants (+40 par rapport à 0.1.0).
- `mypy --strict` et `ruff` propres sur 186+ fichiers source.

## [0.1.0] — 2026-05-19

Première version (alpha). Pipeline complet fonctionnel, UI cockpit dense,
packaging Windows portable opérationnel.

### Ajouté

#### Socle technique
- Hiérarchie d'exceptions typées (`Fahmi2Error` + 9 spécialisations) avec
  codes stables et registre de messages localisés FR.
- `RetryPolicy` exponentielle bornée avec jitter et `with_retry` runner.
- Logging structuré JSONL + sink Qt + redaction globale automatique des
  secrets enregistrés.
- `MigrationRunner` générique forward-only + migration baseline v0→v1.

#### Domaine
- Entités immuables (`Project`, `Run`, `VideoExecution`, `PhaseExecution`,
  `Term`, `Glossary`) + `ProjectSettings` exhaustifs avec validations
  cross-champs.
- Identifiants ULID typés (`ProjectId`, `RunId`, `VideoId` via base
  partagée `_UlidIdBase`).
- Machines d'état Run et Phase avec validation des transitions.

#### Infra
- `SqliteState` mode WAL avec 1 connexion par thread, `busy_timeout`,
  retry `SQLITE_BUSY`, test de concurrence 4 threads × 100 writes.
- `FsArtifactStore` avec writes atomiques (`.tmp` puis `rename`).
- `DPAPISecretsStore` Windows (chiffrement DPAPI utilisateur).
- `FFmpegExtractor` (subprocess avec pré-check ffprobe sur la piste audio).
- 2 providers STT : `FasterWhisperAdapter` (CUDA requis) +
  `OpenAIWhisperAdapter` (verbose JSON, mapping erreurs).
- `DeepSeekAdapter` (SDK OpenAI compatible, mode `thinking` via
  `extra_body`).
- `TfidfGlossaryRetriever` (scikit-learn cosine similarity).
- `PromptLoader` avec surcouche utilisateur `%APPDATA%/Fahmi2/prompts/` +
  8 templates Jinja2 par défaut bundlés.
- Constantes tarifaires DeepSeek v4 (Flash + Pro) centralisées dans
  `_pricing.py`.

#### Pipeline
- `PipelineEngine` avec checkpoint SQLite par phase, retry policy,
  événements typés, pause/cancel coopératif via `PauseToken`.
- `EventBus` thread-safe + 6 types d'événements (`RunStarted`,
  `PhaseStarted`, `PhaseProgress`, `PhaseFinished`, `RetryAttempt`,
  `RunFinished`).
- 8 handlers de phase :
  - Phase 0 STT (extraction audio + transcription)
  - Phase 1 extraction termes glossaire
  - Phase 2 réconciliation glossaire (batch)
  - Phase 3 reformulation (avec injection top-K glossaire)
  - Phase 4 structuration Markdown (admonitions sémantiques)
  - Phase 5 consolidation (résumés intermédiaires + méta-éléments, contenu
    des chapitres recopié tel quel)
  - Phase 6 traduction (copies pour langue source, LLM pour autres)
  - Phase 7 cohérence finale par langue

#### App services
- `ProjectService` CRUD projets.
- `RunOrchestrator` lifecycle Run (scan vidéos automatique, exécution
  pipeline, persistance, pause/cancel/resume).
- `CostEstimator` heuristique pré-run STT + LLM par phase et langue.
- `GlossaryReconciler` (import payload, load, render Markdown).
- `SecretsService` wrapper avec redaction logs auto.
- `HardwareProbe` (détection CUDA/GPU).
- `VideoScanner` (extensions `.mp4 .m4v .mkv .mov .webm`).

#### UI PySide6
- `MainWindow` cockpit dense (sidebar projets + header bar + stats strip +
  matrice vidéos × phases + dock logs).
- `RunMatrixViewModel` et `StatsStripViewModel` testables sans Qt.
- `QtEventBus` adapter EventBus → Signal Qt.
- `NewProjectDialog` assistant 1-page avec blocage STT local sans GPU.
- `GlobalSettingsDialog` (clés API + thème).
- Point d'entrée `app_main.py` avec DI complet.

#### Packaging
- Spec PyInstaller `--onedir` avec validation stricte de la présence de
  ffmpeg.
- `packaging/fetch-ffmpeg.ps1` télécharge automatiquement ffmpeg portable
  (build officiel essentials) avec vérification SHA256.
- `packaging/build.ps1` orchestration complète (fetch → clean → build).
- `packaging/make-portable-zip.ps1` génération de l'archive de distribution.
- Résolution runtime du chemin ffmpeg bundlé (`sys.frozen` + `_MEIPASS`).

#### Documentation
- Spec design complète : `docs/superpowers/specs/2026-05-19-fahmi2-design.md`.
- 12 plans d'implémentation taggés `milestone-01` à `milestone-12`.
- Suite documentaire utilisateur : présentation fonctionnelle, présentation
  technique, README, installation, paramétrage, exploitation, procédures
  techniques, guide utilisateur final.

### Métriques

- 405+ tests passants.
- Couverture globale ≥ 87 %.
- `mypy --strict` et `ruff` propres sur 177+ fichiers source.

### Limitations connues

- 2 langues uniquement (FR/EN).
- Format de sortie Markdown uniquement.
- 1 fournisseur LLM (DeepSeek).
- Pas d'auto-update.
- Pas de signature de code (avertissement SmartScreen au 1er lancement).
- Multi-utilisateur non supporté.
