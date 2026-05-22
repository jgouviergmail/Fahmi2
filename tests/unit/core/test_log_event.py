"""Tests de la dataclass LogEvent."""

from datetime import UTC, datetime

from fahmi2.core.errors.severity import Severity
from fahmi2.core.logging.event import LogEvent


def test_log_event_minimal() -> None:
    ts = datetime.now(tz=UTC)
    ev = LogEvent(timestamp=ts, severity=Severity.INFO, code="X", message="hello")
    assert ev.timestamp == ts
    assert ev.severity is Severity.INFO
    assert ev.code == "X"
    assert ev.message == "hello"
    assert ev.run_id is None
    assert ev.extra == {}


def test_log_event_serializes_to_dict() -> None:
    ts = datetime(2026, 5, 19, 12, 0, 0, tzinfo=UTC)
    ev = LogEvent(
        timestamp=ts,
        severity=Severity.WARNING,
        code="PHASE_STARTED",
        message="…",
        run_id="01HABC",
        phase_id="phase_3_reformulation",
        source_id="01VID",
        extra={"tokens": 1234},
    )
    payload = ev.to_dict()
    assert payload["timestamp"] == "2026-05-19T12:00:00+00:00"
    assert payload["severity"] == "warning"
    assert payload["code"] == "PHASE_STARTED"
    assert payload["run_id"] == "01HABC"
    assert payload["phase_id"] == "phase_3_reformulation"
    assert payload["source_id"] == "01VID"
    assert payload["extra"] == {"tokens": 1234}


def test_log_event_to_dict_keeps_none_optionals() -> None:
    ts = datetime.now(tz=UTC)
    ev = LogEvent(timestamp=ts, severity=Severity.INFO, code="X", message="m")
    payload = ev.to_dict()
    assert payload["run_id"] is None
    assert payload["phase_id"] is None
    assert payload["source_id"] is None
