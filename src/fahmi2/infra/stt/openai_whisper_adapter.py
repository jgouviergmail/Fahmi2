"""Adaptateur ``STTProvider`` qui appelle l'endpoint OpenAI Whisper.

Modèle utilisé : ``whisper-1``. Tarification : 0.006 USD par minute audio.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from openai import APIError, APIStatusError, AuthenticationError, OpenAI, RateLimitError

from fahmi2.core.errors.exceptions import LLMError, STTError
from fahmi2.core.errors.severity import Severity
from fahmi2.domain.enums import Language
from fahmi2.infra.stt.interface import (
    ProgressCallback,
    Transcription,
    TranscriptionSegment,
)

_PROVIDER_NAME = "openai-whisper"
_MODEL_NAME = "whisper-1"
_USD_PER_MINUTE = 0.006
_SECONDS_PER_MINUTE = 60.0


def _map_status_code_to_stt_error(
    exc: APIStatusError | RateLimitError | AuthenticationError | APIError,
) -> STTError | LLMError:
    if isinstance(exc, AuthenticationError):
        return STTError(
            code="STT.AUTH_INVALID",
            user_message=(
                "La clé OpenAI est refusée. Vérifie-la dans Paramètres › Clés API."
            ),
            severity=Severity.ERROR,
            technical_details={"provider": _PROVIDER_NAME},
        )
    if isinstance(exc, RateLimitError):
        return STTError(
            code="STT.RATE_LIMIT",
            user_message="Limite de débit OpenAI atteinte.",
            severity=Severity.WARNING,
            technical_details={"provider": _PROVIDER_NAME},
        )
    return STTError(
        code="STT.API_ERROR",
        user_message="Échec d'appel à l'API OpenAI Whisper.",
        severity=Severity.ERROR,
        technical_details={"provider": _PROVIDER_NAME, "error": str(exc)},
    )


class OpenAIWhisperAdapter:
    """Implémentation ``STTProvider`` appelant l'endpoint OpenAI Whisper."""

    def __init__(self, *, api_key: str, client: OpenAI | None = None) -> None:
        """Construit l'adaptateur.

        Args:
            api_key: Clé API OpenAI.
            client: Client OpenAI injectable (utile pour les tests).
        """
        self._client = client or OpenAI(api_key=api_key)

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
        """Transcrit ``audio_path`` via l'endpoint OpenAI Whisper.

        Args:
            audio_path: Chemin du fichier audio.
            language_hint: Indice de langue (passé à l'API si fourni).
            on_progress: Callback de progression.

        Returns:
            ``Transcription`` reconstruite depuis la réponse JSON verbose.

        Raises:
            STTError: En cas d'erreur API/authentification/rate-limit.
        """
        if on_progress is not None:
            on_progress(0.0)
        try:
            with audio_path.open("rb") as fp:
                kwargs: dict[str, Any] = {
                    "model": _MODEL_NAME,
                    "file": fp,
                    "response_format": "verbose_json",
                }
                if language_hint is not None:
                    kwargs["language"] = str(language_hint)
                response = self._client.audio.transcriptions.create(**kwargs)
        except (
            APIError,
            APIStatusError,
            AuthenticationError,
            RateLimitError,
        ) as exc:
            raise _map_status_code_to_stt_error(exc) from exc
        if on_progress is not None:
            on_progress(1.0)
        return _parse_verbose_response(response.model_dump())

    def estimate_cost(self, duration_seconds: float) -> float:
        """Estime le coût en USD pour une durée audio donnée.

        Args:
            duration_seconds: Durée de l'audio (secondes).

        Returns:
            Coût USD.
        """
        return (duration_seconds / _SECONDS_PER_MINUTE) * _USD_PER_MINUTE


def _parse_verbose_response(payload: dict[str, Any]) -> Transcription:
    """Reconstruit une ``Transcription`` à partir du JSON verbose Whisper.

    Args:
        payload: Réponse Whisper au format verbose_json.

    Returns:
        ``Transcription``.
    """
    raw_segments = payload.get("segments") or []
    segments = tuple(
        TranscriptionSegment(
            start_seconds=float(s["start"]),
            end_seconds=float(s["end"]),
            text=str(s["text"]).strip(),
        )
        for s in raw_segments
    )
    detected = Language(str(payload.get("language", "en")))
    duration = float(payload.get("duration", 0.0))
    return Transcription(
        segments=segments,
        detected_language=detected,
        duration_seconds=duration,
    )
