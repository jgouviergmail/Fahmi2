"""Handler Phase 5 — consolidation finale (dispatcher de stratégies).

Sélectionne la stratégie d'assemblage selon ``settings.consolidation_mode`` :
``ORDERED`` (1 source = 1 chapitre, contenu recopié) ou ``THEMATIC`` (refonte
thématique transversale). La phase reste batch et persiste **un**
``PhaseExecution`` pointant vers ``workspace/consolidated_master.md``.

Détails des stratégies : ``pipeline/handlers/_consolidation/`` (``ordered.py``,
``thematic.py``) ; helpers déterministes partagés dans ``_consolidation/_base.py``.
"""

from __future__ import annotations

from typing import Any

from fahmi2.domain.enums import ConsolidationMode, PhaseId
from fahmi2.domain.phase import PhaseExecution
from fahmi2.domain.source import SourceExecution
from fahmi2.pipeline.handlers._base import build_succeeded_phase, utc_now
from fahmi2.pipeline.handlers._consolidation._base import (
    CONSOLIDATED_MASTER_FILENAME,
    ConsolidationStrategy,
    assemble_document,
    load_all_structured,
    renumber_subheadings,
    strip_existing_numbering,
)
from fahmi2.pipeline.handlers._consolidation.ordered import (
    OrderedConsolidationStrategy,
    build_chapters,
)
from fahmi2.pipeline.handlers._consolidation.thematic import (
    ThematicConsolidationStrategy,
)
from fahmi2.pipeline.phase_handler import PhaseContext, PhaseHandler

_STRATEGIES: dict[ConsolidationMode, type[ConsolidationStrategy]] = {
    ConsolidationMode.ORDERED: OrderedConsolidationStrategy,
    ConsolidationMode.THEMATIC: ThematicConsolidationStrategy,
}


class Phase5ConsolidationHandler(PhaseHandler):
    """Phase 5 — consolidation finale (dispatcher selon ``consolidation_mode``)."""

    @property
    def phase_id(self) -> PhaseId:
        """Identifiant de la phase."""
        return PhaseId.CONSOLIDATION

    @property
    def is_per_source(self) -> bool:
        """Phase batch."""
        return False

    def execute(
        self,
        ctx: PhaseContext,
        *,
        source: SourceExecution | None,
    ) -> PhaseExecution:
        """Consolide le document final via la stratégie du mode courant.

        Args:
            ctx: Contexte d'exécution.
            source: Doit être ``None`` (phase batch).

        Returns:
            ``PhaseExecution`` ``SUCCEEDED`` pointant vers
            ``workspace/consolidated_master.md``.

        Raises:
            ValueError: Si ``source`` est non-None.
            StorageError: Si un fichier structured manque.
            LLMError: Si une réponse LLM est invalide.
        """
        if source is not None:
            raise ValueError(
                "Phase5ConsolidationHandler is batch (source must be None)"
            )
        started_at = utc_now()
        structured_by_source = load_all_structured(ctx.workspace, ctx.run.sources)
        strategy = _STRATEGIES[ctx.settings.consolidation_mode]()
        result = strategy.consolidate(ctx, structured_by_source)
        out_path = ctx.workspace / CONSOLIDATED_MASTER_FILENAME
        ctx.artifacts.write_text_atomic(out_path, result.consolidated_markdown)
        return build_succeeded_phase(
            phase_id=self.phase_id,
            artifact_path=out_path,
            started_at=started_at,
            cost_usd=result.cost_usd,
        )


# --- Compat rétro : symboles déplacés vers _consolidation (tests historiques). ---
# Alias par assignation (attributs de module, pas des ré-exports d'import) pour
# que les tests historiques continuent d'importer ces noms sans modification.
_renumber_subheadings = renumber_subheadings
_strip_existing_numbering = strip_existing_numbering


def _assemble_consolidated(
    meta: dict[str, Any],
    structured_by_source: dict[str, str],
    summaries: list[dict[str, Any]],
) -> str:
    """Shim rétro-compatible de l'ancien ``_assemble_consolidated``.

    Reproduit l'assemblage ORDERED (``build_chapters`` + ``assemble_document``)
    pour que les tests historiques continuent de passer sans modification.

    Args:
        meta: Méta-éléments produits par la consolidation.
        structured_by_source: Documents structurés par source (ordre = chapitres).
        summaries: Résumés (utilisés pour les titres de chapitres).

    Returns:
        Le document Markdown consolidé complet.
    """
    titles_by_source = {
        s.get("source_id", ""): s.get("title", "") for s in summaries
    }
    chapters = build_chapters(structured_by_source, titles_by_source)
    return assemble_document(meta, chapters)
