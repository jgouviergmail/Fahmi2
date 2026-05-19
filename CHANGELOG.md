# Changelog

Toutes les évolutions notables du projet Fahmi2.

Le format suit [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/),
et le projet adhère à [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
