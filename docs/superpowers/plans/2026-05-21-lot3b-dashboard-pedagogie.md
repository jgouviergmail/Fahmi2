# Lot 3b — Dashboard pédagogie (tuiles + matrice 2D)

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (inline, sans subagents).
> **Spec** : [`../specs/2026-05-21-dashboards-coherence-design.md`](../specs/2026-05-21-dashboards-coherence-design.md) §3.3.
> **Prérequis** : Lot 3a (`CostMatrixView`, `CostMatrixSnapshot`, `StatCard`).
> Steps en checkbox. Tout en français (accents). Travail directement sur `main`.

**Goal:** Aligner le dashboard Supports pédagogiques sur la Génération : **bande de
tuiles** (Statut / Supports / Langues / Coût) + **matrice 2D** supports × langues
(via `CostMatrixView`), en conservant le **bandeau de fraîcheur**.

**Architecture:** `PedagogyProgressViewModel` gagne deux producteurs sans Qt —
`cost_matrix_snapshot()` (grille supports × langues) et `stats_snapshot()` (tuiles).
`PedagogyProgressView` est reconstruite : bandeau + tuiles `StatCard` + `CostMatrixView`.
Le contrôleur alimente la vue avec ces deux snapshots.

**Tech Stack:** Python 3.12, PySide6, pytest / pytest-qt.

---

## Task 1 : viewmodel — `cost_matrix_snapshot()` + `stats_snapshot()`

**Files:**
- Modify : `src/fahmi2/ui/viewmodels/pedagogy_progress.py`
- Test : `tests/unit/ui/viewmodels/test_pedagogy_progress.py`

- [ ] **Step 1 : Écrire les tests qui échouent**

Ajouter à `tests/unit/ui/viewmodels/test_pedagogy_progress.py` :

```python
def test_cost_matrix_snapshot_grid() -> None:
    vm = PedagogyProgressViewModel()
    vm.reset(
        supports=(SupportType.QCM, SupportType.KEY_POINTS),
        languages=(Language.FR, Language.EN),
    )
    vm.apply_event(
        SupportFinished(
            timestamp=_now(),
            support_type=SupportType.QCM,
            language=Language.FR,
            status=PhaseStatus.SUCCEEDED,
            cost_usd=0.10,
            error=None,
        )
    )
    snap = vm.cost_matrix_snapshot()
    assert snap.row_header == "Support"
    assert snap.column_labels == ("fr", "en")
    assert snap.row_labels[0] == "QCM"  # ordre canonique (QCM avant points clés)
    # QCM/FR succeeded -> coût compté ; les autres en attente -> None
    assert snap.grand_total == 0.10
    assert snap.cells[0][0].status is PhaseStatus.SUCCEEDED
    assert snap.cells[0][1].cost_usd is None  # QCM/EN en attente


def test_stats_snapshot_counts() -> None:
    vm = PedagogyProgressViewModel()
    vm.reset(supports=(SupportType.QCM,), languages=(Language.FR, Language.EN))
    vm.apply_event(
        SupportFinished(
            timestamp=_now(),
            support_type=SupportType.QCM,
            language=Language.FR,
            status=PhaseStatus.SUCCEEDED,
            cost_usd=0.10,
            error=None,
        )
    )
    stats = vm.stats_snapshot()
    assert stats.tasks_total == 2
    assert stats.tasks_done == 1
    assert stats.languages == (Language.FR, Language.EN)
    assert stats.total_cost_usd == 0.10
```

- [ ] **Step 2 : Lancer, vérifier l'échec**

Run : `.venv\Scripts\python.exe -m pytest tests/unit/ui/viewmodels/test_pedagogy_progress.py -v`
Attendu : ÉCHEC (`AttributeError: ... cost_matrix_snapshot`).

- [ ] **Step 3 : Implémenter dans `pedagogy_progress.py`**

En tête, compléter les imports :

```python
from fahmi2.ui.pedagogy_labels import support_label
from fahmi2.ui.viewmodels.cost_matrix import (
    CostMatrixCell,
    CostMatrixSnapshot,
    build_cost_matrix,
)
```

Ajouter le dataclass de stats (après `PedagogyProgressSnapshot`) :

```python
@dataclass(frozen=True)
class PedagogyStatsSnapshot:
    """Indicateurs agrégés pour la bande de tuiles pédagogie.

    Attributes:
        overall_status: Statut global (``None`` tant que non terminé).
        tasks_done: Tâches (support × langue) terminées (succès ou à jour).
        tasks_total: Nombre total de tâches.
        languages: Langues sélectionnées.
        total_cost_usd: Coût total cumulé.
    """

    overall_status: RunStatus | None
    tasks_done: int
    tasks_total: int
    languages: tuple[Language, ...]
    total_cost_usd: float
```

Dans `reset`, mémoriser les axes (avant la boucle) :

```python
        self._supports = tuple(
            s for s in SupportGeneratorRegistry.canonical_order() if s in selected
        )
        self._languages = languages
```

et initialiser dans `__init__` :

```python
        self._supports: tuple[SupportType, ...] = ()
        self._languages: tuple[Language, ...] = ()
```

Statuts comptant comme « coût connu » et « terminé » (constantes de module) :

```python
_COST_KNOWN_STATUSES = frozenset(
    {PhaseStatus.SUCCEEDED, PhaseStatus.SKIPPED, PhaseStatus.FAILED}
)
_DONE_STATUSES = frozenset({PhaseStatus.SUCCEEDED, PhaseStatus.SKIPPED})
```

Ajouter les producteurs :

```python
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
            1
            for cell in self._cells.values()
            if cell.status in _DONE_STATUSES
        )
        return PedagogyStatsSnapshot(
            overall_status=self._overall_status,
            tasks_done=done,
            tasks_total=len(self._cells),
            languages=self._languages,
            total_cost_usd=self._total_cost_usd,
        )
```

- [ ] **Step 4 : Lancer, vérifier le succès**

Run : `.venv\Scripts\python.exe -m pytest tests/unit/ui/viewmodels/test_pedagogy_progress.py -v`
Attendu : PASS (6 tests).

- [ ] **Step 5 : Vérifs + commit**

```powershell
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m mypy src tests
git add src/fahmi2/ui/viewmodels/pedagogy_progress.py tests/unit/ui/viewmodels/test_pedagogy_progress.py
git commit -m @'
feat(ui): viewmodel pedagogie -> matrice de cout + stats (tuiles)

PedagogyProgressViewModel expose cost_matrix_snapshot() (grille supports x langues,
statut + cout par cellule) et stats_snapshot() (statut, taches faites/total,
langues, cout). Reutilise le viewmodel generique du Lot 3a.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
'@
```

---

## Task 2 : reconstruire `PedagogyProgressView` (bandeau + tuiles + matrice)

**Files:**
- Modify : `src/fahmi2/ui/widgets/pedagogy_progress_view.py`
- Test : `tests/unit/ui/test_pedagogy_progress_view.py`

- [ ] **Step 1 : Réécrire le smoke test (échoue)**

Remplacer le contenu de `tests/unit/ui/test_pedagogy_progress_view.py` par :

```python
"""Smoke tests de PedagogyProgressView."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fahmi2.domain.enums import Language, PhaseStatus, RunStatus, SupportType
from fahmi2.ui.viewmodels.pedagogy_progress import PedagogyProgressViewModel
from fahmi2.ui.viewmodels.pedagogy_state import PedagogyState, PedagogyStateInfo
from fahmi2.ui.widgets.pedagogy_progress_view import PedagogyProgressView


def _vm() -> PedagogyProgressViewModel:
    vm = PedagogyProgressViewModel()
    vm.reset(
        supports=(SupportType.QCM, SupportType.KEY_POINTS),
        languages=(Language.FR,),
    )
    return vm


def test_apply_snapshot_fills_matrix(qtbot: QtBot) -> None:
    view = PedagogyProgressView()
    qtbot.addWidget(view)
    vm = _vm()
    view.apply_snapshot(vm.cost_matrix_snapshot(), vm.stats_snapshot())
    assert view.row_count() == 2  # 2 supports


def test_set_state_updates_banner(qtbot: QtBot) -> None:
    view = PedagogyProgressView()
    qtbot.addWidget(view)
    view.set_state(
        PedagogyStateInfo(
            state=PedagogyState.READY, message="Prêt à générer.", can_generate=True
        )
    )
    assert "Prêt" in view.banner_text()


def test_clear_resets(qtbot: QtBot) -> None:
    view = PedagogyProgressView()
    qtbot.addWidget(view)
    vm = _vm()
    view.apply_snapshot(vm.cost_matrix_snapshot(), vm.stats_snapshot())
    view.clear()
    assert view.row_count() == 0
    assert view.banner_text() == ""
```

- [ ] **Step 2 : Lancer, vérifier l'échec**

Run : `.venv\Scripts\python.exe -m pytest tests/unit/ui/test_pedagogy_progress_view.py -v`
Attendu : ÉCHEC (signature `apply_snapshot` changée).

- [ ] **Step 3 : Réécrire `pedagogy_progress_view.py`**

```python
"""Widget ``PedagogyProgressView`` — bandeau de fraîcheur + tuiles + matrice.

Aligné sur le dashboard Génération : un **bandeau d'état** (fraîcheur, via la
propriété QSS ``state``), une **bande de tuiles** (Statut / Supports / Langues /
Coût) et une **matrice de coût** supports × langues (``CostMatrixView``).
"""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from fahmi2.domain.enums import RunStatus
from fahmi2.ui.viewmodels.cost_matrix import CostMatrixSnapshot
from fahmi2.ui.viewmodels.pedagogy_progress import PedagogyStatsSnapshot
from fahmi2.ui.viewmodels.pedagogy_state import PedagogyStateInfo
from fahmi2.ui.widgets.cost_matrix_view import CostMatrixView
from fahmi2.ui.widgets.stat_card import StatCard

_BANNER_OBJECT_NAME = "pedagogyStateBanner"
_COST_DECIMALS = 2

_STATUS_LABEL: dict[RunStatus, str] = {
    RunStatus.CREATED: "Créé",
    RunStatus.RUNNING: "En cours",
    RunStatus.PAUSED: "En pause",
    RunStatus.COMPLETED: "Terminé",
    RunStatus.FAILED: "Échec",
    RunStatus.CANCELLED: "Annulé",
}
_STATUS_ACCENT: dict[RunStatus, str] = {
    RunStatus.RUNNING: "running",
    RunStatus.PAUSED: "warning",
    RunStatus.COMPLETED: "success",
    RunStatus.FAILED: "danger",
    RunStatus.CANCELLED: "danger",
}


class PedagogyProgressView(QWidget):
    """Bandeau d'état + tuiles + matrice supports × langues."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Construit la vue.

        Args:
            parent: Parent Qt optionnel.
        """
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._banner = QLabel("", self)
        self._banner.setObjectName(_BANNER_OBJECT_NAME)
        self._banner.setWordWrap(True)

        strip = QWidget(self)
        strip.setObjectName("statsStrip")
        strip_layout = QHBoxLayout(strip)
        strip_layout.setContentsMargins(12, 8, 12, 8)
        strip_layout.setSpacing(10)
        self._card_status = StatCard(icon="●", title="Statut", parent=strip)
        self._card_supports = StatCard(icon="▤", title="Supports", parent=strip)
        self._card_languages = StatCard(icon="🌐", title="Langues", parent=strip)
        self._card_cost = StatCard(icon="$", title="Coût", parent=strip)
        for card in (
            self._card_status,
            self._card_supports,
            self._card_languages,
            self._card_cost,
        ):
            strip_layout.addWidget(card, stretch=1)

        self._matrix = CostMatrixView(parent=self)
        self._row_count = 0

        layout.addWidget(self._banner)
        layout.addWidget(strip)
        layout.addWidget(self._matrix, stretch=1)

    def apply_snapshot(
        self, matrix: CostMatrixSnapshot, stats: PedagogyStatsSnapshot
    ) -> None:
        """Met à jour la matrice et les tuiles.

        Args:
            matrix: Grille supports × langues.
            stats: Indicateurs agrégés.
        """
        self._matrix.apply_snapshot(matrix)
        self._row_count = len(matrix.row_labels)
        self._render_stats(stats)

    def _render_stats(self, stats: PedagogyStatsSnapshot) -> None:
        """Met à jour les 4 tuiles.

        Args:
            stats: Indicateurs agrégés.
        """
        if stats.overall_status is not None:
            self._card_status.set_value(
                _STATUS_LABEL.get(stats.overall_status, stats.overall_status.value)
            )
            self._card_status.set_accent(
                _STATUS_ACCENT.get(stats.overall_status, "neutral")
            )
        else:
            self._card_status.set_value("—")
            self._card_status.set_accent("neutral")
        self._card_supports.set_value(
            f"{stats.tasks_done} / {stats.tasks_total}", "tâches"
        )
        langs = " · ".join(lang.value.upper() for lang in stats.languages) or "—"
        self._card_languages.set_value(langs)
        self._card_cost.set_value(f"${stats.total_cost_usd:.{_COST_DECIMALS}f}")

    def set_state(self, info: PedagogyStateInfo) -> None:
        """Met à jour le bandeau d'état.

        Args:
            info: État + message.
        """
        self._banner.setText(info.message)
        self._set_banner_state(info.state.value)

    def clear(self) -> None:
        """Réinitialise (aucun projet sélectionné)."""
        self._matrix.apply_snapshot(_EMPTY_MATRIX)
        self._row_count = 0
        self._banner.setText("")
        self._set_banner_state("")
        for card in (
            self._card_status,
            self._card_supports,
            self._card_languages,
            self._card_cost,
        ):
            card.set_value("—")
            card.set_accent("neutral")

    def _set_banner_state(self, state: str) -> None:
        """Applique la propriété QSS dynamique ``state`` et force le re-style.

        Args:
            state: Valeur de l'état (``""`` pour réinitialiser).
        """
        self._banner.setProperty("state", state)
        style = self._banner.style()
        if style is not None:
            style.unpolish(self._banner)
            style.polish(self._banner)

    def row_count(self) -> int:
        """Nombre de lignes (supports) affichées dans la matrice.

        Returns:
            Le nombre de supports de la dernière matrice appliquée.
        """
        return self._row_count

    def banner_text(self) -> str:
        """Texte courant du bandeau.

        Returns:
            Le texte du bandeau.
        """
        return self._banner.text()


_EMPTY_MATRIX = CostMatrixSnapshot(
    row_header="Support",
    column_labels=(),
    row_labels=(),
    cells=(),
    row_totals=(),
    column_totals=(),
    grand_total=0.0,
)
```

- [ ] **Step 4 : Lancer, vérifier le succès**

Run : `.venv\Scripts\python.exe -m pytest tests/unit/ui/test_pedagogy_progress_view.py -v`
Attendu : PASS (3 tests).

- [ ] **Step 5 : Vérifs + commit**

```powershell
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m mypy src tests
git add src/fahmi2/ui/widgets/pedagogy_progress_view.py tests/unit/ui/test_pedagogy_progress_view.py
git commit -m @'
feat(ui): dashboard pedagogie = bandeau + tuiles + matrice 2D

PedagogyProgressView reconstruite sur les briques du Lot 3a (StatCard +
CostMatrixView) : bandeau de fraicheur conserve, bande de tuiles
(Statut/Supports/Langues/Cout), matrice supports x langues (statut + cout +
totaux). Remplace la table plate.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
'@
```

---

## Task 3 : câbler le contrôleur

**Files:**
- Modify : `src/fahmi2/ui/pedagogy_controller.py`

- [ ] **Step 1 : Adapter les 3 appels `apply_snapshot`**

Dans `pedagogy_controller.py`, remplacer les appels qui passaient un
`PedagogyProgressSnapshot` par le couple matrice + stats :

- Vers la ligne 209 :

```python
        self._progress_view.apply_snapshot(PedagogyProgressViewModel().snapshot())
```
→
```python
        empty = PedagogyProgressViewModel()
        self._progress_view.apply_snapshot(
            empty.cost_matrix_snapshot(), empty.stats_snapshot()
        )
```

- Vers les lignes 345 et 600 (deux occurrences identiques) :

```python
        self._progress_view.apply_snapshot(self._progress_vm.snapshot())
```
→
```python
        self._progress_view.apply_snapshot(
            self._progress_vm.cost_matrix_snapshot(),
            self._progress_vm.stats_snapshot(),
        )
```

- [ ] **Step 2 : Lancer les tests contrôleur**

Run : `.venv\Scripts\python.exe -m pytest tests/unit/ui/test_pedagogy_controller.py -v`
Attendu : PASS (les assertions `banner_text()` / `row_count()` restent valides ;
`row_count()` reflète le nombre de supports de la matrice).

- [ ] **Step 3 : Vérifs + commit**

```powershell
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m mypy src tests
git add src/fahmi2/ui/pedagogy_controller.py
git commit -m @'
feat(ui): cabler le dashboard pedagogie (matrice + tuiles)

Le PedagogyController alimente la vue avec cost_matrix_snapshot() +
stats_snapshot() du viewmodel (au lieu de la table plate).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
'@
```

---

## Clôture du Lot 3b

- [ ] `CHANGELOG.md` (Non publié) : « Modifié » (dashboard pédagogie aligné sur la
  Génération : tuiles + matrice 2D). Commit `docs(changelog): Lot 3b (dashboard pedagogie)`.
- [ ] Contrôle visuel : lancer l'app, onglet Supports pédagogiques → tuiles +
  matrice supports × langues (coût par cellule + totaux), bandeau de fraîcheur.
- [ ] Lots suivants : **3c** (génération), **3d** (estimation).

## Self-review

Couvre §3.3 du spec : tuiles (`StatCard`) + matrice 2D (`CostMatrixView`) + bandeau
conservé. Pas de placeholder : code exact. Types cohérents (`PedagogyStatsSnapshot`,
`cost_matrix_snapshot`, `stats_snapshot`, `apply_snapshot(matrix, stats)`). Le
`PedagogyProgressSnapshot`/`snapshot()` existant **reste** (rétrocompat des tests
viewmodel) ; la vue ne s'en sert plus. `row_count()` = nb de supports (0 après
`clear`).
