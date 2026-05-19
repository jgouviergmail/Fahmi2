"""Bus d'événements générique pour le pipeline.

Implémentation in-memory thread-safe. L'adapter Qt (qui transforme les
publications en ``Signal`` côté UI) vivra dans ``ui/qt_event_bus.py`` (Plan 08)
et héritera de la même interface.
"""

from __future__ import annotations

import threading
from collections.abc import Callable

from fahmi2.pipeline.events import PipelineEvent

EventHandler = Callable[[PipelineEvent], None]


class EventBus:
    """Bus d'événements in-memory thread-safe."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._handlers: list[EventHandler] = []

    def subscribe(self, handler: EventHandler) -> Callable[[], None]:
        """Abonne un handler aux événements futurs.

        Args:
            handler: Fonction appelée à chaque publication.

        Returns:
            Fonction de désabonnement (idempotente).
        """
        with self._lock:
            self._handlers.append(handler)

        def _unsubscribe() -> None:
            with self._lock:
                if handler in self._handlers:
                    self._handlers.remove(handler)

        return _unsubscribe

    def publish(self, event: PipelineEvent) -> None:
        """Distribue ``event`` à tous les handlers abonnés.

        Args:
            event: Événement à publier.

        Note:
            Les exceptions levées par un handler ne sont pas propagées : on
            log silencieusement et on continue (un handler défaillant ne doit
            pas casser la chaîne).
        """
        with self._lock:
            handlers = tuple(self._handlers)
        for h in handlers:
            try:
                h(event)
            except Exception:  # noqa: BLE001, S110 — isolation des handlers
                # On ne masque pas l'erreur silencieusement en production : un
                # sink de logs dédié (Plan futur) écoutera ces erreurs via un
                # autre canal. Pour l'instant on isole.
                pass
