"""Tests de PauseToken."""

import threading
import time

import pytest

from fahmi2.core.concurrency.pause_token import PauseToken
from fahmi2.core.errors.exceptions import PausedError


def test_initial_state_neither_paused_nor_cancelled() -> None:
    token = PauseToken()
    assert not token.is_paused()
    assert not token.is_cancelled()


def test_request_pause_sets_paused() -> None:
    token = PauseToken()
    token.request_pause()
    assert token.is_paused()


def test_resume_clears_pause() -> None:
    token = PauseToken()
    token.request_pause()
    token.resume()
    assert not token.is_paused()


def test_request_cancel_sets_cancelled_and_unblocks_wait() -> None:
    token = PauseToken()
    token.request_cancel()
    assert token.is_cancelled()


def test_wait_if_paused_returns_immediately_when_not_paused() -> None:
    token = PauseToken()
    start = time.monotonic()
    token.wait_if_paused(timeout=1.0)
    elapsed = time.monotonic() - start
    assert elapsed < 0.05


def test_wait_if_paused_blocks_until_resumed() -> None:
    token = PauseToken()
    token.request_pause()
    finished = threading.Event()

    def _waiter() -> None:
        token.wait_if_paused(timeout=5.0)
        finished.set()

    thread = threading.Thread(target=_waiter)
    thread.start()
    time.sleep(0.05)
    assert not finished.is_set(), "thread doit etre bloque tant que paused"
    token.resume()
    thread.join(timeout=1.0)
    assert finished.is_set()


def test_wait_if_paused_unblocked_by_cancel() -> None:
    token = PauseToken()
    token.request_pause()
    finished = threading.Event()

    def _waiter() -> None:
        token.wait_if_paused(timeout=5.0)
        finished.set()

    thread = threading.Thread(target=_waiter)
    thread.start()
    time.sleep(0.05)
    token.request_cancel()
    thread.join(timeout=1.0)
    assert finished.is_set()


def test_raise_if_cancelled_raises_when_set() -> None:
    token = PauseToken()
    token.request_cancel()
    with pytest.raises(PausedError) as exc_info:
        token.raise_if_cancelled()
    assert exc_info.value.code == "RUN.CANCELLED"


def test_raise_if_cancelled_noop_when_not_set() -> None:
    token = PauseToken()
    token.raise_if_cancelled()
