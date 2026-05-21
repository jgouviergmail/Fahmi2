# Corrections post-livraison — Lot 1 (finitions + glossaire en DB)

- **Date** : 2026-05-21
- **Statut** : design validé (à implémenter directement sur `main`)
- **Origine** : retours d'usage après livraison du chantier « supports de révision ».

## 1. Contexte et triage des retours

Six retours d'usage ont été remontés. Ils ont été triés en sous-chantiers
indépendants ; ce document couvre le **Lot 1** uniquement.

| # | Retour | Diagnostic | Lot |
|---|--------|-----------|-----|
| 1 | L'audio extrait est supprimé | `delete_audio_after_stt` existe (domaine/persistance/phase 0) mais codé en dur à `True` dans l'UI | **1a** |
| 2 | Onglets invisibles quand non sélectionnés | Aucune règle QSS `QTabBar`/`QTabWidget` dans `light_fluent.qss` | **1a** |
| 4 | Réglages pédagogie : seul FR proposé | **Comportement correct** (R12 : seules les langues produites par la génération sont proposées ; ici la génération n'a produit que FR). Clarification UX seulement | **1a** |
| 5 | Flashcards glossaire : documents vides | La table SQLite `glossary_terms` n'est **jamais peuplée** : le pipeline n'écrit le glossaire que sur disque. `list_glossary_terms` renvoie toujours `[]` | **1b** |
| 3 | Dashboard pédagogie ≠ génération (tuiles/matrice) + idée de coûts granulaires côté génération | Cohérence UI + design ouvert | différé (Lot 3) |
| 6 | Runs versionnés (sous-dossiers horodatés) + sélection de la source pour la pédagogie | Refonte du modèle de fichiers/run | différé (Lot 2) |

**Hors périmètre de ce document** : #3 et #6 (sous-chantiers dédiés, chacun avec
son propre design → plan).

**Livraison** : **Lot 1a** (finitions #1, #2, #4) et **Lot 1b** (glossaire en DB
#5) sont livrés **séparément** (deux passes de vérifs + deux commits), directement
sur `main`.

## 2. Lot 1a — finitions rapides

Aucun risque pipeline. Constantes centralisées (pas de magic string), docstrings
Google, tout en français.

### 2.1 #1 — Conserver les fichiers audio extraits

`GenerationSettings.delete_audio_after_stt` est déjà respecté par
`Phase0SttHandler` (suppression du `.wav` après STT si `True`). Seul le contrôle
UI manque : `dialogs/generation_settings_view.py` construit le réglage avec
`delete_audio_after_stt=True` en dur.

- **Ajout** : une `QCheckBox` « **Conserver les fichiers audio extraits** » dans
  la page **Transcription** de `GenerationSettingsView`.
- **Mapping** : `delete_audio_after_stt = not checkbox.isChecked()`.
- **Défaut** : décochée → `delete_audio_after_stt=True` = comportement actuel
  préservé. Cocher conserve les `.wav` (utile pour réécouter / déboguer la STT).
- **Édition** : à l'ouverture des réglages d'un projet existant, la case reflète
  l'état courant (`checked = not settings.delete_audio_after_stt`).
- **Libellé** : constante de module (ex. `_KEEP_AUDIO_LABEL`).

**Fichiers** : `src/fahmi2/ui/dialogs/generation_settings_view.py` ;
test `tests/unit/ui/test_generation_settings_view.py` (la case pilote bien
`delete_audio_after_stt`, dans les deux sens).

### 2.2 #2 — Visibilité des onglets

`light_fluent.qss` ne style pas la barre d'onglets ; les onglets inactifs se
fondent dans le fond.

- **Ajout** : un bloc QSS `QTabWidget::pane` + `QTabBar::tab` (état normal :
  fond clair distinct + bordure ; `:selected` : fond blanc + soulignement/bordure
  accent `#0078d4` + texte accentué ; `:hover` : fond intermédiaire). Cohérent
  avec la palette Fluent clair existante (surfaces blanches sur `#f5f7fb`).
- Aucun code Python. Le `.qss` est déjà bundlé via le `.spec`.

**Fichiers** : `src/fahmi2/ui/theme/light_fluent.qss`. (Pas de test unitaire QSS ;
les smoke tests d'onglets existants restent verts.)

### 2.3 #4 — Clarification des langues pédagogie

`PedagogyController._available_languages` propose les langues ayant un
`consolidated.{lang}.md` (R12). Comportement correct ; il manque seulement
l'explication côté UI.

- **Ajout** : un `QLabel` explicatif (texte grisé) en tête de la page **Langues**
  de `PedagogySettingsView` : « *Seules les langues produites par la génération
  sont proposées. Pour en ajouter, relancez une génération en cochant ces langues
  de sortie.* » Texte en constante de module.
- Aucune logique modifiée.

**Fichiers** : `src/fahmi2/ui/dialogs/pedagogy_settings_view.py` (méthode
`_build_languages_page`).

## 3. Lot 1b — glossaire persisté en DB (#5)

### 3.1 Cause racine

`SqliteState.upsert_glossary_term` n'est appelé que par
`GlossaryReconciler.import_master_payload`, lui-même **jamais invoqué** dans le
pipeline réel (seulement testé). Le glossaire structuré n'existe que dans
`workspace/generation/glossary_master.json` (langue **source**) ; la phase 6 ne
produit, par langue de sortie, qu'un `glossary.{lang}.md` **rendu** (pour les
langues non-source, le blob Markdown est traduit par LLM). La table
`glossary_terms` reste donc vide → `SupportsOrchestrator._load_glossary`
(`list_glossary_terms`) renvoie `()` → `FlashcardsGlossaryGenerator` rend
« _Aucun terme de glossaire disponible._ ».

### 3.2 Solution : phase 6 *structured-first* + persistance DB

On rend la production du glossaire de la phase 6 **structurée d'abord**, puis on
persiste en base (la table redevient la source de vérité, comme prévu à
l'origine). `PhaseContext` expose déjà `state: SqliteState` et `run` : la
persistance se fait **dans le handler**, sans changement d'architecture.

Pour chaque langue de `settings.output_languages`, la phase 6 :

1. **Construit des termes structurés** (`domain.glossary.Term`) :
   - langue **source** → termes du `glossary_master.json` tels quels ;
   - langue **non-source** → traduction de la **partie structurée** via un
     **nouveau prompt dédié** (cf. §3.3). On traduit la **définition** et, le cas
     échéant, le nom de terme via `cross_lang` ; on **conserve** l'`acronym` et
     l'`acronym_expansion` dans leur langue d'origine (invariant existant du
     glossaire), ainsi que `sources`/`aliases`.
2. **Persiste** chaque terme : `ctx.state.upsert_glossary_term(ctx.run.id, language, term)`.
3. **Rend** `glossary.{lang}.md` **à partir** de ces termes structurés via
   `render_glossary_markdown_table` (réutilisé), au lieu de traduire le blob
   Markdown. → suppression de la traduction du glossaire en tant que texte (DRY,
   plus robuste, langue garantie).

Les autres artefacts de la phase 6 (per-video, consolidated) sont **inchangés**
(toujours traduits comme aujourd'hui).

### 3.3 Nouveau prompt dédié

- **Fichier** : `src/fahmi2/infra/prompts/defaults/phase_6_glossary_translation.j2`.
- **Contrat** : reçoit la liste structurée des termes (JSON : `term`,
  `definition`, `acronym`, `acronym_expansion`, `cross_lang`) + libellés
  source/cible ; **retourne du JSON** `{"terms": [{term, definition}, ...]}` (on
  ne demande au LLM que ce qui doit être traduit : nom de terme — si non couvert
  par `cross_lang` — et définition ; consigne explicite de **ne pas** traduire
  `acronym`/`acronym_expansion`). Parsing JSON typé côté handler
  (réutilise `parse_json_response`).
- **Éditable** : enregistré dans `PromptsService._TEMPLATE_METADATA` (nouvelle
  entrée `phase_6_glossary_translation`, display name « Phase 6 — Traduction du
  glossaire »), donc modifiable via *Édition → Modifier les prompts…* comme tous
  les autres (le catalogue passe à 9 templates génération + 8 `pedagogy_*`).

### 3.4 Reprise / idempotence

`upsert_glossary_term` fait un `ON CONFLICT(run_id, language, term) DO UPDATE`
(idempotent). Si la phase 6 est **rejouée** ou **skippée** sur reprise, l'état DB
reste correct (réécriture des mêmes termes, ou conservation des termes déjà
persistés au run précédent). La phase 6 reste persistée comme `PhaseExecution`
via le moteur (inchangé).

### 3.5 Pédagogie : aucun changement

`SupportsOrchestrator._load_glossary` lit déjà la DB
(`list_glossary_terms(run.id, language)`). Une fois la table peuplée, les
flashcards de glossaire sont **non vides** dans **toutes** les langues
effectivement produites par la génération.

### 3.6 Tests Lot 1b

- **Phase 6** (`tests/unit/pipeline/handlers/test_phase_6_translation.py`) :
  - langue source → termes du master persistés en DB (vérifier
    `list_glossary_terms`) ; `glossary.fr.md` rendu depuis le structuré ;
  - langue non-source (FakeLLM renvoyant un JSON de termes traduits) → termes
    traduits persistés ; `acronym_expansion` inchangée ; `glossary.en.md` rendu.
- **Bout en bout pédagogie** : `FlashcardsGlossaryGenerator` via l'orchestrateur
  produit des cartes non vides quand la DB est peuplée (test d'intégration léger
  `tests/unit/app/test_supports_orchestrator.py` ou pédagogie).
- **Prompt** : `tests/unit/infra/prompts/` — le template
  `phase_6_glossary_translation` est chargeable et figure au catalogue.
- Le `FakeLLMProvider` doit pouvoir router une réponse pour ce nouveau prompt
  (clé par template), sans casser les tests de phase 6 existants.

## 4. Décisions verrouillées

- **Persistance #5 = DB pendant le pipeline** (≠ lecture disque), via une phase 6
  *structured-first* ; honore le design d'origine (`glossary_terms` source de
  vérité).
- **Traduction du glossaire = nouveau prompt dédié JSON→JSON** éditable, distinct
  de `phase_6_translation` (qui reste pour per-video/consolidated).
- **Découpage** : Lot 1a (#1, #2, #4) puis Lot 1b (#5), commits séparés sur `main`.
- **#4 = aucun changement de logique** (clarification UX uniquement).
- **#1 défaut = comportement actuel** (audio supprimé ; case pour conserver).

## 5. Hors périmètre (différé, sous-chantiers dédiés)

- **#6 — workspaces versionnés par run** (sous-dossiers horodatés génération &
  pédagogie + sélection de la source pour la pédagogie). Refonte du modèle de
  run/chemins/reprise → design propre (Lot 2).
- **#3 — cohérence des dashboards** (tuiles + matrice côté pédagogie ; intégration
  des coûts granulaires côté génération) → design propre (Lot 3), possiblement
  informé par le Lot 2.

## 6. Vérifications

Chaque lot se termine **vert** : `pytest`, `ruff check .`, `mypy src tests`.
Documentation mise à jour si nécessaire (CHANGELOG : entrées « Corrigé » pour #1,
#2, #5 et « Modifié »/« Ajouté » pour le nouveau prompt et la case audio ; le cas
échéant `docs/04-parametrage.md` pour la case audio et la note langues).
