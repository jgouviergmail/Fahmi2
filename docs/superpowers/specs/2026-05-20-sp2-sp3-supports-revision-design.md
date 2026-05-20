# SP2 + SP3 — Générateur de supports de révision (design détaillé)

- **Date** : 2026-05-20
- **Statut** : design (à valider)
- **Chapeau** :
  [`2026-05-20-supports-revision-vision-chapeau.md`](./2026-05-20-supports-revision-vision-chapeau.md)
- **Prérequis** : SP1 (coquille multi-fonctionnalités) terminé — `Project` minimal,
  `GenerationSettings`, onglets, `pedagogy/` réservé, blob v2 avec clé `pedagogy: null`.

## 1. Objectif & portée

- **SP2 — Génération des supports** : à partir du **document consolidé** + **glossaire**
  produits par la Génération, produire des supports de révision (9 types) sous forme
  d'**artefacts structurés** (JSON typé + Markdown rendu) dans `pedagogy/`. Onglet
  pédagogique réel : réglages, sélection des supports, difficulté, lancement, suivi.
- **SP3 — Exports** : convertir les artefacts en **`.apkg` (Anki, genanki)** et
  **Markdown/PDF** (fiches, sujets, corrigés, examen blanc).

## 2. Décisions techniques verrouillées

1. **Orchestrateur dédié léger** (pas le `PipelineEngine`). Justification : `invoke_llm`
   est couplé à `PhaseContext`/`PhaseId`/`phases_config` et le couple `Run`/vidéos ne
   mappe pas la pédagogie (générateurs **indépendants** en éventail, consommant des
   artefacts existants). On réutilise les briques **découplées** : `LLMProvider`,
   `PromptLoader`, `EventBus`, `with_retry` (`RetryPolicy`), `FsArtifactStore`, et un
   helper de parsing JSON **généralisé** (cf. §5.3). On **ne tord pas** les types
   frozen de la génération.
2. **Reprise *coarse* par artefact** : un support déjà produit (fichier présent et plus
   récent que le doc consolidé source) est **sauté**. Pas de checkpoint SQLite fin
   (cohérent avec « curation = fichiers éditables »). Un drapeau « régénérer tout »
   force la reconstruction.
3. **Pas de persistance DB des supports** : les artefacts vivent **sur disque** sous
   `pedagogy/` (curation = fichiers éditables). Le seul état DB est la `PedagogySettings`
   dans le blob `projects.settings_json` (clé `pedagogy`, déjà réservée).
4. **Dépendance genanki** (SP3) : nouvelle dépendance, adapter `infra/anki/`
   (ports/adapters), bundlée dans le `.spec` PyInstaller.
5. **Ordre de build = tranches verticales** : livrer un support **de bout en bout**
   (génération → fichier → export) avant d'élargir. 1ʳᵉ tranche = **flashcards
   glossaire** (sans LLM) → JSON+MD → `.apkg`. Réduit le risque et donne un produit
   fonctionnel tôt.
6. **Réutilisation `PhaseConfig`** pour la config LLM de la pédagogie (thinking,
   reasoning_effort, température) — DRY, pas de nouveau type.

## 3. Modèle de domaine

### 3.1 Enums (`domain/enums.py`)

- `SupportType` : `FLASHCARDS_GLOSSARY`, `FLASHCARDS_CONCEPTS`, `QCM`, `TRUE_FALSE`,
  `CLOZE`, `OPEN_QUESTIONS`, `REVISION_SHEET`, `KEY_POINTS`, `MOCK_EXAM`.
- `TargetAudience` : `DISCOVERY`, `HIGH_SCHOOL`, `LICENCE`, `MASTER_EXPERT`.
- `BloomObjective` : `AUTO`, `RESTITUTE`, `UNDERSTAND_APPLY`, `ANALYZE_BEYOND`.
- `SupportDensity` : `LIGHT`, `STANDARD`, `DENSE`.

Constantes : ensemble des supports **évaluatifs** (corrigé possible) =
`{QCM, TRUE_FALSE, CLOZE, OPEN_QUESTIONS, MOCK_EXAM}` ; supports **sans LLM** =
`{FLASHCARDS_GLOSSARY}`.

### 3.2 `PedagogySettings` (`domain/pedagogy.py`, frozen)

```
PedagogySettings(
    selected_supports: frozenset[SupportType],          # non vide
    separate_correction: frozenset[SupportType],         # ⊆ évaluatifs ∩ selected
    target_audience: TargetAudience,
    bloom_objective: BloomObjective,                     # AUTO par défaut
    pedagogy_directives: str,                            # libre
    languages: tuple[Language, ...],                     # non vide
    density: SupportDensity,
    llm_model: LLMModel,
    llm_config: PhaseConfig,                             # thinking/effort/temp/retries
    export_formats: frozenset[ExportFormat],             # APKG, MARKDOWN, PDF
)
```
`__post_init__` : `selected_supports` non vide ; `separate_correction ⊆ évaluatifs ∩
selected_supports` ; `languages` non vide ; cohérence enums.

### 3.3 `Project.pedagogy`

Ajouter `pedagogy: PedagogySettings | None = None` à `Project` (champ réservé au SP1).
Persistance : `_serialize_project_blob` sérialise `pedagogy` (au lieu de `None` codé en
dur) ; `_deserialize_project_blob` lit la clé `pedagogy` (présente depuis v2).

### 3.4 Entités de support (`domain/supports.py`, frozen)

Représentations structurées (consommées par les exports SP3) :

- `Flashcard(front, back, source_ref, tags)`.
- `QcmItem(question, choices: tuple[str, ...], correct_index, justification, source_ref)`.
- `TrueFalseItem(statement, is_true, justification, source_ref)`.
- `ClozeItem(text, answers: tuple[str, ...], source_ref)`.
- `OpenQuestion(question, expected_points: tuple[str, ...], source_ref)`.
- `RevisionSheet(chapter_title, summary_markdown, source_ref)`.
- `KeyPoints(chapter_title, points: tuple[str, ...], source_ref)`.
- `MockExam(title, sections: tuple[...], grading_markdown)`.
- `SupportArtifact(support_type, language, items, rendered_markdown)` — enveloppe
  unifiée écrite sur disque (JSON + `.md`).

`source_ref` = ancre/chapitre d'origine (traçabilité, réutilise les ancres GFM du doc
consolidé).

## 4. Entrants & dépendance à la Génération

- **Document consolidé** : `<emplacement>/generation/output/consolidated.{lang}.md`.
  Un *parser* découpe en **chapitres** (titres `# N. …`) pour la génération par chapitre.
- **Glossaire** : `glossary.{lang}.md` (tableau) **ou** `SqliteState.list_glossary_terms`
  du dernier run COMPLETED. Décision : lire le **`.md`** de sortie (découplé de la DB,
  cohérent avec « consomme les livrables »).
- **Fraîcheur (R19)** : si le doc consolidé est plus récent que les supports déjà
  produits, l'UI signale « supports périmés — régénérer ». Comparaison de mtime.
- **Indisponibilité** : si la génération n'a pas produit de doc consolidé pour la langue
  demandée → l'onglet affiche « génération requise » (raccourci vers l'onglet Génération).

## 5. Orchestrateur & registre de générateurs (`app/` + `pedagogy/`)

### 5.1 `SupportGenerator` (ABC) + `SupportGeneratorRegistry`

Calqué sur `PhaseHandler`/`PhaseRegistry` (conformité) :

```
class SupportGenerator(ABC):
    @property def support_type(self) -> SupportType
    @property def uses_llm(self) -> bool
    def generate(self, ctx: SupportContext, *, language, chapters, glossary) -> SupportArtifact
```

`SupportGeneratorRegistry` : enregistre/retrouve par `SupportType`, ordre canonique.

### 5.2 `SupportContext` (DI, frozen)

Porte : `pedagogy: PedagogySettings`, `generation_output_dir: Path`, `pedagogy_dir: Path`,
`llm_provider`, `prompts: PromptLoader`, `artifacts: FsArtifactStore`,
`event_bus: EventBus`, `pause_token: PauseToken`. **Pas** de STT/ffmpeg.

### 5.3 `SupportsOrchestrator` (`app/supports_orchestrator.py`)

- Charge inputs (doc consolidé par langue → chapitres ; glossaire par langue).
- Itère `selected_supports × languages` (× chapitres selon le support), invoque le
  générateur via le registre, écrit `pedagogy/<support>/<lang>/…` (JSON + `.md`),
  émet des events (`SupportStarted`/`SupportFinished`/`RetryAttempt`) sur l'`EventBus`,
  agrège le coût, applique la **reprise coarse** (skip si artefact frais).
- LLM via un helper **généralisé** `invoke_llm_chat(llm_provider, llm_model, config,
  system, user)` + `parse_json(content, *, context_label)` (extraits/généralisés depuis
  `pipeline/handlers/_base.py` vers un module partagé `core`/`infra` réutilisable —
  refactor DRY sans casser les handlers existants).
- `with_retry` + `RetryPolicy` pour les appels LLM (mêmes codes retryables).

### 5.4 Événements pédagogie

Nouveaux types (`pipeline/events.py` ou `app/`) : `SupportGenerationStarted`,
`SupportStarted(support_type, language)`, `SupportFinished(…, cost, error)`,
`SupportGenerationFinished(status)`. Bridgés à l'UI via `QtEventBus` (réutilisé).

## 6. Générateurs par support (SP2)

| Support | LLM | Production |
|---------|-----|-----------|
| Flashcards glossaire | non | recto = terme/acronyme, verso = définition (depuis le glossaire) |
| Flashcards concepts | oui | Q/R sur idées-clés par chapitre |
| QCM | oui | question + distracteurs + bonne réponse + justification |
| Vrai/Faux | oui | affirmation + réponse + justification |
| Cloze | oui | phrase à trous + réponses |
| Questions ouvertes | oui | question + éléments de réponse |
| Fiche de révision | oui | synthèse par chapitre |
| Points clés | oui | 3–5 puces par chapitre |
| Examen blanc | oui | sujet composite + barème |

Chaque générateur LLM : prompt calé sur **public cible + Bloom + densité + directives**,
réponse **JSON** parsée en entités typées (§3.4). **Corrigé** : pour les évaluatifs avec
`separate_correction`, le rendu Markdown produit **deux fichiers** (sujet sans réponses /
corrigé). Une **passe de validation/dé-biaisage** des QCM (équilibrage de la bonne
réponse, distracteurs plausibles) est prévue (générateur QCM en 2 temps, optionnel).

## 7. Prompts (`infra/prompts/defaults/`)

Nouveaux templates `pedagogy_<support>.j2` (1 par support LLM, soit 8) avec variables :
`output_language_label`, `audience_label`, `bloom_label`, `density_label`,
`pedagogy_directives`, `chapter_markdown` (ou `consolidated_markdown`),
`glossary_terms`. Surcouche `%APPDATA%` héritée du `PromptLoader` existant.

## 8. UI — onglet pédagogique (SP2)

Remplace le stub. Composé via les briques SP1 :

- **Réglages** (bouton « ⚙ Réglages » + `SettingsView` master-detail) : catégories
  **Supports** (grille des 9 + case « corrigé séparé » sur les évaluatifs), **Difficulté**
  (public cible + Bloom *Auto/Restituer/Comprendre & Appliquer/Analyser & au-delà* +
  directives + densité), **Langues** (parmi les langues produites), **Modèle & coût**
  (modèle LLM + thinking + formats d'export).
- **Cockpit** : bouton **Générer**, **Estimer le coût**, **Ouvrir le dossier**
  (`pedagogy/`), une vue de progression (liste supports × langues, statut/coût), bandeau
  d'état (« génération requise » / « supports périmés » / prêt). `LogsDock` partagé.
- `PedagogyController` (parallèle au `GenerationController`, découplé du `MainWindow`),
  worker `QThread`, pause/cancel via `PauseToken`.

## 9. Exports (SP3)

- **`infra/anki/genanki_exporter.py`** : `.apkg` — `Flashcard`→Basic,
  `ClozeItem`→Cloze, `QcmItem`→note type custom ; **GUID stables** (hash du contenu) pour
  ré-import sans doublon ; **sous-decks** par chapitre ; **tags** (support, langue,
  difficulté). Dépendance `genanki` (bundle `.spec`).
- **`infra/export/markdown_pdf.py`** : rendu Markdown (déjà structuré) ;
  Markdown→PDF via une lib pure-python bundlable (à choisir au plan SP3 : `markdown` +
  `weasyprint`/`xhtml2pdf`, ou export MD seul + note pandoc). **Décision PDF à verrouiller
  au SP3** selon contrainte de bundling PyInstaller.

## 10. Estimation de coût pédagogie

`PedagogyCostEstimator` (parallèle à `CostEstimator`) : estime tokens par support ×
chapitre × langue selon densité + multiplicateur thinking (réutilise la grille existante).
Flashcards glossaire = 0 $. Exposé via « Estimer le coût » de l'onglet.

## 11. Décomposition en plans

**SP2** (génération) :
- **SP2/01 — Domaine & persistance** : enums, `PedagogySettings`, `Project.pedagogy`,
  sérialisation v2 (clé `pedagogy`), entités de support, tests + migration.
- **SP2/02 — Socle orchestrateur (tranche verticale flashcards glossaire)** :
  généralisation des helpers LLM/JSON, `SupportGenerator`/registre, `SupportContext`,
  `SupportsOrchestrator`, parser de chapitres + lecture glossaire, **générateur
  flashcards glossaire (sans LLM)** → JSON+MD, events, reprise coarse, tests.
- **SP2/03 — Générateurs LLM** : flashcards concepts, QCM (+ validation), vrai/faux,
  cloze, questions ouvertes, fiches, points clés, examen blanc + prompts + parsing, tests.
- **SP2/04 — Onglet pédagogique** : `PedagogyController`, `PedagogyTab` réel (réglages
  master-detail, sélection, difficulté, génération, progression), estimation de coût,
  fraîcheur, câblage `app_main`, smoke tests.

**SP3** (exports) :
- **SP3/01 — Export `.apkg`** : adapter genanki, GUID/sous-decks/tags, bouton export,
  tests.
- **SP3/02 — Export Markdown/PDF** : rendu + sujet/corrigé séparés, choix lib PDF, tests.

**SP3 final — Docs & clôture** : `docs/`, `README`, `CLAUDE.md`, `CHANGELOG`, matrice
chapeau (R8–R19 → faits).

Chaque plan : TDD, vérifs `pytest`/`ruff`/`mypy` vertes, commit.

## 12. Hors périmètre / risques

- **PDF** : risque de bundling (libs PDF lourdes sous PyInstaller) — décision au SP3/02 ;
  repli possible : MD seul + note pandoc (déjà documenté).
- **Qualité QCM** : risque produit (distracteurs faibles) — passe de validation au SP2/03.
- **Volume** : 9 supports × N chapitres × M langues = beaucoup d'appels LLM — la reprise
  coarse + l'estimation de coût + le plafond (à porter) atténuent.
- **CWD/threads UI** : le `PedagogyController` suit le pattern thread du
  `GenerationController` (worker `QThread`, `QtEventBus`).
