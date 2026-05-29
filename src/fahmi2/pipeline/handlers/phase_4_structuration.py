"""Handler Phase 4 — structuration Markdown du contenu reformulé.

Charge le texte reformulé de la phase 3, sélectionne les termes du glossaire
master pertinents, appelle le LLM pour produire un Markdown structuré avec
titres, intro, conclusion et admonitions sémantiques, et persiste le résultat
dans ``workspace/structured/{source_id}.md``.
"""

from __future__ import annotations

from fahmi2.domain.enums import PhaseId
from fahmi2.domain.phase import PhaseExecution
from fahmi2.domain.source import SourceExecution
from fahmi2.pipeline.handlers._base import (
    DEFAULT_TOP_K_GLOSSARY,
    build_succeeded_phase,
    invoke_llm,
    language_label,
    load_glossary_master,
    load_reformulated_text,
    select_top_glossary_terms,
    style_label,
    utc_now,
)
from fahmi2.pipeline.phase_handler import PhaseContext, PhaseHandler
from fahmi2.pipeline.workspace_layout import structured_path

_TEMPLATE_NAME = "phase_4_structuration"


class Phase4StructurationHandler(PhaseHandler):
    """Phase 4 — structuration Markdown du contenu reformulé per video."""

    def __init__(self, *, top_k_glossary: int = DEFAULT_TOP_K_GLOSSARY) -> None:
        """Construit le handler.

        Args:
            top_k_glossary: Nombre maximal de termes du glossaire à injecter.
        """
        self._top_k_glossary = top_k_glossary

    @property
    def phase_id(self) -> PhaseId:
        """Identifiant de la phase."""
        return PhaseId.STRUCTURATION

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
        """Structure le contenu reformulé d'une source en Markdown.

        Args:
            ctx: Contexte d'exécution.
            source: Source (obligatoire).

        Returns:
            ``PhaseExecution`` ``SUCCEEDED`` pointant vers
            ``structured/{source_id}.md``.

        Raises:
            ValueError: Si ``source`` est ``None``.
            StorageError: Si le contenu reformulé est introuvable.
            LLMError: En cas d'échec LLM.
        """
        if source is None:
            raise ValueError("Phase4StructurationHandler requires a SourceExecution")
        started_at = utc_now()
        reformulated_text = load_reformulated_text(
            ctx.workspace, source.source_id.value
        )
        master_terms = load_glossary_master(ctx.workspace)
        glossary_terms = select_top_glossary_terms(
            master_terms,
            query=reformulated_text,
            retriever=ctx.retriever,
            top_k=self._top_k_glossary,
        )
        prompt = ctx.prompts.render(
            _TEMPLATE_NAME,
            output_language_label=language_label(ctx.settings.source_language),
            style_label=style_label(ctx.settings.style_preset),
            style_directives=ctx.settings.style_directives,
            glossary_terms=glossary_terms,
            reformulated_text=reformulated_text,
        )
        response = invoke_llm(
            ctx, phase_id=self.phase_id, system_prompt=None, user_prompt=prompt
        )
        out_path = structured_path(ctx.workspace, source.source_id.value)
        ctx.artifacts.write_text_atomic(out_path, response.content)
        return build_succeeded_phase(
            phase_id=self.phase_id,
            artifact_path=out_path,
            started_at=started_at,
            cost_usd=response.cost_usd,
        )
