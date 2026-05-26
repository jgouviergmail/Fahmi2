# Langues supplémentaires (de/es/it/zh/ar) + export DOCX — plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. **Note projet : exécution inline imposée (pas de subagents) ; repasses `pytest`/`ruff`/`mypy` obligatoires.**

**Goal:** Étendre les langues gérées de FR/EN à FR/EN/DE/ES/IT/ZH/AR pour les trois fonctionnalités (Génération, Pédagogie, Dialogue) et ajouter le format d'export DOCX, avec un rendu PDF correct du chinois (CJK) et de l'arabe (RTL).

**Architecture:** L'enum `Language` est la source de propagation (l'UI dérive de `tuple(Language)`). Les libellés de langue dupliqués sont centralisés dans un nouveau module `domain/languages.py`. Le PDF CJK/RTL utilise des polices système Windows enregistrées avec ReportLab (`subfontIndex` pour les TTC) injectées dans `xhtml2pdf.default.DEFAULT_FONT`, plus le tag `<pdf:language>` pour le shaping arabe — sans monkeypatch ni police bundlée. Le DOCX réutilise le rendu Markdown→HTML existant via `htmldocx`.

**Tech Stack:** Python 3.12, PySide6, xhtml2pdf/reportlab, python-docx + htmldocx + beautifulsoup4, faster-whisper/OpenAI, markdown.

**Spec :** `docs/superpowers/specs/2026-05-26-langues-supplementaires-export-docx-design.md`

---

## Structure des fichiers

| Fichier | Responsabilité | Action |
|---------|----------------|--------|
| `src/fahmi2/domain/enums.py` | +5 `Language`, +`ExportFormat.DOCX` | Modifier |
| `src/fahmi2/domain/languages.py` | Source unique des libellés de langue | **Créer** |
| `src/fahmi2/domain/glossary.py` | En-têtes glossaire ×5 langues | Modifier |
| `src/fahmi2/domain/generation.py` | `GENERATION_EXPORT_FORMATS` += DOCX | Modifier |
| `src/fahmi2/pipeline/handlers/_base.py` | `language_label` délègue au domaine | Modifier |
| `src/fahmi2/pedagogy/labels.py` | `language_label` délègue au domaine | Modifier |
| `src/fahmi2/infra/stt/openai_whisper_adapter.py` | Alias Whisper ×5 | Modifier |
| `src/fahmi2/infra/export/markdown_pdf.py` | Polices CJK/RTL + param `language` | Modifier |
| `src/fahmi2/infra/export/markdown_docx.py` | Renderer Markdown→HTML→docx | **Créer** |
| `src/fahmi2/app/document_export.py` | `ExportDocument.language` + dispatch DOCX | Modifier |
| `src/fahmi2/app/generation_export.py` | Renseigne `language` | Modifier |
| `src/fahmi2/app/pedagogy_export.py` | Renseigne `language` | Modifier |
| `src/fahmi2/ui/pedagogy_labels.py` | `EXPORT_LABELS[DOCX]` | Modifier |
| `src/fahmi2/ui/widgets/language_selection_view.py` | `language_display_label` | Modifier |
| `src/fahmi2/ui/dialogs/pedagogy_settings_view.py` | `language_display_label` (fin du code brut) | Modifier |
| `pyproject.toml` | +htmldocx, +beautifulsoup4 | Modifier |
| `packaging/fahmi2.spec` | Collecte bs4/htmldocx (gitignored) | Modifier |
| `CLAUDE.md`, `README.md`, `packaging/README.md` | Documentation | Modifier |

---

## Task 1 : Enum `Language` — 5 nouvelles langues

**Files:**
- Modify: `src/fahmi2/domain/enums.py:8-12`
- Test: `tests/unit/domain/test_enums.py`

- [ ] **Step 1: Écrire le test qui échoue**

Ajouter dans `tests/unit/domain/test_enums.py` :

```python
def test_language_has_seven_supported_values() -> None:
    from fahmi2.domain.enums import Language

    assert {lang.value for lang in Language} == {
        "fr", "en", "de", "es", "it", "zh", "ar",
    }
    # FR reste en première position (défaut d'affichage et d'ordre).
    assert next(iter(Language)) is Language.FR
```

- [ ] **Step 2: Lancer le test pour vérifier l'échec**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/domain/test_enums.py::test_language_has_seven_supported_values -v`
Expected: FAIL (l'ensemble ne contient que `{"fr","en"}`).

- [ ] **Step 3: Implémenter**

Dans `src/fahmi2/domain/enums.py`, remplacer le corps de `Language` :

```python
class Language(StrEnum):
    """Langues supportées (entrée et sortie)."""

    FR = "fr"
    EN = "en"
    DE = "de"
    ES = "es"
    IT = "it"
    ZH = "zh"
    AR = "ar"
```

- [ ] **Step 4: Lancer le test**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/domain/test_enums.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/fahmi2/domain/enums.py tests/unit/domain/test_enums.py
git commit -m "feat(domain): ajoute de/es/it/zh/ar a l'enum Language"
```

---

## Task 2 : Module `domain/languages.py` — source unique des libellés

**Files:**
- Create: `src/fahmi2/domain/languages.py`
- Modify: `src/fahmi2/pipeline/handlers/_base.py:31-58`
- Modify: `src/fahmi2/pedagogy/labels.py:17-52`
- Test: `tests/unit/domain/test_languages.py`

- [ ] **Step 1: Écrire le test qui échoue**

Créer `tests/unit/domain/test_languages.py` :

```python
"""Tests de la source unique des libellés de langue."""

from __future__ import annotations

from fahmi2.domain.enums import Language
from fahmi2.domain.languages import language_display_label, language_label


def test_language_label_is_lowercase_for_prompts() -> None:
    assert language_label(Language.FR) == "français"
    assert language_label(Language.ZH) == "chinois"
    assert language_label(Language.AR) == "arabe"


def test_language_display_label_is_capitalized_for_ui() -> None:
    assert language_display_label(Language.EN) == "Anglais"
    assert language_display_label(Language.DE) == "Allemand"


def test_every_language_has_a_label() -> None:
    for lang in Language:
        assert language_label(lang)
        assert language_display_label(lang)[0].isupper()
```

- [ ] **Step 2: Lancer le test pour vérifier l'échec**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/domain/test_languages.py -v`
Expected: FAIL with "No module named 'fahmi2.domain.languages'"

- [ ] **Step 3: Créer le module**

Créer `src/fahmi2/domain/languages.py` :

```python
"""Source unique de vérité des libellés humains de ``Language``.

Sépare le **fond** (libellé minuscule injecté dans les prompts LLM) de la
**présentation** (libellé capitalisé affiché dans l'UI). Aucune dépendance Qt,
HTTP ni SQL — module de domaine pur.
"""

from __future__ import annotations

from fahmi2.domain.enums import Language

_LANGUAGE_NAMES: dict[Language, str] = {
    Language.FR: "français",
    Language.EN: "anglais",
    Language.DE: "allemand",
    Language.ES: "espagnol",
    Language.IT: "italien",
    Language.ZH: "chinois",
    Language.AR: "arabe",
}


def language_label(language: Language) -> str:
    """Libellé minuscule d'une langue, pour injection dans les prompts.

    Args:
        language: Langue.

    Returns:
        Le libellé (ex: ``"français"``).
    """
    return _LANGUAGE_NAMES[language]


def language_display_label(language: Language) -> str:
    """Libellé capitalisé d'une langue, pour affichage UI.

    Args:
        language: Langue.

    Returns:
        Le libellé capitalisé (ex: ``"Français"``).
    """
    return _LANGUAGE_NAMES[language].capitalize()
```

- [ ] **Step 4: Faire déléguer `pipeline/handlers/_base.py`**

Dans `src/fahmi2/pipeline/handlers/_base.py`, supprimer `_LANGUAGE_LABELS_FR` (lignes 31-34) et remplacer la fonction `language_label` (lignes 49-58) par une délégation. Ajouter l'import en tête (avec les autres imports `fahmi2.domain`) :

```python
from fahmi2.domain.languages import language_label as _language_label
```

Puis remplacer la définition locale par :

```python
def language_label(language: Language) -> str:
    """Libellé humain (FR, minuscule) d'une ``Language``.

    Délègue à la source unique ``domain.languages`` (ré-export pour compat des
    handlers qui importent ``language_label`` depuis ce module).

    Args:
        language: Langue.

    Returns:
        Le libellé (ex: ``"français"``).
    """
    return _language_label(language)
```

- [ ] **Step 5: Faire déléguer `pedagogy/labels.py`**

Dans `src/fahmi2/pedagogy/labels.py`, supprimer `_LANGUAGE_LABELS_FR` (lignes 17-20) et remplacer la fonction `language_label` (lignes 43-52) de la même manière. Ajouter l'import :

```python
from fahmi2.domain.languages import language_label as _language_label
```

Et remplacer la définition par :

```python
def language_label(language: Language) -> str:
    """Libellé FR (minuscule) d'une langue.

    Délègue à la source unique ``domain.languages`` (ré-export pour compat).

    Args:
        language: Langue.

    Returns:
        Le libellé (ex: ``"français"``).
    """
    return _language_label(language)
```

- [ ] **Step 6: Lancer les tests impactés**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/domain/test_languages.py tests/unit/pipeline tests/unit/pedagogy -q`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/fahmi2/domain/languages.py src/fahmi2/pipeline/handlers/_base.py src/fahmi2/pedagogy/labels.py tests/unit/domain/test_languages.py
git commit -m "refactor(domain): centralise les libelles de langue (DRY)"
```

---

## Task 3 : En-têtes de glossaire pour les 5 langues

**Files:**
- Modify: `src/fahmi2/domain/glossary.py:12-15`
- Test: `tests/unit/domain/test_glossary.py`

- [ ] **Step 1: Écrire le test qui échoue**

Ajouter dans `tests/unit/domain/test_glossary.py` :

```python
def test_glossary_headers_exist_for_all_languages() -> None:
    from fahmi2.domain.enums import Language
    from fahmi2.domain.glossary import _HEADERS_BY_LANGUAGE

    for lang in Language:
        headers = _HEADERS_BY_LANGUAGE[lang]
        assert len(headers) == 4
        assert all(h for h in headers)
    assert _HEADERS_BY_LANGUAGE[Language.DE][0] == "Begriff"
    assert _HEADERS_BY_LANGUAGE[Language.ZH][3] == "定义"
```

- [ ] **Step 2: Lancer le test pour vérifier l'échec**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/domain/test_glossary.py::test_glossary_headers_exist_for_all_languages -v`
Expected: FAIL with `KeyError: Language.DE`

- [ ] **Step 3: Implémenter**

Dans `src/fahmi2/domain/glossary.py`, étendre `_HEADERS_BY_LANGUAGE` :

```python
_HEADERS_BY_LANGUAGE: dict[Language, tuple[str, str, str, str]] = {
    Language.FR: ("Terme", "Acronyme", "Signification", "Définition"),
    Language.EN: ("Term", "Acronym", "Meaning", "Definition"),
    Language.DE: ("Begriff", "Akronym", "Bedeutung", "Definition"),
    Language.ES: ("Término", "Acrónimo", "Significado", "Definición"),
    Language.IT: ("Termine", "Acronimo", "Significato", "Definizione"),
    Language.ZH: ("术语", "缩写", "含义", "定义"),
    Language.AR: ("المصطلح", "الاختصار", "المعنى", "التعريف"),
}
```

- [ ] **Step 4: Lancer le test**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/domain/test_glossary.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/fahmi2/domain/glossary.py tests/unit/domain/test_glossary.py
git commit -m "feat(domain): en-tetes de glossaire pour de/es/it/zh/ar"
```

---

## Task 4 : Alias de détection de langue Whisper

**Files:**
- Modify: `src/fahmi2/infra/stt/openai_whisper_adapter.py:44-49`
- Test: `tests/unit/infra/stt/test_openai_whisper_adapter.py`

- [ ] **Step 1: Écrire le test qui échoue**

Ajouter dans `tests/unit/infra/stt/test_openai_whisper_adapter.py` :

```python
def test_resolve_language_maps_new_languages() -> None:
    from fahmi2.domain.enums import Language
    from fahmi2.infra.stt.openai_whisper_adapter import _resolve_language

    assert _resolve_language("german", fallback=None) is Language.DE
    assert _resolve_language("de", fallback=None) is Language.DE
    assert _resolve_language("spanish", fallback=None) is Language.ES
    assert _resolve_language("zh", fallback=None) is Language.ZH
    assert _resolve_language("arabic", fallback=None) is Language.AR
    assert _resolve_language("italian", fallback=None) is Language.IT
```

- [ ] **Step 2: Lancer le test pour vérifier l'échec**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/infra/stt/test_openai_whisper_adapter.py::test_resolve_language_maps_new_languages -v`
Expected: FAIL (retombe sur `_DEFAULT_DETECTED_LANGUAGE`, donc `Language.EN`)

- [ ] **Step 3: Implémenter**

Dans `src/fahmi2/infra/stt/openai_whisper_adapter.py`, étendre `_WHISPER_LANGUAGE_ALIASES` :

```python
_WHISPER_LANGUAGE_ALIASES: dict[str, Language] = {
    "french": Language.FR, "fr": Language.FR,
    "english": Language.EN, "en": Language.EN,
    "german": Language.DE, "de": Language.DE,
    "spanish": Language.ES, "es": Language.ES,
    "italian": Language.IT, "it": Language.IT,
    "chinese": Language.ZH, "zh": Language.ZH,
    "arabic": Language.AR, "ar": Language.AR,
}
```

- [ ] **Step 4: Lancer le test**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/infra/stt/test_openai_whisper_adapter.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/fahmi2/infra/stt/openai_whisper_adapter.py tests/unit/infra/stt/test_openai_whisper_adapter.py
git commit -m "feat(stt): alias de detection Whisper pour de/es/it/zh/ar"
```

---

## Task 5 : `ExportFormat.DOCX` (enum + extension + formats autorisés + libellé)

**Files:**
- Modify: `src/fahmi2/domain/enums.py:185-191`
- Modify: `src/fahmi2/infra/export/markdown_pdf.py:37-41`
- Modify: `src/fahmi2/domain/generation.py:70-72`
- Modify: `src/fahmi2/ui/pedagogy_labels.py:23-28`
- Test: `tests/unit/domain/test_enums.py`, `tests/unit/infra/export/test_markdown_pdf.py`

- [ ] **Step 1: Écrire les tests qui échouent**

Ajouter dans `tests/unit/domain/test_enums.py` :

```python
def test_export_format_includes_docx() -> None:
    from fahmi2.domain.enums import ExportFormat

    assert ExportFormat.DOCX.value == "docx"


def test_generation_export_formats_includes_docx() -> None:
    from fahmi2.domain.enums import ExportFormat
    from fahmi2.domain.generation import GENERATION_EXPORT_FORMATS

    assert ExportFormat.DOCX in GENERATION_EXPORT_FORMATS
    assert ExportFormat.APKG not in GENERATION_EXPORT_FORMATS
```

Ajouter dans `tests/unit/infra/export/test_markdown_pdf.py` (dans `test_extension_by_format`) :

```python
def test_extension_includes_docx() -> None:
    from fahmi2.domain.enums import ExportFormat
    from fahmi2.infra.export.markdown_pdf import EXTENSION_BY_FORMAT

    assert EXTENSION_BY_FORMAT[ExportFormat.DOCX] == ".docx"
```

- [ ] **Step 2: Lancer pour vérifier l'échec**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/domain/test_enums.py::test_export_format_includes_docx tests/unit/infra/export/test_markdown_pdf.py::test_extension_includes_docx -v`
Expected: FAIL (`AttributeError: DOCX`)

- [ ] **Step 3: Implémenter — enum**

Dans `src/fahmi2/domain/enums.py`, dans `ExportFormat` :

```python
class ExportFormat(StrEnum):
    """Formats d'export des supports."""

    APKG = "apkg"
    MARKDOWN = "markdown"
    PDF = "pdf"
    HTML = "html"
    DOCX = "docx"
```

- [ ] **Step 4: Implémenter — extension**

Dans `src/fahmi2/infra/export/markdown_pdf.py`, ajouter à `EXTENSION_BY_FORMAT` :

```python
EXTENSION_BY_FORMAT: dict[ExportFormat, str] = {
    ExportFormat.MARKDOWN: ".md",
    ExportFormat.PDF: ".pdf",
    ExportFormat.HTML: ".html",
    ExportFormat.DOCX: ".docx",
}
```

- [ ] **Step 5: Implémenter — formats génération + libellé UI**

Dans `src/fahmi2/domain/generation.py` :

```python
GENERATION_EXPORT_FORMATS: frozenset[ExportFormat] = frozenset(
    {ExportFormat.MARKDOWN, ExportFormat.PDF, ExportFormat.HTML, ExportFormat.DOCX}
)
```

Dans `src/fahmi2/ui/pedagogy_labels.py`, dans `EXPORT_LABELS` :

```python
EXPORT_LABELS: dict[ExportFormat, str] = {
    ExportFormat.APKG: "Anki (.apkg)",
    ExportFormat.MARKDOWN: "Markdown",
    ExportFormat.PDF: "PDF",
    ExportFormat.HTML: "HTML",
    ExportFormat.DOCX: "Word (.docx)",
}
```

- [ ] **Step 6: Lancer les tests**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/domain/test_enums.py tests/unit/infra/export/test_markdown_pdf.py::test_extension_includes_docx -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/fahmi2/domain/enums.py src/fahmi2/infra/export/markdown_pdf.py src/fahmi2/domain/generation.py src/fahmi2/ui/pedagogy_labels.py tests/unit/domain/test_enums.py tests/unit/infra/export/test_markdown_pdf.py
git commit -m "feat(export): introduit le format DOCX (enum, extension, libelle)"
```

---

## Task 6 : Dépendances DOCX + renderer `markdown_docx.py`

**Files:**
- Modify: `pyproject.toml`
- Create: `src/fahmi2/infra/export/markdown_docx.py`
- Test: `tests/unit/infra/export/test_markdown_docx.py`

- [ ] **Step 1: Ajouter les dépendances et installer**

Dans `pyproject.toml`, dans `dependencies`, ajouter sous `python-docx` :

```toml
  "htmldocx>=0.0.6,<0.1",
  "beautifulsoup4>=4.7,<5",
```

Puis installer dans le venv :

Run: `.venv\Scripts\python.exe -m pip install "htmldocx>=0.0.6,<0.1" "beautifulsoup4>=4.7,<5"`
Expected: `Successfully installed htmldocx-... beautifulsoup4-... soupsieve-...`

- [ ] **Step 2: Écrire le test qui échoue**

Créer `tests/unit/infra/export/test_markdown_docx.py` :

```python
"""Tests du rendu Markdown → DOCX (htmldocx)."""

from __future__ import annotations

import zipfile
from pathlib import Path

from fahmi2.infra.export.markdown_docx import render_markdown_to_docx

_MD = (
    "# Titre\n\n"
    "Paragraphe **gras** et *italique*.\n\n"
    "## Sous-titre 第一章\n\n"
    "| A | B |\n|---|---|\n| 中文 | عربي |\n\n"
    "- point un\n- point deux\n"
)


def _document_xml(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        return archive.read("word/document.xml").decode("utf-8")


def test_render_docx_creates_valid_file(tmp_path: Path) -> None:
    out = tmp_path / "doc.docx"
    render_markdown_to_docx(_MD, out)
    assert out.exists()
    # Un .docx est un zip OOXML : signature "PK".
    assert out.read_bytes()[:2] == b"PK"


def test_render_docx_preserves_structure_and_unicode(tmp_path: Path) -> None:
    out = tmp_path / "doc.docx"
    render_markdown_to_docx(_MD, out)
    xml = _document_xml(out)
    assert "Titre" in xml
    assert "<w:tbl>" in xml          # tableau converti
    assert "第一章" in xml            # chinois préservé
    assert "عربي" in xml             # arabe préservé
```

- [ ] **Step 3: Lancer pour vérifier l'échec**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/infra/export/test_markdown_docx.py -v`
Expected: FAIL with "No module named 'fahmi2.infra.export.markdown_docx'"

- [ ] **Step 4: Créer le renderer**

Créer `src/fahmi2/infra/export/markdown_docx.py` :

```python
"""Renderer d'export Markdown → DOCX (Word), via HTML intermédiaire.

Réutilise le rendu Markdown → HTML du module ``markdown_pdf`` (mêmes extensions
``tables``/``toc``), puis convertit le HTML en document Word avec ``htmldocx``
(qui s'appuie sur ``python-docx``). Pur *renderer* : l'orchestration (collecte,
dispatch par format) vit dans ``app.document_export``.

Word applique nativement la bidirectionnalité (arabe) et la substitution de
police (chinois) à l'affichage : aucune police à déclarer côté DOCX.
"""

from __future__ import annotations

from pathlib import Path

import markdown
from docx import Document
from htmldocx import HtmlToDocx

#: Mêmes extensions que le rendu HTML/PDF (tableaux GFM + sommaire).
_MARKDOWN_EXTENSIONS: list[str] = ["tables", "toc"]


def render_markdown_to_docx(markdown_text: str, output_path: Path) -> None:
    """Rend un Markdown en document Word ``.docx``.

    Args:
        markdown_text: Texte Markdown.
        output_path: Chemin du fichier ``.docx`` à écrire.
    """
    body = markdown.markdown(markdown_text, extensions=_MARKDOWN_EXTENSIONS)
    document = Document()
    HtmlToDocx().add_html_to_document(body, document)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    document.save(str(output_path))
```

- [ ] **Step 5: Lancer le test**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/infra/export/test_markdown_docx.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml src/fahmi2/infra/export/markdown_docx.py tests/unit/infra/export/test_markdown_docx.py
git commit -m "feat(export): renderer Markdown->DOCX via htmldocx"
```

---

## Task 7 : `ExportDocument.language` + dispatch DOCX dans `write_documents`

**Files:**
- Modify: `src/fahmi2/app/document_export.py:26-43,92-111`
- Modify: `src/fahmi2/app/generation_export.py:55-73`
- Modify: `src/fahmi2/app/pedagogy_export.py:100-119`
- Test: `tests/unit/app/test_document_export.py`

- [ ] **Step 1: Écrire le test qui échoue**

Ajouter dans `tests/unit/app/test_document_export.py` :

```python
def test_write_documents_dispatches_docx(tmp_path: Path) -> None:
    from fahmi2.app.document_export import ExportDocument, write_documents
    from fahmi2.domain.enums import ExportFormat

    docs = [ExportDocument(stem="support.fr", markdown="# Titre\n\nTexte.\n")]
    result = write_documents(docs, output_dir=tmp_path, fmt=ExportFormat.DOCX)
    out = tmp_path / "support.fr.docx"
    assert out in result.output_paths
    assert out.read_bytes()[:2] == b"PK"


def test_export_document_carries_language() -> None:
    from fahmi2.app.document_export import ExportDocument
    from fahmi2.domain.enums import Language

    doc = ExportDocument(stem="x", markdown="# x", language=Language.AR)
    assert doc.language is Language.AR
    # Défaut rétro-compatible : FR si non précisé.
    assert ExportDocument(stem="y", markdown="# y").language is Language.FR
```

- [ ] **Step 2: Lancer pour vérifier l'échec**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/app/test_document_export.py::test_write_documents_dispatches_docx tests/unit/app/test_document_export.py::test_export_document_carries_language -v`
Expected: FAIL (`DOCX` non géré → `ValueError` ; `language` inconnu)

- [ ] **Step 3: Ajouter le champ `language`**

Dans `src/fahmi2/app/document_export.py`, ajouter l'import `Language` et le champ :

```python
from fahmi2.domain.enums import ExportFormat, Language
```

Dans `ExportDocument`, ajouter après `pdf_column_widths` (et compléter la docstring `Attributes` avec `language`) :

```python
    language: Language = Language.FR
```

- [ ] **Step 4: Dispatcher DOCX dans `write_documents`**

Dans `src/fahmi2/app/document_export.py`, ajouter l'import du renderer DOCX :

```python
from fahmi2.infra.export.markdown_docx import render_markdown_to_docx
```

Remplacer la boucle d'écriture par (ajoute la branche DOCX et passe `language` au PDF) :

```python
    for document in documents:
        path = output_dir / f"{document.stem}{extension}"
        if fmt is ExportFormat.MARKDOWN:
            store.write_text_atomic(path, document.markdown)
        elif fmt is ExportFormat.PDF:
            render_markdown_to_pdf(
                document.markdown,
                path,
                landscape=document.pdf_landscape,
                table_column_widths=document.pdf_column_widths,
            )
        elif fmt is ExportFormat.DOCX:
            render_markdown_to_docx(document.markdown, path)
        else:  # HTML (seul format documentaire restant après la garde)
            render_markdown_to_html(document.markdown, path)
        paths.append(path)
```

> Note : `ExportDocument.language` est ajouté ici (et renseigné par les collecteurs), mais n'est **consommé** par le PDF/HTML qu'en Task 8 (où les renderers gagnent le paramètre `language` et où `write_documents` le transmet). Cette tâche n'emprunte que les branches MARKDOWN/DOCX dans ses tests → la suite reste verte.

- [ ] **Step 5: Renseigner `language` dans les collecteurs**

Dans `src/fahmi2/app/generation_export.py`, ajouter `language=language` aux deux `ExportDocument` :

```python
        if consolidated.exists():
            documents.append(
                ExportDocument(
                    stem=consolidated.stem,
                    markdown=consolidated.read_text(encoding=_ENCODING_UTF8),
                    language=language,
                )
            )
        glossary = output_dir / glossary_doc_filename(language)
        if glossary.exists():
            documents.append(
                ExportDocument(
                    stem=glossary.stem,
                    markdown=glossary.read_text(encoding=_ENCODING_UTF8),
                    pdf_landscape=True,
                    pdf_column_widths=_GLOSSARY_PDF_COLUMN_WIDTHS,
                    language=language,
                )
            )
```

Dans `src/fahmi2/app/pedagogy_export.py`, ajouter `language=language` aux deux `ExportDocument` du `collect_pedagogy_documents` :

```python
            if subject_path.exists():
                documents.append(
                    ExportDocument(
                        stem=f"{support.value}.{language.value}",
                        markdown=subject_path.read_text(encoding=_ENCODING_UTF8),
                        language=language,
                    )
                )
            ...
            if correction_path.exists():
                documents.append(
                    ExportDocument(
                        stem=f"{support.value}.{language.value}{_CORRECTION_SUFFIX}",
                        markdown=correction_path.read_text(encoding=_ENCODING_UTF8),
                        language=language,
                    )
                )
```

- [ ] **Step 6: Lancer les tests**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/app/test_document_export.py -v`
Expected: PASS (la branche DOCX et le défaut `language` passent ; le PDF reste couvert par Task 8)

- [ ] **Step 7: Commit**

```bash
git add src/fahmi2/app/document_export.py src/fahmi2/app/generation_export.py src/fahmi2/app/pedagogy_export.py tests/unit/app/test_document_export.py
git commit -m "feat(export): ExportDocument.language + dispatch DOCX"
```

---

## Task 8 : Rendu PDF CJK (chinois) + RTL (arabe)

**Files:**
- Modify: `src/fahmi2/infra/export/markdown_pdf.py`
- Test: `tests/unit/infra/export/test_markdown_pdf.py`

- [ ] **Step 1: Écrire les tests qui échouent**

Ajouter dans `tests/unit/infra/export/test_markdown_pdf.py` :

```python
import io

from fahmi2.domain.enums import Language
from fahmi2.infra.export.markdown_pdf import cjk_font_available


def _embedded_font_bases(pdf_bytes: bytes) -> list[str]:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(pdf_bytes))
    bases: list[str] = []
    for value in reader.pages[0]["/Resources"]["/Font"].values():
        bases.append(str(value.get_object().get("/BaseFont")))
    return bases


@pytest.mark.skipif(not cjk_font_available(), reason="Police CJK indisponible")
def test_render_pdf_chinese_embeds_cjk_font(tmp_path: Path) -> None:
    out = tmp_path / "zh.pdf"
    render_markdown_to_pdf(
        "# 第一章 机器学习\n\n这是中文测试段落。\n", out, language=Language.ZH
    )
    pdf = out.read_bytes()
    assert pdf[:5] == b"%PDF-"
    assert any("YaHei" in base for base in _embedded_font_bases(pdf))


@pytest.mark.skipif(not pdf_fonts_available(), reason="Police Unicode indisponible")
def test_render_pdf_arabic_is_shaped(tmp_path: Path) -> None:
    from pypdf import PdfReader

    out = tmp_path / "ar.pdf"
    render_markdown_to_pdf("مرحبا بالعالم هذا اختبار\n", out, language=Language.AR)
    pdf = out.read_bytes()
    assert pdf[:5] == b"%PDF-"
    text = PdfReader(io.BytesIO(pdf)).pages[0].extract_text()
    # Lettres arabes liées => formes de présentation U+FE70..U+FEFF.
    assert any(0xFE70 <= ord(ch) <= 0xFEFF for ch in text)


def test_render_pdf_chinese_raises_without_cjk_font(tmp_path: Path, monkeypatch) -> None:
    from fahmi2.core.errors.exceptions import ConfigError
    from fahmi2.infra.export import markdown_pdf as mod

    monkeypatch.setattr(mod, "_cjk_font_path", lambda: Path("nonexistent.ttc"))
    mod._ensure_language_fonts_registered.cache_clear()
    with pytest.raises(ConfigError) as excinfo:
        render_markdown_to_pdf("# 测试\n", tmp_path / "x.pdf", language=Language.ZH)
    assert excinfo.value.code == "EXPORT.NO_CJK_FONT"
    mod._ensure_language_fonts_registered.cache_clear()
```

- [ ] **Step 2: Lancer pour vérifier l'échec**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/infra/export/test_markdown_pdf.py -k "chinese or arabic or cjk" -v`
Expected: FAIL (`cjk_font_available` / `language` inconnus)

- [ ] **Step 3: Implémenter — résolution et enregistrement des polices**

Dans `src/fahmi2/infra/export/markdown_pdf.py`, ajouter les imports en tête :

```python
from xhtml2pdf import default as xhtml2pdf_default

from fahmi2.domain.enums import ExportFormat, Language
```

Ajouter après le bloc des constantes de police (`_WINDOWS_FONT_FILES`) :

```python
#: Police CJK système Windows (TrueType Collection) — Microsoft YaHei (regular +
#: gras). Chargée via ``subfontIndex`` (ReportLab gère les TTC ainsi).
_CJK_FONT_FILE_REGULAR = "msyh.ttc"
_CJK_FONT_FILE_BOLD = "msyhbd.ttc"
_CJK_FONT_NAME = "CJKFont"
_CJK_FONT_NAME_BOLD = "CJKFont-Bold"
#: Police arabe : Arial système (TTF simple, glyphes arabes complets).
_ARABIC_FONT_NAME = "ArabicFont"
#: Familles ``font-family`` injectées dans la table de résolution xhtml2pdf.
_CJK_FAMILY = "cjk"
_ARABIC_FAMILY = "arab"
#: Tag xhtml2pdf déclenchant le reshaping + bidi (cf. xhtml2pdf/util.py).
_PDF_LANGUAGE_TAG_ARABIC = '<pdf:language name="arabic"/>'


def _cjk_font_path() -> Path:
    """Chemin de la police CJK régulière système.

    Returns:
        ``%SystemRoot%/Fonts/msyh.ttc``.
    """
    return _fonts_dir() / _CJK_FONT_FILE_REGULAR


def cjk_font_available() -> bool:
    """Indique si la police CJK (Microsoft YaHei) est résolue.

    Returns:
        ``True`` si le rendu PDF chinois est possible.
    """
    return _cjk_font_path().exists()
```

- [ ] **Step 4: Implémenter — enregistrement par langue (mémoïsé)**

Toujours dans `markdown_pdf.py`, ajouter une fonction mémoïsée d'enregistrement et d'injection dans `DEFAULT_FONT` :

```python
@functools.cache
def _ensure_language_fonts_registered() -> None:
    """Enregistre les polices CJK et arabe et les injecte dans xhtml2pdf.

    - CJK : Microsoft YaHei (TTC) via ``subfontIndex`` (regular + gras).
    - Arabe : Arial système (réutilise les fichiers déjà connus du module).

    Injecte les familles ``cjk``/``arab`` dans ``xhtml2pdf.default.DEFAULT_FONT``
    (point d'injection standard : ``pisa.CreatePDF`` n'expose pas de hook de
    registre). Idempotent et mémoïsé : exécuté une fois.

    Raises:
        ConfigError: ``EXPORT.NO_CJK_FONT`` si Microsoft YaHei est introuvable.
    """
    fonts = _fonts_dir()
    if not _cjk_font_path().exists():
        raise ConfigError(
            code="EXPORT.NO_CJK_FONT",
            user_message=(
                "Police chinoise (Microsoft YaHei) introuvable pour l'export PDF. "
                "Utilisez l'export Markdown, HTML ou Word."
            ),
            severity=Severity.ERROR,
        )
    pdfmetrics.registerFont(
        TTFont(_CJK_FONT_NAME, str(fonts / _CJK_FONT_FILE_REGULAR), subfontIndex=0)
    )
    bold_path = fonts / _CJK_FONT_FILE_BOLD
    bold_name = _CJK_FONT_NAME_BOLD if bold_path.exists() else _CJK_FONT_NAME
    if bold_path.exists():
        pdfmetrics.registerFont(TTFont(bold_name, str(bold_path), subfontIndex=0))
    addMapping(_CJK_FONT_NAME, 0, 0, _CJK_FONT_NAME)
    addMapping(_CJK_FONT_NAME, 1, 0, bold_name)
    xhtml2pdf_default.DEFAULT_FONT[_CJK_FAMILY] = _CJK_FONT_NAME

    pdfmetrics.registerFont(TTFont(_ARABIC_FONT_NAME, str(fonts / _WINDOWS_FONT_FILES[""])))
    pdfmetrics.registerFont(
        TTFont(_ARABIC_FONT_NAME + "-Bold", str(fonts / _WINDOWS_FONT_FILES["B"]))
    )
    addMapping(_ARABIC_FONT_NAME, 0, 0, _ARABIC_FONT_NAME)
    addMapping(_ARABIC_FONT_NAME, 1, 0, _ARABIC_FONT_NAME + "-Bold")
    xhtml2pdf_default.DEFAULT_FONT[_ARABIC_FAMILY] = _ARABIC_FONT_NAME
```

- [ ] **Step 5: Implémenter — sélection par langue + gabarit paramétré**

Dans `markdown_pdf.py`, ajouter une table de configuration par langue et adapter le gabarit `_PDF_HTML_TEMPLATE` pour accepter `font_family` + `direction`. Remplacer `_PDF_HTML_TEMPLATE` par :

```python
_PDF_HTML_TEMPLATE = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
@page {{ size: a4 {orientation}; margin: 1.8cm; }}
body {{ font-family: "{font_family}"; font-size: 10.5pt; line-height: 1.4; color: #1f2328; direction: {direction}; }}
h1 {{ font-size: 19pt; color: #0a4f93; }}
h2 {{ font-size: 14pt; color: #0a4f93; }}
h3 {{ font-size: 12pt; color: #0a4f93; }}
h4, h5, h6 {{ font-size: 11pt; color: #0a4f93; }}
li {{ margin-bottom: 2pt; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ border: 0.5pt solid #d0d7de; padding: 3pt 5pt; text-align: left;
         vertical-align: top; }}
th {{ background: #f5f7fb; }}
a {{ color: #0a4f93; text-decoration: none; }}
</style></head><body>
{language_tag}{body}
</body></html>
"""
```

Ajouter, près des constantes de police, la table de configuration :

```python
#: Configuration de rendu PDF par langue : (famille font-family, direction CSS,
#: tag pdf:language). Latin (FR/EN/DE/ES/IT) → police par défaut (Helvetica),
#: LTR, sans tag. ZH → famille CJK injectée. AR → famille arabe + RTL + tag.
_PDF_DEFAULT_FAMILY = _PDF_FONT_FAMILY  # "AppSans" (résolu en Helvetica par xhtml2pdf)
_PDF_LANG_CONFIG: dict[Language, tuple[str, str, str]] = {
    Language.ZH: (_CJK_FAMILY, "ltr", ""),
    Language.AR: (_ARABIC_FAMILY, "rtl", _PDF_LANGUAGE_TAG_ARABIC),
}
```

- [ ] **Step 6: Implémenter — signatures `render_markdown_to_pdf` / `render_markdown_to_html`**

Dans `markdown_pdf.py`, modifier `render_markdown_to_pdf` pour accepter `language` et router la police :

```python
def render_markdown_to_pdf(
    markdown_text: str,
    output_path: Path,
    *,
    landscape: bool = False,
    table_column_widths: tuple[str, ...] | None = None,
    language: Language = Language.FR,
) -> None:
    """Rend un Markdown en PDF via ``xhtml2pdf`` (Markdown → HTML → PDF).

    Args:
        markdown_text: Texte Markdown.
        output_path: Chemin du PDF à écrire.
        landscape: Orientation paysage (ex: glossaire large) ; portrait sinon.
        table_column_widths: Largeurs CSS par colonne appliquées aux tableaux.
        language: Langue du contenu (sélectionne la police et la direction :
            chinois → police CJK, arabe → police arabe + RTL + shaping).

    Raises:
        ConfigError: ``EXPORT.NO_PDF_FONT`` si la police Arial est introuvable,
            ``EXPORT.NO_CJK_FONT`` si la police chinoise manque (langue ZH), ou
            ``EXPORT.PDF_RENDER_FAILED`` si le moteur de rendu échoue.
    """
    if not pdf_fonts_available():
        raise ConfigError(
            code="EXPORT.NO_PDF_FONT",
            user_message=(
                "Aucune police Unicode trouvée pour l'export PDF. Utilisez "
                "l'export Markdown, HTML ou Word."
            ),
            severity=Severity.ERROR,
        )
    _ensure_pdf_fonts_registered()
    family, direction, language_tag = _PDF_LANG_CONFIG.get(
        language, (_PDF_DEFAULT_FAMILY, "ltr", "")
    )
    if language in _PDF_LANG_CONFIG:
        _ensure_language_fonts_registered()
    body = markdown.markdown(
        _normalize_for_pdf(markdown_text),
        extensions=_MARKDOWN_EXTENSIONS,
        extension_configs={"toc": {"slugify": _toc_slugify}},
    )
    body = _layout_table_cells(body, table_column_widths)
    document = _PDF_HTML_TEMPLATE.format(
        orientation="landscape" if landscape else "portrait",
        font_family=family,
        direction=direction,
        language_tag=language_tag,
        body=body,
    )
    buffer = io.BytesIO()
    status = pisa.CreatePDF(document, dest=buffer, encoding="utf-8")
    if status.err:
        raise ConfigError(
            code="EXPORT.PDF_RENDER_FAILED",
            user_message="Le rendu du PDF a échoué. Utilisez l'export Markdown, HTML ou Word.",
            severity=Severity.ERROR,
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(buffer.getvalue())
```

Modifier `render_markdown_to_html` pour poser `lang`/`dir` selon la langue. Remplacer la signature et l'appel au gabarit, et ajouter `direction`/`lang` au `_HTML_DOCUMENT_TEMPLATE` (remplacer `<html lang="fr">` par `<html lang="{lang}" dir="{direction}">` et ajouter les deux paramètres au `.format`) :

```python
def render_markdown_to_html(
    markdown_text: str,
    output_path: Path,
    *,
    language: Language = Language.FR,
) -> None:
    """Rend un Markdown en document HTML autonome (UTF-8, style intégré).

    Args:
        markdown_text: Texte Markdown (commençant idéalement par un titre H1).
        output_path: Chemin du fichier ``.html`` à écrire.
        language: Langue du contenu (pose ``lang`` et ``dir`` ; arabe → RTL).
    """
    body = markdown.markdown(
        markdown_text,
        extensions=_MARKDOWN_EXTENSIONS,
        extension_configs={"toc": {"slugify": _toc_slugify}},
    )
    direction = "rtl" if language is Language.AR else "ltr"
    document = _HTML_DOCUMENT_TEMPLATE.format(
        title=escape(_extract_title(markdown_text)),
        body=body,
        lang=language.value,
        direction=direction,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(document, encoding="utf-8")
```

Et dans `_HTML_DOCUMENT_TEMPLATE`, remplacer la ligne `<html lang="fr">` par :

```python
<html lang="{lang}" dir="{direction}">
```

- [ ] **Step 6b: Transmettre `language` depuis `write_documents`**

Dans `src/fahmi2/app/document_export.py`, compléter les branches PDF et HTML de la boucle de `write_documents` pour passer la langue du document :

```python
        elif fmt is ExportFormat.PDF:
            render_markdown_to_pdf(
                document.markdown,
                path,
                landscape=document.pdf_landscape,
                table_column_widths=document.pdf_column_widths,
                language=document.language,
            )
        elif fmt is ExportFormat.DOCX:
            render_markdown_to_docx(document.markdown, path)
        else:  # HTML (seul format documentaire restant après la garde)
            render_markdown_to_html(document.markdown, path, language=document.language)
```

- [ ] **Step 7: Lancer les tests PDF**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/infra/export/test_markdown_pdf.py -v`
Expected: PASS (les tests zh/ar s'exécutent si les polices système sont présentes, sinon `skip` ; le test de garde `NO_CJK_FONT` passe)

- [ ] **Step 8: Vérifier la non-régression du document_export**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/app/test_document_export.py -v`
Expected: PASS

- [ ] **Step 9: Commit**

```bash
git add src/fahmi2/infra/export/markdown_pdf.py src/fahmi2/app/document_export.py tests/unit/infra/export/test_markdown_pdf.py
git commit -m "feat(export): rendu PDF chinois (CJK) et arabe (RTL shape+bidi)"
```

---

## Task 9 : Libellés UI des langues (fin du code brut)

**Files:**
- Modify: `src/fahmi2/ui/widgets/language_selection_view.py:36-44`
- Modify: `src/fahmi2/ui/dialogs/pedagogy_settings_view.py:252-254`
- Test: `tests/unit/ui/test_language_selection_view.py`

- [ ] **Step 1: Écrire le test qui échoue**

Ajouter dans `tests/unit/ui/test_language_selection_view.py` :

```python
def test_language_selection_uses_display_labels(qtbot) -> None:
    from fahmi2.domain.enums import Language
    from fahmi2.ui.widgets.language_selection_view import LanguageSelectionView

    view = LanguageSelectionView(tuple(Language))
    qtbot.addWidget(view)
    labels = {
        view._checks[lang].text() for lang in Language  # type: ignore[attr-defined]
    }
    assert "Chinois" in labels
    assert "Arabe" in labels
    assert "fr" not in labels  # plus de code brut
```

- [ ] **Step 2: Lancer pour vérifier l'échec**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/ui/test_language_selection_view.py::test_language_selection_uses_display_labels -v`
Expected: FAIL si le widget montrait des codes (sinon vérifie au moins la présence de Chinois/Arabe une fois l'enum étendu).

- [ ] **Step 3: Implémenter — `language_selection_view`**

Dans `src/fahmi2/ui/widgets/language_selection_view.py`, supprimer `_LANGUAGE_LABELS` (lignes 36-39) et la fonction `_language_label` (lignes 42-44). Ajouter l'import :

```python
from fahmi2.domain.languages import language_display_label
```

Remplacer les deux usages de `_language_label(lang)` (constructeur ligne 69 et `_rebuild_primary_combo` ligne 146) par `language_display_label(lang)`.

- [ ] **Step 4: Implémenter — `pedagogy_settings_view`**

Dans `src/fahmi2/ui/dialogs/pedagogy_settings_view.py`, ajouter l'import :

```python
from fahmi2.domain.languages import language_display_label
```

Remplacer la ligne 254 :

```python
            self._language_checks[lang] = QCheckBox(language_display_label(lang), self)
```

- [ ] **Step 5: Lancer les tests UI**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/ui/test_language_selection_view.py tests/unit/ui/dialogs -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/fahmi2/ui/widgets/language_selection_view.py src/fahmi2/ui/dialogs/pedagogy_settings_view.py tests/unit/ui/test_language_selection_view.py
git commit -m "refactor(ui): libelles de langue capitalises via domain.languages"
```

---

## Task 10 : Packaging (.spec)

**Files:**
- Modify: `packaging/fahmi2.spec` (gitignored — non versionné)

- [ ] **Step 1: Ajouter la collecte bs4/htmldocx**

Dans `packaging/fahmi2.spec`, à côté du bloc `collect_data_files("docx")`, ajouter :

```python
hiddenimports += ["htmldocx"]
hiddenimports += collect_submodules("bs4")
```

(`arabic_reshaper`/`python-bidi` restent collectés via `collect_all("xhtml2pdf")` déjà présent ; les polices CJK/Arabic sont système → rien à bundler.)

- [ ] **Step 2: Vérifier l'import à froid**

Run: `.venv\Scripts\python.exe -c "import htmldocx, bs4; from fahmi2.infra.export.markdown_docx import render_markdown_to_docx; print('ok')"`
Expected: `ok`

- [ ] **Step 3: (pas de commit — fichier gitignored)**

Le `.spec` n'est pas versionné ; noter le changement dans `packaging/README.md` (Task 11).

---

## Task 11 : Documentation

**Files:**
- Modify: `CLAUDE.md`, `README.md`, `packaging/README.md`

- [ ] **Step 1: Mettre à jour `CLAUDE.md`**

- Section « Projet » / `Language` : indiquer que les langues gérées sont
  **FR/EN/DE/ES/IT/ZH/AR** (au lieu de FR/EN).
- Section « Mécanismes transverses » : ajouter une puce **Export PDF multilingue**
  expliquant polices système (YaHei via `subfontIndex`, Arial pour l'arabe),
  injection dans `xhtml2pdf.default.DEFAULT_FONT`, tag `<pdf:language>` pour le
  shaping arabe, garde `EXPORT.NO_CJK_FONT` ; et **Export DOCX** (`markdown_docx`
  via htmldocx, Markdown→HTML→docx).
- Mentionner la **limitation lexicale chinoise** du Dialogue (TF-IDF) et la
  mitigation `AUTO`→sémantique.
- Mettre à jour la liste `ExportFormat` (`×4` → DOCX inclus) et `infra/export`.

- [ ] **Step 2: Mettre à jour `README.md`**

Ajouter les 5 langues dans la description des fonctionnalités et un mot sur les
formats d'export (MD/PDF/HTML/DOCX). Recommander le mode sémantique du Dialogue
pour le chinois.

- [ ] **Step 3: Mettre à jour `packaging/README.md`**

Documenter : dépendances DOCX (`htmldocx`, `beautifulsoup4` ; `lxml` déjà tiré par
`python-docx`) et le bloc `.spec` correspondant ; rappeler que les polices
CJK/Arabic sont **système Windows** (rien à bundler).

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md README.md packaging/README.md
git commit -m "docs: langues supplementaires, export DOCX, rendu PDF CJK/RTL"
```

---

## Task 12 : Vérifications systématiques finales

- [ ] **Step 1: Suite de tests complète**

Run: `.venv\Scripts\python.exe -m pytest`
Expected: tous verts (les tests PDF zh/ar `skip` si polices absentes).

- [ ] **Step 2: Lint**

Run: `.venv\Scripts\python.exe -m ruff check .`
Expected: `All checks passed!`

- [ ] **Step 3: Typage**

Run: `.venv\Scripts\python.exe -m mypy src tests`
Expected: `Success: no issues found`

- [ ] **Step 4: Lancement rapide de l'app (fumée manuelle, facultatif)**

Run: `.venv\Scripts\python.exe -m fahmi2.ui.app_main`
Vérifier : les 7 langues apparaissent dans le sélecteur Génération et les cases
Pédagogie ; le format **Word (.docx)** est proposé à l'export.

- [ ] **Step 5: Repasser si nécessaire**

Si un défaut subsiste, corriger et relancer Steps 1-3 jusqu'à zéro défaut.

---

## Self-review (couverture du spec)

- §2 langues → Task 1 ✓ ; propagation UI → Tasks 9, 12 ✓
- §3 centralisation libellés → Task 2 ✓
- §4 en-têtes glossaire → Task 3 ✓
- §5 PDF CJK/RTL → Task 8 (polices système + DEFAULT_FONT + pdf:language + garde) ✓
- §6 DOCX → Tasks 5, 6, 7 ✓
- §7 limitation lexicale CJK → documentation Task 11 ✓ (pas de code, conforme YAGNI)
- §8 coût inchangé → aucune tâche (vérifié : compteurs agnostiques) ✓
- §9 découpage par couche → couvert tâche par tâche ✓
- §10 tests → Tasks 1-9 (TDD) + Task 12 ✓
- §11 doc → Task 11 ✓
- §12 hors-périmètre → respecté (pas de tokenizer CJK, pas de RTL UI) ✓
