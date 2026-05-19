"""Tests de l'énumération Severity."""

from fahmi2.core.errors.severity import Severity


def test_severity_has_four_levels() -> None:
    assert {str(s) for s in Severity} == {"info", "warning", "error", "fatal"}


def test_severity_ordering() -> None:
    assert Severity.INFO < Severity.WARNING < Severity.ERROR < Severity.FATAL


def test_severity_from_string() -> None:
    assert Severity("warning") is Severity.WARNING  # type: ignore[arg-type]


def test_severity_case_insensitive_from_string() -> None:
    assert Severity("WARNING") is Severity.WARNING  # type: ignore[arg-type]
