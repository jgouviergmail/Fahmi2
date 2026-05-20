# Changelog

Toutes les évolutions notables du projet Fahmi2.

Le format suit [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/),
et le projet adhère à [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
