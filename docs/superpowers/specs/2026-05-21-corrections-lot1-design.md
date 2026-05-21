# Corrections post-livraison — Lot 1 (finitions + glossaire en DB + pédagogie multilingue)

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
| 5 | Flashcards glossaire vides | La table `glossary_terms` n'est **jamais peuplée** (le pipeline n'écrit le glossaire que sur disque) → `list_glossary_terms` renvoie `[]`. Le même glossaire vide est injecté (silencieusement) dans les prompts LLM des autres supports | **1b** |
| 4 | Réglages pédagogie : seul FR proposé | Restriction trop forte : les supports LLM produisent dans `output_language_label` quelle que soit la langue du document source. Seul le choix de langue est bloqué à tort | **1c** |
| 3 | Dashboard pédagogie ≠ génération (tuiles/matrice) + coûts granulaires côté génération | Cohérence UI + design ouvert | différé (Lot 3) |
| 6 | Runs versionnés (sous-dossiers horodatés) + sélection de la source pédagogie | Refonte du modèle de fichiers/run | différé (Lot 2) |

**Décision produit (flashcards)** : `flashcards_glossary` (déterministe, sans LLM)
est le **glossaire reformaté en cartes** — valeur de transformation quasi nulle.
Il est **retiré** comme *support* ; les cartes de vocabulaire deviennent une
**option d'export Anki** du glossaire (cf. §4.3). `flashcards_concepts` (synthèse
LLM) **reste** en pédagogie : c'est du matériel de révision, LLM, donc multilingue.

**Hors périmètre** : #3 et #6 (sous-chantiers dédiés, chacun son design → plan).

**Livraison** : trois lots livrés **séparément** (vérifs + commit par lot),
directement sur `main`. Ordre : **1a** (indépendant) ; **1b** (pipeline, prérequis
de 1c) ; **1c** (pédagogie).

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

## 3. Lot 1b — glossaire en DB (phase 6 *structured-first*)

### 3.1 Cause racine

`SqliteState.upsert_glossary_term` n'est appelé que par
`GlossaryReconciler.import_master_payload`, **jamais invoqué** dans le pipeline
réel. Le glossaire structuré n'existe que dans `generation/glossary_master.json`
(langue source) ; la phase 6 ne produit, par langue, qu'un `glossary.{lang}.md`
**rendu** (blob traduit par LLM pour les langues non-source). La table
`glossary_terms` reste vide → toute lecture (`list_glossary_terms`) renvoie `()`.

### 3.2 Solution : phase 6 *structured-first* + persistance DB

La DB redevient la **source de vérité** du glossaire (homogène avec le reste de
l'état run-scopé ; supprime le code mort `GlossaryReconciler`/table). `PhaseContext`
expose déjà `state: SqliteState` et `run` → persistance **dans le handler**.

Pour chaque langue de `settings.output_languages`, la phase 6 :

1. **Construit des termes structurés** (`domain.glossary.Term`) :
   - langue **source** → termes du `glossary_master.json` tels quels ;
   - langue **non-source** → traduction de la partie structurée via le **nouveau
     prompt dédié** (§3.3) : on traduit la **définition** (et le nom de terme si
     absent de `cross_lang`) ; on **conserve** `acronym` et `acronym_expansion`
     dans leur langue d'origine (invariant glossaire existant), ainsi que
     `sources`/`aliases`/`cross_lang`.
2. **Persiste** chaque terme : `ctx.state.upsert_glossary_term(ctx.run.id, language, term)`.
3. **Rend** `glossary.{lang}.md` **depuis** ces termes structurés via
   `render_glossary_markdown_table` (réutilisé), au lieu de traduire le blob
   Markdown du glossaire.

Per-video et consolidated restent traduits comme aujourd'hui (inchangés).

### 3.3 Nouveau prompt dédié

- **Fichier** : `src/fahmi2/infra/prompts/defaults/phase_6_glossary_translation.j2`.
- **Contrat** : reçoit la liste structurée des termes (`term`, `definition`,
  `acronym`, `acronym_expansion`, `cross_lang`) + libellés source/cible ;
  **retourne du JSON** `{"terms": [{term, definition}, ...]}` (uniquement ce qui
  doit être traduit ; consigne explicite de **ne pas** traduire
  `acronym`/`acronym_expansion`). Parsing JSON typé côté handler
  (réutilise `parse_json_response`).
- **Éditable** : nouvelle entrée dans `PromptsService._TEMPLATE_METADATA`
  (`phase_6_glossary_translation`, display « Phase 6 — Traduction du glossaire »).
  Catalogue → **9 templates génération + 8 `pedagogy_*`** (les supports passent à 8,
  mais `flashcards_glossary` n'avait **pas** de prompt → le compte pédagogie est
  inchangé).

### 3.4 Reprise / idempotence

`upsert_glossary_term` fait un `ON CONFLICT(run_id, language, term) DO UPDATE`
(idempotent). Phase 6 rejouée ou skippée sur reprise → état DB correct. La phase
reste persistée comme `PhaseExecution` par le moteur (inchangé).

### 3.5 Tests Lot 1b

- `tests/unit/pipeline/handlers/test_phase_6_translation.py` :
  - langue source → termes du master persistés en DB (vérifier `list_glossary_terms`) ;
    `glossary.fr.md` rendu depuis le structuré ;
  - langue non-source (FakeLLM renvoyant un JSON de termes traduits) → termes
    persistés ; `acronym_expansion` **inchangée** ; `glossary.en.md` rendu.
- `FakeLLMProvider` route une réponse pour `phase_6_glossary_translation` (clé par
  template), sans casser les tests de phase 6 existants.
- `tests/unit/infra/prompts/` : le template est chargeable et figure au catalogue.

## 4. Lot 1c — pédagogie multilingue (retrait `flashcards_glossary` + #4 + export glossaire)

Prérequis : **Lot 1b** (DB peuplée).

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
- L'entité `Flashcard` **reste** (utilisée par `flashcards_concepts`).

### 4.2 #4 — langues découplées

Les 8 supports sont LLM ; ils produisent dans `output_language_label`. La langue du
document source n'a pas à correspondre à la langue cible.

- `ui/pedagogy_controller.py` `_available_languages` → proposer **toutes** les
  langues supportées (`tuple(Language)`).
- `ui/dialogs/pedagogy_settings_view.py` : remplacer le libellé « langues issues de
  la génération » par une note : « *Les supports sont rédigés dans la langue choisie,
  même si le document source est dans une autre langue.* »
- `app/supports_orchestrator.py` :
  - **résoudre une langue de contenu** par langue cible : la langue cible si son
    `consolidated.{lang}.md` existe (meilleure fidélité, pas de re-traduction par le
    LLM) ; sinon repli sur la **langue source** de la génération si produite ; sinon
    la première langue produite disponible (helper dédié, ex. `_resolve_content_language`) ;
  - charger `chapters` depuis la langue de contenu ; charger le `glossary` (DB,
    désormais peuplée) pour la langue de contenu ; passer la **langue cible** aux
    générateurs (inchangés — ils reçoivent déjà `language`) ;
  - le `source_mtime` du manifeste suit le `consolidated.{content_lang}.md`
    réellement utilisé (fraîcheur correcte).
- Prérequis pédagogie inchangé : au moins un `consolidated.{lang}.md` doit exister
  (un run de génération COMPLETED).

### 4.3 Glossaire → export Anki

Remplace proprement le support retiré (aucune capacité perdue). Le glossaire étant
structuré en DB (Lot 1b), l'export lit la DB.

- `app/pedagogy_export.py` : l'export `.apkg` ajoute, pour chaque langue produite,
  un **sous-deck « Glossaire »** de cartes **Basic** (recto = terme + acronyme entre
  parenthèses si présent ; verso = définition), construites depuis
  `state.list_glossary_terms(run_id, language)` du dernier run COMPLETED.
- Réutilise le note type Basic et la convention de GUID/sous-decks/tags existante de
  `GenankiExporter` (tags : `glossaire` / langue). Pas de doublon au ré-import.
- L'export Markdown/PDF du glossaire n'est **pas** requis (le glossaire existe déjà
  comme `glossary.{lang}.md`).

### 4.4 Tests Lot 1c

- Suppression : les tests référant `SupportType.FLASHCARDS_GLOSSARY` sont retirés ou
  adaptés ; `build_default_support_registry` n'enregistre plus ce type ; la
  désérialisation tolère l'ancien type.
- #4 : `test_pedagogy_controller.py` — `_available_languages` renvoie toutes les
  langues ; `test_supports_orchestrator.py` — pour une langue cible sans doc
  consolidé, les chapitres/glossaire sont chargés depuis la langue de repli et les
  générateurs reçoivent la langue cible ; le manifeste suit le doc de contenu.
- Export glossaire : `test_pedagogy_export.py` / `test_genanki_exporter.py` — un
  sous-deck Glossaire est produit avec une carte Basic par terme du run.

## 5. Décisions verrouillées

- **Glossaire = DB, source de vérité** (homogénéité ; pas de lecture disque
  parallèle), via phase 6 *structured-first* + prompt dédié JSON→JSON éditable.
- **`flashcards_glossary` retiré** comme support (valeur quasi nulle) ; vocabulaire
  → **export Anki du glossaire** depuis la DB.
- **`flashcards_concepts` conservé** en pédagogie (LLM, multilingue).
- **#4 = langues découplées** : toutes les langues proposées ; orchestrateur
  découple langue-de-contenu / langue-cible.
- **#1 défaut = comportement actuel** (audio supprimé ; case pour conserver).
- **Découpage** : 1a → 1b → 1c, commits séparés sur `main`. **1b est prérequis de 1c**.

## 6. Hors périmètre (différé, sous-chantiers dédiés)

- **#6 — workspaces versionnés par run** (sous-dossiers horodatés + sélection de la
  source pédagogie). Refonte du modèle de run/chemins/reprise → design propre (Lot 2).
- **#3 — cohérence des dashboards** (tuiles + matrice pédagogie ; coûts granulaires
  côté génération) → design propre (Lot 3), possiblement informé par le Lot 2.

## 7. Vérifications

Chaque lot se termine **vert** : `pytest`, `ruff check .`, `mypy src tests`.
Documentation mise à jour par lot : `CHANGELOG` (Corrigé/Modifié/Ajouté), et le cas
échéant `docs/04-parametrage.md` (case audio, note langues), `docs/02` et `CLAUDE.md`
(retrait de `flashcards_glossary` → 8 supports ; nouveau prompt
`phase_6_glossary_translation` ; glossaire persisté en DB ; export Anki du glossaire).
