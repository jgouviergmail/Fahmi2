# SP3 · Plan 03 — Docs finales & clôture du chantier

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (inline, sans subagents).
> **Avancement** : [`./2026-05-20-sp2-sp3-00-avancement.md`](./2026-05-20-sp2-sp3-00-avancement.md).
> Lot **documentaire** : aucune modification de code applicatif. Steps en checkbox.

**Goal:** Clôturer le chantier « supports de révision » : aligner toute la
documentation (`docs/`, `README`, `CLAUDE.md`, `packaging/README`) sur l'état réel du
code (packages `pedagogy/`, `infra/anki`, `infra/export`), **clôturer la matrice
chapeau** (R8–R19), documenter le **bundling** des nouvelles dépendances, puis terminer
la branche.

**Architecture:** Aucune. Mise à jour de docs uniquement. Les vérifs (`pytest`/`ruff`/
`mypy`) doivent rester vertes (les docs ne touchent pas le code).

**Rappels directives :** exactitude (la doc doit refléter le code), exhaustivité (aucune
exigence du chapeau silencieusement abandonnée → R13 « sélection de chapitres » non
retenue en v1 doit être **explicitée**, pas masquée). **Tout en français** (accents).

---

## Task 1 : Clôturer la matrice chapeau (R8–R19)

**Files:** Modify `docs/superpowers/specs/2026-05-20-supports-revision-vision-chapeau.md`

- [ ] Mettre à jour la colonne **Statut** :
  - R8 → Fait (SP2/04) ; R9 → Fait (SP2/02–03) ; R10 → Fait (SP2/03) ;
    R11 → Fait (SP2/03–04) ; R12 → Fait (SP2/04) ; R14 → Fait (SP2/03–04) ;
    R15 → Fait (SP2/02 + SP2/04) ; R16 → Fait (SP2 : artefacts `.md`/`.json` éditables) ;
    R17 → Fait (SP3/01) ; R18 → Fait (SP3/02) ; R19 → Fait (SP2/02 manifeste + SP2/04 bandeau).
  - **R13** → **Partiel (v1)** : « tout le document, par chapitre » **Fait** ; la
    **sélection d'un sous-ensemble de chapitres** n'a **pas** été retenue en v1 (absente
    de `PedagogySettings`). À expliciter dans le statut (honnêteté de traçabilité).
- [ ] Ajouter une note de clôture (orientation technique SP2 §5 : piste **(b) orchestrateur
  dédié léger** retenue et verrouillée par le design — ≠ favorite (a) du chapeau).

---

## Task 2 : `docs/02-presentation-technique.md` (architecture)

- [ ] §2 : insérer une sous-section **`### 2.4 Couche pedagogy`** (moteur de génération
  des supports : `SupportGenerator`/`SupportContext`, `SupportGeneratorRegistry` +
  `build_default_support_registry`, `chapters`, `sources`, `events`, `manifest`,
  `artifact_writer`/`artifact_reader`, `generators/` [base per-chapitre + mixin évaluatif
  + 9 générateurs], `labels`) ; **renuméroter** infra→2.5, app→2.6, ui→2.7.
- [ ] §2.5 `infra` : ajouter `infra/anki/genanki_exporter.py` et `infra/export/markdown_pdf.py` ;
  préciser « 8 + 8 templates » (génération + pédagogie).
- [ ] §2.6 `app` : ajouter `SupportsOrchestrator`, `PedagogyCostEstimator`,
  `pedagogy_export` (Anki/MD/PDF), `_cost_common`.
- [ ] §2.7 `ui` : `PedagogyTab` (réel), `PedagogyController` (+ `PedagogyQtEventBus`),
  viewmodels (`PedagogyProgressViewModel`, `PedagogyStateViewModel`), `PedagogySettingsView`,
  `PedagogyProgressView`, `pedagogy_labels` ; bouton **Exporter** de `ProjectHeaderBar`.
- [ ] §2.2 `domain` : enums pédagogie (`SupportType`×9, `TargetAudience`, `BloomObjective`,
  `SupportDensity`, `ExportFormat`), `PedagogySettings`, entités de support, blob v2.
- [ ] §6.2 métriques : compteur de tests à jour (≈ 637) ; §7 packaging : renvoyer vers
  `packaging/README.md` pour les deps supports.

---

## Task 3 : `CLAUDE.md` (guide dev)

- [ ] Section **Architecture en couches** : ajouter le package **`pedagogy/`** (calqué sur
  `pipeline/`) ; compléter `infra/` (`anki/`, `export/`), `app/` (`SupportsOrchestrator`,
  `PedagogyCostEstimator`, `pedagogy_export`), `ui/` (`PedagogyController`/`PedagogyTab`,
  viewmodels/dialogs pédagogie).
- [ ] **Mécanismes transverses** : ajouter une entrée « Supports pédagogiques » (orchestrateur
  dédié léger, manifeste de fraîcheur, prompts `pedagogy_*.j2` éditables, exports Anki/MD/PDF).
- [ ] Note **packaging** : nouvelles deps (`genanki`, `markdown`, `fpdf2`) à bundler — cf.
  `packaging/README.md` (genanki = `--collect-data`).

---

## Task 4 : `docs/07-guide-utilisateur.md` (guide utilisateur)

- [ ] §5 : remplacer « **Supports pédagogiques** (à venir) » par la description réelle.
- [ ] Ajouter une section **« Générer des supports de révision »** : sélection projet →
  onglet Supports pédagogiques → ⚙ Réglages (supports/difficulté/langues/modèle & coût) →
  Estimer / Générer (progression, bandeau d'état) → **Exporter** (Anki / Markdown / PDF).
  Prérequis : avoir lancé la Génération (document consolidé + glossaire).
- [ ] §10 Astuces : mention de l'édition des prompts `pedagogy_*` (déjà couverte par
  « Personnaliser les prompts »).

---

## Task 5 : `packaging/README.md` (bundling) + `README.md`

- [ ] `packaging/README.md` : nouvelle sous-section **« Dépendances supports pédagogiques »** :
  - **genanki** : embarque des données (`apkg_schema.sql`, `apkg_col.anki2`) → bundler via
    `--collect-data genanki` (ou `collect_data_files('genanki')` dans le `.spec`).
  - **markdown**, **fpdf2** (+ `Pillow`, `fontTools`, `defusedxml`) : modules purs collectés
    par PyInstaller ; ajouter en `hiddenimports` si l'analyse les manque.
  - **PDF** : police **Arial système Windows** (aucune police à bundler).
- [ ] `README.md` : vérifier la mention export (Anki/MD/PDF) + compteur de tests (déjà à jour).

---

## Task 6 : Vérifs + avancement + commit + clôture de branche

- [ ] **Step 1** : `pytest -q` / `ruff check .` / `mypy src tests` → tous verts (non-régression).
- [ ] **Step 2** : avancement : SP3/02 + docs finales → Fait ; « Reste à faire » vidé.
  Vérifier qu'aucun « à venir / stub / bientôt » pédagogie ne subsiste dans `docs/`/`README`.
- [ ] **Step 3** : commit `docs(pedagogy): finalisation docs + cloture matrice chapeau (SP3 final)`.
- [ ] **Step 4** : **superpowers:finishing-a-development-branch** (présenter les options
  d'intégration : merge / PR / cleanup).

---

## Self-review

Couvre : clôture R8–R19 (avec R13 honnêtement *partiel*), architecture (docs/02 + CLAUDE.md),
guide utilisateur, bundling (packaging/README), README. Aucune exigence du chapeau
silencieusement abandonnée. Aucune modification de code → vérifs inchangées.
