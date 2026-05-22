"""Handler Phase 3 — reformulation par vidéo (transcription -> texte écrit).

Charge la transcription brute, sélectionne les termes du glossaire master
pertinents (top-K via retriever), appelle le LLM, et persiste le texte
reformulé dans ``workspace/reformulated/{source_id}.md``.
"""

from __future__ import annotations

import json
from pathlib import Path

from fahmi2.core.errors.exceptions import StorageError
from fahmi2.core.errors.severity import Severity
from fahmi2.domain.enums import PhaseId, SourceKind
from fahmi2.domain.phase import PhaseExecution
from fahmi2.domain.source import SourceExecution
from fahmi2.pipeline.handlers._base import (
    build_succeeded_phase,
    invoke_llm,
    language_label,
    load_glossary_master,
    select_top_glossary_terms,
    style_label,
    utc_now,
)
from fahmi2.pipeline.phase_handler import PhaseContext, PhaseHandler

_REFORMULATED_SUBDIR = "reformulated"
_TRANSCRIPTS_SUBDIR = "transcripts"
_TEMPLATE_NAME = "phase_3_reformulation"
_DEFAULT_TOP_K_GLOSSARY = 30


class Phase3ReformulationHandler(PhaseHandler):
    """Phase 3 — reformulation per video du discours oral en texte écrit."""

    def __init__(self, *, top_k_glossary: int = _DEFAULT_TOP_K_GLOSSARY) -> None:
        """Construit le handler.

        Args:
            top_k_glossary: Nombre maximal de termes du glossaire à injecter.
        """
        self._top_k_glossary = top_k_glossary

    @property
    def phase_id(self) -> PhaseId:
        """Identifiant de la phase."""
        return PhaseId.REFORMULATION

    @property
    def is_per_source(self) -> bool:
        """Phase par vidéo."""
        return True

    def max_parallel_workers(self, ctx: PhaseContext) -> int:
        """Parallélise les vidéos via le pool LLM configuré."""
        return ctx.settings.parallelism.llm_workers

    def execute(
        self,
        ctx: PhaseContext,
        *,
        source: SourceExecution | None,
    ) -> PhaseExecution:
        """Reformule la transcription d'une vidéo.

        Args:
            ctx: Contexte d'exécution.
            source: Source (obligatoire).

        Returns:
            ``PhaseExecution`` ``SUCCEEDED`` pointant vers
            ``reformulated/{source_id}.md``.

        Raises:
            ValueError: Si ``source`` est ``None``.
            StorageError: Si la transcription est introuvable.
            LLMError: En cas d'échec LLM.
        """
        if source is None:
            raise ValueError("Phase3ReformulationHandler requires a SourceExecution")
        started_at = utc_now()
        out_path = (
            ctx.workspace / _REFORMULATED_SUBDIR / f"{source.source_id.value}.md"
        )
        if (
            source.source.kind is SourceKind.DOCUMENT
            and not ctx.settings.reformulate_documents
        ):
            # Pass-through : un document déjà rédigé est inséré tel quel (le
            # segment unique de l'ingestion préserve la structure du texte).
            text = _load_transcription_text(ctx.workspace, source.source_id.value)
            ctx.artifacts.write_text_atomic(out_path, text)
            return build_succeeded_phase(
                phase_id=self.phase_id,
                artifact_path=out_path,
                started_at=started_at,
                cost_usd=0.0,
            )
        transcription_text = _load_transcription_text(
            ctx.workspace, source.source_id.value
        )
        master_terms = load_glossary_master(ctx.workspace)
        glossary_terms = select_top_glossary_terms(
            master_terms,
            query=transcription_text,
            retriever=ctx.retriever,
            top_k=self._top_k_glossary,
        )
        prompt = ctx.prompts.render(
            _TEMPLATE_NAME,
            output_language_label=language_label(ctx.settings.source_language),
            style_label=style_label(ctx.settings.style_preset),
            style_directives=ctx.settings.style_directives,
            glossary_terms=glossary_terms,
            transcription_text=transcription_text,
        )
        response = invoke_llm(
            ctx, phase_id=self.phase_id, system_prompt=None, user_prompt=prompt
        )
        ctx.artifacts.write_text_atomic(out_path, response.content)
        return build_succeeded_phase(
            phase_id=self.phase_id,
            artifact_path=out_path,
            started_at=started_at,
            cost_usd=response.cost_usd,
        )


def _load_transcription_text(workspace: Path, source_id: str) -> str:
    """Charge le texte complet d'une transcription persistée.

    Args:
        workspace: Dossier de travail.
        source_id: ULID de la vidéo.

    Returns:
        Texte concaténé.

    Raises:
        StorageError: Si le fichier est introuvable.
    """
    transcript_path = workspace / _TRANSCRIPTS_SUBDIR / f"{source_id}.json"
    if not transcript_path.exists():
        raise StorageError(
            code="STORAGE.TRANSCRIPT_MISSING",
            user_message=(
                f"La transcription pour {source_id} est introuvable. "
                "Relance la phase STT."
            ),
            severity=Severity.ERROR,
            technical_details={"path": str(transcript_path)},
        )
    payload = json.loads(transcript_path.read_text(encoding="utf-8"))
    return " ".join(str(s.get("text", "")) for s in payload.get("segments", []))
