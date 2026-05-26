"""Stub provisoire de la stratégie THEMATIC — implémentée au Lot 4."""

from __future__ import annotations

from fahmi2.pipeline.handlers._consolidation._base import (
    ConsolidationResult,
    ConsolidationStrategy,
)
from fahmi2.pipeline.phase_handler import PhaseContext


class ThematicConsolidationStrategy(ConsolidationStrategy):
    """Refonte thématique transversale (implémentée au Lot 4)."""

    def consolidate(
        self, ctx: PhaseContext, structured_by_source: dict[str, str]
    ) -> ConsolidationResult:
        """Non implémenté tant que le Lot 4 n'est pas réalisé.

        Args:
            ctx: Contexte d'exécution.
            structured_by_source: Markdown structuré par ``source_id``.

        Raises:
            NotImplementedError: Toujours (stub).
        """
        raise NotImplementedError("ThematicConsolidationStrategy: Lot 4")
