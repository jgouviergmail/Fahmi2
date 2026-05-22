# Export granulaire (pédagogie) + export documentaire Génération — Plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Exporter chaque support pédagogique en **un fichier par support/corrigé** (MD/PDF/HTML) et ajouter à la **Génération** un export documentaire MD/PDF/HTML (consolidé + glossaire séparés par langue), via un cœur d'écriture partagé.

**Architecture :** Approche « A, prête-pour-C » (cf. spec `docs/superpowers/specs/2026-05-22-export-granulaire-et-generation-design.md`). Un cœur `app/document_export.write_documents` écrit une liste `(stem, markdown)` à l'extension d'un `ExportFormat` ; chaque fonctionnalité fournit un **collecteur**. `infra/export/markdown_pdf` reste un pur *renderer* ; le dispatch de format vit dans la couche app. L'UI partage `ui/_export_ui` (choix format + écriture/erreurs/log).

**Tech Stack :** Python 3.12, PySide6, fpdf2, `markdown`, pytest / pytest-qt, ruff, mypy --strict.

**Conventions de vérification (CLAUDE.md) :** à la fin de chaque tâche **et** en clôture, les trois doivent être verts :
- `.venv\Scripts\python.exe -m pytest`
- `.venv\Scripts\python.exe -m ruff check .`
- `.venv\Scripts\python.exe -m mypy src tests`

Tout en français (code, docstrings, messages), Google-style docstrings, pas de magic value (constantes centralisées).

**Branche :** `feat/export-granulaire-generation` (déjà créée depuis `main`).

---

## Ordre des tâches (chaque tâche se termine verte)

1. Cœur partagé `app/document_export.py` + `EXTENSION_BY_FORMAT`.
2. Domaine : `glossary_doc_filename` + refactor phase 6 + `GenerationSettings.export_formats` + fixture.
3. Module `app/generation_export.py`.
4. Persistance : (dé)sérialisation de `export_formats`.
5. Helper UI partagé `ui/_export_ui.py`.
6. Refactor export pédagogie (1 fichier/support) + bascule du contrôleur.
7. UI Génération : page Export des réglages + bouton + handler.
8. Suppression de `assemble_markdown` (devenu mort) + ses tests.
9. Documentation + CHANGELOG.
10. Vérification finale complète.

---

### Task 1 : Cœur d'écriture partagé `app/document_export.py`

**Files:**
- Modify: `src/fahmi2/infra/export/markdown_pdf.py` (ajout import + constante)
- Create: `src/fahmi2/app/document_export.py`
- Test: `tests/unit/app/test_document_export.py`

- [ ] **Step 1 : Ajouter `EXTENSION_BY_FORMAT` dans `markdown_pdf.py`**

Ajouter l'import (après la ligne `from fahmi2.core.errors.severity import Severity`) :

```python
from fahmi2.domain.enums import ExportFormat
```

Ajouter la constante juste après ce bloc d'imports (avant `_PDF_HEADING_COLOR`) :

```python
#: Extension de fichier par format documentaire (MD/PDF/HTML ; APKG non concerné).
EXTENSION_BY_FORMAT: dict[ExportFormat, str] = {
    ExportFormat.MARKDOWN: ".md",
    ExportFormat.PDF: ".pdf",
    ExportFormat.HTML: ".html",
}
```

- [ ] **Step 2 : Écrire le test du cœur** — `tests/unit/app/test_document_export.py`

```python
"""Tests du cœur d'écriture documentaire partagé (``write_documents``)."""

from __future__ import annotations

from pathlib import Path

import pytest

from fahmi2.app.document_export import DocumentExportResult, write_documents
from fahmi2.domain.enums import ExportFormat
from fahmi2.infra.export.markdown_pdf import EXTENSION_BY_FORMAT, pdf_fonts_available


def test_extension_by_format_doc_formats_only() -> None:
    assert EXTENSION_BY_FORMAT == {
        ExportFormat.MARKDOWN: ".md",
        ExportFormat.PDF: ".pdf",
        ExportFormat.HTML: ".html",
    }
    assert ExportFormat.APKG not in EXTENSION_BY_FORMAT


def test_write_markdown_copies_content_and_preserves_order(tmp_path: Path) -> None:
    docs = [("a", "# A\n\nun"), ("b", "# B\n\ndeux")]
    result = write_documents(docs, output_dir=tmp_path, fmt=ExportFormat.MARKDOWN)
    assert result.document_count == 2
    assert result.output_paths == (tmp_path / "a.md", tmp_path / "b.md")
    assert (tmp_path / "a.md").read_text(encoding="utf-8") == "# A\n\nun"


def test_write_html_renders_self_contained(tmp_path: Path) -> None:
    result = write_documents(
        [("doc", "# Titre\n\n- x\n")], output_dir=tmp_path, fmt=ExportFormat.HTML
    )
    assert result.document_count == 1
    content = (tmp_path / "doc.html").read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in content
    assert "<h1>" in content


def test_write_rejects_non_document_format(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="non documentaire"):
        write_documents([("a", "x")], output_dir=tmp_path, fmt=ExportFormat.APKG)


@pytest.mark.skipif(not pdf_fonts_available(), reason="Police Unicode indisponible")
def test_write_pdf(tmp_path: Path) -> None:
    result = write_documents(
        [("doc", "# Titre\n\ntexte\n")], output_dir=tmp_path, fmt=ExportFormat.PDF
    )
    assert (tmp_path / "doc.pdf").exists()
    assert result.document_count == 1
```

- [ ] **Step 3 : Lancer le test (échec attendu)**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/app/test_document_export.py -q`
Expected: FAIL (`ModuleNotFoundError: fahmi2.app.document_export`).

- [ ] **Step 4 : Créer `src/fahmi2/app/document_export.py`**

```python
"""Cœur d'écriture générique des exports documentaires (Markdown / PDF / HTML).

Contrat partagé par les fonctionnalités (génération, pédagogie) : un collecteur
fournit une liste ``(stem, markdown)`` ; ``write_documents`` écrit un fichier par
couple, à l'extension du format demandé. Le **dispatch** par format vit ici (couche
app) ; ``infra/export/markdown_pdf`` reste un pur *renderer*.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

from fahmi2.domain.enums import ExportFormat
from fahmi2.domain.project import Project
from fahmi2.infra.export.markdown_pdf import (
    EXTENSION_BY_FORMAT,
    render_markdown_to_html,
    render_markdown_to_pdf,
)
from fahmi2.infra.storage.fs_artifacts import FsArtifactStore

#: Signature d'un collecteur : ``(project) -> [(stem, markdown), …]`` (stem sans
#: extension). Contrat « prêt-pour-C » : un futur ``DocumentSource.collect()``
#: n'aurait qu'à envelopper une telle fonction.
DocumentCollector = Callable[[Project], list[tuple[str, str]]]


@dataclass(frozen=True)
class DocumentExportResult:
    """Résultat d'un export documentaire (Markdown / PDF / HTML).

    Attributes:
        output_paths: Chemins des documents écrits.
    """

    output_paths: tuple[Path, ...]

    @property
    def document_count(self) -> int:
        """Nombre de documents écrits.

        Returns:
            Le nombre de fichiers produits.
        """
        return len(self.output_paths)


def write_documents(
    documents: Iterable[tuple[str, str]],
    *,
    output_dir: Path,
    fmt: ExportFormat,
) -> DocumentExportResult:
    """Écrit un fichier par ``(stem, markdown)`` à l'extension du format.

    Args:
        documents: Couples ``(stem, markdown)`` (stem sans extension).
        output_dir: Dossier de destination.
        fmt: Format documentaire (``MARKDOWN``, ``PDF`` ou ``HTML``).

    Returns:
        ``DocumentExportResult`` (chemins écrits, ordre d'entrée préservé).

    Raises:
        ValueError: Si ``fmt`` n'est pas un format documentaire (ex. ``APKG``).
        ConfigError: ``EXPORT.NO_PDF_FONT`` en PDF sans police Unicode.
    """
    if fmt not in EXTENSION_BY_FORMAT:
        raise ValueError(f"Format non documentaire : {fmt}")
    extension = EXTENSION_BY_FORMAT[fmt]
    store = FsArtifactStore()
    paths: list[Path] = []
    for stem, markdown_text in documents:
        path = output_dir / f"{stem}{extension}"
        if fmt is ExportFormat.MARKDOWN:
            store.write_text_atomic(path, markdown_text)
        elif fmt is ExportFormat.PDF:
            render_markdown_to_pdf(markdown_text, path)
        else:  # HTML (seul format documentaire restant après la garde)
            render_markdown_to_html(markdown_text, path)
        paths.append(path)
    return DocumentExportResult(output_paths=tuple(paths))
```

- [ ] **Step 5 : Lancer le test (succès attendu)**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/app/test_document_export.py -q`
Expected: PASS (les cas PDF passent si la police Arial est présente, sinon `skip`).

- [ ] **Step 6 : Qualité + commit**

```bash
.venv\Scripts\python.exe -m ruff check . && .venv\Scripts\python.exe -m mypy src tests
git add src/fahmi2/infra/export/markdown_pdf.py src/fahmi2/app/document_export.py tests/unit/app/test_document_export.py
git commit -m "feat(app/export): coeur d'ecriture documentaire partage (write_documents)"
```

---

### Task 2 : Domaine — `glossary_doc_filename`, refactor phase 6, `GenerationSettings.export_formats`

**Files:**
- Modify: `src/fahmi2/domain/generation.py`
- Modify: `src/fahmi2/pipeline/handlers/phase_6_translation.py:181`
- Modify: `tests/conftest.py`
- Test: `tests/unit/domain/test_generation.py`

- [ ] **Step 1 : Écrire les tests domaine** — ajouter à `tests/unit/domain/test_generation.py`

```python
def test_glossary_doc_filename() -> None:
    from fahmi2.domain.enums import Language
    from fahmi2.domain.generation import glossary_doc_filename

    assert glossary_doc_filename(Language.FR) == "glossary.fr.md"
    assert glossary_doc_filename(Language.EN) == "glossary.en.md"


def test_export_formats_defaults_empty(make_generation_settings: Any) -> None:
    gen = make_generation_settings()
    assert gen.export_formats == frozenset()


def test_export_formats_rejects_apkg(make_generation_settings: Any) -> None:
    import pytest

    from fahmi2.domain.enums import ExportFormat

    with pytest.raises(ValueError, match="subset"):
        make_generation_settings(export_formats=frozenset({ExportFormat.APKG}))


def test_export_formats_accepts_doc_formats(make_generation_settings: Any) -> None:
    from fahmi2.domain.enums import ExportFormat

    gen = make_generation_settings(
        export_formats=frozenset({ExportFormat.PDF, ExportFormat.HTML})
    )
    assert gen.export_formats == frozenset({ExportFormat.PDF, ExportFormat.HTML})
```

Vérifier que `Any` est importé en tête de `test_generation.py` (`from typing import Any`) ; l'ajouter sinon.

- [ ] **Step 2 : Lancer (échec attendu)**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/domain/test_generation.py -q`
Expected: FAIL (`glossary_doc_filename` absent ; `export_formats` inconnu).

- [ ] **Step 3 : Modifier `domain/generation.py` — import `ExportFormat`**

Remplacer le bloc d'import des enums :

```python
from fahmi2.domain.enums import (
    Language,
    LLMModel,
    PhaseId,
    SttProvider,
    StylePreset,
)
```

par :

```python
from fahmi2.domain.enums import (
    ExportFormat,
    Language,
    LLMModel,
    PhaseId,
    SttProvider,
    StylePreset,
)
```

- [ ] **Step 4 : Ajouter le helper + les constantes**

Après la fonction `consolidated_doc_filename` (juste avant `@dataclass(frozen=True) class ParallelismConfig`), ajouter :

```python
def glossary_doc_filename(language: Language) -> str:
    """Nom de fichier du glossaire pour une langue.

    Args:
        language: Langue cible.

    Returns:
        Le nom de fichier (ex: ``"glossary.fr.md"``).
    """
    return f"glossary.{language}.md"


#: Formats d'export documentaire autorisés en génération (pas d'APKG : pas de cartes).
GENERATION_EXPORT_FORMATS: frozenset[ExportFormat] = frozenset(
    {ExportFormat.MARKDOWN, ExportFormat.PDF, ExportFormat.HTML}
)

#: Formats cochés par défaut pour un nouveau projet (vide = opt-in).
DEFAULT_GENERATION_EXPORT_FORMATS: frozenset[ExportFormat] = frozenset()
```

- [ ] **Step 5 : Ajouter le champ + l'invariant à `GenerationSettings`**

Dans la docstring `Attributes:`, ajouter après `delete_audio_after_stt: …` :

```python
        export_formats: Formats d'export documentaire (sous-ensemble de
            {MARKDOWN, PDF, HTML} ; vide par défaut).
```

Ajouter le champ après `delete_audio_after_stt: bool` :

```python
    delete_audio_after_stt: bool
    export_formats: frozenset[ExportFormat] = DEFAULT_GENERATION_EXPORT_FORMATS
```

À la fin de `__post_init__` (après le bloc `cost_ceiling_usd`), ajouter :

```python
        if not self.export_formats <= GENERATION_EXPORT_FORMATS:
            invalid = sorted(
                f.value for f in self.export_formats - GENERATION_EXPORT_FORMATS
            )
            raise ValueError(
                f"export_formats must be a subset of {{markdown, pdf, html}}; "
                f"got invalid: {invalid}"
            )
```

- [ ] **Step 6 : Refactor `phase_6_translation.py` (suppression du nom codé en dur)**

Ajouter `glossary_doc_filename` à l'import existant (ligne 28 — `from fahmi2.domain.generation import consolidated_doc_filename`) :

```python
from fahmi2.domain.generation import consolidated_doc_filename, glossary_doc_filename
```

Remplacer la ligne 181 :

```python
        glossary_target = ctx.output_dir / f"glossary.{target.value}.md"
```

par :

```python
        glossary_target = ctx.output_dir / glossary_doc_filename(target)
```

- [ ] **Step 7 : Mettre à jour la fixture `make_generation_settings`**

Dans `tests/conftest.py`, ajouter au dict `base` (après `"delete_audio_after_stt": True,`) :

```python
            "export_formats": frozenset(),
```

- [ ] **Step 8 : Lancer (succès attendu)**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/domain/test_generation.py tests/unit/pipeline/handlers/test_phase_6_translation.py -q`
Expected: PASS (le glossaire reste `glossary.{lang}.md` ; helpers/invariant OK).

- [ ] **Step 9 : Qualité + commit**

```bash
.venv\Scripts\python.exe -m ruff check . && .venv\Scripts\python.exe -m mypy src tests
git add src/fahmi2/domain/generation.py src/fahmi2/pipeline/handlers/phase_6_translation.py tests/conftest.py tests/unit/domain/test_generation.py
git commit -m "feat(domain): glossary_doc_filename + GenerationSettings.export_formats (opt-in)"
```

---

### Task 3 : Module d'export Génération `app/generation_export.py`

**Files:**
- Create: `src/fahmi2/app/generation_export.py`
- Test: `tests/unit/app/test_generation_export.py`

- [ ] **Step 1 : Écrire le test** — `tests/unit/app/test_generation_export.py`

```python
"""Tests de l'export documentaire de la Génération (consolidé + glossaire)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from fahmi2.app.generation_export import (
    collect_generation_documents,
    export_generation_documents,
)
from fahmi2.domain.enums import ExportFormat
from fahmi2.domain.generation import (
    GENERATION_OUTPUT_SUBDIR,
    GENERATION_WORKSPACE_SUBDIR,
)
from fahmi2.domain.ids import ProjectId
from fahmi2.domain.project import Project
from fahmi2.infra.export.markdown_pdf import pdf_fonts_available
from fahmi2.infra.storage.fs_artifacts import FsArtifactStore


def _project(tmp_path: Path) -> Project:
    return Project(
        id=ProjectId.new(),
        name="Cours",
        workspace_folder=tmp_path / "ws",
        created_at=datetime.now(tz=UTC),
        generation=None,
    )


def _seed_output(project: Project) -> Path:
    out = (
        project.workspace_folder
        / GENERATION_WORKSPACE_SUBDIR
        / GENERATION_OUTPUT_SUBDIR
    )
    store = FsArtifactStore()
    store.write_text_atomic(out / "consolidated.fr.md", "# Cours (fr)\n\nCorps.\n")
    store.write_text_atomic(out / "glossary.fr.md", "# Glossaire (fr)\n\n| T | D |\n")
    return out


def test_collect_returns_consolidated_then_glossary(tmp_path: Path) -> None:
    project = _project(tmp_path)
    _seed_output(project)
    stems = [stem for stem, _ in collect_generation_documents(project)]
    assert stems == ["consolidated.fr", "glossary.fr"]


def test_collect_empty_when_no_output(tmp_path: Path) -> None:
    # generation=None et aucun fichier : liste vide (pas de crash).
    assert collect_generation_documents(_project(tmp_path)) == []


def test_export_markdown_writes_separate_files(tmp_path: Path) -> None:
    project = _project(tmp_path)
    _seed_output(project)
    out_dir = tmp_path / "export"
    result = export_generation_documents(
        project, output_dir=out_dir, fmt=ExportFormat.MARKDOWN
    )
    assert (out_dir / "consolidated.fr.md").exists()
    assert (out_dir / "glossary.fr.md").exists()
    assert result.document_count == 2


@pytest.mark.skipif(not pdf_fonts_available(), reason="Police Unicode indisponible")
def test_export_pdf(tmp_path: Path) -> None:
    project = _project(tmp_path)
    _seed_output(project)
    out_dir = tmp_path / "export"
    result = export_generation_documents(
        project, output_dir=out_dir, fmt=ExportFormat.PDF
    )
    assert (out_dir / "consolidated.fr.pdf").exists()
    assert (out_dir / "glossary.fr.pdf").exists()
    assert result.document_count == 2
```

- [ ] **Step 2 : Lancer (échec attendu)**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/app/test_generation_export.py -q`
Expected: FAIL (`fahmi2.app.generation_export` absent).

- [ ] **Step 3 : Créer `src/fahmi2/app/generation_export.py`**

```python
"""Export documentaire des livrables de la Génération (consolidé + glossaire).

Lit sur disque les documents finaux de la génération (``consolidated.{lang}.md`` et
``glossary.{lang}.md`` par langue) et délègue à ``app.document_export.write_documents``
pour produire un fichier par document et par langue, dans le format demandé.
"""

from __future__ import annotations

from pathlib import Path

from fahmi2.app.document_export import DocumentExportResult, write_documents
from fahmi2.domain.enums import ExportFormat, Language
from fahmi2.domain.generation import (
    GENERATION_OUTPUT_SUBDIR,
    GENERATION_WORKSPACE_SUBDIR,
    consolidated_doc_filename,
    glossary_doc_filename,
)
from fahmi2.domain.project import Project

_MD_EXT = ".md"
_ENCODING_UTF8 = "utf-8"


def collect_generation_documents(project: Project) -> list[tuple[str, str]]:
    """Collecte les documents de génération présents sur disque (par langue).

    Itère toutes les langues (robuste : ne dépend pas de ``project.generation``,
    qui peut être ``None``) et retient les fichiers réellement présents.

    Args:
        project: Projet (résout le dossier de sortie de génération).

    Returns:
        Liste de ``(stem, markdown)`` : pour chaque langue, le consolidé puis le
        glossaire s'ils existent. ``stem`` = nom de fichier privé de ``.md``.
    """
    output_dir = (
        project.workspace_folder
        / GENERATION_WORKSPACE_SUBDIR
        / GENERATION_OUTPUT_SUBDIR
    )
    documents: list[tuple[str, str]] = []
    for language in Language:
        for filename in (
            consolidated_doc_filename(language),
            glossary_doc_filename(language),
        ):
            path = output_dir / filename
            if path.exists():
                stem = filename[: -len(_MD_EXT)]
                documents.append((stem, path.read_text(encoding=_ENCODING_UTF8)))
    return documents


def export_generation_documents(
    project: Project, *, output_dir: Path, fmt: ExportFormat
) -> DocumentExportResult:
    """Exporte les documents de génération dans le format demandé.

    Args:
        project: Projet.
        output_dir: Dossier de destination choisi par l'utilisateur (distinct du
            dossier de sortie de génération).
        fmt: Format documentaire (``MARKDOWN`` / ``PDF`` / ``HTML``).

    Returns:
        ``DocumentExportResult``.

    Raises:
        ValueError: Si ``fmt`` n'est pas documentaire.
        ConfigError: ``EXPORT.NO_PDF_FONT`` en PDF sans police Unicode.
    """
    return write_documents(
        collect_generation_documents(project), output_dir=output_dir, fmt=fmt
    )
```

- [ ] **Step 4 : Lancer (succès attendu)**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/app/test_generation_export.py -q`
Expected: PASS.

- [ ] **Step 5 : Qualité + commit**

```bash
.venv\Scripts\python.exe -m ruff check . && .venv\Scripts\python.exe -m mypy src tests
git add src/fahmi2/app/generation_export.py tests/unit/app/test_generation_export.py
git commit -m "feat(app/export): export documentaire de la generation (consolide + glossaire)"
```

---

### Task 4 : Persistance de `export_formats`

**Files:**
- Modify: `src/fahmi2/infra/storage/sqlite_state.py` (`_serialize_generation_settings`, `_deserialize_generation_settings`)
- Test: `tests/unit/infra/storage/test_sqlite_state.py`

- [ ] **Step 1 : Écrire les tests** — ajouter à `tests/unit/infra/storage/test_sqlite_state.py`

```python
def test_generation_export_formats_round_trip(
    tmp_path: Path, make_project: Any, make_generation_settings: Any
) -> None:
    from fahmi2.domain.enums import ExportFormat

    state = SqliteState(tmp_path / "db.sqlite")
    project = make_project(
        generation=make_generation_settings(
            export_formats=frozenset({ExportFormat.PDF, ExportFormat.HTML})
        )
    )
    state.upsert_project(project)
    loaded = state.get_project(project.id)
    assert loaded is not None
    assert loaded.generation is not None
    assert loaded.generation.export_formats == frozenset(
        {ExportFormat.PDF, ExportFormat.HTML}
    )


def test_generation_deserialize_lenient_without_export_formats(
    tmp_path: Path, make_generation_settings: Any
) -> None:
    # Un blob v2 antérieur (sans export_formats) retombe sur l'ensemble vide.
    from fahmi2.infra.storage.sqlite_state import (
        _deserialize_generation_settings,
        _serialize_generation_settings,
    )

    payload = _serialize_generation_settings(make_generation_settings())
    del payload["export_formats"]
    gen = _deserialize_generation_settings(payload)
    assert gen.export_formats == frozenset()
```

Adapter les noms `upsert_project` / `get_project` à ceux réellement utilisés dans ce fichier de test (reprendre un test existant de round-trip de projet comme modèle ; la logique d'assertion sur `export_formats` reste identique).

- [ ] **Step 2 : Lancer (échec attendu)**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/infra/storage/test_sqlite_state.py -k export_formats -q`
Expected: FAIL (`export_formats` non sérialisé / non lu → vide au round-trip non-lenient, KeyError évité mais la 1ʳᵉ assertion échoue).

- [ ] **Step 3 : Sérialiser** — dans `_serialize_generation_settings`, ajouter la clé après `"delete_audio_after_stt": gen.delete_audio_after_stt,` :

```python
        "delete_audio_after_stt": gen.delete_audio_after_stt,
        "export_formats": sorted(f.value for f in gen.export_formats),
```

- [ ] **Step 4 : Désérialiser (lenient)** — dans `_deserialize_generation_settings`, le `return GenerationSettings(...)` se termine par `delete_audio_after_stt=payload["delete_audio_after_stt"],`. Ajouter juste après cette ligne (avant la parenthèse fermante) :

```python
        delete_audio_after_stt=payload["delete_audio_after_stt"],
        export_formats=frozenset(
            ExportFormat(f) for f in payload.get("export_formats", [])
        ),
```

`ExportFormat` est déjà importé dans ce module (utilisé par la pédagogie).

- [ ] **Step 5 : Lancer (succès attendu)**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/infra/storage/test_sqlite_state.py -q`
Expected: PASS.

- [ ] **Step 6 : Qualité + commit**

```bash
.venv\Scripts\python.exe -m ruff check . && .venv\Scripts\python.exe -m mypy src tests
git add src/fahmi2/infra/storage/sqlite_state.py tests/unit/infra/storage/test_sqlite_state.py
git commit -m "feat(storage): persistance lenient de GenerationSettings.export_formats"
```

---

### Task 5 : Helper UI partagé `ui/_export_ui.py`

**Files:**
- Create: `src/fahmi2/ui/_export_ui.py`
- Test: `tests/unit/ui/test_export_ui.py`

- [ ] **Step 1 : Écrire le test** — `tests/unit/ui/test_export_ui.py`

```python
"""Tests du helper d'export UI partagé (choix de format + écriture/erreurs/log)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from PySide6.QtWidgets import QWidget
from pytestqt.qtbot import QtBot

from fahmi2.app.document_export import DocumentExportResult
from fahmi2.core.errors.exceptions import ConfigError
from fahmi2.core.errors.severity import Severity
from fahmi2.core.logging.event import LogEvent
from fahmi2.domain.enums import ExportFormat
from fahmi2.ui import _export_ui as mod
from fahmi2.ui._export_ui import choose_export_format, run_document_export
from fahmi2.ui.pedagogy_labels import EXPORT_LABELS
from fahmi2.ui.widgets.logs_dock import LogsDock


def test_choose_returns_none_when_no_format(
    qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
) -> None:
    win = QWidget()
    qtbot.addWidget(win)
    monkeypatch.setattr(mod.QMessageBox, "information", lambda *a, **k: None)
    assert (
        choose_export_format(
            window=win, configured_formats=frozenset(), label_by_format=EXPORT_LABELS
        )
        is None
    )


def test_choose_returns_picked_format(
    qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
) -> None:
    win = QWidget()
    qtbot.addWidget(win)
    monkeypatch.setattr(
        mod.QInputDialog, "getItem", lambda *a, **k: (EXPORT_LABELS[ExportFormat.PDF], True)
    )
    fmt = choose_export_format(
        window=win,
        configured_formats=frozenset({ExportFormat.PDF, ExportFormat.HTML}),
        label_by_format=EXPORT_LABELS,
    )
    assert fmt is ExportFormat.PDF


def test_run_writes_and_logs(
    qtbot: QtBot, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    win = QWidget()
    qtbot.addWidget(win)
    logs = LogsDock(win)
    events: list[LogEvent] = []
    monkeypatch.setattr(logs, "append_event", events.append)
    monkeypatch.setattr(
        mod.QFileDialog, "getExistingDirectory", lambda *a, **k: str(tmp_path)
    )
    monkeypatch.setattr(mod.QMessageBox, "information", lambda *a, **k: None)
    result = DocumentExportResult(output_paths=(tmp_path / "a.md", tmp_path / "b.md"))
    run_document_export(
        window=win, logs_dock=logs, label="Markdown", exporter=lambda d: result
    )
    assert len(events) == 1
    assert events[0].code == "DOCUMENTS_EXPORTED"


def test_run_reports_fahmi2_error(
    qtbot: QtBot, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    win = QWidget()
    qtbot.addWidget(win)
    logs = LogsDock(win)
    captured: list[str] = []
    monkeypatch.setattr(
        mod.QFileDialog, "getExistingDirectory", lambda *a, **k: str(tmp_path)
    )
    monkeypatch.setattr(
        mod.QMessageBox, "critical", lambda *a, **k: captured.append(a[2])
    )

    def _boom(_d: Path) -> DocumentExportResult:
        raise ConfigError(
            code="EXPORT.NO_PDF_FONT", user_message="pas de police", severity=Severity.ERROR
        )

    run_document_export(window=win, logs_dock=logs, label="PDF", exporter=_boom)
    assert captured and "EXPORT.NO_PDF_FONT" in captured[0]
```

- [ ] **Step 2 : Lancer (échec attendu)**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/ui/test_export_ui.py -q`
Expected: FAIL (`fahmi2.ui._export_ui` absent).

- [ ] **Step 3 : Créer `src/fahmi2/ui/_export_ui.py`**

```python
"""Helper UI partagé pour l'export documentaire (génération & pédagogie).

Deux fonctions réutilisables par les contrôleurs :

- ``choose_export_format`` : propose les formats configurés (ou message si aucun).
- ``run_document_export`` : sélectionne un dossier, exécute l'export, gère les
  erreurs, journalise et notifie.

Le routage spécifique (ex. APKG côté pédagogie) reste dans chaque contrôleur.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QInputDialog, QMessageBox, QWidget

from fahmi2.app.document_export import DocumentExportResult
from fahmi2.core.errors.exceptions import Fahmi2Error
from fahmi2.core.errors.severity import Severity
from fahmi2.core.logging.event import LogEvent
from fahmi2.domain.enums import ExportFormat
from fahmi2.ui.widgets.logs_dock import LogsDock

_NO_FORMAT_TITLE = "Aucun format d'export"
_NO_FORMAT_BODY = (
    "Aucun format d'export n'est sélectionné dans les réglages "
    "(⚙ Réglages → Export)."
)
_PICK_TITLE = "Exporter"
_PICK_LABEL = "Format :"
_EMPTY_TITLE = "Rien à exporter"
_EMPTY_BODY = (
    "Aucun document à exporter. Lancez d'abord la génération pour ce projet."
)
_DONE_TITLE = "Export terminé"
_FAIL_TITLE = "Export impossible"
_UNEXPECTED_TITLE = "Erreur inattendue"
_LOG_CODE = "DOCUMENTS_EXPORTED"


def choose_export_format(
    *,
    window: QWidget,
    configured_formats: frozenset[ExportFormat],
    label_by_format: dict[ExportFormat, str],
) -> ExportFormat | None:
    """Demande à l'utilisateur de choisir un format parmi ceux configurés.

    Args:
        window: Fenêtre parente des dialogues.
        configured_formats: Formats cochés dans les réglages.
        label_by_format: Libellés humains par format.

    Returns:
        Le format choisi, ou ``None`` (aucun configuré / annulation).
    """
    formats = [fmt for fmt in ExportFormat if fmt in configured_formats]
    if not formats:
        QMessageBox.information(window, _NO_FORMAT_TITLE, _NO_FORMAT_BODY)
        return None
    by_label = {label_by_format[fmt]: fmt for fmt in formats}
    choice, ok = QInputDialog.getItem(
        window, _PICK_TITLE, _PICK_LABEL, list(by_label), 0, editable=False
    )
    if not ok:
        return None
    return by_label[choice]


def run_document_export(
    *,
    window: QWidget,
    logs_dock: LogsDock,
    label: str,
    exporter: Callable[[Path], DocumentExportResult],
) -> None:
    """Sélectionne un dossier, exécute l'export, gère erreurs + log + message.

    Args:
        window: Fenêtre parente des dialogues.
        logs_dock: Dock de logs (journalise le succès).
        label: Libellé humain du format (messages).
        exporter: ``(output_dir) -> DocumentExportResult``.
    """
    directory = QFileDialog.getExistingDirectory(window, f"Dossier d'export {label}")
    if not directory:
        return
    try:
        result = exporter(Path(directory))
    except Fahmi2Error as exc:
        QMessageBox.critical(
            window, _FAIL_TITLE, f"{exc.code}\n\n{exc.user_message}"
        )
        return
    except Exception as exc:  # noqa: BLE001 — affichage UX puis stop
        QMessageBox.critical(
            window, _UNEXPECTED_TITLE, f"{type(exc).__name__} : {exc}"
        )
        return
    if result.document_count == 0:
        QMessageBox.information(window, _EMPTY_TITLE, _EMPTY_BODY)
        return
    logs_dock.append_event(
        LogEvent(
            timestamp=datetime.now(tz=UTC),
            severity=Severity.INFO,
            code=_LOG_CODE,
            message=(
                f"{result.document_count} document(s) {label} exporté(s) vers "
                f"{directory}"
            ),
        )
    )
    QMessageBox.information(
        window,
        _DONE_TITLE,
        f"{result.document_count} document(s) {label} exporté(s) dans :\n{directory}",
    )
```

- [ ] **Step 4 : Lancer (succès attendu)**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/ui/test_export_ui.py -q`
Expected: PASS.

- [ ] **Step 5 : Qualité + commit**

```bash
.venv\Scripts\python.exe -m ruff check . && .venv\Scripts\python.exe -m mypy src tests
git add src/fahmi2/ui/_export_ui.py tests/unit/ui/test_export_ui.py
git commit -m "feat(ui): helper d'export documentaire partage (choix format + ecriture)"
```

---

### Task 6 : Refactor export pédagogie (1 fichier/support) + bascule du contrôleur

**Files:**
- Modify: `src/fahmi2/app/pedagogy_export.py` (réécriture des fonctions documentaires)
- Modify: `src/fahmi2/ui/pedagogy_controller.py` (bascule sur le helper partagé)
- Test: `tests/unit/app/test_pedagogy_export_documents.py` (réécriture)

- [ ] **Step 1 : Réécrire `tests/unit/app/test_pedagogy_export_documents.py`** (contenu intégral)

```python
"""Tests de l'export documentaire des supports (un fichier par support / corrigé)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from fahmi2.app.pedagogy_export import (
    _EXPORT_SUPPORT_ORDER,
    collect_pedagogy_documents,
    export_pedagogy_documents,
)
from fahmi2.domain.enums import ExportFormat, Language, SupportType
from fahmi2.domain.ids import ProjectId
from fahmi2.domain.pedagogy import PEDAGOGY_WORKSPACE_SUBDIR
from fahmi2.domain.project import Project
from fahmi2.infra.export.markdown_pdf import pdf_fonts_available
from fahmi2.infra.storage.fs_artifacts import FsArtifactStore
from fahmi2.pedagogy.artifact_writer import (
    artifact_correction_markdown_path,
    artifact_markdown_path,
)


def _project(tmp_path: Path, make_pedagogy_settings: Any) -> Project:
    return Project(
        id=ProjectId.new(),
        name="Mon Cours",
        workspace_folder=tmp_path / "ws",
        created_at=datetime.now(tz=UTC),
        pedagogy=make_pedagogy_settings(),
    )


def _seed_markdown(pedagogy_dir: Path) -> None:
    artifacts = FsArtifactStore()
    artifacts.write_text_atomic(
        artifact_markdown_path(
            pedagogy_dir, SupportType.FLASHCARDS_CONCEPTS, Language.FR
        ),
        "# Flashcards — Glossaire (fr)\n\n### PIB\n\nProduit intérieur brut\n",
    )
    artifacts.write_text_atomic(
        artifact_markdown_path(pedagogy_dir, SupportType.QCM, Language.FR),
        "# QCM (fr)\n\n### 1. Q ?\n\n- A. a\n- B. b\n",
    )
    artifacts.write_text_atomic(
        artifact_correction_markdown_path(pedagogy_dir, SupportType.QCM, Language.FR),
        "# QCM — Corrigé (fr)\n\n### 1. Q ?\n\n**Réponse : A**\n",
    )


def test_markdown_one_file_per_support_and_correction(
    tmp_path: Path, make_pedagogy_settings: Any
) -> None:
    project = _project(tmp_path, make_pedagogy_settings)
    _seed_markdown(project.workspace_folder / PEDAGOGY_WORKSPACE_SUBDIR)
    out_dir = tmp_path / "export"
    result = export_pedagogy_documents(
        project, output_dir=out_dir, fmt=ExportFormat.MARKDOWN
    )
    assert (out_dir / "flashcards_concepts.fr.md").exists()
    assert (out_dir / "qcm.fr.md").exists()
    assert (out_dir / "qcm.fr.corrige.md").exists()
    assert result.document_count == 3
    # Plus d'agrégat par langue.
    assert not (out_dir / "supports.fr.md").exists()
    assert "Produit intérieur brut" in (
        out_dir / "flashcards_concepts.fr.md"
    ).read_text(encoding="utf-8")


def test_markdown_empty(tmp_path: Path, make_pedagogy_settings: Any) -> None:
    project = _project(tmp_path, make_pedagogy_settings)
    result = export_pedagogy_documents(
        project, output_dir=tmp_path / "export", fmt=ExportFormat.MARKDOWN
    )
    assert result.document_count == 0


@pytest.mark.skipif(not pdf_fonts_available(), reason="Police Unicode indisponible")
def test_pdf_one_file_per_support(
    tmp_path: Path, make_pedagogy_settings: Any
) -> None:
    project = _project(tmp_path, make_pedagogy_settings)
    _seed_markdown(project.workspace_folder / PEDAGOGY_WORKSPACE_SUBDIR)
    out_dir = tmp_path / "export"
    result = export_pedagogy_documents(
        project, output_dir=out_dir, fmt=ExportFormat.PDF
    )
    assert (out_dir / "flashcards_concepts.fr.pdf").exists()
    assert (out_dir / "qcm.fr.corrige.pdf").exists()
    assert result.document_count == 3


def test_html_self_contained_per_support(
    tmp_path: Path, make_pedagogy_settings: Any
) -> None:
    project = _project(tmp_path, make_pedagogy_settings)
    _seed_markdown(project.workspace_folder / PEDAGOGY_WORKSPACE_SUBDIR)
    out_dir = tmp_path / "export"
    result = export_pedagogy_documents(
        project, output_dir=out_dir, fmt=ExportFormat.HTML
    )
    assert (out_dir / "qcm.fr.html").exists()
    assert (out_dir / "flashcards_concepts.fr.html").exists()
    assert result.document_count == 3
    content = (out_dir / "qcm.fr.html").read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in content
    assert 'charset="utf-8"' in content
    assert "<h1>" in content


def test_collect_order_learning_then_exercises(
    tmp_path: Path, make_pedagogy_settings: Any
) -> None:
    project = _project(tmp_path, make_pedagogy_settings)
    ped_dir = project.workspace_folder / PEDAGOGY_WORKSPACE_SUBDIR
    artifacts = FsArtifactStore()
    for support, body in (
        (SupportType.MOCK_EXAM, "# Examen blanc (fr)\n"),
        (SupportType.QCM, "# QCM (fr)\n"),
        (SupportType.REVISION_SHEET, "# Fiche (fr)\n"),
    ):
        artifacts.write_text_atomic(
            artifact_markdown_path(ped_dir, support, Language.FR), body
        )
    stems = [stem for stem, _ in collect_pedagogy_documents(project)]
    assert stems.index("revision_sheet.fr") < stems.index("qcm.fr")
    assert stems.index("qcm.fr") < stems.index("mock_exam.fr")


def test_export_order_covers_every_support() -> None:
    assert set(_EXPORT_SUPPORT_ORDER) == set(SupportType)
    assert len(_EXPORT_SUPPORT_ORDER) == len(set(_EXPORT_SUPPORT_ORDER))
```

- [ ] **Step 2 : Lancer (échec attendu)**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/app/test_pedagogy_export_documents.py -q`
Expected: FAIL (`collect_pedagogy_documents` / `export_pedagogy_documents` absents).

- [ ] **Step 3 : Réécrire `src/fahmi2/app/pedagogy_export.py`** (contenu intégral)

```python
"""Services d'export des supports pédagogiques (Anki, Markdown, PDF, HTML).

Scanne le dossier ``pedagogy/`` d'un projet et produit des livrables :

- **Anki `.apkg`** : désérialise les artefacts exportables (flashcards, cloze, QCM)
  et délègue à l'adapter ``GenankiExporter``.
- **Markdown / PDF / HTML** : réutilise le Markdown **déjà rendu** (`<support>.md` /
  `<support>.corrige.md`) et produit **un fichier par support** (et par corrigé),
  via ``app.document_export.write_documents``.
"""

from __future__ import annotations

from pathlib import Path

from fahmi2.app.document_export import DocumentExportResult, write_documents
from fahmi2.domain.enums import ExportFormat, Language, SupportType
from fahmi2.domain.pedagogy import PEDAGOGY_WORKSPACE_SUBDIR
from fahmi2.domain.project import Project
from fahmi2.infra.anki.genanki_exporter import AnkiExportResult, GenankiExporter
from fahmi2.pedagogy.artifact_reader import ParsedArtifact, read_artifact
from fahmi2.pedagogy.artifact_writer import (
    artifact_correction_markdown_path,
    artifact_markdown_path,
)

#: Ordre **pédagogique** des supports dans les fichiers exportés : d'abord les
#: supports d'apprentissage du plus général au plus précis (fiche → points clés →
#: flashcards), puis les exercices du plus précis au plus général (cloze →
#: vrai/faux → QCM → questions ouvertes → examen blanc). Donne un ordre
#: déterministe aux fichiers produits. Distinct de l'ordre canonique du registre.
_EXPORT_SUPPORT_ORDER: tuple[SupportType, ...] = (
    SupportType.REVISION_SHEET,
    SupportType.KEY_POINTS,
    SupportType.FLASHCARDS_CONCEPTS,
    SupportType.CLOZE,
    SupportType.TRUE_FALSE,
    SupportType.QCM,
    SupportType.OPEN_QUESTIONS,
    SupportType.MOCK_EXAM,
)

#: Glob des artefacts JSON : ``<support>/<lang>/<support>.json`` (profondeur 3).
#: Exclut ``pedagogy/manifest.json`` (profondeur 1).
_ARTIFACT_JSON_GLOB = "*/*/*.json"

_ENCODING_UTF8 = "utf-8"
#: Suffixe de stem d'un corrigé (cohérent avec ``<support>.corrige.md`` sur disque).
_CORRECTION_SUFFIX = ".corrige"


def export_pedagogy_to_apkg(project: Project, *, output_path: Path) -> AnkiExportResult:
    """Scanne ``pedagogy/`` et exporte les supports exportables vers un ``.apkg``.

    Args:
        project: Projet (nom = racine de deck ; pédagogie pour la difficulté).
        output_path: Chemin du fichier ``.apkg`` à écrire.

    Returns:
        ``AnkiExportResult`` (chemin + nb de notes + nb de decks).
    """
    pedagogy_dir = project.workspace_folder / PEDAGOGY_WORKSPACE_SUBDIR
    artifacts: list[ParsedArtifact] = []
    if pedagogy_dir.exists():
        for json_path in sorted(pedagogy_dir.glob(_ARTIFACT_JSON_GLOB)):
            parsed = read_artifact(json_path)
            if parsed is not None and parsed.items:
                artifacts.append(parsed)
    difficulty = (
        project.pedagogy.target_audience.value if project.pedagogy is not None else ""
    )
    return GenankiExporter().export_to_file(
        artifacts,
        deck_root=project.name,
        difficulty=difficulty,
        output_path=output_path,
    )


def collect_pedagogy_documents(project: Project) -> list[tuple[str, str]]:
    """Collecte un document par support et par corrigé présents (ordre déterministe).

    Lit les Markdown rendus (`<support>.md` / `<support>.corrige.md`) dans l'ordre
    **pédagogique d'export** (``_EXPORT_SUPPORT_ORDER``).

    Args:
        project: Projet.

    Returns:
        Liste de ``(stem, markdown)`` : ``<support>.<lang>`` (sujet) et
        ``<support>.<lang>.corrige`` (corrigé) pour chaque fichier présent.
    """
    pedagogy_dir = project.workspace_folder / PEDAGOGY_WORKSPACE_SUBDIR
    documents: list[tuple[str, str]] = []
    for language in Language:
        for support in _EXPORT_SUPPORT_ORDER:
            subject_path = artifact_markdown_path(pedagogy_dir, support, language)
            if subject_path.exists():
                documents.append(
                    (
                        f"{support.value}.{language.value}",
                        subject_path.read_text(encoding=_ENCODING_UTF8),
                    )
                )
            correction_path = artifact_correction_markdown_path(
                pedagogy_dir, support, language
            )
            if correction_path.exists():
                documents.append(
                    (
                        f"{support.value}.{language.value}{_CORRECTION_SUFFIX}",
                        correction_path.read_text(encoding=_ENCODING_UTF8),
                    )
                )
    return documents


def export_pedagogy_documents(
    project: Project, *, output_dir: Path, fmt: ExportFormat
) -> DocumentExportResult:
    """Exporte les supports rendus, **un fichier par support / corrigé**.

    Args:
        project: Projet.
        output_dir: Dossier de destination.
        fmt: Format documentaire (``MARKDOWN`` / ``PDF`` / ``HTML``).

    Returns:
        ``DocumentExportResult``.

    Raises:
        ValueError: Si ``fmt`` n'est pas documentaire.
        ConfigError: ``EXPORT.NO_PDF_FONT`` en PDF sans police Unicode.
    """
    return write_documents(
        collect_pedagogy_documents(project), output_dir=output_dir, fmt=fmt
    )
```

- [ ] **Step 4 : Lancer le test de l'export pédagogie (succès attendu)**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/app/test_pedagogy_export_documents.py -q`
Expected: PASS. (À ce stade `pedagogy_controller.py` importe encore les anciens noms : son import cassera — corrigé au Step 5. Ne pas lancer toute la suite avant.)

- [ ] **Step 5 : Basculer `pedagogy_controller.py` sur le helper partagé**

5a. Remplacer le bloc d'import `from fahmi2.app.pedagogy_export import (...)` (lignes 33-39) par :

```python
from fahmi2.app.pedagogy_export import (
    export_pedagogy_documents,
    export_pedagogy_to_apkg,
)
```

5b. Supprimer les constantes désormais inutiles (lignes 86-89) :

```python
#: Libellé du format (messages) pour les exports documentaires.
_LABEL_MARKDOWN = "Markdown"
_LABEL_PDF = "PDF"
_LABEL_HTML = "HTML"
```

5c. Ajouter l'import du helper et des types (après la ligne d'import `from fahmi2.ui.dialogs.pedagogy_settings_view import PedagogySettingsView`) :

```python
from fahmi2.ui._export_ui import choose_export_format, run_document_export
```

5d. Retirer `Callable` (collections.abc), `QFileDialog`, `QInputDialog` des imports **s'ils ne sont plus utilisés ailleurs** dans le fichier (ruff signalera les imports inutiles : appliquer `ruff check --fix`). `DocumentExportResult` n'est plus importé.

5e. Remplacer la méthode `_on_export_requested` (lignes 564-607) **et** supprimer `_export_actions` (609-620), `export_markdown` (622-624), `export_pdf` (626-628), `export_html` (630-632), `_export_documents` (634-694) par cette unique méthode :

```python
    def _on_export_requested(self) -> None:
        """Propose les formats d'export configurés et exécute l'export choisi.

        APKG est routé vers ``export_apkg`` ; les formats documentaires
        (Markdown / PDF / HTML) passent par le helper partagé.
        """
        project = self._current_project
        if project is None:
            QMessageBox.warning(
                self._window,
                "Aucun projet sélectionné",
                "Sélectionne un projet dans la sidebar avant d'exporter.",
            )
            return
        if project.pedagogy is None:
            QMessageBox.information(
                self._window,
                "Supports non configurés",
                "Configurez d'abord les supports pédagogiques (⚙ Réglages).",
            )
            return
        fmt = choose_export_format(
            window=self._window,
            configured_formats=project.pedagogy.export_formats,
            label_by_format=EXPORT_LABELS,
        )
        if fmt is None:
            return
        if fmt is ExportFormat.APKG:
            self.export_apkg()
            return
        run_document_export(
            window=self._window,
            logs_dock=self._logs_dock,
            label=EXPORT_LABELS[fmt],
            exporter=lambda d: export_pedagogy_documents(
                project, output_dir=d, fmt=fmt
            ),
        )
```

(`export_apkg` reste inchangé. `self._window` et `self._logs_dock` existent déjà dans le contrôleur.)

- [ ] **Step 6 : Auto-fix lint + lancer la suite ciblée**

```bash
.venv\Scripts\python.exe -m ruff check --fix src/fahmi2/ui/pedagogy_controller.py
.venv\Scripts\python.exe -m pytest tests/unit/app/test_pedagogy_export_documents.py tests/unit/ui/test_pedagogy_controller.py -q
```
Expected: PASS. Si `test_pedagogy_controller.py` testait les anciennes méthodes (`export_markdown`/`_export_documents`/`_export_actions`), adapter ces tests pour appeler `_on_export_requested` en monkeypatchant `choose_export_format` (retourne un format) et `run_document_export`/`QFileDialog`, sur le modèle de `tests/unit/ui/test_export_ui.py`.

- [ ] **Step 7 : Qualité complète + commit**

```bash
.venv\Scripts\python.exe -m pytest -q && .venv\Scripts\python.exe -m ruff check . && .venv\Scripts\python.exe -m mypy src tests
git add src/fahmi2/app/pedagogy_export.py src/fahmi2/ui/pedagogy_controller.py tests/unit/app/test_pedagogy_export_documents.py tests/unit/ui/test_pedagogy_controller.py
git commit -m "feat(pedagogy/export): un fichier par support/corrige + bascule helper partage"
```

---

### Task 7 : UI Génération — page Export des réglages + bouton + handler

**Files:**
- Modify: `src/fahmi2/ui/dialogs/generation_settings_view.py`
- Modify: `src/fahmi2/ui/features/generation_tab.py`
- Modify: `src/fahmi2/ui/generation_controller.py`
- Test: `tests/unit/ui/test_generation_settings_view.py`

- [ ] **Step 1 : Écrire le test de la page Export** — ajouter à `tests/unit/ui/test_generation_settings_view.py`

```python
def test_export_page_roundtrip(qtbot: QtBot, make_generation_settings: Any) -> None:
    from fahmi2.domain.enums import ExportFormat

    gen = make_generation_settings(
        input_folder=Path("D:/Cours"),
        export_formats=frozenset({ExportFormat.PDF, ExportFormat.HTML}),
    )
    view = GenerationSettingsView(_HW, initial=gen)
    qtbot.addWidget(view)
    # Les cases reflètent les réglages…
    assert view._export_checks[ExportFormat.PDF].isChecked()  # noqa: SLF001
    assert view._export_checks[ExportFormat.HTML].isChecked()  # noqa: SLF001
    assert ExportFormat.APKG not in view._export_checks  # noqa: SLF001
    # …et to_settings les relit.
    view._on_accept()  # noqa: SLF001
    out = view.get_generation_settings()
    assert out is not None
    assert out.export_formats == frozenset({ExportFormat.PDF, ExportFormat.HTML})
```

- [ ] **Step 2 : Lancer (échec attendu)**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/ui/test_generation_settings_view.py::test_export_page_roundtrip -q`
Expected: FAIL (`_export_checks` inexistant).

- [ ] **Step 3 : Modifier `generation_settings_view.py` — imports**

Ajouter à l'import PySide6 (bloc `from PySide6.QtWidgets import (...)`) : `QLabel`.

Remplacer l'import enums :

```python
from fahmi2.domain.enums import Language, LLMModel, SttProvider, StylePreset
```

par :

```python
from fahmi2.domain.enums import (
    ExportFormat,
    Language,
    LLMModel,
    SttProvider,
    StylePreset,
)
```

Ajouter `GENERATION_EXPORT_FORMATS` à l'import `from fahmi2.domain.generation import (...)` :

```python
from fahmi2.domain.generation import (
    GENERATION_EXPORT_FORMATS,
    MAX_LLM_WORKERS,
    MAX_STT_CLOUD_WORKERS,
    GenerationSettings,
    ParallelismConfig,
)
```

Ajouter l'import des libellés (après l'import `from fahmi2.ui.widgets.settings_view import SettingsView`) :

```python
from fahmi2.ui.pedagogy_labels import EXPORT_LABELS
```

- [ ] **Step 4 : Ajouter la catégorie + constantes**

Après `_CAT_PHASES = "Phases"` ajouter :

```python
_CAT_EXPORT = "Export"
_EXPORT_HINT = (
    "Formats proposés lors de l'export des livrables de la génération (le bouton "
    "« Exporter » liste les formats cochés). Sans sélection, l'export invite à en "
    "choisir ici."
)
_EXPORT_FORMATS_LABEL = "Formats d'export :"
```

Dans `SettingsView([...])` (constructeur), ajouter la page après `(_CAT_PHASES, self._build_phases_page())` :

```python
                (_CAT_PHASES, self._build_phases_page()),
                (_CAT_EXPORT, self._build_export_page()),
```

- [ ] **Step 5 : Instancier les cases (dans `_build_fields`)**

À la fin de `_build_fields` (après le bloc `self._llm_workers_input…setToolTip(...)`), ajouter :

```python
        self._export_checks: dict[ExportFormat, QCheckBox] = {}
        for fmt in ExportFormat:
            if fmt in GENERATION_EXPORT_FORMATS:
                self._export_checks[fmt] = QCheckBox(EXPORT_LABELS[fmt], self)
```

- [ ] **Step 6 : Construire la page Export** (après `_build_phases_page`)

```python
    def _build_export_page(self) -> QWidget:
        """Construit la page « Export » (formats d'export proposés).

        Returns:
            Le widget de page.
        """
        page = QWidget(self)
        outer = QVBoxLayout(page)
        hint = QLabel(_EXPORT_HINT, page)
        hint.setWordWrap(True)
        outer.addWidget(hint)
        outer.addWidget(QLabel(_EXPORT_FORMATS_LABEL, page))
        for cb in self._export_checks.values():
            outer.addWidget(cb)
        outer.addStretch(1)
        return page
```

- [ ] **Step 7 : `_populate` + `_on_accept`**

Dans `_populate`, après `self._phase_configs_widget.set_phase_configs(generation.phases_config)` :

```python
        for fmt, cb in self._export_checks.items():
            cb.setChecked(fmt in generation.export_formats)
```

Dans `_on_accept`, avant `self._result = GenerationSettings(`, calculer :

```python
        export_formats = frozenset(
            fmt for fmt, cb in self._export_checks.items() if cb.isChecked()
        )
```

et passer le champ au constructeur (après `delete_audio_after_stt=...`):

```python
            delete_audio_after_stt=not self._keep_audio_checkbox.isChecked(),
            export_formats=export_formats,
        )
```

- [ ] **Step 8 : Lancer le test de la vue (succès attendu)**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/ui/test_generation_settings_view.py -q`
Expected: PASS.

- [ ] **Step 9 : Afficher le bouton Exporter dans l'onglet** — `generation_tab.py`

Ajouter en tête du module (avec les autres constantes de l'onglet) :

```python
_EXPORT_TOOLTIP = (
    "Exporte les livrables de la génération (document consolidé et glossaire) "
    "dans les formats cochés (Markdown / PDF / HTML)."
)
```

Remplacer (ligne 56) :

```python
        self._header_bar = ProjectHeaderBar(self._widget)
```

par :

```python
        self._header_bar = ProjectHeaderBar(
            self._widget,
            show_export=True,
            export_tooltip=_EXPORT_TOOLTIP,
        )
```

- [ ] **Step 10 : Brancher le handler dans `generation_controller.py`**

10a. Ajouter les imports (zone des imports `fahmi2.app.*`) :

```python
from fahmi2.app.generation_export import export_generation_documents
```

et (zone `fahmi2.ui.*`) :

```python
from fahmi2.ui._export_ui import choose_export_format, run_document_export
from fahmi2.ui.pedagogy_labels import EXPORT_LABELS
```

10b. Dans `__init__`, après `self._header_bar.reset_requested.connect(self.reset_generation)` :

```python
        self._header_bar.export_requested.connect(self.export_documents)
```

10c. Ajouter la méthode (près de `open_output_folder`) :

```python
    def export_documents(self) -> None:
        """Exporte les livrables de génération (consolidé + glossaire) au format choisi."""
        project = self._current_project
        if project is None:
            QMessageBox.warning(
                self._window,
                "Aucun projet sélectionné",
                "Sélectionne un projet dans la sidebar avant d'exporter.",
            )
            return
        if project.generation is None:
            QMessageBox.information(
                self._window,
                "Génération non configurée",
                "Configurez d'abord la génération (⚙ Réglages).",
            )
            return
        fmt = choose_export_format(
            window=self._window,
            configured_formats=project.generation.export_formats,
            label_by_format=EXPORT_LABELS,
        )
        if fmt is None:
            return
        run_document_export(
            window=self._window,
            logs_dock=self._logs_dock,
            label=EXPORT_LABELS[fmt],
            exporter=lambda d: export_generation_documents(
                project, output_dir=d, fmt=fmt
            ),
        )
```

- [ ] **Step 11 : Qualité complète + commit**

```bash
.venv\Scripts\python.exe -m pytest -q && .venv\Scripts\python.exe -m ruff check . && .venv\Scripts\python.exe -m mypy src tests
git add src/fahmi2/ui/dialogs/generation_settings_view.py src/fahmi2/ui/features/generation_tab.py src/fahmi2/ui/generation_controller.py tests/unit/ui/test_generation_settings_view.py
git commit -m "feat(ui/generation): page reglages Export + bouton Exporter (MD/PDF/HTML)"
```

---

### Task 8 : Supprimer `assemble_markdown` (code mort) + ses tests

**Files:**
- Modify: `src/fahmi2/infra/export/markdown_pdf.py`
- Modify: `tests/unit/infra/export/test_markdown_pdf.py`

- [ ] **Step 1 : Vérifier l'absence d'usage restant**

Run: `.venv\Scripts\python.exe -m pytest --collect-only -q ; ` puis chercher : aucun import de `assemble_markdown` ne doit subsister hors de son propre module/test (Grep `assemble_markdown` sur `src/` et `tests/` → seules `markdown_pdf.py` et `test_markdown_pdf.py` doivent ressortir).

- [ ] **Step 2 : Retirer les 2 tests** dans `tests/unit/infra/export/test_markdown_pdf.py`

Supprimer `from fahmi2.infra.export.markdown_pdf import (... assemble_markdown ...)` (ne garder que `pdf_fonts_available, render_markdown_to_pdf`), et supprimer les fonctions `test_assemble_markdown_joins_bodies` et `test_assemble_markdown_empty`. Ajouter un test de la nouvelle constante :

```python
def test_extension_by_format() -> None:
    from fahmi2.domain.enums import ExportFormat
    from fahmi2.infra.export.markdown_pdf import EXTENSION_BY_FORMAT

    assert EXTENSION_BY_FORMAT[ExportFormat.MARKDOWN] == ".md"
    assert EXTENSION_BY_FORMAT[ExportFormat.PDF] == ".pdf"
    assert EXTENSION_BY_FORMAT[ExportFormat.HTML] == ".html"
    assert ExportFormat.APKG not in EXTENSION_BY_FORMAT
```

- [ ] **Step 3 : Supprimer `assemble_markdown` et ses constantes** dans `markdown_pdf.py`

Supprimer la fonction `assemble_markdown` (def + docstring + corps) ainsi que les constantes désormais inutilisées `_SECTION_SEPARATOR` et `_EMPTY_BODY` (vérifier via Grep qu'elles ne servent qu'à `assemble_markdown`).

- [ ] **Step 4 : Lancer (succès attendu)**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/infra/export/test_markdown_pdf.py -q`
Expected: PASS.

- [ ] **Step 5 : Qualité + commit**

```bash
.venv\Scripts\python.exe -m ruff check . && .venv\Scripts\python.exe -m mypy src tests
git add src/fahmi2/infra/export/markdown_pdf.py tests/unit/infra/export/test_markdown_pdf.py
git commit -m "refactor(export): supprimer assemble_markdown (mort apres passage 1 fichier/support)"
```

---

### Task 9 : Documentation + CHANGELOG

**Files:**
- Modify: `docs/01-presentation-fonctionnelle.md`, `docs/04-parametrage.md`, `docs/07-guide-utilisateur.md`, `CLAUDE.md`, `CHANGELOG.md`

- [ ] **Step 1 : `docs/01-presentation-fonctionnelle.md`**

Là où l'export pédagogie est décrit (« Exporter propose 4 formats … documents agrégés par langue, sujet et corrigé séparés »), remplacer la formulation « documents agrégés par langue » par : **un fichier par support et par corrigé** (`<support>.<lang>.<ext>` / `<support>.<lang>.corrige.<ext>`). Ajouter une phrase sur le **nouvel export Génération** : le bouton « Exporter » de l'onglet Génération produit le **document consolidé** et le **glossaire** par langue en Markdown / PDF / HTML.

- [ ] **Step 2 : `docs/04-parametrage.md`**

Dans la section réglages Génération, documenter la **page « Export »** (cases Markdown / PDF / HTML, vide par défaut = opt-in). Dans la section pédagogie, préciser que MD/PDF/HTML produisent désormais **un fichier par support / corrigé** (`consolidated.{lang}` / `glossary.{lang}` côté génération).

- [ ] **Step 3 : `docs/07-guide-utilisateur.md`**

Dans le tableau des réglages Génération, ajouter une ligne **Export** (« Formats d'export : Markdown / PDF / HTML »). Décrire le bouton **Exporter** de l'onglet Génération et les fichiers produits (consolidé + glossaire par langue). Côté supports, préciser « un fichier par support et par corrigé ».

- [ ] **Step 4 : `CLAUDE.md`**

Dans la puce « Supports pédagogiques », remplacer « Exports : `.apkg` (genanki), Markdown et PDF via `app/pedagogy_export.py` » par une formulation incluant **HTML** et **un fichier par support/corrigé**, et mentionner le **cœur partagé `app/document_export.py`** + l'**export Génération `app/generation_export.py`** (consolidé + glossaire, MD/PDF/HTML, réglage `GenerationSettings.export_formats`).

- [ ] **Step 5 : `CHANGELOG.md`**

Ajouter une entrée datée 2026-05-22 :

```markdown
### Ajouté
- Export documentaire de la **Génération** (document consolidé + glossaire par
  langue) en **Markdown / PDF / HTML**, réglage `export_formats` (opt-in).

### Modifié
- Export des **supports pédagogiques** (MD/PDF/HTML) : désormais **un fichier par
  support et par corrigé** (au lieu d'un document agrégé par langue).
- Factorisation : cœur d'écriture partagé `app/document_export.py` ;
  `infra/export/markdown_pdf` devient un pur *renderer* (suppression de
  `assemble_markdown`).
```

- [ ] **Step 6 : Commit**

```bash
git add docs/01-presentation-fonctionnelle.md docs/04-parametrage.md docs/07-guide-utilisateur.md CLAUDE.md CHANGELOG.md
git commit -m "docs: export granulaire pedagogie + export documentaire generation"
```

---

### Task 10 : Vérification finale complète

- [ ] **Step 1 : Suite complète + lint + types**

```bash
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m mypy src tests
```
Expected: tous verts (0 échec, « All checks passed! », « Success: no issues found »).

- [ ] **Step 2 : Cohérence finale**

Vérifier (Grep) qu'aucune référence obsolète ne subsiste : `export_pedagogy_to_markdown|export_pedagogy_to_pdf|export_pedagogy_to_html|assemble_markdown|_export_actions|_export_documents` → aucun résultat hors historique. Vérifier que `EXPORT_LABELS` est bien importé là où il est utilisé (vues + contrôleurs).

- [ ] **Step 3 : Finalisation de branche** — invoquer la skill `superpowers:finishing-a-development-branch` (tests verts → présenter les options de fusion/PR).

---

## Self-Review (rempli à la rédaction)

**1. Couverture spec :** §1 → Task 1+8 ; §2 (document_export) → Task 1 ; §3 (pédagogie) → Task 6 ; §4 (generation_export) → Task 3 ; §5 (domaine : glossary_doc_filename, export_formats, invariant) → Task 2 ; §6 (persistance lenient) → Task 4 ; §7 (UI : settings view, helper, contrôleurs, EXPORT_LABELS) → Tasks 5+6+7 ; nommage → Tasks 3/6 ; erreurs → Task 5 ; tests → chaque task ; docs → Task 9. Aucun trou.

**2. Placeholders :** aucun « TBD/TODO » ; code complet à chaque step modifiant du code ; commandes exactes.

**3. Cohérence des types/signatures :** `write_documents(documents, *, output_dir, fmt)` ; `DocumentExportResult.document_count` ; `export_{pedagogy,generation}_documents(project, *, output_dir, fmt)` ; `collect_*_documents(project) -> list[tuple[str, str]]` ; `choose_export_format(*, window, configured_formats, label_by_format) -> ExportFormat | None` ; `run_document_export(*, window, logs_dock, label, exporter)` — identiques d'une task à l'autre. Stems : `SupportType.value` confirmés (`flashcards_concepts`, `qcm`, `revision_sheet`, `mock_exam`…), `consolidated.{lang}` / `glossary.{lang}` cohérents avec `consolidated_doc_filename` / `glossary_doc_filename`.
