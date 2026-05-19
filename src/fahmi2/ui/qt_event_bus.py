"""Adaptateur Qt de :py:class:`EventBus` pour bridger worker → UI thread.

``QtEventBus`` hérite l'interface :py:class:`EventBus` (subscribe/publish) tout
en exposant un Signal Qt ``event_emitted`` qui est émis sur le thread courant.
La connection ``connect(..., Qt.QueuedConnection)`` côté UI permet d'amener
sans race les événements du worker vers le main thread.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from fahmi2.pipeline.event_bus import EventBus
from fahmi2.pipeline.events import PipelineEvent


class QtEventBus(QObject, EventBus):
    """``EventBus`` Qt-aware émettant un Signal pour chaque publication."""

    event_emitted = Signal(object)

    def __init__(self, parent: QObject | None = None) -> None:
        """Construit le bus.

        Args:
            parent: Parent Qt optionnel.
        """
        QObject.__init__(self, parent)
        EventBus.__init__(self)

    def publish(self, event: PipelineEvent) -> None:
        """Distribue ``event`` aux abonnés Python ET émet le Signal Qt.

        Args:
            event: Événement à publier.
        """
        super().publish(event)
        self.event_emitted.emit(event)
