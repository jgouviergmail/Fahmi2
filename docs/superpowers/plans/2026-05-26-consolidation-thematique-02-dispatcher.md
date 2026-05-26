# Lot 2 — Dispatcher de stratégies + stratégie `ORDERED` (non-régression)

> Sous-skill d'exécution : superpowers:executing-plans. Étapes en `- [ ]`.

**But du lot :** Extraire un package `_consolidation/` avec `ConsolidationResult`,
`ConsolidationStrategy` (ABC) et les helpers déterministes partagés ; faire de
`phase_5_consolidation.py` un **dispatcher** ; **conserver à l'identique** le
comportement `ORDERED`. La suite de tests existante doit rester verte.

**Principe de refactor :** déplacement de code **verbatim** depuis l'actuel
`phase_5_consolidation.py` (cf. listes ci-dessous), + un seul vrai ajout structurel
(`assemble_document` extrait de `_assemble_consolidated`, ABC, dispatcher).

---

### Task 2.1 : Package `_consolidation/` + `_base.py`

**Files:**
- Create: `src/fahmi2/pipeline/handlers/_consolidation/__init__.py` (vide ou docstring)
- Create: `src/fahmi2/pipeline/handlers/_consolidation/_base.py`
- Test: `tests/unit/pipeline/handlers/_consolidation/test_base.py`

- [ ] **Step 1 : Test des helpers déterministes partagés**

```python
"""Tests des helpers déterministes partagés de consolidation."""

from fahmi2.pipeline.handlers._consolidation._base import (
    ConsolidationResult,
    strip_existing_numbering,
)


def test_consolidation_result_carries_markdown_and_cost() -> None:
    res = ConsolidationResult(consolidated_markdown="# T\n", cost_usd=1.5)
    assert res.consolidated_markdown == "# T\n"
    assert res.cost_usd == 1.5


def test_strip_existing_numbering() -> None:
    assert strip_existing_numbering("1.2 Titre") == "Titre"
    assert strip_existing_numbering("Titre") == "Titre"
```

- [ ] **Step 2 : Lancer → échec**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/pipeline/handlers/_consolidation/test_base.py -v`
Expected: FAIL (`ModuleNotFoundError: ..._consolidation._base`).

- [ ] **Step 3 : Créer `_base.py`**

Contenu de `_base.py` :

1. **Docstring de module.**
2. **Imports** : `from __future__ import annotations`, `re`, `dataclass`,
   `Path`, `typing.Any`, `ABC`/`abstractmethod`, `slugify_anchor` (core),
   `Severity`, `StorageError`, `SourceExecution`, `PhaseContext`.
3. **Constantes** (déplacées verbatim de `phase_5_consolidation.py`, **sans** le
   préfixe `_` désormais public dans le module) :
   `STRUCTURED_SUBDIR = "structured"`, `CONSOLIDATED_MASTER_FILENAME =
   "consolidated_master.md"`, `SUMMARY_HEADING = "Résumé"`, `TOC_MAX_DEPTH = 3`,
   et les regexes `_RE_CODE_FENCE`, `_RE_H1`, `_RE_H2`, `_RE_H3`, `_RE_H4_PLUS`,
   `_RE_EXISTING_NUMBERING`.
4. **Dataclasses déplacées verbatim** : `_Subheading`, `_Chapter`.
5. **Fonctions déplacées verbatim** depuis `phase_5_consolidation.py`
   (en retirant le `_` de tête pour les rendre partagées) :
   - `load_all_structured(workspace, sources)` (ex `_load_all_structured`) — utiliser
     `STRUCTURED_SUBDIR`.
   - `build_toc_lines(chapters)` (ex `_build_toc_lines`) — utiliser `TOC_MAX_DEPTH`.
   - `renumber_subheadings(body, chapter_index)` (ex `_renumber_subheadings`).
   - `strip_existing_numbering(title)` (ex `_strip_existing_numbering`).
   - `demote_chapter_h1(structured_markdown)` (ex `_demote_chapter_h1`).
6. **Nouveau** : `ConsolidationResult` :

```python
@dataclass(frozen=True)
class ConsolidationResult:
    """Résultat d'une stratégie de consolidation.

    Attributes:
        consolidated_markdown: Document consolidé final en langue source.
        cost_usd: Coût cumulé de tous les appels LLM de la stratégie.
    """

    consolidated_markdown: str
    cost_usd: float
```

7. **Nouveau** : `assemble_document(meta, chapters)` — extrait du corps de l'actuel
   `_assemble_consolidated`, à partir de la construction des `parts` (titre →
   résumé → intro → sommaire → chapitres → conclusion). Signature :

```python
def assemble_document(
    meta: dict[str, Any], chapters: list[_Chapter]
) -> str:
    """Assemble le document consolidé final (méta + chapitres + sommaire).

    Args:
        meta: Méta-éléments (``global_title``, ``summary_markdown``,
            ``introduction_markdown``, ``conclusion_markdown``).
        chapters: Chapitres déjà numérotés/renumérotés (ordre = ordre final).

    Returns:
        Le document Markdown consolidé complet.
    """
    title = str(meta.get("global_title", "Document consolidé"))
    summary = str(meta.get("summary_markdown", "")).strip()
    introduction = str(meta.get("introduction_markdown", "")).strip()
    conclusion = str(meta.get("conclusion_markdown", "")).strip()

    parts: list[str] = [f"# {title}", ""]
    if summary:
        parts.extend([f"## {SUMMARY_HEADING}", "", summary, ""])
    if introduction:
        parts.extend(["## Introduction générale", "", introduction, ""])
    if chapters:
        parts.append("## Sommaire")
        parts.append("")
        parts.extend(build_toc_lines(chapters))
        parts.append("")
    for chapter in chapters:
        parts.append(f"# {chapter.index}. {chapter.title}")
        parts.append("")
        if chapter.body:
            parts.append(chapter.body)
            parts.append("")
    if conclusion:
        parts.extend(["## Conclusion générale", "", conclusion, ""])
    return "\n".join(parts).rstrip() + "\n"
```

8. **Nouveau** : ABC :

```python
class ConsolidationStrategy(ABC):
    """Stratégie d'assemblage du document consolidé (phase 5)."""

    @abstractmethod
    def consolidate(
        self,
        ctx: PhaseContext,
        structured_by_source: dict[str, str],
    ) -> ConsolidationResult:
        """Produit le document consolidé à partir des structurés par source.

        Args:
            ctx: Contexte d'exécution de la phase.
            structured_by_source: Markdown structuré par ``source_id`` (ordre
                = ordre des sources du run).

        Returns:
            ``ConsolidationResult`` (markdown + coût cumulé).
        """
```

- [ ] **Step 4 : Lancer → succès**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/pipeline/handlers/_consolidation/test_base.py -v`
Expected: PASS.

- [ ] **Step 5 : Commit**

```powershell
git add src/fahmi2/pipeline/handlers/_consolidation/
git add tests/unit/pipeline/handlers/_consolidation/test_base.py
git commit -m "refactor(pipeline): _consolidation/_base (ABC + helpers deterministes partages)"
```

---

### Task 2.2 : `OrderedConsolidationStrategy`

**Files:**
- Create: `src/fahmi2/pipeline/handlers/_consolidation/ordered.py`
- Test: `tests/unit/pipeline/handlers/_consolidation/test_ordered.py`

- [ ] **Step 1 : Test (comportement actuel reproduit)**

Reprendre le scénario de l'actuel `test_execute_assembles_consolidated_markdown`
mais via la stratégie : construire un `PhaseContext` (helper `build_phase_context`),
2 sources structurées, un `FakeLLMProvider` séquentiel (2 résumés + 1 méta), puis :

```python
def test_ordered_strategy_assembles_in_order(tmp_path, make_generation_settings):
    # ... build ctx avec 2 sources structurées + fake LLM (2 résumés, 1 méta) ...
    from fahmi2.pipeline.handlers._consolidation.ordered import (
        OrderedConsolidationStrategy,
    )
    from fahmi2.pipeline.handlers._consolidation._base import load_all_structured

    structured = load_all_structured(ctx.workspace, ctx.run.sources)
    result = OrderedConsolidationStrategy().consolidate(ctx, structured)
    assert "# 1. Chapitre Un" in result.consolidated_markdown
    assert "# 2. Chapitre Deux" in result.consolidated_markdown
    assert result.cost_usd > 0
```

- [ ] **Step 2 : Lancer → échec**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/pipeline/handlers/_consolidation/test_ordered.py -v`
Expected: FAIL (module absent).

- [ ] **Step 3 : Créer `ordered.py`**

`ordered.py` contient :

1. Docstring de module (reprendre le préambule actuel de `phase_5_consolidation.py`
   décrivant la pré-consolidation + consolidation globale).
2. Constantes : `TEMPLATE_VIDEO_SUMMARY = "phase_5_video_summary"`,
   `TEMPLATE_CONSOLIDATION = "phase_5_consolidation"`.
3. Imports de `_base` : `ConsolidationResult`, `ConsolidationStrategy`, `_Chapter`,
   `assemble_document`, `demote_chapter_h1`, `renumber_subheadings`,
   `strip_existing_numbering`. Imports de `_helpers` LLM : `invoke_llm`,
   `language_label`, `parse_json_response`, `style_label` (depuis
   `fahmi2.pipeline.handlers._base`). `map_bounded`, `PhaseId`.
4. `build_chapters(structured_by_source, titles_by_source)` (ex `_build_chapters`
   déplacée verbatim, en appelant `strip_existing_numbering`, `demote_chapter_h1`,
   `renumber_subheadings`, `_Chapter` de `_base`).
5. La classe :

```python
class OrderedConsolidationStrategy(ConsolidationStrategy):
    """Mode ORDERED : 1 source = 1 chapitre, contenu recopié dans l'ordre."""

    def consolidate(self, ctx, structured_by_source):
        summary_results = map_bounded(
            lambda kv: self._summarize_one(ctx, kv),
            list(structured_by_source.items()),
            max_workers=ctx.settings.parallelism.llm_workers,
            pause_token=ctx.pause_token,
        )
        summaries = [s for s, _ in summary_results]
        total_cost = sum(c for _, c in summary_results)
        meta, meta_cost = self._produce_meta(ctx, summaries)
        total_cost += meta_cost
        titles_by_source = {
            s.get("source_id", ""): s.get("title", "") for s in summaries
        }
        chapters = build_chapters(structured_by_source, titles_by_source)
        markdown = assemble_document(meta, chapters)
        return ConsolidationResult(consolidated_markdown=markdown, cost_usd=total_cost)
```

   Les méthodes `_summarize_one`, `_summarize_source`, `_produce_meta` sont
   **déplacées verbatim** depuis l'actuel `Phase5ConsolidationHandler` (mêmes corps,
   `self`/`ctx` inchangés ; utiliser `PhaseId.CONSOLIDATION`).

- [ ] **Step 4 : Lancer → succès**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/pipeline/handlers/_consolidation/test_ordered.py -v`
Expected: PASS.

- [ ] **Step 5 : Commit**

```powershell
git add src/fahmi2/pipeline/handlers/_consolidation/ordered.py
git add tests/unit/pipeline/handlers/_consolidation/test_ordered.py
git commit -m "refactor(pipeline): OrderedConsolidationStrategy (comportement actuel)"
```

---

### Task 2.3 : Dispatcher `phase_5_consolidation.py` + non-régression

**Files:**
- Modify (réécriture): `src/fahmi2/pipeline/handlers/phase_5_consolidation.py`
- (Le test historique `test_phase_5_consolidation.py` reste **inchangé** grâce aux
  ré-exports de compat — cf. Step 1bis.)

- [ ] **Step 1 : Réécrire le handler en dispatcher**

Nouveau contenu de `phase_5_consolidation.py` :

```python
"""Handler Phase 5 — consolidation finale (dispatcher de stratégies).

Sélectionne la stratégie d'assemblage selon ``settings.consolidation_mode`` :
``ORDERED`` (1 source = 1 chapitre, contenu recopié) ou ``THEMATIC`` (refonte
thématique transversale). La phase reste batch et persiste **un** ``PhaseExecution``.
"""

from __future__ import annotations

from fahmi2.domain.enums import ConsolidationMode, PhaseId
from fahmi2.domain.phase import PhaseExecution
from fahmi2.domain.source import SourceExecution
from fahmi2.pipeline.handlers._base import build_succeeded_phase, utc_now
from fahmi2.pipeline.handlers._consolidation._base import (
    CONSOLIDATED_MASTER_FILENAME,
    ConsolidationStrategy,
    load_all_structured,
)
from fahmi2.pipeline.handlers._consolidation.ordered import OrderedConsolidationStrategy
from fahmi2.pipeline.handlers._consolidation.thematic import (
    ThematicConsolidationStrategy,
)
from fahmi2.pipeline.phase_handler import PhaseContext, PhaseHandler

_STRATEGIES: dict[ConsolidationMode, type[ConsolidationStrategy]] = {
    ConsolidationMode.ORDERED: OrderedConsolidationStrategy,
    ConsolidationMode.THEMATIC: ThematicConsolidationStrategy,
}


class Phase5ConsolidationHandler(PhaseHandler):
    """Phase 5 — consolidation finale (dispatcher)."""

    @property
    def phase_id(self) -> PhaseId:
        return PhaseId.CONSOLIDATION

    @property
    def is_per_source(self) -> bool:
        return False

    def execute(
        self, ctx: PhaseContext, *, source: SourceExecution | None
    ) -> PhaseExecution:
        if source is not None:
            raise ValueError(
                "Phase5ConsolidationHandler is batch (source must be None)"
            )
        started_at = utc_now()
        structured_by_source = load_all_structured(ctx.workspace, ctx.run.sources)
        strategy = _STRATEGIES[ctx.settings.consolidation_mode]()
        result = strategy.consolidate(ctx, structured_by_source)
        out_path = ctx.workspace / CONSOLIDATED_MASTER_FILENAME
        ctx.artifacts.write_text_atomic(out_path, result.consolidated_markdown)
        return build_succeeded_phase(
            phase_id=self.phase_id,
            artifact_path=out_path,
            started_at=started_at,
            cost_usd=result.cost_usd,
        )
```

> **Note (dépendance) :** ce fichier importe `ThematicConsolidationStrategy`, créée
> au **Lot 4**. Pour exécuter le Lot 2 isolément, ajouter d'abord un stub minimal
> `thematic.py` (classe qui lève `NotImplementedError` dans `consolidate`) ; le
> Lot 4 le remplacera. Créer ce stub dans cette étape.

Stub `thematic.py` (provisoire, remplacé au Lot 4) :

```python
"""Stub provisoire — remplacé au Lot 4."""

from __future__ import annotations

from fahmi2.pipeline.handlers._consolidation._base import (
    ConsolidationResult,
    ConsolidationStrategy,
)
from fahmi2.pipeline.phase_handler import PhaseContext


class ThematicConsolidationStrategy(ConsolidationStrategy):
    """Refonte thématique (implémentée au Lot 4)."""

    def consolidate(
        self, ctx: PhaseContext, structured_by_source: dict[str, str]
    ) -> ConsolidationResult:
        raise NotImplementedError("ThematicConsolidationStrategy: Lot 4")
```

- [ ] **Step 1bis : Ré-exports de compat (non-régression sans toucher au test)**

Pour que `tests/unit/pipeline/handlers/test_phase_5_consolidation.py` reste
**inchangé** (il importe des symboles désormais déplacés), ajouter **en fin** de
`phase_5_consolidation.py` un bloc de compat :

```python
# --- Compat rétro : symboles déplacés vers _consolidation (tests existants). ---
from typing import Any  # noqa: E402

from fahmi2.pipeline.handlers._consolidation._base import (  # noqa: E402,F401
    assemble_document as _assemble_document,
    renumber_subheadings as _renumber_subheadings,
    strip_existing_numbering as _strip_existing_numbering,
)
from fahmi2.pipeline.handlers._consolidation.ordered import (  # noqa: E402
    build_chapters as _build_chapters,
)


def _assemble_consolidated(
    meta: dict[str, Any],
    structured_by_source: dict[str, str],
    summaries: list[dict[str, Any]],
) -> str:
    """Shim rétro-compatible de l'ancien ``_assemble_consolidated``.

    Reproduit l'assemblage ORDERED (build_chapters + assemble_document) pour que
    les tests historiques continuent de passer sans modification.
    """
    titles_by_source = {
        s.get("source_id", ""): s.get("title", "") for s in summaries
    }
    chapters = _build_chapters(structured_by_source, titles_by_source)
    return _assemble_document(meta, chapters)
```

> **Pourquoi** : enumérer *tous* les symboles internes que le test historique
> importe est fragile. Les ré-exports garantissent une vraie non-régression : le
> fichier de test n'est **pas modifié**. (Si `ruff` se plaint d'imports inutilisés
> malgré `F401`, regrouper sous `__all__`.)

- [ ] **Step 2 : Vérifier que le test historique passe inchangé**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/pipeline/handlers/test_phase_5_consolidation.py -v`
Expected: PASS **sans aucune modification** du fichier de test (grâce aux ré-exports).
Ne **pas** ajouter ce fichier au `git add` du commit final de ce lot.

- [ ] **Step 3 : Lancer la suite phase 5 complète → succès**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/pipeline/handlers/test_phase_5_consolidation.py tests/unit/pipeline/handlers/_consolidation/ -v`
Expected: PASS (mode ORDERED par défaut → comportement identique).

- [ ] **Step 4 : Vérifs de lot**

```powershell
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m mypy src tests
```

Expected : **tout vert** — c'est la preuve de non-régression du mode ORDERED.

- [ ] **Step 5 : Commit**

```powershell
git add src/fahmi2/pipeline/handlers/phase_5_consolidation.py
git add src/fahmi2/pipeline/handlers/_consolidation/thematic.py
git commit -m "refactor(pipeline): phase 5 = dispatcher de strategies (ORDERED inchange)"
```
