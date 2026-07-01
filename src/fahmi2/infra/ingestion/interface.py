"""Contrat d'ingestion : ``SourceIngestor`` produit une ``Transcription`` à
partir d'une ``InputSource``, quel que soit son type.

Les dépendances communes (workspace, ffmpeg, STT, store d'artefacts) sont
regroupées dans ``IngestionDeps``, construit par la phase 0 à partir du
``PhaseContext``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from fahmi2.domain.enums import Language, SourceKind
from fahmi2.domain.source import InputSource
from fahmi2.infra.audio.ffmpeg_extractor import FFmpegExtractor
from fahmi2.infra.storage.fs_artifacts import FsArtifactStore
from fahmi2.infra.stt.interface import STTProvider, Transcription
from fahmi2.infra.vision.slide_analyzer import SlideAnalyzer


@dataclass(frozen=True)
class IngestionDeps:
    """Dépendances communes injectées aux ingesteurs (issues du ``PhaseContext``).

    Attributes:
        workspace: Dossier de travail du run.
        artifacts: Helper d'écriture atomique d'artefacts.
        stt_provider: Provider STT (vidéo/audio/YouTube).
        ffmpeg: Extracteur ffmpeg.
        slide_analyzer: Analyseur de slides (``None`` = option indisponible —
            pas de clé OpenAI ou aucune source flaggée).
    """

    workspace: Path
    artifacts: FsArtifactStore
    stt_provider: STTProvider
    ffmpeg: FFmpegExtractor
    slide_analyzer: SlideAnalyzer | None = None


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
        analyze_slides: bool = False,
    ) -> Transcription:
        """Transcrit ou extrait le contenu de ``source`` en une ``Transcription``.

        Args:
            source: Source d'entrée à ingérer.
            source_id: Identifiant de la source (nom des artefacts intermédiaires).
            deps: Dépendances injectées (ffmpeg, STT, workspace, artefacts).
            language_hint: Indice de langue pour le STT (``None`` = auto).
            delete_audio_after: Supprime l'audio intermédiaire après usage si ``True``.
            analyze_slides: Analyse les slides de la vidéo et fusionne leur
                contenu dans la transcription (vidéo/YouTube uniquement ;
                requiert ``deps.slide_analyzer``).

        Returns:
            La ``Transcription`` produite.

        Raises:
            Fahmi2Error: Toute erreur d'ingestion (propagée au moteur).
        """
