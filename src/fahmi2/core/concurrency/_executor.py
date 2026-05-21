"""Exécution bornée et concurrente d'une fonction sur une séquence d'items.

Primitif partagé par le moteur de génération et l'orchestrateur pédagogie.
Borne la concurrence à ``max_workers`` threads (adapté aux appels I/O-bound :
LLM, STT cloud — le GIL est libéré pendant l'attente réseau). Préserve l'ordre
des résultats, applique une politique *fail-fast*, et honore un ``PauseToken``
coopératif **entre les soumissions** (pause/annulation prises en compte sans
interrompre les tâches déjà démarrées).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from typing import TypeVar

from fahmi2.pipeline.pause_token import PauseToken

_T = TypeVar("_T")
_R = TypeVar("_R")


def map_bounded(
    fn: Callable[[_T], _R],
    items: Sequence[_T],
    *,
    max_workers: int,
    pause_token: PauseToken | None = None,
) -> list[_R]:
    """Applique ``fn`` à chaque item, au plus ``max_workers`` à la fois.

    Args:
        fn: Fonction appliquée à chaque item (peut lever : *fail-fast*).
        items: Items à traiter.
        max_workers: Concurrence maximale (>= 1). ``1`` => séquentiel.
        pause_token: Jeton coopératif consulté avant chaque soumission
            (bloque si pause, lève ``PausedError`` si annulation).

    Returns:
        Les résultats dans l'ordre des ``items``.

    Raises:
        BaseException: La première exception levée par ``fn`` (les tâches non
            démarrées sont annulées ; les démarrées vont au bout).
        PausedError: Si ``pause_token`` signale une annulation.
    """
    work = list(items)
    n = len(work)
    if n == 0:
        return []
    collected: dict[int, _R] = {}
    if max_workers <= 1:
        for index, item in enumerate(work):
            _wait_or_cancel(pause_token)
            collected[index] = fn(item)
        return [collected[i] for i in range(n)]

    next_index = 0
    in_flight: dict[Future[_R], int] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        try:
            while next_index < n and len(in_flight) < max_workers:
                _wait_or_cancel(pause_token)
                in_flight[executor.submit(fn, work[next_index])] = next_index
                next_index += 1
            while in_flight:
                done_set, _ = wait(set(in_flight), return_when=FIRST_COMPLETED)
                for done in done_set:
                    index = in_flight.pop(done)
                    collected[index] = done.result()  # fail-fast : propage
                    if next_index < n:
                        _wait_or_cancel(pause_token)
                        in_flight[
                            executor.submit(fn, work[next_index])
                        ] = next_index
                        next_index += 1
        except BaseException:
            for pending in in_flight:
                pending.cancel()
            raise
    return [collected[i] for i in range(n)]


def _wait_or_cancel(pause_token: PauseToken | None) -> None:
    """Bloque si pause demandée, lève ``PausedError`` si annulation.

    Args:
        pause_token: Jeton coopératif (``None`` => no-op).
    """
    if pause_token is None:
        return
    pause_token.wait_if_paused()
    pause_token.raise_if_cancelled()
