"""Smoke tests des widgets PySide6 (instanciation + propriétés simples).

Vérifie uniquement que les widgets peuvent être construits sans erreur et
que leurs slots/signaux principaux fonctionnent. Pas de rendu visuel testé
en pixel-perfect.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from pytestqt.qtbot import QtBot

from fahmi2.core.errors.severity import Severity
from fahmi2.core.logging.event import LogEvent
from fahmi2.domain.enums import Language, RunStatus
from fahmi2.ui.viewmodels.stats_strip import StatsSnapshot
from fahmi2.ui.widgets.logs_dock import LogsDock
from fahmi2.ui.widgets.project_header_bar import ProjectHeaderBar
from fahmi2.ui.widgets.projects_sidebar import ProjectListEntry, ProjectsSidebar
from fahmi2.ui.widgets.stats_strip import StatsStripWidget


def test_stats_strip_renders_snapshot(qtbot: QtBot) -> None:
    widget = StatsStripWidget()
    qtbot.addWidget(widget)
    started = datetime.now(tz=UTC)
    snapshot = StatsSnapshot(
        run_status=RunStatus.RUNNING,
        videos_total=10,
        videos_completed=3,
        phases_total=5,
        phases_completed=1,
        cost_usd_so_far=0.42,
        cost_ceiling_usd=5.0,
        started_at=started,
        finished_at=None,
        elapsed_seconds=12.5,
        languages=(Language.FR,),
    )
    widget.apply_snapshot(snapshot)


def test_project_header_bar_signals_emit(qtbot: QtBot) -> None:
    widget = ProjectHeaderBar()
    qtbot.addWidget(widget)
    received: list[str] = []
    widget.start_requested.connect(lambda: received.append("start"))
    widget.start_requested.emit()
    assert received == ["start"]


def test_project_header_bar_emits_estimate_cost(qtbot: QtBot) -> None:
    widget = ProjectHeaderBar()
    qtbot.addWidget(widget)
    received: list[str] = []
    widget.estimate_cost_requested.connect(lambda: received.append("estimate"))
    widget.estimate_cost_requested.emit()
    assert received == ["estimate"]


def test_projects_sidebar_select_callback(qtbot: QtBot) -> None:
    widget = ProjectsSidebar()
    qtbot.addWidget(widget)
    selected: list[str] = []
    widget.set_on_project_selected(lambda pid: selected.append(pid.value))
    # set_projects vide est OK
    widget.set_projects([])


def test_projects_sidebar_edit_and_delete_callbacks_attachable(
    qtbot: QtBot,
) -> None:
    widget = ProjectsSidebar()
    qtbot.addWidget(widget)
    edited: list[str] = []
    deleted: list[str] = []
    widget.set_on_edit_requested(lambda pid: edited.append(pid.value))
    widget.set_on_delete_requested(lambda pid: deleted.append(pid.value))
    widget.set_projects([])
    assert edited == []
    assert deleted == []


def test_projects_sidebar_select_project_triggers_callback(
    qtbot: QtBot, tmp_path: object, make_generation_settings: object
) -> None:
    """``select_project`` doit declencher le signal de selection."""
    from datetime import UTC as _UTC  # noqa: PLC0415
    from datetime import datetime as _dt  # noqa: PLC0415
    from pathlib import Path as _Path  # noqa: PLC0415

    from fahmi2.domain.ids import ProjectId  # noqa: PLC0415
    from fahmi2.domain.project import Project  # noqa: PLC0415

    settings = make_generation_settings()  # type: ignore[operator]
    p1 = Project(
        id=ProjectId.new(),
        name="P1",
        workspace_folder=_Path("."),
        created_at=_dt.now(tz=_UTC),
        generation=settings,
    )
    p2 = Project(
        id=ProjectId.new(),
        name="P2",
        workspace_folder=_Path("."),
        created_at=_dt.now(tz=_UTC),
        generation=settings,
    )

    widget = ProjectsSidebar()
    qtbot.addWidget(widget)
    received: list[str] = []
    widget.set_on_project_selected(lambda pid: received.append(pid.value))
    widget.set_projects(
        [
            ProjectListEntry(p1, RunStatus.CREATED, RunStatus.CREATED),
            ProjectListEntry(p2, RunStatus.COMPLETED, RunStatus.RUNNING),
        ]
    )
    widget.select_project(p2.id)
    assert received[-1] == p2.id.value


def test_logs_dock_appends_within_threshold(qtbot: QtBot) -> None:
    dock = LogsDock()
    qtbot.addWidget(dock)
    event = LogEvent(
        timestamp=datetime.now(tz=UTC),
        severity=Severity.INFO,
        code="TEST",
        message="hello",
    )
    dock.append_event(event)


def test_logs_dock_filters_below_threshold(qtbot: QtBot) -> None:
    dock = LogsDock()
    qtbot.addWidget(dock)
    event = LogEvent(
        timestamp=datetime.now(tz=UTC),
        severity=Severity.INFO,
        code="TEST",
        message="hello",
    )
    dock.append_event(event)  # niveau par défaut INFO, OK


# --- Pause / reprise du compteur de durée -----------------------------------


def _make_snapshot(
    *,
    started_at: datetime,
    elapsed_seconds: float,
    run_status: RunStatus,
    finished_at: datetime | None = None,
) -> StatsSnapshot:
    """Helper : construit un ``StatsSnapshot`` minimal."""
    return StatsSnapshot(
        run_status=run_status,
        videos_total=2,
        videos_completed=0,
        phases_total=10,
        phases_completed=0,
        cost_usd_so_far=0.0,
        cost_ceiling_usd=None,
        started_at=started_at,
        finished_at=finished_at,
        elapsed_seconds=elapsed_seconds,
        languages=(),
    )


def test_stats_strip_compute_elapsed_running(qtbot: QtBot) -> None:
    widget = StatsStripWidget()
    qtbot.addWidget(widget)
    started = datetime.now(tz=UTC) - timedelta(seconds=30)
    snap = _make_snapshot(
        started_at=started, elapsed_seconds=30, run_status=RunStatus.RUNNING
    )
    elapsed = widget._compute_displayed_elapsed(snap, started + timedelta(seconds=30))  # noqa: SLF001
    assert 29.5 <= elapsed <= 30.5


def test_stats_strip_compute_elapsed_paused_is_frozen(qtbot: QtBot) -> None:
    """Quand snapshot = PAUSED et _paused_at est défini, la valeur affichée
    est figée à `paused_at - started_at` (moins l'offset cumulé)."""
    widget = StatsStripWidget()
    qtbot.addWidget(widget)
    started = datetime.now(tz=UTC) - timedelta(minutes=2)
    paused_at = started + timedelta(seconds=60)
    widget._paused_at = paused_at  # noqa: SLF001
    snap = _make_snapshot(
        started_at=started, elapsed_seconds=120, run_status=RunStatus.PAUSED
    )
    # Peu importe `now` qui suit : la durée est figée à 60s
    elapsed_now1 = widget._compute_displayed_elapsed(snap, paused_at + timedelta(seconds=5))  # noqa: SLF001
    elapsed_now2 = widget._compute_displayed_elapsed(snap, paused_at + timedelta(seconds=60))  # noqa: SLF001
    assert elapsed_now1 == elapsed_now2 == 60.0


def test_stats_strip_compute_elapsed_running_with_paused_offset(qtbot: QtBot) -> None:
    """Le temps cumulé en pause est retiré du calcul live en RUNNING."""
    widget = StatsStripWidget()
    qtbot.addWidget(widget)
    started = datetime.now(tz=UTC) - timedelta(seconds=120)
    widget._paused_offset_seconds = 30.0  # noqa: SLF001
    snap = _make_snapshot(
        started_at=started, elapsed_seconds=120, run_status=RunStatus.RUNNING
    )
    elapsed = widget._compute_displayed_elapsed(snap, started + timedelta(seconds=120))  # noqa: SLF001
    # 120 (absolu) - 30 (offset) = 90 secondes "actives"
    assert 89.5 <= elapsed <= 90.5


def _paused_at_of(widget: StatsStripWidget) -> object:
    """Lit ``_paused_at`` sans déclencher le narrowing mypy.

    Les tests qui appellent ``apply_snapshot`` font évoluer l'attribut
    privé ; mypy strict garde son narrowing après l'appel, ce qui rend
    les assertions suivantes « unreachable » par erreur. Passer par
    ``getattr`` produit un ``object`` non narrowé.
    """
    return getattr(widget, "_paused_at")  # noqa: B009


def _paused_offset_of(widget: StatsStripWidget) -> float:
    return float(getattr(widget, "_paused_offset_seconds"))  # noqa: B009


def test_stats_strip_pause_tracking_transitions(qtbot: QtBot) -> None:
    """Vérifie qu'un cycle RUNNING -> PAUSED -> RUNNING enregistre bien
    un offset > 0 et libère ``_paused_at``."""
    import time  # noqa: PLC0415

    widget = StatsStripWidget()
    qtbot.addWidget(widget)
    started = datetime.now(tz=UTC)
    widget.apply_snapshot(
        _make_snapshot(
            started_at=started, elapsed_seconds=0, run_status=RunStatus.RUNNING
        )
    )
    assert _paused_at_of(widget) is None
    widget.apply_snapshot(
        _make_snapshot(
            started_at=started, elapsed_seconds=0, run_status=RunStatus.PAUSED
        )
    )
    assert _paused_at_of(widget) is not None
    time.sleep(0.1)
    widget.apply_snapshot(
        _make_snapshot(
            started_at=started, elapsed_seconds=0, run_status=RunStatus.RUNNING
        )
    )
    assert _paused_at_of(widget) is None
    assert _paused_offset_of(widget) >= 0.05


def test_stats_strip_new_run_resets_pause_tracking(qtbot: QtBot) -> None:
    """Reg : un nouveau Run (started_at différent) doit reset le tracking."""
    widget = StatsStripWidget()
    qtbot.addWidget(widget)
    widget._paused_offset_seconds = 42.0  # noqa: SLF001
    widget._paused_at = datetime.now(tz=UTC)  # noqa: SLF001
    widget._last_snapshot = _make_snapshot(  # noqa: SLF001
        started_at=datetime.now(tz=UTC) - timedelta(hours=1),
        elapsed_seconds=3600,
        run_status=RunStatus.PAUSED,
    )
    new_snap = _make_snapshot(
        started_at=datetime.now(tz=UTC),
        elapsed_seconds=0,
        run_status=RunStatus.RUNNING,
    )
    widget.apply_snapshot(new_snap)
    assert _paused_at_of(widget) is None
    assert _paused_offset_of(widget) == 0.0
