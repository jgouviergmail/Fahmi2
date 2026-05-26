# Lot 4 — Stratégie `THEMATIC` (map-reduce à provenance)

> Sous-skill d'exécution : superpowers:executing-plans. Étapes en `- [ ]`.
> **Dépend de** : Lot 2 (ABC `_base`) et Lot 3 (prompts).

**But du lot :** Implémenter `ThematicConsolidationStrategy` : T1 relevé factuel →
T2 plan + couverture #1 → T3 rédaction par chapitre + couverture #2 → T4 méta +
assemblage ; artefacts conservés + reprise intra-phase.

**Décision de journalisation (précision vs spec §3.2/§3.3) :** le sous-système de
logs passe par des *sinks* non injectés dans `PhaseContext`. Les diagnostics de
couverture sont donc **persistés dans `consolidation/coverage.json`** (consultable),
plutôt que dans `events.jsonl`. Le filet « Éléments complémentaires » garantit
qu'aucun élément ne disparaît, indépendamment de la journalisation. Surface UI des
logs = hors périmètre.

**Constantes (dans `thematic.py`) :**
```python
CONSOLIDATION_SUBDIR = "consolidation"
FACTS_MASTER_FILENAME = "facts_master.json"
FACTS_READABLE_FILENAME = "facts.md"
THEMATIC_PLAN_FILENAME = "thematic_plan.json"
COVERAGE_FILENAME = "coverage.json"
MANIFEST_FILENAME = "_manifest.json"
CHAPTERS_SUBDIR = "chapters"
COMPLEMENTARY_CHAPTER_TITLE = "Éléments complémentaires"
TEMPLATE_FACT_LEDGER = "phase_5_fact_ledger"
TEMPLATE_THEMATIC_PLAN = "phase_5_thematic_plan"
TEMPLATE_THEMATIC_CHAPTER = "phase_5_thematic_chapter"
TEMPLATE_CONSOLIDATION = "phase_5_consolidation"  # méta réutilisée (T4)
```

**Dataclasses (dans `thematic.py`) :**
```python
@dataclass(frozen=True)
class _FactElement:
    """Élément de contenu tracé (relevé factuel T1)."""
    id: str           # "<source_id>#<n>"
    source_id: str
    type: str
    enonce: str
    donnees: str
    extrait_verbatim: str


@dataclass(frozen=True)
class _PlannedChapter:
    """Chapitre planifié (T2)."""
    title: str
    order: int
    element_ids: tuple[str, ...]
```

---

### Task 4.1 : T1 — Relevé factuel par source + artefacts

**Files:**
- Modify (remplace le stub): `src/fahmi2/pipeline/handlers/_consolidation/thematic.py`
- Test: `tests/unit/pipeline/handlers/_consolidation/test_thematic.py`

- [ ] **Step 1 : Test de l'id global + rendu `facts.md` (fonctions pures)**

```python
def test_assign_global_ids_prefixes_source() -> None:
    from fahmi2.pipeline.handlers._consolidation.thematic import _elements_from_payload

    payload = {"elements": [
        {"n": 1, "type": "fait", "enonce": "E1", "donnees": "", "extrait_verbatim": "v1"},
        {"n": 2, "type": "chiffre", "enonce": "E2", "donnees": "42", "extrait_verbatim": "v2"},
    ]}
    elements = _elements_from_payload(payload, source_id="s1")
    assert [e.id for e in elements] == ["s1#1", "s1#2"]
    assert elements[1].donnees == "42"


def test_render_facts_md_groups_by_source() -> None:
    from fahmi2.pipeline.handlers._consolidation.thematic import (
        _FactElement,
        _render_facts_md,
    )

    els = [
        _FactElement("s1#1", "s1", "fait", "E1", "", "v1"),
        _FactElement("s2#1", "s2", "chiffre", "E2", "42", "v2"),
    ]
    md = _render_facts_md(els)
    assert "s1" in md and "s2" in md and "E1" in md and "42" in md
```

- [ ] **Step 2 : Lancer → échec** (`ImportError`)

Run: `.venv\Scripts\python.exe -m pytest tests/unit/pipeline/handlers/_consolidation/test_thematic.py -k "global_ids or facts_md" -v`

- [ ] **Step 3 : Implémenter T1 (début de `thematic.py`)**

Remplacer le stub par : docstring de module, imports
(`json`, `hashlib`, `dataclass`, `Path`, `Any`, `map_bounded`, helpers `_base`
de `_consolidation`, helpers LLM `invoke_llm`/`parse_json_response`/`language_label`/
`style_label`, `PhaseId`, `ConsolidationResult`/`ConsolidationStrategy`,
`PhaseContext`), les constantes et dataclasses ci-dessus, puis :

```python
def _elements_from_payload(
    payload: dict[str, Any], *, source_id: str
) -> list[_FactElement]:
    """Construit les éléments tracés d'une source (id global = source_id#n)."""
    out: list[_FactElement] = []
    for raw in payload.get("elements", []):
        n = int(raw["n"])
        out.append(
            _FactElement(
                id=f"{source_id}#{n}",
                source_id=source_id,
                type=str(raw.get("type", "")),
                enonce=str(raw.get("enonce", "")),
                donnees=str(raw.get("donnees", "")),
                extrait_verbatim=str(raw.get("extrait_verbatim", "")),
            )
        )
    return out


def _extract_ledger_one(
    ctx: PhaseContext, item: tuple[str, str]
) -> tuple[list[_FactElement], float]:
    """T1 pour une source : (source_id, structured_md) -> (éléments, coût)."""
    source_id, structured_md = item
    prompt = ctx.prompts.render(
        TEMPLATE_FACT_LEDGER,
        output_language_label=language_label(ctx.settings.source_language),
        structured_markdown=structured_md,
    )
    response = invoke_llm(
        ctx, phase_id=PhaseId.CONSOLIDATION, system_prompt=None, user_prompt=prompt
    )
    payload = parse_json_response(response.content, phase_id=PhaseId.CONSOLIDATION)
    return _elements_from_payload(dict(payload), source_id=source_id), response.cost_usd


def _render_facts_md(elements: list[_FactElement]) -> str:
    """Rendu lisible du relevé factuel, groupé par source."""
    lines: list[str] = ["# Relevé factuel", ""]
    by_source: dict[str, list[_FactElement]] = {}
    for el in elements:
        by_source.setdefault(el.source_id, []).append(el)
    for source_id, els in by_source.items():
        lines.append(f"## Source `{source_id}`")
        lines.append("")
        for el in els:
            data = f" — _{el.donnees}_" if el.donnees else ""
            lines.append(f"- **[{el.id}]** ({el.type}) {el.enonce}{data}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
```

- [ ] **Step 4 : Lancer → succès**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/pipeline/handlers/_consolidation/test_thematic.py -k "global_ids or facts_md" -v`
Expected: PASS.

- [ ] **Step 5 : Commit**

```powershell
git add src/fahmi2/pipeline/handlers/_consolidation/thematic.py tests/unit/pipeline/handlers/_consolidation/test_thematic.py
git commit -m "feat(consolidation): T1 releve factuel par source (ids traces + facts.md)"
```

---

### Task 4.2 : T2 — Plan thématique + contrôle de couverture #1

**Files:**
- Modify: `src/fahmi2/pipeline/handlers/_consolidation/thematic.py`
- Test: `tests/unit/pipeline/handlers/_consolidation/test_thematic.py`

- [ ] **Step 1 : Test de réconciliation de couverture (fonction pure)**

```python
def test_reconcile_coverage_adds_complementary_for_orphans() -> None:
    from fahmi2.pipeline.handlers._consolidation.thematic import (
        _PlannedChapter,
        _reconcile_coverage,
        COMPLEMENTARY_CHAPTER_TITLE,
    )

    planned = [_PlannedChapter("Thème A", 1, ("s1#1",))]
    chapters, orphans = _reconcile_coverage(planned, all_ids=["s1#1", "s1#2", "s2#1"])
    assert orphans == ["s1#2", "s2#1"]
    assert chapters[-1].title == COMPLEMENTARY_CHAPTER_TITLE
    assert chapters[-1].element_ids == ("s1#2", "s2#1")


def test_reconcile_coverage_no_orphans_keeps_plan() -> None:
    from fahmi2.pipeline.handlers._consolidation.thematic import (
        _PlannedChapter,
        _reconcile_coverage,
    )

    planned = [_PlannedChapter("A", 1, ("s1#1", "s1#2"))]
    chapters, orphans = _reconcile_coverage(planned, all_ids=["s1#1", "s1#2"])
    assert orphans == []
    assert len(chapters) == 1
```

- [ ] **Step 2 : Lancer → échec**

- [ ] **Step 3 : Implémenter T2 + couverture #1**

```python
def _build_elements_listing(elements: list[_FactElement]) -> str:
    """Listing compact (id — énoncé), groupé par source, pour le plan."""
    by_source: dict[str, list[_FactElement]] = {}
    for el in elements:
        by_source.setdefault(el.source_id, []).append(el)
    lines: list[str] = []
    for source_id, els in by_source.items():
        lines.append(f"Source {source_id} :")
        lines.extend(f"  {el.id} — {el.enonce}" for el in els)
    return "\n".join(lines)


def _plan_thematic(
    ctx: PhaseContext, elements: list[_FactElement]
) -> tuple[str, list[_PlannedChapter], float]:
    """T2 : appelle le LLM, renvoie (global_title, chapitres planifiés, coût)."""
    prompt = ctx.prompts.render(
        TEMPLATE_THEMATIC_PLAN,
        output_language_label=language_label(ctx.settings.source_language),
        elements_listing=_build_elements_listing(elements),
    )
    response = invoke_llm(
        ctx, phase_id=PhaseId.CONSOLIDATION, system_prompt=None, user_prompt=prompt
    )
    payload = dict(parse_json_response(response.content, phase_id=PhaseId.CONSOLIDATION))
    global_title = str(payload.get("global_title", "Document consolidé"))
    planned = [
        _PlannedChapter(
            title=str(c.get("title", "")).strip() or f"Chapitre {i}",
            order=int(c.get("order", i)),
            element_ids=tuple(str(x) for x in c.get("element_ids", [])),
        )
        for i, c in enumerate(payload.get("chapters", []), start=1)
    ]
    planned.sort(key=lambda c: c.order)
    return global_title, planned, response.cost_usd


def _reconcile_coverage(
    planned: list[_PlannedChapter], *, all_ids: list[str]
) -> tuple[list[_PlannedChapter], list[str]]:
    """Contrôle #1 : rattache les ids orphelins à un chapitre complémentaire.

    Args:
        planned: Chapitres issus du plan LLM.
        all_ids: Tous les ids extraits en T1 (ordre stable).

    Returns:
        ``(chapitres_avec_filet, ids_orphelins)``. Les ids inconnus produits par
        le LLM (hors ``all_ids``) sont ignorés (ne peuvent rien rendre).
    """
    known = set(all_ids)
    assigned: set[str] = set()
    cleaned: list[_PlannedChapter] = []
    for chap in planned:
        kept = tuple(eid for eid in chap.element_ids if eid in known)
        assigned.update(kept)
        cleaned.append(
            _PlannedChapter(title=chap.title, order=chap.order, element_ids=kept)
        )
    orphans = [eid for eid in all_ids if eid not in assigned]
    if orphans:
        cleaned.append(
            _PlannedChapter(
                title=COMPLEMENTARY_CHAPTER_TITLE,
                order=len(cleaned) + 1,
                element_ids=tuple(orphans),
            )
        )
    return cleaned, orphans
```

- [ ] **Step 4 : Lancer → succès**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/pipeline/handlers/_consolidation/test_thematic.py -k reconcile -v`
Expected: PASS.

- [ ] **Step 5 : Commit**

```powershell
git add src/fahmi2/pipeline/handlers/_consolidation/thematic.py tests/unit/pipeline/handlers/_consolidation/test_thematic.py
git commit -m "feat(consolidation): T2 plan thematique + controle de couverture #1"
```

---

### Task 4.3 : T3 — Rédaction par chapitre + contrôle de couverture #2

**Files:**
- Modify: `src/fahmi2/pipeline/handlers/_consolidation/thematic.py`
- Test: `tests/unit/pipeline/handlers/_consolidation/test_thematic.py`

- [ ] **Step 1 : Test du gap de couverture #2 (pur) + élément JSON d'un chapitre**

```python
def test_chapter_coverage_gaps() -> None:
    from fahmi2.pipeline.handlers._consolidation.thematic import _chapter_coverage_gaps

    assert _chapter_coverage_gaps(assigned=("a", "b", "c"), used=("a", "c")) == ["b"]
    assert _chapter_coverage_gaps(assigned=("a",), used=("a", "z")) == []
```

- [ ] **Step 2 : Lancer → échec**

- [ ] **Step 3 : Implémenter T3 + couverture #2**

```python
def _elements_payload_for_chapter(
    element_ids: tuple[str, ...], by_id: dict[str, _FactElement]
) -> list[dict[str, str]]:
    """Construit la charge JSON des éléments assignés à un chapitre."""
    return [
        {
            "id": by_id[eid].id,
            "source": by_id[eid].source_id,
            "type": by_id[eid].type,
            "enonce": by_id[eid].enonce,
            "donnees": by_id[eid].donnees,
            "extrait_verbatim": by_id[eid].extrait_verbatim,
        }
        for eid in element_ids
        if eid in by_id
    ]


def _write_chapter_body(
    ctx: PhaseContext,
    chapter: _PlannedChapter,
    by_id: dict[str, _FactElement],
) -> tuple[str, list[str], float]:
    """T3 pour un chapitre : -> (body_markdown, used_ids, coût)."""
    elements_payload = _elements_payload_for_chapter(chapter.element_ids, by_id)
    prompt = ctx.prompts.render(
        TEMPLATE_THEMATIC_CHAPTER,
        output_language_label=language_label(ctx.settings.source_language),
        style_label=style_label(ctx.settings.style_preset),
        style_directives=ctx.settings.style_directives,
        chapter_title=chapter.title,
        elements_json=json.dumps(elements_payload, ensure_ascii=False, indent=2),
    )
    response = invoke_llm(
        ctx, phase_id=PhaseId.CONSOLIDATION, system_prompt=None, user_prompt=prompt
    )
    payload = dict(parse_json_response(response.content, phase_id=PhaseId.CONSOLIDATION))
    body = str(payload.get("body_markdown", "")).strip()
    used = [str(x) for x in payload.get("used_element_ids", [])]
    return body, used, response.cost_usd


def _chapter_coverage_gaps(
    *, assigned: tuple[str, ...], used: tuple[str, ...]
) -> list[str]:
    """Contrôle #2 : ids assignés mais non rendus (assigned - used)."""
    used_set = set(used)
    return [eid for eid in assigned if eid not in used_set]
```

- [ ] **Step 4 : Lancer → succès**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/pipeline/handlers/_consolidation/test_thematic.py -k coverage_gaps -v`
Expected: PASS.

- [ ] **Step 5 : Commit**

```powershell
git add src/fahmi2/pipeline/handlers/_consolidation/thematic.py tests/unit/pipeline/handlers/_consolidation/test_thematic.py
git commit -m "feat(consolidation): T3 redaction par chapitre + controle de couverture #2"
```

---

### Task 4.4 : T4 méta + `consolidate()` (bout en bout) + coût

**Files:**
- Modify: `src/fahmi2/pipeline/handlers/_consolidation/thematic.py`
- Test: `tests/unit/pipeline/handlers/_consolidation/test_thematic.py`

- [ ] **Step 1 : Test bout en bout avec `FakeLLMProvider` séquentiel**

Construire un `PhaseContext` (helper `build_phase_context`) avec settings
`consolidation_mode=THEMATIC`, 2 sources structurées. Fake LLM séquentiel :
2 réponses T1 (relevés), 1 réponse T2 (plan couvrant tous les ids), N réponses T3
(une par chapitre), 1 réponse T4 (méta). Puis :

```python
def test_thematic_consolidate_end_to_end(tmp_path, make_generation_settings):
    # ... build ctx (THEMATIC) + structured (2 sources) + fake LLM séquentiel ...
    from fahmi2.pipeline.handlers._consolidation.thematic import (
        ThematicConsolidationStrategy,
    )
    from fahmi2.pipeline.handlers._consolidation._base import load_all_structured

    structured = load_all_structured(ctx.workspace, ctx.run.sources)
    result = ThematicConsolidationStrategy().consolidate(ctx, structured)

    assert result.consolidated_markdown.startswith("# ")
    assert "## Sommaire" in result.consolidated_markdown
    assert result.cost_usd > 0
    # artefacts conservés
    base = ctx.workspace / "consolidation"
    assert (base / "facts_master.json").exists()
    assert (base / "facts.md").exists()
    assert (base / "thematic_plan.json").exists()
    assert (base / "coverage.json").exists()
    assert (base / "chapters").is_dir()
```

- [ ] **Step 2 : Lancer → échec**

- [ ] **Step 3 : Implémenter T4 + `consolidate()`**

```python
def _produce_meta(
    ctx: PhaseContext, global_title: str, chapters: list[_PlannedChapter]
) -> tuple[dict[str, Any], float]:
    """T4 : méta-éléments (réutilise le prompt phase_5_consolidation)."""
    summaries = [
        {"source_id": "", "title": c.title, "outline": list(c.element_ids)}
        for c in chapters
    ]
    prompt = ctx.prompts.render(
        TEMPLATE_CONSOLIDATION,
        output_language_label=language_label(ctx.settings.source_language),
        style_label=style_label(ctx.settings.style_preset),
        style_directives=ctx.settings.style_directives,
        summaries_json=json.dumps(summaries, ensure_ascii=False, indent=2),
    )
    response = invoke_llm(
        ctx, phase_id=PhaseId.CONSOLIDATION, system_prompt=None, user_prompt=prompt
    )
    payload = dict(parse_json_response(response.content, phase_id=PhaseId.CONSOLIDATION))
    payload["global_title"] = payload.get("global_title") or global_title
    return payload, response.cost_usd
```

Puis la classe (remplace le stub du Lot 2) :

```python
class ThematicConsolidationStrategy(ConsolidationStrategy):
    """Mode THEMATIC : refonte thématique transversale (map-reduce à provenance)."""

    def consolidate(
        self, ctx: PhaseContext, structured_by_source: dict[str, str]
    ) -> ConsolidationResult:
        base_dir = ctx.workspace / CONSOLIDATION_SUBDIR
        total_cost = 0.0

        # T1 — relevé factuel par source (parallélisé, ordre préservé).
        ledger_results = map_bounded(
            lambda kv: _extract_ledger_one(ctx, kv),
            list(structured_by_source.items()),
            max_workers=ctx.settings.parallelism.llm_workers,
            pause_token=ctx.pause_token,
        )
        elements: list[_FactElement] = []
        for els, cost in ledger_results:
            elements.extend(els)
            total_cost += cost
        ctx.artifacts.write_json_atomic(
            base_dir / FACTS_MASTER_FILENAME,
            {"elements": [el.__dict__ for el in elements]},
        )
        ctx.artifacts.write_text_atomic(
            base_dir / FACTS_READABLE_FILENAME, _render_facts_md(elements)
        )

        # T2 — plan thématique + couverture #1.
        global_title, planned, plan_cost = _plan_thematic(ctx, elements)
        total_cost += plan_cost
        all_ids = [el.id for el in elements]
        chapters_plan, orphans = _reconcile_coverage(planned, all_ids=all_ids)
        ctx.artifacts.write_json_atomic(
            base_dir / THEMATIC_PLAN_FILENAME,
            {
                "global_title": global_title,
                "chapters": [
                    {"title": c.title, "order": c.order,
                     "element_ids": list(c.element_ids)}
                    for c in chapters_plan
                ],
            },
        )

        # T3 — rédaction par chapitre (parallélisée) + couverture #2.
        by_id = {el.id: el for el in elements}
        write_results = map_bounded(
            lambda c: _write_chapter_body(ctx, c, by_id),
            chapters_plan,
            max_workers=ctx.settings.parallelism.llm_workers,
            pause_token=ctx.pause_token,
        )
        chapter_gaps: dict[str, list[str]] = {}
        chapters: list[_Chapter] = []
        for index, (planned_chapter, (body, used, cost)) in enumerate(
            zip(chapters_plan, write_results, strict=True), start=1
        ):
            total_cost += cost
            gaps = _chapter_coverage_gaps(
                assigned=planned_chapter.element_ids, used=tuple(used)
            )
            if gaps:
                chapter_gaps[planned_chapter.title] = gaps
            renumbered, subheadings = renumber_subheadings(body, index)
            ctx.artifacts.write_text_atomic(
                base_dir / CHAPTERS_SUBDIR / f"{index}.md", renumbered
            )
            chapters.append(
                _Chapter(
                    index=index,
                    title=strip_existing_numbering(planned_chapter.title)
                    or f"Chapitre {index}",
                    body=renumbered,
                    subheadings=tuple(subheadings),
                )
            )
        ctx.artifacts.write_json_atomic(
            base_dir / COVERAGE_FILENAME,
            {"orphans": orphans, "chapter_gaps": chapter_gaps},
        )

        # T4 — méta + assemblage déterministe.
        meta, meta_cost = _produce_meta(ctx, global_title, chapters_plan)
        total_cost += meta_cost
        markdown = assemble_document(meta, chapters)
        return ConsolidationResult(
            consolidated_markdown=markdown, cost_usd=total_cost
        )
```

> Imports requis depuis `_base` (de `_consolidation`) : `_Chapter`,
> `assemble_document`, `renumber_subheadings`, `strip_existing_numbering`,
> `ConsolidationResult`, `ConsolidationStrategy`.

- [ ] **Step 4 : Lancer → succès**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/pipeline/handlers/_consolidation/test_thematic.py::test_thematic_consolidate_end_to_end -v`
Expected: PASS.

- [ ] **Step 5 : Commit**

```powershell
git add src/fahmi2/pipeline/handlers/_consolidation/thematic.py tests/unit/pipeline/handlers/_consolidation/test_thematic.py
git commit -m "feat(consolidation): T4 meta + consolidate() bout en bout (mode THEMATIC)"
```

---

### Task 4.5 : Reprise intra-phase (hash de cohérence)

**Files:**
- Modify: `src/fahmi2/pipeline/handlers/_consolidation/thematic.py`
- Test: `tests/unit/pipeline/handlers/_consolidation/test_thematic.py`

- [ ] **Step 1 : Test — un artefact frais est réutilisé (pas de 2e appel T1)**

```python
def test_thematic_reuses_fresh_artifacts_on_resume(tmp_path, make_generation_settings):
    # 1er run complet (fake LLM séquentiel complet). Compter les appels via fake.calls.
    # 2e run avec MÊMES sources/settings : le hash matche -> facts/plan/chapitres
    # frais réutilisés ; le fake ne doit PAS recevoir de nouveaux appels T1.
    # Assert : nombre d'appels au 2e run == 0 (tout réutilisé) OU artefacts identiques.
    ...
```

> Implémentation du test : réutiliser le `FakeLLMProvider` et vérifier
> `len(fake.calls)` inchangé après le 2e `consolidate`.

- [ ] **Step 2 : Lancer → échec**

- [ ] **Step 3 : Implémenter le hash + réutilisation**

Ajouter :

```python
def _consistency_hash(ctx: PhaseContext, structured_by_source: dict[str, str]) -> str:
    """Empreinte (mode + modèle + style + langues + contenu structuré)."""
    payload = {
        "mode": str(ctx.settings.consolidation_mode),
        "model": str(ctx.settings.llm_model),
        "style": str(ctx.settings.style_preset),
        "style_directives": ctx.settings.style_directives,
        "source_language": str(ctx.settings.source_language),
        "sources": {
            sid: hashlib.sha256(md.encode("utf-8")).hexdigest()
            for sid, md in structured_by_source.items()
        },
    }
    blob = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()
```

Au début de `consolidate`, après `base_dir = ...` :

```python
        current_hash = _consistency_hash(ctx, structured_by_source)
        manifest_path = base_dir / MANIFEST_FILENAME
        stale = (
            not manifest_path.exists()
            or json.loads(manifest_path.read_text("utf-8")).get("hash") != current_hash
        )
        if stale and base_dir.exists():
            shutil.rmtree(base_dir)  # artefacts d'un run incompatible
        ctx.artifacts.write_json_atomic(manifest_path, {"hash": current_hash})
```

Puis encapsuler chaque étape coûteuse par une réutilisation *skip-if-exists* :
- T1 : si `FACTS_MASTER_FILENAME` existe (et hash frais), **charger** les éléments
  via `_elements_from_payload`-équivalent au lieu d'appeler le LLM.
- T2 : si `THEMATIC_PLAN_FILENAME` existe, charger `chapters_plan`/`global_title`.
- T3 : si `chapters/<index>.md` existe, le **relire** (et reconstruire le `_Chapter`
  via `renumber_subheadings` n'est plus nécessaire — le fichier est déjà renuméroté ;
  reconstruire `subheadings` en re-parsant n'est pas requis pour l'assemblage si on
  conserve le body tel quel et qu'on régénère les sous-titres via une relecture
  légère). **Décision** : pour le sommaire, re-dériver les `subheadings` du body relu
  via une fonction `subheadings_of(body)` (à ajouter dans `_base`, parse des `##`/`###`
  déjà numérotés). Cela garde l'assemblage déterministe à partir des fichiers.

> Ajouter dans `_base` : `subheadings_of(body: str) -> tuple[_Subheading, ...]`
> (parse des lignes `## N.M …` / `### N.M.P …`, hors blocs ```` ``` ````), avec son
> test unitaire dans `test_base.py`.

Importer `shutil` et `hashlib` en tête de `thematic.py`.

- [ ] **Step 4 : Lancer → succès**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/pipeline/handlers/_consolidation/test_thematic.py -k resume -v`
Expected: PASS.

- [ ] **Step 5 : Commit**

```powershell
git add src/fahmi2/pipeline/handlers/_consolidation/thematic.py
git add src/fahmi2/pipeline/handlers/_consolidation/_base.py
git add tests/unit/pipeline/handlers/_consolidation/test_thematic.py
git add tests/unit/pipeline/handlers/_consolidation/test_base.py
git commit -m "feat(consolidation): reprise intra-phase thematique (hash de coherence)"
```

---

### Task 4.6 : Conflits présentés par source (test d'intégration)

**Files:**
- Test: `tests/unit/pipeline/handlers/_consolidation/test_thematic.py`

- [ ] **Step 1 : Test — deux sources contradictoires, même chapitre**

Fake LLM : T1 produit pour s1 un élément « la valeur est 10 » et pour s2 « la
valeur est 20 » ; T2 place `s1#1` et `s2#1` dans le **même** chapitre ; T3 (fourni
par le fake) renvoie un body qui cite les deux sources. Vérifier que le body du
chapitre **contient les deux énoncés** et n'en supprime aucun (le fake simule le
comportement attendu ; le test verrouille le **flux de données** : les deux
éléments contradictoires arrivent bien ensemble au rédacteur T3).

```python
def test_conflicting_elements_reach_same_chapter(tmp_path, make_generation_settings):
    captured = {}
    # fake T3 qui capture elements_json reçu pour le chapitre
    # ... assert que le payload du chapitre contient s1#1 ET s2#1 ...
```

- [ ] **Step 2 : Lancer → succès** (le code de Task 4.4 le permet déjà ; ce test
  verrouille le contrat).

- [ ] **Step 3 : Vérifs de lot + commit**

```powershell
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m mypy src tests
git add tests/unit/pipeline/handlers/_consolidation/test_thematic.py
git commit -m "test(consolidation): conflits co-localises au meme chapitre (flux T2->T3)"
```
