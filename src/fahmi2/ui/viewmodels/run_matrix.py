"""ViewModel ``RunMatrixViewModel`` — alimente la matrice générique de coût.

Convertit un ``Run`` + ses ``PhaseExecution`` SQLite en ``CostMatrixSnapshot``
(lignes = sources, colonnes = phases). Les phases **batch** (non per-source) affichent
leur statut sur chaque ligne mais leur **coût n'est porté que par le total de
colonne** (coût au niveau du run, ``—`` en cellule) ; le total de ligne ne somme que
les phases par-source. Sans logique Qt en dehors des libellés traduits exposés
par :func:`column_labels` / :func:`_tooltip`.

i18n : les libellés courts des phases et les libellés de statut viennent de
``QCoreApplication.translate("RunMatrix", "literal")`` — résolus à l'usage
pour suivre la langue active à chaque construction de snapshot.
"""

from __future__ import annotations

from PySide6.QtCore import QCoreApplication

from fahmi2.domain.enums import PhaseId, PhaseStatus
from fahmi2.domain.ids import SourceId
from fahmi2.domain.run import Run
from fahmi2.domain.source import SourceExecution
from fahmi2.infra.storage.sqlite_state import PhaseCell, SqliteState
from fahmi2.pipeline.phase_registry import PhaseRegistry
from fahmi2.ui.viewmodels.cost_matrix import CostMatrixCell, CostMatrixSnapshot


def _phase_short_label(phase_id: PhaseId) -> str:
    """Libellé court traduit d'une phase (colonnes de la matrice)."""
    mapping = {
        PhaseId.STT: QCoreApplication.translate("RunMatrix", "Ingestion"),
        PhaseId.TERM_EXTRACTION: QCoreApplication.translate("RunMatrix", "Termes"),
        PhaseId.GLOSSARY_RECONCILIATION: QCoreApplication.translate(
            "RunMatrix", "Glossaire"
        ),
        PhaseId.REFORMULATION: QCoreApplication.translate("RunMatrix", "Reformul."),
        PhaseId.STRUCTURATION: QCoreApplication.translate("RunMatrix", "Structur."),
        PhaseId.CONSOLIDATION: QCoreApplication.translate("RunMatrix", "Consolid."),
        PhaseId.TRANSLATION: QCoreApplication.translate("RunMatrix", "Traduction"),
        PhaseId.COHERENCE: QCoreApplication.translate("RunMatrix", "Cohérence"),
    }
    return mapping.get(phase_id, phase_id.value)


def _status_label(status: PhaseStatus) -> str:
    """Libellé traduit d'un statut de phase (tooltip de cellule)."""
    if status is PhaseStatus.PENDING:
        return QCoreApplication.translate("RunMatrix", "en attente")
    if status is PhaseStatus.RUNNING:
        return QCoreApplication.translate("RunMatrix", "en cours")
    if status is PhaseStatus.SUCCEEDED:
        return QCoreApplication.translate("RunMatrix", "terminé")
    if status is PhaseStatus.FAILED:
        return QCoreApplication.translate("RunMatrix", "échec")
    # ``status`` est une enum exhaustive (5 valeurs traitées ci-dessus) — le
    # ``return`` final n'est jamais atteint en pratique, mais reste comme repli
    # défensif si un nouvel état était introduit sans mise à jour ici.
    if status is PhaseStatus.SKIPPED:
        return QCoreApplication.translate("RunMatrix", "déjà fait")
    return str(status.value)  # type: ignore[unreachable]


class RunMatrixViewModel:
    """Construit un ``CostMatrixSnapshot`` à partir de l'état SQLite d'un Run."""

    def __init__(self, *, state: SqliteState, registry: PhaseRegistry) -> None:
        """Construit le viewmodel.

        Args:
            state: Accès SQLite.
            registry: Registre des handlers (ordre des colonnes + per-source).
        """
        self._state = state
        self._registry = registry

    def _phases(self) -> tuple[tuple[PhaseId, bool], ...]:
        """Phases dans l'ordre canonique + drapeau per-source."""
        return tuple(
            (h.phase_id, h.is_per_source) for h in self._registry.ordered_handlers()
        )

    def cost_matrix_snapshot(self, run: Run) -> CostMatrixSnapshot:
        """Construit la matrice sources × phases (statut + coût + totaux)."""
        cells_by_key: dict[tuple[PhaseId, SourceId | None], PhaseCell] = {
            (c.phase_id, c.source_id): c for c in self._state.list_phase_cells(run.id)
        }
        return self._build(run.sources, self._phases(), cells_by_key)

    def preview_cost_matrix(
        self, sources: tuple[SourceExecution, ...]
    ) -> CostMatrixSnapshot:
        """Matrice de prévisualisation (toutes phases ``PENDING``, coût 0)."""
        return self._build(sources, self._phases(), {})

    def _build(
        self,
        sources: tuple[SourceExecution, ...],
        phases: tuple[tuple[PhaseId, bool], ...],
        cells_by_key: dict[tuple[PhaseId, SourceId | None], PhaseCell],
    ) -> CostMatrixSnapshot:
        """Assemble le snapshot (cellules + totaux, gestion batch).

        Phases per-source : chaque cellule porte son coût propre.

        Phases batch : un unique coût existe en base (``source_id=NULL``)
        partagé par toutes les sources. Pour le rendre visible sans risque
        d'addition mentale erronée (12 lignes × coût ≠ total réel), on
        l'affiche **uniquement sur la cellule de la 1ʳᵉ ligne** ; les autres
        restent à ``None`` (rendues ``—``). Le total de colonne reste la
        valeur batch unique, qui sert d'autorité.
        """
        column_labels = tuple(_phase_short_label(p) for p, _ in phases)
        grid: list[tuple[CostMatrixCell, ...]] = []
        row_totals: list[float] = []
        for index, source in enumerate(sources):
            row: list[CostMatrixCell] = []
            row_total = 0.0
            for phase_id, per_source in phases:
                key = (phase_id, source.source_id if per_source else None)
                pc = cells_by_key.get(key)
                status = pc.status if pc is not None else PhaseStatus.PENDING
                cost = pc.cost_usd if pc is not None else 0.0
                if per_source:
                    row_total += cost
                    cell_cost = cost if pc is not None else None
                elif index == 0 and pc is not None:
                    # Coût batch visible sur la 1ʳᵉ ligne uniquement
                    # (cf. docstring de la méthode).
                    cell_cost = cost
                else:
                    cell_cost = None
                row.append(
                    CostMatrixCell(
                        status=status,
                        cost_usd=cell_cost,
                        tooltip=_tooltip(phase_id, status, cost, batch=not per_source),
                    )
                )
            grid.append(tuple(row))
            row_totals.append(row_total)

        column_totals: list[float] = []
        grand_total = sum(row_totals)
        for phase_id, per_source in phases:
            if per_source:
                column_totals.append(
                    sum(
                        pc.cost_usd
                        for s in sources
                        if (pc := cells_by_key.get((phase_id, s.source_id))) is not None
                    )
                )
            else:
                batch = cells_by_key.get((phase_id, None))
                batch_cost = batch.cost_usd if batch is not None else 0.0
                column_totals.append(batch_cost)
                grand_total += batch_cost

        return CostMatrixSnapshot(
            row_header=QCoreApplication.translate("RunMatrix", "Source"),
            column_labels=column_labels,
            row_labels=tuple(s.source.display_name() for s in sources),
            cells=tuple(grid),
            row_totals=tuple(row_totals),
            column_totals=tuple(column_totals),
            grand_total=grand_total,
        )


def _tooltip(
    phase_id: PhaseId, status: PhaseStatus, cost: float, *, batch: bool = False
) -> str:
    """Construit l'infobulle d'une cellule."""
    label = _status_label(status)
    suffix = (
        QCoreApplication.translate("RunMatrix", " (coût au niveau du run)")
        if batch
        else ""
    )
    cost_label = QCoreApplication.translate("RunMatrix", "coût")
    return f"{phase_id.value} — {label} — {cost_label}: ${cost:.4f}{suffix}"
