"""ViewModel ``PedagogyProgressViewModel`` — progression supports × langues.

La fonctionnalité pédagogie n'a **pas** d'état SQLite : la progression est
accumulée en mémoire à partir des ``PedagogyEvent``. Le contrôleur appelle
``reset`` au lancement (cellules en attente), puis ``apply_event`` à chaque
événement ; la vue consomme ``cost_matrix_snapshot`` (grille supports × langues)
et ``stats_snapshot`` (tuiles). Testable sans Qt.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime

from fahmi2.domain.enums import Language, PhaseStatus, RunStatus, SupportType
from fahmi2.pedagogy.events import (
    PedagogyEvent,
    SupportFinished,
    SupportGenerationFinished,
    SupportGenerationStarted,
    SupportStarted,
)
from fahmi2.pedagogy.support_registry import SupportGeneratorRegistry
from fahmi2.ui.pedagogy_labels import support_label
from fahmi2.ui.viewmodels.cost_matrix import (
    CostMatrixCell,
    CostMatrixSnapshot,
    build_cost_matrix,
)

#: Statuts pour lesquels le coût d'une cellule est connu (à compter dans les totaux).
_COST_KNOWN_STATUSES = frozenset(
    {PhaseStatus.SUCCEEDED, PhaseStatus.SKIPPED, PhaseStatus.FAILED}
)
#: Statuts considérés comme « tâche terminée » pour le compteur de tuiles.
_DONE_STATUSES = frozenset({PhaseStatus.SUCCEEDED, PhaseStatus.SKIPPED})


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
class PedagogyStatsSnapshot:
    """Indicateurs agrégés pour la bande de tuiles pédagogie.

    Attributes:
        overall_status: Statut global (``None`` tant que non terminé).
        tasks_done: Tâches (support × langue) terminées (succès ou à jour).
        tasks_total: Nombre total de tâches.
        languages: Langues sélectionnées.
        total_cost_usd: Coût total cumulé.
        cost_ceiling_usd: Plafond de coût éventuel (``None`` = sans plafond).
        started_at: Démarrage de la dernière exécution (``None`` si jamais lancée).
        finished_at: Fin de la dernière exécution (``None`` si en cours / jamais).
    """

    overall_status: RunStatus | None
    tasks_done: int
    tasks_total: int
    languages: tuple[Language, ...]
    total_cost_usd: float
    cost_ceiling_usd: float | None
    started_at: datetime | None
    finished_at: datetime | None


class PedagogyProgressViewModel:
    """Accumule les ``PedagogyEvent`` en cellules de progression supports × langues.

    Les cellules sont exposées via ``cost_matrix_snapshot`` (grille) et
    ``stats_snapshot`` (indicateurs agrégés).
    """

    def __init__(self) -> None:
        self._cells: dict[tuple[SupportType, Language], PedagogyProgressCell] = {}
        self._order: list[tuple[SupportType, Language]] = []
        self._overall_status: RunStatus | None = None
        self._supports: tuple[SupportType, ...] = ()
        self._languages: tuple[Language, ...] = ()
        self._cost_ceiling_usd: float | None = None
        self._started_at: datetime | None = None
        self._finished_at: datetime | None = None

    def reset(
        self,
        *,
        supports: tuple[SupportType, ...],
        languages: tuple[Language, ...],
        cost_ceiling_usd: float | None = None,
    ) -> None:
        """(Ré)initialise la grille en cellules « en attente ».

        Les cellules sont ordonnées langue × support (ordre canonique du
        registre).

        Args:
            supports: Supports sélectionnés.
            languages: Langues sélectionnées.
            cost_ceiling_usd: Plafond de coût éventuel (affiché par la tuile Coût).
        """
        self._cells = {}
        self._order = []
        self._overall_status = None
        self._cost_ceiling_usd = cost_ceiling_usd
        self._started_at = None
        self._finished_at = None
        selected = set(supports)
        self._supports = tuple(
            s for s in SupportGeneratorRegistry.canonical_order() if s in selected
        )
        self._languages = languages
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

    def load_persisted(
        self,
        *,
        supports: tuple[SupportType, ...],
        languages: tuple[Language, ...],
        generated_costs: Mapping[tuple[SupportType, Language], float],
        cost_ceiling_usd: float | None = None,
        overall_status: RunStatus | None = None,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
    ) -> None:
        """Charge l'état des supports déjà générés (reconstruction à la sélection).

        Réinitialise la grille puis marque ``SUCCEEDED`` (+ coût) les ``(support,
        langue)`` dont un artefact existe sur disque ; les autres restent en
        attente. Restaure aussi le statut/horodatages de la dernière exécution
        (depuis ``run_state.json``) pour afficher un statut homogène avec la
        génération, sans worker actif.

        Args:
            supports: Supports sélectionnés.
            languages: Langues sélectionnées.
            generated_costs: Coût par ``(support, langue)`` déjà généré.
            cost_ceiling_usd: Plafond de coût éventuel.
            overall_status: Statut de la dernière exécution (``None`` si jamais).
            started_at: Démarrage de la dernière exécution.
            finished_at: Fin de la dernière exécution.
        """
        self.reset(
            supports=supports,
            languages=languages,
            cost_ceiling_usd=cost_ceiling_usd,
        )
        self._overall_status = overall_status
        self._started_at = started_at
        self._finished_at = finished_at
        for (support, language), cost in generated_costs.items():
            if (support, language) in self._cells:
                self._set_cell(
                    support, language, status=PhaseStatus.SUCCEEDED, cost_usd=cost
                )

    def apply_event(self, event: PedagogyEvent) -> None:
        """Met à jour l'état à partir d'un événement pédagogie.

        Args:
            event: Événement reçu.
        """
        if isinstance(event, SupportGenerationStarted):
            self._overall_status = RunStatus.RUNNING
            self._started_at = event.timestamp
            self._finished_at = None
        elif isinstance(event, SupportStarted):
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
            self._finished_at = event.timestamp

    def cost_matrix_snapshot(self) -> CostMatrixSnapshot:
        """Construit la matrice supports × langues (statut + coût par cellule).

        Returns:
            ``CostMatrixSnapshot`` (lignes = supports, colonnes = langues).
        """
        column_labels = tuple(lang.value for lang in self._languages)
        rows = tuple(
            (
                support_label(support),
                tuple(self._matrix_cell(support, lang) for lang in self._languages),
            )
            for support in self._supports
        )
        return build_cost_matrix(
            row_header="Support", column_labels=column_labels, rows=rows
        )

    def _matrix_cell(
        self, support: SupportType, language: Language
    ) -> CostMatrixCell:
        """Convertit la cellule de progression en cellule de matrice.

        Args:
            support: Support (ligne).
            language: Langue (colonne).

        Returns:
            ``CostMatrixCell`` (coût ``None`` tant que la tâche n'a pas de coût
            connu : en attente / en cours).
        """
        cell = self._cells.get((support, language))
        status = cell.status if cell is not None else None
        cost = (
            cell.cost_usd
            if cell is not None and cell.status in _COST_KNOWN_STATUSES
            else None
        )
        return CostMatrixCell(
            status=status or PhaseStatus.PENDING,
            cost_usd=cost,
            tooltip="",
        )

    def stats_snapshot(self) -> PedagogyStatsSnapshot:
        """Construit le snapshot des tuiles pédagogie.

        Returns:
            ``PedagogyStatsSnapshot``.
        """
        done = sum(
            1 for cell in self._cells.values() if cell.status in _DONE_STATUSES
        )
        # Cumul live (cohérent avec le total de la matrice) : somme des coûts des
        # cellules dont le coût est connu, plutôt que le total figé de fin de run.
        total = sum(
            cell.cost_usd
            for cell in self._cells.values()
            if cell.status in _COST_KNOWN_STATUSES
        )
        return PedagogyStatsSnapshot(
            overall_status=self._overall_status,
            tasks_done=done,
            tasks_total=len(self._cells),
            languages=self._languages,
            total_cost_usd=total,
            cost_ceiling_usd=self._cost_ceiling_usd,
            started_at=self._started_at,
            finished_at=self._finished_at,
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
