"""Handler de la phase 0 : ingestion d'une source → transcription JSON.

Le handler délègue à l'``IngestionDispatcher`` (injecté dans le ``PhaseContext``),
qui choisit l'ingesteur adapté au type de source (vidéo/audio via ffmpeg + STT,
document via extraction de texte, lien YouTube via téléchargement puis STT) et
renvoie une ``Transcription``. Le
handler persiste cette transcription en JSON dans
``workspace/transcripts/{source_id}.json`` et calcule le coût STT à partir de la
durée transcrite.

Le handler ne gère pas le retry / le checkpoint : ces logiques sont au niveau
du ``PipelineEngine``.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fahmi2.domain.enums import PhaseId, PhaseStatus, SttProvider
from fahmi2.domain.phase import PhaseExecution
from fahmi2.domain.source import SourceExecution
from fahmi2.infra.ingestion.interface import IngestionDeps
from fahmi2.infra.stt.interface import Transcription
from fahmi2.pipeline.phase_handler import PhaseContext, PhaseHandler

_TRANSCRIPTS_SUBDIR = "transcripts"
_TRANSCRIPT_EXTENSION = ".json"


class Phase0SttHandler(PhaseHandler):
    """Phase 0 — ingestion d'une source en transcription."""

    @property
    def phase_id(self) -> PhaseId:
        """Identifiant de la phase."""
        return PhaseId.STT

    @property
    def is_per_source(self) -> bool:
        """Phase par source."""
        return True

    def max_parallel_workers(self, ctx: PhaseContext) -> int:
        """STT cloud : pool ``stt_cloud_workers`` ; STT local : 1 (GPU unique)."""
        if ctx.settings.stt_provider is SttProvider.OPENAI_CLOUD:
            return ctx.settings.parallelism.stt_cloud_workers
        return 1

    def execute(
        self,
        ctx: PhaseContext,
        *,
        source: SourceExecution | None,
    ) -> PhaseExecution:
        """Ingère une source et produit sa transcription JSON.

        Args:
            ctx: Contexte d'exécution.
            source: Source à ingérer (obligatoire, la phase est per-source).

        Returns:
            ``PhaseExecution`` avec ``status=SUCCEEDED`` et ``artifact_path``
            pointant vers la transcription JSON.

        Raises:
            ValueError: Si ``source`` est ``None``.
            Fahmi2Error: Toute erreur des sous-systèmes (ingestion, ffmpeg, STT)
                est propagée pour permettre au moteur d'appliquer la retry policy.
        """
        if source is None:
            raise ValueError("Phase0SttHandler requires a SourceExecution")

        started = datetime.now(tz=UTC)
        transcript_path = (
            ctx.workspace
            / _TRANSCRIPTS_SUBDIR
            / f"{source.source_id.value}{_TRANSCRIPT_EXTENSION}"
        )
        deps = IngestionDeps(
            workspace=ctx.workspace,
            artifacts=ctx.artifacts,
            stt_provider=ctx.stt_provider,
            ffmpeg=ctx.ffmpeg,
        )
        transcription = ctx.ingestion.ingest(
            source.source,
            source.source_id.value,
            deps,
            language_hint=ctx.settings.source_language,
            delete_audio_after=ctx.settings.delete_audio_after_stt,
        )
        cost = ctx.stt_provider.estimate_cost(transcription.duration_seconds)
        ctx.artifacts.write_json_atomic(
            transcript_path,
            _serialize_transcription(transcription),
        )

        finished = datetime.now(tz=UTC)
        return PhaseExecution(
            phase_id=PhaseId.STT,
            status=PhaseStatus.SUCCEEDED,
            started_at=started,
            finished_at=finished,
            artifact_path=transcript_path,
            cost_usd=cost,
        )


def _serialize_transcription(transcription: Transcription) -> dict[str, object]:
    """Sérialise une ``Transcription`` au format dict JSON-friendly.

    Args:
        transcription: Résultat de l'ingestion.

    Returns:
        Représentation dict.
    """
    return {
        "detected_language": str(transcription.detected_language),
        "duration_seconds": transcription.duration_seconds,
        "segments": [
            {
                "start_seconds": s.start_seconds,
                "end_seconds": s.end_seconds,
                "text": s.text,
            }
            for s in transcription.segments
        ],
    }
