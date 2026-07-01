"""Tests de la fusion des slides dans la transcription horodatée."""

from fahmi2.domain.enums import Language
from fahmi2.infra.ingestion.slide_merge import (
    format_timestamp,
    merge_slides_into_transcription,
)
from fahmi2.infra.stt.interface import Transcription, TranscriptionSegment
from fahmi2.infra.vision.interface import AnalyzedSlide, SlideContent


def _transcription() -> Transcription:
    return Transcription(
        segments=(
            TranscriptionSegment(0.0, 10.0, "Bonjour à tous."),
            TranscriptionSegment(10.0, 20.0, "Passons au premier point."),
            TranscriptionSegment(20.0, 30.0, "Voici le second point."),
        ),
        detected_language=Language.FR,
        duration_seconds=30.0,
    )


def test_format_timestamp() -> None:
    assert format_timestamp(0.0) == "00:00"
    assert format_timestamp(754.0) == "12:34"
    assert format_timestamp(3725.0) == "1:02:05"


def test_fusion_intercale_aux_bons_timestamps() -> None:
    slides = [
        AnalyzedSlide(10.0, 20.0, SlideContent("Plan du cours", "Un sommaire")),
    ]
    merged = merge_slides_into_transcription(_transcription(), slides)
    texts = [s.text for s in merged.segments]
    assert len(merged.segments) == 4
    slide_index = next(i for i, t in enumerate(texts) if t.startswith("[Slide"))
    assert texts[slide_index] == (
        "[Slide affichée de 00:10 à 00:20] Plan du cours — Visuels : Un sommaire"
    )
    # ordre temporel préservé
    starts = [s.start_seconds for s in merged.segments]
    assert starts == sorted(starts)
    # métadonnées inchangées
    assert merged.detected_language is Language.FR
    assert merged.duration_seconds == 30.0


def test_slide_vide_non_injectee() -> None:
    slides = [AnalyzedSlide(10.0, 20.0, SlideContent("", "  "))]
    merged = merge_slides_into_transcription(_transcription(), slides)
    assert len(merged.segments) == 3


def test_slide_sans_texte_avec_visuels() -> None:
    slides = [AnalyzedSlide(0.0, 10.0, SlideContent("", "Un diagramme de flux"))]
    merged = merge_slides_into_transcription(_transcription(), slides)
    slide_seg = next(s for s in merged.segments if s.text.startswith("[Slide"))
    assert slide_seg.text == (
        "[Slide affichée de 00:00 à 00:10] Visuels : Un diagramme de flux"
    )


def test_aucune_slide_transcription_inchangee() -> None:
    original = _transcription()
    assert merge_slides_into_transcription(original, []) is original
