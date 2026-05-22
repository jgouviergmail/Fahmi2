# Entrants élargis (audio, YouTube, documents) + ordonnancement des sources — design détaillé (Spec A)

- **Date** : 2026-05-22
- **Statut** : design (à valider)
- **Périmètre** : cette spec couvre **l'ingestion élargie** et **l'ordonnancement
  des sources**. Les **modes de consolidation** (ordre intelligent / refonte
  thématique) sont sortis dans une spec dédiée à brainstormer :
  `2026-05-22-modes-consolidation-backlog.md`. La consolidation reste ici en
  comportement **actuel** (ordre des sources, 1 source = 1 chapitre).
- **Contexte** : la génération n'accepte aujourd'hui que des **vidéos** locales
  (5 extensions) dans un dossier scanné, assemblées dans l'ordre du nom de fichier.
  On veut (1) élargir les entrants aux **audios**, **liens YouTube** (unitaires) et
  **documents texte** (pdf, docx, md, txt), et (2) donner un **contrôle d'ordre
  explicite** des sources.
- **Pivot** : tout l'aval (phases 1-7) ne consomme qu'une **transcription JSON**
  par source. C'est le point d'extension de l'ingestion (phase 0).

## 1. Objectif & portée

Généraliser l'ingestion (phase 0) pour produire la même `Transcription` JSON quelle
que soit l'origine, **sans toucher aux phases 1-7**.

- **Audio** : `ffmpeg.extract` accepte déjà tout conteneur audio → quasi-natif.
- **YouTube** (liens **unitaires**) : `yt-dlp` télécharge l'audio, puis STT comme
  un média local. Pas de playlists, pas de réutilisation de sous-titres.
- **Documents texte** : extraction de texte → `Transcription` synthétique (sans
  STT). Drapeau projet décidant s'ils passent par la reformulation.
- **Ordonnancement** : l'utilisateur définit l'ordre de traitement (et donc l'ordre
  des chapitres du document consolidé) dans tous les cas, sans dépendre du
  renommage des fichiers.

**Cas d'usage prioritaire** : projets **homogènes**. Le **mélange** hétérogène
fonctionne mais n'est pas privilégié dans l'ergonomie.

**Hors périmètre (YAGNI)** : playlists/chaînes YouTube, réutilisation de sous-titres,
formats texte exotiques (`.doc`, `.rtf`, `.odt`, `.epub`), OCR de PDF scannés
(PDF sans texte → erreur claire), détection auto de langue des documents (on fait
confiance à `source_language`), **modes de consolidation** (spec séparée).

## 2. Décisions verrouillées

1. **Dispatcher d'ingesteurs** (ports/adapters) : port `SourceIngestor` + 3
   adapters + dispatcher. Pipeline aval **inchangé**.
2. **Saisie** : dossier scanné **élargi** (vidéo + audio + documents) **+** champ
   « liens YouTube ». La collecte alimente une **liste d'ordre réordonnable**.
3. **YouTube** : liens **unitaires**, `yt-dlp` (binaire bundlé + override), audio
   seul, STT systématique.
4. **Documents texte** : drapeau `reformulate_documents` (défaut `True`) ; sinon
   **pass-through** en phase 3. Un document = transcription à **segment unique**
   (texte intégral, structure préservée).
5. **Renommage** `VideoExecution → SourceExecution`, `VideoId → SourceId`,
   `Run.videos → Run.sources`, **et migration de colonne SQLite `video_id →
   source_id`** (cohérence complète Python/SQL).
6. **`PhaseId.STT` conservé** ; libellé UI « Transcription / Ingestion ».
7. **Bibliothèques** : `yt-dlp` (binaire), `pypdf` (BSD), `python-docx` (MIT).
8. **Ordonnancement & exclusion** : `source_order` (clés ordonnées des incluses) +
   `excluded_sources` (clés exclues), réconciliés au scan ; **double liste**
   réordonnable dans l'UI ; « Rafraîchir » **conserve** les exclusions.

## 3. Modèle de données (`domain`)

### 3.1 Enum `SourceKind` (`domain/enums.py`)

```python
class SourceKind(StrEnum):
    """Origine d'une source d'entrée de la génération."""
    VIDEO = "video"
    AUDIO = "audio"
    DOCUMENT = "document"
    YOUTUBE = "youtube"
```

### 3.2 Value object `InputSource` (`domain/source.py`, nouveau)

```python
@dataclass(frozen=True)
class InputSource:
    """Une source d'entrée (fichier local ou URL distante)."""
    kind: SourceKind
    location: str  # chemin de fichier OU URL selon kind

    @property
    def is_remote(self) -> bool:
        return self.kind is SourceKind.YOUTUBE

    @property
    def as_path(self) -> Path:
        """Chemin local ; lève ValueError si source distante."""
        if self.is_remote:
            raise ValueError("Une source distante n'a pas de chemin local")
        return Path(self.location)

    def order_key(self) -> str:
        """Clé stable d'ordonnancement (nom de fichier ou URL)."""
        return self.location if self.is_remote else Path(self.location).name

    def display_name(self) -> str:
        return self.order_key()
```

### 3.3 `SourceExecution` (renommage de `VideoExecution`, `domain/source.py`)

```python
@dataclass(frozen=True)
class SourceExecution:
    """État d'exécution d'une source dans un Run."""
    source_id: SourceId
    source: InputSource
    detected_language: Language | None = None
    phase_executions: dict[PhaseId, PhaseExecution] = field(default_factory=dict)
    def phase_status(self, phase_id: PhaseId) -> PhaseStatus: ...  # inchangé
```

`domain/video.py` supprimé → `domain/source.py`. `VideoId → SourceId`
(`domain/ids.py`). `Run.videos → Run.sources: tuple[SourceExecution, ...]`.

> Renommage transverse (~20-30 fichiers) **et** migration SQLite (§13) faits
> **maintenant** (refactor de fondation), pas tardivement.

## 4. Couche ingestion (`infra/ingestion/`, nouveau package)

### 4.1 Port `SourceIngestor` (`interface.py`)

```python
@dataclass(frozen=True)
class IngestionDeps:
    workspace: Path
    artifacts: FsArtifactStore
    stt_provider: STTProvider
    ffmpeg: FFmpegExtractor


class SourceIngestor(Protocol):
    @property
    def kind(self) -> SourceKind: ...
    def ingest(self, source: InputSource, source_id: str, deps: IngestionDeps,
               *, language_hint: Language | None,
               delete_audio_after: bool) -> Transcription: ...
```

### 4.2 `MediaIngestor` (VIDEO + AUDIO) (`media_ingestor.py`)
Extrait la logique actuelle de `phase_0_stt.py` : `ffmpeg.extract(source.as_path →
audio/{id}.wav)` puis `stt.transcribe`. VIDEO et AUDIO identiques.

### 4.3 `YoutubeIngestor` (YOUTUBE) (`youtube_ingestor.py`)
Compose `MediaIngestor` :
1. `YoutubeDownloader.download_audio(url, dest_dir, stem) -> Path` (port injecté ;
   adapter `YtDlpDownloader` appelant le **binaire yt-dlp** résolu au runtime,
   `-f bestaudio`, `--ffmpeg-location <ffmpeg bundlé>`, `--newline` pour la
   progression). La progression de téléchargement est remontée via `on_progress`
   (parsée depuis la sortie yt-dlp) → events phase 0.
2. Construit `InputSource(AUDIO, fichier téléchargé)` → délègue au `MediaIngestor`.
3. Nettoie le fichier téléchargé après extraction WAV.

```python
class YoutubeDownloader(Protocol):
    def download_audio(self, url: str, dest_dir: Path, stem: str,
                       *, on_progress: ProgressCallback | None = None) -> Path: ...
    def probe_duration(self, url: str) -> float:
        """Durée via yt-dlp --print duration --skip-download ; 0.0 si indéterminable."""
```

**Résolution du binaire** : `resolve_ytdlp_binary_or_none()` (calqué sur
`resolve_ffmpeg_binary_or_none`) — cherche le binaire bundlé, puis un override
(réglage/variable d'env `FAHMI2_YTDLP`), puis le `PATH`. Absent → `INGESTION.YTDLP_NOT_FOUND`.

### 4.4 `DocumentIngestor` (DOCUMENT) (`document_ingestor.py`)
1. `TextExtractor.extract(source.as_path) -> str` (texte avec sauts de ligne/
   paragraphes **préservés**).
2. → `Transcription` à **segment unique** : `TranscriptionSegment(start=0.0,
   end=0.0, text=<texte intégral>)`, `detected_language = language_hint`. Pas
   d'audio, pas de STT.
   > **Pourquoi un seul segment** : `_load_transcription_text` joint les segments
   > par une espace ; un découpage par paragraphe **aplatirait** la structure (et
   > casserait le pass-through). Un segment unique préserve le texte intact pour
   > la reformulation **comme** pour le pass-through.
3. Texte vide après extraction → `INGESTION.EMPTY_DOCUMENT`.

### 4.5 `TextExtractor` (`text_extractor.py`)
Port + `DefaultTextExtractor` : `.pdf`→`pypdf` (texte des pages, séparées par
double saut de ligne), `.docx`→`python-docx` (paragraphes joints par saut de
ligne), `.md`/`.txt`→lecture UTF-8 directe (intacte). Erreur → `TEXT_EXTRACTION_FAILED`.

### 4.6 `IngestionDispatcher` (`dispatcher.py`)
Registre `SourceKind → SourceIngestor` (calqué sur `PhaseRegistry`) +
`build_default_ingestion_dispatcher(youtube_downloader, text_extractor)`. Kind sans
ingesteur → `INGESTION.UNSUPPORTED_SOURCE`.

### 4.7 Classification (`classify.py`)
```python
_VIDEO_EXTENSIONS = {".mp4", ".m4v", ".mkv", ".mov", ".webm"}
_AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".flac", ".ogg", ".opus", ".aac"}
_DOCUMENT_EXTENSIONS = {".pdf", ".docx", ".md", ".txt"}
def classify_file(path: Path) -> SourceKind | None: ...
```
Extensions **centralisées** ici, réexposées par `supported_extensions()`.

## 5. Intégration phase 0 (`pipeline/handlers/phase_0_stt.py`)
Conserve `PhaseId.STT`, `is_per_video=True`, **délègue au dispatcher** ; produit le
**même** `transcripts/{id}.json`. `PhaseContext` gagne `ingestion:
IngestionDispatcher` (les champs `stt_provider`, `ffmpeg` restent, injectés dans
`IngestionDeps`). Phases 1-7 inchangées.

> `max_parallel_workers` phase 0 : inchangé (STT cloud `stt_cloud_workers`, sinon 1).
> Les documents (extraction rapide, sans GPU/réseau) restent dans ce pool —
> inefficacité bénigne assumée (un projet mixte audio-local + docs reste à 1 worker).

## 6. Drapeau « reformuler les documents » (phase 3)
- `GenerationSettings.reformulate_documents: bool = True`.
- Dans `phase_3_reformulation.py`, avant l'appel LLM :
```python
if src.source.kind is SourceKind.DOCUMENT and not ctx.settings.reformulate_documents:
    text = _load_transcription_text(ctx.workspace, src.source_id.value)  # texte intégral (1 segment)
    ctx.artifacts.write_text_atomic(out_path, text)  # reformulated/{id}.md
    return build_succeeded_phase(phase_id=self.phase_id, artifact_path=out_path,
                                 started_at=started_at, cost_usd=0.0)
```
Grâce au **segment unique** (§4.4), le pass-through restitue le document **intact**
(structure préservée). La phase 4 lit toujours `reformulated/{id}.md` → aucune
logique conditionnelle ailleurs.

## 7. Ordonnancement & exclusion explicites des sources

### 7.1 Réglages & clé stable
- `GenerationSettings.source_order: tuple[str, ...] = ()` : suite ordonnée des
  **clés stables** des sources **incluses** (`InputSource.order_key()` — nom de
  fichier, scan **plat** donc unique ; URL pour les liens).
- `GenerationSettings.excluded_sources: tuple[str, ...] = ()` : clés des sources
  **exclues** (présentes dans le dossier/champ mais à ne pas traiter).

### 7.2 Réconciliation au scan (`build_input_sources`)
1. Collecter : fichiers reconnus (`classify_file`) + URLs.
2. **Filtrer** les sources dont la clé est dans `excluded_sources` (non traitées).
3. Ordonner les restantes :
   - clés présentes dans `source_order` → ordre de `source_order` ;
   - sources **absentes** de `source_order` (nouvelles) → triées par
     `_natural_sort_key` (fichiers) / ordre de saisie (URLs), **ajoutées après** ;
   - clés de `source_order`/`excluded_sources` sans source correspondante →
     ignorées (fichier supprimé du dossier).
4. `source_order` **vide** ⇒ défaut : fichiers triés naturellement puis URLs en
   ordre de saisie (rétro-compatible).

L'ordre résultant alimente `run.sources` → **ordre des chapitres** du document
consolidé (consolidation actuelle, inchangée). Seules les sources **incluses**
comptent dans l'estimation de coût et le traitement.

### 7.3 UI — double liste (shuttle)
Vue « Sources » (réglages génération) avec **deux listes** :
- **« Sources à traiter — ordre des chapitres »** : sources incluses, réordonnables
  (glisser-déposer + flèches ↑/↓). Chaque ligne : rang, pastille de type
  (VID/AUD/DOC/YT), nom de fichier ou URL, durée si connue, badge « nouveau » pour
  une source apparue depuis le dernier réglage.
- **« Exclues — non traitées »** : sources écartées (style grisé), avec « ↑ réinclure »
  par ligne.
- **Glisser-déposer entre les deux listes** pour exclure/réinclure. Écrit
  `source_order` (haut) et `excluded_sources` (bas).
- Deux boutons : **« Rafraîchir »** (re-scanne le dossier — nouveaux fichiers en fin
  de liste du haut, fichiers disparus retirés — **en conservant** les exclusions) ;
  **« Tout réinclure »** (vide `excluded_sources`).
- Persistance à la sauvegarde des réglages (comme le reste du formulaire).

Maquettes validées : `.superpowers/brainstorm/.../sources-ordering-v2.html`.

## 8. Estimation de coût (`app/cost_estimator.py`, `app/_cost_common.py`)

Entrée généralisée de `videos_durations_seconds` → **poids par source** :
```python
@dataclass(frozen=True)
class SourceWeight:
    kind: SourceKind
    audio_seconds: float       # vidéo/audio/YouTube ; 0 pour document
    text_tokens: float         # document ; 0 sinon
    reformulated: bool = True  # False si document en pass-through
```
- **STT** : `sum(audio_seconds)` × tarif (documents exclus).
- **LLM par source** : base = `audio_seconds → mots → tokens` (média) ou
  `text_tokens` (document). REFORMULATION mise à 0 si `reformulated=False`.
- **Durée YouTube** : `YoutubeDownloader.probe_duration(url)` (réseau ; 0 si
  indispo → avertissement « estimation partielle »).
- **Tokens document** : `len(texte) / TEXT_CHARS_PER_TOKEN` (≈ 4), constante
  centralisée.

`CostEstimator.estimate(source_weights, ...)`. Appelants UI adaptés.

## 9. Réglages & assemblage

### 9.1 `GenerationSettings` (`domain/generation.py`)
Nouveaux champs (migration *lenient* du blob `settings_json` v2 ; absents → défauts) :
- `youtube_urls: tuple[str, ...] = ()`
- `reformulate_documents: bool = True`
- `source_order: tuple[str, ...] = ()`
- `excluded_sources: tuple[str, ...] = ()`

### 9.2 `build_input_sources` (`app/input_sources.py`, ex `video_scanner.py`)
```python
def build_input_sources(settings: GenerationSettings) -> list[SourceExecution]:
    """Fichiers scannés + URLs, moins les exclues, ordonnés selon source_order (§7.2).

    Raises:
        StorageError: dossier inaccessible.
        ConfigError: CONFIG.NO_INPUT_SOURCE si aucune source **incluse**
            (toutes exclues, ou ni fichier ni URL).
    """
```
`RunOrchestrator.create_run`/`resume_or_create_run` l'appellent.

## 10. UI
- `GenerationSettingsView` : page « Sources » avec libellé dossier « Dossier
  d'entrée (vidéos, audios, documents) » ; champ multi-lignes « Liens YouTube (un
  par ligne) » ; case « Reformuler les documents texte » (cochée par défaut) ;
  composant **double liste** « Sources à traiter » (ordonnée) / « Exclues »
  (glisser-déposer entre les deux, boutons « Rafraîchir » / « Tout réinclure »).
- Matrice / viewmodels : libellé phase 0 → « Transcription / Ingestion » ; colonne
  source affiche `InputSource.display_name()` ; tri/affichage par `source_id`.
- `generation_controller` : DI du dispatcher (binaires ffmpeg/yt-dlp résolus) ;
  estimation via `SourceWeight`.

## 11. Erreurs (`core/errors`)

| Code | Sévérité | Sens |
|---|---|---|
| `INGESTION.UNSUPPORTED_SOURCE` | ERROR | Aucun ingesteur pour ce `SourceKind` |
| `INGESTION.YTDLP_NOT_FOUND` | FATAL | Binaire yt-dlp introuvable |
| `INGESTION.YOUTUBE_DOWNLOAD_FAILED` | ERROR | Échec download (réseau, privé, géo-bloc, **yt-dlp obsolète**) |
| `INGESTION.TEXT_EXTRACTION_FAILED` | ERROR | PDF/docx illisible |
| `INGESTION.EMPTY_DOCUMENT` | ERROR | Document sans texte extractible |
| `CONFIG.NO_INPUT_SOURCE` | ERROR | Ni fichier supporté ni URL |

Hiérarchie `IngestionError(Fahmi2Error)` ; messages FR dans `messages.py`. Le message
`YOUTUBE_DOWNLOAD_FAILED` **mentionne explicitement** l'obsolescence possible de
yt-dlp et invite à mettre à jour le binaire (override §4.3). Toute erreur
d'ingesteur est une `Fahmi2Error` → `PhaseFinished.error`.

## 12. Dépendances & packaging
- `pyproject.toml` : `pypdf`, `python-docx` (modules Python). `yt-dlp` est utilisé
  en **binaire** (pas en dépendance pip importée), bundlé comme ffmpeg.
- `packaging/` : télécharger le **binaire yt-dlp** au build (script type
  `fetch-ffmpeg.ps1`), le bundler, le résoudre au runtime (`resolve_ytdlp_binary`).
  `.spec` : `pypdf`/`docx` purs (hiddenimports si manqués ; `--collect-data docx`).
- **Stratégie d'obsolescence yt-dlp** (point dur d'une app portable) :
  1. binaire **remplaçable** par l'utilisateur sans rebuild (override) ;
  2. message d'erreur explicite invitant à la mise à jour ;
  3. documentation : rebuild régulier recommandé pour rafraîchir le binaire bundlé.
- Documenter dans `packaging/README.md` (réseau YouTube ; ToS YouTube assumées par
  l'utilisateur ; obsolescence yt-dlp).

## 13. Persistance SQLite (`infra/storage/sqlite_state.py`)
Migration de colonne **propre et idempotente** dans `_apply_soft_migrations`
(SQLite ≥ 3.25, fourni par Python 3.12) :
- table des exécutions de source : `video_id → source_id` ; ajout `source_kind TEXT`,
  `source_location TEXT` ;
- table `phase_executions` : `video_id → source_id` (+ contrainte/index
  `UNIQUE(run_id, phase_id, source_id)` recréée — attention au piège `NULL` des
  phases batch déjà géré par `DELETE+INSERT`) ;
- garde-fou : `PRAGMA table_info` pour détecter une migration déjà appliquée
  (idempotence) ; lignes legacy → `source_kind='video'`, `source_location=<ancien path>`.

`youtube_urls`/`reformulate_documents`/`source_order` vivent dans le blob
`settings_snapshot`/`settings_json` (pas de colonne dédiée).

> Test dédié : ouverture d'une base **legacy** (pré-migration) → migration
> appliquée sans perte, relecture des `SourceExecution` correcte.

## 14. Tests
- `classify_file` ; `build_input_sources` (mixte trié + URLs ; `source_order`
  respecté + réconciliation nouveaux/obsolètes ; **`excluded_sources` filtrées** ;
  toutes exclues ou rien → `CONFIG.NO_INPUT_SOURCE`).
- `MediaIngestor` (ffmpeg réel + `FakeSTTProvider`).
- `DocumentIngestor` (`FakeTextExtractor` → **segment unique** texte intégral,
  structure préservée ; vide → `EMPTY_DOCUMENT`). `TextExtractor` (petit PDF/docx réels).
- `YoutubeIngestor` (`FakeYoutubeDownloader` → délégation MediaIngestor + progression ;
  erreur → `YOUTUBE_DOWNLOAD_FAILED`).
- `IngestionDispatcher` (routage + `UNSUPPORTED_SOURCE`).
- **Phase 3 pass-through** : document + drapeau off → `reformulated/{id}.md`
  **identique** au texte source (structure préservée), coût 0, LLM **non** appelé.
- `CostEstimator` : `SourceWeight` document (STT 0, reformulation 0 si pass-through) ;
  YouTube durée sondée.
- **Migration SQLite** : base legacy → `source_id` + colonnes, relecture OK ;
  idempotence (2e application sans effet).
- e2e mixte (1 audio + 1 PDF).
- `pytest`, `ruff check .`, `mypy src tests` verts.

## 15. Découpage des responsabilités (fichiers)

| Fichier | Rôle | Action |
|---|---|---|
| `domain/enums.py` | `SourceKind` | Modifier |
| `domain/source.py` | `InputSource`, `SourceExecution` | Créer |
| `domain/video.py` | (supprimé) | Supprimer |
| `domain/ids.py` | `VideoId → SourceId` | Modifier |
| `domain/run.py` | `Run.videos → Run.sources` | Modifier |
| `domain/generation.py` | `youtube_urls`, `reformulate_documents`, `source_order`, `excluded_sources` | Modifier |
| `infra/ingestion/interface.py` | `SourceIngestor`, `IngestionDeps` | Créer |
| `infra/ingestion/media_ingestor.py` | VIDEO + AUDIO | Créer |
| `infra/ingestion/youtube_ingestor.py` | YOUTUBE + `YoutubeDownloader` port | Créer |
| `infra/ingestion/youtube_downloader.py` | adapter `YtDlpDownloader` + résolution binaire | Créer |
| `infra/ingestion/document_ingestor.py` | DOCUMENT | Créer |
| `infra/ingestion/text_extractor.py` | `TextExtractor` + défaut | Créer |
| `infra/ingestion/dispatcher.py` | `IngestionDispatcher` + builder | Créer |
| `infra/ingestion/classify.py` | extensions + `classify_file` | Créer |
| `infra/ingestion/_fakes.py` | fakes downloader/extractor | Créer |
| `core/config/paths.py` | `resolve_ytdlp_binary_or_none` | Modifier |
| `pipeline/phase_handler.py` | `PhaseContext.ingestion` | Modifier |
| `pipeline/handlers/phase_0_stt.py` | délègue au dispatcher | Modifier |
| `pipeline/handlers/phase_3_reformulation.py` | pass-through document | Modifier |
| `pipeline/handlers/phase_1/4/5/6/7` | `video → source` (renommage) | Modifier |
| `app/input_sources.py` | `build_input_sources` (ex video_scanner) | Créer/Renommer |
| `app/run_orchestrator.py` | appel `build_input_sources` | Modifier |
| `app/cost_estimator.py` + `_cost_common.py` | `SourceWeight` | Modifier |
| `infra/storage/sqlite_state.py` | migration `video_id → source_id` + colonnes | Modifier |
| `ui/dialogs/generation_settings_view.py` | URLs + reformulation + ordre | Modifier |
| `ui/widgets/*` (sources) | double liste réordonnable + exclusion (shuttle) | Créer |
| `ui/generation_controller.py` | DI dispatcher + libellés + estimation | Modifier |
| `ui/viewmodels/*`, matrice | `source` + libellé phase | Modifier |
| `pyproject.toml`, `packaging/*` | deps + bundling yt-dlp/pypdf/docx | Modifier |
| `tests/**` | fakes + tests §14 | Créer/Modifier |
| `docs/`, `CLAUDE.md`, `README.md`, `CHANGELOG` | doc transverse | Modifier |

## 16. Lots d'implémentation
1. **Fondation + Audio** : `SourceKind`, `InputSource`, `SourceExecution`
   (renommage), migration SQLite, `classify`, dispatcher + `MediaIngestor`
   (refactor phase 0), extensions audio, `build_input_sources` (sans
   ordonnancement custom), adaptation UI matrice/DI. → vidéo **et** audio OK.
2. **Documents** : `TextExtractor`, `DocumentIngestor` (segment unique), drapeau +
   pass-through phase 3, `SourceWeight` (coût documents), case UI.
3. **YouTube** : `YtDlpDownloader` (binaire + résolution + override + progression),
   `YoutubeIngestor`, champ URLs UI, durée via métadonnée, packaging.
4. **Ordonnancement & exclusion** : `source_order` + `excluded_sources`,
   réconciliation/filtrage dans `build_input_sources`, composant UI **double liste**
   (shuttle) « Sources à traiter » / « Exclues » avec « Rafraîchir » (préserve) /
   « Tout réinclure ».

## 17. Limites connues (assumées)
- **PDF scannés** non gérés (pas d'OCR) → `EMPTY_DOCUMENT`.
- **Timestamps documents** : segment unique `start=end=0` (aucun aval n'en dépend).
- **yt-dlp** fragile aux évolutions YouTube : mitigé par binaire remplaçable +
  message + doc, mais pas éliminé (cf. §12).
- **ToS YouTube** : le téléchargement relève de la responsabilité de l'utilisateur.
- **Mélange** hétérogène fonctionnel mais non optimisé en ergonomie ; un projet
  mixte audio-local + docs reste à 1 worker en phase 0 (§5).
- **Ordre des chapitres** = `source_order` (consolidation actuelle). Les modes
  alternatifs (intelligent/thématique) relèvent de la spec séparée.
