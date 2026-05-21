"""Handler Phase 1 — extraction des termes candidats pour le glossaire.

Lit la transcription brute persistée par la phase 0, appelle le LLM pour
extraire les termes techniques candidats avec définition contextuelle, et
persiste le résultat JSON dans ``workspace/candidates/{video_id}.json``.
"""

from __future__ import annotations

import json
from pathlib import Path

from fahmi2.core.errors.exceptions import StorageError
from fahmi2.core.errors.severity import Severity
from fahmi2.domain.enums import PhaseId
from fahmi2.domain.phase import PhaseExecution
from fahmi2.domain.video import VideoExecution
from fahmi2.pipeline.handlers._base import (
    build_succeeded_phase,
    invoke_llm,
    language_label,
    parse_json_response,
    style_label,
    utc_now,
)
from fahmi2.pipeline.phase_handler import PhaseContext, PhaseHandler

_CANDIDATES_SUBDIR = "candidates"
_TRANSCRIPTS_SUBDIR = "transcripts"
_TEMPLATE_NAME = "phase_1_term_extraction"


class Phase1TermExtractionHandler(PhaseHandler):
    """Phase 1 — extraction des termes candidats par vidéo."""

    @property
    def phase_id(self) -> PhaseId:
        """Identifiant de la phase."""
        return PhaseId.TERM_EXTRACTION

    @property
    def is_per_video(self) -> bool:
        """Phase par vidéo."""
        return True

    def max_parallel_workers(self, ctx: PhaseContext) -> int:
        """Parallélise les vidéos via le pool LLM configuré."""
        return ctx.settings.parallelism.llm_workers

    def execute(
        self,
        ctx: PhaseContext,
        *,
        video: VideoExecution | None,
    ) -> PhaseExecution:
        """Extrait les termes candidats pour ``video``.

        Args:
            ctx: Contexte d'exécution.
            video: Vidéo à traiter (obligatoire).

        Returns:
            ``PhaseExecution`` ``SUCCEEDED`` pointant vers ``candidates/{vid}.json``.

        Raises:
            ValueError: Si ``video`` est ``None``.
            StorageError: Si la transcription n'est pas présente sur disque.
            LLMError: Si le LLM renvoie un JSON invalide.
        """
        if video is None:
            raise ValueError("Phase1TermExtractionHandler requires a VideoExecution")

        started_at = utc_now()
        transcription_text = _load_transcription_text(ctx.workspace, video.video_id.value)
        prompt = ctx.prompts.render(
            _TEMPLATE_NAME,
            source_language_label=language_label(ctx.settings.source_language),
            style_label=style_label(ctx.settings.style_preset),
            style_directives=ctx.settings.style_directives,
            transcription_text=transcription_text,
        )
        response = invoke_llm(
            ctx,
            phase_id=self.phase_id,
            system_prompt=None,
            user_prompt=prompt,
        )
        payload = parse_json_response(response.content, phase_id=self.phase_id)
        candidates_path = (
            ctx.workspace / _CANDIDATES_SUBDIR / f"{video.video_id.value}.json"
        )
        ctx.artifacts.write_json_atomic(candidates_path, payload)
        return build_succeeded_phase(
            phase_id=self.phase_id,
            artifact_path=candidates_path,
            started_at=started_at,
            cost_usd=response.cost_usd,
        )


def _load_transcription_text(workspace: Path, video_id: str) -> str:
    """Charge le texte complet d'une transcription persistée.

    Args:
        workspace: Dossier de travail du run.
        video_id: Identifiant ULID de la vidéo.

    Returns:
        Texte concaténé de tous les segments.

    Raises:
        StorageError: Si le fichier n'existe pas ou est invalide.
    """
    transcript_path = workspace / _TRANSCRIPTS_SUBDIR / f"{video_id}.json"
    if not transcript_path.exists():
        raise StorageError(
            code="STORAGE.TRANSCRIPT_MISSING",
            user_message=(
                f"La transcription pour {video_id} est introuvable. "
                "Relance la phase STT."
            ),
            severity=Severity.ERROR,
            technical_details={"path": str(transcript_path)},
        )
    payload = json.loads(transcript_path.read_text(encoding="utf-8"))
    segments = payload.get("segments", [])
    return " ".join(str(s.get("text", "")) for s in segments)
