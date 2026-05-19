"""Jeton de pause/annulation injecté à l'orchestrateur du pipeline.

Le ``PauseToken`` permet de signaler depuis l'UI un événement utilisateur
(pause volontaire ou annulation) ; le moteur du pipeline check le token aux
frontières sûres (entre phases, entre retries) et se met en attente ou lève
une ``PausedError`` selon le cas.

Thread-safe : repose sur ``threading.Event``.
"""

from __future__ import annotations

import threading

from fahmi2.core.errors.exceptions import PausedError
from fahmi2.core.errors.severity import Severity


class PauseToken:
    """Token coopératif de pause/annulation du pipeline."""

    def __init__(self) -> None:
        # _resume_event : set quand la pause est terminée (le thread peut continuer).
        self._resume_event = threading.Event()
        self._resume_event.set()
        self._paused = False
        self._cancelled = threading.Event()
        self._lock = threading.Lock()

    def is_paused(self) -> bool:
        """Indique si la pause est demandée.

        Returns:
            ``True`` si en pause.
        """
        with self._lock:
            return self._paused

    def is_cancelled(self) -> bool:
        """Indique si l'annulation a été demandée.

        Returns:
            ``True`` si annulé.
        """
        return self._cancelled.is_set()

    def request_pause(self) -> None:
        """Demande une pause (le moteur s'arrêtera à la prochaine frontière sûre)."""
        with self._lock:
            self._paused = True
            self._resume_event.clear()

    def resume(self) -> None:
        """Lève la pause et débloque les threads en attente."""
        with self._lock:
            self._paused = False
            self._resume_event.set()

    def request_cancel(self) -> None:
        """Demande l'annulation et débloque les threads en attente."""
        self._cancelled.set()
        # On débloque tout attente de pause pour que le check raise_if_cancelled fasse
        # son office plus haut dans la pile.
        with self._lock:
            self._resume_event.set()

    def wait_if_paused(self, *, timeout: float | None = None) -> None:
        """Bloque tant que la pause est active, ou jusqu'au timeout.

        Args:
            timeout: Délai max en secondes (``None`` = attendre indéfiniment).
        """
        self._resume_event.wait(timeout=timeout)

    def raise_if_cancelled(self) -> None:
        """Lève ``PausedError(code='RUN.CANCELLED')`` si l'annulation est demandée.

        Raises:
            PausedError: Si ``request_cancel`` a été appelé.
        """
        if self._cancelled.is_set():
            raise PausedError(
                code="RUN.CANCELLED",
                user_message="Le run a été annulé par l'utilisateur.",
                severity=Severity.INFO,
            )
