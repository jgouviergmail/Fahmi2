"""ViewModel ``PedagogyProgressViewModel`` — progression supports × langues.

La fonctionnalité pédagogie n'a **pas** d'état SQLite : la progression est
accumulée en mémoire à partir des ``PedagogyEvent``. Le contrôleur appelle
``reset`` au lancement (cellules en attente), puis ``apply_event`` à chaque
événement ; la vue affiche le ``snapshot``. Testable sans Qt.
"""

from __future__ import annotations

from dataclasses import dataclass

from fahmi2.domain.enums import Language, PhaseStatus, RunStatus, SupportType
from fahmi2.pedagogy.events import (
    PedagogyEvent,
    SupportFinished,
    SupportGenerationFinished,
    SupportStarted,
)
from fahmi2.pedagogy.support_registry import SupportGeneratorRegistry


@dataclass(frozen=True)
class PedagogyProgressCell:
    """Cellule de progression pour un (support, langue).

    Attributes:
        support_type: Type de support.
        language: Langue.
        status: Statut courant (``None`` = en attente).
        cost_usd: Coût LLM accumulé.
    """

    support_type: SupportType
    language: Language
    status: PhaseStatus | None
    cost_usd: float


@dataclass(frozen=True)
class PedagogyProgressSnapshot:
    """Snapshot de progression d'une génération de supports.

    Attributes:
        cells: Cellules ordonnées (langue × support canonique).
        overall_status: Statut global (``None`` tant que non terminé).
        total_cost_usd: Coût total cumulé.
    """

    cells: tuple[PedagogyProgressCell, ...]
    overall_status: RunStatus | None
    total_cost_usd: float


class PedagogyProgressViewModel:
    """Accumule les ``PedagogyEvent`` en un ``PedagogyProgressSnapshot``."""

    def __init__(self) -> None:
        self._cells: dict[tuple[SupportType, Language], PedagogyProgressCell] = {}
        self._order: list[tuple[SupportType, Language]] = []
        self._overall_status: RunStatus | None = None
        self._total_cost_usd: float = 0.0

    def reset(
        self,
        *,
        supports: tuple[SupportType, ...],
        languages: tuple[Language, ...],
    ) -> None:
        """(Ré)initialise la grille en cellules « en attente ».

        Les cellules sont ordonnées langue × support (ordre canonique du
        registre).

        Args:
            supports: Supports sélectionnés.
            languages: Langues sélectionnées.
        """
        self._cells = {}
        self._order = []
        self._overall_status = None
        self._total_cost_usd = 0.0
        selected = set(supports)
        for language in languages:
            for support in SupportGeneratorRegistry.canonical_order():
                if support not in selected:
                    continue
                key = (support, language)
                self._cells[key] = PedagogyProgressCell(
                    support_type=support,
                    language=language,
                    status=None,
                    cost_usd=0.0,
                )
                self._order.append(key)

    def apply_event(self, event: PedagogyEvent) -> None:
        """Met à jour l'état à partir d'un événement pédagogie.

        Args:
            event: Événement reçu.
        """
        if isinstance(event, SupportStarted):
            self._set_status(event.support_type, event.language, PhaseStatus.RUNNING)
        elif isinstance(event, SupportFinished):
            self._set_cell(
                event.support_type,
                event.language,
                status=event.status,
                cost_usd=event.cost_usd,
            )
        elif isinstance(event, SupportGenerationFinished):
            self._overall_status = event.status
            self._total_cost_usd = event.total_cost_usd

    def snapshot(self) -> PedagogyProgressSnapshot:
        """Construit le snapshot courant.

        Returns:
            ``PedagogyProgressSnapshot``.
        """
        return PedagogyProgressSnapshot(
            cells=tuple(self._cells[key] for key in self._order),
            overall_status=self._overall_status,
            total_cost_usd=self._total_cost_usd,
        )

    def _set_status(
        self, support_type: SupportType, language: Language, status: PhaseStatus
    ) -> None:
        """Met à jour le statut d'une cellule (coût inchangé).

        Args:
            support_type: Support.
            language: Langue.
            status: Nouveau statut.
        """
        current = self._cells.get((support_type, language))
        cost = current.cost_usd if current is not None else 0.0
        self._set_cell(support_type, language, status=status, cost_usd=cost)

    def _set_cell(
        self,
        support_type: SupportType,
        language: Language,
        *,
        status: PhaseStatus,
        cost_usd: float,
    ) -> None:
        """Insère/met à jour une cellule (l'ajoute à l'ordre si absente).

        Args:
            support_type: Support.
            language: Langue.
            status: Statut.
            cost_usd: Coût.
        """
        key = (support_type, language)
        if key not in self._cells:
            self._order.append(key)
        self._cells[key] = PedagogyProgressCell(
            support_type=support_type,
            language=language,
            status=status,
            cost_usd=cost_usd,
        )
