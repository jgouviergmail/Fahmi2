"""ViewModel ``VisualsProgressViewModel`` — progression livrables × langues.

La fonctionnalité Visualisations n'a **pas** d'état SQLite : la progression est
accumulée en mémoire à partir des ``VisualsEvent``. Le contrôleur appelle ``reset`` au
lancement (cellules en attente), puis ``apply_event`` à chaque événement ; la vue
consomme ``cost_matrix_snapshot`` (grille livrables × langues, statut uniquement) et
``stats_snapshot`` (tuiles).

L'orchestrateur émet un coût **par langue** (localisation) et un coût **total**
faisant foi sur l'événement de fin (incluant l'extraction de structure, non rattachée à
une langue). Les cellules de la matrice ne portent donc **pas** de coût ; le total est
porté par les tuiles (somme live des coûts par langue, puis total faisant foi à la fin).
Testable sans Qt.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

from PySide6.QtCore import QCoreApplication

from fahmi2.domain.enums import Language, PhaseStatus, RunStatus
from fahmi2.ui.viewmodels.cost_matrix import (
    CostMatrixCell,
    CostMatrixSnapshot,
    build_cost_matrix,
)
from fahmi2.ui.visuals_labels import (
    VisualsDeliverable,
    deliverable_label,
    structure_step_label,
)
from fahmi2.visuals.events import (
    VisualsEvent,
    VisualsGenerationFinished,
    VisualsGenerationStarted,
    VisualsLanguageFinished,
    VisualsLanguageStarted,
    VisualsStructureFinished,
    VisualsStructureProgress,
    VisualsStructureStarted,
    VisualsStructureStep,
)

#: Statuts considérés comme « langue terminée » pour le compteur de tuiles.
_DONE_STATUSES = frozenset({PhaseStatus.SUCCEEDED, PhaseStatus.SKIPPED})

#: En-tête de la colonne des libellés de lignes (livrables) de la matrice.
_ROW_HEADER = "Livrable"

#: Étape de structure → livrable dont elle alimente la colonne « Structure ».
_STEP_TO_DELIVERABLE: dict[VisualsStructureStep, VisualsDeliverable] = {
    VisualsStructureStep.GRAPH: VisualsDeliverable.KNOWLEDGE_MAP,
    VisualsStructureStep.COMMUNITY_REPORTS: VisualsDeliverable.KNOWLEDGE_MAP,
    VisualsStructureStep.IDEA_CHAINS: VisualsDeliverable.KNOWLEDGE_MAP,
    VisualsStructureStep.DIAGRAMS: VisualsDeliverable.DIAGRAMS,
}


def _structure_column_label() -> str:
    """Libellé traduit de la colonne « Structure » (extraction commune)."""
    return QCoreApplication.translate("VisualsProgress", "Structure")


@dataclass(frozen=True)
class VisualsStatsSnapshot:
    """Indicateurs agrégés pour la bande de tuiles Visualisations.

    Attributes:
        overall_status: Statut global (``None`` tant que non terminé).
        languages_done: Langues totalement produites (succès ou à jour).
        languages_total: Nombre total de langues.
        languages: Langues latines traitées.
        total_cost_usd: Coût total cumulé (live, puis faisant foi à la fin).
        cost_ceiling_usd: Plafond de coût éventuel (``None`` = sans plafond).
        started_at: Démarrage de la dernière exécution (``None`` si jamais lancée).
        finished_at: Fin de la dernière exécution (``None`` si en cours / jamais).
    """

    overall_status: RunStatus | None
    languages_done: int
    languages_total: int
    languages: tuple[Language, ...]
    total_cost_usd: float
    cost_ceiling_usd: float | None
    started_at: datetime | None
    finished_at: datetime | None


class VisualsProgressViewModel:
    """Accumule les ``VisualsEvent`` en progression livrables × langues.

    Exposée via ``cost_matrix_snapshot`` (grille de statuts) et ``stats_snapshot``
    (indicateurs agrégés).
    """

    def __init__(self) -> None:
        self._status: dict[Language, PhaseStatus | None] = {}
        self._deliverables: tuple[VisualsDeliverable, ...] = ()
        self._languages: tuple[Language, ...] = ()
        self._overall_status: RunStatus | None = None
        self._cost_ceiling_usd: float | None = None
        self._total_cost_usd: float = 0.0
        self._started_at: datetime | None = None
        self._finished_at: datetime | None = None
        # Phase de structure (commune, avant les langues) : statut + détail par livrable.
        self._structure_status: dict[VisualsDeliverable, PhaseStatus | None] = {}
        self._structure_detail: dict[VisualsDeliverable, str] = {}

    def reset(
        self,
        *,
        deliverables: tuple[VisualsDeliverable, ...],
        languages: tuple[Language, ...],
        cost_ceiling_usd: float | None = None,
    ) -> None:
        """(Ré)initialise la grille en cellules « en attente ».

        Args:
            deliverables: Livrables activés (lignes, dans l'ordre d'affichage).
            languages: Langues latines à produire (colonnes).
            cost_ceiling_usd: Plafond de coût éventuel (affiché par la tuile Coût).
        """
        self._deliverables = deliverables
        self._languages = languages
        self._status = {language: None for language in languages}
        self._overall_status = None
        self._cost_ceiling_usd = cost_ceiling_usd
        self._total_cost_usd = 0.0
        self._started_at = None
        self._finished_at = None
        self._structure_status = {deliverable: None for deliverable in deliverables}
        self._structure_detail = {}

    def load_persisted(
        self,
        *,
        deliverables: tuple[VisualsDeliverable, ...],
        languages: tuple[Language, ...],
        generated_languages: Iterable[Language],
        total_cost_usd: float = 0.0,
        cost_ceiling_usd: float | None = None,
        overall_status: RunStatus | None = None,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
    ) -> None:
        """Charge l'état persisté (reconstruction à la sélection du projet).

        Réinitialise la grille puis marque ``SUCCEEDED`` les langues dont les livrables
        existent sur disque ; les autres restent en attente. Restaure aussi le statut /
        horodatages / coût de la dernière exécution (depuis ``run_state.json``).

        Args:
            deliverables: Livrables activés (lignes).
            languages: Langues latines disponibles (colonnes).
            generated_languages: Langues dont les livrables existent déjà.
            total_cost_usd: Coût total de la dernière exécution.
            cost_ceiling_usd: Plafond de coût éventuel.
            overall_status: Statut de la dernière exécution (``None`` si jamais).
            started_at: Démarrage de la dernière exécution.
            finished_at: Fin de la dernière exécution.
        """
        self.reset(
            deliverables=deliverables,
            languages=languages,
            cost_ceiling_usd=cost_ceiling_usd,
        )
        self._overall_status = overall_status
        self._total_cost_usd = total_cost_usd
        self._started_at = started_at
        self._finished_at = finished_at
        generated = list(generated_languages)
        for language in generated:
            if language in self._status:
                self._status[language] = PhaseStatus.SUCCEEDED
        # Des livrables présents impliquent que la structure a été extraite : les
        # cellules « Structure » sont donc à jour (SUCCEEDED).
        if generated:
            for deliverable in self._deliverables:
                self._structure_status[deliverable] = PhaseStatus.SUCCEEDED

    def apply_event(self, event: VisualsEvent) -> None:
        """Met à jour l'état à partir d'un événement Visualisations.

        Args:
            event: Événement reçu.
        """
        if isinstance(event, VisualsGenerationStarted):
            self._overall_status = RunStatus.RUNNING
            self._started_at = event.timestamp
            self._finished_at = None
            self._total_cost_usd = 0.0
        elif isinstance(
            event,
            VisualsStructureStarted | VisualsStructureProgress | VisualsStructureFinished,
        ):
            self._apply_structure_event(event)
        elif isinstance(event, VisualsLanguageStarted):
            self._status[event.language] = PhaseStatus.RUNNING
        elif isinstance(event, VisualsLanguageFinished):
            self._status[event.language] = event.status
            self._total_cost_usd += event.cost_usd
        elif isinstance(event, VisualsGenerationFinished):
            self._overall_status = event.status
            self._finished_at = event.timestamp
            self._total_cost_usd = event.total_cost_usd

    def _apply_structure_event(
        self,
        event: VisualsStructureStarted
        | VisualsStructureProgress
        | VisualsStructureFinished,
    ) -> None:
        """Met à jour les cellules « Structure » à partir d'un évènement de structure.

        Args:
            event: Évènement de structure (début / progression / fin).
        """
        if isinstance(event, VisualsStructureStarted):
            for deliverable in self._deliverables:
                self._structure_status[deliverable] = PhaseStatus.RUNNING
        elif isinstance(event, VisualsStructureProgress):
            deliverable = _STEP_TO_DELIVERABLE[event.step]
            if deliverable in self._structure_status:
                self._structure_status[deliverable] = PhaseStatus.RUNNING
                self._structure_detail[deliverable] = (
                    f"{structure_step_label(event.step)} "
                    f"{event.completed}/{event.total}"
                )
        else:
            for deliverable in self._deliverables:
                self._structure_status[deliverable] = PhaseStatus.SUCCEEDED
                self._structure_detail.pop(deliverable, None)

    def cost_matrix_snapshot(self) -> CostMatrixSnapshot:
        """Construit la matrice livrables × (Structure + langues), statut par cellule.

        La colonne **Structure** (extraction commune, exécutée une fois) précède les
        colonnes de langues, pour matérialiser l'avancement de la phase la plus longue
        **avant** la production par langue.

        Returns:
            ``CostMatrixSnapshot`` (lignes = livrables ; colonnes = Structure + langues).
        """
        column_labels = (
            _structure_column_label(),
            *(lang.value for lang in self._languages),
        )
        rows = tuple(
            (
                deliverable_label(deliverable),
                (
                    self._structure_cell(deliverable),
                    *(self._cell(lang) for lang in self._languages),
                ),
            )
            for deliverable in self._deliverables
        )
        return build_cost_matrix(
            row_header=_ROW_HEADER, column_labels=column_labels, rows=rows
        )

    def _structure_cell(self, deliverable: VisualsDeliverable) -> CostMatrixCell:
        """Cellule de la colonne « Structure » pour un livrable (statut + détail).

        Args:
            deliverable: Livrable (ligne).

        Returns:
            ``CostMatrixCell`` (coût ``None`` ; infobulle = ex. « Graphe 12/32 »).
        """
        status = self._structure_status.get(deliverable)
        return CostMatrixCell(
            status=status or PhaseStatus.PENDING,
            cost_usd=None,
            tooltip=self._structure_detail.get(deliverable, ""),
        )

    def _cell(self, language: Language) -> CostMatrixCell:
        """Cellule de matrice pour une langue (statut uniquement, coût non rattaché).

        Args:
            language: Langue (colonne).

        Returns:
            ``CostMatrixCell`` (coût ``None`` : voir le total dans les tuiles).
        """
        status = self._status.get(language)
        return CostMatrixCell(
            status=status or PhaseStatus.PENDING, cost_usd=None, tooltip=""
        )

    def stats_snapshot(self) -> VisualsStatsSnapshot:
        """Construit le snapshot des tuiles Visualisations.

        Returns:
            ``VisualsStatsSnapshot``.
        """
        done = sum(1 for status in self._status.values() if status in _DONE_STATUSES)
        return VisualsStatsSnapshot(
            overall_status=self._overall_status,
            languages_done=done,
            languages_total=len(self._languages),
            languages=self._languages,
            total_cost_usd=self._total_cost_usd,
            cost_ceiling_usd=self._cost_ceiling_usd,
            started_at=self._started_at,
            finished_at=self._finished_at,
        )
