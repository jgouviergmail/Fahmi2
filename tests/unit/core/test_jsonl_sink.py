"""Tests du sink fichier JSONL."""

import json
from datetime import UTC, datetime
from pathlib import Path

from fahmi2.core.errors.severity import Severity
from fahmi2.core.logging.event import LogEvent
from fahmi2.core.logging.jsonl_sink import JsonlFileSink


def _evt(code: str = "X", severity: Severity = Severity.INFO) -> LogEvent:
    return LogEvent(
        timestamp=datetime(2026, 5, 19, 12, 0, 0, tzinfo=UTC),
        severity=severity,
        code=code,
        message="m",
    )


def test_jsonl_sink_writes_one_line_per_event(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    sink = JsonlFileSink(path)
    try:
        sink.emit(_evt("A"))
        sink.emit(_evt("B"))
    finally:
        sink.close()

    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["code"] == "A"
    assert json.loads(lines[1])["code"] == "B"


def test_jsonl_sink_creates_parent_dir(tmp_path: Path) -> None:
    path = tmp_path / "sub" / "events.jsonl"
    sink = JsonlFileSink(path)
    sink.close()
    assert path.exists()


def test_jsonl_sink_respects_min_severity(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    sink = JsonlFileSink(path, min_severity=Severity.WARNING)
    try:
        sink.emit(_evt("low", severity=Severity.INFO))
        sink.emit(_evt("high", severity=Severity.WARNING))
    finally:
        sink.close()
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["code"] == "high"


def test_jsonl_sink_can_be_used_as_context_manager(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    with JsonlFileSink(path) as sink:
        sink.emit(_evt())
    assert path.read_text(encoding="utf-8").strip()


def test_jsonl_sink_appends_to_existing_file(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    with JsonlFileSink(path) as sink:
        sink.emit(_evt("first"))
    with JsonlFileSink(path) as sink:
        sink.emit(_evt("second"))
    lines = path.read_text(encoding="utf-8").splitlines()
    assert [json.loads(line)["code"] for line in lines] == ["first", "second"]
