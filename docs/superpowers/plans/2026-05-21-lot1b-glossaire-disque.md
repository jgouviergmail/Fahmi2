# Lot 1b — Glossaire homogène (lecture disque + retrait de l'anomalie DB)

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (inline, sans subagents).
> **Spec** : [`../specs/2026-05-21-corrections-lot1-design.md`](../specs/2026-05-21-corrections-lot1-design.md) §3.
> Steps en checkbox. Tout en français (accents). Travail directement sur `main`.

**Goal:** Faire lire le glossaire à la pédagogie **depuis le disque**
(`glossary_master.json`), comme le pipeline (`load_glossary_master`), et **supprimer
l'anomalie** : table `glossary_terms` + `GlossaryReconciler` (code mort vestigial).

**Architecture:** Le parsing (dict → `Term`) et le rendu Markdown du glossaire
remontent dans `domain/glossary.py` (réutilisables par pipeline ET pédagogie, sans
violer les couches). La pédagogie lit le master via un helper de `pedagogy/sources.py`.
La table DB et son service disparaissent.

**Tech Stack:** Python 3.12, SQLite, pytest.

**Ordre des tâches** (chaque tâche se termine verte + commit) :
1. domain : `parse_glossary_master_terms` + `render_glossary_markdown_table` ;
2. pédagogie lit le glossaire sur disque (orchestrateur + sources) ;
3. retrait de l'anomalie DB (schéma, SqliteState, `GlossaryReconciler`, tests).

---

## Task 1 : domain — parsing + rendu du glossaire master

**Files:**
- Modify : `src/fahmi2/domain/glossary.py`
- Create : `tests/unit/domain/test_glossary.py`

On déplace dans le domaine la logique aujourd'hui dans `app/glossary_reconciler.py`
(`_extract_terms` → `parse_glossary_master_terms` ; `render_glossary_markdown_table`).

- [ ] **Step 1 : Écrire les tests qui échouent**

Créer `tests/unit/domain/test_glossary.py` :

```python
"""Tests des helpers de glossaire (parsing master + rendu Markdown)."""

from __future__ import annotations

from fahmi2.domain.enums import Language
from fahmi2.domain.glossary import (
    parse_glossary_master_terms,
    render_glossary_markdown_table,
)


def test_parse_master_terms_reads_all_fields() -> None:
    payload = {
        "terms": [
            {
                "term": "PIB",
                "definition": "produit intérieur brut",
                "acronym": "PIB",
                "acronym_expansion": "Produit Intérieur Brut",
                "aliases": ["Produit Intérieur Brut"],
                "sources": ["v1"],
                "cross_lang": {"en": "GDP"},
            },
            {"term": "Inflation", "definition": "hausse des prix"},
        ]
    }
    terms = parse_glossary_master_terms(payload)
    assert len(terms) == 2
    pib = terms[0]
    assert pib.term == "PIB"
    assert pib.acronym_expansion == "Produit Intérieur Brut"
    assert pib.aliases == ("Produit Intérieur Brut",)
    assert pib.cross_lang[Language.EN] == "GDP"
    assert [s.value for s in pib.sources] == ["v1"]


def test_parse_master_terms_empty_payload() -> None:
    assert parse_glossary_master_terms({}) == ()
    assert parse_glossary_master_terms({"terms": []}) == ()


def test_render_table_french_headers_and_invariant_expansion() -> None:
    terms = parse_glossary_master_terms(
        {
            "terms": [
                {
                    "term": "Retour sur investissement",
                    "acronym": "ROI",
                    "acronym_expansion": "Return On Investment",
                    "definition": "Indicateur de rentabilité.",
                },
                {"term": "Inflation", "definition": "Hausse des prix."},
            ]
        }
    )
    md = render_glossary_markdown_table(
        title="Glossaire", language=Language.FR, terms=terms
    )
    assert md.startswith("# Glossaire")
    assert "| Terme | Acronyme | Signification | Définition |" in md
    assert "Return On Investment" in md  # expansion invariante
    assert "| Inflation |  |  | Hausse des prix. |" in md


def test_render_table_english_headers() -> None:
    terms = parse_glossary_master_terms(
        {"terms": [{"term": "GDP", "definition": "Gross domestic product."}]}
    )
    md = render_glossary_markdown_table(
        title="Glossary", language=Language.EN, terms=terms
    )
    assert md.startswith("# Glossary")
    assert "| Term | Acronym | Meaning | Definition |" in md
```

- [ ] **Step 2 : Lancer, vérifier l'échec**

Run : `.venv\Scripts\python.exe -m pytest tests/unit/domain/test_glossary.py -v`
Attendu : ÉCHEC (`ImportError: cannot import name 'parse_glossary_master_terms'`).

- [ ] **Step 3 : Ajouter les helpers dans `domain/glossary.py`**

Dans `src/fahmi2/domain/glossary.py`, remplacer l'en-tête d'imports :

```python
from collections.abc import Iterator
from dataclasses import dataclass, field

from fahmi2.domain.enums import Language
from fahmi2.domain.ids import VideoId
```

par :

```python
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from typing import Any

from fahmi2.domain.enums import Language
from fahmi2.domain.ids import VideoId

_HEADERS_BY_LANGUAGE: dict[Language, tuple[str, str, str, str]] = {
    Language.FR: ("Terme", "Acronyme", "Signification", "Définition"),
    Language.EN: ("Term", "Acronym", "Meaning", "Definition"),
}
```

Puis ajouter, à la fin du fichier :

```python
def parse_glossary_master_terms(payload: dict[str, Any]) -> tuple[Term, ...]:
    """Convertit un payload JSON ``glossary_master`` en termes domaine.

    Args:
        payload: Dictionnaire ``{"terms": [{...}, ...]}`` produit par la phase 2.

    Returns:
        Les ``Term`` (tuple vide si aucun terme).
    """
    raw_terms = payload.get("terms", [])
    result: list[Term] = []
    for raw in raw_terms:
        sources_raw = raw.get("sources", []) or []
        aliases_raw = raw.get("aliases", []) or []
        cross_lang_raw = raw.get("cross_lang", {}) or {}
        acronym = raw.get("acronym")
        expansion = raw.get("acronym_expansion")
        result.append(
            Term(
                term=str(raw.get("term", "")),
                definition=str(raw.get("definition", "")),
                acronym=str(acronym) if acronym else None,
                acronym_expansion=str(expansion) if expansion else None,
                sources=tuple(VideoId(value=str(s)) for s in sources_raw),
                aliases=tuple(str(a) for a in aliases_raw),
                cross_lang={Language(k): str(v) for k, v in cross_lang_raw.items()},
            )
        )
    return tuple(result)


def render_glossary_markdown_table(
    *,
    title: str,
    language: Language,
    terms: Iterable[Term],
) -> str:
    """Rend une liste de ``Term`` au format tableau Markdown 4 colonnes.

    Colonnes ``| Terme | Acronyme | Signification | Définition |`` (FR) ou
    ``| Term | Acronym | Meaning | Definition |`` (EN). La colonne *Signification*
    contient l'expansion littérale de l'acronyme, conservée dans sa langue
    d'origine. Vide si le terme n'a pas d'acronyme.

    Args:
        title: Titre H1 du document.
        language: Langue (libellés d'en-têtes).
        terms: Termes à afficher (déjà triés par l'appelant).

    Returns:
        Le Markdown complet (titre, ligne vide, tableau, saut final).
    """
    headers = _HEADERS_BY_LANGUAGE.get(language, _HEADERS_BY_LANGUAGE[Language.EN])
    lines: list[str] = [f"# {title}", ""]
    lines.append(f"| {headers[0]} | {headers[1]} | {headers[2]} | {headers[3]} |")
    lines.append("|---|---|---|---|")
    for term in terms:
        acronym = term.acronym or ""
        expansion = term.acronym_expansion or ""
        term_cell = term.term.replace("|", "\\|")
        acronym_cell = acronym.replace("|", "\\|")
        expansion_cell = expansion.replace("|", "\\|").replace("\n", " ")
        def_cell = term.definition.replace("|", "\\|").replace("\n", " ")
        lines.append(
            f"| {term_cell} | {acronym_cell} | {expansion_cell} | {def_cell} |"
        )
    return "\n".join(lines) + "\n"
```

- [ ] **Step 4 : Lancer, vérifier le succès**

Run : `.venv\Scripts\python.exe -m pytest tests/unit/domain/test_glossary.py -v`
Attendu : PASS (4 tests).

- [ ] **Step 5 : Vérifs + commit**

```powershell
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m mypy src tests
git add src/fahmi2/domain/glossary.py tests/unit/domain/test_glossary.py
git commit -m @'
refactor(domain): parse_glossary_master_terms + render_glossary_markdown_table

Remonte dans le domaine le parsing du glossaire master et le rendu Markdown
(jusqu'ici dans app/glossary_reconciler), pour reutilisation par le pipeline et
la pedagogie sans violer les couches.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
'@
```

---

## Task 2 : la pédagogie lit le glossaire sur disque

**Files:**
- Modify : `src/fahmi2/pedagogy/sources.py`
- Modify : `src/fahmi2/app/supports_orchestrator.py`
- Modify : `tests/unit/pedagogy/test_sources.py`
- Modify : `tests/unit/app/test_supports_orchestrator.py`

- [ ] **Step 1 : Test du helper de lecture disque (échoue)**

Ajouter à `tests/unit/pedagogy/test_sources.py` (imports en tête à compléter :
`from fahmi2.pedagogy.sources import load_glossary_master_terms` et
`from fahmi2.infra.storage.fs_artifacts import FsArtifactStore`, `import json`) :

```python
def test_load_glossary_master_terms_reads_disk(tmp_path: Path) -> None:
    gen_dir = tmp_path / "generation"
    FsArtifactStore().write_json_atomic(
        gen_dir / "glossary_master.json",
        {"terms": [{"term": "PIB", "definition": "produit intérieur brut"}]},
    )
    terms = load_glossary_master_terms(gen_dir)
    assert len(terms) == 1
    assert terms[0].term == "PIB"


def test_load_glossary_master_terms_absent_returns_empty(tmp_path: Path) -> None:
    assert load_glossary_master_terms(tmp_path / "generation") == ()
```

- [ ] **Step 2 : Lancer, vérifier l'échec**

Run : `.venv\Scripts\python.exe -m pytest tests/unit/pedagogy/test_sources.py -v`
Attendu : ÉCHEC (`ImportError: ... load_glossary_master_terms`).

- [ ] **Step 3 : Implémenter `load_glossary_master_terms` dans `pedagogy/sources.py`**

En tête de `sources.py`, ajouter aux imports :

```python
import json
```

et après les imports existants :

```python
from fahmi2.domain.glossary import Term, parse_glossary_master_terms
```

Ajouter la constante (après `_ENCODING_UTF8`) :

```python
_GLOSSARY_MASTER_FILENAME = "glossary_master.json"
```

Ajouter la fonction (à la fin du fichier) :

```python
def load_glossary_master_terms(generation_dir: Path) -> tuple[Term, ...]:
    """Charge le glossaire master (langue source) depuis le disque.

    Lit ``<generation_dir>/glossary_master.json`` produit par la phase 2 — comme
    le pipeline (``load_glossary_master``). Sert l'injection terminologique des
    prompts des générateurs LLM.

    Args:
        generation_dir: Dossier de travail de la génération (contient le master).

    Returns:
        Les termes (tuple vide si le master n'existe pas).
    """
    path = generation_dir / _GLOSSARY_MASTER_FILENAME
    if not path.exists():
        return ()
    payload = json.loads(path.read_text(encoding=_ENCODING_UTF8))
    return parse_glossary_master_terms(payload)
```

- [ ] **Step 4 : Brancher l'orchestrateur sur le disque**

Dans `src/fahmi2/app/supports_orchestrator.py` :

Ajouter à l'import de `pedagogy.sources` :

```python
from fahmi2.pedagogy.sources import (
    consolidated_doc_path,
    load_chapters,
    load_glossary_master_terms,
    source_mtime_ns,
)
```
(adapter à l'import existant `from fahmi2.pedagogy.sources import load_chapters, source_mtime_ns`).

Remplacer la méthode `_load_glossary` :

```python
    def _load_glossary(self, project: Project, language: Language) -> tuple[Term, ...]:
        """Charge le glossaire de la langue depuis le dernier run COMPLETED.
        ...
        """
        run = self._project_service.get_last_completed_run(project.id)
        if run is None:
            return ()
        return tuple(self._state.list_glossary_terms(run.id, language))
```

par :

```python
    def _load_glossary(self, project: Project) -> tuple[Term, ...]:
        """Charge le glossaire master (langue source) depuis le disque.

        Lit ``<workspace>/generation/glossary_master.json`` — comme le pipeline.
        Sert l'injection terminologique des prompts.

        Args:
            project: Projet.

        Returns:
            Les termes du glossaire master (vide si absent).
        """
        generation_dir = project.workspace_folder / GENERATION_WORKSPACE_SUBDIR
        return load_glossary_master_terms(generation_dir)
```

Dans `generate`, sortir le chargement du glossaire de la boucle des langues
(il est indépendant de la langue) :

```python
        any_failure = False
        total_cost = 0.0
        glossary = self._load_glossary(project)
        try:
            for language in pedagogy.languages:
                source_mtime = source_mtime_ns(ctx.generation_output_dir, language)
                chapters = load_chapters(ctx.generation_output_dir, language)
                for support_type in self._registry.canonical_order():
```

(supprimer la ligne `glossary = self._load_glossary(project, language)` qui était
dans la boucle).

- [ ] **Step 5 : Adapter le seed de `test_supports_orchestrator.py`**

Dans `tests/unit/app/test_supports_orchestrator.py`, remplacer
`_seed_completed_run_with_glossary` :

```python
def _seed_completed_run_with_glossary(
    state: SqliteState, project_id: ProjectId, settings: Any
) -> None:
    run = Run(
        id=RunId.new(),
        project_id=project_id,
        started_at=datetime.now(tz=UTC),
        status=RunStatus.COMPLETED,
        settings_snapshot=settings,
    )
    state.upsert_run(run)
    state.upsert_glossary_term(
        run.id, Language.FR, Term(term="PIB", definition="Produit intérieur brut")
    )
```

par (le glossaire vit désormais sur disque) :

```python
def _seed_completed_run(state: SqliteState, project_id: ProjectId, settings: Any) -> None:
    state.upsert_run(
        Run(
            id=RunId.new(),
            project_id=project_id,
            started_at=datetime.now(tz=UTC),
            status=RunStatus.COMPLETED,
            settings_snapshot=settings,
        )
    )


def _write_glossary_master(ws: Path) -> None:
    FsArtifactStore().write_json_atomic(
        ws / GENERATION_WORKSPACE_SUBDIR / "glossary_master.json",
        {"terms": [{"term": "PIB", "definition": "Produit intérieur brut"}]},
    )
```

Puis, dans les tests qui appelaient `_seed_completed_run_with_glossary(state, project.id, settings)`,
remplacer par les deux appels `_seed_completed_run(state, project.id, settings)` **et**
`_write_glossary_master(ws)` (le `ws` du test = `tmp_path / "ws"`, qui est
`workspace_folder`). Vérifier chaque occurrence (`grep _seed_completed_run_with_glossary`).

- [ ] **Step 6 : Lancer les tests pédagogie/orchestrateur**

Run : `.venv\Scripts\python.exe -m pytest tests/unit/pedagogy/test_sources.py tests/unit/app/test_supports_orchestrator.py -v`
Attendu : PASS (le glossaire lu sur disque alimente les flashcards et l'injection).

- [ ] **Step 7 : Vérifs + commit**

```powershell
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m mypy src tests
git add src/fahmi2/pedagogy/sources.py src/fahmi2/app/supports_orchestrator.py tests/unit/pedagogy/test_sources.py tests/unit/app/test_supports_orchestrator.py
git commit -m @'
feat(pedagogy): lire le glossaire sur disque (comme le pipeline)

L'orchestrateur lit glossary_master.json sur disque (load_glossary_master_terms)
au lieu de la table glossary_terms (jamais peuplee). Corrige les flashcards de
glossaire vides et l'injection terminologique vide des prompts LLM.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
'@
```

---

## Task 3 : retrait de l'anomalie DB

**Files:**
- Modify : `src/fahmi2/infra/storage/_schema.sql`
- Modify : `src/fahmi2/infra/storage/sqlite_state.py`
- Delete : `src/fahmi2/app/glossary_reconciler.py`
- Delete : `tests/unit/app/test_glossary_reconciler.py`
- Modify : `src/fahmi2/pipeline/handlers/phase_6_translation.py`
- Modify : `tests/unit/infra/storage/test_sqlite_state.py`
- Modify : `tests/unit/ui/test_pedagogy_controller.py`

- [ ] **Step 1 : Retirer la table du schéma**

Dans `src/fahmi2/infra/storage/_schema.sql`, **supprimer** le bloc
`CREATE TABLE IF NOT EXISTS glossary_terms (...)` et l'index
`idx_glossary_run_lang` (lignes 60–75).

- [ ] **Step 2 : Migration de suppression + nettoyage `sqlite_state`**

Dans `_apply_soft_migrations`, remplacer le bloc de colonnes `glossary_terms` :

```python
        existing_cols = {
            row[1]
            for row in conn.execute("PRAGMA table_info(glossary_terms)").fetchall()
        }
        if "acronym" not in existing_cols:
            conn.execute("ALTER TABLE glossary_terms ADD COLUMN acronym TEXT")
        if "acronym_expansion" not in existing_cols:
            conn.execute(
                "ALTER TABLE glossary_terms ADD COLUMN acronym_expansion TEXT"
            )
```

par :

```python
        # La table glossary_terms (intention de socle jamais branchee) est
        # retiree : le glossaire est lu sur disque comme les autres documents
        # generes (glossary_master.json).
        conn.execute("DROP TABLE IF EXISTS glossary_terms")
```

Supprimer les méthodes `upsert_glossary_term` (et son docstring) et
`list_glossary_terms`, ainsi que le helper `_row_to_term`. Lancer ensuite
`ruff --fix` pour retirer les imports devenus inutiles (`Term`, `VideoId`,
`Iterable`… s'ils ne servent plus ailleurs dans le module).

- [ ] **Step 3 : Supprimer `GlossaryReconciler` + adapter la phase 6**

Supprimer `src/fahmi2/app/glossary_reconciler.py` (la fonction
`render_glossary_markdown_table` et le parsing sont désormais dans `domain/glossary`).

```powershell
git rm src/fahmi2/app/glossary_reconciler.py tests/unit/app/test_glossary_reconciler.py
```

Dans `src/fahmi2/pipeline/handlers/phase_6_translation.py`, dans `_render_glossary_md`,
remplacer les deux imports locaux :

```python
    from fahmi2.app.glossary_reconciler import render_glossary_markdown_table  # noqa: PLC0415
    from fahmi2.domain.glossary import Term  # noqa: PLC0415
```

par :

```python
    from fahmi2.domain.glossary import Term, render_glossary_markdown_table  # noqa: PLC0415
```

- [ ] **Step 4 : Retirer les tests DB glossaire**

Dans `tests/unit/infra/storage/test_sqlite_state.py`, supprimer la section
« Tests glossary » : `test_upsert_and_list_glossary_terms` et
`test_glossary_terms_filtered_by_language` (lignes ~280–324) ; lancer `ruff --fix`
pour les imports inutiles (`Term`, `VideoId` s'ils ne servent plus).

Dans `tests/unit/ui/test_pedagogy_controller.py`, remplacer
`_seed_completed_run_with_glossary` (qui appelle `upsert_glossary_term`) par un seed
disque, et ses appels :

```python
def _write_glossary_master(ws: Path) -> None:
    FsArtifactStore().write_json_atomic(
        ws / GENERATION_WORKSPACE_SUBDIR / "glossary_master.json",
        {"terms": [{"term": "PIB", "definition": "Produit intérieur brut"}]},
    )
```

(supprimer `_seed_completed_run_with_glossary` ; aux endroits qui l'utilisaient,
appeler `_seed_completed_run(...)` puis `_write_glossary_master(ws)`). Retirer les
imports devenus inutiles (`Term`, `Language` si plus utilisés) via `ruff --fix`.

- [ ] **Step 5 : Lancer toute la suite, vérifier le vert**

```powershell
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m mypy src tests
```
Attendu : tout vert (aucune référence à `glossary_terms` / `GlossaryReconciler`
restante hors du domaine).

- [ ] **Step 6 : Commit**

```powershell
git add -A
git commit -m @'
refactor(storage): retirer l'anomalie glossary_terms (table + GlossaryReconciler)

Aucun document genere n'a de table de contenu en DB ; le glossaire suit le meme
traitement (artefact disque + PhaseExecution). Supprime la table glossary_terms,
upsert/list_glossary_terms, le GlossaryReconciler (code mort jamais branche) ;
la phase 6 importe render_glossary_markdown_table depuis le domaine.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
'@
```

---

## Clôture du Lot 1b

- [ ] `CHANGELOG.md` (Non publié) : section « Corrigé » (flashcards de glossaire +
  injection terminologique non vides) et « Supprimé » (table `glossary_terms` +
  `GlossaryReconciler`). Commit `docs(changelog): Lot 1b (glossaire sur disque)`.
- [ ] Le **Lot 1c** (retrait `flashcards_glossary` + #4) fera l'objet de son propre plan.

## Self-review

Couvre §3 du spec : lecture disque (Task 2), retrait table + reconciler (Task 3),
parsing/rendu en domaine (Task 1, respecte les couches : pédagogie→domaine OK,
pipeline→domaine OK). Pas de placeholder : code exact, chemins exacts. Types
cohérents (`Term`, `parse_glossary_master_terms`, `render_glossary_markdown_table`,
`load_glossary_master_terms(generation_dir)`). Effet de bord positif documenté
(injection LLM non vide). `_load_glossary` perd son paramètre `language` (master =
langue source) ; le seul appelant est mis à jour (chargement hors boucle).
