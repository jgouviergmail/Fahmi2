"""ViewModel générique d'une matrice de coût (présentationnel, sans Qt).

Structure 2D ``lignes × colonnes`` où chaque cellule porte un statut et un coût
optionnel. Produit par les viewmodels génération (vidéos × phases) et pédagogie
(supports × langues) ; consommé par ``CostMatrixView``. Les totaux (par ligne, par
colonne, général) sont calculés ici (somme des coûts, ``None`` comptant pour 0).
"""

from __future__ import annotations

from dataclasses import dataclass

from fahmi2.domain.enums import PhaseStatus


@dataclass(frozen=True)
class CostMatrixCell:
    """Cellule : statut + coût optionnel + infobulle.

    Attributes:
        status: Statut de la tâche (réutilise ``PhaseStatus``).
        cost_usd: Coût en USD, ou ``None`` si non encore connu (en attente).
        tooltip: Texte d'infobulle (déjà formaté par le producteur).
    """

    status: PhaseStatus
    cost_usd: float | None
    tooltip: str = ""


@dataclass(frozen=True)
class CostMatrixSnapshot:
    """Snapshot complet d'une matrice de coût.

    Attributes:
        row_header: En-tête de la colonne des libellés de lignes.
        column_labels: Libellés des colonnes de données (ordre d'affichage).
        row_labels: Libellés des lignes (ordre d'affichage).
        cells: Cellules ``[ligne][colonne]`` (même cardinalité que les libellés).
        row_totals: Coût total par ligne.
        column_totals: Coût total par colonne.
        grand_total: Coût total général.
    """

    row_header: str
    column_labels: tuple[str, ...]
    row_labels: tuple[str, ...]
    cells: tuple[tuple[CostMatrixCell, ...], ...]
    row_totals: tuple[float, ...]
    column_totals: tuple[float, ...]
    grand_total: float


def build_cost_matrix(
    *,
    row_header: str,
    column_labels: tuple[str, ...],
    rows: tuple[tuple[str, tuple[CostMatrixCell, ...]], ...],
) -> CostMatrixSnapshot:
    """Construit un ``CostMatrixSnapshot`` et calcule les totaux.

    Args:
        row_header: En-tête de la colonne des libellés.
        column_labels: Libellés des colonnes de données.
        rows: Tuple de ``(libellé_ligne, cellules)`` ; chaque ``cellules`` doit
            avoir autant d'éléments que ``column_labels``.

    Returns:
        Le snapshot avec totaux calculés.

    Raises:
        ValueError: Si une ligne n'a pas le bon nombre de cellules.
    """
    n_cols = len(column_labels)
    for label, cells in rows:
        if len(cells) != n_cols:
            raise ValueError(
                f"row '{label}' cell count {len(cells)} != {n_cols} columns"
            )
    row_labels = tuple(label for label, _ in rows)
    grid = tuple(cells for _, cells in rows)
    row_totals = tuple(sum(c.cost_usd or 0.0 for c in cells) for cells in grid)
    column_totals = tuple(
        sum((grid[r][col].cost_usd or 0.0) for r in range(len(grid)))
        for col in range(n_cols)
    )
    grand_total = sum(row_totals)
    return CostMatrixSnapshot(
        row_header=row_header,
        column_labels=column_labels,
        row_labels=row_labels,
        cells=grid,
        row_totals=row_totals,
        column_totals=column_totals,
        grand_total=grand_total,
    )
