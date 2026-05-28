"""Tests du helper d'export UI partagé (choix de format + écriture/erreurs/log)."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtWidgets import QWidget
from pytestqt.qtbot import QtBot

from fahmi2.app.document_export import DocumentExportResult
from fahmi2.core.errors.exceptions import ConfigError
from fahmi2.core.errors.severity import Severity
from fahmi2.core.logging.event import LogEvent
from fahmi2.domain.enums import ExportFormat
from fahmi2.ui._export_ui import choose_export_format, run_document_export
from fahmi2.ui.pedagogy_labels import export_labels
from fahmi2.ui.widgets.logs_dock import LogsDock

_MOD = "fahmi2.ui._export_ui"
# Snapshot des libellés au moment de l'import (la traduction est résolue à
# l'appel ; ici la langue active est la source FR — c'est ce qu'attendent
# les assertions sur les libellés exacts).
EXPORT_LABELS = export_labels()


def test_choose_returns_none_when_no_format(
    qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
) -> None:
    win = QWidget()
    qtbot.addWidget(win)
    monkeypatch.setattr(f"{_MOD}.QMessageBox.information", lambda *a, **k: None)
    assert (
        choose_export_format(
            window=win, configured_formats=frozenset(), label_by_format=EXPORT_LABELS
        )
        is None
    )


def test_choose_returns_picked_format(
    qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
) -> None:
    win = QWidget()
    qtbot.addWidget(win)
    monkeypatch.setattr(
        f"{_MOD}.QInputDialog.getItem",
        lambda *a, **k: (EXPORT_LABELS[ExportFormat.PDF], True),
    )
    fmt = choose_export_format(
        window=win,
        configured_formats=frozenset({ExportFormat.PDF, ExportFormat.HTML}),
        label_by_format=EXPORT_LABELS,
    )
    assert fmt is ExportFormat.PDF


def test_run_writes_and_logs(
    qtbot: QtBot, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    win = QWidget()
    qtbot.addWidget(win)
    logs = LogsDock(win)
    events: list[LogEvent] = []
    monkeypatch.setattr(logs, "append_event", events.append)
    monkeypatch.setattr(
        f"{_MOD}.QFileDialog.getExistingDirectory", lambda *a, **k: str(tmp_path)
    )
    monkeypatch.setattr(f"{_MOD}.QMessageBox.information", lambda *a, **k: None)
    result = DocumentExportResult(output_paths=(tmp_path / "a.md", tmp_path / "b.md"))
    run_document_export(
        window=win, logs_dock=logs, label="Markdown", exporter=lambda d: result
    )
    assert len(events) == 1
    assert events[0].code == "DOCUMENTS_EXPORTED"


def test_run_cancel_when_no_directory(
    qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
) -> None:
    win = QWidget()
    qtbot.addWidget(win)
    logs = LogsDock(win)
    events: list[LogEvent] = []
    monkeypatch.setattr(logs, "append_event", events.append)
    monkeypatch.setattr(f"{_MOD}.QFileDialog.getExistingDirectory", lambda *a, **k: "")
    called = False

    def _exporter(_d: Path) -> DocumentExportResult:
        nonlocal called
        called = True
        return DocumentExportResult(output_paths=())

    run_document_export(window=win, logs_dock=logs, label="PDF", exporter=_exporter)
    assert not called
    assert events == []


def test_run_reports_fahmi2_error(
    qtbot: QtBot, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    win = QWidget()
    qtbot.addWidget(win)
    logs = LogsDock(win)
    captured: list[str] = []
    monkeypatch.setattr(
        f"{_MOD}.QFileDialog.getExistingDirectory", lambda *a, **k: str(tmp_path)
    )
    monkeypatch.setattr(
        f"{_MOD}.QMessageBox.critical", lambda *a, **k: captured.append(a[2])
    )

    def _boom(_d: Path) -> DocumentExportResult:
        raise ConfigError(
            code="EXPORT.NO_PDF_FONT",
            user_message="pas de police",
            severity=Severity.ERROR,
        )

    run_document_export(window=win, logs_dock=logs, label="PDF", exporter=_boom)
    assert captured and "EXPORT.NO_PDF_FONT" in captured[0]
