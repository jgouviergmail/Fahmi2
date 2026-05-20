# SP2 + SP3 — Avancement & reprise (générateur de supports de révision)

> **But de ce document** : permettre à **n'importe quelle session** de reprendre le
> travail sans perte de contexte. À lire **en premier** avant de coder.

## Branche & état

- **Branche de travail** : `feat/sp1-coquille-multi-fonctionnalites` (poussée sur
  `origin`). Tout le travail (SP1 + SP2) y est commité.
- **Vérifs au vert** au dernier point : `pytest` (508), `ruff`, `mypy --strict`.

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

## Reste à faire (ordre) ⏭️

| Lot | Contenu | Réf design |
|-----|---------|-----------|
| **SP2/02** | Socle orchestrateur + **tranche verticale flashcards glossaire** (sans LLM) : généraliser helpers LLM/JSON, `SupportGenerator`/registre, `SupportContext`, `SupportsOrchestrator`, parseur de chapitres + lecture glossaire DB, générateur flashcards glossaire → JSON+MD, events, manifeste, tests. | §5, §6 |
| **SP2/03** | **8 générateurs LLM** (flashcards concepts, QCM + validation, vrai/faux, cloze, questions ouvertes, fiche, points clés, examen blanc) + **8 prompts** `pedagogy_*.j2` + parsing typé + corrigés séparés, tests. | §6, §7 |
| **SP2/04** | **Onglet pédagogique réel** : `PedagogyController` + `PedagogyTab` (réglages master-detail : Supports/Difficulté/Langues/Modèle ; bouton Générer/Estimer ; progression ; fraîcheur), `PedagogyCostEstimator`, câblage `app_main`, smoke tests. | §8, §10 |
| **SP3/01** | Export **`.apkg`** (genanki) : note types (Basic/Cloze/QCM), GUID stables, sous-decks, tags, bouton export, tests. | §9 |
| **SP3/02** | Export **Markdown/PDF** (sujet/corrigé séparés ; choix lib PDF), tests. | §9 |
| **Docs finales** | `docs/`, `README`, `CLAUDE.md`, `CHANGELOG` ; clôture matrice chapeau (R8–R19 → Fait). | — |

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
