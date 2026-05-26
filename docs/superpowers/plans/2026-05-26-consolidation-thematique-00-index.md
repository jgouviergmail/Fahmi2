# Mode de consolidation « Refonte thématique » — plan d'implémentation (index)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans
> (exécution inline, choix de l'utilisateur — cf. mémoire `feedback-execution-inline-no-subagents`)
> pour implémenter ce plan tâche par tâche. Les étapes utilisent la syntaxe
> case à cocher (`- [ ]`).

**Goal :** Ajouter à la phase 5 (consolidation) un mode **`THEMATIC`** où le LLM
agrège/agence/structure transversalement le contenu de tous les entrants (modèle
journaliste, rigueur sur le fond / souplesse sur la forme), à côté du mode
**`ORDERED`** actuel conservé par défaut.

**Architecture :** Phase 5 transformée en **dispatcher de stratégies**
(`ConsolidationStrategy` ABC). `ORDERED` = comportement actuel inchangé.
`THEMATIC` = **map-reduce à provenance** : relevé factuel par source (T1, ids
traçables + extraits verbatim) → plan thématique (T2, co-localise les conflits) →
rédaction par chapitre (T3, parallélisée) → méta + assemblage déterministe (T4).
**Double contrôle déterministe de couverture** sur les ids (au lieu d'une passe de
vérification LLM). Artefacts conservés et servant de **checkpoint intra-phase**.

**Tech Stack :** Python 3.12, DeepSeek (`LLMProvider`), Jinja2 (prompts),
`core/concurrency.map_bounded` (parallélisme borné), `FsArtifactStore` (écritures
atomiques JSON/texte), SQLite (état, inchangé), PySide6 (UI), pytest + ruff +
mypy --strict.

**Spec :** [`docs/superpowers/specs/2026-05-26-modes-consolidation-thematique-design.md`](../specs/2026-05-26-modes-consolidation-thematique-design.md)

---

## Principe directeur (rappel)

- **Fond (rigueur)** : interdiction d'inventer/ajouter ; préserver tous faits,
  chiffres, données, raisonnements. Couverture garantie par circulation d'ids.
- **Forme (souplesse)** : le LLM décide la structure, reformule, fusionne,
  déduplique, rédige les transitions.
- **Conflits** : présentés par source, **sans arbitrage**.

## Structure de fichiers (créés / modifiés)

**Domaine & persistance**
- `src/fahmi2/domain/enums.py` *(modif)* — `ConsolidationMode`.
- `src/fahmi2/domain/generation.py` *(modif)* — champ `consolidation_mode` + constantes.
- `src/fahmi2/infra/storage/sqlite_state.py` *(modif)* — (dé)sérialisation lenient.

**Moteur de consolidation**
- `src/fahmi2/pipeline/handlers/_consolidation/__init__.py` *(créé)*.
- `src/fahmi2/pipeline/handlers/_consolidation/_base.py` *(créé)* — `ConsolidationResult`,
  `ConsolidationStrategy` (ABC), helpers déterministes partagés (déplacés de phase 5).
- `src/fahmi2/pipeline/handlers/_consolidation/ordered.py` *(créé)* — stratégie actuelle.
- `src/fahmi2/pipeline/handlers/_consolidation/thematic.py` *(créé)* — nouvelle stratégie.
- `src/fahmi2/pipeline/handlers/phase_5_consolidation.py` *(réécrit)* — dispatcher (+ ré-exports de compat).

**Prompts**
- `src/fahmi2/infra/prompts/defaults/phase_5_fact_ledger.j2` *(créé)* — T1.
- `src/fahmi2/infra/prompts/defaults/phase_5_thematic_plan.j2` *(créé)* — T2.
- `src/fahmi2/infra/prompts/defaults/phase_5_thematic_chapter.j2` *(créé)* — T3.
- `src/fahmi2/app/prompts_service.py` *(modif)* — catalogue (3 entrées).

**Coût & UI**
- `src/fahmi2/app/cost_estimator.py` *(modif)* — paramètre `consolidation_mode` + facteurs.
- `src/fahmi2/ui/generation_controller.py` *(modif)* — passe le mode à l'estimateur.
- `src/fahmi2/ui/dialogs/generation_settings_view.py` *(modif)* — sélecteur de mode.
- `src/fahmi2/ui/widgets/source_order_view.py` *(modif)* — note « ordre sans effet ».

**Tests** — un fichier de test par zone (cf. lots).

**Docs** — `CLAUDE.md`, `README.md`, mise à jour du backlog
`docs/superpowers/specs/2026-05-22-modes-consolidation-backlog.md`.

## Lots (ordre d'exécution)

| Lot | Fichier plan | Contenu | Dépend de |
|----|----|----|----|
| 1 | [`...-01-fondations.md`](2026-05-26-consolidation-thematique-01-fondations.md) | Enum `ConsolidationMode`, champ settings, (dé)sérialisation lenient | — |
| 2 | [`...-02-dispatcher.md`](2026-05-26-consolidation-thematique-02-dispatcher.md) | Package `_consolidation/`, ABC + `_base`, stratégie `ORDERED`, phase 5 = dispatcher (**non-régression**) | 1 |
| 3 | [`...-03-prompts.md`](2026-05-26-consolidation-thematique-03-prompts.md) | 3 templates `.j2` + catalogue `PromptsService` | — (parallélisable avec 1/2) |
| 4 | [`...-04-thematique.md`](2026-05-26-consolidation-thematique-04-thematique.md) | Stratégie `THEMATIC` (T1→T4), contrôles de couverture, conflits, checkpoint | 2, 3 |
| 5 | [`...-05-cout.md`](2026-05-26-consolidation-thematique-05-cout.md) | `CostEstimator` par mode + branchement contrôleur | 1 |
| 6 | [`...-06-ui.md`](2026-05-26-consolidation-thematique-06-ui.md) | Sélecteur de mode + note d'ordre | 1 |
| 7 | [`...-07-aval-docs.md`](2026-05-26-consolidation-thematique-07-aval-docs.md) | Non-régression phases 6/7 + documentation | 4 |

## Conventions de test (lever l'ambiguïté des `...`)

Quand un step de test affiche `...` pour la **mise en place** (construction d'un
`PhaseContext`, `FakeLLMProvider` séquentiel, écriture des `structured/*.md`), il
faut **recopier verbatim le montage** déjà présent dans
`tests/unit/pipeline/handlers/test_phase_5_consolidation.py` (helpers
`build_phase_context` de `tests/unit/pipeline/handlers/_helpers.py`,
`_write_structured`, `_sequential_responses`). Seules les **assertions** (le cœur du
test) sont données en entier dans le plan. Aucun comportement n'est laissé « à
déterminer » : la logique testée est toujours explicite.

## Vérifications de fin (à chaque lot ET en clôture)

```powershell
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m mypy src tests
```

Les trois doivent être **verts** (cf. CLAUDE.md). Repasser jusqu'à zéro défaut.

## Auto-revue (couverture spec → lots)

- Spec §2.1 (enum + champ + migration) → **Lot 1**.
- Spec §2.2 (dispatcher + `_base` + `ordered`) → **Lot 2**.
- Spec §3.1–3.4 (T1→T4, ids, artefacts, conflits) → **Lot 4**.
- Spec §3.3 (glossaire non injecté) → **Lot 4** (décision intégrée au prompt T3).
- Spec §4 (garanties de fidélité) → **Lot 4** (tests des 2 contrôles + verbatim).
- Spec §5 (checkpoint intra-phase) → **Lot 4** (hash de cohérence).
- Spec §6 (coût par mode ; pas d'enforcement runtime) → **Lot 5**.
- Spec §7 (aval 6/7 inchangé) → **Lot 7** (test de non-régression).
- Spec §8 (UI) → **Lot 6**.
- Spec §9 (prompts + catalogue) → **Lot 3**.
- Spec §10 (constantes centralisées) → transverse, vérifié à chaque lot.
- Spec §11 (tests) → réparti sur tous les lots.
