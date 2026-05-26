# Lot 7 — Non-régression aval (phases 6/7) + documentation

> Sous-skill d'exécution : superpowers:executing-plans. Étapes en `- [ ]`.
> **Dépend de** : Lot 4.

**But du lot :** Prouver que les phases 6 (traduction) et 7 (cohérence) traitent un
consolidé **thématique** sans hypothèse cassée, et documenter la fonctionnalité.

---

### Task 7.1 : Test de non-régression phases 6/7 sur un consolidé thématique

**Files:**
- Test: `tests/unit/pipeline/handlers/test_downstream_thematic.py`

- [ ] **Step 1 : Écrire le test**

Le consolidé thématique a des chapitres qui **ne correspondent pas aux sources**.
Vérifier que :
- Phase 6, langue = source : **copie** `consolidated_master.md` à l'identique dans
  `output_dir/consolidated.{source}.md` (aucune hypothèse 1 source = 1 chapitre).
- Phase 7 : s'exécute sur ce consolidé (fake LLM) sans erreur et produit son artefact.

```python
"""Non-régression : phases 6/7 sur un document consolidé thématique."""

from pathlib import Path
from typing import Any

from fahmi2.domain.enums import Language
from fahmi2.pipeline.handlers.phase_6_translation import Phase6TranslationHandler
# (réutiliser le helper build_phase_context et un FakeLLMProvider)


_THEMATIC_DOC = (
    "# Cours consolidé\n\n## Sommaire\n\n1. [Thème transversal](#1-theme-transversal)\n\n"
    "# 1. Thème transversal\n\n## 1.1 Sous-thème\n\nContenu fusionné de plusieurs sources.\n"
)


def test_phase6_source_language_copies_thematic_doc(
    tmp_path: Path, make_generation_settings: Any
) -> None:
    # settings : output_languages = (source,) uniquement -> pas de traduction LLM
    # écrire workspace/consolidated_master.md = _THEMATIC_DOC + les structured/*.md
    # exécuter Phase6TranslationHandler().execute(ctx, source=None)
    # assert (output_dir / "consolidated.fr.md").read_text() == _THEMATIC_DOC
    ...
```

> S'appuyer sur les fixtures et le helper `build_phase_context` déjà utilisés par
> `test_phase_6_translation.py` / `test_phase_7_coherence.py` (copier leur montage).

- [ ] **Step 2 : Lancer → succès attendu sans modification du code aval**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/pipeline/handlers/test_downstream_thematic.py -v`
Expected: PASS **sans toucher** aux handlers 6/7 (preuve d'indépendance). Si un test
échoue, c'est un vrai défaut d'hypothèse → corriger le handler concerné et
documenter.

- [ ] **Step 3 : Commit**

```powershell
git add tests/unit/pipeline/handlers/test_downstream_thematic.py
git commit -m "test(pipeline): non-regression phases 6/7 sur un consolide thematique"
```

---

### Task 7.2 : Documentation

**Files:**
- Modify: `CLAUDE.md`
- Modify: `README.md`
- Modify: `docs/superpowers/specs/2026-05-22-modes-consolidation-backlog.md`

- [ ] **Step 1 : `CLAUDE.md`**

Dans le tableau « Le pipeline en 8 phases » et/ou la section consolidation, ajouter
une note : la **phase 5 est un dispatcher** `ConsolidationMode` (`ORDERED` défaut /
`THEMATIC`). Décrire en une ligne le mode thématique (map-reduce à provenance :
relevé factuel → plan → chapitres → assemblage ; double contrôle déterministe de
couverture ; artefacts `consolidation/` conservés). Ajouter à la liste des
mécanismes transverses le renvoi à la spec
`2026-05-26-modes-consolidation-thematique-design.md`.

- [ ] **Step 2 : `README.md`**

Mentionner le choix du mode de consolidation (ordonné vs refonte thématique) dans la
description de la fonctionnalité Génération.

- [ ] **Step 3 : Mettre à jour le backlog**

Dans `2026-05-22-modes-consolidation-backlog.md`, marquer `THEMATIC_MERGE` comme
**réalisé** (renvoi vers la spec/le plan de 2026-05-26) ; `SMART_ORDER` **reste
parqué**. Mettre à jour l'en-tête « Statut ».

- [ ] **Step 4 : Vérifs finales de clôture**

```powershell
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m mypy src tests
```

Les trois **verts**. Repasser jusqu'à zéro défaut (cf. CLAUDE.md).

- [ ] **Step 5 : Commit**

```powershell
git add CLAUDE.md README.md docs/superpowers/specs/2026-05-22-modes-consolidation-backlog.md
git commit -m "docs: documente le mode de consolidation thematique (CLAUDE.md, README, backlog)"
```

---

## Clôture du chantier

À l'issue du Lot 7, la branche `feat/consolidation-thematique` porte la
fonctionnalité complète. Étapes de finalisation (à valider avec l'utilisateur) :
mise à jour des compteurs de tests, puis skill `superpowers:finishing-a-development-branch`
(merge / PR) — **hors plan**, sur décision explicite.
