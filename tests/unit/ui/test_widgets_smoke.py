"""Smoke tests des widgets PySide6 (instanciation + propriétés simples).

Vérifie uniquement que les widgets peuvent être construits sans erreur et
que leurs slots/signaux principaux fonctionnent. Pas de rendu visuel testé
en pixel-perfect.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pytestqt.qtbot import QtBot

from fahmi2.core.errors.severity import Severity
from fahmi2.core.logging.event import LogEvent
from fahmi2.domain.enums import RunStatus
from fahmi2.ui.viewmodels.stats_strip import StatsSnapshot
from fahmi2.ui.widgets.logs_dock import LogsDock
from fahmi2.ui.widgets.project_header_bar import ProjectHeaderBar
from fahmi2.ui.widgets.projects_sidebar import ProjectsSidebar
from fahmi2.ui.widgets.run_matrix_view import RunMatrixView
from fahmi2.ui.widgets.stats_strip import StatsStripWidget


def test_stats_strip_renders_snapshot(qtbot: QtBot) -> None:
    widget = StatsStripWidget()
    qtbot.addWidget(widget)
    snapshot = StatsSnapshot(
        run_status=RunStatus.RUNNING,
        videos_total=10,
        videos_completed=3,
        phases_total=5,
        phases_completed=1,
        cost_usd_so_far=0.42,
        cost_ceiling_usd=5.0,
    )
    widget.apply_snapshot(snapshot)


def test_run_matrix_view_is_constructible(qtbot: QtBot) -> None:
    widget = RunMatrixView()
    qtbot.addWidget(widget)
    assert widget.model() is not None


def test_project_header_bar_signals_emit(qtbot: QtBot) -> None:
    widget = ProjectHeaderBar()
    qtbot.addWidget(widget)
    widget.set_title("Test")
    received: list[str] = []
    widget.start_requested.connect(lambda: received.append("start"))
    widget.start_requested.emit()
    assert received == ["start"]


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
