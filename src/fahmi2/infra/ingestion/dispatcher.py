"""Aiguillage d'une source vers l'ingesteur adapté à son ``SourceKind``.

Pattern calqué sur ``PhaseRegistry`` : un mapping figé ``SourceKind →
SourceIngestor`` est construit par ``build_default_ingestion_dispatcher`` et
injecté dans le ``PhaseContext``. La phase 0 délègue l'ingestion au dispatcher
sans connaître les types concrets de source.
"""

from __future__ import annotations

from fahmi2.core.errors.exceptions import IngestionError
from fahmi2.core.errors.severity import Severity
from fahmi2.domain.enums import Language, SourceKind
from fahmi2.domain.source import InputSource
from fahmi2.infra.ingestion.document_ingestor import DocumentIngestor
from fahmi2.infra.ingestion.interface import IngestionDeps, SourceIngestor
from fahmi2.infra.ingestion.media_ingestor import MediaIngestor
from fahmi2.infra.ingestion.text_extractor import DefaultTextExtractor
from fahmi2.infra.stt.interface import Transcription


class IngestionDispatcher:
    """Route ``ingest`` vers le ``SourceIngestor`` enregistré pour le ``SourceKind``."""

    def __init__(self, by_kind: dict[SourceKind, SourceIngestor]) -> None:
        """Construit le dispatcher.

        Args:
            by_kind: Mapping ``SourceKind → SourceIngestor``.
        """
        self._by_kind = dict(by_kind)

    def has_ingestor(self, kind: SourceKind) -> bool:
        """Indique si un ingesteur est enregistré pour ``kind``.

        Args:
            kind: Type de source.

        Returns:
            ``True`` si un ingesteur gère ce type.
        """
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

        Args:
            source: Source d'entrée à ingérer.
            source_id: Identifiant de la source.
            deps: Dépendances injectées.
            language_hint: Indice de langue pour le STT (``None`` = auto).
            delete_audio_after: Supprime l'audio intermédiaire après usage.

        Returns:
            La ``Transcription`` produite par l'ingesteur adapté.

        Raises:
            IngestionError: ``INGESTION.UNSUPPORTED_SOURCE`` si aucun ingesteur
                n'est enregistré pour le type de ``source``.
        """
        ingestor = self._by_kind.get(source.kind)
        if ingestor is None:
            raise IngestionError(
                code="INGESTION.UNSUPPORTED_SOURCE",
                user_message=(
                    f"Type de source non pris en charge : {source.kind.value}."
                ),
                severity=Severity.ERROR,
                technical_details={
                    "kind": source.kind.value,
                    "location": source.location,
                },
            )
        return ingestor.ingest(
            source,
            source_id,
            deps,
            language_hint=language_hint,
            delete_audio_after=delete_audio_after,
        )


def build_default_ingestion_dispatcher() -> IngestionDispatcher:
    """Construit le dispatcher par défaut (vidéo + audio + documents).

    Returns:
        Un ``IngestionDispatcher`` avec ``MediaIngestor`` pour ``VIDEO``/``AUDIO``
        et ``DocumentIngestor`` (extracteur par défaut) pour ``DOCUMENT``.
    """
    media = MediaIngestor()
    document = DocumentIngestor(DefaultTextExtractor())
    return IngestionDispatcher(
        {
            SourceKind.VIDEO: media,
            SourceKind.AUDIO: media,
            SourceKind.DOCUMENT: document,
        }
    )
