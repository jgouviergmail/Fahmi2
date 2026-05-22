# Lot 3 — Liens YouTube (unitaires) : téléchargement audio + ingestion (plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Accepter des **liens YouTube unitaires** comme entrants : `yt-dlp` télécharge l'audio, puis ingestion via le `MediaIngestor` existant (ffmpeg + STT). Saisie via un champ « Liens YouTube » dans les réglages ; coût estimé via la durée de la vidéo (métadonnée yt-dlp).

**Architecture:** Nouveau port `YoutubeDownloader` + adapter `YtDlpDownloader` (binaire yt-dlp résolu au runtime, override env). `YoutubeIngestor` **compose** `MediaIngestor` (télécharge → `InputSource(AUDIO, fichier)` → délègue) : zéro duplication de la logique ffmpeg/STT. `GenerationSettings.youtube_urls` (saisie) ; `build_input_sources` ajoute les URLs après les fichiers. Pas de playlist (`--no-playlist`), STT systématique.

**Tech Stack:** Python 3.12, `yt-dlp` **binaire** (bundlé + override `FAHMI2_YTDLP`), subprocess, pytest, ruff (line-length 100), mypy --strict. Interpréteur : `.venv\Scripts\python.exe`.

**Prérequis:** Lots 1A/1B/2 (couche `infra/ingestion/`, dispatcher, `MediaIngestor`, `SourceWeight`, `build_input_sources`).

**Spec de référence:** `docs/superpowers/specs/2026-05-22-entrants-generation-elargis-design.md` (§4.3, §8 YouTube, §11, §12).

**Limites assumées (Lot 3) :** pas de remontée fine de la **progression** du téléchargement (le port `SourceIngestor` n'expose pas `on_progress` ; ajout différé pour ne pas modifier le contrat) ; `YtDlpDownloader` non couvert par un test réseau (réseau requis) — seuls le mapping d'erreur et la composition `YoutubeIngestor` (downloader fake) sont testés.

---

## Tâche 1 : `resolve_ytdlp_binary_or_none` (résolution runtime + override)

**Files:** Modify `src/fahmi2/core/config/paths.py` ; Modify `tests/unit/core/test_paths.py`

- [ ] **Step 1: Écrire les tests**

```python
# tests/unit/core/test_paths.py — ajouter
import os
from fahmi2.core.config.paths import resolve_ytdlp_binary_or_none


def test_ytdlp_override_env_takes_precedence(monkeypatch) -> None:
    monkeypatch.setenv("FAHMI2_YTDLP", "C:/tools/yt-dlp.exe")
    assert resolve_ytdlp_binary_or_none() == "C:/tools/yt-dlp.exe"


def test_ytdlp_none_in_dev(monkeypatch) -> None:
    monkeypatch.delenv("FAHMI2_YTDLP", raising=False)
    # En dev (non packagé), pas de binaire bundlé → None (PATH système).
    assert resolve_ytdlp_binary_or_none() is None
```

- [ ] **Step 2: Lancer (échec)** — fonction absente.

- [ ] **Step 3: Implémenter**

Dans `paths.py`, ajouter les constantes et la fonction :
```python
_YTDLP_OVERRIDE_ENV = "FAHMI2_YTDLP"
_YTDLP_BINARY_NAME = "yt-dlp.exe"


def resolve_ytdlp_binary_or_none() -> str | None:
    """Retourne le chemin du binaire ``yt-dlp`` à utiliser, ou ``None``.

    Priorité : variable d'environnement ``FAHMI2_YTDLP`` (override permettant de
    pointer un yt-dlp à jour sans rebuild), puis binaire bundlé (mode packagé),
    sinon ``None`` (le ``PATH`` système est utilisé).

    Returns:
        Chemin absolu/explicite, ou ``None`` si aucun (fallback PATH).
    """
    override = os.environ.get(_YTDLP_OVERRIDE_ENV)
    if override:
        return override
    bundle_dir = resolve_bundled_ffmpeg_dir()  # même racine de bundle que ffmpeg
    if bundle_dir is None:
        return None
    candidate = bundle_dir / _YTDLP_BINARY_NAME
    return str(candidate) if candidate.exists() else None
```

- [ ] **Step 4: Lancer (succès)** — `pytest tests/unit/core/test_paths.py -v` → PASS
- [ ] **Step 5: Commit** — `git commit -m "feat(config): resolve_ytdlp_binary_or_none (bundle + override FAHMI2_YTDLP)"`

---

## Tâche 2 : Port `YoutubeDownloader` + adapter `YtDlpDownloader` + fake

**Files:** Create `src/fahmi2/infra/ingestion/youtube_downloader.py` ; Modify `src/fahmi2/infra/ingestion/_fakes.py` ; Test `tests/unit/infra/ingestion/test_youtube_downloader.py`

- [ ] **Step 1: Ajouter `FakeYoutubeDownloader`** (`_fakes.py`)

```python
class FakeYoutubeDownloader:
    """``YoutubeDownloader`` factice : « télécharge » en créant un fichier local."""

    def __init__(self, *, duration_seconds: float = 60.0,
                 fail_with: Exception | None = None) -> None:
        self._duration = duration_seconds
        self._fail_with = fail_with

    def download_audio(self, url: str, dest_dir: Path, stem: str) -> Path:
        if self._fail_with is not None:
            raise self._fail_with
        dest_dir.mkdir(parents=True, exist_ok=True)
        out = dest_dir / f"{stem}.m4a"
        out.write_bytes(b"fake-audio")
        return out

    def probe_duration(self, url: str) -> float:
        return self._duration
```

- [ ] **Step 2: Écrire les tests de l'adapter (mapping d'erreur ; pas de réseau)**

```python
# tests/unit/infra/ingestion/test_youtube_downloader.py
from pathlib import Path

import pytest

from fahmi2.core.errors.exceptions import IngestionError
from fahmi2.infra.ingestion.youtube_downloader import YtDlpDownloader


def test_download_missing_binary_raises_not_found(tmp_path: Path) -> None:
    downloader = YtDlpDownloader(ytdlp_binary="ytdlp-inexistant-xyz")
    with pytest.raises(IngestionError) as exc:
        downloader.download_audio("https://youtu.be/x", tmp_path, "01H")
    assert exc.value.code == "INGESTION.YTDLP_NOT_FOUND"


def test_probe_duration_missing_binary_returns_zero(tmp_path: Path) -> None:
    downloader = YtDlpDownloader(ytdlp_binary="ytdlp-inexistant-xyz")
    assert downloader.probe_duration("https://youtu.be/x") == 0.0
```

- [ ] **Step 3: Lancer (échec)** — module absent.

- [ ] **Step 4: Implémenter `youtube_downloader.py`**

```python
"""Téléchargement de l'audio d'une vidéo YouTube via le binaire ``yt-dlp``.

Port ``YoutubeDownloader`` + adapter ``YtDlpDownloader`` (subprocess). Liens
**unitaires** uniquement (``--no-playlist``). Le binaire est résolu au runtime
(bundlé / override), et reste **remplaçable** sans rebuild (yt-dlp casse
régulièrement quand YouTube évolue).
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Protocol

from fahmi2.core.errors.exceptions import IngestionError
from fahmi2.core.errors.severity import Severity

_YTDLP_BINARY = "yt-dlp"
_BESTAUDIO_FORMAT = "bestaudio/best"
_NO_PLAYLIST = "--no-playlist"


class YoutubeDownloader(Protocol):
    """Télécharge l'audio d'une vidéo YouTube et sonde sa durée."""

    def download_audio(self, url: str, dest_dir: Path, stem: str) -> Path:
        """Télécharge la meilleure piste audio de ``url`` dans ``dest_dir``.

        Args:
            url: URL de la vidéo YouTube (unitaire).
            dest_dir: Dossier de destination (créé si absent).
            stem: Nom de base du fichier produit (sans extension).

        Returns:
            Le chemin du fichier audio téléchargé.

        Raises:
            IngestionError: ``INGESTION.YTDLP_NOT_FOUND`` / ``YOUTUBE_DOWNLOAD_FAILED``.
        """

    def probe_duration(self, url: str) -> float:
        """Durée de la vidéo (s) via métadonnée, sans téléchargement.

        Args:
            url: URL de la vidéo.

        Returns:
            La durée en secondes (``0.0`` si indéterminable / réseau indisponible).
        """


class YtDlpDownloader:
    """Adapter ``yt-dlp`` (binaire externe)."""

    def __init__(self, *, ytdlp_binary: str | None = None) -> None:
        """Construit l'adapter.

        Args:
            ytdlp_binary: Chemin du binaire yt-dlp (``None`` = ``yt-dlp`` du PATH).
        """
        self._ytdlp = ytdlp_binary or _YTDLP_BINARY

    def download_audio(self, url: str, dest_dir: Path, stem: str) -> Path:
        """Télécharge la meilleure piste audio (cf. port)."""
        dest_dir.mkdir(parents=True, exist_ok=True)
        output_template = str(dest_dir / f"{stem}.%(ext)s")
        cmd = [
            self._ytdlp, _NO_PLAYLIST, "-f", _BESTAUDIO_FORMAT,
            "-o", output_template, url,
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True)  # noqa: S603
        except FileNotFoundError as exc:
            raise IngestionError(
                code="INGESTION.YTDLP_NOT_FOUND",
                user_message=(
                    "yt-dlp est introuvable. Installez-le ou définissez la "
                    "variable d'environnement FAHMI2_YTDLP."
                ),
                severity=Severity.FATAL,
                technical_details={"ytdlp_binary": self._ytdlp},
            ) from exc
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr.decode("utf-8", errors="replace") if exc.stderr else ""
            raise IngestionError(
                code="INGESTION.YOUTUBE_DOWNLOAD_FAILED",
                user_message=(
                    "Échec du téléchargement YouTube (vidéo indisponible, privée, "
                    "géo-bloquée, ou yt-dlp obsolète — essayez de le mettre à jour)."
                ),
                severity=Severity.ERROR,
                technical_details={"url": url, "stderr": stderr},
            ) from exc
        produced = sorted(dest_dir.glob(f"{stem}.*"))
        if not produced:
            raise IngestionError(
                code="INGESTION.YOUTUBE_DOWNLOAD_FAILED",
                user_message="Le téléchargement YouTube n'a produit aucun fichier.",
                severity=Severity.ERROR,
                technical_details={"url": url, "stem": stem},
            )
        return produced[0]

    def probe_duration(self, url: str) -> float:
        """Durée via ``--print duration --skip-download`` (cf. port)."""
        cmd = [
            self._ytdlp, _NO_PLAYLIST, "--skip-download", "--print", "duration", url,
        ]
        try:
            result = subprocess.run(  # noqa: S603
                cmd, check=True, capture_output=True
            )
        except (FileNotFoundError, subprocess.CalledProcessError):
            return 0.0
        try:
            return float(result.stdout.decode("utf-8").strip().splitlines()[-1])
        except (ValueError, IndexError):
            return 0.0
```

- [ ] **Step 5: Lancer (succès)** — `pytest tests/unit/infra/ingestion/test_youtube_downloader.py -v` → PASS
- [ ] **Step 6: Commit** — `git commit -m "feat(ingestion): YoutubeDownloader + YtDlpDownloader (binaire) + fake"`

---

## Tâche 3 : `YoutubeIngestor` (compose `MediaIngestor`)

**Files:** Create `src/fahmi2/infra/ingestion/youtube_ingestor.py` ; Test `tests/unit/infra/ingestion/test_youtube_ingestor.py`

- [ ] **Step 1: Écrire les tests (download fake + STT fake, ffmpeg réel requis)**

```python
# tests/unit/infra/ingestion/test_youtube_ingestor.py
import subprocess
from pathlib import Path

import pytest

from fahmi2.core.errors.exceptions import IngestionError
from fahmi2.domain.enums import Language, SourceKind
from fahmi2.domain.source import InputSource
from fahmi2.infra.audio.ffmpeg_extractor import FFmpegExtractor, has_ffmpeg_in_path
from fahmi2.infra.ingestion._fakes import FakeYoutubeDownloader
from fahmi2.infra.ingestion.interface import IngestionDeps
from fahmi2.infra.ingestion.media_ingestor import MediaIngestor
from fahmi2.infra.ingestion.youtube_ingestor import YoutubeIngestor
from fahmi2.infra.storage.fs_artifacts import FsArtifactStore
from fahmi2.infra.stt._fakes import FakeSTTProvider

_SOURCE_ID = "01HZX9KQ7N8YV3JD4M2C6B5A0E"
pytestmark = pytest.mark.skipif(not has_ffmpeg_in_path(), reason="ffmpeg requis")


def _real_audio_downloader(tmp_path: Path):
    # Downloader fake qui produit un vrai WAV (pour que ffmpeg puisse l'extraire).
    class _D(FakeYoutubeDownloader):
        def download_audio(self, url: str, dest_dir: Path, stem: str) -> Path:
            dest_dir.mkdir(parents=True, exist_ok=True)
            out = dest_dir / f"{stem}.wav"
            subprocess.run(
                ["ffmpeg", "-y", "-f", "lavfi", "-i",
                 "sine=frequency=440:duration=1", "-ac", "1", "-ar", "16000",
                 "-loglevel", "error", str(out)],
                check=True, capture_output=True,
            )
            return out
    return _D()


def _deps(tmp_path: Path) -> IngestionDeps:
    return IngestionDeps(
        workspace=tmp_path / "ws", artifacts=FsArtifactStore(),
        stt_provider=FakeSTTProvider(), ffmpeg=FFmpegExtractor(),
    )


def test_youtube_ingest_delegates_to_media(tmp_path: Path) -> None:
    ingestor = YoutubeIngestor(_real_audio_downloader(tmp_path), MediaIngestor())
    transcription = ingestor.ingest(
        InputSource(kind=SourceKind.YOUTUBE, location="https://youtu.be/abc"),
        _SOURCE_ID, _deps(tmp_path),
        language_hint=Language.FR, delete_audio_after=True,
    )
    assert transcription.segments  # STT (fake) a produit un segment
    # Le fichier téléchargé intermédiaire est nettoyé.
    assert not (tmp_path / "ws" / "downloads" / f"{_SOURCE_ID}.wav").exists()


def test_youtube_ingest_propagates_download_error(tmp_path: Path) -> None:
    boom = IngestionError(code="INGESTION.YOUTUBE_DOWNLOAD_FAILED",
                          user_message="x", severity=__import__(
                              "fahmi2.core.errors.severity", fromlist=["Severity"]
                          ).Severity.ERROR)
    ingestor = YoutubeIngestor(FakeYoutubeDownloader(fail_with=boom), MediaIngestor())
    with pytest.raises(IngestionError) as exc:
        ingestor.ingest(
            InputSource(kind=SourceKind.YOUTUBE, location="https://youtu.be/x"),
            _SOURCE_ID, _deps(tmp_path),
            language_hint=Language.FR, delete_audio_after=True,
        )
    assert exc.value.code == "INGESTION.YOUTUBE_DOWNLOAD_FAILED"
```
> (Simplifier l'import `Severity` dans le test : `from fahmi2.core.errors.severity import Severity` en tête.)

- [ ] **Step 2: Lancer (échec)** — module absent.

- [ ] **Step 3: Implémenter `youtube_ingestor.py`**

```python
"""Ingesteur des sources YouTube : téléchargement audio puis délégation média.

Compose ``MediaIngestor`` : ``yt-dlp`` télécharge la piste audio dans le
workspace, puis le fichier est ingéré comme un média local (ffmpeg + STT). Le
fichier téléchargé intermédiaire est supprimé après extraction.
"""

from __future__ import annotations

from fahmi2.domain.enums import Language, SourceKind
from fahmi2.domain.source import InputSource
from fahmi2.infra.ingestion.interface import IngestionDeps
from fahmi2.infra.ingestion.media_ingestor import MediaIngestor
from fahmi2.infra.ingestion.youtube_downloader import YoutubeDownloader
from fahmi2.infra.stt.interface import Transcription

_DOWNLOADS_SUBDIR = "downloads"


class YoutubeIngestor:
    """Ingesteur YouTube : télécharge l'audio (yt-dlp) puis délègue au média."""

    def __init__(
        self, downloader: YoutubeDownloader, media_ingestor: MediaIngestor
    ) -> None:
        """Construit l'ingesteur.

        Args:
            downloader: Téléchargeur yt-dlp.
            media_ingestor: Ingesteur média réutilisé pour l'audio téléchargé.
        """
        self._downloader = downloader
        self._media_ingestor = media_ingestor

    @property
    def kind(self) -> SourceKind:
        """Type de source géré."""
        return SourceKind.YOUTUBE

    def ingest(
        self,
        source: InputSource,
        source_id: str,
        deps: IngestionDeps,
        *,
        language_hint: Language | None,
        delete_audio_after: bool,
    ) -> Transcription:
        """Télécharge l'audio de ``source`` (URL) puis l'ingère via le média.

        Args:
            source: Source YouTube (``location`` = URL).
            source_id: Identifiant de la source.
            deps: Dépendances injectées (workspace, ffmpeg, STT).
            language_hint: Indice de langue pour le STT.
            delete_audio_after: Transmis au ``MediaIngestor`` (WAV extrait).

        Returns:
            La ``Transcription`` produite.

        Raises:
            IngestionError: Échec de téléchargement (propagé du downloader).
        """
        downloads_dir = deps.workspace / _DOWNLOADS_SUBDIR
        downloaded = self._downloader.download_audio(
            source.location, downloads_dir, source_id
        )
        try:
            media_source = InputSource(
                kind=SourceKind.AUDIO, location=str(downloaded)
            )
            return self._media_ingestor.ingest(
                media_source, source_id, deps,
                language_hint=language_hint, delete_audio_after=delete_audio_after,
            )
        finally:
            if downloaded.exists():
                try:
                    downloaded.unlink()
                except OSError:
                    pass
```

- [ ] **Step 4: Lancer (succès)** — PASS
- [ ] **Step 5: Commit** — `git commit -m "feat(ingestion): YoutubeIngestor (compose MediaIngestor)"`

---

## Tâche 4 : Brancher `YoutubeIngestor` dans le dispatcher

**Files:** Modify `src/fahmi2/infra/ingestion/dispatcher.py` ; Modify `tests/unit/infra/ingestion/test_dispatcher.py`

- [ ] **Step 1: Test** — `test_default_dispatcher_handles_video_audio_and_documents` : ajouter `assert dispatcher.has_ingestor(SourceKind.YOUTUBE)` (renommer en `_handles_all_kinds`). Remplacer `test_unsupported_kind_raises` : créer un dispatcher **vide** `IngestionDispatcher({})` et vérifier `UNSUPPORTED_SOURCE` (puisque tous les kinds sont désormais gérés par défaut).
- [ ] **Step 2: Lancer (échec)** — YOUTUBE pas enregistré.
- [ ] **Step 3: Implémenter** — dans `build_default_ingestion_dispatcher` : 
```python
from fahmi2.core.config.paths import resolve_ytdlp_binary_or_none  # en tête
from fahmi2.infra.ingestion.youtube_downloader import YtDlpDownloader
from fahmi2.infra.ingestion.youtube_ingestor import YoutubeIngestor

    media = MediaIngestor()
    document = DocumentIngestor(DefaultTextExtractor())
    youtube = YoutubeIngestor(
        YtDlpDownloader(ytdlp_binary=resolve_ytdlp_binary_or_none()), media
    )
    return IngestionDispatcher({
        SourceKind.VIDEO: media,
        SourceKind.AUDIO: media,
        SourceKind.DOCUMENT: document,
        SourceKind.YOUTUBE: youtube,
    })
```
Mettre à jour la docstring. (Note : `resolve_ytdlp_binary_or_none` dans `core.config.paths` ne crée aucun cycle.)
- [ ] **Step 4: Lancer (succès)** — `pytest tests/unit/infra/ingestion -v` → PASS
- [ ] **Step 5: Commit** — `git commit -m "feat(ingestion): branche YoutubeIngestor dans le dispatcher"`

---

## Tâche 5 : `youtube_urls` (domain + persistance + fixture + UI)

**Files:** Modify `src/fahmi2/domain/generation.py`, `src/fahmi2/infra/storage/sqlite_state.py`, `tests/conftest.py`, `src/fahmi2/ui/dialogs/generation_settings_view.py` ; Test `tests/unit/domain/test_generation.py`

- [ ] **Step 1: Domaine** — `GenerationSettings` : ajouter `youtube_urls: tuple[str, ...] = ()` (après `reformulate_documents`) + docstring.
- [ ] **Step 2: Persistance** — `_serialize_generation_settings` : `"youtube_urls": list(gen.youtube_urls),` ; `_deserialize_generation_settings` : `youtube_urls=tuple(payload.get("youtube_urls", [])),`.
- [ ] **Step 3: Fixture** — `conftest.py` : `"youtube_urls": (),` dans `base`.
- [ ] **Step 4: Test domaine** :
```python
def test_youtube_urls_default_empty() -> None:
    assert _make().youtube_urls == ()
    assert _make(youtube_urls=("https://youtu.be/x",)).youtube_urls == ("https://youtu.be/x",)
```
- [ ] **Step 5: UI** — dans `generation_settings_view.py` :
  - constantes `_YOUTUBE_URLS_LABEL = "Liens YouTube (un par ligne)"` + `_YOUTUBE_URLS_PLACEHOLDER`.
  - `_build_fields` : `self._youtube_urls_input = QTextEdit(self)` + placeholder + `setFixedHeight(...)` + `setAcceptRichText(False)`.
  - page « Sources »/« Entrée & langues » (`_build_input_page`) : `form.addRow(_YOUTUBE_URLS_LABEL, self._youtube_urls_input)`.
  - `_populate` : `self._youtube_urls_input.setPlainText("\n".join(generation.youtube_urls))`.
  - `_on_accept` : parser → `youtube_urls = tuple(u.strip() for u in self._youtube_urls_input.toPlainText().splitlines() if u.strip())`, passé au constructeur.
- [ ] **Step 6: Lancer** — `pytest tests/unit/domain/test_generation.py tests/unit/infra/storage tests/unit/ui/test_generation_settings_view.py -q` → PASS
- [ ] **Step 7: Commit** — `git commit -m "feat(generation): champ youtube_urls (saisie + persistance + UI)"`

---

## Tâche 6 : `build_input_sources` ajoute les URLs YouTube

**Files:** Modify `src/fahmi2/app/input_sources.py` ; Test `tests/unit/app/test_input_sources.py`

- [ ] **Step 1: Tests** :
```python
def test_youtube_urls_appended_after_files(tmp_path, make_generation_settings):
    (tmp_path / "01-a.mp4").write_bytes(b"x")
    settings = make_generation_settings(
        input_folder=tmp_path, youtube_urls=("https://youtu.be/abc",)
    )
    sources = build_input_sources(settings)
    assert sources[0].source.kind is SourceKind.VIDEO
    assert sources[-1].source.kind is SourceKind.YOUTUBE
    assert sources[-1].source.location == "https://youtu.be/abc"


def test_youtube_only_is_valid(tmp_path, make_generation_settings):
    settings = make_generation_settings(
        input_folder=tmp_path, youtube_urls=("https://youtu.be/abc",)
    )
    sources = build_input_sources(settings)
    assert len(sources) == 1
    assert sources[0].source.kind is SourceKind.YOUTUBE


def test_no_files_no_urls_raises(tmp_path, make_generation_settings):
    settings = make_generation_settings(input_folder=tmp_path)
    with pytest.raises(ConfigError) as exc:
        build_input_sources(settings)
    assert exc.value.code == "CONFIG.NO_INPUT_SOURCE"
```

- [ ] **Step 2: Lancer (échec)** — URLs non ajoutées ; le `test_youtube_only` lève `NO_INPUT_SOURCE` (le dossier est vide).

- [ ] **Step 3: Implémenter** — dans `build_input_sources` :
  - Après la construction des sources fichier (`file_sources`), ajouter les URLs :
    ```python
    youtube_sources = [
        SourceExecution(
            source_id=SourceId.new(),
            source=InputSource(kind=SourceKind.YOUTUBE, location=url),
        )
        for url in settings.youtube_urls
    ]
    all_sources = file_sources + youtube_sources
    ```
  - Déplacer le test « aucune source » : lever `CONFIG.NO_INPUT_SOURCE` seulement si `not all_sources` (et le contrôle « dossier inaccessible » reste ; un dossier vide **avec** des URLs est valide). Adapter le message (« vidéos, audios, documents ou liens YouTube »).
  - **Important** : le dossier doit rester scanné même s'il est vide tant qu'il existe ; si `input_folder` n'existe pas mais qu'il y a des URLs → tolérer (ne pas lever `READ_DENIED`)? Décision : si `youtube_urls` non vide et dossier inexistant, **ne pas** lever `READ_DENIED` (on traite seulement les URLs). Sinon (pas d'URL), conserver `READ_DENIED`. Réorganiser : scanner les fichiers seulement si le dossier existe ; sinon `file_sources = []`.

- [ ] **Step 4: Lancer (succès)** — `pytest tests/unit/app/test_input_sources.py -v` → PASS
- [ ] **Step 5: Commit** — `git commit -m "feat(ingestion): build_input_sources ajoute les liens YouTube"`

---

## Tâche 7 : Coût — durée YouTube via métadonnée

**Files:** Modify `src/fahmi2/ui/generation_controller.py` ; Test `tests/unit/ui/...` (smoke) ou test du helper

- [ ] **Step 1: Adapter `_source_weight`** — ajouter un paramètre `youtube_downloader: YoutubeDownloader` :
```python
    if source.source.kind is SourceKind.YOUTUBE:
        return SourceWeight(
            audio_seconds=youtube_downloader.probe_duration(source.source.location),
            text_tokens=0.0,
        )
    if source.source.kind is SourceKind.DOCUMENT:
        ...  # inchangé
    return SourceWeight(audio_seconds=ffmpeg.probe_duration_seconds(source.source.as_path), text_tokens=0.0)
```
- [ ] **Step 2: Appelant (estimation)** — créer `youtube_downloader = YtDlpDownloader(ytdlp_binary=resolve_ytdlp_binary_or_none())` avant la boucle ; passer aux `_source_weight(s, ffmpeg, settings, youtube_downloader)`. Importer `YtDlpDownloader`, `resolve_ytdlp_binary_or_none`, `YoutubeDownloader` (type hint). (`probe_duration` renvoie 0 si réseau indisponible → estimation partielle assumée.)
- [ ] **Step 3: Lancer** — `pytest tests/unit/ui -q` → PASS (le smoke d'estimation ne sonde pas de YouTube réel).
- [ ] **Step 4: Commit** — `git commit -m "feat(cost): duree YouTube via yt-dlp pour l'estimation"`

---

## Tâche 8 : Repasse qualité finale + doc + packaging

- [ ] **Step 1: Suite + lint + types**

Run:
```
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m mypy src tests
```
Expected: tout vert.

- [ ] **Step 2: Documentation**
- `CLAUDE.md` : intro (YouTube supporté) ; couche `infra/ingestion` (YoutubeIngestor + YtDlpDownloader) ; mécanisme entrants (URLs via `youtube_urls`, `--no-playlist`, binaire remplaçable).
- `packaging/README.md` : **télécharger le binaire `yt-dlp.exe`** au build (script type `fetch-ffmpeg.ps1`), le bundler à la racine ; résolution runtime `resolve_ytdlp_binary_or_none` (override `FAHMI2_YTDLP`) ; **fragilité** (mettre à jour régulièrement) ; réseau requis ; ToS YouTube assumées par l'utilisateur.
- `packaging/fetch-ytdlp.ps1` (nouveau, optionnel) : télécharge `yt-dlp.exe` depuis la release GitHub officielle vers le dossier de bundle. (Documenté ; non exécuté hors build.)

- [ ] **Step 3: Commit doc** — `git commit -m "docs: entrants YouTube (Lot 3)"`

---

## Self-review (rédacteur)
- **Spec §4.3** : `YoutubeDownloader`/`YtDlpDownloader` (T2), `YoutubeIngestor` compose `MediaIngestor` (T3) ✓.
- **Spec §8 (coût YouTube)** : durée via `probe_duration` (T7) ✓.
- **Spec §11** : erreurs `YTDLP_NOT_FOUND`/`YOUTUBE_DOWNLOAD_FAILED` (T2) ✓.
- **Spec §12** : résolution binaire + override (T1), packaging documenté (T8) ✓.
- **Saisie** : `youtube_urls` + UI (T5), `build_input_sources` (T6) ✓.
- **Type consistency** : `YoutubeIngestor.ingest(...)` conforme au port `SourceIngestor` ; `download_audio(url, dest_dir, stem)` / `probe_duration(url)` cohérents entre port, adapter, fake (T2/T3) ✓.
- **Constantes** : `_BESTAUDIO_FORMAT`, `_NO_PLAYLIST`, `_DOWNLOADS_SUBDIR`, `_YTDLP_OVERRIDE_ENV`, `_YTDLP_BINARY_NAME` ✓.

## Dépendances vers le lot suivant
- **Lot 4 (Ordonnancement)** : `source_order`/`excluded_sources` ordonnent/filtrent toutes les sources (fichiers + URLs) ; double liste UI.
