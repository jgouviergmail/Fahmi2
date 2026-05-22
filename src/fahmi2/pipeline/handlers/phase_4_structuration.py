"""Handler Phase 4 — structuration Markdown du contenu reformulé.

Charge le texte reformulé de la phase 3, sélectionne les termes du glossaire
master pertinents, appelle le LLM pour produire un Markdown structuré avec
titres, intro, conclusion et admonitions sémantiques, et persiste le résultat
dans ``workspace/structured/{source_id}.md``.
"""

from __future__ import annotations

from pathlib import Path

from fahmi2.core.errors.exceptions import StorageError
from fahmi2.core.errors.severity import Severity
from fahmi2.domain.enums import PhaseId
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
_STRUCTURED_SUBDIR = "structured"
_TEMPLATE_NAME = "phase_4_structuration"
_DEFAULT_TOP_K_GLOSSARY = 30


class Phase4StructurationHandler(PhaseHandler):
    """Phase 4 — structuration Markdown du contenu reformulé per video."""

    def __init__(self, *, top_k_glossary: int = _DEFAULT_TOP_K_GLOSSARY) -> None:
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
        source: SourceExecution | None,
    ) -> PhaseExecution:
        """Structure le contenu reformulé d'une vidéo en Markdown.

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
        reformulated_text = _load_reformulated(ctx.workspace, source.source_id.value)
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
        out_path = ctx.workspace / _STRUCTURED_SUBDIR / f"{source.source_id.value}.md"
        ctx.artifacts.write_text_atomic(out_path, response.content)
        return build_succeeded_phase(
            phase_id=self.phase_id,
            artifact_path=out_path,
            started_at=started_at,
            cost_usd=response.cost_usd,
        )


def _load_reformulated(workspace: Path, source_id: str) -> str:
    """Charge le contenu reformulé d'une vidéo.

    Args:
        workspace: Dossier de travail.
        source_id: ULID de la vidéo.

    Returns:
        Le contenu reformulé sous forme de chaîne.

    Raises:
        StorageError: Si le fichier est introuvable.
    """
    path = workspace / _REFORMULATED_SUBDIR / f"{source_id}.md"
    if not path.exists():
        raise StorageError(
            code="STORAGE.REFORMULATED_MISSING",
            user_message=(
                f"Le contenu reformulé pour {source_id} est introuvable. "
                "Relance la phase de reformulation."
            ),
            severity=Severity.ERROR,
            technical_details={"path": str(path)},
        )
    return path.read_text(encoding="utf-8")
