"""Registre des handlers de phase indexés par ``PhaseId``.

Permet au moteur ``PipelineEngine`` de découvrir dynamiquement les handlers
disponibles dans l'ordre canonique du pipeline.
"""

from __future__ import annotations

from collections.abc import Iterable

from fahmi2.domain.enums import PhaseId
from fahmi2.pipeline.phase_handler import PhaseHandler

_PIPELINE_ORDER: tuple[PhaseId, ...] = (
    PhaseId.STT,
    PhaseId.TERM_EXTRACTION,
    PhaseId.GLOSSARY_RECONCILIATION,
    PhaseId.REFORMULATION,
    PhaseId.STRUCTURATION,
    PhaseId.CONSOLIDATION,
    PhaseId.TRANSLATION,
    PhaseId.COHERENCE,
)


class PhaseRegistry:
    """Enregistre et retrouve les handlers de phase."""

    def __init__(self, handlers: Iterable[PhaseHandler] = ()) -> None:
        """Construit le registre.

        Args:
            handlers: Handlers à enregistrer initialement.

        Raises:
            ValueError: Si deux handlers déclarent le même ``phase_id``.
        """
        self._by_phase: dict[PhaseId, PhaseHandler] = {}
        for handler in handlers:
            self.register(handler)

    def register(self, handler: PhaseHandler) -> None:
        """Enregistre un handler (écrase un éventuel handler précédent).

        Args:
            handler: Handler à enregistrer.

        Raises:
            ValueError: Si ``phase_id`` est déjà enregistré.
        """
        if handler.phase_id in self._by_phase:
            raise ValueError(
                f"Handler already registered for phase {handler.phase_id}"
            )
        self._by_phase[handler.phase_id] = handler

    def get(self, phase_id: PhaseId) -> PhaseHandler:
        """Retourne le handler pour une phase, ou lève ``KeyError``.

        Args:
            phase_id: Phase.

        Returns:
            Handler enregistré.

        Raises:
            KeyError: Si aucun handler n'est enregistré pour cette phase.
        """
        try:
            return self._by_phase[phase_id]
        except KeyError as exc:
            raise KeyError(f"No handler registered for phase {phase_id}") from exc

    def has(self, phase_id: PhaseId) -> bool:
        """Indique si un handler est enregistré pour la phase.

        Args:
            phase_id: Phase.

        Returns:
            ``True`` si présent.
        """
        return phase_id in self._by_phase

    def ordered_handlers(self) -> list[PhaseHandler]:
        """Retourne les handlers dans l'ordre canonique du pipeline.

        Les phases sans handler enregistré sont omises.

        Returns:
            Liste ordonnée des handlers présents.
        """
        return [
            self._by_phase[pid] for pid in _PIPELINE_ORDER if pid in self._by_phase
        ]

    @staticmethod
    def canonical_order() -> tuple[PhaseId, ...]:
        """Retourne l'ordre canonique des phases du pipeline.

        Returns:
            Tuple immuable des ``PhaseId`` dans l'ordre attendu.
        """
        return _PIPELINE_ORDER
