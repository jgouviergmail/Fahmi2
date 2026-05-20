# SP3 · Plan 01 — Export Anki (`.apkg`, genanki)

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (inline, sans subagents).
> **Design** : [`../specs/2026-05-20-sp2-sp3-supports-revision-design.md`](../specs/2026-05-20-sp2-sp3-supports-revision-design.md) (§9).
> **Avancement** : [`./2026-05-20-sp2-sp3-00-avancement.md`](./2026-05-20-sp2-sp3-00-avancement.md).
> Steps use checkbox (`- [ ]`) syntax.

**Goal:** Exporter les supports générés (sur disque sous `pedagogy/`) vers un fichier
**Anki `.apkg`** via `genanki` : flashcards (glossaire + concepts) → note **Basic**,
cloze → note **Cloze**, QCM → note **custom** ; **GUID stables** (ré-import sans
doublon), **sous-decks par support**, **tags** (support, langue, difficulté, chapitre).
Bouton **Exporter** dans l'onglet pédagogique.

**Architecture:** Adapter `infra/anki/genanki_exporter.py` (ports/adapters, dépendance
`genanki`) consommant des artefacts **désérialisés** (`pedagogy/artifact_reader.py`,
inverse de `artifact_writer.serialize_artifact`). Un service applicatif
`app/pedagogy_export.py` scanne `pedagogy/`, lit les artefacts exportables et délègue
à l'adapter. UI : bouton **Exporter** ajouté (optionnel) à `ProjectHeaderBar` (réutilisé)
+ action dans `PedagogyController`. Les types de supports non mappés en cartes Anki
(vrai/faux, questions ouvertes, fiche, points clés, examen blanc) sont **ignorés** par
l'export Anki (ils relèveront du Markdown/PDF, SP3/02).

**Tech Stack:** `genanki` 0.13, `pytest`, `ruff`, `mypy --strict`.

**Rappels directives :** pas de magic value (IDs de modèles/decks, marqueurs, suffixes
en constantes), docstrings Google + module, réutiliser les patterns (adapters infra en
classe, `FsArtifactStore`, entités `domain/supports`, `artifact_writer` paths), DRY/YAGNI/
KISS/SRP/SoC, composition. **Tout en français** (accents).

**Décisions verrouillées :**
- **Désérialisation limitée aux types exportables Anki** (Flashcard, ClozeItem, QcmItem)
  — YAGNI ; SP3/02 étendra `artifact_reader` aux autres entités pour le Markdown/PDF.
- **Sous-decks par support** (`<DeckRoot>::<libellé support>`), DeckRoot = nom du projet ;
  le **chapitre** est porté par un **tag** (`chapitre:<source_ref>`), car les items ne
  portent que l'ancre (`source_ref`), pas le titre du chapitre. Tags sans espace
  (valeurs d'enum), compatibles Anki.
- **GUID stable** = `genanki.guid_for(deck_root, support_type, language, clé_contenu)`
  (clé = recto / texte / question selon le type) → ré-import sans doublon.
- **IDs de modèles** : 3 constantes entières fixes (Basic / Cloze / QCM). **IDs de decks**
  dérivés (sha256 du nom → entier borné, stable).
- **Cloze** : conversion `___` → `{{cN::réponse}}` (n-ième trou ↔ n-ième réponse).

---

## File structure (vue d'ensemble)

**Créés :**

- `src/fahmi2/pedagogy/artifact_reader.py` — `ParsedArtifact` + `read_artifact` (désérialise
  Flashcard/ClozeItem/QcmItem ; `None` pour les types non exportables).
- `src/fahmi2/infra/anki/__init__.py`
- `src/fahmi2/infra/anki/genanki_exporter.py` — modèles (Basic/Cloze/QCM), `GenankiExporter`,
  `AnkiExportResult`.
- `src/fahmi2/app/pedagogy_export.py` — `export_pedagogy_to_apkg(project, *, output_path)`.
- Tests : `tests/unit/pedagogy/test_artifact_reader.py`,
  `tests/unit/infra/anki/test_genanki_exporter.py`,
  `tests/unit/app/test_pedagogy_export.py`,
  `tests/unit/ui/test_pedagogy_controller.py` (action export — ajout).

**Modifiés :**

- `pyproject.toml` — dépendance `genanki` + override mypy `genanki.*`.
- `src/fahmi2/ui/widgets/project_header_bar.py` — bouton export optionnel + `export_requested`.
- `src/fahmi2/ui/features/pedagogy_tab.py` — active le bouton export.
- `src/fahmi2/ui/pedagogy_controller.py` — action `export_apkg`.
- Docs : `docs/01-presentation-fonctionnelle.md`, `docs/02-presentation-technique.md`,
  `docs/04-parametrage.md`, `CHANGELOG.md`, avancement.
- `packaging/fahmi2.spec` (gitignored) — bundler `genanki` (note seulement, non versionné).

---

## Task 1 : Dépendance `genanki`

**Files:** Modify `pyproject.toml`

- [ ] **Step 1** : Ajouter à `dependencies` : `"genanki>=0.13,<1",`.
- [ ] **Step 2** : Ajouter `genanki.*` (+ ses deps non typées) à l'override mypy
  `ignore_missing_imports` :

```toml
[[tool.mypy.overrides]]
module = [
  "pywin32.*",
  "win32crypt.*",
  "ffmpeg.*",
  "faster_whisper.*",
  "sklearn.*",
  "torch.*",
  "ctranslate2.*",
  "genanki.*",
]
ignore_missing_imports = true
```

- [ ] **Step 3** : Vérifier l'installation (déjà installée dans le venv) :

Run: `.venv\Scripts\python.exe -c "import genanki; print(genanki.version)"`

> **Packaging** : `packaging/fahmi2.spec` (gitignored) devra inclure `genanki` et ses
> deps (`chevron`, `frozendict`, `cached-property`) dans les `hiddenimports`/`datas`.
> Documenter (non versionné).

---

## Task 2 : Désérialisation des artefacts (`pedagogy/artifact_reader.py`)

> Inverse de `artifact_writer.serialize_artifact`, limité aux types exportables Anki.

**Files:** Create `src/fahmi2/pedagogy/artifact_reader.py` ;
Test `tests/unit/pedagogy/test_artifact_reader.py`

- [ ] **Step 1 : Test (échoue)** — round-trip serialize → write → read :

```python
"""Tests de la désérialisation des artefacts de supports."""

from __future__ import annotations

from pathlib import Path

from fahmi2.domain.enums import Language, SupportType
from fahmi2.domain.supports import ClozeItem, Flashcard, QcmItem, SupportArtifact
from fahmi2.infra.storage.fs_artifacts import FsArtifactStore
from fahmi2.pedagogy.artifact_reader import read_artifact
from fahmi2.pedagogy.artifact_writer import artifact_json_path, serialize_artifact


def _write(tmp_path: Path, artifact: SupportArtifact) -> Path:
    path = artifact_json_path(tmp_path, artifact.support_type, artifact.language)
    FsArtifactStore().write_json_atomic(path, serialize_artifact(artifact))
    return path


def test_read_flashcards(tmp_path: Path) -> None:
    artifact = SupportArtifact(
        support_type=SupportType.FLASHCARDS_GLOSSARY,
        language=Language.FR,
        items=(Flashcard(front="PIB", back="def", source_ref="PIB", tags=("t",)),),
        rendered_markdown="x",
    )
    parsed = read_artifact(_write(tmp_path, artifact))
    assert parsed is not None
    assert parsed.support_type is SupportType.FLASHCARDS_GLOSSARY
    assert parsed.language is Language.FR
    card = parsed.items[0]
    assert isinstance(card, Flashcard)
    assert card.front == "PIB"
    assert card.tags == ("t",)


def test_read_qcm(tmp_path: Path) -> None:
    artifact = SupportArtifact(
        support_type=SupportType.QCM,
        language=Language.FR,
        items=(
            QcmItem(
                question="Q", choices=("a", "b"), correct_index=1,
                justification="j", source_ref="1-c",
            ),
        ),
        rendered_markdown="x",
    )
    parsed = read_artifact(_write(tmp_path, artifact))
    assert parsed is not None
    item = parsed.items[0]
    assert isinstance(item, QcmItem)
    assert item.correct_index == 1
    assert item.choices == ("a", "b")


def test_read_cloze(tmp_path: Path) -> None:
    artifact = SupportArtifact(
        support_type=SupportType.CLOZE,
        language=Language.FR,
        items=(ClozeItem(text="a ___", answers=("x",), source_ref="1-c"),),
        rendered_markdown="x",
    )
    parsed = read_artifact(_write(tmp_path, artifact))
    assert parsed is not None
    assert isinstance(parsed.items[0], ClozeItem)


def test_read_unexportable_returns_none(tmp_path: Path) -> None:
    artifact = SupportArtifact(
        support_type=SupportType.KEY_POINTS,
        language=Language.FR,
        items=(),
        rendered_markdown="x",
    )
    assert read_artifact(_write(tmp_path, artifact)) is None


def test_read_missing_file_returns_none(tmp_path: Path) -> None:
    assert read_artifact(tmp_path / "absent.json") is None
```

- [ ] **Step 2 : Lancer** → FAIL.

- [ ] **Step 3 : Créer `pedagogy/artifact_reader.py`** :

```python
"""Lecture/désérialisation des artefacts de supports (inverse du writer).

Reconstruit les entités de support depuis le JSON persisté. Limité aux types
**exportables vers Anki** (Flashcard, ClozeItem, QcmItem) ; les autres types
renvoient ``None`` (ils relèvent de l'export Markdown/PDF, SP3/02).
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fahmi2.domain.enums import Language, SupportType
from fahmi2.domain.supports import ClozeItem, Flashcard, QcmItem, SupportItem

_ENCODING_UTF8 = "utf-8"


@dataclass(frozen=True)
class ParsedArtifact:
    """Artefact désérialisé (sous-ensemble exportable Anki).

    Attributes:
        support_type: Type de support.
        language: Langue.
        items: Entités reconstruites.
    """

    support_type: SupportType
    language: Language
    items: tuple[SupportItem, ...]


def _flashcard(raw: dict[str, Any]) -> Flashcard:
    return Flashcard(
        front=str(raw["front"]),
        back=str(raw["back"]),
        source_ref=str(raw["source_ref"]),
        tags=tuple(str(t) for t in raw.get("tags", [])),
    )


def _qcm(raw: dict[str, Any]) -> QcmItem:
    return QcmItem(
        question=str(raw["question"]),
        choices=tuple(str(c) for c in raw["choices"]),
        correct_index=int(raw["correct_index"]),
        justification=str(raw["justification"]),
        source_ref=str(raw["source_ref"]),
    )


def _cloze(raw: dict[str, Any]) -> ClozeItem:
    return ClozeItem(
        text=str(raw["text"]),
        answers=tuple(str(a) for a in raw["answers"]),
        source_ref=str(raw["source_ref"]),
    )


#: Désérialiseurs d'items par type de support exportable Anki.
_ITEM_DESERIALIZERS: dict[SupportType, Callable[[dict[str, Any]], SupportItem]] = {
    SupportType.FLASHCARDS_GLOSSARY: _flashcard,
    SupportType.FLASHCARDS_CONCEPTS: _flashcard,
    SupportType.QCM: _qcm,
    SupportType.CLOZE: _cloze,
}


def read_artifact(json_path: Path) -> ParsedArtifact | None:
    """Lit un artefact JSON et reconstruit ses items (si exportable Anki).

    Args:
        json_path: Chemin du fichier ``<support>.json``.

    Returns:
        Le ``ParsedArtifact``, ou ``None`` si le fichier est absent/illisible
        ou si le type de support n'est pas exportable vers Anki.
    """
    if not json_path.exists():
        return None
    try:
        payload = json.loads(json_path.read_text(encoding=_ENCODING_UTF8))
        support_type = SupportType(payload["support_type"])
        language = Language(payload["language"])
    except (OSError, json.JSONDecodeError, KeyError, ValueError):
        return None
    deserializer = _ITEM_DESERIALIZERS.get(support_type)
    if deserializer is None:
        return None
    items = tuple(deserializer(dict(raw)) for raw in payload.get("items", []))
    return ParsedArtifact(
        support_type=support_type, language=language, items=items
    )
```

- [ ] **Step 4 : Lancer** → PASS.

---

## Task 3 : Adapter `GenankiExporter`

**Files:** Create `src/fahmi2/infra/anki/__init__.py`, `src/fahmi2/infra/anki/genanki_exporter.py` ;
Test `tests/unit/infra/anki/test_genanki_exporter.py`

Détails :
- **Modèles** (IDs fixes) : `_BASIC_MODEL` (champs Recto/Verso), `_CLOZE_MODEL`
  (`model_type=genanki.Model.CLOZE`, champ Texte), `_QCM_MODEL` (champs Question/Choix/
  Réponse/Justification). CSS minimal partagé.
- **GUID** : `genanki.guid_for(deck_root, support_type.value, language.value, key)`.
- **Decks** : `f"{deck_root}::{support_label}"` ; `deck_id = _stable_id(name)`
  (`int(sha256(name)[:8], 16)` borné < 2³¹, > 0).
- **Tags** : `[support_type.value, f"langue:{lang}", f"niveau:{difficulty}", f"chapitre:{source_ref}"]`.
- **Cloze** : `_to_anki_cloze(text, answers)` remplace le i-ᵉ ``___`` par `{{c{i+1}::ans}}`.
- **QCM** : choix rendus `A. … B. …` (lettres `_CHOICE_LETTERS`), réponse = lettre + texte.

- [ ] **Step 1 : Test (échoue)** :

```python
"""Tests de l'exportateur Anki (genanki)."""

from __future__ import annotations

from pathlib import Path

from fahmi2.domain.enums import Language, SupportType
from fahmi2.domain.supports import ClozeItem, Flashcard, QcmItem
from fahmi2.infra.anki.genanki_exporter import GenankiExporter, _to_anki_cloze
from fahmi2.pedagogy.artifact_reader import ParsedArtifact


def test_to_anki_cloze() -> None:
    assert _to_anki_cloze("a ___ b ___", ("x", "y")) == "a {{c1::x}} b {{c2::y}}"


def test_export_writes_apkg(tmp_path: Path) -> None:
    artifacts = [
        ParsedArtifact(
            support_type=SupportType.FLASHCARDS_GLOSSARY,
            language=Language.FR,
            items=(Flashcard(front="PIB", back="def", source_ref="PIB"),),
        ),
        ParsedArtifact(
            support_type=SupportType.QCM,
            language=Language.FR,
            items=(
                QcmItem(
                    question="Q", choices=("a", "b"), correct_index=0,
                    justification="j", source_ref="1-c",
                ),
            ),
        ),
        ParsedArtifact(
            support_type=SupportType.CLOZE,
            language=Language.FR,
            items=(ClozeItem(text="a ___", answers=("x",), source_ref="1-c"),),
        ),
    ]
    out = tmp_path / "deck.apkg"
    result = GenankiExporter().export_to_file(
        artifacts, deck_root="Projet", difficulty="licence", output_path=out
    )
    assert out.exists()
    assert out.stat().st_size > 0
    assert result.note_count == 3


def test_guid_is_stable(tmp_path: Path) -> None:
    artifact = ParsedArtifact(
        support_type=SupportType.FLASHCARDS_GLOSSARY,
        language=Language.FR,
        items=(Flashcard(front="PIB", back="def", source_ref="PIB"),),
    )
    exporter = GenankiExporter()
    g1 = exporter._note_guid(artifact, "PIB")  # noqa: SLF001
    g2 = exporter._note_guid(artifact, "PIB")  # noqa: SLF001
    assert g1 == g2
```

- [ ] **Step 2 : Lancer** → FAIL.

- [ ] **Step 3 : Créer `infra/anki/genanki_exporter.py`** (modèles + classe). Squelette :

```python
"""Adapter d'export Anki (.apkg) via ``genanki``.

Convertit les artefacts de supports en cartes Anki : flashcards → note Basic,
cloze → note Cloze, QCM → note custom. GUID stables (ré-import sans doublon),
sous-decks par support, tags (support/langue/difficulté/chapitre).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import genanki

from fahmi2.domain.enums import Language, SupportType
from fahmi2.domain.supports import ClozeItem, Flashcard, QcmItem
from fahmi2.pedagogy.artifact_reader import ParsedArtifact

# IDs de modèles Anki (fixes, choisis aléatoirement une fois pour toutes).
_BASIC_MODEL_ID = 1_607_392_319
_CLOZE_MODEL_ID = 1_607_392_320
_QCM_MODEL_ID = 1_607_392_321

_DECK_ID_MODULO = 1 << 31
_DECK_SEPARATOR = "::"
_CLOZE_MARKER = "___"
_CHOICE_LETTERS = "ABCDEFGHIJ"

_SUPPORT_LABELS: dict[SupportType, str] = {
    SupportType.FLASHCARDS_GLOSSARY: "Flashcards Glossaire",
    SupportType.FLASHCARDS_CONCEPTS: "Flashcards Concepts",
    SupportType.QCM: "QCM",
    SupportType.CLOZE: "Textes à trous",
}

_BASIC_MODEL = genanki.Model(
    _BASIC_MODEL_ID,
    "Fahmi2 Basic",
    fields=[{"name": "Recto"}, {"name": "Verso"}],
    templates=[
        {
            "name": "Carte",
            "qfmt": "{{Recto}}",
            "afmt": '{{FrontSide}}<hr id="answer">{{Verso}}',
        }
    ],
)
_CLOZE_MODEL = genanki.Model(
    _CLOZE_MODEL_ID,
    "Fahmi2 Cloze",
    fields=[{"name": "Texte"}],
    templates=[{"name": "Cloze", "qfmt": "{{cloze:Texte}}", "afmt": "{{cloze:Texte}}"}],
    model_type=genanki.Model.CLOZE,
)
_QCM_MODEL = genanki.Model(
    _QCM_MODEL_ID,
    "Fahmi2 QCM",
    fields=[
        {"name": "Question"},
        {"name": "Choix"},
        {"name": "Reponse"},
        {"name": "Justification"},
    ],
    templates=[
        {
            "name": "QCM",
            "qfmt": "{{Question}}<br><br>{{Choix}}",
            "afmt": (
                '{{FrontSide}}<hr id="answer"><b>Réponse :</b> {{Reponse}}'
                "<br>{{Justification}}"
            ),
        }
    ],
)


@dataclass(frozen=True)
class AnkiExportResult:
    """Résultat d'un export Anki.

    Attributes:
        output_path: Chemin du fichier ``.apkg`` écrit.
        note_count: Nombre de notes exportées.
        deck_count: Nombre de sous-decks créés.
    """

    output_path: Path
    note_count: int
    deck_count: int


def _to_anki_cloze(text: str, answers: tuple[str, ...]) -> str:
    """Convertit un texte à trous ``___`` en syntaxe cloze Anki ``{{cN::…}}``."""
    result = text
    for index, answer in enumerate(answers, start=1):
        if _CLOZE_MARKER not in result:
            break
        result = result.replace(_CLOZE_MARKER, f"{{{{c{index}::{answer}}}}}", 1)
    return result


def _stable_deck_id(name: str) -> int:
    """ID de deck stable dérivé du nom (sha256 borné)."""
    digest = hashlib.sha256(name.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % _DECK_ID_MODULO + 1


class GenankiExporter:
    """Exporte des ``ParsedArtifact`` vers un fichier ``.apkg``."""

    def export_to_file(
        self,
        artifacts: list[ParsedArtifact],
        *,
        deck_root: str,
        difficulty: str,
        output_path: Path,
    ) -> AnkiExportResult:
        """Construit les decks/notes et écrit le paquet Anki.

        Args:
            artifacts: Artefacts désérialisés (exportables).
            deck_root: Racine du nom de deck (nom du projet).
            difficulty: Libellé de difficulté (tag), ex. ``"licence"``.
            output_path: Chemin du ``.apkg`` à écrire.

        Returns:
            ``AnkiExportResult``.
        """
        decks: dict[str, genanki.Deck] = {}
        note_count = 0
        for artifact in artifacts:
            deck = self._deck_for(decks, deck_root, artifact.support_type)
            for item in artifact.items:
                note = self._note_for(artifact, item, difficulty=difficulty)
                if note is not None:
                    deck.add_note(note)
                    note_count += 1
        output_path.parent.mkdir(parents=True, exist_ok=True)
        genanki.Package(list(decks.values())).write_to_file(str(output_path))
        return AnkiExportResult(
            output_path=output_path, note_count=note_count, deck_count=len(decks)
        )
```

  + méthodes privées :
  - `_deck_for(decks, deck_root, support_type)` : nom `f"{deck_root}{_DECK_SEPARATOR}{_SUPPORT_LABELS[support_type]}"`, crée/retourne le `genanki.Deck(_stable_deck_id(name), name)`.
  - `_note_guid(artifact, key)` : `genanki.guid_for(artifact.support_type.value, artifact.language.value, key)`.
  - `_tags(artifact, difficulty, source_ref)` : `[artifact.support_type.value, f"langue:{artifact.language.value}", f"niveau:{difficulty}", f"chapitre:{source_ref}"]`.
  - `_note_for(artifact, item, *, difficulty)` : dispatch sur le type d'item
    (`isinstance` interdit par S101 → dispatch sur `artifact.support_type` + cast, ou
    `match`/`isinstance` est OK ? **S101 vise `assert`, pas `isinstance`** → `isinstance`
    autorisé). Utiliser `isinstance(item, Flashcard|QcmItem|ClozeItem)` :
    - `Flashcard` → `genanki.Note(_BASIC_MODEL, [front, back], guid=_note_guid(artifact, front), tags=...)`.
    - `ClozeItem` → `genanki.Note(_CLOZE_MODEL, [_to_anki_cloze(text, answers)], guid=_note_guid(artifact, text), tags=...)`.
    - `QcmItem` → champs (question, choix HTML via `_render_choices`, réponse lettre+texte, justification), `guid=_note_guid(artifact, question)`.

  > **Note S101** : `isinstance` est autorisé (ruff S101 ne concerne que `assert`). Le
  > dispatch par `isinstance` sur le type d'item est donc propre et type-narrowing pour mypy.

- [ ] **Step 4 : Lancer** → PASS (le `.apkg` est un zip SQLite ; on vérifie l'écriture +
  le compte de notes + la stabilité du GUID).

---

## Task 4 : Service applicatif `app/pedagogy_export.py`

**Files:** Create `src/fahmi2/app/pedagogy_export.py` ;
Test `tests/unit/app/test_pedagogy_export.py`

- [ ] **Step 1 : Test (échoue)** : écrire 2 artefacts (flashcards glossaire + QCM) sous
  `pedagogy/`, appeler `export_pedagogy_to_apkg(project, output_path=…)`, vérifier le
  `.apkg` écrit + `result.note_count == 2`. Un projet sans artefact → `note_count == 0`
  (et pas de crash).

- [ ] **Step 2 : Lancer** → FAIL.

- [ ] **Step 3 : Créer `app/pedagogy_export.py`** :

```python
"""Service d'export des supports pédagogiques vers Anki (.apkg)."""

from __future__ import annotations

from pathlib import Path

from fahmi2.domain.pedagogy import PEDAGOGY_WORKSPACE_SUBDIR
from fahmi2.domain.project import Project
from fahmi2.infra.anki.genanki_exporter import AnkiExportResult, GenankiExporter
from fahmi2.pedagogy.artifact_reader import ParsedArtifact, read_artifact
from fahmi2.pedagogy.labels import audience_label

_JSON_GLOB = "*/*/*.json"


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
        for json_path in sorted(pedagogy_dir.glob(_JSON_GLOB)):
            parsed = read_artifact(json_path)
            if parsed is not None and parsed.items:
                artifacts.append(parsed)
    difficulty = (
        audience_label(project.pedagogy.target_audience)
        if project.pedagogy is not None
        else ""
    )
    return GenankiExporter().export_to_file(
        artifacts,
        deck_root=project.name,
        difficulty=difficulty,
        output_path=output_path,
    )
```

  > Le `manifest.json` est à la racine de `pedagogy/`, pas en `*/*/*.json` → ignoré par
  > le glob (profondeur 3). Le difficulté-tag utilise le **libellé** ? Anki interdit les
  > espaces dans les tags → utiliser `project.pedagogy.target_audience.value` (sans
  > espace) **plutôt** que `audience_label`. **Corriger** : `difficulty =
  > project.pedagogy.target_audience.value if project.pedagogy else ""` (retirer l'import
  > `audience_label`).

- [ ] **Step 4 : Lancer** → PASS.

---

## Task 5 : UI — bouton Exporter + action contrôleur

**Files:** Modify `src/fahmi2/ui/widgets/project_header_bar.py`,
`src/fahmi2/ui/features/pedagogy_tab.py`, `src/fahmi2/ui/pedagogy_controller.py` ;
Test `tests/unit/ui/test_pedagogy_controller.py`

- [ ] **Step 1 : `ProjectHeaderBar`** — bouton export optionnel :
  - signal `export_requested = Signal()`.
  - param constructeur `show_export: bool = False` + `export_tooltip: str = ""`.
  - créer `self._export_button = self._make_button("📦  Exporter", role="default")`,
    `setToolTip(export_tooltip)`, `clicked.connect(self.export_requested)`, ajouté au
    layout, `setVisible(show_export)`. (Génération : non affiché → comportement inchangé.)

- [ ] **Step 2 : `PedagogyTab`** — passer `show_export=True` + `export_tooltip` (constante)
  au `ProjectHeaderBar`.

- [ ] **Step 3 : `PedagogyController`** — brancher `export_requested` →
  `self.export_apkg` :
  - si pas de projet → warning.
  - chemin de sortie via `QFileDialog.getSaveFileName(window, "Exporter vers Anki",
    f"{project.name}.apkg", "Paquets Anki (*.apkg)")` ; si vide → return.
  - `result = export_pedagogy_to_apkg(project, output_path=Path(path))`.
  - si `result.note_count == 0` → information « aucun support exportable » ; sinon
    information « N cartes exportées vers <chemin> » + log INFO `PEDAGOGY_EXPORTED`.
  - isoler les `Fahmi2Error`/`Exception` en `QMessageBox.critical`.

- [ ] **Step 4 : Test** (`tests/unit/ui/test_pedagogy_controller.py`) : monkeypatch
  `QFileDialog.getSaveFileName` (retourne `(str(tmp_path/"d.apkg"), "filtre")`) +
  artefacts amorcés sous `pedagogy/` ; appeler `controller.export_apkg()` ; vérifier que
  le `.apkg` existe. Cas « aucun projet » → pas de crash.

- [ ] **Step 5 : Lancer** → PASS + non-régression UI.

---

## Task 6 : Vérifications systématiques + docs + commit

- [ ] **Step 1** : `.venv\Scripts\python.exe -m pytest -q` → tout vert.
- [ ] **Step 2** : `.venv\Scripts\python.exe -m ruff check .` → clean.
- [ ] **Step 3** : `.venv\Scripts\python.exe -m mypy src tests` → Success.
- [ ] **Step 4 : Docs** : `docs/01` (export Anki depuis l'onglet), `docs/02` (adapter
  `infra/anki`, mapping note types, GUID/decks/tags), `docs/04` (bouton Exporter),
  `CHANGELOG.md`, avancement (SP3/01 → Fait). Note packaging `.spec`.
- [ ] **Step 5 : Commit** :

```bash
git add -A
git commit -m "feat(pedagogy): export Anki .apkg via genanki (SP3/01)"
```

---

## Self-review

**Couverture du design §9 :** Flashcard→Basic / Cloze→Cloze / QCM→custom (Task 3) ;
GUID stables (Task 3, `guid_for`) ; sous-decks (par support — déviation documentée vs
« par chapitre » faute de titre dans l'item ; chapitre en tag) ; tags support/langue/
difficulté/chapitre (Task 3) ; dépendance genanki + bundle .spec (Task 1) ; bouton export
(Task 5).

**Hors périmètre (tracé) :** export Markdown/PDF (SP3/02, qui étendra `artifact_reader`
aux autres entités) ; supports non-cartes (vrai/faux, questions ouvertes, fiche, points
clés, examen blanc) non exportés en Anki.

**Cohérence types/signatures :** `read_artifact(Path) -> ParsedArtifact | None` (Tasks 2/3/4) ;
`GenankiExporter.export_to_file(artifacts, *, deck_root, difficulty, output_path) ->
AnkiExportResult` (Tasks 3/4) ; `export_pedagogy_to_apkg(project, *, output_path) ->
AnkiExportResult` (Tasks 4/5) ; `ProjectHeaderBar(..., show_export, export_tooltip)` +
`export_requested` (Tasks 5).
