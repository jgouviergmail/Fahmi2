"""Tests du mapping ``PipelineEvent`` → ``LogEvent`` (run_controller).

Vérifie en particulier que les phases en échec exposent le détail
d'erreur (code, user_message, technical_details) dans le message du
``LogEvent`` et dans son ``extra``.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fahmi2.core.errors.error_info import ErrorInfo
from fahmi2.core.errors.severity import Severity
from fahmi2.domain.enums import PhaseId, PhaseStatus, RunStatus
from fahmi2.domain.ids import RunId, VideoId
from fahmi2.pipeline.events import (
    PhaseFinished,
    PhaseStarted,
    RetryAttempt,
    RunFinished,
    RunStarted,
)
from fahmi2.ui.run_controller import _format_technical_details, _to_log_event


def _now() -> datetime:
    return datetime.now(tz=UTC)


def test_phase_finished_succeeded_log_message() -> None:
    event = PhaseFinished(
        timestamp=_now(),
        run_id=RunId.new(),
        phase_id=PhaseId.STT,
        video_id=None,
        final_status=PhaseStatus.SUCCEEDED,
        cost_usd=0.0123,
        error=None,
    )
    log = _to_log_event(event)
    assert log.severity is Severity.INFO
    assert "phase_0_stt" in log.message
    assert "succeeded" in log.message
    assert "0.0123" in log.message
    # Pas de detail d'erreur quand SUCCEEDED
    assert "error_code" not in log.extra


def test_phase_finished_failed_log_exposes_error_details() -> None:
    """Reg : le panneau Logs DOIT afficher le code + user_message + detail
    technique quand la phase est en echec."""
    error = ErrorInfo(
        code="LLM.INVALID_JSON",
        user_message="La réponse du LLM pour phase_5_consolidation n'est pas du JSON valide.",
        severity=Severity.ERROR,
        technical_details={
            "phase_id": "phase_5_consolidation",
            "raw_content": "Voici le résumé : { ...",
        },
    )
    event = PhaseFinished(
        timestamp=_now(),
        run_id=RunId.new(),
        phase_id=PhaseId.CONSOLIDATION,
        video_id=None,
        final_status=PhaseStatus.FAILED,
        cost_usd=0.0042,
        error=error,
    )
    log = _to_log_event(event)
    assert log.severity is Severity.ERROR
    # Le message doit contenir tous les details essentiels
    assert "phase_5_consolidation" in log.message
    assert "failed" in log.message
    assert "LLM.INVALID_JSON" in log.message
    assert "La réponse du LLM" in log.message
    assert "raw_content=" in log.message
    # Extra : tout le detail technique pour le fichier JSONL
    assert log.extra["error_code"] == "LLM.INVALID_JSON"
    assert "raw_content" in log.extra["error_technical_details"]


def test_phase_finished_failed_log_includes_traceback_in_extra() -> None:
    error = ErrorInfo(
        code="STORAGE.STRUCTURED_MISSING",
        user_message="Le document structuré est introuvable.",
        severity=Severity.ERROR,
        technical_details={"path": "/tmp/missing.md"},
        traceback="Traceback (most recent call last):\n  ...",
    )
    event = PhaseFinished(
        timestamp=_now(),
        run_id=RunId.new(),
        phase_id=PhaseId.CONSOLIDATION,
        video_id=None,
        final_status=PhaseStatus.FAILED,
        cost_usd=0.0,
        error=error,
    )
    log = _to_log_event(event)
    assert "error_traceback" in log.extra
    assert "Traceback" in str(log.extra["error_traceback"])


def test_retry_attempt_log_includes_user_message() -> None:
    error = ErrorInfo(
        code="LLM.RATE_LIMIT",
        user_message="Quota DeepSeek atteint, réessai automatique.",
        severity=Severity.WARNING,
    )
    event = RetryAttempt(
        timestamp=_now(),
        run_id=RunId.new(),
        phase_id=PhaseId.REFORMULATION,
        video_id=VideoId.new(),
        attempt=2,
        delay_seconds=4.0,
        error=error,
    )
    log = _to_log_event(event)
    assert log.severity is Severity.WARNING
    assert "LLM.RATE_LIMIT" in log.message
    assert "Quota DeepSeek atteint" in log.message
    assert log.extra["error_code"] == "LLM.RATE_LIMIT"


def test_run_started_and_finished_logs_unchanged() -> None:
    rid = RunId.new()
    started = _to_log_event(RunStarted(timestamp=_now(), run_id=rid))
    assert started.severity is Severity.INFO
    assert "démarré" in started.message
    finished_ok = _to_log_event(
        RunFinished(timestamp=_now(), run_id=rid, final_status=RunStatus.COMPLETED)
    )
    assert finished_ok.severity is Severity.INFO
    finished_failed = _to_log_event(
        RunFinished(timestamp=_now(), run_id=rid, final_status=RunStatus.FAILED)
    )
    assert finished_failed.severity is Severity.WARNING


def test_phase_started_log_format() -> None:
    event = PhaseStarted(
        timestamp=_now(),
        run_id=RunId.new(),
        phase_id=PhaseId.STT,
        video_id=VideoId.new(),
    )
    log = _to_log_event(event)
    assert log.severity is Severity.INFO
    assert "phase_0_stt" in log.message


def test_format_technical_details_empty() -> None:
    assert _format_technical_details({}) == ""


def test_format_technical_details_truncates_long_values() -> None:
    long_value = "x" * 500
    out = _format_technical_details({"raw": long_value})
    assert out.startswith("raw=")
    assert len(out) <= 250  # "raw=" + 197 chars + "…" + marge
    assert "…" in out


def test_format_technical_details_compact_form() -> None:
    out = _format_technical_details({"k1": "v1", "k2": 42})
    assert "k1=v1" in out
    assert "k2=42" in out
