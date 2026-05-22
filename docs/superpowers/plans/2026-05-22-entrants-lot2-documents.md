# Lot 2 — Documents texte (pdf, docx, md, txt) : ingestion + reformulation réglable + coût (plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Accepter les **documents texte** (pdf, docx, md, txt) comme entrants de la génération : extraction de texte → `Transcription` à **segment unique** (structure préservée), avec un drapeau projet `reformulate_documents` (pass-through phase 3 si désactivé) et une estimation de coût adaptée (`SourceWeight`).

**Architecture:** Nouvel adapter `DocumentIngestor` (branché sur le dispatcher existant via un `TextExtractor` port). Un document devient une `Transcription` à **un seul segment** portant le texte intégral — `_load_transcription_text` le restitue intact (pas d'aplatissement), ce qui rend le pass-through fidèle. Le `CostEstimator` passe de `videos_durations_seconds` à `list[SourceWeight]` (durée audio **ou** tokens texte par source, drapeau `reformulated`). Le pipeline aval (phases 1-7) est inchangé hors le pass-through optionnel de la phase 3.

**Tech Stack:** Python 3.12, `pypdf` (BSD, typé), `python-docx` (MIT, module `docx`), pytest, ruff (line-length 100), mypy --strict. Interpréteur : `.venv\Scripts\python.exe`.

**Prérequis:** Lots 1A + 1B appliqués (couche `infra/ingestion/`, dispatcher, `build_input_sources`, `PhaseContext.ingestion`).

**Spec de référence:** `docs/superpowers/specs/2026-05-22-entrants-generation-elargis-design.md` (§4.4, §4.5, §6, §8 SourceWeight, §10).

---

## Tâche 1 : Dépendances pypdf + python-docx

**Files:** Modify `pyproject.toml`

- [ ] **Step 1: Ajouter les dépendances runtime**

Dans `[project].dependencies`, ajouter :
```toml
  "pypdf>=4,<6",
  "python-docx>=1.1,<2",
```

- [ ] **Step 2: mypy override pour `docx` (pas de stubs ; pypdf est typé)**

Dans `[[tool.mypy.overrides]].module`, ajouter `"docx.*",`.

- [ ] **Step 3: Installer dans le venv**

Run: `.venv\Scripts\python.exe -m pip install "pypdf>=4,<6" "python-docx>=1.1,<2"`
Expected: installation réussie.

- [ ] **Step 4: Vérifier l'import**

Run: `.venv\Scripts\python.exe -c "import pypdf, docx; print('ok')"`
Expected: `ok`

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml
git commit -m "build: ajoute pypdf + python-docx (entrants documents)"
```

---

## Tâche 2 : Étendre `classify` aux documents

**Files:** Modify `src/fahmi2/infra/ingestion/classify.py` ; Modify `tests/unit/infra/ingestion/test_classify.py`

- [ ] **Step 1: Mettre à jour les tests existants**

Dans `test_classify.py`, changer les cas `("a.txt", None)` et `("a.pdf", None)` en `SourceKind.DOCUMENT`, et ajouter `("a.docx", SourceKind.DOCUMENT)`, `("a.MD", SourceKind.DOCUMENT)`. Dans `test_supported_extensions_contains_audio_and_video`, remplacer `assert ".txt" not in exts` par `assert ".txt" in exts` et `assert ".pdf" in exts`.

- [ ] **Step 2: Lancer (échec attendu)**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/infra/ingestion/test_classify.py -v`
Expected: FAIL (`.txt` classé `None`).

- [ ] **Step 3: Ajouter les extensions document**

Dans `classify.py`, après `AUDIO_EXTENSIONS` :
```python
#: Extensions document reconnues (minuscules, point initial inclus).
DOCUMENT_EXTENSIONS: frozenset[str] = frozenset({".pdf", ".docx", ".md", ".txt"})
```
Et dans `_EXTENSION_TO_KIND`, ajouter :
```python
    **{ext: SourceKind.DOCUMENT for ext in DOCUMENT_EXTENSIONS},
```

- [ ] **Step 4: Lancer (succès)** — `pytest tests/unit/infra/ingestion/test_classify.py -v` → PASS
- [ ] **Step 5: Commit** — `git commit -m "feat(ingestion): classify reconnait les documents (pdf/docx/md/txt)"`

---

## Tâche 3 : `TextExtractor` (port + extracteur par défaut)

**Files:** Create `src/fahmi2/infra/ingestion/text_extractor.py` ; Test `tests/unit/infra/ingestion/test_text_extractor.py`

- [ ] **Step 1: Écrire les tests**

```python
# tests/unit/infra/ingestion/test_text_extractor.py
from pathlib import Path

import pytest
from docx import Document

from fahmi2.core.errors.exceptions import IngestionError
from fahmi2.infra.ingestion.text_extractor import DefaultTextExtractor


def test_extract_txt(tmp_path: Path) -> None:
    p = tmp_path / "notes.txt"
    p.write_text("Ligne 1\n\nLigne 2", encoding="utf-8")
    assert DefaultTextExtractor().extract(p) == "Ligne 1\n\nLigne 2"


def test_extract_md_preserves_structure(tmp_path: Path) -> None:
    p = tmp_path / "cours.md"
    p.write_text("# Titre\n\nParagraphe.", encoding="utf-8")
    assert "# Titre" in DefaultTextExtractor().extract(p)


def test_extract_docx(tmp_path: Path) -> None:
    p = tmp_path / "doc.docx"
    doc = Document()
    doc.add_paragraph("Premier paragraphe.")
    doc.add_paragraph("Second paragraphe.")
    doc.save(str(p))
    text = DefaultTextExtractor().extract(p)
    assert "Premier paragraphe." in text
    assert "Second paragraphe." in text


def test_extract_unsupported_raises(tmp_path: Path) -> None:
    p = tmp_path / "x.zip"
    p.write_bytes(b"x")
    with pytest.raises(IngestionError) as exc:
        DefaultTextExtractor().extract(p)
    assert exc.value.code == "INGESTION.TEXT_EXTRACTION_FAILED"
```

- [ ] **Step 2: Lancer (échec)** — module absent

- [ ] **Step 3: Implémenter `text_extractor.py`**

```python
"""Extraction de texte brut depuis un document (pdf, docx, md, txt).

Port ``TextExtractor`` + implémentation par défaut. La structure (sauts de
ligne / paragraphes) est **préservée** : l'aval (reformulation ou pass-through)
reçoit le texte tel quel.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from fahmi2.core.errors.exceptions import IngestionError
from fahmi2.core.errors.severity import Severity

_PDF_PAGE_SEPARATOR = "\n\n"
_DOCX_PARAGRAPH_SEPARATOR = "\n"
_ENCODING_UTF8 = "utf-8"
_PLAIN_TEXT_SUFFIXES = frozenset({".md", ".txt"})
_PDF_SUFFIX = ".pdf"
_DOCX_SUFFIX = ".docx"


class TextExtractor(Protocol):
    """Extrait le texte brut d'un document."""

    def extract(self, path: Path) -> str:
        """Retourne le texte brut du document.

        Args:
            path: Chemin du document.

        Returns:
            Le texte extrait (structure préservée).

        Raises:
            IngestionError: ``INGESTION.TEXT_EXTRACTION_FAILED`` si le document
                est illisible ou de format non géré.
        """


class DefaultTextExtractor:
    """Extracteur par défaut : pypdf (pdf), python-docx (docx), lecture directe (md/txt)."""

    def extract(self, path: Path) -> str:
        """Extrait le texte selon l'extension du document.

        Args:
            path: Chemin du document.

        Returns:
            Le texte extrait.

        Raises:
            IngestionError: ``INGESTION.TEXT_EXTRACTION_FAILED`` si le format
                n'est pas géré ou si l'extraction échoue.
        """
        suffix = path.suffix.lower()
        try:
            if suffix in _PLAIN_TEXT_SUFFIXES:
                return path.read_text(encoding=_ENCODING_UTF8)
            if suffix == _PDF_SUFFIX:
                return self._extract_pdf(path)
            if suffix == _DOCX_SUFFIX:
                return self._extract_docx(path)
        except IngestionError:
            raise
        except Exception as exc:  # noqa: BLE001 — toute erreur lib → IngestionError
            raise _extraction_error(path, str(exc)) from exc
        raise _extraction_error(path, f"format non géré : {suffix}")

    @staticmethod
    def _extract_pdf(path: Path) -> str:
        from pypdf import PdfReader  # noqa: PLC0415 — import paresseux (dépendance lourde)

        reader = PdfReader(str(path))
        return _PDF_PAGE_SEPARATOR.join(
            (page.extract_text() or "") for page in reader.pages
        )

    @staticmethod
    def _extract_docx(path: Path) -> str:
        from docx import Document  # noqa: PLC0415 — import paresseux

        document = Document(str(path))
        return _DOCX_PARAGRAPH_SEPARATOR.join(p.text for p in document.paragraphs)


def _extraction_error(path: Path, detail: str) -> IngestionError:
    """Construit l'erreur d'extraction de texte.

    Args:
        path: Document concerné.
        detail: Détail technique.

    Returns:
        L'``IngestionError`` à lever.
    """
    return IngestionError(
        code="INGESTION.TEXT_EXTRACTION_FAILED",
        user_message=f"Impossible d'extraire le texte du document : {path.name}",
        severity=Severity.ERROR,
        technical_details={"path": str(path), "detail": detail},
    )
```

- [ ] **Step 4: Lancer (succès)** — `pytest tests/unit/infra/ingestion/test_text_extractor.py -v` → PASS
- [ ] **Step 5: Commit** — `git commit -m "feat(ingestion): TextExtractor (pdf/docx/md/txt)"`

---

## Tâche 4 : `DocumentIngestor` (segment unique) + fakes

**Files:** Create `src/fahmi2/infra/ingestion/document_ingestor.py` ; Create `src/fahmi2/infra/ingestion/_fakes.py` ; Test `tests/unit/infra/ingestion/test_document_ingestor.py`

- [ ] **Step 1: Créer le fake `FakeTextExtractor`** (`_fakes.py`)

```python
"""Doubles de test pour la couche d'ingestion."""

from __future__ import annotations

from pathlib import Path


class FakeTextExtractor:
    """``TextExtractor`` factice : renvoie un texte fixe (ou par nom de fichier)."""

    def __init__(self, *, default_text: str = "Texte de document.",
                 by_name: dict[str, str] | None = None) -> None:
        self._default = default_text
        self._by_name = dict(by_name or {})

    def extract(self, path: Path) -> str:
        """Retourne le texte scénarisé pour ``path`` (ou le défaut)."""
        return self._by_name.get(path.name, self._default)
```

- [ ] **Step 2: Écrire les tests du `DocumentIngestor`**

```python
# tests/unit/infra/ingestion/test_document_ingestor.py
from pathlib import Path

import pytest

from fahmi2.core.errors.exceptions import IngestionError
from fahmi2.domain.enums import Language, SourceKind
from fahmi2.domain.source import InputSource
from fahmi2.infra.audio.ffmpeg_extractor import FFmpegExtractor
from fahmi2.infra.ingestion._fakes import FakeTextExtractor
from fahmi2.infra.ingestion.document_ingestor import DocumentIngestor
from fahmi2.infra.ingestion.interface import IngestionDeps
from fahmi2.infra.storage.fs_artifacts import FsArtifactStore
from fahmi2.infra.stt._fakes import FakeSTTProvider


def _deps(tmp_path: Path) -> IngestionDeps:
    return IngestionDeps(
        workspace=tmp_path, artifacts=FsArtifactStore(),
        stt_provider=FakeSTTProvider(), ffmpeg=FFmpegExtractor(),
    )


def test_ingest_document_single_segment_preserves_text(tmp_path: Path) -> None:
    extractor = FakeTextExtractor(default_text="# Titre\n\nParagraphe 1.\n\nParagraphe 2.")
    ingestor = DocumentIngestor(extractor)
    transcription = ingestor.ingest(
        InputSource(kind=SourceKind.DOCUMENT, location=str(tmp_path / "c.md")),
        "01HZX9KQ7N8YV3JD4M2C6B5A0E", _deps(tmp_path),
        language_hint=Language.FR, delete_audio_after=True,
    )
    assert len(transcription.segments) == 1
    assert transcription.segments[0].text == "# Titre\n\nParagraphe 1.\n\nParagraphe 2."
    assert transcription.full_text() == "# Titre\n\nParagraphe 1.\n\nParagraphe 2."
    assert transcription.detected_language is Language.FR
    assert transcription.duration_seconds == 0.0


def test_ingest_empty_document_raises(tmp_path: Path) -> None:
    ingestor = DocumentIngestor(FakeTextExtractor(default_text="   \n  "))
    with pytest.raises(IngestionError) as exc:
        ingestor.ingest(
            InputSource(kind=SourceKind.DOCUMENT, location=str(tmp_path / "v.txt")),
            "01HZX9KQ7N8YV3JD4M2C6B5A0E", _deps(tmp_path),
            language_hint=Language.FR, delete_audio_after=True,
        )
    assert exc.value.code == "INGESTION.EMPTY_DOCUMENT"
```

- [ ] **Step 3: Lancer (échec)** — module absent

- [ ] **Step 4: Implémenter `document_ingestor.py`**

```python
"""Ingesteur des sources document (pdf, docx, md, txt) : extraction texte.

Un document est converti en une ``Transcription`` à **segment unique** portant
le texte intégral. Le découpage par paragraphe est volontairement évité :
``_load_transcription_text`` joint les segments par une espace, ce qui
aplatirait la structure ; un segment unique préserve le texte (essentiel pour
le pass-through de la phase 3). Pas d'audio, pas de STT.
"""

from __future__ import annotations

from fahmi2.core.errors.exceptions import IngestionError
from fahmi2.core.errors.severity import Severity
from fahmi2.domain.enums import Language, SourceKind
from fahmi2.domain.source import InputSource
from fahmi2.infra.ingestion.interface import IngestionDeps
from fahmi2.infra.ingestion.text_extractor import TextExtractor
from fahmi2.infra.stt.interface import Transcription, TranscriptionSegment

_DOCUMENT_DURATION_SECONDS = 0.0
_SEGMENT_TIMESTAMP_SECONDS = 0.0
_DEFAULT_DOCUMENT_LANGUAGE = Language.FR


class DocumentIngestor:
    """Ingesteur document : extraction texte → ``Transcription`` à segment unique."""

    def __init__(self, text_extractor: TextExtractor) -> None:
        """Construit l'ingesteur.

        Args:
            text_extractor: Extracteur de texte (pdf/docx/md/txt).
        """
        self._text_extractor = text_extractor

    @property
    def kind(self) -> SourceKind:
        """Type de source géré."""
        return SourceKind.DOCUMENT

    def ingest(
        self,
        source: InputSource,
        source_id: str,
        deps: IngestionDeps,
        *,
        language_hint: Language | None,
        delete_audio_after: bool,
    ) -> Transcription:
        """Extrait le texte de ``source`` en une ``Transcription`` à segment unique.

        Args:
            source: Source document locale.
            source_id: Identifiant de la source (non utilisé : pas d'artefact audio).
            deps: Dépendances injectées (non utilisées : pas de ffmpeg/STT).
            language_hint: Langue du document (= langue source du projet).
            delete_audio_after: Sans effet (pas d'audio).

        Returns:
            La ``Transcription`` à segment unique (texte intégral).

        Raises:
            IngestionError: ``INGESTION.EMPTY_DOCUMENT`` si aucun texte exploitable.
        """
        del source_id, deps, delete_audio_after  # non pertinents pour un document
        text = self._text_extractor.extract(source.as_path)
        if not text.strip():
            raise IngestionError(
                code="INGESTION.EMPTY_DOCUMENT",
                user_message=(
                    f"Le document ne contient aucun texte exploitable : "
                    f"{source.as_path.name}"
                ),
                severity=Severity.ERROR,
                technical_details={"location": source.location},
            )
        segment = TranscriptionSegment(
            start_seconds=_SEGMENT_TIMESTAMP_SECONDS,
            end_seconds=_SEGMENT_TIMESTAMP_SECONDS,
            text=text,
        )
        return Transcription(
            segments=(segment,),
            detected_language=language_hint or _DEFAULT_DOCUMENT_LANGUAGE,
            duration_seconds=_DOCUMENT_DURATION_SECONDS,
        )
```

- [ ] **Step 5: Lancer (succès)** — `pytest tests/unit/infra/ingestion/test_document_ingestor.py -v` → PASS
- [ ] **Step 6: Commit** — `git commit -m "feat(ingestion): DocumentIngestor (segment unique) + FakeTextExtractor"`

---

## Tâche 5 : Brancher `DocumentIngestor` dans le dispatcher

**Files:** Modify `src/fahmi2/infra/ingestion/dispatcher.py` ; Modify `tests/unit/infra/ingestion/test_dispatcher.py`

- [ ] **Step 1: Mettre à jour le test dispatcher**

Dans `test_dispatcher.py`, `test_default_dispatcher_handles_video_and_audio` : remplacer `assert not dispatcher.has_ingestor(SourceKind.DOCUMENT)` par `assert dispatcher.has_ingestor(SourceKind.DOCUMENT)`. Adapter `test_unsupported_kind_raises` pour utiliser `SourceKind.YOUTUBE` (encore non géré) au lieu de `DOCUMENT`.

- [ ] **Step 2: Lancer (échec attendu)** — DOCUMENT pas encore enregistré.

- [ ] **Step 3: Enregistrer le `DocumentIngestor`**

Dans `dispatcher.py`, `build_default_ingestion_dispatcher` :
```python
from fahmi2.infra.ingestion.document_ingestor import DocumentIngestor
from fahmi2.infra.ingestion.text_extractor import DefaultTextExtractor

def build_default_ingestion_dispatcher() -> IngestionDispatcher:
    """Construit le dispatcher par défaut (vidéo + audio + documents)."""
    media = MediaIngestor()
    document = DocumentIngestor(DefaultTextExtractor())
    return IngestionDispatcher(
        {
            SourceKind.VIDEO: media,
            SourceKind.AUDIO: media,
            SourceKind.DOCUMENT: document,
        }
    )
```
Mettre à jour la docstring (« vidéo + audio + documents »).

- [ ] **Step 4: Lancer (succès)** — `pytest tests/unit/infra/ingestion -v` → PASS
- [ ] **Step 5: Commit** — `git commit -m "feat(ingestion): branche DocumentIngestor dans le dispatcher"`

---

## Tâche 6 : Drapeau `reformulate_documents` (domain + persistance + fixtures + UI)

**Files:** Modify `src/fahmi2/domain/generation.py`, `src/fahmi2/infra/storage/sqlite_state.py`, `tests/conftest.py`, `src/fahmi2/ui/dialogs/generation_settings_view.py` ; Test `tests/unit/domain/test_generation.py`

- [ ] **Step 1: Ajouter le champ au domaine**

Dans `GenerationSettings` (`generation.py`), ajouter après `export_formats` :
```python
    reformulate_documents: bool = True
```
Documenter dans la docstring `Attributes` : « ``reformulate_documents``: si ``True`` (défaut), les documents texte passent par la reformulation (phase 3) comme une transcription ; sinon ils sont insérés tels quels (pass-through). »

- [ ] **Step 2: Sérialisation SQLite**

Dans `sqlite_state.py`, `_serialize_generation_settings` : ajouter `"reformulate_documents": gen.reformulate_documents,`. Dans `_deserialize_generation_settings`, ajouter au constructeur `reformulate_documents=bool(payload.get("reformulate_documents", True)),` (défaut `True` pour les blobs antérieurs — migration *lenient*).

- [ ] **Step 3: Fixture de test**

Dans `tests/conftest.py`, `make_generation_settings` : ajouter `"reformulate_documents": True,` au dict `base`.

- [ ] **Step 4: Test domaine (round-trip défaut)**

```python
# tests/unit/domain/test_generation.py — ajouter
def test_reformulate_documents_defaults_true(make_generation_settings) -> None:
    assert make_generation_settings().reformulate_documents is True
    assert make_generation_settings(reformulate_documents=False).reformulate_documents is False
```

- [ ] **Step 5: Case UI**

Dans `generation_settings_view.py` :
- `_build_fields` : `self._reformulate_documents_checkbox = QCheckBox(_REFORMULATE_DOCS_LABEL, self)` puis `self._reformulate_documents_checkbox.setChecked(True)` ; ajouter les constantes `_REFORMULATE_DOCS_LABEL = "Reformuler les documents texte"` et un `_REFORMULATE_DOCS_TOOLTIP`.
- `_build_input_page` (ou la page « Style ») : `form.addRow(self._reformulate_documents_checkbox)`.
- `_populate` : `self._reformulate_documents_checkbox.setChecked(generation.reformulate_documents)`.
- `_on_accept` : passer `reformulate_documents=self._reformulate_documents_checkbox.isChecked()` au constructeur `GenerationSettings`.

- [ ] **Step 6: Lancer**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/domain/test_generation.py tests/unit/infra/storage tests/unit/ui/test_generation_settings_view.py -q`
Expected: PASS

- [ ] **Step 7: Commit** — `git commit -m "feat(generation): drapeau reformulate_documents (defaut active) + UI + persistance"`

---

## Tâche 7 : Pass-through phase 3 pour documents non reformulés

**Files:** Modify `src/fahmi2/pipeline/handlers/phase_3_reformulation.py` ; Test `tests/unit/pipeline/handlers/test_phase_3_reformulation.py`

- [ ] **Step 1: Écrire le test (document + drapeau off → pass-through)**

```python
# test_phase_3_reformulation.py — ajouter
def test_document_passthrough_when_reformulation_disabled(
    tmp_path, make_generation_settings
) -> None:
    source = SourceExecution(
        source_id=SourceId.new(),
        source=InputSource(kind=SourceKind.DOCUMENT, location=str(tmp_path / "c.pdf")),
    )
    ctx, _ = build_phase_context(
        tmp_path, make_generation_settings, sources=(source,),
        settings_overrides={"reformulate_documents": False},
    )
    write_transcription_fixture(
        ctx.workspace, source.source_id.value, text="Texte de cours déjà rédigé."
    )
    handler = Phase3ReformulationHandler()
    result = handler.execute(ctx, source=source)
    assert result.status is PhaseStatus.SUCCEEDED
    assert result.cost_usd == 0.0
    out = ctx.workspace / "reformulated" / f"{source.source_id.value}.md"
    assert out.read_text(encoding="utf-8") == "Texte de cours déjà rédigé."
```
(Imports nécessaires : `SourceExecution`, `InputSource`, `SourceId`, `SourceKind`, `PhaseStatus`.)

- [ ] **Step 2: Lancer (échec)** — pass-through pas implémenté (le handler appelle le LLM).

- [ ] **Step 3: Implémenter le pass-through**

Dans `phase_3_reformulation.py`, importer `SourceKind`. Au début de `execute` (après le garde `source is None` et `started_at`) :
```python
        if (
            source.source.kind is SourceKind.DOCUMENT
            and not ctx.settings.reformulate_documents
        ):
            text = _load_transcription_text(ctx.workspace, source.source_id.value)
            out_path = (
                ctx.workspace / _REFORMULATED_SUBDIR / f"{source.source_id.value}.md"
            )
            ctx.artifacts.write_text_atomic(out_path, text)
            return build_succeeded_phase(
                phase_id=self.phase_id,
                artifact_path=out_path,
                started_at=started_at,
                cost_usd=0.0,
            )
```

- [ ] **Step 4: Lancer (succès)** — `pytest tests/unit/pipeline/handlers/test_phase_3_reformulation.py -v` → PASS (le segment unique garantit la fidélité du pass-through).
- [ ] **Step 5: Commit** — `git commit -m "feat(pipeline): phase 3 pass-through pour documents non reformules"`

---

## Tâche 8 : Coût `SourceWeight` (CostEstimator + appelant + tests)

**Files:** Modify `src/fahmi2/app/cost_estimator.py`, `src/fahmi2/app/_cost_common.py`, `src/fahmi2/ui/generation_controller.py` ; Modify `tests/unit/app/test_cost_estimator.py`

- [ ] **Step 1: Constante**

Dans `_cost_common.py`, ajouter `TEXT_CHARS_PER_TOKEN = 4.0` (≈ 1 token ≈ 4 caractères ; constante centralisée).

- [ ] **Step 2: `SourceWeight` + nouvelle signature**

Dans `cost_estimator.py`, ajouter :
```python
@dataclass(frozen=True)
class SourceWeight:
    """Charge estimée d'une source pour le calcul de coût.

    Attributes:
        audio_seconds: Durée audio (vidéo/audio ; 0 pour un document).
        text_tokens: Tokens texte estimés (document ; 0 sinon).
        reformulated: ``False`` si la source saute la reformulation (document
            en pass-through).
    """
    audio_seconds: float
    text_tokens: float
    reformulated: bool = True
```
`estimate` prend désormais `source_weights: list[SourceWeight]` (au lieu de `videos_durations_seconds`). Calculs :
- `total_audio_seconds = sum(w.audio_seconds for w in source_weights)` (→ STT, inchangé).
- `n_sources = len(source_weights)`.
- `total_base_tokens = sum(w.audio_seconds/60*WPM*TPW + w.text_tokens for w in source_weights)`.
- `reformulated_base_tokens = sum(... for w in source_weights if w.reformulated)`.
- `_llm_cost_per_phase` reçoit `total_base_tokens`, `reformulated_base_tokens`, `n_sources`. Remplacer `base_tokens_per_video * n_videos` par `total_base_tokens` (égalité algébrique : la moyenne × n = total). La phase `REFORMULATION` utilise `reformulated_base_tokens` à la place de `total_base_tokens`. Les sous-loops/batch (facteurs × total) utilisent `total_base_tokens`.
- `CostEstimation.total_audio_seconds` conservé.

> **DRY/KISS** : la logique par phase est inchangée ; seul le « volume de base »
> est généralisé (durée audio **+** tokens texte) et la reformulation isolée.

- [ ] **Step 3: Adapter l'appelant (`generation_controller`, estimation pré-run)**

Construire les `SourceWeight` depuis les sources scannées :
```python
# constante module : _TEXT_BYTES_PER_TOKEN heuristique d'estimation pré-run
weights = []
for s in sources:
    if s.source.kind is SourceKind.DOCUMENT:
        size = s.source.as_path.stat().st_size
        weights.append(SourceWeight(
            audio_seconds=0.0,
            text_tokens=size / _TEXT_BYTES_PER_TOKEN,
            reformulated=settings.reformulate_documents,
        ))
    else:
        weights.append(SourceWeight(
            audio_seconds=ffmpeg.probe_duration_seconds(s.source.as_path),
            text_tokens=0.0,
        ))
estimation = CostEstimator().estimate(source_weights=weights, ...)
```
(Constante `_TEXT_BYTES_PER_TOKEN` dans `generation_controller`, ex. `4.0` ; heuristique pré-run grossière assumée, le coût réel dépend du texte extrait.) Importer `SourceWeight`, `SourceKind`.

- [ ] **Step 4: Adapter `test_cost_estimator.py`**

Remplacer chaque `videos_durations_seconds=[a, b]` par `source_weights=[SourceWeight(audio_seconds=a, text_tokens=0.0), ...]`. Ajouter 2 tests : un document (`SourceWeight(audio_seconds=0, text_tokens=5000)`) → `stt_usd == 0` et `llm_usd > 0` ; un document `reformulated=False` → coût phase REFORMULATION nul (comparer à `reformulated=True`).

- [ ] **Step 5: Lancer**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/app/test_cost_estimator.py tests/unit/ui -q`
Expected: PASS

- [ ] **Step 6: Commit** — `git commit -m "feat(cost): SourceWeight (audio + texte) pour l'estimation documents"`

---

## Tâche 9 : Repasse qualité finale & doc

- [ ] **Step 1: Suite + lint + types**

Run:
```
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m mypy src tests
```
Expected: tout vert.

- [ ] **Step 2: Documentation**

- `CLAUDE.md` : compléter la couche `infra/ingestion` (DocumentIngestor + TextExtractor) ; mention du drapeau `reformulate_documents` et du pass-through dans la section « Mécanismes transverses » ; intro (documents désormais supportés).
- `packaging/README.md` : noter le bundling `pypdf` (pur) + `python-docx` (`--collect-data docx`).

- [ ] **Step 3: Commit doc** — `git commit -m "docs: entrants documents (Lot 2)"`

---

## Self-review (rédacteur)
- **Spec §4.4** : `DocumentIngestor` segment unique (T4) ✓. **§4.5** : `TextExtractor` (T3) ✓.
- **Spec §6** : pass-through phase 3 fidèle grâce au segment unique (T7) ✓.
- **Spec §8** : `SourceWeight` (T8) ✓. **§10** : drapeau + UI (T6) ✓.
- **Erreurs** : `TEXT_EXTRACTION_FAILED` (T3), `EMPTY_DOCUMENT` (T4) ✓.
- **Type consistency** : `DocumentIngestor.ingest(source, source_id, deps, *, language_hint, delete_audio_after)` conforme au port `SourceIngestor` (T4 vs Lot 1B) ✓.
- **Constantes** : extensions (classify), `TEXT_CHARS_PER_TOKEN`/`_TEXT_BYTES_PER_TOKEN`, séparateurs d'extraction — centralisées ✓.

## Dépendances vers les lots suivants
- **Lot 3 (YouTube)** : `YtDlpDownloader` + `YoutubeIngestor` (réutilise `MediaIngestor`), `youtube_urls`, durée via métadonnée → `SourceWeight(audio_seconds=…)`.
- **Lot 4 (Ordonnancement)** : `source_order`/`excluded_sources` + double liste UI.
