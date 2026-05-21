# Corrections post-livraison — Lot 1 (finitions + glossaire homogène + pédagogie multilingue)

- **Date** : 2026-05-21
- **Statut** : design validé (à implémenter directement sur `main`)
- **Origine** : retours d'usage après livraison du chantier « supports de révision ».

## 1. Contexte et triage des retours

Six retours d'usage ont été remontés, triés en sous-chantiers indépendants. Ce
document couvre le **Lot 1**, scindé en **1a / 1b / 1c**.

| # | Retour | Diagnostic | Lot |
|---|--------|-----------|-----|
| 1 | L'audio extrait est supprimé | `delete_audio_after_stt` existe (domaine/persistance/phase 0) mais codé en dur à `True` dans l'UI | **1a** |
| 2 | Onglets invisibles quand non sélectionnés | Aucune règle QSS `QTabBar`/`QTabWidget` dans `light_fluent.qss` | **1a** |
| 5 | Flashcards glossaire vides | La pédagogie lit le glossaire dans la table DB `glossary_terms`, **jamais peuplée** (anomalie : le pipeline lit le glossaire **sur disque**, cf. §3). Le même glossaire vide est injecté silencieusement dans les prompts LLM des autres supports | **1b** |
| 4 | Réglages pédagogie : seul FR proposé | Restriction trop forte : les supports LLM produisent dans `output_language_label` quelle que soit la langue du document source. Seul le choix de langue est bloqué à tort | **1c** |
| 3 | Dashboard pédagogie ≠ génération (tuiles/matrice) + coûts granulaires côté génération | Cohérence UI + design ouvert | différé (Lot 3) |
| 6 | Runs versionnés (sous-dossiers horodatés) + sélection de la source pédagogie | Refonte du modèle de fichiers/run | différé (Lot 2) |

**Décision produit (flashcards)** : `flashcards_glossary` (déterministe, sans LLM)
est le **glossaire reformaté en cartes** — valeur de transformation quasi nulle.
Il est **retiré** comme *support* ; le glossaire reste un **document de référence**
de la génération (`glossary.{lang}.md`), sans export Anki dédié. `flashcards_concepts`
(synthèse LLM) **reste** en pédagogie : matériel de révision, LLM, donc multilingue.

**Hors périmètre** : #3 et #6 (sous-chantiers dédiés, chacun son design → plan).

**Livraison** : trois lots livrés **séparément** (vérifs + commit par lot),
directement sur `main`. Ordre : **1a** (indépendant) ; **1b** (socle glossaire) ;
**1c** (pédagogie, s'appuie sur 1b).

## 2. Lot 1a — finitions UI

Aucun risque pipeline. Constantes centralisées, docstrings Google, tout en français.

### 2.1 #1 — Conserver les fichiers audio extraits

`GenerationSettings.delete_audio_after_stt` est déjà respecté par
`Phase0SttHandler`. Seul le contrôle UI manque (`dialogs/generation_settings_view.py`
construit le réglage avec `delete_audio_after_stt=True` en dur).

- **Ajout** : `QCheckBox` « **Conserver les fichiers audio extraits** » dans la page
  **Transcription** de `GenerationSettingsView`.
- **Mapping** : `delete_audio_after_stt = not checkbox.isChecked()`.
- **Défaut** : décochée → comportement actuel préservé (audio supprimé). Cocher
  conserve les `.wav`.
- **Édition** : à l'ouverture d'un projet existant, la case reflète l'état courant
  (`checked = not settings.delete_audio_after_stt`).
- **Libellé** : constante de module (`_KEEP_AUDIO_LABEL`).
- **Fichiers** : `src/fahmi2/ui/dialogs/generation_settings_view.py` ; test
  `tests/unit/ui/test_generation_settings_view.py` (la case pilote
  `delete_audio_after_stt` dans les deux sens).

### 2.2 #2 — Visibilité des onglets

`light_fluent.qss` ne style pas la barre d'onglets ; les onglets inactifs se
fondent dans le fond.

- **Ajout** : bloc QSS `QTabWidget::pane` + `QTabBar::tab` (normal : fond clair
  distinct + bordure ; `:selected` : fond blanc + accent `#0078d4` ; `:hover` :
  fond intermédiaire), cohérent avec la palette Fluent clair existante.
- Aucun code Python. Le `.qss` est déjà bundlé via le `.spec`.
- **Fichiers** : `src/fahmi2/ui/theme/light_fluent.qss`. Smoke tests d'onglets
  existants restent verts.

## 3. Lot 1b — glossaire homogène (lecture disque + retrait de l'anomalie DB)

### 3.1 Cause racine & intention initiale

Le **pipeline lit déjà le glossaire sur disque** :
`phase_3_reformulation` / `phase_4_structuration` appellent
`load_glossary_master(ctx.workspace)` (lecture de `glossary_master.json`) puis un
**retrieval TF-IDF**. C'est le pattern établi et fonctionnel.

La table SQLite `glossary_terms` + le service `GlossaryReconciler` étaient une
**intention initiale du socle** (store structuré requêtable) qui **n'a jamais été
branchée** : `import_master_payload` n'est appelé nulle part, le `GlossaryReconciler`
n'est instancié nulle part. `list_glossary_terms` n'est lu que par la pédagogie
(`SupportsOrchestrator._load_glossary`, sur une table **vide** → le bug). Les
utilités envisagées (requêtes SQL, éditeur de glossaire) ne sont pas réalisées et
sont exclues (R16 : curation = fichiers éditables, pas d'éditeur intégré). C'est du
**code mort vestigial**.

### 3.2 Solution : homogénéiser sur le disque

Aligner la pédagogie sur le pattern du pipeline (lecture du master disque) et
**supprimer l'anomalie DB**. Aucun document généré n'a de table de contenu en DB ;
le glossaire suit le même traitement (artefact disque + `PhaseExecution`).

- **Lecture disque en pédagogie** : ajouter `load_glossary` dans
  `pedagogy/sources.py` (à côté de `load_chapters`, déjà disque) qui lit
  `generation/glossary_master.json` et le parse en `tuple[Term, ...]`. Réutilise la
  logique de parsing existante (relocaliser `GlossaryReconciler._extract_terms` en
  fonction de module, ex. `parse_glossary_master_terms`).
- **Orchestrateur** : `SupportsOrchestrator._load_glossary` lit via ce helper disque
  au lieu de `self._state.list_glossary_terms(...)` (langue source du master ;
  cohérent avec ce qu'injecte déjà le pipeline). Plus de dépendance à `state` pour
  le glossaire.
- **Retrait de l'anomalie DB** :
  - `infra/storage/_schema.sql` : retirer la table `glossary_terms` ; soft-migration
    `DROP TABLE IF EXISTS glossary_terms` dans `_apply_soft_migrations` (idempotent) ;
    retirer les migrations de colonnes `glossary_terms` devenues sans objet.
  - `infra/storage/sqlite_state.py` : retirer `upsert_glossary_term` et
    `list_glossary_terms` (+ `_row_to_term` si inutilisé ailleurs).
  - `app/glossary_reconciler.py` : retirer la classe `GlossaryReconciler` (méthodes
    DB `import_master_payload` / `load_glossary` / `render_markdown`). **Conserver**
    `render_glossary_markdown_table` (utilisé par la phase 6) et exposer
    `parse_glossary_master_terms` (issu de `_extract_terms`).
- **Génération inchangée** : `glossary_master.json` et `glossary.{lang}.md` restent
  produits comme aujourd'hui (aucun refactor phase 6, aucun nouveau prompt).

### 3.3 Effet de bord positif

L'injection terminologique des prompts LLM de pédagogie (`format_glossary_terms`)
reçoit enfin des termes (le master disque, non vide) au lieu d'une liste vide.

### 3.4 Tests Lot 1b

- `pedagogy/sources` : `load_glossary` lit et parse `glossary_master.json` (termes,
  acronyme, définition) ; renvoie `()` si absent.
- `SupportsOrchestrator` : le glossaire injecté provient du disque (un master présent
  → termes non vides dans le contexte des générateurs).
- Suppression : retirer/adapter les tests de `upsert/list_glossary_terms`,
  `GlossaryReconciler` (DB) et de la migration `glossary_terms` ; conserver les tests
  de `render_glossary_markdown_table` et ajouter un test de `parse_glossary_master_terms`.
- Non-régression : `mypy`/`ruff`/`pytest` verts (la suppression ne doit pas laisser
  d'import mort).

## 4. Lot 1c — pédagogie multilingue (retrait `flashcards_glossary` + #4)

Prérequis : **Lot 1b** (`_load_glossary` lit le disque).

### 4.1 Retrait du support `flashcards_glossary`

- `domain/enums.py` : retirer `SupportType.FLASHCARDS_GLOSSARY` (8 supports restants).
- `pedagogy/generators/flashcards_glossary.py` : supprimer (+ test
  `tests/unit/pedagogy/test_flashcards_glossary.py`).
- `pedagogy/default_registry.py` : retirer l'enregistrement.
- `pedagogy/labels.py` et `ui/pedagogy_labels.py` (`SUPPORT_LABELS`) : retirer l'entrée.
- `infra/anki/genanki_exporter.py` (`_SUPPORT_LABELS`) : retirer l'entrée.
- `pedagogy/artifact_reader.py` (`_ITEM_DESERIALIZERS`) : retirer l'entrée
  `FLASHCARDS_GLOSSARY` (l'entrée `FLASHCARDS_CONCEPTS → Flashcard` reste).
- `domain/pedagogy.py` : retirer `FLASHCARDS_GLOSSARY` du défaut éventuel de
  `selected_supports` ; **désérialisation tolérante** : ignorer un type de support
  inconnu (réglages persistés contenant l'ancien type) plutôt que de lever.
- L'entité `Flashcard` **reste** (utilisée par `flashcards_concepts`). Le glossaire
  reste lu (1b) pour l'injection terminologique.

### 4.2 #4 — langues découplées

Les 8 supports sont LLM ; ils produisent dans `output_language_label`. La langue du
document source n'a pas à correspondre à la langue cible.

- `ui/pedagogy_controller.py` `_available_languages` → proposer **toutes** les
  langues supportées (`tuple(Language)`).
- `ui/dialogs/pedagogy_settings_view.py` : remplacer le libellé « langues issues de
  la génération » par : « *Les supports sont rédigés dans la langue choisie, même si
  le document source est dans une autre langue.* »
- `app/supports_orchestrator.py` :
  - **résoudre une langue de contenu** par langue cible : la langue cible si son
    `consolidated.{lang}.md` existe (meilleure fidélité, pas de re-traduction) ;
    sinon repli sur la **langue source** de la génération si produite ; sinon la
    première langue produite disponible (helper dédié `_resolve_content_language`) ;
  - charger `chapters` depuis la langue de contenu ; le `glossary` provient du master
    disque (1b) ; passer la **langue cible** aux générateurs (inchangés — ils
    reçoivent déjà `language`) ;
  - le `source_mtime` du manifeste suit le `consolidated.{content_lang}.md`
    réellement utilisé.
- Prérequis pédagogie inchangé : au moins un `consolidated.{lang}.md` doit exister.

### 4.3 Tests Lot 1c

- Suppression : tests référant `SupportType.FLASHCARDS_GLOSSARY` retirés/adaptés ;
  `build_default_support_registry` n'enregistre plus ce type ; désérialisation
  tolère l'ancien type.
- #4 : `test_pedagogy_controller.py` — `_available_languages` renvoie toutes les
  langues ; `test_supports_orchestrator.py` — pour une langue cible sans doc
  consolidé, chapitres/glossaire chargés depuis la langue de repli, générateurs
  reçoivent la langue cible, manifeste suit le doc de contenu.

## 5. Décisions verrouillées

- **Glossaire homogène = lecture disque** (`glossary_master.json`), **comme le
  pipeline** ; **suppression** de la table `glossary_terms` et du `GlossaryReconciler`
  (anomalie/code mort vestigial). Pas de persistance DB, pas de refactor phase 6, pas
  de nouveau prompt, pas d'export Anki du glossaire.
- **`flashcards_glossary` retiré** comme support (valeur quasi nulle) ; le glossaire
  reste un document de référence + source d'injection terminologique.
- **`flashcards_concepts` conservé** en pédagogie (LLM, multilingue).
- **#4 = langues découplées** : toutes les langues proposées ; orchestrateur découple
  langue-de-contenu / langue-cible.
- **#1 défaut = comportement actuel** (audio supprimé ; case pour conserver).
- **Découpage** : 1a → 1b → 1c, commits séparés sur `main`. **1b prérequis de 1c**.

## 6. Hors périmètre (différé, sous-chantiers dédiés)

- **#6 — workspaces versionnés par run** (sous-dossiers horodatés + sélection de la
  source pédagogie). Refonte du modèle de run/chemins/reprise → design propre (Lot 2).
  *Note* : résout aussi l'accès « par run » au glossaire côté disque (un master par run).
- **#3 — cohérence des dashboards** (tuiles + matrice pédagogie ; coûts granulaires
  côté génération) → design propre (Lot 3).

## 7. Vérifications

Chaque lot se termine **vert** : `pytest`, `ruff check .`, `mypy src tests`.
Documentation mise à jour par lot : `CHANGELOG` (Corrigé/Modifié/Supprimé), et le cas
échéant `docs/02` et `CLAUDE.md` (retrait de `flashcards_glossary` → 8 supports ;
glossaire lu sur disque ; suppression de la table `glossary_terms` /
`GlossaryReconciler`), `docs/04-parametrage.md` (case audio, note langues).
