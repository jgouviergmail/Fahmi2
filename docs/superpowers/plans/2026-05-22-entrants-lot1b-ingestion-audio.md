# Lot 1B — Couche d'ingestion (dispatcher) + fichiers audio (plan d'implémentation)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduire la couche `infra/ingestion/` (port `SourceIngestor` + `MediaIngestor` + `IngestionDispatcher`), faire **déléguer la phase 0** au dispatcher, et **élargir le scan aux fichiers audio** — sans toucher aux phases 1-7.

**Architecture:** Ports/adapters identiques à `STTProvider`. La phase 0 ne fait plus ffmpeg+STT en dur : elle appelle `ctx.ingestion.ingest(source, …)` qui renvoie une `Transcription` (artefact JSON inchangé). Au Lot 1B, le dispatcher ne route que `VIDEO`/`AUDIO` vers `MediaIngestor` (`ffmpeg.extract` → `stt.transcribe`, identiques entre vidéo et audio). `classify.py` centralise les extensions ; `scan_input_folder` devient `build_input_sources` et accepte vidéo + audio. DOCUMENT/YOUTUBE arrivent aux Lots 2/3.

**Tech Stack:** Python 3.12, Protocol, dataclasses frozen, pytest (ffmpeg réel pour `MediaIngestor`, `FakeSTTProvider` pour le STT), ruff, mypy --strict. Interpréteur : `.venv\Scripts\python.exe`.

**Prérequis:** Lot 1A appliqué (`SourceExecution`, `SourceId`, `InputSource`, `Run.sources`, migration SQLite).

**Spec de référence:** `docs/superpowers/specs/2026-05-22-entrants-generation-elargis-design.md` (§4, §4.7, §5, §9.2).

---

## Tâche 1 : Erreur `IngestionError` + code `UNSUPPORTED_SOURCE`

**Files:**
- Modify: `src/fahmi2/core/errors/exceptions.py`
- Modify: `src/fahmi2/core/errors/messages.py` (registre FR des messages)
- Test: `tests/unit/core/errors/test_exceptions.py` (ajout)

- [ ] **Step 1: Écrire le test**

```python
# tests/unit/core/errors/test_exceptions.py — ajouter
from fahmi2.core.errors.exceptions import Fahmi2Error, IngestionError
from fahmi2.core.errors.severity import Severity


def test_ingestion_error_is_fahmi2_error():
    err = IngestionError(
        code="INGESTION.UNSUPPORTED_SOURCE",
        user_message="x",
        severity=Severity.ERROR,
    )
    assert isinstance(err, Fahmi2Error)
    assert err.code == "INGESTION.UNSUPPORTED_SOURCE"
```

- [ ] **Step 2: Lancer (échec attendu)**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/core/errors/test_exceptions.py -v`
Expected: FAIL — `cannot import name 'IngestionError'`

- [ ] **Step 3: Ajouter la classe** (calquée sur les sous-classes existantes comme `FFmpegError`)

```python
# core/errors/exceptions.py
class IngestionError(Fahmi2Error):
    """Erreur survenue pendant l'ingestion d'une source (phase 0)."""
```

- [ ] **Step 4: Lancer (succès)**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/core/errors/test_exceptions.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/fahmi2/core/errors/ tests/unit/core/errors/test_exceptions.py
git commit -m "feat(errors): ajoute IngestionError"
```

---

## Tâche 2 : `classify.py` — extensions centralisées + `classify_file`

**Files:**
- Create: `src/fahmi2/infra/ingestion/__init__.py` (vide)
- Create: `src/fahmi2/infra/ingestion/classify.py`
- Test: `tests/unit/infra/ingestion/test_classify.py`

- [ ] **Step 1: Écrire les tests**

```python
# tests/unit/infra/ingestion/test_classify.py
from pathlib import Path

import pytest

from fahmi2.domain.enums import SourceKind
from fahmi2.infra.ingestion.classify import classify_file, supported_file_extensions


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("a.mp4", SourceKind.VIDEO),
        ("a.MKV", SourceKind.VIDEO),
        ("a.wav", SourceKind.AUDIO),
        ("a.mp3", SourceKind.AUDIO),
        ("a.m4a", SourceKind.AUDIO),
        ("a.txt", None),  # document : pas encore supporté au Lot 1B
        ("a.zip", None),
    ],
)
def test_classify_file(name: str, expected: SourceKind | None) -> None:
    assert classify_file(Path(name)) == expected


def test_supported_extensions_contains_audio_and_video() -> None:
    exts = supported_file_extensions()
    assert ".mp4" in exts and ".mp3" in exts
    assert ".txt" not in exts  # Lot 2
```

- [ ] **Step 2: Lancer (échec)**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/infra/ingestion/test_classify.py -v`
Expected: FAIL — module absent

- [ ] **Step 3: Implémenter `classify.py`**

```python
"""Classification d'une source fichier par extension.

Centralise les ensembles d'extensions reconnues (réexposés par
``supported_file_extensions`` pour le scan). DOCUMENT et YOUTUBE sont ajoutés
aux lots ultérieurs.
"""

from __future__ import annotations

from pathlib import Path

from fahmi2.domain.enums import SourceKind

_VIDEO_EXTENSIONS: frozenset[str] = frozenset(
    {".mp4", ".m4v", ".mkv", ".mov", ".webm"}
)
_AUDIO_EXTENSIONS: frozenset[str] = frozenset(
    {".wav", ".mp3", ".m4a", ".flac", ".ogg", ".opus", ".aac"}
)

_EXTENSION_TO_KIND: dict[str, SourceKind] = {
    **{ext: SourceKind.VIDEO for ext in _VIDEO_EXTENSIONS},
    **{ext: SourceKind.AUDIO for ext in _AUDIO_EXTENSIONS},
}


def classify_file(path: Path) -> SourceKind | None:
    """Type d'une source fichier d'après son extension.

    Args:
        path: Chemin du fichier.

    Returns:
        Le ``SourceKind`` correspondant, ou ``None`` si l'extension n'est pas
        prise en charge.
    """
    return _EXTENSION_TO_KIND.get(path.suffix.lower())


def supported_file_extensions() -> frozenset[str]:
    """Ensemble immuable des extensions fichier reconnues (minuscules, point inclus)."""
    return frozenset(_EXTENSION_TO_KIND)
```

- [ ] **Step 4: Lancer (succès)** — `pytest tests/unit/infra/ingestion/test_classify.py -v` → PASS
- [ ] **Step 5: Commit** — `git commit -m "feat(ingestion): classify_file + extensions audio/vidéo"`

---

## Tâche 3 : Port `SourceIngestor` + `IngestionDeps`

**Files:**
- Create: `src/fahmi2/infra/ingestion/interface.py`

- [ ] **Step 1: Implémenter (pas de test dédié : Protocol pur, couvert par les ingesteurs)**

```python
"""Contrat d'ingestion : ``SourceIngestor`` produit une ``Transcription`` à
partir d'une ``InputSource``, quel que soit son type."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from fahmi2.domain.enums import Language, SourceKind
from fahmi2.domain.source import InputSource
from fahmi2.infra.audio.ffmpeg_extractor import FFmpegExtractor
from fahmi2.infra.storage.fs_artifacts import FsArtifactStore
from fahmi2.infra.stt.interface import STTProvider, Transcription


@dataclass(frozen=True)
class IngestionDeps:
    """Dépendances communes injectées aux ingesteurs (issues du ``PhaseContext``).

    Attributes:
        workspace: Dossier de travail du run.
        artifacts: Helper d'écriture atomique d'artefacts.
        stt_provider: Provider STT (vidéo/audio/YouTube).
        ffmpeg: Extracteur ffmpeg.
    """

    workspace: Path
    artifacts: FsArtifactStore
    stt_provider: STTProvider
    ffmpeg: FFmpegExtractor


class SourceIngestor(Protocol):
    """Produit une ``Transcription`` à partir d'une source d'entrée."""

    @property
    def kind(self) -> SourceKind:
        """Type de source géré par cet ingesteur."""

    def ingest(
        self,
        source: InputSource,
        source_id: str,
        deps: IngestionDeps,
        *,
        language_hint: Language | None,
        delete_audio_after: bool,
    ) -> Transcription:
        """Transcrit/extrait le contenu de ``source`` en une ``Transcription``."""
```

- [ ] **Step 2: Compilation** — `.venv\Scripts\python.exe -m mypy src/fahmi2/infra/ingestion/interface.py` → OK
- [ ] **Step 3: Commit** — `git commit -m "feat(ingestion): port SourceIngestor + IngestionDeps"`

---

## Tâche 4 : `MediaIngestor` (VIDEO + AUDIO)

**Files:**
- Create: `src/fahmi2/infra/ingestion/media_ingestor.py`
- Test: `tests/unit/infra/ingestion/test_media_ingestor.py`

- [ ] **Step 1: Écrire le test (ffmpeg réel + `FakeSTTProvider`)**

```python
# tests/unit/infra/ingestion/test_media_ingestor.py
import subprocess
from pathlib import Path

import pytest

from fahmi2.domain.enums import Language, SourceKind
from fahmi2.domain.source import InputSource
from fahmi2.infra.audio.ffmpeg_extractor import FFmpegExtractor, has_ffmpeg_in_path
from fahmi2.infra.ingestion.interface import IngestionDeps
from fahmi2.infra.ingestion.media_ingestor import MediaIngestor
from fahmi2.infra.stt._fakes import FakeSTTProvider
from fahmi2.infra.storage.fs_artifacts import FsArtifactStore

pytestmark = pytest.mark.skipif(not has_ffmpeg_in_path(), reason="ffmpeg requis")


def _make_wav(path: Path) -> None:
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
         "-ac", "1", "-ar", "16000", str(path)],
        check=True, capture_output=True,
    )


def test_media_ingestor_video_and_audio(tmp_path: Path) -> None:
    src_file = tmp_path / "clip.wav"
    _make_wav(src_file)
    workspace = tmp_path / "ws"
    deps = IngestionDeps(
        workspace=workspace, artifacts=FsArtifactStore(),
        stt_provider=FakeSTTProvider(), ffmpeg=FFmpegExtractor(),
    )
    ingestor = MediaIngestor()
    assert ingestor.kind in {SourceKind.VIDEO, SourceKind.AUDIO}  # cf. note dispatcher
    transcription = ingestor.ingest(
        InputSource(kind=SourceKind.AUDIO, location=str(src_file)),
        "01HZX9KQ7N8YV3JD4M2C6B5A0E", deps,
        language_hint=Language.FR, delete_audio_after=True,
    )
    assert transcription.segments  # FakeSTTProvider renvoie des segments
    assert not (workspace / "audio" / "01HZX9KQ7N8YV3JD4M2C6B5A0E.wav").exists()
```

> Note : un ingesteur gère un seul `kind` via la propriété. `MediaIngestor` gère
> **deux** kinds (VIDEO et AUDIO) au comportement identique. Le dispatcher (Tâche 5)
> enregistre **la même instance** sous les deux clés. La propriété `kind` n'est
> donc pas utilisée pour le routage du `MediaIngestor` (le dispatcher mappe
> explicitement) ; on la fixe à `SourceKind.AUDIO` par convention et le test
> ci-dessus vérifie juste qu'elle est l'une des deux.

- [ ] **Step 2: Lancer (échec)** — module absent

- [ ] **Step 3: Implémenter `media_ingestor.py`** (logique extraite de l'ancien `phase_0_stt`)

```python
"""Ingesteur des sources média locales (vidéo + audio) : ffmpeg → STT."""

from __future__ import annotations

from pathlib import Path

from fahmi2.domain.enums import Language, SourceKind
from fahmi2.domain.source import InputSource
from fahmi2.infra.ingestion.interface import IngestionDeps
from fahmi2.infra.stt.interface import Transcription

_AUDIO_SUBDIR = "audio"
_AUDIO_EXTENSION = ".wav"


class MediaIngestor:
    """Ingesteur vidéo/audio : extrait l'audio (WAV 16 kHz mono) puis transcrit."""

    @property
    def kind(self) -> SourceKind:
        """Convention : AUDIO (le dispatcher mappe aussi VIDEO sur cette instance)."""
        return SourceKind.AUDIO

    def ingest(
        self,
        source: InputSource,
        source_id: str,
        deps: IngestionDeps,
        *,
        language_hint: Language | None,
        delete_audio_after: bool,
    ) -> Transcription:
        """Extrait l'audio de ``source`` et le transcrit.

        Args:
            source: Source média locale (vidéo ou audio).
            source_id: Identifiant de la source (nom du WAV intermédiaire).
            deps: Dépendances injectées (ffmpeg, STT, workspace).
            language_hint: Indice de langue pour le STT (``None`` = auto).
            delete_audio_after: Supprime le WAV après transcription si ``True``.

        Returns:
            La ``Transcription`` produite.

        Raises:
            FFmpegError / STTError: propagées (retry géré par le moteur).
        """
        audio_path = deps.workspace / _AUDIO_SUBDIR / f"{source_id}{_AUDIO_EXTENSION}"
        try:
            deps.ffmpeg.extract(source.as_path, audio_path)
            return deps.stt_provider.transcribe(audio_path, language_hint=language_hint)
        finally:
            if delete_audio_after:
                _safe_delete(audio_path)


def _safe_delete(path: Path) -> None:
    """Supprime ``path`` si présent, sans lever en cas d'échec."""
    if path.exists():
        try:
            path.unlink()
        except OSError:
            pass
```

- [ ] **Step 4: Lancer (succès)** — `pytest tests/unit/infra/ingestion/test_media_ingestor.py -v` → PASS
- [ ] **Step 5: Commit** — `git commit -m "feat(ingestion): MediaIngestor (vidéo+audio)"`

---

## Tâche 5 : `IngestionDispatcher` + builder

**Files:**
- Create: `src/fahmi2/infra/ingestion/dispatcher.py`
- Test: `tests/unit/infra/ingestion/test_dispatcher.py`

- [ ] **Step 1: Écrire les tests**

```python
# tests/unit/infra/ingestion/test_dispatcher.py
import pytest

from fahmi2.core.errors.exceptions import IngestionError
from fahmi2.domain.enums import Language, SourceKind
from fahmi2.domain.source import InputSource
from fahmi2.infra.ingestion.dispatcher import build_default_ingestion_dispatcher
from fahmi2.infra.ingestion.interface import IngestionDeps


def test_dispatcher_routes_audio_and_video(tmp_path):
    dispatcher = build_default_ingestion_dispatcher()
    # MediaIngestor enregistré pour VIDEO et AUDIO :
    assert dispatcher.has_ingestor(SourceKind.VIDEO)
    assert dispatcher.has_ingestor(SourceKind.AUDIO)


def test_dispatcher_unsupported_kind_raises(tmp_path):
    dispatcher = build_default_ingestion_dispatcher()
    deps = IngestionDeps(workspace=tmp_path, artifacts=None, stt_provider=None, ffmpeg=None)  # type: ignore[arg-type]
    with pytest.raises(IngestionError) as exc:
        dispatcher.ingest(
            InputSource(kind=SourceKind.DOCUMENT, location="a.pdf"),
            "01HZX9KQ7N8YV3JD4M2C6B5A0E", deps,
            language_hint=Language.FR, delete_audio_after=True,
        )
    assert exc.value.code == "INGESTION.UNSUPPORTED_SOURCE"
```

- [ ] **Step 2: Lancer (échec)** — module absent

- [ ] **Step 3: Implémenter `dispatcher.py`**

```python
"""Aiguillage d'une source vers l'ingesteur adapté à son ``SourceKind``."""

from __future__ import annotations

from fahmi2.core.errors.exceptions import IngestionError
from fahmi2.core.errors.severity import Severity
from fahmi2.domain.enums import Language, SourceKind
from fahmi2.domain.source import InputSource
from fahmi2.infra.ingestion.interface import IngestionDeps, SourceIngestor
from fahmi2.infra.ingestion.media_ingestor import MediaIngestor
from fahmi2.infra.stt.interface import Transcription


class IngestionDispatcher:
    """Route ``ingest`` vers le ``SourceIngestor`` enregistré pour le ``SourceKind``."""

    def __init__(self, by_kind: dict[SourceKind, SourceIngestor]) -> None:
        """Construit le dispatcher.

        Args:
            by_kind: Mapping ``SourceKind → SourceIngestor``.
        """
        self._by_kind = by_kind

    def has_ingestor(self, kind: SourceKind) -> bool:
        """Indique si un ingesteur est enregistré pour ``kind``."""
        return kind in self._by_kind

    def ingest(
        self,
        source: InputSource,
        source_id: str,
        deps: IngestionDeps,
        *,
        language_hint: Language | None,
        delete_audio_after: bool,
    ) -> Transcription:
        """Aiguille vers l'ingesteur du ``kind`` de ``source``.

        Raises:
            IngestionError: ``INGESTION.UNSUPPORTED_SOURCE`` si aucun ingesteur.
        """
        ingestor = self._by_kind.get(source.kind)
        if ingestor is None:
            raise IngestionError(
                code="INGESTION.UNSUPPORTED_SOURCE",
                user_message=(
                    f"Type de source non pris en charge : {source.kind.value}."
                ),
                severity=Severity.ERROR,
                technical_details={"kind": source.kind.value, "location": source.location},
            )
        return ingestor.ingest(
            source, source_id, deps,
            language_hint=language_hint, delete_audio_after=delete_audio_after,
        )


def build_default_ingestion_dispatcher() -> IngestionDispatcher:
    """Construit le dispatcher par défaut (Lot 1B : vidéo + audio).

    Returns:
        Un ``IngestionDispatcher`` avec ``MediaIngestor`` pour VIDEO et AUDIO.
    """
    media = MediaIngestor()
    return IngestionDispatcher({SourceKind.VIDEO: media, SourceKind.AUDIO: media})
```

- [ ] **Step 4: Lancer (succès)** — `pytest tests/unit/infra/ingestion/test_dispatcher.py -v` → PASS
- [ ] **Step 5: Commit** — `git commit -m "feat(ingestion): IngestionDispatcher + builder par défaut"`

---

## Tâche 6 : `PhaseContext.ingestion` + phase 0 déléguée

**Files:**
- Modify: `src/fahmi2/pipeline/phase_handler.py`
- Modify: `src/fahmi2/pipeline/handlers/phase_0_stt.py`
- Modify: `tests/unit/pipeline/handlers/test_phase_0_stt.py`, `tests/unit/pipeline/handlers/_helpers.py`

- [ ] **Step 1: Ajouter le champ au `PhaseContext`**

Dans `phase_handler.py` : importer `from fahmi2.infra.ingestion.dispatcher import IngestionDispatcher` et ajouter le champ `ingestion: IngestionDispatcher` au dataclass `PhaseContext` (documenter dans la docstring).

- [ ] **Step 2: Réécrire `phase_0_stt.py` pour déléguer**

```python
# imports ajoutés
from fahmi2.infra.ingestion.interface import IngestionDeps

# dans execute(...) — corps remplacé :
        if source is None:
            raise ValueError("Phase0SttHandler requires a SourceExecution")
        started = datetime.now(tz=UTC)
        transcript_path = (
            ctx.workspace / _TRANSCRIPTS_SUBDIR
            / f"{source.source_id.value}{_TRANSCRIPT_EXTENSION}"
        )
        deps = IngestionDeps(
            workspace=ctx.workspace, artifacts=ctx.artifacts,
            stt_provider=ctx.stt_provider, ffmpeg=ctx.ffmpeg,
        )
        transcription = ctx.ingestion.ingest(
            source.source, source.source_id.value, deps,
            language_hint=ctx.settings.source_language,
            delete_audio_after=ctx.settings.delete_audio_after_stt,
        )
        cost = ctx.stt_provider.estimate_cost(transcription.duration_seconds)
        ctx.artifacts.write_json_atomic(
            transcript_path, _serialize_transcription(transcription)
        )
        finished = datetime.now(tz=UTC)
        return PhaseExecution(
            phase_id=PhaseId.STT, status=PhaseStatus.SUCCEEDED,
            started_at=started, finished_at=finished,
            artifact_path=transcript_path, cost_usd=cost,
        )
```

Supprimer de `phase_0_stt.py` l'extraction directe ffmpeg + le `_safe_delete` (désormais dans `MediaIngestor`) ; conserver `_serialize_transcription`. Mettre à jour les constantes inutilisées (`_AUDIO_SUBDIR`/`_AUDIO_EXTENSION` retirés ici).

- [ ] **Step 3: Adapter `_helpers.py`** — le builder de `PhaseContext` de test ajoute `ingestion=build_default_ingestion_dispatcher()`.

- [ ] **Step 4: Adapter `test_phase_0_stt.py`** — fournir un `PhaseContext` avec `ingestion`, une `SourceExecution(source=InputSource(kind=SourceKind.AUDIO|VIDEO, …))`, et vérifier que le transcript JSON est écrit. (Le test ffmpeg réel reste skip si ffmpeg absent.)

- [ ] **Step 5: Lancer**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/pipeline/handlers/test_phase_0_stt.py -v`
Expected: PASS

---

## Tâche 7 : `build_input_sources` (renommage scanner + audio) + orchestrateur

**Files:**
- Rename/Create: `src/fahmi2/app/video_scanner.py` → `src/fahmi2/app/input_sources.py`
- Modify: `src/fahmi2/app/run_orchestrator.py`
- Test: rename `tests/unit/app/test_video_scanner.py` → `tests/unit/app/test_input_sources.py`

- [ ] **Step 1: Écrire/adapter les tests**

```python
# tests/unit/app/test_input_sources.py
from pathlib import Path

import pytest

from fahmi2.core.errors.exceptions import ConfigError
from fahmi2.domain.enums import SourceKind
from fahmi2.app.input_sources import build_input_sources


def test_scans_video_and_audio_sorted(tmp_path, make_generation_settings):
    (tmp_path / "02-b.mp3").write_bytes(b"x")
    (tmp_path / "01-a.mp4").write_bytes(b"x")
    (tmp_path / "notes.zip").write_bytes(b"x")  # ignoré
    settings = make_generation_settings(input_folder=tmp_path)
    sources = build_input_sources(settings)
    assert [s.source.order_key() for s in sources] == ["01-a.mp4", "02-b.mp3"]
    assert sources[0].source.kind is SourceKind.VIDEO
    assert sources[1].source.kind is SourceKind.AUDIO


def test_empty_folder_raises(tmp_path, make_generation_settings):
    settings = make_generation_settings(input_folder=tmp_path)
    with pytest.raises(ConfigError) as exc:
        build_input_sources(settings)
    assert exc.value.code == "CONFIG.NO_INPUT_SOURCE"
```

- [ ] **Step 2: Lancer (échec)** — module absent

- [ ] **Step 3: Créer `input_sources.py`**

Déplacer le contenu de `video_scanner.py`, et :
- signature `build_input_sources(settings: GenerationSettings) -> list[SourceExecution]` (lit `settings.input_folder`) ;
- filtrer par `classify_file(p) is not None` (au lieu de `_SUPPORTED_EXTENSIONS`) ;
- conserver `_natural_sort_key` ;
- produire `SourceExecution(source_id=SourceId.new(), source=InputSource(kind=classify_file(p), location=str(p)))` ;
- erreur : code `CONFIG.NO_INPUT_SOURCE`, message « Le dossier d'entrée ne contient aucune source prise en charge (vidéos, audios). » ;
- conserver une fonction `supported_extensions()` déléguant à `classify.supported_file_extensions()` si encore référencée, sinon la retirer.

```python
from fahmi2.infra.ingestion.classify import classify_file, supported_file_extensions
# ...
def build_input_sources(settings: GenerationSettings) -> list[SourceExecution]:
    input_folder = settings.input_folder
    if not input_folder.exists() or not input_folder.is_dir():
        raise StorageError(code="STORAGE.READ_DENIED", ...)
    candidates = sorted(
        (p for p in input_folder.iterdir()
         if p.is_file() and classify_file(p) is not None),
        key=_natural_sort_key,
    )
    if not candidates:
        raise ConfigError(
            code="CONFIG.NO_INPUT_SOURCE",
            user_message=(
                "Le dossier d'entrée ne contient aucune source prise en charge "
                "(vidéos, audios)."
            ),
            severity=Severity.ERROR,
            technical_details={"input_folder": str(input_folder),
                               "supported": sorted(supported_file_extensions())},
        )
    return [
        SourceExecution(
            source_id=SourceId.new(),
            source=InputSource(kind=_kind_of(p), location=str(p)),
        )
        for p in candidates
    ]


def _kind_of(path: Path) -> SourceKind:
    kind = classify_file(path)
    assert kind is not None  # garanti par le filtre ci-dessus
    return kind
```

> Note : `build_input_sources` prend désormais `settings` (et non un `Path`), pour
> préparer l'usage de `youtube_urls`/`source_order` aux lots suivants.

- [ ] **Step 4: `run_orchestrator.py`** — remplacer `from fahmi2.app.video_scanner import scan_input_folder` par `from fahmi2.app.input_sources import build_input_sources` ; dans `create_run`, `videos = scan_input_folder(project.generation.input_folder)` → `sources = build_input_sources(project.generation)` ; `Run(..., sources=tuple(sources))`. Mettre à jour les docstrings (`ConfigError` code `CONFIG.NO_INPUT_SOURCE`).

- [ ] **Step 5: `git rm` l'ancien fichier**

```bash
git rm src/fahmi2/app/video_scanner.py tests/unit/app/test_video_scanner.py
```

- [ ] **Step 6: Lancer** — `pytest tests/unit/app/test_input_sources.py tests/unit/app/test_run_orchestrator.py -v` → PASS

---

## Tâche 8 : DI du dispatcher + estimation (contrôleur) + libellé UI

**Files:**
- Modify: `src/fahmi2/ui/generation_controller.py`
- Modify: `src/fahmi2/ui/viewmodels/run_matrix.py` (libellé phase 0)

- [ ] **Step 1: Injecter le dispatcher dans le `PhaseContext`**

Dans `generation_controller.py` : importer `from fahmi2.infra.ingestion.dispatcher import build_default_ingestion_dispatcher` ; dans la construction du `PhaseContext` (~ligne 524), ajouter `ingestion=build_default_ingestion_dispatcher(),`.

- [ ] **Step 2: Estimation de coût**

Remplacer `scan_input_folder(settings.input_folder)` (~ligne 685) par `build_input_sources(settings)` (import depuis `app.input_sources`) ; `durations = [ffmpeg.probe_duration_seconds(s.source.as_path) for s in sources]` ; `n_videos=len(sources)`. (La généralisation `SourceWeight` est traitée au Lot 2 ; au Lot 1B toutes les sources ont une durée audio.)

- [ ] **Step 3: Libellé phase 0**

Dans `run_matrix.py` (viewmodel), repérer le libellé de `PhaseId.STT` (table de libellés) et le passer de « STT »/« Transcription » à « Transcription / Ingestion ».

- [ ] **Step 4: Smoke test UI**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/ui -v`
Expected: PASS

---

## Tâche 9 : Repasse qualité finale & e2e

- [ ] **Step 1: Suite complète + lint + types**

Run:
```
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m mypy src tests
```
Expected: tout vert. (Le e2e `tests/e2e/test_full_pipeline.py` doit passer avec une source audio/vidéo via le dispatcher.)

- [ ] **Step 2: Commit final**

```bash
git add -A
git commit -m "feat(ingestion): phase 0 déléguée au dispatcher + scan audio (Lot 1B)"
```

---

## Self-review (rédacteur)
- **Spec §4** : port `SourceIngestor` (T3), `MediaIngestor` (T4), dispatcher + builder (T5) ✓.
- **Spec §4.7** : `classify_file` + extensions centralisées (T2) ✓.
- **Spec §5** : phase 0 délègue, `PhaseContext.ingestion`, artefact JSON inchangé (T6) ✓.
- **Spec §9.2** : `build_input_sources` (renommage scanner, audio), `CONFIG.NO_INPUT_SOURCE`, orchestrateur (T7) ✓.
- **Type consistency** : `IngestionDeps`, signature `ingest(source, source_id, deps, *, language_hint, delete_audio_after)` identique entre port (T3), `MediaIngestor` (T4), dispatcher (T5), phase 0 (T6) ✓.
- **Hors périmètre** (rappel) : DOCUMENT/YOUTUBE, `SourceWeight`, ordonnancement = lots 2/3/4.

## Dépendances vers les lots suivants
- **Lot 2 (Documents)** : ajoute `.pdf/.docx/.md/.txt` à `classify`, `TextExtractor` + `DocumentIngestor` (segment unique), enregistrement dans le builder du dispatcher, drapeau `reformulate_documents` + pass-through phase 3, `SourceWeight`.
- **Lot 3 (YouTube)** : `YtDlpDownloader` + `YoutubeIngestor`, `youtube_urls`, durée via métadonnée.
- **Lot 4 (Ordonnancement)** : `source_order`/`excluded_sources` + double liste UI.
