"""Handler Phase 1 — extraction des termes candidats pour le glossaire.

Lit la transcription brute persistée par la phase 0, appelle le LLM pour
extraire les termes techniques candidats avec définition contextuelle, et
persiste le résultat JSON dans ``workspace/candidates/{source_id}.json``.
"""

from __future__ import annotations

from fahmi2.domain.enums import PhaseId
from fahmi2.domain.phase import PhaseExecution
from fahmi2.domain.source import SourceExecution
from fahmi2.infra.llm.interface import JSON_OBJECT_RESPONSE_FORMAT
from fahmi2.pipeline.handlers._base import (
    build_succeeded_phase,
    invoke_llm,
    language_label,
    load_transcription_text,
    parse_json_response,
    style_label,
    utc_now,
)
from fahmi2.pipeline.phase_handler import PhaseContext, PhaseHandler
from fahmi2.pipeline.workspace_layout import candidates_path

_TEMPLATE_NAME = "phase_1_term_extraction"


class Phase1TermExtractionHandler(PhaseHandler):
    """Phase 1 — extraction des termes candidats par source."""

    @property
    def phase_id(self) -> PhaseId:
        """Identifiant de la phase."""
        return PhaseId.TERM_EXTRACTION

    @property
    def is_per_source(self) -> bool:
        """Phase par source."""
        return True

    def max_parallel_workers(self, ctx: PhaseContext) -> int:
        """Parallélise les sources via le pool LLM configuré."""
        return ctx.settings.parallelism.llm_workers

    def execute(
        self,
        ctx: PhaseContext,
        *,
        source: SourceExecution | None,
    ) -> PhaseExecution:
        """Extrait les termes candidats pour ``source``.

        Args:
            ctx: Contexte d'exécution.
            source: Source à traiter (obligatoire).

        Returns:
            ``PhaseExecution`` ``SUCCEEDED`` pointant vers
            ``candidates/{source_id}.json``.

        Raises:
            ValueError: Si ``source`` est ``None``.
            StorageError: Si la transcription n'est pas présente sur disque.
            LLMError: Si le LLM renvoie un JSON invalide.
        """
        if source is None:
            raise ValueError("Phase1TermExtractionHandler requires a SourceExecution")

        started_at = utc_now()
        transcription_text = load_transcription_text(
            ctx.workspace, source.source_id.value
        )
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
            response_format=JSON_OBJECT_RESPONSE_FORMAT,
        )
        payload = parse_json_response(
            response.content,
            phase_id=self.phase_id,
            finish_reason=response.finish_reason,
        )
        out_path = candidates_path(ctx.workspace, source.source_id.value)
        ctx.artifacts.write_json_atomic(out_path, payload)
        return build_succeeded_phase(
            phase_id=self.phase_id,
            artifact_path=out_path,
            started_at=started_at,
            cost_usd=response.cost_usd,
        )
