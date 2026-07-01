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
#: Langue de repli quand aucun ``language_hint`` n'est fourni. En pratique le
#: hint vaut toujours la langue source du projet (jamais ``None`` dans le flux
#: normal) ; ce défaut n'est qu'un garde-fou pour les appels directs/tests.
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
        analyze_slides: bool = False,
    ) -> Transcription:
        """Extrait le texte de ``source`` en une ``Transcription`` à segment unique.

        Args:
            source: Source document locale.
            source_id: Identifiant de la source (non utilisé : pas d'artefact audio).
            deps: Dépendances injectées (non utilisées : pas de ffmpeg/STT).
            language_hint: Langue du document (= langue source du projet).
            delete_audio_after: Sans effet (pas d'audio).
            analyze_slides: Sans effet (un document n'a pas de slides).

        Returns:
            La ``Transcription`` à segment unique (texte intégral).

        Raises:
            IngestionError: ``INGESTION.EMPTY_DOCUMENT`` si aucun texte exploitable ;
                ``INGESTION.TEXT_EXTRACTION_FAILED`` (via l'extracteur) si illisible.
        """
        # analyze_slides : non pertinent pour un document (ignoré).
        del source_id, deps, delete_audio_after, analyze_slides
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
