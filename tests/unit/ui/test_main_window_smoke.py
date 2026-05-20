"""Smoke test du MainWindow et du QtEventBus."""

from __future__ import annotations

from datetime import UTC, datetime

from pytestqt.qtbot import QtBot

from fahmi2.domain.ids import RunId
from fahmi2.pipeline.events import RunStarted
from fahmi2.ui.main_window import MainWindow
from fahmi2.ui.qt_event_bus import QtEventBus


def test_main_window_constructs_and_shows(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    assert window.projects_sidebar is not None
    assert window.logs_dock is not None


def test_main_window_exposes_prompts_editor_callback(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    received: list[str] = []
    window.set_on_open_prompts_editor(lambda: received.append("open"))
    window._open_prompts_action.triggered.emit()  # noqa: SLF001
    assert received == ["open"]


def test_qt_event_bus_publishes_and_emits(qtbot: QtBot) -> None:
    bus = QtEventBus()
    received_python: list[object] = []
    received_qt: list[object] = []
    bus.subscribe(received_python.append)
    bus.event_emitted.connect(received_qt.append)

    event = RunStarted(timestamp=datetime.now(tz=UTC), run_id=RunId.new())
    bus.publish(event)

    assert received_python == [event]
    assert received_qt == [event]
    del qtbot  # silence linter unused
