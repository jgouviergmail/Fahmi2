"""Tests de la hiérarchie d'exceptions Fahmi2."""

from fahmi2.core.errors.error_info import ErrorInfo
from fahmi2.core.errors.exceptions import (
    BudgetExceededError,
    ConfigError,
    Fahmi2Error,
    FFmpegError,
    LLMError,
    PausedError,
    PermanentError,
    StorageError,
    STTError,
    TransientError,
)
from fahmi2.core.errors.severity import Severity


def test_fahmi2_error_carries_code_and_severity() -> None:
    err = Fahmi2Error(code="TEST.X", user_message="oups", severity=Severity.ERROR)
    assert err.code == "TEST.X"
    assert err.user_message == "oups"
    assert err.severity is Severity.ERROR
    assert err.technical_details == {}


def test_fahmi2_error_accepts_technical_details() -> None:
    err = Fahmi2Error(
        code="TEST.X",
        user_message="oups",
        severity=Severity.ERROR,
        technical_details={"status_code": 503},
    )
    assert err.technical_details["status_code"] == 503


def test_fahmi2_error_str_includes_code_and_message() -> None:
    err = Fahmi2Error(code="TEST.X", user_message="oups", severity=Severity.ERROR)
    assert "TEST.X" in str(err)
    assert "oups" in str(err)


def test_transient_and_permanent_are_subclasses() -> None:
    assert issubclass(TransientError, Fahmi2Error)
    assert issubclass(PermanentError, Fahmi2Error)


def test_domain_specific_errors_inherit_from_base() -> None:
    for cls in (STTError, LLMError, FFmpegError, StorageError, ConfigError):
        assert issubclass(cls, Fahmi2Error)


def test_budget_exceeded_is_distinct() -> None:
    err = BudgetExceededError(
        code="BUDGET.EXCEEDED",
        user_message="plafond dépassé",
        severity=Severity.WARNING,
    )
    assert isinstance(err, Fahmi2Error)
    assert not isinstance(err, TransientError)


def test_paused_error_is_distinct() -> None:
    err = PausedError(
        code="RUN.PAUSED",
        user_message="pause demandée",
        severity=Severity.INFO,
    )
    assert isinstance(err, Fahmi2Error)


def test_error_info_serializes_to_dict() -> None:
    info = ErrorInfo(
        code="TEST.X",
        user_message="oups",
        severity=Severity.ERROR,
        technical_details={"k": "v"},
        traceback="trace…",
    )
    payload = info.to_dict()
    assert payload["code"] == "TEST.X"
    assert payload["severity"] == "error"
    assert payload["technical_details"] == {"k": "v"}
    assert payload["traceback"] == "trace…"


def test_error_info_from_exception_captures_traceback() -> None:
    try:
        raise Fahmi2Error(
            code="TEST.X",
            user_message="oups",
            severity=Severity.ERROR,
            technical_details={"k": "v"},
        )
    except Fahmi2Error as exc:
        info = ErrorInfo.from_exception(exc)
    assert info.code == "TEST.X"
    assert info.user_message == "oups"
    assert info.severity is Severity.ERROR
    assert "TEST.X" in (info.traceback or "")


def test_error_info_from_arbitrary_exception() -> None:
    try:
        raise ValueError("plain")
    except ValueError as exc:
        info = ErrorInfo.from_exception(exc)
    assert info.code == "UNEXPECTED.VALUEERROR"
    assert info.severity is Severity.ERROR
    assert "plain" in info.user_message
