# SP2 + SP3 — Avancement & reprise (générateur de supports de révision)

> **But de ce document** : permettre à **n'importe quelle session** de reprendre le
> travail sans perte de contexte. À lire **en premier** avant de coder.

## Branche & état

- **Branche de travail** : `feat/sp1-coquille-multi-fonctionnalites` (poussée sur
  `origin`). Tout le travail (SP1 + SP2 + SP3 complet : 01 → 03) y est commité.
- **Vérifs au vert** au dernier point : `pytest` (637), `ruff`, `mypy --strict`.

## Documents de référence (à lire avant d'agir)

1. **Chapeau (contrat + traçabilité)** :
   [`../specs/2026-05-20-supports-revision-vision-chapeau.md`](../specs/2026-05-20-supports-revision-vision-chapeau.md)
2. **Design détaillé SP2/SP3** *(architecture + décisions verrouillées)* :
   [`../specs/2026-05-20-sp2-sp3-supports-revision-design.md`](../specs/2026-05-20-sp2-sp3-supports-revision-design.md)
3. `CLAUDE.md` (conventions + directives systématiques + architecture à jour).

## Décisions verrouillées (ne pas re-litiger)

- **Orchestrateur dédié léger** (`SupportsOrchestrator`), **pas** le `PipelineEngine` :
  réutilise `LLMProvider` / `PromptLoader` / `EventBus` / `with_retry` / `FsArtifactStore`
  et un parseur JSON généralisé ; ne touche pas aux types frozen de la génération.
- **Persistance = fichiers** sous `<emplacement>/pedagogy/` (pas de DB) ; **génération
  idempotente** (écrase) + **manifeste** `pedagogy/manifest.json` (hash réglages + mtime
  du doc) pour l'indicateur de péremption.
- **Glossaire lu depuis la DB** (`list_glossary_terms` du dernier run COMPLETED), doc
  consolidé lu **sur disque** (`generation/output/consolidated.{lang}.md`, parsé en
  chapitres).
- **Réutiliser `PhaseConfig`** pour la config LLM pédagogie.
- **Build en tranches verticales** ; **les 9 supports** comme cible.
- **`genanki`** = dépendance SP3 (bundler dans le `.spec`). **Lib PDF** : à trancher au
  SP3/02 (repli MD seul + pandoc documenté).
- **Limite assumée** : la **qualité LLM** des supports n'est pas testable en CI
  (`FakeLLMProvider`) → itération produit post-livraison via l'éditeur de prompts.

## Fait ✅

- **SP1** (coquille multi-fonctionnalités) — plans 01–04, terminé. Matrice chapeau
  R1–R7 close.
- **SP2/01 — domaine & persistance** (commit `927b277`) : enums (`SupportType`×9,
  `TargetAudience`, `BloomObjective`, `SupportDensity`, `ExportFormat`),
  `domain/pedagogy.py` (`PedagogySettings` + constantes), `Project.pedagogy`,
  sérialisation blob v2 (clé `pedagogy`) + migration, fixture `make_pedagogy_settings`,
  tests. Plan : [`2026-05-20-sp2-01-domaine-pedagogie.md`](./2026-05-20-sp2-01-domaine-pedagogie.md).
- **SP2/02 — socle orchestrateur + tranche flashcards glossaire** : helpers LLM/JSON
  généralisés (`infra/llm/invocation.py`, `_base.py` délègue), `EventBus` rendu
  **générique** (`EventBus[E]`), package **`pedagogy/`** (parseur de chapitres, events,
  `SupportGenerator`/`SupportContext`, `SupportGeneratorRegistry`, manifeste de
  fraîcheur, `artifact_writer`, générateur **flashcards glossaire sans LLM**),
  `app/supports_orchestrator.py` (inputs par langue, boucle supports×langues, écriture
  JSON+MD, events, reprise coarse, pause/annulation), `domain/supports.py`
  (`Flashcard`/`SupportArtifact`), `ProjectService.get_last_completed_run`,
  `create_project(pedagogy=…)`, + **régression corrigée** (perte de `pedagogy` en fin
  de run de génération). Constantes de chemins centralisées (`GENERATION_OUTPUT_SUBDIR`,
  `consolidated_doc_filename`). Plan :
  [`2026-05-20-sp2-02-socle-orchestrateur-flashcards-glossaire.md`](./2026-05-20-sp2-02-socle-orchestrateur-flashcards-glossaire.md).
- **SP2/03 — générateurs LLM + prompts** : 8 entités de support (`QcmItem`,
  `TrueFalseItem`, `ClozeItem`, `OpenQuestion`, `RevisionSheet`, `KeyPoints`,
  `MockExam`/`MockExamSection`), socle `pedagogy/generators/_base.py`
  (`invoke_support_llm` avec retry + `SupportRetryAttempt`, helpers de parsing JSON
  typé, bases génériques par chapitre + mixin évaluatif), 8 générateurs (flashcards
  concepts, QCM + **dé-biaisage déterministe**, vrai/faux, cloze, questions ouvertes,
  fiche, points clés, examen blanc doc-entier) + 8 prompts `pedagogy_*.j2`
  **éditables** (`_TEMPLATE_METADATA`), **corrigés séparés** (`SupportArtifact.correction_markdown`
  + `<support>.corrige.md`), `default_classify` remonté dans `core/retry/classification.py`,
  factory `build_default_support_registry()`, tests (586 verts). Plan :
  [`2026-05-20-sp2-03-generateurs-llm-prompts.md`](./2026-05-20-sp2-03-generateurs-llm-prompts.md).
- **SP2/04 — onglet pédagogique réel** : helpers `pedagogy/sources.py` +
  heuristiques de coût partagées `app/_cost_common.py`, `PedagogyCostEstimator`,
  viewmodels `PedagogyProgressViewModel` (accumulation d'events) +
  `PedagogyStateViewModel` (fraîcheur : non configuré / génération requise / prêt /
  à jour / périmé), `PedagogySettingsView` (master-detail Supports/Difficulté/Langues/
  Modèle & coût), `PedagogyProgressView` (bandeau + table), `PedagogyController` +
  `PedagogyQtEventBus` (worker `QThread`, pause/cancel), `PedagogyTab` réel + câblage
  `app_main` (registre des 9 générateurs), plafond de coût dans l'orchestrateur, +
  fix régression `_edit_project` (préserver `pedagogy`), tests (615 verts). Plan :
  [`2026-05-20-sp2-04-onglet-pedagogique.md`](./2026-05-20-sp2-04-onglet-pedagogique.md).
- **SP3/01 — export Anki `.apkg`** : dépendance `genanki`, `pedagogy/artifact_reader.py`
  (désérialise Flashcard/ClozeItem/QcmItem), adapter `infra/anki/genanki_exporter.py`
  (note types Basic/Cloze/QCM, GUID stables via `guid_for`, sous-decks par support, tags
  support/langue/niveau/chapitre), service `app/pedagogy_export.py` (scan `pedagogy/`),
  bouton **Exporter** (`ProjectHeaderBar.show_export` + `export_requested`) + action
  `PedagogyController.export_apkg`, tests (628 verts). Plan :
  [`2026-05-20-sp3-01-export-apkg.md`](./2026-05-20-sp3-01-export-apkg.md).
- **SP3/02 — export Markdown / PDF** : dépendances `markdown` + `fpdf2`, adapter
  `infra/export/markdown_pdf.py` (assemblage + rendu PDF via `markdown`→HTML→`fpdf2`,
  police Unicode système Windows Arial), service `app/pedagogy_export.py` étendu
  (`export_pedagogy_to_markdown`/`_pdf`, sujet/corrigé séparés par langue), sélecteur de
  format (`QInputDialog`) + `PedagogyController.export_markdown`/`export_pdf`. **Réutilise
  les `.md` rendus** (pas d'extension d'`artifact_reader` — DRY/SoC). Tests (637 verts ;
  tests PDF *skippés* hors Windows). Plan :
  [`2026-05-20-sp3-02-export-markdown-pdf.md`](./2026-05-20-sp3-02-export-markdown-pdf.md).
- **SP3/03 — docs finales & clôture** : alignement de toute la documentation sur l'état
  réel du code — `docs/02` (couche `pedagogy/`, `infra/anki`+`infra/export`, app/ui
  pédagogie, métriques 637 tests / 272 fichiers, renvoi packaging), `CLAUDE.md` (package
  `pedagogy/`, mécanisme « Supports pédagogiques », note bundling), `docs/07` (section
  « Générer des supports de révision » + exports Anki/MD/PDF, retrait des « à venir »),
  `packaging/README.md` (sous-section dépendances genanki/markdown/fpdf2 + police Arial),
  **clôture de la matrice chapeau** (R8–R19 ; R13 honnêtement *partiel* — sélection de
  chapitres hors v1). Lot **documentaire** (aucun code modifié, 637 verts inchangés). Plan :
  [`2026-05-20-sp3-03-docs-finales.md`](./2026-05-20-sp3-03-docs-finales.md).

## Reste à faire (ordre) ⏭️

**Aucun — chantier « supports de révision » terminé.** SP1 + SP2 + SP3 livrés, matrice
chapeau close (R1–R19), branche prête pour `finishing-a-development-branch`.

> Rappel build : au prochain build du `.zip` portable, bundler dans `packaging/fahmi2.spec`
> (gitignored) `genanki` (`--collect-data`), `markdown`, `fpdf2` (+ `Pillow`, `fontTools`,
> `defusedxml`) — cf. [`../../../packaging/README.md`](../../../packaging/README.md).

## Procédure de reprise (chaque lot)

1. `git checkout feat/sp1-coquille-multi-fonctionnalites` (et `git pull`).
2. Lire ce document + le **design SP2/SP3** + `CLAUDE.md`, et `git log --oneline -10`
   pour l'état réel.
3. **Rédiger le plan détaillé** du lot (ex. `2026-05-20-sp2-02-*.md`) **contre le code
   à jour** (relire les fichiers concernés avant), le committer.
4. **Exécuter en TDD**, puis **passes qualité obligatoires** : `.venv\Scripts\python.exe
   -m pytest` / `ruff check .` / `mypy src tests` — **tout vert** avant de committer.
5. Committer le lot ; mettre à jour la section « Fait / Reste » de **ce document**.
6. Au tout dernier lot : `superpowers:finishing-a-development-branch`.

> Exécution **inline, sans subagents** (préférence projet). Directives systématiques :
> cf. `CLAUDE.md` (constantes, docstrings Google, DRY/YAGNI/KISS/SRP, conformité aux
> patterns existants, mise à jour des docs).
