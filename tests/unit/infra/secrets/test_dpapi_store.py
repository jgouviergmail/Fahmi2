"""Tests du DPAPISecretsStore (Windows uniquement)."""

import sys
from pathlib import Path

import pytest

from fahmi2.infra.secrets.dpapi_store import DPAPISecretsStore

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="DPAPI requires Windows")


def test_set_then_get_round_trip(tmp_path: Path) -> None:
    store = DPAPISecretsStore(tmp_path / "secrets.dat")
    store.set("openai_api_key", "sk-abc-123")
    assert store.get("openai_api_key") == "sk-abc-123"


def test_persists_across_instances(tmp_path: Path) -> None:
    secrets_file = tmp_path / "secrets.dat"
    store1 = DPAPISecretsStore(secrets_file)
    store1.set("k", "secret-value")
    del store1

    store2 = DPAPISecretsStore(secrets_file)
    assert store2.get("k") == "secret-value"


def test_get_missing_returns_none(tmp_path: Path) -> None:
    store = DPAPISecretsStore(tmp_path / "secrets.dat")
    assert store.get("missing") is None


def test_delete_removes_value(tmp_path: Path) -> None:
    store = DPAPISecretsStore(tmp_path / "secrets.dat")
    store.set("k", "v")
    store.delete("k")
    assert store.get("k") is None


def test_delete_missing_is_idempotent(tmp_path: Path) -> None:
    store = DPAPISecretsStore(tmp_path / "secrets.dat")
    store.delete("missing")


def test_keys_lists_present_keys(tmp_path: Path) -> None:
    store = DPAPISecretsStore(tmp_path / "secrets.dat")
    store.set("a", "1")
    store.set("b", "2")
    assert set(store.keys()) == {"a", "b"}


def test_secrets_file_is_encrypted(tmp_path: Path) -> None:
    secrets_file = tmp_path / "secrets.dat"
    store = DPAPISecretsStore(secrets_file)
    store.set("openai_api_key", "sk-sensitive-value-12345")

    raw = secrets_file.read_bytes()
    assert b"sk-sensitive-value-12345" not in raw, (
        "La valeur doit etre chiffree sur disque"
    )
