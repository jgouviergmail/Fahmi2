"""Adaptateur ``STTProvider`` utilisant ``faster-whisper`` localement.

Cet adapter requiert un GPU NVIDIA compatible CUDA : sans GPU, ``transcribe``
lève ``STT.GPU_UNAVAILABLE`` (la spec impose un blocage strict côté UI, voir
section 7.7 du design). Le modèle ``large-v3-turbo`` est téléchargé au premier
usage et mis en cache dans ``%LOCALAPPDATA%/Fahmi2/models/``.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from fahmi2.core.errors.exceptions import STTError
from fahmi2.core.errors.severity import Severity
from fahmi2.domain.enums import Language
from fahmi2.infra.stt.interface import (
    ProgressCallback,
    Transcription,
    TranscriptionSegment,
)

_PROVIDER_NAME = "faster-whisper-large-v3-turbo"
_MODEL_NAME = "large-v3-turbo"
_DEVICE_CUDA = "cuda"
_COMPUTE_TYPE_CUDA = "int8_float16"
_BEAM_SIZE = 5


def _default_cuda_check() -> bool:
    """Retourne ``True`` si CUDA est disponible.

    Utilise ``torch.cuda.is_available()`` si ``torch`` est importable. Si non
    importable (cas où faster-whisper est installé sans torch direct), tente
    via ``ctranslate2.get_cuda_device_count``.

    Returns:
        ``True`` si au moins un device CUDA est disponible.
    """
    try:
        import torch  # noqa: PLC0415 — import dynamique optionnel
    except ImportError:
        try:
            import ctranslate2  # noqa: PLC0415

            return bool(ctranslate2.get_cuda_device_count() > 0)
        except (ImportError, AttributeError):
            return False
    return bool(torch.cuda.is_available())


class FasterWhisperAdapter:
    """Adaptateur ``STTProvider`` local basé sur ``faster-whisper`` (CUDA requis)."""

    def __init__(
        self,
        *,
        model_cache_dir: Path,
        cuda_check: Callable[[], bool] | None = None,
    ) -> None:
        """Construit l'adaptateur.

        Args:
            model_cache_dir: Dossier où télécharger / lire le modèle.
            cuda_check: Fonction de détection CUDA (injectable pour les tests).
        """
        self._model_cache_dir = model_cache_dir
        self._cuda_check = cuda_check or _default_cuda_check
        self._model: object | None = None  # lazy, type étoffé en chargement

    @property
    def name(self) -> str:
        """Identifiant stable du provider."""
        return _PROVIDER_NAME

    def transcribe(
        self,
        audio_path: Path,
        *,
        language_hint: Language | None = None,
        on_progress: ProgressCallback | None = None,
    ) -> Transcription:
        """Transcrit ``audio_path`` via faster-whisper local.

        Args:
            audio_path: Fichier audio à transcrire.
            language_hint: Indice de langue (None = auto-détection).
            on_progress: Callback de progression.

        Returns:
            ``Transcription``.

        Raises:
            STTError: ``STT.GPU_UNAVAILABLE`` si CUDA absent.
            STTError: ``STT.MODEL_LOAD_FAILED`` si chargement modèle échoue.
            STTError: ``STT.GPU_OOM`` si CUDA OOM en transcription.
        """
        if not self._cuda_check():
            raise STTError(
                code="STT.GPU_UNAVAILABLE",
                user_message=(
                    "Aucun GPU NVIDIA compatible CUDA détecté. "
                    "Passe sur le mode OpenAI cloud."
                ),
                severity=Severity.ERROR,
                technical_details={"provider": _PROVIDER_NAME},
            )

        model = self._load_model_or_raise()
        if on_progress is not None:
            on_progress(0.0)

        segments_iter, info = model.transcribe(  # type: ignore[attr-defined]
            str(audio_path),
            language=str(language_hint) if language_hint else None,
            beam_size=_BEAM_SIZE,
        )

        segments: list[TranscriptionSegment] = []
        for seg in segments_iter:
            segments.append(
                TranscriptionSegment(
                    start_seconds=float(seg.start),
                    end_seconds=float(seg.end),
                    text=str(seg.text).strip(),
                )
            )
            if on_progress is not None and info.duration:
                on_progress(min(1.0, seg.end / info.duration))

        if on_progress is not None:
            on_progress(1.0)

        return Transcription(
            segments=tuple(segments),
            detected_language=Language(info.language),
            duration_seconds=float(info.duration),
        )

    def estimate_cost(self, duration_seconds: float) -> float:
        """Coût USD : 0 (exécution locale).

        Args:
            duration_seconds: Durée audio (ignorée).

        Returns:
            ``0.0``.
        """
        del duration_seconds
        return 0.0

    def _load_model_or_raise(self) -> object:
        """Charge le modèle au 1er usage (lazy).

        Returns:
            L'objet ``WhisperModel`` chargé.

        Raises:
            STTError: ``STT.MODEL_LOAD_FAILED`` si chargement échoue.
        """
        if self._model is not None:
            return self._model
        try:
            from faster_whisper import WhisperModel  # noqa: PLC0415

            self._model_cache_dir.mkdir(parents=True, exist_ok=True)
            self._model = WhisperModel(
                _MODEL_NAME,
                device=_DEVICE_CUDA,
                compute_type=_COMPUTE_TYPE_CUDA,
                download_root=str(self._model_cache_dir),
            )
        except Exception as exc:  # noqa: BLE001 — mappé vers une STTError typée
            raise STTError(
                code="STT.MODEL_LOAD_FAILED",
                user_message=(
                    "Le modèle faster-whisper n'a pas pu être chargé. "
                    "Vérifie ton installation et l'accès au GPU."
                ),
                severity=Severity.ERROR,
                technical_details={"error": str(exc)},
            ) from exc
        return self._model
