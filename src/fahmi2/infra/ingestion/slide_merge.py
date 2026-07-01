"""Fusion des slides analysées dans la transcription horodatée (pur).

Chaque slide non vide devient un ``TranscriptionSegment`` intercalé aux
timestamps de sa plage d'affichage : les phases aval (1..7) voient le contenu
des slides adjacent aux propos oraux qui les commentent, sans modification.
Libellés en français (cohérents avec les prompts FR gelés du pipeline).
"""

from __future__ import annotations

from collections.abc import Sequence

from fahmi2.infra.stt.interface import Transcription, TranscriptionSegment
from fahmi2.infra.vision.interface import AnalyzedSlide

_SECONDS_PER_HOUR = 3600
_SECONDS_PER_MINUTE = 60
_SLIDE_TEMPLATE = "[Slide affichée de {start} à {end}] {body}"
_VISUALS_SEPARATOR = " — Visuels : "
_VISUALS_ONLY_PREFIX = "Visuels : "


def format_timestamp(seconds: float) -> str:
    """Met en forme un horodatage ``mm:ss`` (``h:mm:ss`` au-delà d'une heure).

    Args:
        seconds: Position dans la vidéo (s, bornée à 0).

    Returns:
        L'horodatage lisible.
    """
    total = int(max(0.0, seconds))
    hours, remainder = divmod(total, _SECONDS_PER_HOUR)
    minutes, secs = divmod(remainder, _SECONDS_PER_MINUTE)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def merge_slides_into_transcription(
    transcription: Transcription, slides: Sequence[AnalyzedSlide]
) -> Transcription:
    """Intercale le contenu des slides dans la transcription.

    Args:
        transcription: Transcription audio d'origine.
        slides: Slides analysées (les vides sont ignorées).

    Returns:
        Une nouvelle ``Transcription`` aux segments ordonnés temporellement
        (la transcription d'origine, inchangée, si aucune slide à injecter).
    """
    inserts: list[TranscriptionSegment] = []
    for slide in slides:
        if slide.content.is_empty():
            continue
        text = slide.content.text.strip()
        visuals = slide.content.visuals_description.strip()
        if text and visuals:
            body = f"{text}{_VISUALS_SEPARATOR}{visuals}"
        elif text:
            body = text
        else:
            body = f"{_VISUALS_ONLY_PREFIX}{visuals}"
        inserts.append(
            TranscriptionSegment(
                start_seconds=slide.start_seconds,
                end_seconds=max(slide.end_seconds, slide.start_seconds),
                text=_SLIDE_TEMPLATE.format(
                    start=format_timestamp(slide.start_seconds),
                    end=format_timestamp(slide.end_seconds),
                    body=body,
                ),
            )
        )
    if not inserts:
        return transcription
    merged = sorted(
        [*transcription.segments, *inserts],
        key=lambda segment: (segment.start_seconds, segment.end_seconds),
    )
    return Transcription(
        segments=tuple(merged),
        detected_language=transcription.detected_language,
        duration_seconds=transcription.duration_seconds,
    )
