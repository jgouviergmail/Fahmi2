"""Tests du filtrage par niveau du LogsDock."""

from __future__ import annotations

from datetime import UTC, datetime

from pytestqt.qtbot import QtBot

from fahmi2.core.errors.severity import Severity
from fahmi2.core.logging.event import LogEvent
from fahmi2.ui.widgets.logs_dock import LogsDock

# Index du combo de niveau (ordre _SEVERITY_CHOICES : INFO, WARN, ERREUR, FATAL).
_LEVEL_INFO = 0
_LEVEL_ERROR = 2


def _event(severity: Severity, code: str) -> LogEvent:
    return LogEvent(
        timestamp=datetime.now(tz=UTC), severity=severity, code=code, message="m"
    )


def test_min_level_filters_existing_display(qtbot: QtBot) -> None:
    dock = LogsDock()
    qtbot.addWidget(dock)
    dock.append_event(_event(Severity.INFO, "XCODEINFO"))
    dock.append_event(_event(Severity.ERROR, "XCODEERR"))
    # Niveau INFO par défaut : les deux events sont affichés.
    assert "XCODEINFO" in dock._text.toPlainText()  # noqa: SLF001
    assert "XCODEERR" in dock._text.toPlainText()  # noqa: SLF001
    # Monter le seuil à ERREUR re-filtre l'affichage existant (l'INFO disparaît).
    dock._level_combo.setCurrentIndex(_LEVEL_ERROR)  # noqa: SLF001
    text = dock._text.toPlainText()  # noqa: SLF001
    assert "XCODEINFO" not in text
    assert "XCODEERR" in text


def test_lowering_level_restores_hidden_events(qtbot: QtBot) -> None:
    dock = LogsDock()
    qtbot.addWidget(dock)
    dock._level_combo.setCurrentIndex(_LEVEL_ERROR)  # noqa: SLF001
    dock.append_event(_event(Severity.INFO, "XCODEINFO"))  # sous le seuil
    assert "XCODEINFO" not in dock._text.toPlainText()  # noqa: SLF001
    # Rebaisser le seuil à INFO : l'event masqué réapparaît (il était conservé).
    dock._level_combo.setCurrentIndex(_LEVEL_INFO)  # noqa: SLF001
    assert "XCODEINFO" in dock._text.toPlainText()  # noqa: SLF001
