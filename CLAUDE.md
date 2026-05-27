# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Projet

Fahmi2 transforme des cours (vidéos, fichiers audio, documents texte —
pdf/docx/md/txt — **et** liens YouTube unitaires) en documents Markdown
consolidés (reformulés, structurés, glossaire) via un pipeline STT + 7 phases
LLM DeepSeek. Application desktop Windows mono-utilisateur, PySide6, packagée en
`.zip` portable (installation double-clic, ffmpeg bundlé).

**Langues gérées** (entrée et sortie, pour les 3 fonctionnalités) : français,
anglais, allemand, espagnol, italien, chinois, arabe (`Language`, 7 valeurs).

L'app est organisée en **onglets de fonctionnalité** (Génération ; Supports
pédagogiques — 8 types de supports de révision avec exports Anki/Markdown/PDF/HTML/DOCX ;
**Dialogue** — chat ancré sur le corpus, réponses citées + streaming, retrieval
lexical/sémantique) : un `Project` ne porte que son nom + son emplacement, les
réglages métier vivant par fonctionnalité (`GenerationSettings`, `PedagogySettings`,
`ChatSettings`).

## Langue et conventions de travail

- **Tout en français** : code comments, docstrings, messages utilisateur, logs,
  commits. Orthographe parfaite avec accents et diacritiques (jamais d'ASCII de
  substitution). Les identifiants de code restent dans leur forme d'origine.
- **Google Python Style Guide** : docstrings avec sections `Args`, `Returns`,
  `Raises` ; docstring de module sur chaque fichier.
- **Vérification systématique en fin de tâche** : `pytest`, `ruff check .`,
  `mypy src tests` doivent tous être verts avant de considérer un travail
  terminé. Repasser autant de fois que nécessaire jusqu'à zéro défaut.
- Entités domaine immuables (`@dataclass(frozen=True)`) + méthodes `with_*` pour
  les copies modifiées. Helpers privés `_method`, modules internes `_module.py`
  (`_base.py`, `_pricing.py`, `_schema.sql`, `_fakes.py`).

## Commandes

L'interpréteur du venv est `.venv\Scripts\python.exe` (Python 3.12 — **pas 3.13**,
contrainte `>=3.11,<3.13` dans `pyproject.toml`). En PowerShell on peut activer
via `.\.venv\Scripts\Activate.ps1`, mais préférer l'appel direct de l'exe.

```powershell
# Tests
.venv\Scripts\python.exe -m pytest                              # toute la suite
.venv\Scripts\python.exe -m pytest tests/unit/app               # une couche
.venv\Scripts\python.exe -m pytest tests/unit/app/test_x.py::test_name -v   # un seul test
.venv\Scripts\python.exe -m pytest --cov=src/fahmi2 --cov-report=term-missing

# Qualité (les deux doivent être propres)
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m mypy src tests

# Lancer l'app en dev
.venv\Scripts\python.exe -m fahmi2.ui.app_main

# Build du .zip portable Windows (télécharge ffmpeg, valide, build PyInstaller)
.\packaging\build.ps1
.\packaging\make-portable-zip.ps1
```

Note Windows : git réécrit LF→CRLF (warnings attendus, sans conséquence). Le
fichier `packaging/fahmi2.spec` est `.gitignore` (`*.spec`) — modifier le `.spec`
pour bundler de nouvelles ressources ne sera pas versionné.

Dépendances exports dans le `.spec` (déjà câblées, cf. `packaging/fahmi2.spec`,
gitignored) : le PDF est rendu par **`xhtml2pdf`** (moteur **`reportlab`**, +
`html5lib`, `pypdf`, `Pillow`, `svglib`, `arabic-reshaper`, `python-bidi`,
`pyHanko` — tous Python pur) → `collect_all('xhtml2pdf')` + `collect_all(
'reportlab')` (données/polices internes) + `collect_all('arabic_reshaper')` ;
`markdown` charge ses extensions par nom → `collect_submodules('markdown')`.
**`genanki` 0.13.1 inline le schéma en modules Python** (`apkg_col.py`/
`apkg_schema.py`) — **aucun fichier de données à collecter**, ses modules sont
bundlés par l'analyse d'imports. L'**export DOCX** ajoute `htmldocx` (+ `beautifulsoup4`,
`lxml` déjà tiré par python-docx) → `hiddenimports += ['htmldocx']` +
`collect_submodules('bs4')`. Le PDF utilise des **polices système Windows** (Arial
pour latin/arabe, Microsoft YaHei pour le chinois) — **rien à bundler** côté police.
Détails dans `packaging/README.md`.

## Architecture en couches

Dépendances dirigées vers le bas (UI → app → pipeline/infra → domain/core).
`core` et `domain` n'importent ni Qt, ni HTTP, ni SQL.

- `core/` — transverse : `errors` (hiérarchie `Fahmi2Error` + `ErrorInfo`
  sérialisable + messages FR), `retry` (`RetryPolicy` + `with_retry`), `logging`
  (JSONL + redaction secrets), `config/paths` (`AppPaths` Windows + résolution
  ffmpeg bundlé runtime), `migrations`, `retrieval` (TF-IDF glossaire),
  `concurrency` (`map_bounded` : pool borné, fail-fast, ordre préservé, honore le
  `PauseToken` ; partagé pour paralléliser les appels LLM/STT I/O-bound), `ids`,
  `slugify` (`slugify_anchor` : ancre GFM **source unique** — sommaire du consolidé
  en génération, parseur de chapitres pédagogiques, ids de titres de l'export HTML).
- `domain/` — entités pures immuables (`Project` [identité minimale : nom +
  emplacement + réglages par fonctionnalité], `GenerationSettings`,
  `PedagogySettings`, `Run`, `InputSource`, `SourceExecution`, `PhaseExecution`, `Term`,
  `Glossary`, entités de support dans `supports.py` : `Flashcard`, `QcmItem`,
  `TrueFalseItem`, `ClozeItem`, `OpenQuestion`, `RevisionSheet`, `KeyPoints`,
  `MockExam`, `SupportArtifact`), enums (génération + pédagogie : `SupportType`×8,
  `TargetAudience`, `BloomObjective`, `SupportDensity`, `ExportFormat`,
  `ReasoningEffort`), IDs ULID typés, et **machines d'état** (`state_machine.py`)
  qui valident les transitions Run et Phase.
- `pipeline/` — moteur d'exécution pur de la **génération** : `PipelineEngine`
  (checkpoint SQLite par phase + retry + events + pause/cancel), `PhaseRegistry`
  (ordre canonique des 8 phases), `PhaseHandler`/`PhaseContext` (DI),
  `EventBus` (générique), `PauseToken`, `handlers/phase_N_*.py` (un par phase).
- `pedagogy/` — moteur des **supports de révision** (calqué sur `pipeline/`, mais
  sans STT/SQLite) : `SupportGenerator` (ABC) + `SupportContext` (DI),
  `SupportGeneratorRegistry` + `build_default_support_registry`, `chapters`
  (parseur), `sources`, `events`, `manifest` (fraîcheur), `artifact_writer`/
  `artifact_reader`, `generators/` (`_base` per-chapitre + mixin évaluatif + 8
  générateurs LLM : flashcards concepts, QCM, vrai/faux, cloze, questions
  ouvertes, fiche, points clés, examen blanc), `labels`.
- `chat/` — moteur du **Dialogue** (chat RAG sur corpus) : `corpus` (chargement +
  chunking par section + glossaire), `prompt_builder` (système/historique + passages
  numérotés + garde-fou d'historique), `citations` (`resolve_citations` : réécrit
  les marqueurs `[§N]` du LLM en liens numérotés cliquables `[[N]](ancre)`, `Citation`
  portant le `number` d'affichage séquentiel dédupliqué par ancre), `query_expander`
  (reformulation LLM à la demande), `retriever_factory` (résolution `AUTO` + repli),
  `chat_service` (`answer`/`stream_answer`). Retrieval en ports : `PassageRetriever`
  (`core/retrieval`, lexical TF-IDF) + `EmbeddingProvider` (`infra/embeddings`,
  OpenAI, **modèle configurable** `EmbeddingModel` + `_pricing`) +
  `SemanticPassageRetriever` (`infra/retrieval`, index `.npz` + empreinte incluant
  le modèle **+ mtime du consolidé ET du glossaire** → réindexation si changement).
  **Fraîcheur du corpus** : `ChatController.refresh_corpus_if_stale()` re-dérive le
  corpus quand le consolidé/glossaire a changé sur disque (clé = langue + 2 mtimes),
  appelé avant chaque réponse **et** au signal `run_state_changed` de la génération
  → le Dialogue ne cite jamais un document périmé après régénération (sans recharger
  le projet). Streaming via `LLMProvider.chat_stream`
  (extension **additive**). **Coût exhaustif** : `consumed_cost_usd()` sur les ports
  retrieval/embedding agrégé dans `ChatMessage.cost_usd`. Conversations persistées et
  **supprimables** (`app/chat_conversation_store`) ; `ChatSettings` dans le blob v2.
  Citations/chunking bornés au plan du document (`##`/`###`).
  **Langue du corpus par conversation** : `Conversation.language` pilote la langue
  **lue/citée ET la langue de réponse** ; un sélecteur (peuplé par
  `pedagogy.sources.available_content_languages`) la choisit à la création d'une
  conversation (parmi les `consolidated.{lang}.md` produits ; masqué si une seule
  langue ; la liste latérale **préfixe** chaque conversation par son code langue, la
  langue d'une conversation étant **fixe**). Le corpus, le glossaire injecté (pré-localisé terme + définition) et
  l'index `.npz` (déjà **par langue**, construit **paresseusement**) suivent ;
  `_resolve_content_language(project, target)` préfère la langue de la conversation,
  repli source puis 1ʳᵉ produite.
  **Limitation connue (chinois)** : le retrieval **lexical** TF-IDF tokenise sur
  `\b\w+\b`, peu adapté au chinois (pas d'espaces entre les mots) → privilégier le mode
  **sémantique** pour le chinois (le défaut `AUTO` y route dès qu'une clé OpenAI est
  présente). L'arabe (mots séparés par des espaces) n'est pas concerné.
- `infra/` — adapters (ports/adapters) : `stt/` (FasterWhisper local + OpenAI
  cloud + fakes ; **modèle configurable par provider** `LocalSttModel`/`CloudSttModel`
  + `_pricing` USD/min ; cloud `gpt-4o-*` sans timestamps → segment unique),
  `embeddings/` (port `EmbeddingProvider` + OpenAI + `_pricing` + fakes),
  `retrieval/` (`SemanticPassageRetriever`), `llm/` (DeepSeek + `_pricing` +
  `invocation` + fakes ; `max_tokens` au plafond modèle + garde `finish_reason`
  anti-troncature),
  `audio/ffmpeg_extractor` + `cloud_audio_preparer` (compression Opus +
  découpage aux silences : franchit la limite 25 Mo d'OpenAI Whisper, injecté
  dans l'adapter STT cloud), `ingestion/` (dispatcher `source → transcription`
  injecté en phase 0 : `classify` [extensions vidéo/audio/document] + port
  `SourceIngestor` + `MediaIngestor` [vidéo+audio via ffmpeg+STT] +
  `DocumentIngestor` [pdf/docx/md/txt → transcription à **segment unique**, via
  `TextExtractor` pypdf/python-docx] + `YoutubeIngestor` [URL → `YtDlpDownloader`
  télécharge l'audio (binaire yt-dlp résolu/remplaçable) → délègue au
  `MediaIngestor`]), `anki/genanki_exporter` (`.apkg`),
  `export/markdown_pdf` (Markdown + HTML + PDF) + `export/markdown_docx` (DOCX via
  htmldocx, réutilise `render_markdown_body`), `storage/sqlite_state` (WAL) +
  `fs_artifacts` (writes atomiques), `secrets/` (DPAPI Windows),
  `prompts/loader` + `defaults/*.j2` (8 phases + 3 `phase_5_*` thématiques +
  8 `pedagogy_*` + 3 `chat_*`).
- `app/` — use-cases : `ProjectService` (+ `get_last_completed_run` ; la
  suppression d'un projet efface aussi son **dossier workspace** sur disque,
  best-effort, hors dossier d'entrée et base globale),
  `RunOrchestrator`, `SupportsOrchestrator`, `CostEstimator`,
  `PedagogyCostEstimator`, `pedagogy_export` (Anki/MD/PDF/HTML/DOCX) + `generation_export`
  (consolidé + glossaire MD/PDF/HTML/DOCX) sur le cœur partagé `document_export`, `_cost_common`,
  `PromptsService`, `SecretsService`, `input_sources` (`build_input_sources` :
  scan dossier vidéo+audio → `SourceExecution`),
  `HardwareProbe`. (Le glossaire est lu sur disque — `glossary_master.json` —
  comme le pipeline ; parsing/rendu dans `domain/glossary`, pas de service dédié.)
- `ui/` — PySide6 : `features/` (abstraction onglet : `FeatureId`, `FeatureTab`,
  `FeatureRegistry`, `GenerationTab`, `PedagogyTab` réel), `viewmodels/` (logique
  testable **sans Qt**, dont `PedagogyProgressViewModel`/`PedagogyStateViewModel`),
  `widgets/` (dont `SettingsView` master-detail réutilisable, `PedagogyProgressView`),
  `dialogs/` (dont `GenerationSettingsView`, `PedagogySettingsView`),
  `theme/` (QSS Clair Fluent), `pedagogy_labels`, `main_window` (sidebar +
  `QTabWidget`), `generation_controller`, `pedagogy_controller`, `qt_event_bus`
  (`QtEventBus` + `PedagogyQtEventBus`), `app_main` (point d'entrée + DI complet).

## Le pipeline en 8 phases

Ordre canonique dans `phase_registry.py`. Chaque handler déclare `is_per_source`
(une source = vidéo, audio, document ou lien YouTube) :

| Phase | Handler | Mode |
|-------|---------|------|
| 0 STT | `phase_0_stt` | **par source** |
| 1 Extraction termes | `phase_1_term_extraction` | **par source** |
| 2 Réconciliation glossaire | `phase_2_glossary_reconciliation` | batch |
| 3 Reformulation | `phase_3_reformulation` | **par source** |
| 4 Structuration | `phase_4_structuration` | **par source** |
| 5 Consolidation | `phase_5_consolidation` (dispatcher `ORDERED`/`THEMATIC`) | batch |
| 6 Traduction (+ localisation glossaire) | `phase_6_translation` | batch (boucle sources × langues) |
| 7 Cohérence | `phase_7_coherence` | batch (boucle langues) |

Le `PipelineEngine._execute_one` persiste chaque `PhaseExecution` en SQLite. Une
phase déjà `SUCCEEDED` est **skippée** (passée en `SKIPPED`). C'est le socle du
checkpoint/reprise. Les phases batch sont persistées avec `source_id IS NULL`.

**Parallélisme** : le moteur exécute les phases per-source via
`core/concurrency/map_bounded` borné par `PhaseHandler.max_parallel_workers(ctx)`
(défaut 1 ; phase 0 = `parallelism.stt_cloud_workers` si STT cloud sinon 1 — 1 GPU
local ; phases 1/3/4 = `parallelism.llm_workers`). Les phases batch parallélisent
leurs boucles internes : 6 sur `(langue × document)`, 7 sur les langues, 5 sur les
résumés par source (ordre des résultats préservé → assemblage déterministe). Les
barrières restent les phases batch 2 et 5 (le moteur reste « phase par phase »).
`ParallelismConfig` est câblée et réglable dans l'UI (défaut `llm_workers=16`,
`stt_cloud_workers=3`). Détails : `docs/superpowers/specs/2026-05-21-parallelisation-traitements-design.md`.

## Mécanismes transverses (à connaître avant de modifier)

- **Modes de consolidation (phase 5)** : `GenerationSettings.consolidation_mode`
  (`ConsolidationMode`, défaut `ORDERED`, migration *lenient*) sélectionne une
  **stratégie** (`pipeline/handlers/_consolidation/` : ABC `ConsolidationStrategy`
  + helpers déterministes partagés dans `_base.py` ; `ordered.py` = comportement
  historique ; `thematic.py` = nouveau). `phase_5_consolidation.py` n'est plus
  qu'un **dispatcher** (+ ré-exports de compat pour les tests historiques).
  `ORDERED` : 1 source = 1 chapitre, contenu recopié. `THEMATIC` : **refonte
  thématique transversale** par le LLM (rigueur sur le fond / souplesse sur la
  forme) en map-reduce à provenance — T1 relevé factuel par source (ids tracés
  `source#n` + extrait verbatim, artefacts `consolidation/facts_master.json` +
  `facts.md`), T2 plan thématique (couverture déterministe #1 → chapitre filet
  « Éléments complémentaires »), T3 rédaction par chapitre (couverture #2,
  conflits présentés par source), T4 méta + assemblage déterministe réutilisé.
  **Les identifiants techniques (ULID, `source#n`) ne fuitent jamais dans le
  livrable** : le LLM ne reçoit que des libellés lisibles « Source N » pour
  l'attribution, et `_strip_provenance_ids` remplace tout id résiduel (filet
  déterministe).
  Reprise intra-phase via *hash de cohérence* (sans toucher `PipelineEngine`).
  Coût : facteur dédié dans `CostEstimator` (pas d'enforcement runtime en
  génération). UI : sélecteur dans `GenerationSettingsView` + note « ordre sans
  effet » sur `SourceOrderView`. 3 prompts `phase_5_fact_ledger`/`_thematic_plan`/
  `_thematic_chapter`. Spec : `docs/superpowers/specs/2026-05-26-modes-consolidation-thematique-design.md`.
- **Localisation terminologique du glossaire (phase 6)** : les **termes** du glossaire
  sont localisés **par langue cible** (traduit-sauf-international ; acronyme conservé ;
  `acronym_expansion` invariante) par un **appel LLM structuré** (`_localize_glossary`,
  prompt `phase_6_glossary_localization`). **Appariement par position** (le prompt impose
  un objet JSON par terme **dans l'ordre**) — robuste à une réémission imparfaite du champ
  `source` (sinon les **acronymes** voyaient leur **définition** retomber en langue source) ;
  repli sur l'appariement par terme source puis per-terme si le compte diffère. La
  **définition est toujours traduite** (même pour un acronyme gardé) ; seule
  l'`acronym_expansion` reste en langue source. La phase 6 (1) **rend `glossary.{L}.md` de façon déterministe** (le
  glossaire **n'est plus une `_TranslationTask`**), (2) injecte les vrais équivalents
  `source → cible` dans la traduction du consolidé/docs par source, (3) **persiste
  `cross_lang` dans `glossary_master.json`** (écriture atomique, pour l'aval). **Source
  unique** : `domain/glossary.localize_glossary_terms(terms, language)` (= `cross_lang[L]`,
  repli sur le terme source). **Propagation** : la **Pédagogie** (`SupportsOrchestrator`)
  et le **Dialogue** (`corpus.load_corpus_chunks`) **pré-localisent** le glossaire à la
  **langue de contenu** qu'ils chargent (générateurs / `format_glossary_terms` /
  `_glossary_chunks` inchangés). `cross_lang` porte **terme + définition**
  (`domain/glossary.LocalizedTerm` ; persisté par `_persist_cross_lang` **sans appel LLM
  supplémentaire** car la définition traduite est déjà calculée ; parsing *lenient* :
  objet `{term,definition}` ou **chaîne legacy** = terme seul, définition repliée sur la
  source) → le glossaire est **entièrement localisé en aval** (Pédagogie/Dialogue), pas
  seulement le terme. Seule l'`acronym_expansion` (colonne *Signification*) reste
  **invariante** par langue (voulu). Specs :
  `docs/superpowers/specs/2026-05-27-localisation-terminologique-glossaire-design.md`
  + `docs/superpowers/specs/2026-05-27-dialogue-langue-corpus-design.md`.
- **Coquille multi-fonctionnalités** : la zone projet est une `QTabWidget` peuplée
  par un `FeatureRegistry` (calqué sur `PhaseRegistry`). Un `Project` ne porte que
  nom + emplacement (immuable après création) ; les réglages métier sont par
  fonctionnalité (`GenerationSettings`, `None` = « à configurer »). Le workspace a un
  dossier par fonctionnalité (`<emplacement>/generation/…`). Le blob
  `projects.settings_json` est en **v2** (`{version, workspace_folder, generation,
  pedagogy}`) avec migration *lenient* v1→v2 à la lecture. Ajouter une fonctionnalité
  = enregistrer un `FeatureTab`, sans toucher `MainWindow` ni `Project`.
- **Entrants polymorphes (ingestion)** : la phase 0 délègue à
  `IngestionDispatcher` (injecté dans `PhaseContext`) qui route selon le
  `SourceKind` d'un `InputSource` (`SourceExecution.source` ; fichier **ou** URL).
  `MediaIngestor` (vidéo/audio) extrait l'audio puis STT ; `DocumentIngestor`
  (pdf/docx/md/txt) extrait le texte en une `Transcription` à **segment unique**
  (le texte intégral, structure préservée — `_load_transcription_text` joint les
  segments par une espace, donc *un seul* segment évite tout aplatissement).
  `build_input_sources` (ex `scan_input_folder`) scanne le dossier via
  `classify_file`, puis **ajoute après** les liens YouTube de
  `GenerationSettings.youtube_urls` (**unitaires**, `--no-playlist`) téléchargés
  par `YtDlpDownloader` (binaire yt-dlp **résolu/remplaçable** :
  `resolve_ytdlp_binary_or_none`, override `FAHMI2_YTDLP`). Un document n'a pas
  de STT (`duration_seconds=0`). Le drapeau
  `GenerationSettings.reformulate_documents` (défaut `True`) : si désactivé, la
  phase 3 fait un **pass-through** (le document est inséré tel quel, coût 0) au
  lieu de reformuler. Le `CostEstimator` raisonne en `SourceWeight` (durée audio
  **ou** tokens texte, drapeau `reformulated`). **Ordre & exclusion** :
  `source_order` (clés ordonnées des incluses) + `excluded_sources` (clés exclues)
  sont réconciliés au scan par la fonction pure `reconcile_source_order` (partagée
  `build_input_sources` ↔ widget UI `SourceOrderView` double liste) ; clés stables
  = `InputSource.order_key()` (nom de fichier / URL) ; les clés obsolètes sont
  ignorées, les nouvelles ajoutées en fin.
- **Checkpoint / reprise après erreur** : un Run garde le même `RunId` du début à
  la fin. `RunOrchestrator.resume_or_create_run(project)` reprend le dernier Run
  s'il est `FAILED`/`PAUSED`/`RUNNING`-orphelin (les phases `SUCCEEDED` seront
  skippées), sinon crée un nouveau Run. La state machine autorise donc
  `FAILED → RUNNING`. Ne jamais re-`create_run` pour « reprendre » : ça forge un
  nouveau `RunId` et perd tout le checkpoint.
- **Piège SQLite `UNIQUE` + `NULL`** : SQLite traite `NULL` comme distinct dans
  une contrainte `UNIQUE`, donc `ON CONFLICT(run_id, phase_id, source_id)` ne se
  déclenche **jamais** pour les phases batch (`source_id IS NULL`).
  `SqliteState.upsert_phase_execution` fait un `DELETE + INSERT` explicite dans ce
  cas. Toute évolution du schéma passe par `_apply_soft_migrations` (idempotent,
  `ALTER TABLE ADD COLUMN` ou nettoyage de données).
- **DeepSeek thinking** : `DeepSeekAdapter` envoie le mode raisonnement via
  `extra_body={"thinking": {"type": "enabled"|"disabled"}, "reasoning_effort":
  "high"|"max"}`, configurable **par phase** (`PhaseConfig.thinking_enabled` +
  `reasoning_effort`). `CostEstimator` applique un multiplicateur sur les tokens
  de sortie selon ce niveau (×2.5 / ×3.5 HIGH / ×6 MAX) — les tokens de
  raisonnement sont facturés au tarif output.
- **Override des prompts** : `PromptLoader` charge prioritairement
  `%APPDATA%/Fahmi2/prompts/<nom>.j2` s'il existe et est un Jinja2 valide, sinon
  le défaut bundlé dans `infra/prompts/defaults/`. `PromptsService` +
  `PromptsEditorDialog` exposent ça dans l'UI. Modifier un `.j2` de `defaults/`
  change la base pour tous, mais un override `%APPDATA%` le masque. Le catalogue
  couvre les 8 phases, les **3 templates `phase_5_*` du mode thématique** **et**
  les 8 templates `pedagogy_*` (tous éditables pareil).
- **Supports pédagogiques** : 8 types, tous LLM, générés par un **orchestrateur
  dédié léger** (`SupportsOrchestrator`, **pas** le `PipelineEngine`) qui
  **parallélise les unités (langue × support)** via `core/concurrency/map_bounded`
  (borné par `PedagogySettings.llm_workers`, défaut 16, plage 1–64 exposée en
  réglage ; verrou sur le manifeste, compteur de coût partagé). Le **plafond de
  coût est best-effort** en parallèle (léger dépassement toléré par les requêtes
  en vol). Détails : `docs/superpowers/specs/2026-05-21-parallelisation-traitements-design.md`.
  Les entrants sont lus **sur disque** comme le pipeline :
  document consolidé (parsé en chapitres ; une **langue de contenu** est résolue
  parmi les `consolidated.{lang}.md` existants — la langue cible peut donc différer)
  et glossaire (`glossary_master.json` ; pas de table SQLite). Les supports sont
  rédigés par le LLM dans la **langue cible** choisie, indépendamment de la langue
  du document source. Pas de checkpoint SQLite : la fraîcheur est suivie par le
  `pedagogy/manifest.json` (hash des réglages + mtime source par langue), une source
  régénérée **périme** les supports (bandeau d'état UI). **Alignement sur la
  génération** (`_is_complete`) : relancer un ensemble **complet** (tout présent +
  frais) **régénère** tout (écrase, comme un nouveau run) ; un ensemble **incomplet**
  (interruption / plafond) est **repris** *coarse* (supports frais skippés, manquants
  générés). Le statut de la dernière exécution est persisté sur disque
  (`pedagogy/run_state.json` : `RunStatus` + horodatages + coût) pour un statut
  homogène avec la génération (sidebar, tuiles), lisible hors session active. Le
  `SupportsOrchestrator` applique
  un **plafond de coût** (`PedagogyCostEstimator`). Les générateurs LLM partagent
  le retry du pipeline (`core/retry/classification.default_classify`) via
  `pedagogy/generators/_base.py` (parsing JSON typé). Les supports **évaluatifs**
  « corrigé séparé » produisent un `<support>.corrige.md` distinct du sujet.
  Exports : `.apkg` (genanki) via `app/pedagogy_export.py`, **Markdown/PDF/HTML/DOCX
  un fichier par support et par corrigé** (`<support>.<lang>(.corrige).<ext>`) via
  le cœur partagé `app/document_export.py` (`write_documents` : collecteur →
  écriture par format ; `infra/export/markdown_pdf` et `markdown_docx` restent de purs
  *renderers*). `ExportDocument` porte la **langue** du contenu (pilote police/direction
  du rendu PDF/HTML). La **génération** a son propre export documentaire
  `app/generation_export.py` (consolidé + glossaire, un fichier par langue,
  MD/PDF/HTML/DOCX ; réglage `GenerationSettings.export_formats`, opt-in). Côté UI, le helper partagé
  `ui/_export_ui.py` (`choose_export_format` + `run_document_export`) factorise
  choix de format → dossier → erreurs → log pour les deux contrôleurs. Les
  prompts autorisent un Markdown léger dans le contenu ; l'export Anki **convertit
  les champs Markdown en HTML** (`genanki_exporter._md_to_html`) — sauf le texte
  cloze (mécanique `{{cN::}}` préservée). MD/PDF/HTML/DOCX consomment le Markdown rendu
  tel quel ; le **corps HTML est rendu une fois** par `render_markdown_body` (extensions
  `tables`+`toc`), réutilisé par HTML, PDF **et** DOCX. **Normalisation des tableaux**
  (`_normalize_table_blocks`, partagée donc HTML/PDF/DOCX) : les sorties LLM collent
  souvent un tableau pipe à la phrase qui l'introduit ou l'indentent dans une liste
  numérotée → python-markdown ne l'active pas (barres littérales). On garantit une ligne
  vide avant/après + désindentation. *Limite python-markdown* : un tableau ne s'imbrique
  pas dans un `<li>` → il en ressort ; la numérotation de la liste qui suit est rétablie
  par `_renumber_lists_split_by_tables` (attribut `<ol start>`, honoré navigateur + PDF
  xhtml2pdf). Réutilisé par HTML, PDF **et** DOCX (`markdown_docx` → htmldocx →
  python-docx ; Word gère nativement CJK et coupe de ligne ; l'**arabe** reçoit une
  direction RTL explicite (`w:bidi` paragraphes, `w:rtl` runs, `w:bidiVisual` tableaux →
  colonnes inversées, comme `direction:rtl` PDF / `dir="rtl"` HTML), les toggles insérés
  à la bonne position du schéma OOXML via `insert_element_before` ; l'**orientation
  paysage** — option `landscape`, ex: glossaire — est posée sur les sections du document
  via `WD_ORIENT.LANDSCAPE` + permutation largeur/hauteur.
  **htmldocx ne traduit ni les bordures CSS ni `width:100%`** (tableaux sans contour,
  largeur ajustée au contenu) → `markdown_docx._format_docx_tables` reformate **tous**
  les tableaux après conversion : style intégré `Table Grid` (bordures) + `tblW` à
  `pct` 5000 (100 %), pour s'aligner sur HTML/PDF.
  **Rendu PDF/HTML (`infra/export/markdown_pdf`)** : le **PDF est rendu à partir du
  HTML via `xhtml2pdf`** (moteur ReportLab, Python pur, *bundleable*) — vraie
  pagination (listes/tableaux multi-pages), typo CSS, orientation paysage. Gotchas :
  (1) tableaux pipe GFM → extension python-markdown `tables` (sinon texte littéral) ;
  (2) sommaire **cliquable** via l'extension `toc` + `core/slugify.slugify_anchor`
  (ids de titres = ancres du sommaire ; `slugify_anchor` conserve les lettres Unicode
  → ancres CJK/arabes valides) ; (3) `app.document_export.ExportDocument`
  porte l'**orientation `landscape`** (PDF **et** DOCX), les **largeurs de colonnes PDF**
  (`pdf_column_widths`) et la **langue** — le **glossaire** s'exporte en paysage (PDF +
  DOCX) + largeurs dédiées (PDF) ; (4) xhtml2pdf n'honore les largeurs de colonnes que
  posées sur **chaque** cellule et effondre les cellules vides → `_layout_table_cells`
  (largeurs + remplissage `&nbsp;`) ; (5) ReportLab+Arial ne rend pas U+2010/2011/2012/2015
  (carré) → `_normalize_for_pdf` les normalise (em-dash/en-dash conservés) ; (6) plus
  largement, tout caractère **sans glyphe** dans la police active (émojis décoratifs
  📖/📝/💡/🎯…) est **retiré** avant rendu (`_strip_unrenderable_for_pdf` ; couverture
  via `pdfmetrics.getFont(...).face.charToGlyph`, catégories Cc/Cf/Zs/Zl/Zp conservées
  dont ZWJ/RLM pour l'arabe) — sinon ReportLab dessine un carré (pas d'émojis couleur,
  pas de repli par glyphe) ; HTML/DOCX, eux, les conservent ; (7) le **chinois s'écrit
  sans espaces** et ReportLab ne coupe qu'aux espaces (le mode CSS `-pdf-word-wrap: CJK`
  de xhtml2pdf 0.2.17 plante sur `<p>`/`<li>`) → la prose CJK est **pré-coupée** par
  `<br/>` (`_prewrap_cjk_runs` via `reportlab…wordSplit` + BeautifulSoup, largeur dérivée
  des constantes A4/marge) et les **cellules** par la règle CSS `-pdf-word-wrap: CJK`
  (seul contexte où elle fonctionne) ; les deux ne s'appliquent qu'aux langues CJK
  (`_CJK_LANGUAGES`). Le pré-formatage opère **par bloc** (paragraphe/li/titre) sur le
  **texte aplati** — fragments **gras/italiques inclus** : couper nœud par nœud plaçait
  la 1ʳᵉ ligne suivant un terme en gras *après* ce terme → débordement à droite. La
  largeur cible réserve **un idéogramme** (`_CJK_WIDEST_CHAR`) car `wordSplit` dépasse sa
  cible du dernier caractère ajouté. **Police PDF par langue** : latin
  (fr/en/de/es/it) → Arial système (résolu en Helvetica par xhtml2pdf, couvre Latin-1) ;
  **chinois** → Microsoft YaHei (`msyh.ttc` système, chargé via `subfontIndex`) injecté
  dans `xhtml2pdf.default.DEFAULT_FONT` (garde `EXPORT.NO_CJK_FONT` si absent) ;
  **arabe** → Arial (glyphes arabes) + `direction:rtl` + tag `<pdf:language name="arabic"/>`
  qui déclenche le reshaping contextuel + bidi (`arabic-reshaper`/`python-bidi`, transitifs
  xhtml2pdf). ⚠ **Arial Italic/Bold-Italic n'ont aucun glyphe arabe** (l'arabe n'a pas de
  formes italiques) → l'arabe en emphase (`*…*`) tombait en carrés ; `_ensure_arabic_font_registered`
  enregistre une famille dédiée `AppArabic` dont **italique/gras-italique pointent sur les
  variantes droites** (régulier/gras), qui couvrent l'arabe.
  `domain.languages.is_rtl` = **source unique RTL** (PDF `direction`, HTML `dir`, DOCX
  `bidi`/`bidiVisual`) ; `_text_direction` en dérive la valeur CSS ; tailles de police et
  marge `@page` **centralisées** (source unique gabarit CSS ↔ calcul de largeur du
  pré-formatage CJK). **Polices toutes système Windows — rien à bundler.**
- **Erreurs → UI** : une exception levée par un handler **doit** être une
  `Fahmi2Error` (code + user_message + technical_details). Le moteur la convertit
  en `ErrorInfo`, la propage dans `PhaseFinished.error`, et `generation_controller._to_log_event`
  l'expose dans le panneau Logs (code + message + détails) et `events.jsonl`.
- **UI threading & projet affiché** : un Run tourne dans un `QThread` worker. Le
  `GenerationController` (découplé du `MainWindow` : il reçoit header/stats/matrice/logs)
  distingue `_current_project` (affiché dans le dashboard) de
  `_active_worker_project_id` (projet du worker actif) — les events du pipeline
  ne rafraîchissent matrice/stats que si les deux coïncident, pour ne pas écraser
  le dashboard quand l'utilisateur navigue entre projets pendant un Run. Le
  bridge worker→UI passe par `QtEventBus` (EventBus → Signal Qt).
- **Secrets** : clés API chiffrées via DPAPI Windows (`DPAPISecretsStore`),
  jamais en clair sur disque ni dans les logs. Hors Windows (dev), fallback
  `InMemorySecretsStore`.

## Tests

Fixtures clés (dans `tests/conftest.py`) : `make_generation_settings` fabrique des
`GenerationSettings` valides, `make_project` un `Project` minimal ; passer des kwargs
pour surcharger. Les providers
réels ont des doubles `_fakes.py` (`FakeLLMProvider`, `FakeSTTProvider`). Les
viewmodels UI se testent sans Qt ; les widgets ont des smoke tests `pytest-qt`.
`mypy --strict` est actif : attention au narrowing après un `assert` suivi d'un
appel mutant (contourner via `getattr` plutôt que d'accepter un faux
`unreachable`).

## Directives systématiques

0. **Toujours valider la complétude du plan**
1. **Constants centralization** — pas de magic string, magic number, valeur par défaut directement dans le code mais dans des constantes
2.  Conformity with existing codebase patterns (reuse existing classes, methods, helpers, constants, mixins, base classes)
3.  Follow the Google Python Style Guide — Google-style docstrings with Args, Returns, Raises sections; module-level docstrings on every file
4.  Verify naming consistency (imports, classes, methods, variables, constants) and that all arguments are properly defined and passed
5. Respect framework patterns
6. Respect DRY, YAGNI, KISS, SRP, SoC, Boy Scout Rule, Composition over Inheritance
7. Write generic, extensible code — no duplication, reuse validator mixins and base classes
8. Update all documentation in `docs/` as well as all cross-cutting docs, `README.md`