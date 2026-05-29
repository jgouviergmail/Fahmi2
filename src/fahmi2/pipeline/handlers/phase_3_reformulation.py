"""Handler Phase 3 — reformulation par source (transcription -> texte écrit).

Charge la transcription brute, sélectionne les termes du glossaire master
pertinents (top-K via retriever), appelle le LLM, et persiste le texte
reformulé dans ``workspace/reformulated/{source_id}.md``.
"""

from __future__ import annotations

from fahmi2.domain.enums import PhaseId, SourceKind
from fahmi2.domain.phase import PhaseExecution
from fahmi2.domain.source import SourceExecution
from fahmi2.pipeline.handlers._base import (
    DEFAULT_TOP_K_GLOSSARY,
    build_succeeded_phase,
    invoke_llm,
    language_label,
    load_glossary_master,
    load_transcription_text,
    select_top_glossary_terms,
    style_label,
    utc_now,
)
from fahmi2.pipeline.phase_handler import PhaseContext, PhaseHandler
from fahmi2.pipeline.workspace_layout import reformulated_path

_TEMPLATE_NAME = "phase_3_reformulation"


class Phase3ReformulationHandler(PhaseHandler):
    """Phase 3 — reformulation per video du discours oral en texte écrit."""

    def __init__(self, *, top_k_glossary: int = DEFAULT_TOP_K_GLOSSARY) -> None:
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
        """Reformule la transcription d'une source.

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
        out_path = reformulated_path(ctx.workspace, source.source_id.value)
        if (
            source.source.kind is SourceKind.DOCUMENT
            and not ctx.settings.reformulate_documents
        ):
            # Pass-through : un document déjà rédigé est inséré tel quel (le
            # segment unique de l'ingestion préserve la structure du texte).
            text = load_transcription_text(ctx.workspace, source.source_id.value)
            ctx.artifacts.write_text_atomic(out_path, text)
            return build_succeeded_phase(
                phase_id=self.phase_id,
                artifact_path=out_path,
                started_at=started_at,
                cost_usd=0.0,
            )
        transcription_text = load_transcription_text(
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
