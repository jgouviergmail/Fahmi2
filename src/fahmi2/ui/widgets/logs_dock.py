"""Widget ``LogsDock`` — panneau ancré affichant les logs live du run.

Chaque ligne de log est rendue en HTML (texte enrichi) pour pouvoir colorer
les éléments par sévérité, conserver la mise en forme monospace de la zone
horodate / code / message, et faciliter le suivi visuel en cours de run.
"""

from __future__ import annotations

from html import escape

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDockWidget,
    QHBoxLayout,
    QLabel,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from fahmi2.core.errors.severity import Severity
from fahmi2.core.logging.event import LogEvent

_SEVERITY_CHOICES = [Severity.INFO, Severity.WARNING, Severity.ERROR, Severity.FATAL]

# Couleurs et libellés FR par sévérité — alignés sur le thème Clair Fluent.
_SEVERITY_STYLE: dict[Severity, tuple[str, str]] = {
    Severity.INFO: ("#57606a", "INFO"),
    Severity.WARNING: ("#b45309", "WARN"),
    Severity.ERROR: ("#cf222e", "ERREUR"),
    Severity.FATAL: ("#a30713", "FATAL"),
}


class LogsDock(QDockWidget):
    """Panneau de logs (filtrage par sévérité, rendu HTML coloré)."""

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
        container.setObjectName("logsDockContainer")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(6)

        header_row = QHBoxLayout()
        header_row.setSpacing(8)
        header_row.addWidget(QLabel("Niveau minimum :", container))
        self._level_combo = QComboBox(container)
        for sev in _SEVERITY_CHOICES:
            self._level_combo.addItem(_SEVERITY_STYLE[sev][1], sev)
        self._level_combo.setCurrentIndex(0)
        self._level_combo.currentIndexChanged.connect(self._on_level_changed)
        header_row.addWidget(self._level_combo)
        header_row.addStretch(1)
        layout.addLayout(header_row)

        self._text = QTextEdit(container)
        self._text.setObjectName("logsDockArea")
        self._text.setReadOnly(True)
        self._text.setAcceptRichText(True)
        layout.addWidget(self._text)
        self.setWidget(container)

    def append_event(self, event: LogEvent) -> None:
        """Ajoute un événement de log s'il dépasse le seuil de sévérité.

        Les sauts de ligne (``\\n``) dans le message sont convertis en
        ``<br>`` pour préserver la lisibilité quand un événement a un
        détail multi-ligne (typiquement une erreur de phase avec code,
        user_message et technical_details).

        Args:
            event: Événement à afficher.
        """
        if event.severity < self._min_severity:
            return
        color, label = _SEVERITY_STYLE.get(
            event.severity, _SEVERITY_STYLE[Severity.INFO]
        )
        time_str = event.timestamp.strftime("%H:%M:%S")
        message_html = escape(event.message).replace("\n", "<br>")
        html = (
            f'<span style="color:#8b95a1;">{escape(time_str)}</span> '
            f'<span style="color:{color}; font-weight:600;">{escape(label):<7}</span> '
            f'<span style="color:#0a4f93;">{escape(event.code)}</span> '
            f'<span style="color:#1f2328;">— {message_html}</span>'
        )
        self._text.append(html)

    def _on_level_changed(self, index: int) -> None:
        """Slot interne : met à jour le filtre de sévérité minimale.

        Args:
            index: Index du combo.
        """
        self._min_severity = _SEVERITY_CHOICES[index]
