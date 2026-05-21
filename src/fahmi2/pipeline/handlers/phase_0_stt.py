"""Handler de la phase 0 : extraction audio + transcription STT.

Pour chaque vidéo, le handler :

1. Extrait l'audio (WAV 16 kHz mono) via ``FFmpegExtractor`` dans
   ``workspace/audio/{video_id}.wav``.
2. Transcrit l'audio via le ``STTProvider`` configuré.
3. Persiste la transcription JSON dans ``workspace/transcripts/{video_id}.json``.
4. Si ``settings.delete_audio_after_stt`` est ``True``, supprime le WAV.

Le handler ne gère pas le retry / le checkpoint : ces logiques sont au niveau
du ``PipelineEngine``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from fahmi2.core.errors.exceptions import Fahmi2Error
from fahmi2.domain.enums import PhaseId, PhaseStatus, SttProvider
from fahmi2.domain.phase import PhaseExecution
from fahmi2.domain.video import VideoExecution
from fahmi2.infra.stt.interface import Transcription
from fahmi2.pipeline.phase_handler import PhaseContext, PhaseHandler

_AUDIO_SUBDIR = "audio"
_TRANSCRIPTS_SUBDIR = "transcripts"
_AUDIO_EXTENSION = ".wav"
_TRANSCRIPT_EXTENSION = ".json"


class Phase0SttHandler(PhaseHandler):
    """Phase 0 — extraction audio + transcription STT."""

    @property
    def phase_id(self) -> PhaseId:
        """Identifiant de la phase."""
        return PhaseId.STT

    @property
    def is_per_video(self) -> bool:
        """Phase par vidéo."""
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
        video: VideoExecution | None,
    ) -> PhaseExecution:
        """Extrait l'audio et produit la transcription pour une vidéo.

        Args:
            ctx: Contexte d'exécution.
            video: Vidéo à transcrire (obligatoire, la phase est per-video).

        Returns:
            ``PhaseExecution`` avec ``status=SUCCEEDED`` et ``artifact_path``
            pointant vers la transcription JSON.

        Raises:
            ValueError: Si ``video`` est ``None``.
            Fahmi2Error: Toute erreur des sous-systèmes (ffmpeg, STT) est
                propagée pour permettre au moteur d'appliquer la retry policy.
        """
        if video is None:
            raise ValueError("Phase0SttHandler requires a VideoExecution")

        started = datetime.now(tz=UTC)
        audio_path = ctx.workspace / _AUDIO_SUBDIR / f"{video.video_id.value}{_AUDIO_EXTENSION}"
        transcript_path = (
            ctx.workspace
            / _TRANSCRIPTS_SUBDIR
            / f"{video.video_id.value}{_TRANSCRIPT_EXTENSION}"
        )

        try:
            audio_info = ctx.ffmpeg.extract(video.source_path, audio_path)
            transcription = ctx.stt_provider.transcribe(
                audio_path,
                language_hint=ctx.settings.source_language,
            )
            cost = ctx.stt_provider.estimate_cost(audio_info.duration_seconds)
            ctx.artifacts.write_json_atomic(
                transcript_path,
                _serialize_transcription(transcription),
            )
        except Fahmi2Error:
            raise
        finally:
            if ctx.settings.delete_audio_after_stt:
                _safe_delete(audio_path)

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
        transcription: Résultat STT.

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


def _safe_delete(path: Path) -> None:
    """Supprime ``path`` si présent, sans lever en cas d'échec.

    Args:
        path: Fichier à supprimer.
    """
    if path.exists():
        try:
            path.unlink()
        except OSError:
            pass
