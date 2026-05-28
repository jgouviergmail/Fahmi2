"""Widget ``LogsDock`` — panneau ancré affichant les logs live du run.

Chaque ligne de log est rendue en HTML (texte enrichi) pour pouvoir colorer
les éléments par sévérité, conserver la mise en forme monospace de la zone
horodate / code / message, et faciliter le suivi visuel en cours de run.
"""

from __future__ import annotations

from html import escape
from typing import cast

from PySide6.QtCore import QT_TRANSLATE_NOOP, QCoreApplication, Qt
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

#: Couleurs et libellés **sources** par sévérité — alignés sur le thème
#: Clair Fluent. Les libellés sont marqués par :func:`QT_TRANSLATE_NOOP`
#: pour extraction ; la résolution effective passe par
#: :func:`_severity_label` à l'usage (le ``QTranslator`` n'est pas installé
#: à l'import du module).
_SEVERITY_STYLE: dict[Severity, tuple[str, str]] = {
    Severity.INFO: ("#57606a", cast(str, QT_TRANSLATE_NOOP("LogsDock", "INFO"))),
    Severity.WARNING: ("#b45309", cast(str, QT_TRANSLATE_NOOP("LogsDock", "WARN"))),
    Severity.ERROR: ("#cf222e", cast(str, QT_TRANSLATE_NOOP("LogsDock", "ERREUR"))),
    Severity.FATAL: ("#a30713", cast(str, QT_TRANSLATE_NOOP("LogsDock", "FATAL"))),
}


def _severity_label(severity: Severity) -> str:
    """Libellé traduit d'une sévérité (combo + rendu HTML d'une ligne)."""
    _, source = _SEVERITY_STYLE.get(severity, _SEVERITY_STYLE[Severity.INFO])
    return QCoreApplication.translate("LogsDock", source)


class LogsDock(QDockWidget):
    """Panneau de logs (filtrage par sévérité, rendu HTML coloré)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Construit le dock.

        Args:
            parent: Parent Qt optionnel.
        """
        # ``self.tr()`` n'est pas accessible avant ``super().__init__()`` ;
        # on passe par ``QCoreApplication.translate(<context>, ...)`` qui
        # est extrait par ``pyside6-lupdate`` au même titre.
        super().__init__(QCoreApplication.translate("LogsDock", "Logs"), parent)
        self.setAllowedAreas(
            Qt.DockWidgetArea.BottomDockWidgetArea
            | Qt.DockWidgetArea.RightDockWidgetArea
        )
        self._min_severity = Severity.INFO
        # Tous les events reçus sont conservés : changer le niveau minimum
        # re-filtre l'affichage (les events sous le seuil sont masqués, pas perdus).
        self._events: list[LogEvent] = []

        container = QWidget(self)
        container.setObjectName("logsDockContainer")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(6)

        header_row = QHBoxLayout()
        header_row.setSpacing(8)
        header_row.addWidget(QLabel(self.tr("Niveau minimum"), container))
        self._level_combo = QComboBox(container)
        for sev in _SEVERITY_CHOICES:
            self._level_combo.addItem(_severity_label(sev), sev)
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
        """Mémorise un événement de log et l'affiche s'il dépasse le seuil.

        L'event est toujours conservé (pour pouvoir réapparaître si l'on
        abaisse le niveau minimum), mais n'est rendu que si sa sévérité
        atteint le seuil courant.

        Args:
            event: Événement à mémoriser/afficher.
        """
        self._events.append(event)
        if event.severity >= self._min_severity:
            self._text.append(self._format_event(event))

    @staticmethod
    def _format_event(event: LogEvent) -> str:
        """Met en forme un événement en ligne HTML colorée par sévérité.

        Les sauts de ligne (``\\n``) du message sont convertis en ``<br>`` pour
        préserver la lisibilité d'un détail multi-ligne (code + user_message +
        technical_details d'une erreur de phase).

        Args:
            event: Événement à formater.

        Returns:
            La ligne HTML.
        """
        color, _source_label = _SEVERITY_STYLE.get(
            event.severity, _SEVERITY_STYLE[Severity.INFO]
        )
        label = _severity_label(event.severity)
        time_str = event.timestamp.strftime("%H:%M:%S")
        message_html = escape(event.message).replace("\n", "<br>")
        return (
            f'<span style="color:#8b95a1;">{escape(time_str)}</span> '
            f'<span style="color:{color}; font-weight:600;">{escape(label):<7}</span> '
            f'<span style="color:#0a4f93;">{escape(event.code)}</span> '
            f'<span style="color:#1f2328;">— {message_html}</span>'
        )

    def _on_level_changed(self, index: int) -> None:
        """Slot interne : change le seuil et re-filtre l'affichage existant.

        Args:
            index: Index du combo.
        """
        self._min_severity = _SEVERITY_CHOICES[index]
        self._rerender()

    def _rerender(self) -> None:
        """Réaffiche tous les events mémorisés au-dessus du seuil courant."""
        self._text.clear()
        for event in self._events:
            if event.severity >= self._min_severity:
                self._text.append(self._format_event(event))
