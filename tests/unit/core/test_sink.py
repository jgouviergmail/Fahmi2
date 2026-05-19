"""Tests de l'interface LogSink et de la redaction des secrets."""

from datetime import UTC, datetime

import pytest

from fahmi2.core.errors.severity import Severity
from fahmi2.core.logging.event import LogEvent
from fahmi2.core.logging.sink import (
    LogSink,
    MinSeverityFilter,
    SecretRedactor,
    register_secret,
    unregister_secret,
)


class _CapturingSink(LogSink):
    def __init__(self, min_severity: Severity = Severity.INFO) -> None:
        super().__init__(min_severity=min_severity)
        self.events: list[LogEvent] = []

    def _write(self, event: LogEvent) -> None:
        self.events.append(event)


def _evt(
    message: str = "msg",
    severity: Severity = Severity.INFO,
    extra: dict[str, object] | None = None,
) -> LogEvent:
    return LogEvent(
        timestamp=datetime.now(tz=UTC),
        severity=severity,
        code="X",
        message=message,
        extra=extra or {},
    )


def test_sink_emits_event_through_filter() -> None:
    sink = _CapturingSink(min_severity=Severity.INFO)
    sink.emit(_evt("hello"))
    assert len(sink.events) == 1


def test_min_severity_filter_drops_below() -> None:
    flt = MinSeverityFilter(Severity.WARNING)
    assert not flt.allow(_evt(severity=Severity.INFO))
    assert flt.allow(_evt(severity=Severity.WARNING))
    assert flt.allow(_evt(severity=Severity.ERROR))


def test_sink_drops_below_min_severity() -> None:
    sink = _CapturingSink(min_severity=Severity.WARNING)
    sink.emit(_evt(severity=Severity.INFO))
    assert sink.events == []


def test_secret_redactor_replaces_registered_value() -> None:
    register_secret("sk-abc123")
    try:
        redactor = SecretRedactor()
        assert redactor.redact("voici sk-abc123 dans un texte") == "voici *** dans un texte"
    finally:
        unregister_secret("sk-abc123")


def test_sink_redacts_secrets_in_message_and_extra() -> None:
    register_secret("sk-abc123")
    try:
        sink = _CapturingSink()
        sink.emit(_evt(message="key=sk-abc123", extra={"prompt": "use sk-abc123"}))
        assert "sk-abc123" not in sink.events[0].message
        assert "sk-abc123" not in sink.events[0].extra["prompt"]
    finally:
        unregister_secret("sk-abc123")


def test_register_secret_rejects_empty_or_short() -> None:
    with pytest.raises(ValueError):
        register_secret("")
    with pytest.raises(ValueError):
        register_secret("ab")


def test_redactor_handles_nested_structures() -> None:
    register_secret("supersecret")
    try:
        redactor = SecretRedactor()
        assert redactor.redact_value({"k": "supersecret", "nested": ["supersecret"]}) == {
            "k": "***",
            "nested": ["***"],
        }
    finally:
        unregister_secret("supersecret")
