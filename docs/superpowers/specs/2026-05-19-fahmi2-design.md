# Fahmi2 — Design Document

**Date** : 2026-05-19
**Auteur** : co-conception utilisateur + assistant
**Statut** : Spec validée par l'utilisateur, prête pour la phase de planification d'implémentation
**Plateforme cible** : Windows 11 (10 minimum), mono-utilisateur, support GPU NVIDIA optionnel

---

## 1. Vision & objectifs

### 1.1 Problème

Un enseignant en économie et finance dispose d'un volume important de vidéos MP4 de cours oraux (FR ou EN, 25 fps, audio 48 kHz / 196 kbps, 10 à 50 vidéos par batch typique). Ce savoir reste captif du format vidéo : non recherchable, non réutilisable, non formalisé à l'écrit.

### 1.2 Objectif produit

Application desktop Windows locale qui transforme un dossier de vidéos en :

- **Un document Markdown autonome par vidéo** : titre, structure hiérarchique, introduction, conclusion, contenu reformulé fidèlement mais dans les règles de l'art de la langue de sortie.
- **Un glossaire commun** des termes techniques, experts ou professionnels, avec définitions contextualisées.
- **Un document consolidé** par langue de sortie demandée, avec titre global, introduction générale, plan d'ensemble, conclusion générale.

Le tout en garantissant : fidélité au discours oral (pas d'hallucination), reformulation soignée et adaptée au style cible, cohérence terminologique inter-vidéos.

### 1.3 Principes directeurs

- **User-friendly** : utilisable par un non-expert. Aucune édition manuelle de fichiers n'est nécessaire. Tout passe par l'UI.
- **Installation très simple** : distribution portable (.zip), pas de prérequis système (ffmpeg bundlé, modèle whisper téléchargé au 1er lancement).
- **Robustesse industrielle** : excellence sur logs, erreurs, exceptions, retries, gestion des ressources. Aucun travail perdu en cas de crash / pause / annulation.
- **Code générique, extensible, évolutif** : respect strict de DRY, YAGNI, KISS, SRP, SoC, Boy Scout Rule, composition over inheritance. Architecture en ports/adapters pour swap futur de providers.

---

## 2. Périmètre v1

### 2.1 Inclus

- Pipeline complet vidéo → Markdown structuré + glossaire + consolidé multilingue
- 2 providers STT : faster-whisper-large-v3-turbo (local) et OpenAI Whisper (cloud, `whisper-1`)
- 1 provider LLM : DeepSeek v4 (`deepseek-v4-flash` et `deepseek-v4-pro`)
- 2 langues de sortie : FR et EN
- 4 styles de rendu : décontracté, standard, professionnel, académique + directives libres
- Concept de Projet persistant avec historique de runs
- Pause / annulation / reprise fine par phase
- Estimation de coût pré-run + plafond budget avec arrêt propre
- UI cockpit dense (matrice vidéos × phases, logs live, sidebar projets)
- Éditeur de prompts dans l'UI (Settings)
- Stockage des clés API via Windows DPAPI
- Logs structurés JSONL + panneau UI

### 2.2 Explicitement HORS v1

- Multi-utilisateur, collaboration, cloud sync
- Édition manuelle des transcriptions dans l'UI
- Export PDF / DOCX / HTML (Markdown uniquement ; conversion externe via pandoc possible)
- Support de langues autres que FR / EN
- Support de providers LLM autres que DeepSeek (architecture prête mais non implémenté)
- Auto-update de l'application
- Signature de code

---

## 3. Architecture

### 3.1 Vue d'ensemble en couches

```
┌────────────────────────────────────────────────────────────────────┐
│                          UI (PySide6 — MVVM)                       │
│  MainWindow  ProjectsSidebar  RunMatrixView  LogsDock  SettingsDlg │
└─────────────────────────────┬──────────────────────────────────────┘
                              │ signaux Qt, ViewModels
┌─────────────────────────────▼──────────────────────────────────────┐
│                       Application (use-cases)                      │
│   ProjectService · RunOrchestrator · CostEstimator                 │
│   GlossaryReconciler · SettingsService · SecretsService            │
└────┬──────────┬───────────┬──────────────┬───────────┬─────────────┘
     │          │           │              │           │
     ▼          ▼           ▼              ▼           ▼
┌────────┐ ┌─────────┐ ┌─────────┐  ┌────────────┐ ┌─────────┐
│ Domain │ │Pipeline │ │  Infra  │  │   Core     │ │  Tests  │
│ pure   │ │ 7 phases│ │ stt/llm │  │ log/retry/ │ │ fakes & │
│ models │ │ + state │ │ ffmpeg/ │  │ errors/cfg │ │ fixtures│
│        │ │ machine │ │ sqlite/ │  │ ids        │ │         │
│        │ │         │ │ dpapi   │  │            │ │         │
└────────┘ └─────────┘ └─────────┘  └────────────┘ └─────────┘
```

### 3.2 Arborescence du code

```
fahmi2/
├── pyproject.toml
├── README.md
├── LICENSE
├── .gitignore
├── .pre-commit-config.yaml
├── docs/
│   └── superpowers/specs/2026-05-19-fahmi2-design.md
├── src/fahmi2/
│   ├── core/
│   │   ├── logging/      # structured logs, sinks (JSONL, Qt, console)
│   │   ├── errors/       # Fahmi2Error hierarchy + codes + messages.fr.json
│   │   ├── retry/        # RetryPolicy, with_retry, classifiers
│   │   ├── config/       # AppConfig, paths, env detection (CUDA, etc.)
│   │   ├── migrations/   # MigrationRunner, v01_to_v02.py, ...
│   │   ├── retrieval/    # GlossaryRetriever (TF-IDF v1, swap-friendly)
│   │   └── ids.py        # ULID helpers
│   ├── domain/
│   │   ├── project.py
│   │   ├── run.py
│   │   ├── phase.py
│   │   ├── glossary.py
│   │   └── enums.py      # RunStatus, PhaseStatus, PhaseId, Language, etc.
│   ├── pipeline/
│   │   ├── engine.py             # PipelineEngine (moteur d'exécution pur, pas de UI ni de notion "Projet")
│   │   ├── phase_registry.py
│   │   ├── handlers/
│   │   │   ├── _base.py             # PhaseHandler ABC
│   │   │   ├── phase_0_stt.py
│   │   │   ├── phase_1_term_extraction.py
│   │   │   ├── phase_2_glossary_reconciliation.py
│   │   │   ├── phase_3_reformulation.py
│   │   │   ├── phase_4_structuration.py
│   │   │   ├── phase_5_consolidation.py
│   │   │   ├── phase_6_translation.py
│   │   │   └── phase_7_coherence.py
│   │   ├── state_machine.py
│   │   ├── pause_token.py
│   │   └── event_bus.py
│   ├── infra/
│   │   ├── stt/
│   │   │   ├── _interface.py        # STTProvider Protocol
│   │   │   ├── faster_whisper_adapter.py
│   │   │   └── openai_whisper_adapter.py
│   │   ├── llm/
│   │   │   ├── _interface.py        # LLMProvider Protocol
│   │   │   └── deepseek_adapter.py
│   │   ├── audio/
│   │   │   └── ffmpeg_extractor.py
│   │   ├── storage/
│   │   │   ├── sqlite_state.py
│   │   │   └── fs_artifacts.py
│   │   ├── secrets/
│   │   │   └── dpapi_store.py
│   │   ├── prompts/
│   │   │   ├── loader.py            # default → %APPDATA% override
│   │   │   └── defaults/            # *.j2 templates (bundled)
│   │   └── render/
│   │       └── markdown_renderer.py
│   ├── app/
│   │   ├── project_service.py
│   │   ├── run_orchestrator.py   # RunOrchestrator (use-case applicatif : lifecycle, snapshot, UI events)
│   │   ├── cost_estimator.py
│   │   ├── glossary_reconciler.py
│   │   ├── hardware_probe.py     # détection CUDA/GPU au démarrage de l'app
│   │   ├── settings_service.py
│   │   └── secrets_service.py
│   ├── ui/
│   │   ├── main_window.py
│   │   ├── widgets/
│   │   │   ├── projects_sidebar.py
│   │   │   ├── run_matrix_view.py
│   │   │   ├── stats_strip.py
│   │   │   ├── logs_dock.py
│   │   │   └── ...
│   │   ├── dialogs/
│   │   │   ├── new_project_dialog.py
│   │   │   ├── global_settings_dialog.py
│   │   │   ├── phase_detail_dialog.py
│   │   │   ├── prompt_editor_dialog.py
│   │   │   └── project_report_dialog.py
│   │   ├── viewmodels/              # logique testable hors Qt
│   │   └── qt_event_bus.py
│   └── packaging/
│       ├── pyinstaller.spec
│       ├── bundle_ffmpeg.ps1
│       └── icons/
├── tests/
│   ├── fixtures/
│   ├── unit/
│   ├── integration/
│   └── e2e/
└── scripts/
    ├── build.ps1
    └── make-portable-zip.ps1
```

---

## 4. Modèle de domaine

### 4.1 Entités principales

```python
@dataclass(frozen=True)
class ProjectId: value: str             # ULID
class RunId:     value: str
class VideoId:   value: str

class Language(StrEnum):
    FR = "fr"
    EN = "en"

class StylePreset(StrEnum):
    DECONTRACTE   = "decontracte"
    STANDARD      = "standard"
    PROFESSIONNEL = "professionnel"
    ACADEMIQUE    = "academique"

class PhaseId(StrEnum):
    STT                       = "phase_0_stt"
    TERM_EXTRACTION           = "phase_1_term_extraction"
    GLOSSARY_RECONCILIATION   = "phase_2_glossary_reconciliation"
    REFORMULATION             = "phase_3_reformulation"
    STRUCTURATION             = "phase_4_structuration"
    CONSOLIDATION             = "phase_5_consolidation"
    TRANSLATION               = "phase_6_translation"
    COHERENCE                 = "phase_7_coherence"

class RunStatus(StrEnum):
    CREATED = "created"
    RUNNING = "running"
    PAUSED = "paused"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    FAILED = "failed"

class PhaseStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"      # checkpoint hit, déjà fait
```

```python
@dataclass(frozen=True)
class PhaseConfig:
    enabled_thinking: bool = False
    temperature: float = 0.3
    max_retries: int = 5

@dataclass(frozen=True)
class ParallelismConfig:
    stt_cloud_workers: int = 3
    llm_workers: int = 4
    # stt local : toujours 1 (limite GPU)

@dataclass(frozen=True)
class ProjectSettings:
    name: str
    input_folder: Path
    workspace_folder: Path                    # défaut: %APPDATA%/Fahmi2/projects/<id>/
    source_language: Language                 # déterministe, défini par l'utilisateur
    output_languages: list[Language]          # >= 1, contient au moins source_language
    style_preset: StylePreset
    style_directives: str                     # libre, peut être vide
    stt_provider: Literal["faster_whisper_local", "openai_cloud"]
    llm_model: Literal["deepseek-v4-flash", "deepseek-v4-pro"]
    phases_config: dict[PhaseId, PhaseConfig] # toutes les phases LLM (1..7)
    cost_ceiling_usd: float | None            # None = pas de plafond
    parallelism: ParallelismConfig
    delete_audio_after_stt: bool = True

@dataclass
class Project:
    id: ProjectId
    settings: ProjectSettings
    created_at: datetime
    last_run_at: datetime | None
    runs: list[RunId]                         # historique
```

```python
@dataclass
class Run:
    id: RunId
    project_id: ProjectId
    started_at: datetime
    finished_at: datetime | None
    status: RunStatus
    settings_snapshot: ProjectSettings        # copie immuable à t0
    cost_usd: float                           # cumulé en temps réel
    videos: list[VideoExecution]
    phase_executions: dict[PhaseId, PhaseExecution]  # pour phases batch (2 et 5)

@dataclass
class VideoExecution:
    video_id: VideoId
    source_path: Path
    detected_language: Language | None
    phase_executions: dict[PhaseId, PhaseExecution]  # pour phases par-vidéo

@dataclass
class PhaseExecution:
    phase_id: PhaseId
    status: PhaseStatus
    started_at: datetime | None
    finished_at: datetime | None
    artifact_path: Path | None
    retry_count: int = 0
    cost_usd: float = 0.0
    error: ErrorInfo | None = None

@dataclass
class Term:
    term: str
    definition: str
    sources: list[VideoId]
    aliases: list[str] = field(default_factory=list)
    cross_lang: dict[Language, str] = field(default_factory=dict)
```

### 4.2 Machines d'état

```
RunStatus :
    CREATED ──▶ RUNNING ──┬──▶ COMPLETED
                          ├──▶ PAUSED ──▶ RUNNING (reprise)
                          ├──▶ CANCELLED
                          └──▶ FAILED   (échec irrécupérable d'une phase)

PhaseStatus (par vidéo ou par batch selon la phase) :
    PENDING ──▶ RUNNING ──┬──▶ SUCCEEDED
                          ├──▶ FAILED     (peut être REPLAYED manuellement)
                          └──▶ SKIPPED    (checkpoint hit)
```

**Invariant clé** : la transition vers SUCCEEDED implique que l'artefact est écrit sur disque **avant** la mise à jour du statut en SQLite (`fsync` puis update transactionnel). Garantie : pas de phase marquée SUCCEEDED dont l'artefact serait absent.

### 4.3 Frontière `RunOrchestrator` ↔ `PipelineEngine`

Deux composants distincts aux responsabilités explicites — il faut bien les distinguer pour éviter la duplication :

| Composant | Module | Rôle | Connaît |
|-----------|--------|------|---------|
| `RunOrchestrator` | `app/run_orchestrator.py` | Use-case applicatif : lifecycle d'un Run (création, démarrage, pause, annulation), snapshot des settings, persistance des métadonnées Run, communication UI via EventBus | Project, Run, EventBus, PipelineEngine, SqliteState |
| `PipelineEngine` | `pipeline/engine.py` | Moteur d'exécution pur : itération des phases, lookup checkpoint, invocation des `PhaseHandler` avec retry policy, émission d'événements, respect du PauseToken | Run, PhaseHandler, RetryPolicy, SqliteState, EventBus. **Ne connaît rien de l'UI ni du concept "Projet utilisateur"** |

`RunOrchestrator` appelle `engine.execute(run, pause_token, event_bus)`. Cette séparation rend `PipelineEngine` 100 % testable avec des fakes (`FakeRun`, `FakeSqliteState`, `FakeEventBus`).

---

## 5. Pipeline — 7 phases LLM + STT

### 5.1 Vue d'ensemble

| # | Phase                  | Granularité    | Provider | Artefact produit |
|---|------------------------|----------------|----------|------------------|
| 0 | **STT** (transcription) | par vidéo | STT | `workspace/transcripts/{vid}.json` |
| 1 | Extraction termes      | par vidéo     | LLM      | `workspace/candidates/{vid}.json` |
| 2 | Réconciliation glossaire | batch entier | LLM      | `workspace/glossary_master.json` |
| 3 | Reformulation          | par vidéo     | LLM      | `workspace/reformulated/{vid}.md` |
| 4 | Structuration + sémantique | par vidéo | LLM      | `workspace/structured/{vid}.md` |
| 5 | Consolidation          | batch entier (interne : (a) résumé condensé par vidéo, (b) consolidation globale) | LLM | `workspace/consolidated_master.md` |
| 6 | Traduction             | par doc × langue cible ≠ source | LLM | `output/per-video/{lang}/`, `output/consolidated.{lang}.md`, `output/glossary.{lang}.md` |
| 7 | Cohérence finale       | par langue de sortie | LLM      | réécriture en place de `output/consolidated.{lang}.md` |

### 5.2 Multilingue — pipeline en étoile autour du master

Le batch entier est traité d'abord dans **la langue source** (`settings.source_language`, choix explicite utilisateur). Le résultat des phases 1→5 constitue le **master canonique**. Pour chaque langue de sortie ≠ source, la phase 6 produit une **traduction stylisée** des artefacts finaux (per-video docs, consolidé, glossaire). La phase 7 fait ensuite une passe de cohérence relecture par langue.

Cas mixte FR/EN dans le même batch : pas de comportement spécial. La langue détectée par whisper est consignée. Si elle diffère de `source_language`, un WARN est loggé mais le traitement continue (le LLM en phase 3 reformule vers `source_language` même si l'oral est dans l'autre langue).

### 5.3 Reprise fine par phase

À chaque entrée de phase pour une vidéo donnée :
1. Lookup SQLite `SELECT status FROM phase_executions WHERE run_id=? AND phase_id=? AND video_id=?`
2. Si `SUCCEEDED` → SKIPPED, on passe.
3. Sinon (PENDING / FAILED / RUNNING orphelin) → exécution complète de la phase.

Aucun travail perdu sur crash / coupure réseau / pause / cancel : on reprend exactement où on en était à la frontière de phase la plus avancée.

### 5.4 Parallélisme hybride

| Phase | Stratégie |
|-------|-----------|
| 0 STT local (faster-whisper) | Séquentiel (1 instance, GPU partagé) |
| 0 STT cloud (OpenAI) | Pool `stt_cloud_workers` (défaut 3) |
| 1, 3, 4, 6, 7 (par vidéo) | Pool `llm_workers` (défaut 4) avec rate-limit handling |
| 2, 5 (batch entier) | Séquentiel (1 appel par phase) |

### 5.5 Glossaire — stratégie two-pass

- **Phase 1** : pour chaque vidéo, extraction parallèle des termes candidats avec définitions contextuelles à partir de la transcription brute.
- **Phase 2** : passe unique qui réconcilie, dédoublonne, fusionne les définitions, hiérarchise → glossaire master figé.
- **Phases 3, 4, 5, 6, 7** : injection en contexte d'un **extrait top-K** du glossaire pertinent au contenu traité (top 30 termes par défaut, configurable).

**Retrieval top-K** : géré par `core/retrieval/GlossaryRetriever`, interface stable avec une implémentation v1 **TF-IDF scikit-learn** (vectorizer fitté une fois par run sur l'ensemble glossaire + chunks à traiter, cosine similarity). Permet un swap futur vers embeddings sans toucher au pipeline.

### 5.6 Détail interne de la phase 5

Pour gérer le volume important (~250 000 tokens potentiels en input cumulé), la phase 5 fait en interne deux sous-étapes (transparent pour l'UI qui voit un seul bloc) :

1. **Pré-consolidation par vidéo** : un appel LLM court par vidéo qui produit un résumé condensé (titre, plan en bullets, idées-clés, ~300-500 tokens). **Sert uniquement de carte mentale au LLM**, jamais inséré dans le document final.
2. **Consolidation globale** : un seul appel qui reçoit les 50 résumés + le glossaire master + les directives stylistiques et produit titre global, introduction générale, plan d'ensemble et conclusion générale.

**Garantie de fidélité** : la phase 5 ne touche **jamais** au contenu détaillé des vidéos. Les chapitres = sorties brutes de la phase 4, recopiées telles quelles dans le document consolidé final. Aucune perte de finesse, aucune dégradation du fond.

### 5.7 Éléments sémantiques

Encodés en **GitHub-Flavored Markdown admonitions** dans les artefacts structurés :

```markdown
> [!NOTE]
> **Remarque** — Le PIB en valeur ne tient pas compte de l'inflation.

> [!TIP]
> **Exemple** — Calcul du PIB nominal d'une économie fictive…

> [!IMPORTANT]
> **Définition** — *Inflation* : augmentation soutenue du niveau général des prix.

> [!CAUTION]
> **Exercice** — Calculez le taux d'inflation entre 2020 et 2024 sachant que…
```

Le LLM en phase 4 détecte et tagge ces éléments à partir du contenu reformulé.

---

## 6. Adaptateurs externes (ports)

### 6.1 STTProvider

```python
class STTProvider(Protocol):
    @property
    def name(self) -> str: ...
    def transcribe(
        self,
        audio_path: Path,
        *,
        language_hint: Language | None = None,
        on_progress: Callable[[float], None] | None = None,
    ) -> Transcription: ...
    def estimate_cost(self, duration_seconds: float) -> float: ...

@dataclass
class Transcription:
    segments: list[TranscriptionSegment]
    detected_language: Language
    duration_seconds: float

@dataclass
class TranscriptionSegment:
    start_seconds: float
    end_seconds: float
    text: str
```

**FasterWhisperAdapter** : charge `large-v3-turbo` une fois en cache. **Requiert CUDA** (`device="cuda"`, `compute_type="int8_float16"`). Si CUDA indisponible au démarrage du run, l'application bloque la sélection de ce provider et oriente l'utilisateur vers OpenAI cloud (voir section 7.7). Modèle téléchargé **à la demande** au premier run en mode local (jamais bundlé) dans `%LOCALAPPDATA%/Fahmi2/models/`, vérification SHA256, barre de progression UI, reprise possible. Coût = 0 USD mais durée de compute consignée.

**OpenAIWhisperAdapter** : appel `client.audio.transcriptions.create(model="whisper-1", ...)`. Coût = 0.006 USD / minute audio. Auth via clé stockée DPAPI.

### 6.2 LLMProvider

```python
class LLMProvider(Protocol):
    def chat(
        self,
        *,
        messages: list[Message],
        model: str,
        thinking: bool,
        temperature: float,
        max_tokens: int | None = None,
    ) -> LLMResponse: ...
    def estimate_cost(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        model: str,
        thinking: bool,
        cached_prompt_tokens: int = 0,
    ) -> float: ...

@dataclass
class LLMResponse:
    content: str
    thinking_content: str | None
    prompt_tokens: int
    completion_tokens: int
    cached_prompt_tokens: int
    cost_usd: float
```

**DeepSeekAdapter** : utilise le SDK `openai` configuré sur `base_url="https://api.deepseek.com"`. Prompt caching automatique : on construit les prompts avec la partie stable (system + glossaire) en début pour maximiser les hits cache. Métriques `cached_prompt_tokens` exposées dans les logs.

Tarification embarquée (mise à jour au besoin via constantes) :

| Modèle | input cache hit | input cache miss | output |
|--------|------------------|-------------------|--------|
| `deepseek-v4-flash` | 0.0028 $/Mt | 0.14 $/Mt | 0.28 $/Mt |
| `deepseek-v4-pro`   | 0.003625 $/Mt | 0.435 $/Mt | 0.87 $/Mt |

### 6.3 Autres ports

- **`FFmpegExtractor`** : commande `ffmpeg -i in.mp4 -ac 1 -ar 16000 -c:a pcm_s16le out.wav`. Binaire ffmpeg bundlé dans le .zip portable. Détection codec / piste audio absente.
- **`DPAPISecretsStore`** : `win32crypt.CryptProtectData` avec entropie applicative. Fichier `%APPDATA%/Fahmi2/secrets.dat`.
- **`MarkdownRenderer`** : templates Jinja2, admonitions GFM, TOC auto, ancres slugifiées, liens internes vers glossaire.
- **`FsArtifactStore`** : writes atomiques (`.tmp` puis `rename`), JSON `ensure_ascii=False` indent=2.
- **`PromptsLoader`** : charge depuis `src/fahmi2/infra/prompts/defaults/*.j2` puis override par `%APPDATA%/Fahmi2/prompts/*.j2` si présent.
- **`SqliteState`** : ouverture en mode **WAL** (`PRAGMA journal_mode=WAL` + `PRAGMA synchronous=NORMAL` + `PRAGMA busy_timeout=5000`). **Une connexion par thread** via `threading.local()` (pas de partage cross-thread). Retry léger intégré sur `SQLITE_BUSY` (3 tentatives : 50 / 200 / 500 ms). Transactions courtes, commit après chaque update. Test de concurrence dans la suite : 4 threads × 100 writes parallèles, assertion sur cohérence + zéro exception non gérée.

---

## 7. UI (PySide6)

### 7.1 MainWindow — cockpit dense

```
┌─────────────────────────────────────────────────────────────────────┐
│ Fichier  Édition  Affichage  ?                                      │
├──────────┬──────────────────────────────────────────────────────────┤
│ PROJETS  │ ProjectHeaderBar    [▶ Lancer] [⏸ Pause] [✕ Annuler]    │
│ ──────── │ ─────────────────────────────────────────────────────── │
│ • Macro  │ StatsStrip   12/30 vids · 3/7 phases · 1h42/3h10 · $1.42│
│   L3 ◀   │ ─────────────────────────────────────────────────────── │
│ • Fin M1 │ RunMatrixView (QTableView)                              │
│ • Stats  │   ┌─Vidéo───────────┬P1┬P2┬P3┬P4┬P5┬P6┬P7┬──────────┐  │
│ • + New  │   │ macro-01.mp4    │✓ │✓ │✓ │✓ │✓ │✓ │· │ terminé  │  │
│          │   │ macro-02.mp4    │✓ │✓ │✓ │▶ │  │  │  │ en cours │  │
│ Paramè-  │   │ …               │  │  │  │  │  │  │  │          │  │
│ tres ⚙   │   └─────────────────┴──┴──┴──┴──┴──┴──┴──┴──────────┘  │
│          │ ─────────────────────────────────────────────────────── │
│          │ LogsDock (en bas, replicable)            niveau ▾ filter│
│          │ 14:02 INFO  STT vidéo 12/30 terminée (78.3s)             │
└──────────┴──────────────────────────────────────────────────────────┘
```

### 7.2 Widgets

- **`ProjectsSidebar`** (QListView + modèle) : ajout / édition / suppression / duplication de projet.
- **`RunMatrixView`** (QTableView + `RunMatrixModel: QAbstractTableModel`) : cellules colorées par statut, tooltip = détail (timestamps, retry count, coût, dernier message), double-clic = `PhaseDetailDialog`.
- **`StatsStrip`** : barre stats temps réel (vidéos faites/total, phase courante, durée écoulée/estimée, coût/budget).
- **`LogsDock`** (QDockWidget) : repliable, filtrable par niveau/source, bouton "Ouvrir events.jsonl".
- **`ProjectHeaderBar`** : nom du projet + boutons Lancer / Pause / Annuler + indicateur d'état.

### 7.3 Dialogues

| Dialogue | Rôle |
|----------|------|
| `NewProjectDialog` | Assistant 1-fenêtre : nom, dossiers in/out, langues, style, providers, modèle, phases (7 sections collapsibles), plafond budget, bouton "Estimer le coût" |
| `GlobalSettingsDialog` | Clés API (avec test connexion), chemins par défaut, thème, niveau logs UI, onglet **Prompts** (éditeur) |
| `PhaseDetailDialog` | Détail d'une cellule de la matrice + bouton "Rejouer cette phase" |
| `ProjectReportDialog` | Résumé d'un projet terminé, liens livrables, bouton "Ouvrir dossier" |
| `PromptEditorDialog` | Sous-onglet de GlobalSettingsDialog : édition WYSIWYG des templates `.j2`, bouton "Restaurer le défaut" |

### 7.4 Threading Qt

- Un seul thread UI (main).
- Tout le pipeline tourne dans un `QThread` worker via `RunWorker(QObject)` déplacé.
- Communication exclusivement par `Signal/Slot`.
- L'orchestrateur reçoit un `EventBus` abstrait → l'adapter `QtEventBus` émet en Signal.
- **Le domaine ne dépend pas de Qt.** Aucun import de `PySide6` dans `domain/`, `pipeline/`, `infra/` (sauf `infra/render` qui n'a pas besoin de Qt non plus).

### 7.5 Pause / Cancel

- `PauseToken` injecté à l'orchestrateur.
- Checks aux frontières sûres : entre 2 phases, entre 2 retries LLM.
- Cancel = pause + `RunStatus.CANCELLED` (artefacts conservés).

### 7.6 Persistance UI

`QSettings` natif (registre Windows `HKCU\Software\Fahmi2`) : géométrie fenêtre, état dock, dernier projet ouvert, niveau logs UI par défaut. **Aucun secret** ici (les secrets restent dans DPAPI).

### 7.7 Blocage CPU-only en mode STT local

Détection précoce de l'environnement matériel par `app/hardware_probe.py` au démarrage de l'application (`torch.cuda.is_available()` + version + nom GPU). Stocké dans `AppContext.hardware_info`.

**Dans `NewProjectDialog`** : si l'utilisateur sélectionne `faster_whisper_local` alors que aucun GPU CUDA n'est détecté, la sélection est **bloquée** avec un message clair :

> ⚠️ **GPU NVIDIA compatible CUDA introuvable**
>
> La transcription locale (faster-whisper) nécessite un GPU NVIDIA. En CPU pur, le temps de traitement serait environ 5× supérieur au temps réel audio (≈ 50-75 h pour 30 vidéos de 30 min), ce qui n'est pas une expérience acceptable.
>
> **Veuillez utiliser le mode "OpenAI cloud"** (≈ 0.006 $/min, soit ~5 $ pour 15 h d'audio).
>
> [Configurer la clé OpenAI maintenant] [Annuler]

Filet de sécurité au lancement du run : re-check de `hardware_info` (l'utilisateur peut avoir débranché un eGPU entre la création du projet et le run). Mêmes garde-fous.

---

## 8. Erreurs, retries, observabilité

### 8.1 Hiérarchie d'exceptions

```python
class Fahmi2Error(Exception):
    code: str                  # ex: "STT.MODEL_LOAD_FAILED"
    severity: Severity         # INFO / WARNING / ERROR / FATAL
    user_message: str          # message FR humain, sûr en UI
    technical_details: dict    # logs uniquement

class TransientError(Fahmi2Error): ...
class PermanentError(Fahmi2Error): ...
class BudgetExceededError(Fahmi2Error): ...
class PausedError(Fahmi2Error): ...

# Spécialisations :
class STTError(Fahmi2Error): ...
class LLMError(Fahmi2Error): ...        # avec RateLimit, Auth, BadRequest, ServerError
class FFmpegError(Fahmi2Error): ...
class StorageError(Fahmi2Error): ...
class ConfigError(Fahmi2Error): ...
```

Codes stables : `STT.MODEL_LOAD_FAILED`, `LLM.RATE_LIMIT`, `LLM.AUTH_INVALID`, `LLM.SERVER_ERROR`, `FFMPEG.NO_AUDIO_STREAM`, `STORAGE.NO_SPACE`, etc. Mapping centralisé dans `core/errors/messages.fr.json`.

### 8.2 RetryPolicy

```python
@dataclass
class RetryPolicy:
    max_attempts: int = 5
    initial_delay_seconds: float = 1.0
    max_delay_seconds: float = 60.0
    backoff_multiplier: float = 2.0
    jitter: bool = True
```

Mapping :
- `LLM.RATE_LIMIT` (429) → RETRY, respecte `Retry-After`
- `LLM.SERVER_ERROR` (5xx) → RETRY
- `LLM.AUTH_INVALID` / `LLM.BAD_REQUEST` (4xx hors 429) → NO_RETRY, UI immédiat
- `STT.GPU_OOM` → RETRY (1 fois) ; si persiste → phase FAILED, run mis en pause, message à l'utilisateur (pas de fallback CPU silencieux)
- Réseau (timeout, conn refusée) → RETRY
- `BudgetExceededError` → RAISE_BUDGET (pas de retry, run pausé)

### 8.3 Logs structurés

3 sinks parallèles :
1. **`JsonlFileSink`** → `<workspace>/events.jsonl` (1 ligne / event, niveau DEBUG+)
2. **`QtConsoleSink`** → Signal Qt → `LogsDock` (niveau INFO+ par défaut, filtrable)
3. **`ConsoleSink`** (dev) → stdout coloré

```python
@dataclass
class LogEvent:
    timestamp: datetime
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR"]
    code: str                  # "PHASE_STARTED", "LLM_CALL", "RETRY", ...
    run_id: RunId | None
    phase_id: PhaseId | None
    video_id: VideoId | None
    message: str
    extra: dict
```

Filter custom redacte les clés API dans tous les events.

### 8.4 Edge cases couverts

| Scénario | Traitement |
|----------|-----------|
| Vidéo MP4 sans piste audio | `FFMPEG.NO_AUDIO_STREAM` → vidéo FAILED, run continue sur les autres |
| Vidéo très longue (>2h) | faster-whisper-turbo gère en streaming, progression via `on_progress` |
| Fichiers non-MP4 dans le dossier d'entrée | Ignorés à l'inventaire avec WARN listant les noms. Extensions acceptées : `.mp4`, `.m4v`, `.mkv`, `.mov`, `.webm` (configurable) |
| Dossier d'entrée vide ou inaccessible | `CONFIG.INPUT_FOLDER_EMPTY` ou `STORAGE.READ_DENIED` → bloque la création/lancement du run avec message clair |
| `output_languages` ne contient pas `source_language` | Validation au moment de la création du projet : auto-ajout de `source_language` à la liste, WARN UI |
| Coupure réseau | Retry policy applique. Max atteint → phase FAILED, run en pause |
| Crash app pendant phase | Au redémarrage, SQLite + artefacts disque → reprise depuis dernière phase SUCCEEDED |
| Disque plein | `STORAGE.NO_SPACE` → FATAL, run pausé, message clair |
| Modèle whisper non téléchargé | Download au premier usage avec progression UI, idempotent |
| Langue détectée ≠ source_language | WARN loggé, traitement continue normalement |
| GPU CUDA indisponible alors que provider STT local choisi | **Bloqué** au moment de la création du projet (section 7.7). Pas de fallback CPU silencieux : on force l'utilisateur à choisir OpenAI cloud |
| GPU CUDA détecté à la création mais indisponible au moment du run (driver, eGPU débranché) | Filet de sécurité au lancement : même blocage que ci-dessus, run non démarré, message clair |
| Clé API manquante au lancement run | Bloque avec dialog "Configure tes clés" |
| Plafond budget atteint en plein run | Pause propre (jamais d'interruption d'un appel LLM en cours) |
| Surcouche prompt invalide (Jinja syntax error) | `PROMPT.INVALID_OVERRIDE` → fallback sur défaut + WARN UI |

---

## 9. Tests

### 9.1 Stratégie par couche

| Couche | Type | Outil | Couverture cible |
|--------|------|-------|------------------|
| `domain/` | unitaires purs | `pytest` | 95 %+ |
| `core/` | unitaires | `pytest` | 90 %+ |
| `pipeline/` | unitaires + providers fakes | `pytest` | 90 %+ |
| `infra/` adapters | intégration isolés (`responses` pour HTTP, fixtures audio) | `pytest` | 70 %+ |
| `app/` use-cases | intégration avec fakes infra | `pytest` | 85 %+ |
| `ui/` viewmodels | unitaires (sans Qt) | `pytest` | 70 %+ |
| `ui/` widgets | smoke rendu | `pytest-qt` | golden path |
| End-to-end | run complet sur 2 fixtures audio courtes, providers fakes | `pytest` + `pytest-qt` | 1 happy path + 3 chemins d'erreur clés |

### 9.2 Principes

- **Fakes plutôt que mocks** : `FakeSTTProvider`, `FakeLLMProvider` implémentent l'interface complète avec scénarios paramétrables. Plus stables et plus expressifs que `unittest.mock`.
- **Tests métier, pas UI cosmétique** : on n'assert pas la couleur d'un bouton, on assert l'événement émis.
- **Pas de tests inutiles** : couverture ciblée, pas de gonflement artificiel.

### 9.3 Fixtures de test — version légère

**Choix v1 : pas de fichiers audio dans le repo**. ffmpeg et faster-whisper sont testés en intégration manuelle (script `scripts/integration-test-stt.ps1` lancé hors CI sur une machine avec GPU). Pour la CI et les tests automatiques, on s'appuie exclusivement sur des fakes déterministes.

```
tests/fixtures/
├── transcriptions.py             # transcriptions canoniques en Python (Transcription objects)
├── llm_responses/                # réponses LLM canoniques par phase
│   ├── phase_1_term_extraction.json
│   ├── phase_2_glossary_recon.json
│   ├── phase_3_reformulation.json
│   ├── phase_4_structuration.json
│   ├── phase_5_consolidation.json
│   ├── phase_6_translation.json
│   └── phase_7_coherence.json
└── projects/                     # mini-projets de démonstration (settings JSON, structure de dossier)
```

`FakeSTTProvider.transcribe(audio_path)` : lookup par nom de fichier dans le dict de `transcriptions.py`. Si non trouvé → transcription générique paramétrable.

`FakeLLMProvider.chat(...)` : hash l'input (messages + model + thinking + temperature) → lookup dans le scénario JSON. Si non trouvé → réponse générique. Permet aussi d'**injecter des erreurs** par scénario (`rate_limit`, `auth_invalid`, `server_error`) pour tester les retry policies.

### 9.4 Outillage qualité

- **Linter / format** : `ruff` (E, F, W, B, C90, N, UP, ANN, S, PL) + `ruff format`
- **Type checker** : `mypy --strict`
- **Pre-commit** : ruff + mypy + pytest fast subset
- **Coverage** : `pytest-cov`, seuil global 85 %, configurable par module

---

## 10. Packaging & distribution

### 10.1 Mode de distribution : **portable .zip**

- PyInstaller `--onedir` (démarrage rapide, antivirus + SmartScreen plus calmes que `--onefile`)
- Dossier `Fahmi2/` contenant : `Fahmi2.exe`, libs Python embarquées, `ffmpeg.exe`, `ffprobe.exe`, ressources, templates de prompts par défaut
- Distribution finale = `Fahmi2-x.y.z-win64.zip` (~250 Mo)
- Modèle whisper téléchargé **à la demande au premier run en mode STT local** dans `%LOCALAPPDATA%/Fahmi2/models/` (~1.5 Go). Jamais téléchargé si l'utilisateur reste en mode OpenAI cloud.
- L'utilisateur décompresse où il veut, crée son raccourci. **Pas d'installeur, pas d'UAC, pas de signature requise.** SmartScreen affiche un avertissement au 1er lancement uniquement (clic "Plus d'infos" → "Exécuter quand même").

**Séparation stricte code / données utilisateur** :
- Le dossier d'extraction du .zip contient **uniquement** du code et des ressources statiques. Aucune donnée utilisateur n'y est écrite. Une mise à jour = écraser ce dossier, sans aucun impact sur les données.
- Les données utilisateur (projets, secrets, prompts override, préférences, cache modèles) sont **toujours** dans `%APPDATA%/Fahmi2/`, `%LOCALAPPDATA%/Fahmi2/`, ou le registre Windows. **Jamais touchées par une mise à jour.**

### 10.2 Stockage utilisateur

| Chemin | Contenu |
|--------|---------|
| `%APPDATA%/Fahmi2/secrets.dat` | Clés API chiffrées DPAPI |
| `%APPDATA%/Fahmi2/projects/<id>/` | Workspace de projet par défaut (peut être déplacé) |
| `%APPDATA%/Fahmi2/prompts/*.j2` | Surcouches utilisateur des prompts (optionnel) |
| `%LOCALAPPDATA%/Fahmi2/models/` | Modèles whisper téléchargés (cache) |
| `HKCU\Software\Fahmi2` (registre) | Préférences UI (`QSettings`) |

### 10.3 Dépendances Python

```toml
[project]
name = "fahmi2"
version = "0.1.0"
requires-python = ">=3.11,<3.13"

[project.dependencies]
PySide6 = "^6.7"
faster-whisper = "^1.0"
openai = "^1.40"             # SDK compatible DeepSeek
ffmpeg-python = "^0.2"
pywin32 = "^306"             # DPAPI
jinja2 = "^3.1"
pydantic = "^2"
python-ulid = "^2"
structlog = "^24"
tenacity = "^9"
scikit-learn = "^1.5"        # TF-IDF pour GlossaryRetriever
```

---

## 11. Métriques & estimation de coût

### 11.1 Estimation pré-run (`CostEstimator`)

À partir de :
- Durée totale des vidéos (lue via ffprobe en pré-scan)
- Provider STT choisi (coût audio)
- Modèle LLM + phases activées
- Heuristique : 150 mots/minute oraux, ~1.3 tokens/mot, ratio output/input par phase typé

Sortie : estimation `min/max` USD affichée avant lancement.

### 11.2 Coût en temps réel

Chaque réponse LLM consigne `prompt_tokens`, `cached_prompt_tokens`, `completion_tokens`, `cost_usd`. Agrégation incrémentale dans `Run.cost_usd`. Affichage temps réel dans `StatsStrip`. Si plafond approché (>80 %), warning visuel. Si dépassé, **arrêt propre** (pause à la prochaine frontière sûre, jamais en plein milieu d'un appel LLM).

### 11.3 Estimation du temps restant

Moyenne mobile sur la durée des phases déjà complétées par vidéo. Affichage `1h42 / ~3h10` mis à jour à chaque event.

---

## 12. Sécurité

- **Clés API** : DPAPI, jamais en clair sur disque, jamais loggées (filter redaction).
- **Pas de télémétrie externe**.
- **Mode hors-ligne possible** : si l'utilisateur choisit faster-whisper local + n'utilise pas le LLM (cas dégradé, pas v1 réelle mais le code doit le supporter sans crash).
- **Vérification d'intégrité du modèle whisper** : SHA256 à la fin du download.

---

## 13. Migrations & mise à jour utilisateur

### 13.1 Procédure de mise à jour côté utilisateur

```
1. Télécharger Fahmi2-vX.Y.Z-win64.zip
2. Fermer l'application si elle est ouverte
3. Décompresser le nouveau .zip dans un nouveau dossier (ou écraser l'ancien)
4. Relancer Fahmi2.exe
```

Aucune intervention manuelle sur `%APPDATA%`. Les paramètres, projets, secrets et caches restent en place. Documentée dans le README en section "Mise à jour".

### 13.2 `schema_version` et `MigrationRunner`

Chaque artefact persistant comporte un numéro de version :
- `project.json` : champ `schema_version: int`
- SQLite `project.db` : table `meta(key, value)` avec une entrée `schema_version`
- `secrets.dat` : entête binaire avec un magic + version

Au démarrage de l'application, `core/migrations/MigrationRunner` :
1. Lit la version courante de chaque artefact persistant détecté
2. Compare à la version attendue par le code (constante `CURRENT_SCHEMA_VERSION`)
3. Si version < courante :
   - Crée une sauvegarde automatique (`project.db` → `project.db.backup-v{X}-{date}`)
   - Applique les migrations en chaîne via les modules `core/migrations/v01_to_v02.py`, `v02_to_v03.py`…
   - Met à jour `schema_version`
   - Affiche un dialog modal à l'utilisateur : *"Mise à jour du format de stockage (vX → vY). Une sauvegarde a été créée dans %APPDATA%/Fahmi2/backups/. [Continuer]"*

### 13.3 Conventions de versioning

- Version SemVer (`MAJOR.MINOR.PATCH`) pour le code
- `schema_version` monotone (entier) indépendant de la SemVer du code (incrémenté uniquement quand un changement de schéma est introduit)
- Les migrations sont **toujours forward-only** en v1 (pas de downgrade). Si l'utilisateur lance une ancienne version sur des données récentes → message d'erreur clair *"Cette version est plus ancienne que vos données. Téléchargez une version récente ou restaurez la sauvegarde."*

---

## 14. Critères d'acceptation v1

1. ✅ L'utilisateur télécharge un .zip, le décompresse, double-clique sur l'exe, l'app s'ouvre sans erreur.
2. ✅ Il configure ses clés API DeepSeek + OpenAI via `GlobalSettingsDialog` et le test de connexion passe.
3. ✅ Il crée un projet avec 10 vidéos MP4 (mix FR/EN), choisit langue source FR, sorties FR+EN, style "académique".
4. ✅ Il voit l'estimation de coût, fixe un plafond, lance le run.
5. ✅ Pendant l'exécution : la matrice et la `StatsStrip` se mettent à jour en temps réel, les logs défilent.
6. ✅ Il met en pause après la phase 3, ferme l'app, la rouvre 1h plus tard, reprend → le run reprend exactement où il s'était arrêté.
7. ✅ Un crash simulé (kill -9) en pleine phase 4 → relance → la phase 4 se relance proprement sur les vidéos non finies.
8. ✅ En fin de run, les livrables Markdown sont présents dans `output/` : per-video FR + EN, glossaire FR + EN, consolidé FR + EN, tous avec admonitions sémantiques, cohérence terminologique respectée.
9. ✅ Un dépassement de budget → pause propre, message clair, possibilité de relever le plafond et reprendre.
10. ✅ Tests automatisés : couverture globale ≥ 85 %, end-to-end happy path + 3 erreurs en CI.

---

## 15. Roadmap d'implémentation (vue à dérouler par writing-plans)

Ordre de construction recommandé :

1. **Socle** : `core/` (logging, errors, retry, config, ids, migrations stub) + `domain/` (entités, enums, machines d'état)
2. **Infra basique** : `infra/storage/sqlite_state.py` (mode WAL + 1 conn/thread + test concurrence), `infra/storage/fs_artifacts.py`, `infra/secrets/dpapi_store.py`
3. **Providers (fakes d'abord, real ensuite)** : `infra/audio/ffmpeg_extractor.py`, `infra/stt/faster_whisper_adapter.py` (real testé manuellement), `infra/stt/openai_whisper_adapter.py` (testé via fakes), `infra/llm/deepseek_adapter.py` (testé via fakes/`responses`)
4. **Retrieval** : `core/retrieval/GlossaryRetriever` (TF-IDF, tests unitaires)
5. **Pipeline** : `pipeline/engine.py` (PipelineEngine), `phase_registry.py`, `pause_token.py`, `event_bus.py`, `phase_0_stt` (sans LLM), tests intégration avec fakes
6. **Prompts + phases LLM** : `infra/prompts/` (loader + override mécanisme), puis phases 1 → 7 une par une (chaque phase = handler + prompt template + tests). Phase 5 implémente le sous-découpage interne (résumé condensé + consolidation globale).
7. **Glossaire** : `app/glossary_reconciler.py` (phase 2 + injection top-K via `GlossaryRetriever`)
8. **App services** : `app/project_service.py`, `app/run_orchestrator.py`, `app/cost_estimator.py`, `app/settings_service.py`, `app/hardware_probe.py`
9. **UI socle** : `MainWindow`, `ProjectsSidebar`, `RunMatrixView`, `StatsStrip`, `LogsDock`, `QtEventBus`
10. **UI dialogues** : `NewProjectDialog` (avec blocage CPU-only en mode STT local), `GlobalSettingsDialog`, `PhaseDetailDialog`, `PromptEditorDialog`, `ProjectReportDialog`
11. **End-to-end** : tests E2E sur fakes (happy path + 3 chemins d'erreur), polissage UX
12. **Migrations** : `core/migrations/MigrationRunner` + premier squelette `v01_baseline.py`, tests
13. **Packaging** : PyInstaller spec `--onedir`, bundle ffmpeg, script `make-portable-zip.ps1`, premier .zip de release
14. **Documentation utilisateur** : README (installation, mise à jour, dépannage), guide de démarrage rapide

Chaque étape passe par : code + tests + revue. Le plan détaillé sera produit par le skill `writing-plans` en sortie de ce design.

---

*Fin du design document.*
