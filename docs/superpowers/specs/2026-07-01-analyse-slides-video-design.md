# Analyse des slides dans les vidéos — Design

Date : 2026-07-01
Statut : validé (brainstorming interactif)

## Objectif

Certaines vidéos de cours affichent des slides (plein écran ou en fenêtre
partielle) qui enrichissent le propos oral. La fonctionnalité ajoute une
**option activable par vidéo** (locale ou YouTube) qui extrait le contenu des
slides (texte fidèle + description des éléments visuels) via un modèle vision
OpenAI et l'**intercale, horodaté, dans la transcription** produite en phase 0,
de sorte que toute la chaîne de synthèse (phases 1 à 7) en tienne compte avec
la bonne correspondance temporelle audio ↔ slides — sans aucune modification
des phases aval.

## Décisions clés (arbitrées avec l'utilisateur)

| Décision | Choix retenu |
|---|---|
| Contenu extrait | Texte fidèle de la slide **+** description synthétique des visuels (schémas, graphiques, tableaux, images) |
| Point d'intégration | **Fusion dans la `Transcription`** : segments horodatés intercalés avec les segments audio en phase 0 |
| Option par vidéo | Case à cocher par source dans `SourceOrderView`, persistée comme `slides_sources: tuple[str, ...]` (pattern `excluded_sources`) |
| Modèle vision | **Configurable** (enum `VisionModel`, pattern `CloudSttModel`), défaut **gpt-5-mini** (~0,25 $/M entrée, ~2 $/M sortie — meilleur rapport qualité/prix, vérifié 2026-07) ; options gpt-5-nano (éco) et gpt-5.4-mini (qualité) |
| Granularité | **1 image par slide, état final** : pour une slide dévoilée progressivement, on retient la dernière image stable avant transition (contient tout le contenu) ; horodatage = plage d'affichage de la slide |

Justification de la granularité : l'alignement oral ↔ slide se fait par
entrelacement temporel au niveau slide ; la synthèse travaille au niveau
sections/chapitres, le micro-horodatage intra-slide (puce par puce) n'apporte
rien et multiplierait les appels vision (3–10×) en injectant du contenu
dupliqué (chaque état intermédiaire répète les puces précédentes).

## Architecture

### 1. Domaine (`domain/`)

- `GenerationSettings` gagne :
  - `slides_sources: tuple[str, ...] = ()` — clés stables
    (`InputSource.order_key()`) des sources vidéo/YouTube dont l'analyse de
    slides est activée. Réconciliation au scan comme `excluded_sources`
    (clés obsolètes ignorées, via la fonction pure partagée) ; migration
    *lenient* du blob v2 (champ absent = tuple vide).
  - `vision_model: VisionModel = VisionModel.GPT_5_MINI`.
- Nouvel enum `VisionModel { GPT_5_NANO, GPT_5_MINI, GPT_5_4_MINI }` dans
  `domain/enums.py` (valeurs = identifiants API OpenAI).

### 2. Extraction d'images (`infra/video/`)

Nouveau module `infra/video/` :

- **`frame_extractor.py`** — `SlideFrameExtractor` :
  1. **Une passe ffmpeg** échantillonne la vidéo à intervalle fixe
     (~1 image / 2 s) en frames JPEG réduites (côté max ~1280 px, qualité
     ~80 — lisibilité des slides préservée, tokens image minimisés) dans
     `workspace/frames/<source_id>/`.
  2. **Regroupement par hachage perceptuel par tuiles** (dHash via Pillow,
     déjà dépendance du projet). Un dHash *global* diluerait un changement de
     slide **fenêtrée ou en demi-page** (distance faible → slides fusionnées à
     tort) ; la détection travaille donc par régions :
     - la frame est découpée en **grille de tuiles** (ex. 8×8), chacune avec
       son dHash ;
     - **masque de bruit temporel** : les tuiles qui changent à quasi chaque
       échantillon (webcam incrustée, vidéo dans la slide, animation
       permanente) sont **exclues** de la mesure ;
     - la décision se prend sur la **fraction de tuiles actives changeant
       simultanément**, avec **double seuil** :
       - fraction < `F_bas` : image identique → ignorée ;
       - `F_bas` ≤ fraction < `F_haut` : même slide en dévoilement progressif
         (une puce ne touche que 1–2 tuiles) → la frame représentative du
         groupe est **remplacée** par la plus récente (état final) ;
       - fraction ≥ `F_haut` : nouvelle slide (la majorité des tuiles de la
         zone de slide bascule d'un coup) → nouveau groupe.
     La mesure étant **relative aux tuiles actives**, elle est insensible au
     fenêtrage : slide plein écran, en moitié d'image ou en fenêtre sont
     détectées de la même façon ; l'affichage progressif et les incrustations
     animées sont discriminés par la localité du changement.
  3. Sortie : liste ordonnée de `SlideFrame(start_seconds, end_seconds,
     image_path)` (début = première frame du groupe, fin = dernière ; le
     dernier groupe se clôt à la fin de la vidéo).
- **Garde-fous de robustesse** (la détection est heuristique — cas
  pathologiques : cours filmés caméra, vidéo dans la slide, webcam très
  animée) :
  - **Plafond de slides analysées par vidéo** : constante ~4 slides/min +
    borne absolue ; au-delà, les groupes excédentaires sont ignorés et un
    avertissement explicite est journalisé (« détection instable, N images
    ignorées ») — coût borné, jamais de facture surprise.
  - **Dédoublonnage inter-slides** : si le hash de la slide N est
    quasi identique à celui de la slide N−1 (re-détection parasite), les
    groupes sont fusionnés (pas de ré-analyse vision).
- **`_constants.py`** — tous les nombres magiques centralisés : intervalle
  d'échantillonnage, dimension/qualité JPEG, taille de la grille de tuiles,
  seuil de bruit temporel, seuils `F_bas`/`F_haut`, plafonds slides/min et
  absolu (directive n° 1).
- Les frames sont **supprimées après analyse** (best-effort, comme le WAV
  intermédiaire).

### 3. Port vision (`infra/vision/`)

Pattern ports/adapters existant (miroir de `infra/embeddings/`) :

- **`interface.py`** — port `SlideVisionProvider` (Protocol) :
  `analyze_slide(image_path, *, language) -> SlideContent(text,
  visuals_description)` + `estimate_cost(...)` + `consumed_cost_usd()`.
- **`openai_vision.py`** — `OpenAIVisionAdapter` : appel responses/chat avec
  image encodée, **JSON mode** (sortie typée `{texte, visuels}`), retry via
  `core/retry` (classification par défaut), modèle piloté par `VisionModel`.
- **`_pricing.py`** — USD/token par `VisionModel` + calcul des tokens image
  (patches) ; source unique pour l'adapter et les estimateurs.
- **`_fakes.py`** — `FakeVisionProvider` (déterministe, coûts simulés).
- **Prompt** `infra/prompts/defaults/slide_analysis.j2` : transcription
  fidèle du texte de la slide + description synthétique des visuels, en
  **langue détectée par le STT** (le transcript fusionné reste monolingue ;
  la traduction reste l'affaire de la phase 6). Le prompt précise que la
  slide peut être **plein écran, en moitié d'image ou fenêtrée** : extraire
  le contenu de la slide/illustration où qu'elle soit, **ignorer** le
  présentateur, la webcam et le décor ; si **aucune slide n'est visible**,
  renvoyer un contenu vide (→ aucun segment injecté, pas de bruit). Ajouté
  au catalogue `PromptsService` → éditable via `PromptsEditorDialog`,
  override `%APPDATA%` comme les autres.
- **Parallélisation** : appels vision bornés par `map_bounded`
  (`parallelism.llm_workers`, ordre préservé → déterministe), **honore le
  `PauseToken`**. Une image par requête.
- **`slide_analyzer.py`** — `SlideAnalyzer` : façade composant
  `SlideFrameExtractor` + `SlideVisionProvider`
  (`analyze(video_path, source_id, *, language) -> list[AnalyzedSlide]`,
  chaque `AnalyzedSlide` portant plage temporelle + `SlideContent`). C'est
  cette façade qui est injectée dans `IngestionDeps` et qui porte la
  parallélisation `map_bounded` et le nettoyage des frames.

### 4. Intégration ingestion (phase 0)

- `IngestionDeps` gagne `slide_analyzer: SlideAnalyzer | None`
  (composition `SlideFrameExtractor` + `SlideVisionProvider` ; `None` =
  fonctionnalité indisponible — pas de clé OpenAI).
- Le protocole `SourceIngestor.ingest` gagne le keyword
  `analyze_slides: bool` ; `DocumentIngestor` l'ignore.
- **`MediaIngestor`** : si `analyze_slides` et source vidéo → après le STT,
  extraction des frames + analyse vision + fusion. L'ordre STT-d'abord
  fournit la langue détectée au prompt vision.
- **Fusion** — fonction pure `merge_slides_into_transcription(transcription,
  slides) -> Transcription` (`infra/ingestion/slide_merge.py`) : intercale
  des `TranscriptionSegment` aux timestamps d'affichage, texte au format
  `[Slide affichée de mm:ss à mm:ss] <texte> — Visuels : <description>`
  (libellés FR, cohérents avec les prompts FR gelés). L'ordre temporel des
  segments est préservé ; `full_text()` expose naturellement le contenu
  entrelacé aux phases aval.
- **YouTube** : si l'option est activée pour l'URL,
  `YtDlpDownloader.download_video` (nouveau, format **≤ 720p** — suffisant
  pour lire des slides, minimise le téléchargement) au lieu de l'audio seul ;
  le fichier téléchargé est ingéré comme vidéo locale (délégation
  `MediaIngestor` existante), puis supprimé.
- Le handler `phase_0_stt` lit `settings.slides_sources`, apparie par
  `order_key()`, et passe `analyze_slides` par source.
- **Pré-condition** : option activée sur ≥ 1 source sans clé OpenAI
  configurée → `Fahmi2Error` explicite (code + message FR) **avant** le run.

### 5. Coûts (`app/`)

- `SourceWeight` gagne `slide_count: float` (0 par défaut), estimé à partir
  de la durée audio × constante slides/min (dans `_cost_common` ou constants
  du module).
- `CostEstimator` : nouveau poste vision = `slide_count × (tokens image +
  tokens sortie estimés) × tarif VisionModel` ; facteur d'augmentation du
  volume de base aval (le texte des slides grossit l'entrée des phases
  1/3/4/5) via une constante dédiée.
- **Coût réel** : `consumed_cost_usd()` du provider vision agrégé au coût de
  la phase 0 par source (pattern d'attribution per-source v1.5.1).

### 6. UI (`ui/`)

- **`SourceOrderView`** : case à cocher « Analyser les slides » par ligne,
  active uniquement pour vidéo/YouTube (grisée pour audio/documents),
  persistée dans `slides_sources` (réconciliation partagée avec le scan).
- **`GenerationSettingsView`** : sélecteur du modèle vision (libellés
  centralisés, pattern `_model_labels`), placé près du modèle STT cloud.
- **Estimation de coût** : dialogue `CostEstimate` affiche le poste vision.
- **i18n** : nouvelles chaînes via `self.tr()` (contexte = classe),
  ré-extraction (`scripts/i18n_extract.py`) + compilation
  (`scripts/i18n_compile.py`) + traductions EN + garde-fous
  `tests/unit/i18n/test_i18n.py`.
- **Progression** : pas de sous-barre dédiée pour l'étape vision (YAGNI) ;
  la phase 0 journalise des événements de log par étape (extraction /
  analyse / fusion).

### 7. Erreurs

- Nouvelle `VisionError` dans la hiérarchie `Fahmi2Error` (code +
  `user_message` FR + détails techniques) ; l'extraction de frames échoue en
  `FFmpegError` existante. Propagation standard → `ErrorInfo` →
  panneau Logs + `events.jsonl`.

### 8. Tests

- **Unités pures** : regroupement par tuiles (cas nominaux + dévoilement
  progressif + nouvelle slide plein écran + **nouvelle slide fenêtrée /
  demi-page** + webcam simulée exclue par le masque de bruit + plafond +
  dédoublonnage inter-slides), `merge_slides_into_transcription` (ordre
  temporel, formats, **slide vide non injectée**), réconciliation
  `slides_sources`, `_pricing` vision, `CostEstimator` avec `slide_count`.
- **Fakes** : `FakeVisionProvider` ; `MediaIngestor` testé avec fakes
  (slides activées/désactivées, source audio → jamais d'analyse).
- **UI** : viewmodels sans Qt ; smoke pytest-qt `SourceOrderView` (case
  grisée/active) ; garde-fous i18n sur les nouvelles chaînes.
- Fin de tâche : `pytest` + `ruff check .` + `mypy src tests` **tous
  propres**.

### 9. Documentation & packaging

- `CLAUDE.md` (mécanismes transverses + arbo `infra/`), `README.md`,
  `docs/` (EN).
- Packaging : aucune dépendance nouvelle à bundler (Pillow déjà présent via
  xhtml2pdf ; ffmpeg déjà bundlé) ; note dans `packaging/README.md` si le
  `.spec` doit référencer le prompt `slide_analysis.j2` (couvert par le
  glob des defaults existant, à vérifier au plan).

## Hors périmètre (YAGNI)

- Granularité par puce / étape de révélation.
- OCR local (Tesseract & co) — le modèle vision couvre texte + visuels.
- Analyse de slides sur sources audio ou documents.
- Cap de coût runtime dédié à la vision (l'estimation pré-run + le plafond
  de slides bornent le coût, comme la génération).
- Insertion des images de slides dans le document consolidé (le livrable
  reste textuel).

## Risque résiduel assumé

La détection de changement de slide est heuristique : sur des vidéos
atypiques (cours filmés caméra, incrustations très animées), la qualité de
détection peut se dégrader. Le risque est **borné en coût** (plafond),
**observable** (avertissements journalisés) et **corrigeable sans refonte**
(seuils centralisés en constantes, prompt vision éditable).
