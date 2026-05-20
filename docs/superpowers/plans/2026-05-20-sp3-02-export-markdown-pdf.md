# SP3 · Plan 02 — Export Markdown / PDF

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (inline, sans subagents).
> **Design** : [`../specs/2026-05-20-sp2-sp3-supports-revision-design.md`](../specs/2026-05-20-sp2-sp3-supports-revision-design.md) (§9).
> **Avancement** : [`./2026-05-20-sp2-sp3-00-avancement.md`](./2026-05-20-sp2-sp3-00-avancement.md).
> Steps use checkbox (`- [ ]`) syntax.

**Goal:** Exporter les supports générés vers des documents **Markdown** et **PDF**,
**sujet / corrigé séparés**, par langue. Le bouton **Exporter** propose désormais 3
formats (Anki / Markdown / PDF).

**Architecture:** Les supports sont **déjà rendus** sur disque sous `pedagogy/` en
`<support>.md` (sujet) et `<support>.corrige.md` (corrigé) par les générateurs. L'export
**réutilise ces fichiers** (pas de re-désérialisation ni de re-rendu — DRY/SoC). Un
adapter `infra/export/markdown_pdf.py` assemble les Markdown agrégés et rend le PDF
(pipeline pur-python **`markdown` → HTML → `fpdf2.write_html`**, police Unicode système
Windows **Arial**). Le service `app/pedagogy_export.py` (étendu) scanne `pedagogy/`,
agrège par langue et écrit les fichiers. L'UI ajoute un sélecteur de format.

> **Décision PDF (verrouillée)** : lib pure-python **`fpdf2`** + **`markdown`** (toutes
> deux bundlables PyInstaller). Police **Unicode système Windows Arial** (les polices
> cœur de fpdf2 sont latin-1 → lèvent sur « — », « … » fréquents en français ; Arial est
> toujours présent sous Windows, l'app étant Windows-only) — aucun binaire de police à
> committer. Repli documenté : si aucune police Unicode n'est résolue, l'export PDF lève
> une erreur claire (l'export Markdown reste disponible).

> **`artifact_reader` n'est PAS étendu** : l'export MD/PDF lit les `.md` rendus (le
> rendu vit déjà sur disque ; re-rendre dupliquerait la logique des générateurs).

**Tech Stack:** `markdown`, `fpdf2`, `pytest`, `ruff`, `mypy --strict`.

**Rappels directives :** pas de magic value (noms de police, gabarits de fichiers,
libellés de format en constantes), docstrings Google + module, réutiliser les patterns
(adapters infra, `artifact_writer` paths, `pedagogy.labels`, `ProjectHeaderBar`), DRY/
YAGNI/KISS/SRP/SoC, composition. **Tout en français** (accents).

---

## File structure (vue d'ensemble)

**Créés :**

- `src/fahmi2/infra/export/__init__.py`
- `src/fahmi2/infra/export/markdown_pdf.py` — `assemble_markdown`,
  `render_markdown_to_pdf`, `pdf_fonts_available`.
- Tests : `tests/unit/infra/export/test_markdown_pdf.py`.

**Modifiés :**

- `pyproject.toml` — dépendances `markdown` + `fpdf2` + overrides mypy.
- `src/fahmi2/app/pedagogy_export.py` — `DocumentExportResult`,
  `export_pedagogy_to_markdown`, `export_pedagogy_to_pdf` (+ collecte partagée).
- `src/fahmi2/ui/pedagogy_controller.py` — sélecteur de format + `export_markdown`/`export_pdf`.
- Tests : `tests/unit/app/test_pedagogy_export.py`, `tests/unit/ui/test_pedagogy_controller.py`.
- Docs : `docs/01`, `docs/02`, `docs/04`, `CHANGELOG.md`, avancement.
- `packaging/fahmi2.spec` (gitignored) — bundler `markdown`, `fpdf2` (+ Pillow, fonttools)
  (note seulement, non versionné).

---

## Task 1 : Dépendances `markdown` + `fpdf2`

**Files:** Modify `pyproject.toml`

- [ ] **Step 1** : Ajouter à `dependencies` : `"markdown>=3.5,<4",` et `"fpdf2>=2.8,<3",`.
- [ ] **Step 2** : Ajouter `markdown.*` et `fpdf.*` à l'override mypy `ignore_missing_imports`.
- [ ] **Step 3** : Vérifier (déjà installées) :
  `.venv\Scripts\python.exe -c "import markdown, fpdf; print(markdown.__version__, fpdf.FPDF_VERSION)"`.

> **Packaging** : `packaging/fahmi2.spec` devra inclure `markdown`, `fpdf2`, `fontTools`,
> `PIL` (hiddenimports/datas). Documenter.

---

## Task 2 : Adapter `infra/export/markdown_pdf.py`

**Files:** Create `src/fahmi2/infra/export/__init__.py`,
`src/fahmi2/infra/export/markdown_pdf.py` ; Test `tests/unit/infra/export/test_markdown_pdf.py`

Détails :
- `assemble_markdown(title, bodies)` : `f"# {title}\n\n"` + corps joints par `\n\n---\n\n`
  (chaque corps porte déjà son titre `# …`). Si aucun corps : titre + ligne « aucun support ».
- Police PDF : famille `_PDF_FONT_FAMILY = "AppSans"`, 4 variantes Arial depuis
  `%SystemRoot%\Fonts` (`_WINDOWS_FONT_FILES = {"" : "arial.ttf", "B": "arialbd.ttf",
  "I": "ariali.ttf", "BI": "arialbi.ttf"}`). `pdf_fonts_available()` → la régulière existe.
- `render_markdown_to_pdf(markdown_text, output_path)` : résout les polices (sinon
  `ConfigError("EXPORT.NO_PDF_FONT")`), `FPDF` + `add_font`×4 + `set_font` + `add_page`,
  `markdown.markdown(text)` → `write_html`, `output(str(path))`.

- [ ] **Step 1 : Test (échoue)** :

```python
"""Tests de l'assemblage Markdown et du rendu PDF."""

from __future__ import annotations

from pathlib import Path

import pytest

from fahmi2.infra.export.markdown_pdf import (
    assemble_markdown,
    pdf_fonts_available,
    render_markdown_to_pdf,
)


def test_assemble_markdown_joins_bodies() -> None:
    out = assemble_markdown("Titre", ("# A\n\ncorps a", "# B\n\ncorps b"))
    assert out.startswith("# Titre")
    assert "# A" in out and "# B" in out
    assert "---" in out


def test_assemble_markdown_empty() -> None:
    out = assemble_markdown("Titre", ())
    assert out.startswith("# Titre")


@pytest.mark.skipif(not pdf_fonts_available(), reason="Police Unicode indisponible")
def test_render_pdf_unicode(tmp_path: Path) -> None:
    out = tmp_path / "doc.pdf"
    render_markdown_to_pdf(
        "# Flashcards — Glossaire\n\nTexte… « x », **gras**, *ital*, éàç, ×, ≤.\n",
        out,
    )
    assert out.exists()
    assert out.read_bytes()[:5] == b"%PDF-"


@pytest.mark.skipif(not pdf_fonts_available(), reason="Police Unicode indisponible")
def test_render_pdf_handles_hr_and_lists(tmp_path: Path) -> None:
    out = tmp_path / "doc2.pdf"
    render_markdown_to_pdf("### Q\n\nR\n\n---\n\n- a\n- b\n", out)
    assert out.exists()
```

- [ ] **Step 2 : Lancer** → FAIL.

- [ ] **Step 3 : Créer `infra/export/markdown_pdf.py`** :

```python
"""Adapter d'export Markdown / PDF des supports pédagogiques.

L'export réutilise le Markdown **déjà rendu** par les générateurs : ce module
assemble les documents agrégés et rend le PDF via ``markdown`` → HTML →
``fpdf2.write_html`` (police Unicode système Windows ``Arial`` : les polices cœur
de fpdf2 sont latin-1 et lèvent sur les caractères typographiques français).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import markdown
from fpdf import FPDF

from fahmi2.core.errors.exceptions import ConfigError
from fahmi2.core.errors.severity import Severity

_SECTION_SEPARATOR = "\n\n---\n\n"
_EMPTY_BODY = "_Aucun support à exporter._"
_PDF_FONT_FAMILY = "AppSans"
_PDF_FONT_SIZE = 11
_WINDOWS_FONT_FILES: dict[str, str] = {
    "": "arial.ttf",
    "B": "arialbd.ttf",
    "I": "ariali.ttf",
    "BI": "arialbi.ttf",
}


def _fonts_dir() -> Path:
    """Dossier des polices système Windows."""
    return Path(os.environ.get("SystemRoot", r"C:\Windows")) / "Fonts"


def pdf_fonts_available() -> bool:
    """Indique si la police Unicode (Arial régulier) est résolue.

    Returns:
        ``True`` si le rendu PDF est possible.
    """
    return (_fonts_dir() / _WINDOWS_FONT_FILES[""]).exists()


def assemble_markdown(title: str, bodies: tuple[str, ...]) -> str:
    """Assemble un document Markdown agrégé (titre + corps).

    Args:
        title: Titre du document.
        bodies: Corps Markdown déjà rendus (chacun porte son propre titre).

    Returns:
        Le Markdown agrégé.
    """
    if not bodies:
        return f"# {title}\n\n{_EMPTY_BODY}\n"
    return f"# {title}\n\n" + _SECTION_SEPARATOR.join(bodies) + "\n"


@dataclass(frozen=True)
class _PdfFonts:
    """Chemins des 4 variantes de police pour le rendu PDF."""

    regular: Path
    bold: Path
    italic: Path
    bold_italic: Path


def _resolve_pdf_fonts() -> _PdfFonts | None:
    """Résout les 4 variantes Arial, ou ``None`` si la régulière est absente."""
    fonts = _fonts_dir()
    regular = fonts / _WINDOWS_FONT_FILES[""]
    if not regular.exists():
        return None
    return _PdfFonts(
        regular=regular,
        bold=fonts / _WINDOWS_FONT_FILES["B"],
        italic=fonts / _WINDOWS_FONT_FILES["I"],
        bold_italic=fonts / _WINDOWS_FONT_FILES["BI"],
    )


def render_markdown_to_pdf(markdown_text: str, output_path: Path) -> None:
    """Rend un Markdown en PDF (``markdown`` → HTML → ``fpdf2``).

    Args:
        markdown_text: Texte Markdown.
        output_path: Chemin du PDF à écrire.

    Raises:
        ConfigError: ``EXPORT.NO_PDF_FONT`` si aucune police Unicode n'est résolue.
    """
    fonts = _resolve_pdf_fonts()
    if fonts is None:
        raise ConfigError(
            code="EXPORT.NO_PDF_FONT",
            user_message=(
                "Aucune police Unicode trouvée pour l'export PDF. Utilisez "
                "l'export Markdown."
            ),
            severity=Severity.ERROR,
        )
    pdf = FPDF()
    pdf.add_font(_PDF_FONT_FAMILY, "", str(fonts.regular))
    pdf.add_font(_PDF_FONT_FAMILY, "B", str(fonts.bold))
    pdf.add_font(_PDF_FONT_FAMILY, "I", str(fonts.italic))
    pdf.add_font(_PDF_FONT_FAMILY, "BI", str(fonts.bold_italic))
    pdf.add_page()
    pdf.set_font(_PDF_FONT_FAMILY, size=_PDF_FONT_SIZE)
    pdf.write_html(markdown.markdown(markdown_text))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(output_path))
```

- [ ] **Step 4 : Lancer** → PASS (les tests PDF sont *skippés* hors Windows).

---

## Task 3 : Service `app/pedagogy_export.py` (Markdown + PDF)

**Files:** Modify `src/fahmi2/app/pedagogy_export.py` ; Test `tests/unit/app/test_pedagogy_export.py`

Détails :
- `DocumentExportResult(output_paths: tuple[Path, ...])` + propriété `document_count`.
- `_build_documents(project) -> list[tuple[str, str]]` : pour chaque `Language`, pour
  chaque support (ordre canonique), lire `artifact_markdown_path` (sujet) et
  `artifact_correction_markdown_path` (corrigé) s'ils existent ; agréger via
  `assemble_markdown` ; retourner `(stem, markdown_text)` :
  `("supports.{lang}", sujet)` si sujets, `("supports.{lang}.corrige", corrigé)` si corrigés.
  Titres via `pedagogy.labels.language_label`.
- `export_pedagogy_to_markdown(project, *, output_dir)` : écrit chaque `<stem>.md`.
- `export_pedagogy_to_pdf(project, *, output_dir)` : rend chaque `<stem>.pdf`.

- [ ] **Step 1 : Tests (échouent)** : écrire des `.md` (+ `.corrige.md`) sous `pedagogy/`,
  vérifier que `export_pedagogy_to_markdown` produit `supports.fr.md` (+ `.corrige.md`) avec
  le contenu agrégé ; `export_pedagogy_to_pdf` produit les `.pdf` (skipif police) ; projet
  sans `.md` → `document_count == 0`.

- [ ] **Step 2 : Lancer** → FAIL.

- [ ] **Step 3 : Étendre `app/pedagogy_export.py`** (constantes de gabarits de noms +
  helpers ci-dessus ; réutiliser `artifact_markdown_path`/`artifact_correction_markdown_path`,
  `SupportGeneratorRegistry.canonical_order()`, `language_label`, `assemble_markdown`,
  `render_markdown_to_pdf`). Constantes :
  `_SUBJECT_STEM = "supports.{lang}"`, `_CORRECTION_STEM = "supports.{lang}.corrige"`,
  `_MD_EXT = ".md"`, `_PDF_EXT = ".pdf"`, titres FR.

- [ ] **Step 4 : Lancer** → PASS.

---

## Task 4 : UI — sélecteur de format + actions Markdown/PDF

**Files:** Modify `src/fahmi2/ui/pedagogy_controller.py` ;
Test `tests/unit/ui/test_pedagogy_controller.py`

- [ ] **Step 1 : Sélecteur de format** — re-brancher `export_requested` vers
  `_on_export_requested` (au lieu de `export_apkg` directement) :
  - `QInputDialog.getItem(window, "Exporter", "Format :", [_FORMAT_ANKI, _FORMAT_MARKDOWN,
    _FORMAT_PDF], 0, editable=False)` → `(label, ok)` ; si pas ok → return ; dispatch.
  - Constantes `_FORMAT_ANKI = "Anki (.apkg)"`, `_FORMAT_MARKDOWN = "Markdown"`,
    `_FORMAT_PDF = "PDF"`.

- [ ] **Step 2 : `export_markdown` / `export_pdf`** :
  - si pas de projet → warning.
  - `QFileDialog.getExistingDirectory(window, "Dossier d'export")` ; si vide → return.
  - `result = export_pedagogy_to_markdown(project, output_dir=Path(dir))` (resp. `_to_pdf`).
  - isoler `Fahmi2Error`/`Exception` → `QMessageBox.critical`.
  - si `document_count == 0` → information « aucun support à exporter » ; sinon information
    « N document(s) exporté(s) dans <dir> » + log INFO `PEDAGOGY_EXPORTED`.

- [ ] **Step 3 : Tests** (`tests/unit/ui/test_pedagogy_controller.py`) :
  - `export_markdown` : artefacts `.md` amorcés + monkeypatch `QFileDialog.getExistingDirectory`
    (+ `QMessageBox.information`) → `supports.fr.md` écrit dans le dossier.
  - dispatch : monkeypatch `QInputDialog.getItem` → `(_FORMAT_MARKDOWN, True)` +
    monkeypatch `export_markdown` (ou les dialogues) → `_on_export_requested` appelle la
    bonne méthode. (Vérifier via un drapeau/mock.)
  - `export_pdf` : skipif police indisponible.

- [ ] **Step 4 : Lancer** → PASS + non-régression UI.

---

## Task 5 : Vérifications systématiques + docs + commit

- [ ] **Step 1** : `pytest -q` → tout vert.
- [ ] **Step 2** : `ruff check .` → clean.
- [ ] **Step 3** : `mypy src tests` → Success.
- [ ] **Step 4 : Docs** : `docs/01` (export Markdown/PDF), `docs/02` (adapter `infra/export`,
  pipeline markdown+fpdf2, police Arial), `docs/04` (bouton Exporter : 3 formats),
  `CHANGELOG.md`, avancement (SP3/02 → Fait ; ne reste que docs finales). Note packaging.
- [ ] **Step 5 : Commit** :

```bash
git add -A
git commit -m "feat(pedagogy): export Markdown/PDF des supports (SP3/02)"
```

---

## Self-review

**Couverture du design §9 :** rendu Markdown (réutilisation des `.md` rendus, Task 2/3) ;
Markdown→PDF via lib pure-python bundlable (`markdown` + `fpdf2`, Task 2) ; sujet/corrigé
séparés (Task 3 : `supports.{lang}.md` + `supports.{lang}.corrige.md`) ; choix lib PDF
verrouillé (`fpdf2`, police Arial). Bouton export multi-format (Task 4).

**Décisions documentées :** `artifact_reader` non étendu (réutilisation des `.md` rendus,
DRY) ; police Unicode système Windows (app Windows-only) avec repli erreur claire ; tests
PDF *skippés* si police indisponible (portabilité CI).

**Cohérence types/signatures :** `assemble_markdown(title, bodies) -> str`,
`render_markdown_to_pdf(text, path) -> None`, `pdf_fonts_available() -> bool` (Task 2) ;
`export_pedagogy_to_markdown/pdf(project, *, output_dir) -> DocumentExportResult`
(Tasks 3/4) ; sélecteur `_on_export_requested` + `export_markdown`/`export_pdf` (Task 4).
