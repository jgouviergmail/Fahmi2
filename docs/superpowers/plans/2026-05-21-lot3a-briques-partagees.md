# Lot 3a — Briques partagées (CostMatrixView + StatCard)

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (inline, sans subagents).
> **Spec** : [`../specs/2026-05-21-dashboards-coherence-design.md`](../specs/2026-05-21-dashboards-coherence-design.md) §3.1–3.2.
> Steps en checkbox. Tout en français (accents). Travail directement sur `main`.

**Goal:** Créer les deux briques UI partagées — une **matrice de coût générique**
(`CostMatrixView` + viewmodel `cost_matrix`) et une **carte de stat réutilisable**
(`StatCard`) — sans changer le comportement visible des dashboards (socle consommé
en 3b/3c).

**Architecture:** Un viewmodel **présentationnel pur** (`CostMatrixSnapshot` :
libellés + cellules `(statut, coût)` déjà résolus + totaux calculés), sans Qt ni
métier, produit plus tard par les viewmodels génération/pédagogie. Un widget
`QTableView` générique + délégué de peinture (glyphe de statut proéminent + coût
secondaire ; totaux mis en avant). Extraction de la carte `_StatCard` de
`stats_strip.py` en `StatCard` public, `StatsStripWidget` refactoré dessus.

**Tech Stack:** Python 3.12, PySide6 (Qt Widgets), pytest / pytest-qt.

---

## Task 1 : viewmodel `cost_matrix` (pur, testable)

**Files:**
- Create : `src/fahmi2/ui/viewmodels/cost_matrix.py`
- Test : `tests/unit/ui/viewmodels/test_cost_matrix.py`

- [ ] **Step 1 : Écrire les tests qui échouent**

Créer `tests/unit/ui/viewmodels/test_cost_matrix.py` :

```python
"""Tests du viewmodel générique de matrice de coût."""

from __future__ import annotations

import pytest

from fahmi2.domain.enums import PhaseStatus
from fahmi2.ui.viewmodels.cost_matrix import (
    CostMatrixCell,
    build_cost_matrix,
)


def _cell(status: PhaseStatus, cost: float | None) -> CostMatrixCell:
    return CostMatrixCell(status=status, cost_usd=cost, tooltip="")


def test_build_computes_totals() -> None:
    snap = build_cost_matrix(
        row_header="Support",
        column_labels=("FR", "EN"),
        rows=(
            ("QCM", (_cell(PhaseStatus.SUCCEEDED, 0.10), _cell(PhaseStatus.RUNNING, None))),
            ("Cloze", (_cell(PhaseStatus.SUCCEEDED, 0.05), _cell(PhaseStatus.SUCCEEDED, 0.07))),
        ),
    )
    assert snap.row_labels == ("QCM", "Cloze")
    assert snap.row_totals == (0.10, 0.12)
    assert snap.column_totals == (0.15, 0.07)
    assert snap.grand_total == pytest.approx(0.22)


def test_none_costs_count_as_zero() -> None:
    snap = build_cost_matrix(
        row_header="Vidéo",
        column_labels=("STT",),
        rows=(("v1", (_cell(PhaseStatus.PENDING, None),)),),
    )
    assert snap.row_totals == (0.0,)
    assert snap.grand_total == 0.0


def test_empty_matrix() -> None:
    snap = build_cost_matrix(row_header="X", column_labels=("A",), rows=())
    assert snap.row_labels == ()
    assert snap.column_totals == (0.0,)
    assert snap.grand_total == 0.0


def test_row_with_wrong_cell_count_raises() -> None:
    with pytest.raises(ValueError, match="cell count"):
        build_cost_matrix(
            row_header="X",
            column_labels=("A", "B"),
            rows=(("r", (_cell(PhaseStatus.PENDING, None),)),),
        )
```

- [ ] **Step 2 : Lancer, vérifier l'échec**

Run : `.venv\Scripts\python.exe -m pytest tests/unit/ui/viewmodels/test_cost_matrix.py -v`
Attendu : ÉCHEC (`ModuleNotFoundError: ... cost_matrix`).

- [ ] **Step 3 : Implémenter le viewmodel**

Créer `src/fahmi2/ui/viewmodels/cost_matrix.py` :

```python
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
    row_totals = tuple(
        sum(c.cost_usd or 0.0 for c in cells) for cells in grid
    )
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
```

- [ ] **Step 4 : Lancer, vérifier le succès**

Run : `.venv\Scripts\python.exe -m pytest tests/unit/ui/viewmodels/test_cost_matrix.py -v`
Attendu : PASS (4 tests).

- [ ] **Step 5 : Vérifs + commit**

```powershell
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m mypy src tests
git add src/fahmi2/ui/viewmodels/cost_matrix.py tests/unit/ui/viewmodels/test_cost_matrix.py
git commit -m @'
feat(ui): viewmodel generique CostMatrixSnapshot (matrice de cout)

Structure presentationnelle 2D (lignes x colonnes) avec statut + cout par cellule
et totaux calcules (ligne/colonne/general). Socle partage des dashboards.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
'@
```

---

## Task 2 : widget `CostMatrixView` (QTableView + délégué)

**Files:**
- Create : `src/fahmi2/ui/widgets/cost_matrix_view.py`
- Test : `tests/unit/ui/test_cost_matrix_view.py`

- [ ] **Step 1 : Écrire le smoke test (échoue)**

Créer `tests/unit/ui/test_cost_matrix_view.py` :

```python
"""Smoke tests du widget CostMatrixView."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fahmi2.domain.enums import PhaseStatus
from fahmi2.ui.viewmodels.cost_matrix import CostMatrixCell, build_cost_matrix
from fahmi2.ui.widgets.cost_matrix_view import CostMatrixView


def _snapshot():
    return build_cost_matrix(
        row_header="Support",
        column_labels=("FR", "EN"),
        rows=(
            (
                "QCM",
                (
                    CostMatrixCell(PhaseStatus.SUCCEEDED, 0.10, "ok"),
                    CostMatrixCell(PhaseStatus.PENDING, None, "attente"),
                ),
            ),
        ),
    )


def test_view_dimensions(qtbot: QtBot) -> None:
    view = CostMatrixView()
    qtbot.addWidget(view)
    view.apply_snapshot(_snapshot())
    model = view.model()
    assert model is not None
    # 1 ligne data + 1 ligne Total
    assert model.rowCount() == 2
    # colonne libellé + 2 colonnes data + colonne Total
    assert model.columnCount() == 4


def test_empty_view_does_not_crash(qtbot: QtBot) -> None:
    view = CostMatrixView()
    qtbot.addWidget(view)
    assert view.model() is not None
```

- [ ] **Step 2 : Lancer, vérifier l'échec**

Run : `.venv\Scripts\python.exe -m pytest tests/unit/ui/test_cost_matrix_view.py -v`
Attendu : ÉCHEC (`ModuleNotFoundError: ... cost_matrix_view`).

- [ ] **Step 3 : Implémenter le widget**

Créer `src/fahmi2/ui/widgets/cost_matrix_view.py` :

```python
"""Widget ``CostMatrixView`` — matrice de coût générique (statut + coût + totaux).

``QTableView`` + ``QAbstractTableModel`` piloté par un ``CostMatrixSnapshot``.
Chaque cellule de données est peinte par ``_CostCellDelegate`` : glyphe de statut
proéminent (couleur du statut) + coût en secondaire (petit, gris). La dernière
colonne et la dernière ligne portent les totaux (mis en avant). Réutilisé par les
dashboards Génération et Pédagogie (axes injectés via le snapshot).
"""

from __future__ import annotations

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QPersistentModelIndex,
    QRect,
    Qt,
)
from PySide6.QtGui import QBrush, QColor, QFont
from PySide6.QtWidgets import (
    QHeaderView,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableView,
    QWidget,
)

from fahmi2.domain.enums import PhaseStatus
from fahmi2.ui.viewmodels.cost_matrix import CostMatrixCell, CostMatrixSnapshot

_COST_DECIMALS = 4
_TOTAL_HEADER = "Total"
_CELL_ROLE = int(Qt.ItemDataRole.UserRole) + 1

_STATUS_SYMBOLS: dict[PhaseStatus, str] = {
    PhaseStatus.PENDING: "·",
    PhaseStatus.RUNNING: "▶",
    PhaseStatus.SUCCEEDED: "✓",
    PhaseStatus.FAILED: "✗",
    PhaseStatus.SKIPPED: "↷",
}

_STATUS_COLORS: dict[PhaseStatus, tuple[QColor, QColor]] = {
    PhaseStatus.PENDING: (QColor("#f8fafc"), QColor("#8b95a1")),
    PhaseStatus.RUNNING: (QColor("#e3f0fb"), QColor("#0a4f93")),
    PhaseStatus.SUCCEEDED: (QColor("#e6f6ec"), QColor("#1a7f37")),
    PhaseStatus.FAILED: (QColor("#fcebec"), QColor("#cf222e")),
    PhaseStatus.SKIPPED: (QColor("#f1eefb"), QColor("#5b4cc7")),
}

_COST_FG = QColor("#8b95a1")
_LABEL_BG = QColor("#ffffff")
_LABEL_FG = QColor("#1f2328")


def _empty_snapshot() -> CostMatrixSnapshot:
    """Snapshot vide pour l'initialisation.

    Returns:
        Un ``CostMatrixSnapshot`` sans ligne ni colonne.
    """
    return CostMatrixSnapshot(
        row_header="",
        column_labels=(),
        row_labels=(),
        cells=(),
        row_totals=(),
        column_totals=(),
        grand_total=0.0,
    )


def _fmt_cost(value: float | None) -> str:
    """Formate un coût (``None`` → tiret).

    Args:
        value: Coût ou ``None``.

    Returns:
        Chaîne ``$x.xxxx`` ou ``—``.
    """
    return "—" if value is None else f"${value:.{_COST_DECIMALS}f}"


class _CostMatrixModel(QAbstractTableModel):
    """Modèle Qt adossé à un ``CostMatrixSnapshot`` (+ colonne/ligne Total)."""

    def __init__(self, snapshot: CostMatrixSnapshot) -> None:
        super().__init__()
        self._s = snapshot

    def set_snapshot(self, snapshot: CostMatrixSnapshot) -> None:
        """Remplace le snapshot et réinitialise la vue.

        Args:
            snapshot: Nouveau snapshot.
        """
        self.beginResetModel()
        self._s = snapshot
        self.endResetModel()

    def rowCount(  # noqa: N802
        self, parent: QModelIndex | QPersistentModelIndex | None = None
    ) -> int:
        if parent is not None and parent.isValid():
            return 0
        # lignes data + 1 ligne Total (si au moins une colonne)
        return len(self._s.row_labels) + (1 if self._s.column_labels else 0)

    def columnCount(  # noqa: N802
        self, parent: QModelIndex | QPersistentModelIndex | None = None
    ) -> int:
        if parent is not None and parent.isValid():
            return 0
        # libellé + colonnes data + colonne Total (si au moins une colonne)
        return 1 + len(self._s.column_labels) + (1 if self._s.column_labels else 0)

    def headerData(  # noqa: N802
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> object:
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation is not Qt.Orientation.Horizontal:
            return None
        if section == 0:
            return self._s.row_header
        n_cols = len(self._s.column_labels)
        if 1 <= section <= n_cols:
            return self._s.column_labels[section - 1]
        return _TOTAL_HEADER

    def _is_total_row(self, row: int) -> bool:
        return row == len(self._s.row_labels)

    def _is_total_col(self, col: int) -> bool:
        return col == 1 + len(self._s.column_labels)

    def data(  # noqa: C901, PLR0911
        self,
        index: QModelIndex | QPersistentModelIndex,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> object:
        if not index.isValid():
            return None
        row, col = index.row(), index.column()
        total_row = self._is_total_row(row)
        total_col = self._is_total_col(col)

        # Cellule de données (peinte par le délégué) : on expose la cellule.
        if not total_row and not total_col and col >= 1:
            if role == _CELL_ROLE:
                return self._s.cells[row][col - 1]
            if role == Qt.ItemDataRole.ToolTipRole:
                return self._s.cells[row][col - 1].tooltip or None
            return None

        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0:
                return _TOTAL_HEADER if total_row else self._s.row_labels[row]
            if total_row and total_col:
                return _fmt_cost(self._s.grand_total)
            if total_row:
                return _fmt_cost(self._s.column_totals[col - 1])
            if total_col:
                return _fmt_cost(self._s.row_totals[row])
            return None
        if role == Qt.ItemDataRole.TextAlignmentRole:
            if col == 0:
                return int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            return int(Qt.AlignmentFlag.AlignCenter)
        if role == Qt.ItemDataRole.FontRole and (total_row or total_col):
            font = QFont()
            font.setBold(True)
            return font
        if role == Qt.ItemDataRole.BackgroundRole:
            return QBrush(_LABEL_BG)
        if role == Qt.ItemDataRole.ForegroundRole:
            return QBrush(_LABEL_FG)
        return None


class _CostCellDelegate(QStyledItemDelegate):
    """Peint une cellule de données : glyphe de statut + coût secondaire."""

    def paint(
        self,
        painter: object,
        option: QStyleOptionViewItem,
        index: QModelIndex | QPersistentModelIndex,
    ) -> None:
        """Peint la cellule si elle porte une ``CostMatrixCell``, sinon défaut.

        Args:
            painter: ``QPainter`` fourni par Qt.
            option: Options de style (rectangle, etc.).
            index: Index de la cellule.
        """
        cell = index.data(_CELL_ROLE)
        if not isinstance(cell, CostMatrixCell):
            super().paint(painter, option, index)  # type: ignore[arg-type]
            return
        bg, fg = _STATUS_COLORS.get(cell.status, (_LABEL_BG, _LABEL_FG))
        rect: QRect = option.rect
        painter.fillRect(rect, bg)  # type: ignore[attr-defined]

        glyph = _STATUS_SYMBOLS.get(cell.status, "?")
        glyph_font = QFont()
        glyph_font.setBold(True)
        glyph_font.setPointSize(11)
        painter.setFont(glyph_font)  # type: ignore[attr-defined]
        painter.setPen(fg)  # type: ignore[attr-defined]
        top = QRect(rect.x(), rect.y() + 2, rect.width(), rect.height() // 2)
        painter.drawText(  # type: ignore[attr-defined]
            top, int(Qt.AlignmentFlag.AlignCenter), glyph
        )

        cost_font = QFont()
        cost_font.setPointSize(8)
        painter.setFont(cost_font)  # type: ignore[attr-defined]
        painter.setPen(_COST_FG)  # type: ignore[attr-defined]
        bottom = QRect(
            rect.x(), rect.y() + rect.height() // 2, rect.width(), rect.height() // 2 - 2
        )
        painter.drawText(  # type: ignore[attr-defined]
            bottom, int(Qt.AlignmentFlag.AlignCenter), _fmt_cost(cell.cost_usd)
        )


class CostMatrixView(QTableView):
    """Matrice de coût générique (statut + coût par cellule, totaux)."""

    def __init__(
        self,
        snapshot: CostMatrixSnapshot | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """Construit la vue.

        Args:
            snapshot: Snapshot initial (peut être ``None``).
            parent: Parent Qt optionnel.
        """
        super().__init__(parent)
        self.setObjectName("costMatrix")
        self._model = _CostMatrixModel(snapshot or _empty_snapshot())
        self.setModel(self._model)
        self.setItemDelegate(_CostCellDelegate(self))
        self.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.setShowGrid(False)
        v_header = self.verticalHeader()
        if v_header is not None:
            v_header.setVisible(False)
            v_header.setDefaultSectionSize(40)
        header = self.horizontalHeader()
        if header is not None:
            header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)

    def apply_snapshot(self, snapshot: CostMatrixSnapshot) -> None:
        """Applique un nouveau snapshot.

        Args:
            snapshot: Nouveau snapshot.
        """
        self._model.set_snapshot(snapshot)
```

- [ ] **Step 4 : Lancer, vérifier le succès**

Run : `.venv\Scripts\python.exe -m pytest tests/unit/ui/test_cost_matrix_view.py -v`
Attendu : PASS (2 tests).

- [ ] **Step 5 : Style QSS de la matrice générique**

Dans `src/fahmi2/ui/theme/light_fluent.qss`, sous la section de la matrice
existante (`#runMatrix`), ajouter un sélecteur partagé pour `#costMatrix` (même
apparence : fond blanc, bordure, en-têtes). Dupliquer le bloc `#runMatrix` /
`#runMatrix QHeaderView::section` en `#costMatrix` (le `#runMatrix` sera retiré au
Lot 3c quand la génération migrera).

- [ ] **Step 6 : Vérifs + commit**

```powershell
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m mypy src tests
git add src/fahmi2/ui/widgets/cost_matrix_view.py tests/unit/ui/test_cost_matrix_view.py src/fahmi2/ui/theme/light_fluent.qss
git commit -m @'
feat(ui): widget CostMatrixView generique (statut + cout + totaux)

QTableView + delegue de peinture : glyphe de statut proeminent + cout secondaire
(petit, gris) par cellule ; colonne/ligne Total mis en avant. QSS #costMatrix.
Socle partage, non encore branche (consomme en 3b/3c).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
'@
```

---

## Task 3 : extraire `StatCard` réutilisable

**Files:**
- Create : `src/fahmi2/ui/widgets/stat_card.py`
- Modify : `src/fahmi2/ui/widgets/stats_strip.py`
- Test : `tests/unit/ui/test_stat_card.py`

- [ ] **Step 1 : Smoke test de `StatCard` (échoue)**

Créer `tests/unit/ui/test_stat_card.py` :

```python
"""Smoke test de la carte de stat réutilisable."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fahmi2.ui.widgets.stat_card import StatCard


def test_stat_card_set_value_and_accent(qtbot: QtBot) -> None:
    card = StatCard(icon="$", title="Coût")
    qtbot.addWidget(card)
    card.set_value("$1.50", "plafond $2.00")
    card.set_accent("warning")
    assert card.value_text() == "$1.50"
```

- [ ] **Step 2 : Lancer, vérifier l'échec**

Run : `.venv\Scripts\python.exe -m pytest tests/unit/ui/test_stat_card.py -v`
Attendu : ÉCHEC (`ModuleNotFoundError: ... stat_card`).

- [ ] **Step 3 : Créer `stat_card.py`**

Créer `src/fahmi2/ui/widgets/stat_card.py` en déplaçant la classe `_StatCard` de
`stats_strip.py`, renommée **`StatCard`** (publique), avec un accesseur de test
`value_text()` :

```python
"""Widget ``StatCard`` — carte d'indicateur réutilisable (icône + valeur + sous-info).

Extraite de ``stats_strip`` pour être partagée par les bandes de stats Génération
et Pédagogie. Une variante d'accent (``neutral``/``running``/``success``/
``warning``/``danger``) pilote la couleur de la valeur via le QSS global.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget


class StatCard(QFrame):
    """Carte d'indicateur (icône + titre + valeur principale + sous-info)."""

    def __init__(
        self,
        *,
        icon: str,
        title: str,
        parent: QWidget | None = None,
    ) -> None:
        """Construit la carte.

        Args:
            icon: Glyphe Unicode décoratif.
            title: Libellé court de l'indicateur.
            parent: Parent Qt optionnel.
        """
        super().__init__(parent)
        self.setObjectName("statCard")
        self.setFrameShape(QFrame.Shape.NoFrame)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(2)

        header = QHBoxLayout()
        header.setSpacing(6)
        self._icon_label = QLabel(icon, self)
        self._icon_label.setObjectName("statCardIcon")
        self._title_label = QLabel(title, self)
        self._title_label.setObjectName("statCardTitle")
        header.addWidget(self._icon_label)
        header.addWidget(self._title_label)
        header.addStretch(1)
        layout.addLayout(header)

        self._value_label = QLabel("—", self)
        self._value_label.setObjectName("statCardValue")
        self._value_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.NoTextInteraction
        )
        layout.addWidget(self._value_label)

        self._sub_label = QLabel(" ", self)
        self._sub_label.setObjectName("statCardSub")
        layout.addWidget(self._sub_label)

    def set_value(self, value: str, sub: str = "") -> None:
        """Met à jour la valeur principale et la sous-info.

        Args:
            value: Texte de la valeur principale.
            sub: Texte secondaire (peut être vide).
        """
        self._value_label.setText(value)
        self._sub_label.setText(sub or " ")

    def set_accent(self, kind: str) -> None:
        """Force une variante d'accent visuelle via une propriété Qt.

        Args:
            kind: ``"neutral"``, ``"running"``, ``"success"``, ``"warning"`` ou
                ``"danger"`` (interprété par le QSS global).
        """
        self._value_label.setProperty("accent", kind)
        style = self._value_label.style()
        if style is not None:
            style.unpolish(self._value_label)
            style.polish(self._value_label)

    def value_text(self) -> str:
        """Retourne le texte courant de la valeur principale (tests).

        Returns:
            Le texte de la valeur.
        """
        return self._value_label.text()
```

- [ ] **Step 4 : Refactorer `stats_strip.py` sur `StatCard`**

Dans `src/fahmi2/ui/widgets/stats_strip.py` : supprimer la classe locale `_StatCard`
(et ses imports devenus inutiles : `QFrame`), importer
`from fahmi2.ui.widgets.stat_card import StatCard`, et remplacer les usages
`_StatCard(icon=..., title=..., parent=self)` par `StatCard(icon=..., title=...,
parent=self)`. Aucun autre changement (le rendu et les `set_value`/`set_accent`
sont identiques).

- [ ] **Step 5 : Lancer les tests UI, vérifier le succès**

Run : `.venv\Scripts\python.exe -m pytest tests/unit/ui/test_stat_card.py tests/unit/ui/viewmodels/test_stats_strip.py tests/unit/ui/test_widgets_smoke.py -v`
Attendu : PASS (la bande de stats fonctionne à l'identique).

- [ ] **Step 6 : Vérifs + commit**

```powershell
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m mypy src tests
git add src/fahmi2/ui/widgets/stat_card.py src/fahmi2/ui/widgets/stats_strip.py tests/unit/ui/test_stat_card.py
git commit -m @'
refactor(ui): extraire StatCard reutilisable depuis stats_strip

Carte d'indicateur publique partagee (icone + valeur + sous-info + accent),
sans changement de rendu. Prepare la bande de stats pedagogie (Lot 3b).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
'@
```

---

## Clôture du Lot 3a

- [ ] `CHANGELOG.md` (Non publié) : « Ajouté » (briques UI partagées
  `CostMatrixView` + `StatCard`, socle de la cohérence des dashboards). Commit
  `docs(changelog): Lot 3a (briques partagees dashboards)`.
- [ ] Lots suivants (plans dédiés) : **3b** (pédagogie : tuiles + matrice), **3c**
  (génération : migration vers `CostMatrixView`), **3d** (estimation granulaire +
  fourchette).

## Self-review

Couvre §3.1 (CostMatrixView + viewmodel) et §3.2 (StatCard) du spec. Pas de
placeholder : code et chemins exacts. Types cohérents (`CostMatrixCell`,
`CostMatrixSnapshot`, `build_cost_matrix`, `StatCard`). Socle non encore branché
(consommé en 3b/3c) → testé en isolation (viewmodel unitaire, widgets smoke). Le
`StatCard` est consommé immédiatement par `StatsStripWidget` (non-régression
couverte par les smoke tests existants).
