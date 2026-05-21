"""Tests du primitif map_bounded."""

from __future__ import annotations

import threading
import time

import pytest

from fahmi2.core.concurrency import map_bounded
from fahmi2.core.errors.exceptions import LLMError, PausedError
from fahmi2.core.errors.severity import Severity
from fahmi2.pipeline.pause_token import PauseToken


def test_preserves_result_order() -> None:
    assert map_bounded(lambda x: x * 2, [1, 2, 3, 4, 5], max_workers=3) == [
        2,
        4,
        6,
        8,
        10,
    ]


def test_empty_items_returns_empty() -> None:
    assert map_bounded(lambda x: x, [], max_workers=4) == []


def test_sequential_when_single_worker() -> None:
    calls: list[int] = []
    map_bounded(calls.append, [1, 2, 3], max_workers=1)
    assert calls == [1, 2, 3]


def test_bounds_concurrency() -> None:
    lock = threading.Lock()
    state = {"current": 0, "max": 0}

    def work(_: int) -> int:
        with lock:
            state["current"] += 1
            state["max"] = max(state["max"], state["current"])
        time.sleep(0.02)
        with lock:
            state["current"] -= 1
        return 0

    map_bounded(work, list(range(20)), max_workers=4)
    assert state["max"] <= 4


def test_fail_fast_propagates_first_exception() -> None:
    def work(x: int) -> int:
        if x == 3:
            raise LLMError(
                code="LLM.X", user_message="boom", severity=Severity.ERROR
            )
        return x

    with pytest.raises(LLMError):
        map_bounded(work, [1, 2, 3, 4, 5], max_workers=2)


def test_cancellation_raises_paused_error() -> None:
    token = PauseToken()
    token.request_cancel()
    with pytest.raises(PausedError):
        map_bounded(lambda x: x, [1, 2, 3], max_workers=4, pause_token=token)
