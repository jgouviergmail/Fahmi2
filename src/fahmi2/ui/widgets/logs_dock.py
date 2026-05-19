"""Widget ``LogsDock`` — panneau ancré affichant les logs live du run."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDockWidget,
    QHBoxLayout,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from fahmi2.core.errors.severity import Severity
from fahmi2.core.logging.event import LogEvent

_SEVERITY_CHOICES = [Severity.INFO, Severity.WARNING, Severity.ERROR, Severity.FATAL]


class LogsDock(QDockWidget):
    """Panneau de logs (filtrage par sévérité)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Construit le dock.

        Args:
            parent: Parent Qt optionnel.
        """
        super().__init__("Logs", parent)
        self.setAllowedAreas(
            Qt.DockWidgetArea.BottomDockWidgetArea
            | Qt.DockWidgetArea.RightDockWidgetArea
        )
        self._min_severity = Severity.INFO

        container = QWidget(self)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(4, 4, 4, 4)

        header_row = QHBoxLayout()
        self._level_combo = QComboBox(container)
        for sev in _SEVERITY_CHOICES:
            self._level_combo.addItem(sev.name, sev)
        self._level_combo.setCurrentIndex(0)
        self._level_combo.currentIndexChanged.connect(self._on_level_changed)
        header_row.addWidget(self._level_combo)
        header_row.addStretch(1)
        layout.addLayout(header_row)

        self._text = QPlainTextEdit(container)
        self._text.setReadOnly(True)
        layout.addWidget(self._text)
        self.setWidget(container)

    def append_event(self, event: LogEvent) -> None:
        """Ajoute un événement de log s'il dépasse le seuil de sévérité.

        Args:
            event: Événement à afficher.
        """
        if event.severity < self._min_severity:
            return
        line = (
            f"{event.timestamp.isoformat()} {event.severity.name:<7} "
            f"{event.code} — {event.message}"
        )
        self._text.appendPlainText(line)

    def _on_level_changed(self, index: int) -> None:
        """Slot interne : met à jour le filtre de sévérité minimale.

        Args:
            index: Index du combo.
        """
        self._min_severity = _SEVERITY_CHOICES[index]
