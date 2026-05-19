"""Tests des helpers ULID."""

import time
from datetime import UTC

import pytest

from fahmi2.core.ids import new_ulid, parse_ulid, ulid_to_datetime


def test_new_ulid_returns_26_char_string() -> None:
    value = new_ulid()
    assert isinstance(value, str)
    assert len(value) == 26


def test_new_ulid_returns_unique_values() -> None:
    values = {new_ulid() for _ in range(100)}
    assert len(values) == 100


def test_new_ulid_is_monotonic_in_time() -> None:
    ulids: list[str] = []
    for _ in range(10):
        ulids.append(new_ulid())
        time.sleep(0.002)
    assert ulids == sorted(ulids), (
        "ULIDs générés à >= 1 ms d'intervalle doivent être ordonnés"
    )


def test_parse_ulid_accepts_valid_ulid() -> None:
    original = new_ulid()
    parsed = parse_ulid(original)
    assert parsed == original


def test_parse_ulid_rejects_invalid() -> None:
    with pytest.raises(ValueError):
        parse_ulid("not-a-ulid")


def test_ulid_to_datetime_returns_utc_aware() -> None:
    value = new_ulid()
    dt = ulid_to_datetime(value)
    assert dt.tzinfo is not None
    assert dt.tzinfo.utcoffset(dt) == UTC.utcoffset(dt)
