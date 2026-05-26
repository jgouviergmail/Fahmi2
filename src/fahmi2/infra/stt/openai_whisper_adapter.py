"""Adaptateur ``STTProvider`` qui appelle l'endpoint de transcription OpenAI.

Modèle **configurable** (cf. :class:`fahmi2.domain.enums.CloudSttModel`), défaut
``whisper-1``. ``whisper-1`` renvoie des segments horodatés (``verbose_json``) ;
les modèles ``gpt-4o-*-transcribe`` ne supportent que ``json`` (texte sans
timestamps) — l'adapter produit alors **un segment unique par tranche audio**
(texte + offset/durée fournis par le ``CloudAudioPreparer``), le contenu transcrit
restant identique. Tarifs : cf. ``infra/stt/_pricing``.
"""

from __future__ import annotations

import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from openai import APIError, APIStatusError, AuthenticationError, OpenAI, RateLimitError

from fahmi2.core.errors.exceptions import LLMError, STTError
from fahmi2.core.errors.severity import Severity
from fahmi2.domain.enums import CloudSttModel, Language
from fahmi2.infra.audio.cloud_audio_preparer import AudioChunk, AudioPreparer
from fahmi2.infra.stt._pricing import stt_cost_usd
from fahmi2.infra.stt.interface import (
    ProgressCallback,
    Transcription,
    TranscriptionSegment,
)

_PROVIDER_NAME = "openai-whisper"
_DEFAULT_CLOUD_MODEL = str(CloudSttModel.WHISPER_1)
#: Modèles renvoyant des segments horodatés via ``verbose_json`` (sinon ``json``).
_VERBOSE_JSON_MODELS: frozenset[str] = frozenset({CloudSttModel.WHISPER_1.value})
_RESPONSE_FORMAT_VERBOSE = "verbose_json"
_RESPONSE_FORMAT_JSON = "json"
# OpenAI garde la connexion ouverte sous charge : timeout client large.
_REQUEST_TIMEOUT_SECONDS = 600.0

# OpenAI Whisper (``verbose_json``) renvoie le **nom anglais complet** de la
# langue détectée (ex. ``"french"``), pas le code ISO. On mappe noms ET codes
# vers les langues supportées ; une langue hors périmètre retombe sur l'indice
# de langue fourni (``language_hint``), sinon sur l'anglais.
_WHISPER_LANGUAGE_ALIASES: dict[str, Language] = {
    "french": Language.FR,
    "fr": Language.FR,
    "english": Language.EN,
    "en": Language.EN,
    "german": Language.DE,
    "de": Language.DE,
    "spanish": Language.ES,
    "es": Language.ES,
    "italian": Language.IT,
    "it": Language.IT,
    "chinese": Language.ZH,
    "zh": Language.ZH,
    "arabic": Language.AR,
    "ar": Language.AR,
}
_DEFAULT_DETECTED_LANGUAGE = Language.EN


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

    def __init__(
        self,
        *,
        api_key: str,
        client: OpenAI | None = None,
        preparer: AudioPreparer | None = None,
        model: str = _DEFAULT_CLOUD_MODEL,
        timeout: float = _REQUEST_TIMEOUT_SECONDS,
    ) -> None:
        """Construit l'adaptateur.

        Args:
            api_key: Clé API OpenAI.
            client: Client OpenAI injectable (utile pour les tests).
            preparer: Préparateur d'audio cloud (compression + découpage). En
                production il est **obligatoire** (injecté par le contrôleur) ;
                ``None`` = transcription directe d'un seul fichier (tests).
            model: Modèle de transcription cloud (cf. ``CloudSttModel``).
            timeout: Timeout des requêtes en secondes.
        """
        self._client = client or OpenAI(api_key=api_key, timeout=timeout)
        self._preparer = preparer
        self._model = model

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
            ``Transcription`` recollée à partir des segments préparés.

        Raises:
            STTError: En cas d'erreur API/authentification/rate-limit.
            FFmpegError: Si la préparation audio (compression/découpage) échoue.
        """
        if on_progress is not None:
            on_progress(0.0)
        if self._preparer is None:
            result = self._transcribe_one(
                AudioChunk(path=audio_path, offset_seconds=0.0),
                language_hint=language_hint,
            )
            if on_progress is not None:
                on_progress(1.0)
            return _merge_transcriptions([result], fallback=language_hint)

        with tempfile.TemporaryDirectory(prefix="fahmi2-stt-") as tmp:
            chunks = self._preparer.prepare(audio_path, Path(tmp))
            parts: list[Transcription] = []
            for index, chunk in enumerate(chunks):
                parts.append(
                    self._transcribe_one(chunk, language_hint=language_hint)
                )
                if on_progress is not None:
                    on_progress((index + 1) / len(chunks))
        return _merge_transcriptions(parts, fallback=language_hint)

    def _transcribe_one(
        self,
        chunk: AudioChunk,
        *,
        language_hint: Language | None,
    ) -> Transcription:
        """Transcrit une tranche audio, en absolu (timestamps décalés de l'offset).

        Selon le modèle : ``verbose_json`` (segments horodatés, décalés de
        l'offset) ou ``json`` (texte seul → un segment unique couvrant la tranche).

        Args:
            chunk: Tranche audio (fichier + offset + durée).
            language_hint: Indice de langue.

        Returns:
            ``Transcription`` de la tranche (timestamps absolus).

        Raises:
            STTError: En cas d'erreur API.
        """
        verbose = self._model in _VERBOSE_JSON_MODELS
        try:
            with chunk.path.open("rb") as fp:
                kwargs: dict[str, Any] = {
                    "model": self._model,
                    "file": fp,
                    "response_format": (
                        _RESPONSE_FORMAT_VERBOSE if verbose else _RESPONSE_FORMAT_JSON
                    ),
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
        if not verbose:
            return _single_segment_transcription(
                str(response.text), chunk=chunk, fallback=language_hint
            )
        base = _parse_verbose_response(response.model_dump(), fallback=language_hint)
        return _shift_transcription(base, offset_seconds=chunk.offset_seconds)

    def estimate_cost(self, duration_seconds: float) -> float:
        """Estime le coût en USD pour une durée audio donnée.

        Args:
            duration_seconds: Durée de l'audio (secondes).

        Returns:
            Coût USD (tarif du modèle configuré).
        """
        return stt_cost_usd(model=self._model, duration_seconds=duration_seconds)


def _resolve_language(raw: str, *, fallback: Language | None) -> Language:
    """Résout la langue Whisper (nom complet ou code ISO) vers ``Language``.

    Args:
        raw: Valeur brute du champ ``language`` (ex. ``"french"`` ou ``"fr"``).
        fallback: Langue de repli si ``raw`` n'est pas reconnue (typiquement
            l'indice de langue source) ; ``_DEFAULT_DETECTED_LANGUAGE`` en
            dernier recours.

    Returns:
        La ``Language`` correspondante.
    """
    resolved = _WHISPER_LANGUAGE_ALIASES.get(raw.strip().lower())
    if resolved is not None:
        return resolved
    return fallback if fallback is not None else _DEFAULT_DETECTED_LANGUAGE


def _parse_verbose_response(
    payload: dict[str, Any], *, fallback: Language | None = None
) -> Transcription:
    """Reconstruit une ``Transcription`` à partir du JSON verbose Whisper.

    Args:
        payload: Réponse Whisper au format verbose_json.
        fallback: Langue de repli si la langue détectée est hors du périmètre
            supporté ou absente.

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
    detected = _resolve_language(str(payload.get("language", "")), fallback=fallback)
    duration = float(payload.get("duration", 0.0))
    return Transcription(
        segments=segments,
        detected_language=detected,
        duration_seconds=duration,
    )


def _single_segment_transcription(
    text: str, *, chunk: AudioChunk, fallback: Language | None
) -> Transcription:
    """Construit une transcription à **segment unique** (modèles sans timestamps).

    Args:
        text: Texte transcrit de la tranche.
        chunk: Tranche source (offset + durée → timestamps absolus du segment).
        fallback: Langue de repli (les modèles ``json`` ne renvoient pas la langue).

    Returns:
        ``Transcription`` couvrant ``[offset, offset + durée]``.
    """
    segment = TranscriptionSegment(
        start_seconds=chunk.offset_seconds,
        end_seconds=chunk.offset_seconds + chunk.duration_seconds,
        text=text.strip(),
    )
    return Transcription(
        segments=(segment,),
        detected_language=fallback if fallback is not None else _DEFAULT_DETECTED_LANGUAGE,
        duration_seconds=chunk.duration_seconds,
    )


def _shift_transcription(base: Transcription, *, offset_seconds: float) -> Transcription:
    """Décale tous les timestamps d'une transcription de ``offset_seconds``.

    Args:
        base: Transcription d'une tranche (timestamps relatifs à la tranche).
        offset_seconds: Décalage temporel de la tranche dans l'audio d'origine.

    Returns:
        La transcription aux timestamps absolus (inchangée si offset nul).
    """
    if offset_seconds == 0.0:
        return base
    shifted = tuple(
        TranscriptionSegment(
            start_seconds=s.start_seconds + offset_seconds,
            end_seconds=s.end_seconds + offset_seconds,
            text=s.text,
        )
        for s in base.segments
    )
    return Transcription(
        segments=shifted,
        detected_language=base.detected_language,
        duration_seconds=base.duration_seconds + offset_seconds,
    )


def _merge_transcriptions(
    parts: Sequence[Transcription], *, fallback: Language | None
) -> Transcription:
    """Concatène plusieurs ``Transcription`` (segments déjà décalés).

    Args:
        parts: Transcriptions ordonnées par offset croissant.
        fallback: Langue de repli si ``parts`` est vide.

    Returns:
        Une ``Transcription`` unique (langue du 1er segment, durée = max des fins).
    """
    segments: list[TranscriptionSegment] = []
    for part in parts:
        segments.extend(part.segments)
    detected = parts[0].detected_language if parts else (fallback or Language.EN)
    duration = max((s.end_seconds for s in segments), default=0.0)
    return Transcription(
        segments=tuple(segments),
        detected_language=detected,
        duration_seconds=duration,
    )
