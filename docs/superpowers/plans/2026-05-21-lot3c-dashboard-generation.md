# Lot 3c — Dashboard génération (migration vers CostMatrixView)

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (inline, sans subagents).
> **Spec** : [`../specs/2026-05-21-dashboards-coherence-design.md`](../specs/2026-05-21-dashboards-coherence-design.md) §3.4.
> **Prérequis** : Lot 3a (`CostMatrixView`, `CostMatrixSnapshot`).
> Steps en checkbox. Tout en français (accents). Travail directement sur `main`.

**Goal:** Migrer la matrice Génération (vidéos × phases) vers le composant partagé
`CostMatrixView` : **coût par cellule + totaux** (par vidéo, par phase, général), en
exposant le coût par (phase, vidéo) — non disponible aujourd'hui.

**Architecture:** Ajout d'une requête `SqliteState.list_phase_cells(run)` retournant
le statut + coût par `(phase, vidéo|None)`. `RunMatrixViewModel` produit un
`CostMatrixSnapshot` (lignes = vidéos, colonnes = phases). **Phases batch** (non
per-vidéo) : statut affiché par ligne, coût `—` en cellule (coût au niveau du run),
le **total de colonne** d'une phase batch portant son coût réel ; le total de ligne
ne somme que les phases par-vidéo (totaux construits explicitement par le viewmodel).
La `RunMatrixView` (ancien widget) et `MatrixSnapshot` sont supprimés.

**Tech Stack:** Python 3.12, SQLite, PySide6, pytest / pytest-qt.

---

## Task 1 : infra — `list_phase_cells`

**Files:**
- Modify : `src/fahmi2/infra/storage/sqlite_state.py`
- Test : `tests/unit/infra/storage/test_sqlite_state.py`

- [ ] **Step 1 : Écrire le test qui échoue**

Ajouter à `tests/unit/infra/storage/test_sqlite_state.py` (section après les phases) :

```python
def test_list_phase_cells_returns_status_and_cost(
    tmp_path: Path, make_generation_settings: Any
) -> None:
    with SqliteState(tmp_path / "t.db") as state:
        project = _make_project(make_generation_settings)
        state.upsert_project(project)
        run = _make_run(project)
        state.upsert_run(run)
        vid = VideoId.new()
        state.upsert_phase_execution(
            run.id,
            PhaseExecution(
                phase_id=PhaseId.STT, status=PhaseStatus.SUCCEEDED, cost_usd=0.07
            ),
            video_id=vid,
        )
        state.upsert_phase_execution(
            run.id,
            PhaseExecution(
                phase_id=PhaseId.GLOSSARY_RECONCILIATION,
                status=PhaseStatus.SUCCEEDED,
                cost_usd=0.20,
            ),
            video_id=None,
        )
        cells = state.list_phase_cells(run.id)
        by_key = {(c.phase_id, c.video_id): c for c in cells}
        assert by_key[(PhaseId.STT, vid)].cost_usd == 0.07
        assert by_key[(PhaseId.STT, vid)].status is PhaseStatus.SUCCEEDED
        assert by_key[(PhaseId.GLOSSARY_RECONCILIATION, None)].cost_usd == 0.20
```

- [ ] **Step 2 : Lancer, vérifier l'échec**

Run : `.venv\Scripts\python.exe -m pytest tests/unit/infra/storage/test_sqlite_state.py -k phase_cells -v`
Attendu : ÉCHEC (`AttributeError: ... list_phase_cells`).

- [ ] **Step 3 : Implémenter le DTO + la requête**

Dans `sqlite_state.py`, ajouter le DTO (près des imports / en tête, après les
constantes de blob) :

```python
@dataclass(frozen=True)
class PhaseCell:
    """Statut + coût d'une exécution de phase pour une (phase, vidéo).

    Attributes:
        phase_id: Phase.
        video_id: Vidéo (``None`` pour une phase batch).
        status: Statut.
        cost_usd: Coût en USD.
        retry_count: Nombre de retries.
    """

    phase_id: PhaseId
    video_id: VideoId | None
    status: PhaseStatus
    cost_usd: float
    retry_count: int
```

(Vérifier que `dataclass` est importé — il l'est déjà via `from dataclasses import
replace` ? sinon ajouter `from dataclasses import dataclass`.)

Ajouter la méthode (après `list_phase_executions`) :

```python
    def list_phase_cells(self, run_id: RunId) -> list[PhaseCell]:
        """Liste le statut + coût par (phase, vidéo) d'un Run.

        Args:
            run_id: Run propriétaire.

        Returns:
            Une ``PhaseCell`` par exécution (``video_id`` ``None`` = phase batch).
        """
        rows = self._get_connection().execute(
            "SELECT phase_id, video_id, status, cost_usd, retry_count "
            "FROM phase_executions WHERE run_id = ? ORDER BY id",
            (run_id.value,),
        ).fetchall()
        return [
            PhaseCell(
                phase_id=PhaseId(row[0]),
                video_id=VideoId(value=row[1]) if row[1] else None,
                status=PhaseStatus(row[2]),
                cost_usd=row[3],
                retry_count=row[4],
            )
            for row in rows
        ]
```

- [ ] **Step 4 : Lancer, vérifier le succès**

Run : `.venv\Scripts\python.exe -m pytest tests/unit/infra/storage/test_sqlite_state.py -k phase_cells -v`
Attendu : PASS.

- [ ] **Step 5 : Vérifs + commit**

```powershell
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m mypy src tests
git add src/fahmi2/infra/storage/sqlite_state.py tests/unit/infra/storage/test_sqlite_state.py
git commit -m @'
feat(storage): list_phase_cells (statut + cout par phase x video)

Expose le statut et le cout par (phase, video|None) d'un run (donnee deja en base),
necessaire au cout par cellule de la matrice Generation.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
'@
```

---

## Task 2 : viewmodel — `RunMatrixViewModel` produit un `CostMatrixSnapshot`

**Files:**
- Rewrite : `src/fahmi2/ui/viewmodels/run_matrix.py`
- Rewrite : `tests/unit/ui/viewmodels/test_run_matrix.py`

- [ ] **Step 1 : Réécrire le test (échoue)**

Remplacer le contenu de `tests/unit/ui/viewmodels/test_run_matrix.py` par :

```python
"""Tests de RunMatrixViewModel (matrice de coût générique)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fahmi2.domain.enums import PhaseId, PhaseStatus, RunStatus
from fahmi2.domain.ids import ProjectId, RunId, VideoId
from fahmi2.domain.phase import PhaseExecution
from fahmi2.domain.project import Project
from fahmi2.domain.run import Run
from fahmi2.domain.video import VideoExecution
from fahmi2.infra.storage.sqlite_state import SqliteState
from fahmi2.pipeline.handlers.phase_0_stt import Phase0SttHandler
from fahmi2.pipeline.handlers.phase_1_term_extraction import (
    Phase1TermExtractionHandler,
)
from fahmi2.pipeline.handlers.phase_2_glossary_reconciliation import (
    Phase2GlossaryReconciliationHandler,
)
from fahmi2.pipeline.phase_registry import PhaseRegistry
from fahmi2.ui.viewmodels.run_matrix import RunMatrixViewModel


def _setup(
    tmp_path: Path, make_generation_settings: Any
) -> tuple[SqliteState, Run, PhaseRegistry]:
    state = SqliteState(tmp_path / "t.db")
    settings = make_generation_settings()
    project = Project(
        id=ProjectId.new(),
        name="Test",
        workspace_folder=tmp_path / "ws",
        created_at=datetime.now(tz=UTC),
        generation=settings,
    )
    state.upsert_project(project)
    videos = tuple(
        VideoExecution(video_id=VideoId.new(), source_path=tmp_path / f"v{i}.mp4")
        for i in range(2)
    )
    run = Run(
        id=RunId.new(),
        project_id=project.id,
        started_at=datetime.now(tz=UTC),
        status=RunStatus.RUNNING,
        settings_snapshot=settings,
        videos=videos,
    )
    state.upsert_run(run)
    registry = PhaseRegistry(
        [
            Phase0SttHandler(),
            Phase1TermExtractionHandler(),
            Phase2GlossaryReconciliationHandler(),
        ]
    )
    return state, run, registry


def test_snapshot_row_per_video_and_phase_columns(
    tmp_path: Path, make_generation_settings: Any
) -> None:
    state, run, registry = _setup(tmp_path, make_generation_settings)
    vm = RunMatrixViewModel(state=state, registry=registry)
    snap = vm.cost_matrix_snapshot(run)
    assert len(snap.row_labels) == 2  # 2 vidéos
    assert snap.column_labels == ("STT", "Termes", "Glossaire")
    assert snap.row_labels[0] == run.videos[0].source_path.name


def test_per_video_cost_in_cell_and_row_total(
    tmp_path: Path, make_generation_settings: Any
) -> None:
    state, run, registry = _setup(tmp_path, make_generation_settings)
    state.upsert_phase_execution(
        run.id,
        PhaseExecution(phase_id=PhaseId.STT, status=PhaseStatus.SUCCEEDED, cost_usd=0.05),
        video_id=run.videos[0].video_id,
    )
    vm = RunMatrixViewModel(state=state, registry=registry)
    snap = vm.cost_matrix_snapshot(run)
    assert snap.cells[0][0].status is PhaseStatus.SUCCEEDED
    assert snap.cells[0][0].cost_usd == 0.05
    assert snap.row_totals[0] == 0.05  # somme des phases par-vidéo de la vidéo 0


def test_batch_phase_cost_in_column_total_not_in_cell(
    tmp_path: Path, make_generation_settings: Any
) -> None:
    state, run, registry = _setup(tmp_path, make_generation_settings)
    state.upsert_phase_execution(
        run.id,
        PhaseExecution(
            phase_id=PhaseId.GLOSSARY_RECONCILIATION,
            status=PhaseStatus.SUCCEEDED,
            cost_usd=0.20,
        ),
        video_id=None,
    )
    vm = RunMatrixViewModel(state=state, registry=registry)
    snap = vm.cost_matrix_snapshot(run)
    # colonne 2 = Glossaire (batch) : statut visible, coût cellule None, total colonne = coût run
    assert snap.cells[0][2].status is PhaseStatus.SUCCEEDED
    assert snap.cells[0][2].cost_usd is None
    assert snap.column_totals[2] == 0.20
    assert snap.grand_total == 0.20  # batch compté une seule fois


def test_preview_all_pending(tmp_path: Path, make_generation_settings: Any) -> None:
    state, run, registry = _setup(tmp_path, make_generation_settings)
    vm = RunMatrixViewModel(state=state, registry=registry)
    snap = vm.preview_cost_matrix(run.videos)
    assert len(snap.row_labels) == 2
    assert all(
        cell.status is PhaseStatus.PENDING for row in snap.cells for cell in row
    )
    assert snap.grand_total == 0.0
```

- [ ] **Step 2 : Lancer, vérifier l'échec**

Run : `.venv\Scripts\python.exe -m pytest tests/unit/ui/viewmodels/test_run_matrix.py -v`
Attendu : ÉCHEC (`AttributeError: ... cost_matrix_snapshot`).

- [ ] **Step 3 : Réécrire `run_matrix.py`**

```python
"""ViewModel ``RunMatrixViewModel`` — alimente la matrice générique de coût.

Convertit un ``Run`` + ses ``PhaseExecution`` SQLite en ``CostMatrixSnapshot``
(lignes = vidéos, colonnes = phases). Les phases **batch** (non per-vidéo) affichent
leur statut sur chaque ligne mais leur **coût n'est porté que par le total de
colonne** (coût au niveau du run, ``—`` en cellule) ; le total de ligne ne somme que
les phases par-vidéo. Sans logique Qt.
"""

from __future__ import annotations

from fahmi2.domain.enums import PhaseId, PhaseStatus
from fahmi2.domain.ids import VideoId
from fahmi2.domain.run import Run
from fahmi2.domain.video import VideoExecution
from fahmi2.infra.storage.sqlite_state import PhaseCell, SqliteState
from fahmi2.pipeline.phase_registry import PhaseRegistry
from fahmi2.ui.viewmodels.cost_matrix import CostMatrixCell, CostMatrixSnapshot

_ROW_HEADER = "Vidéo"

_PHASE_SHORT_LABELS: dict[PhaseId, str] = {
    PhaseId.STT: "STT",
    PhaseId.TERM_EXTRACTION: "Termes",
    PhaseId.GLOSSARY_RECONCILIATION: "Glossaire",
    PhaseId.REFORMULATION: "Reformul.",
    PhaseId.STRUCTURATION: "Structur.",
    PhaseId.CONSOLIDATION: "Consolid.",
    PhaseId.TRANSLATION: "Traduction",
    PhaseId.COHERENCE: "Cohérence",
}

_STATUS_LABEL: dict[PhaseStatus, str] = {
    PhaseStatus.PENDING: "en attente",
    PhaseStatus.RUNNING: "en cours",
    PhaseStatus.SUCCEEDED: "terminé",
    PhaseStatus.FAILED: "échec",
    PhaseStatus.SKIPPED: "déjà fait",
}


class RunMatrixViewModel:
    """Construit un ``CostMatrixSnapshot`` à partir de l'état SQLite d'un Run."""

    def __init__(self, *, state: SqliteState, registry: PhaseRegistry) -> None:
        """Construit le viewmodel.

        Args:
            state: Accès SQLite.
            registry: Registre des handlers (ordre des colonnes + per-video).
        """
        self._state = state
        self._registry = registry

    def _phases(self) -> tuple[tuple[PhaseId, bool], ...]:
        """Phases dans l'ordre canonique + drapeau per-vidéo.

        Returns:
            Tuple de ``(phase_id, is_per_video)``.
        """
        return tuple(
            (h.phase_id, h.is_per_video) for h in self._registry.ordered_handlers()
        )

    def cost_matrix_snapshot(self, run: Run) -> CostMatrixSnapshot:
        """Construit la matrice vidéos × phases (statut + coût + totaux).

        Args:
            run: Run en cours ou terminé.

        Returns:
            ``CostMatrixSnapshot`` (coût batch porté par les totaux de colonne).
        """
        phases = self._phases()
        cells_by_key: dict[tuple[PhaseId, VideoId | None], PhaseCell] = {
            (c.phase_id, c.video_id): c for c in self._state.list_phase_cells(run.id)
        }
        return self._build(run.videos, phases, cells_by_key)

    def preview_cost_matrix(
        self, videos: tuple[VideoExecution, ...]
    ) -> CostMatrixSnapshot:
        """Matrice de prévisualisation (toutes phases ``PENDING``, coût 0).

        Args:
            videos: Vidéos détectées.

        Returns:
            ``CostMatrixSnapshot`` sans coût.
        """
        return self._build(videos, self._phases(), {})

    def _build(
        self,
        videos: tuple[VideoExecution, ...],
        phases: tuple[tuple[PhaseId, bool], ...],
        cells_by_key: dict[tuple[PhaseId, VideoId | None], PhaseCell],
    ) -> CostMatrixSnapshot:
        """Assemble le snapshot (cellules + totaux, gestion batch).

        Args:
            videos: Vidéos (lignes).
            phases: Phases + drapeau per-vidéo (colonnes).
            cells_by_key: Statut/coût par ``(phase, vidéo|None)``.

        Returns:
            Le ``CostMatrixSnapshot`` complet.
        """
        column_labels = tuple(_PHASE_SHORT_LABELS.get(p, p.value) for p, _ in phases)
        grid: list[tuple[CostMatrixCell, ...]] = []
        row_totals: list[float] = []
        for video in videos:
            row: list[CostMatrixCell] = []
            row_total = 0.0
            for phase_id, per_video in phases:
                if per_video:
                    pc = cells_by_key.get((phase_id, video.video_id))
                    status = pc.status if pc is not None else PhaseStatus.PENDING
                    cost = pc.cost_usd if pc is not None else 0.0
                    row_total += cost
                    row.append(
                        CostMatrixCell(
                            status=status,
                            cost_usd=cost if pc is not None else None,
                            tooltip=_tooltip(phase_id, status, cost),
                        )
                    )
                else:
                    pc = cells_by_key.get((phase_id, None))
                    status = pc.status if pc is not None else PhaseStatus.PENDING
                    cost = pc.cost_usd if pc is not None else 0.0
                    row.append(
                        CostMatrixCell(
                            status=status,
                            cost_usd=None,  # batch : coût au niveau du run (cf. total)
                            tooltip=_tooltip(phase_id, status, cost, batch=True),
                        )
                    )
            grid.append(tuple(row))
            row_totals.append(row_total)

        column_totals: list[float] = []
        grand_total = sum(row_totals)
        for col, (phase_id, per_video) in enumerate(phases):
            if per_video:
                column_totals.append(
                    sum((cells_by_key.get((phase_id, v.video_id)) or _ZERO).cost_usd
                        for v in videos)
                )
            else:
                batch = cells_by_key.get((phase_id, None))
                batch_cost = batch.cost_usd if batch is not None else 0.0
                column_totals.append(batch_cost)
                grand_total += batch_cost
            del col

        return CostMatrixSnapshot(
            row_header=_ROW_HEADER,
            column_labels=column_labels,
            row_labels=tuple(v.source_path.name for v in videos),
            cells=tuple(grid),
            row_totals=tuple(row_totals),
            column_totals=tuple(column_totals),
            grand_total=grand_total,
        )


_ZERO = PhaseCell(
    phase_id=PhaseId.STT,
    video_id=None,
    status=PhaseStatus.PENDING,
    cost_usd=0.0,
    retry_count=0,
)


def _tooltip(
    phase_id: PhaseId, status: PhaseStatus, cost: float, *, batch: bool = False
) -> str:
    """Construit l'infobulle d'une cellule.

    Args:
        phase_id: Phase.
        status: Statut.
        cost: Coût.
        batch: ``True`` si phase batch (coût au niveau du run).

    Returns:
        Texte d'infobulle.
    """
    label = _STATUS_LABEL.get(status, status.value)
    suffix = " (coût au niveau du run)" if batch else ""
    return f"{phase_id.value} — {label} — coût: ${cost:.4f}{suffix}"
```

- [ ] **Step 4 : Lancer, vérifier le succès**

Run : `.venv\Scripts\python.exe -m pytest tests/unit/ui/viewmodels/test_run_matrix.py -v`
Attendu : PASS (4 tests).

- [ ] **Step 5 : Vérifs (mypy/ruff peuvent signaler des usages restants de l'ancien
  `snapshot`/`MatrixSnapshot` dans le contrôleur — corrigés en Task 3) ; commit
  reporté en fin de Task 3** (le contrôleur casse tant qu'il n'est pas migré).

Run ciblé : `.venv\Scripts\python.exe -m pytest tests/unit/ui/viewmodels/test_run_matrix.py -q` (PASS).

---

## Task 3 : widget + contrôleur + nettoyage

**Files:**
- Modify : `src/fahmi2/ui/features/generation_tab.py`
- Modify : `src/fahmi2/ui/generation_controller.py`
- Delete : `src/fahmi2/ui/widgets/run_matrix_view.py`
- Modify : `tests/unit/ui/test_widgets_smoke.py`
- Modify : `src/fahmi2/ui/theme/light_fluent.qss`

- [ ] **Step 1 : `generation_tab.py` → `CostMatrixView`**

Remplacer l'import `from fahmi2.ui.widgets.run_matrix_view import RunMatrixView` par
`from fahmi2.ui.widgets.cost_matrix_view import CostMatrixView`, et
`self._run_matrix = RunMatrixView(parent=self._widget)` par
`self._run_matrix = CostMatrixView(parent=self._widget)`.

- [ ] **Step 2 : `generation_controller.py` — type + preview + reset + live**

- Remplacer l'import widget : `from fahmi2.ui.widgets.run_matrix_view import RunMatrixView`
  → `from fahmi2.ui.widgets.cost_matrix_view import CostMatrixView` ; type du
  paramètre/attribut `run_matrix: CostMatrixView`.
- `_show_preview_for_project` : remplacer la construction manuelle du `MatrixSnapshot`
  (imports locaux `MatrixCell/MatrixRow/MatrixSnapshot` + boucle `rows`) par :

```python
        matrix_vm = RunMatrixViewModel(state=self._state, registry=self._registry)
        self._run_matrix.apply_snapshot(matrix_vm.preview_cost_matrix(tuple(videos)))
```
  (retirer les imports locaux `PhaseStatus`, `RunId`, `MatrixCell`, `MatrixRow`,
  `MatrixSnapshot` devenus inutiles ; garder `StatsSnapshot`.)

- `_reset_views` : remplacer la construction de `MatrixSnapshot` vide par une matrice
  vide via une constante partagée. Importer en tête
  `from fahmi2.ui.widgets.cost_matrix_view import EMPTY_COST_MATRIX` (cf. Step 4) et :

```python
        self._run_matrix.apply_snapshot(EMPTY_COST_MATRIX)
```
  (retirer l'import local `MatrixSnapshot` + `RunId` si inutile.)

- `_refresh_views` (live) : remplacer `matrix_vm.snapshot(run)` par
  `matrix_vm.cost_matrix_snapshot(run)`.

- [ ] **Step 3 : Supprimer l'ancien widget**

```powershell
git rm src/fahmi2/ui/widgets/run_matrix_view.py
```

- [ ] **Step 4 : Exposer `EMPTY_COST_MATRIX`**

Dans `src/fahmi2/ui/widgets/cost_matrix_view.py`, renommer `_empty_snapshot()` en une
constante publique réutilisable **ou** ajouter, en tête (après les constantes) :

```python
EMPTY_COST_MATRIX = CostMatrixSnapshot(
    row_header="",
    column_labels=(),
    row_labels=(),
    cells=(),
    row_totals=(),
    column_totals=(),
    grand_total=0.0,
)
```

et faire pointer `_empty_snapshot()`/le constructeur dessus
(`CostMatrixView(snapshot or EMPTY_COST_MATRIX)`). Le Lot 3b
(`pedagogy_progress_view._EMPTY_MATRIX`) pourra réutiliser cette constante plus tard
(hors périmètre ici).

- [ ] **Step 5 : `test_widgets_smoke.py` — retirer `RunMatrixView`**

Retirer l'import et le smoke test de `RunMatrixView` (le widget n'existe plus ;
`CostMatrixView` est couvert par `test_cost_matrix_view.py`).

- [ ] **Step 6 : Retirer le QSS `#runMatrix`**

Dans `light_fluent.qss`, supprimer le bloc `#runMatrix` … (la matrice utilise
désormais `#costMatrix`).

- [ ] **Step 7 : `ruff --fix` + suite complète + mypy**

```powershell
.venv\Scripts\python.exe -m ruff check --fix .
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m mypy src tests
```
Attendu : tout vert ; aucune référence résiduelle à `RunMatrixView` / `MatrixSnapshot`.

- [ ] **Step 8 : commit**

```powershell
git add -A
git commit -m @'
feat(ui): matrice Generation migree vers CostMatrixView (cout par cellule + totaux)

RunMatrixViewModel produit un CostMatrixSnapshot (lignes vidéos x colonnes phases,
cout par cellule reel via list_phase_cells, phases batch en total de colonne).
generation_tab/controller utilisent CostMatrixView (apercu/reset/live). Ancien
widget RunMatrixView + MatrixSnapshot + QSS #runMatrix supprimes.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
'@
```

---

## Clôture du Lot 3c

- [ ] `CHANGELOG.md` (Non publié) : « Modifié » (matrice Génération = coût par cellule
  + totaux, composant partagé). Commit `docs(changelog): Lot 3c (dashboard generation)`.
- [ ] Contrôle visuel : onglet Génération → matrice vidéos × phases avec coût par
  cellule (discret) + totaux ligne/colonne/général.
- [ ] Dernier lot : **3d** (estimation granulaire + fourchette ±33 %).

## Self-review

Couvre §3.4 : coût par cellule + totaux (composant partagé), via une requête infra
`list_phase_cells` (la donnée existait). Phases batch gérées (coût en total de
colonne, ``—`` en cellule, infobulle explicite) — totaux construits explicitement
par le viewmodel (pas via `build_cost_matrix`, qui sommerait mal le batch). Pas de
placeholder : code exact. Types cohérents (`PhaseCell`, `cost_matrix_snapshot`,
`preview_cost_matrix`, `EMPTY_COST_MATRIX`). Suppression de `RunMatrixView`/
`MatrixSnapshot`/`#runMatrix` (migration complète). Task 2 et 3 se committent
ensemble (le contrôleur casse entre les deux) — d'où le commit reporté.
