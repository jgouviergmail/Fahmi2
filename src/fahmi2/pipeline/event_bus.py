"""Bus d'événements générique (in-memory, thread-safe).

Paramétré par le type d'événement (``EventBus[PipelineEvent]`` pour la
génération, ``EventBus[PedagogyEvent]`` pour la pédagogie). L'adapter Qt
(``ui/qt_event_bus.py``) en hérite pour bridger worker → UI thread.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Generic, TypeVar

E = TypeVar("E")


class EventBus(Generic[E]):
    """Bus d'événements in-memory thread-safe, paramétré par le type d'event."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._handlers: list[Callable[[E], None]] = []

    def subscribe(self, handler: Callable[[E], None]) -> Callable[[], None]:
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

    def publish(self, event: E) -> None:
        """Distribue ``event`` à tous les handlers abonnés.

        Args:
            event: Événement à publier.

        Note:
            Les exceptions levées par un handler ne sont pas propagées : on
            isole chaque handler pour ne pas casser la chaîne.
        """
        with self._lock:
            handlers = tuple(self._handlers)
        for h in handlers:
            try:
                h(event)
            except Exception:  # noqa: BLE001, S110 — isolation des handlers
                pass
