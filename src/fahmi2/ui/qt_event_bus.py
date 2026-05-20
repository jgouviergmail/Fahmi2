"""Adaptateurs Qt de :py:class:`EventBus` pour bridger worker → UI thread.

``QtEventBus`` (génération) et ``PedagogyQtEventBus`` (pédagogie) héritent
l'interface :py:class:`EventBus` (subscribe/publish) tout en exposant un Signal Qt
``event_emitted`` émis sur le thread courant. La connection
``connect(..., Qt.QueuedConnection)`` côté UI permet d'amener sans race les
événements du worker vers le main thread. Deux classes concrètes (plutôt qu'une
générique) pour éviter les écueils ``QObject`` + ``Generic`` paramétré.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from fahmi2.pedagogy.events import PedagogyEvent
from fahmi2.pipeline.event_bus import EventBus
from fahmi2.pipeline.events import PipelineEvent


class QtEventBus(QObject, EventBus[PipelineEvent]):
    """``EventBus[PipelineEvent]`` Qt-aware émettant un Signal par publication."""

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


class PedagogyQtEventBus(QObject, EventBus[PedagogyEvent]):
    """``EventBus[PedagogyEvent]`` Qt-aware (parallèle à ``QtEventBus``)."""

    event_emitted = Signal(object)

    def __init__(self, parent: QObject | None = None) -> None:
        """Construit le bus.

        Args:
            parent: Parent Qt optionnel.
        """
        QObject.__init__(self, parent)
        EventBus.__init__(self)

    def publish(self, event: PedagogyEvent) -> None:
        """Distribue ``event`` aux abonnés Python ET émet le Signal Qt.

        Args:
            event: Événement à publier.
        """
        super().publish(event)
        self.event_emitted.emit(event)
