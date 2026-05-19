"""Tests de l'interface SecretsStore et de InMemorySecretsStore."""

from fahmi2.infra.secrets.interface import InMemorySecretsStore, SecretsStore


def test_set_then_get_returns_value() -> None:
    store = InMemorySecretsStore()
    store.set("openai_api_key", "sk-xxx")
    assert store.get("openai_api_key") == "sk-xxx"


def test_get_unknown_returns_none() -> None:
    store = InMemorySecretsStore()
    assert store.get("missing") is None


def test_set_overwrites_existing_value() -> None:
    store = InMemorySecretsStore()
    store.set("k", "v1")
    store.set("k", "v2")
    assert store.get("k") == "v2"


def test_delete_removes_value() -> None:
    store = InMemorySecretsStore()
    store.set("k", "v")
    store.delete("k")
    assert store.get("k") is None


def test_delete_missing_is_idempotent() -> None:
    store = InMemorySecretsStore()
    store.delete("missing")  # ne lève pas


def test_keys_lists_present_keys() -> None:
    store = InMemorySecretsStore()
    store.set("a", "1")
    store.set("b", "2")
    assert set(store.keys()) == {"a", "b"}


def test_keys_empty_initially() -> None:
    store = InMemorySecretsStore()
    assert list(store.keys()) == []


def test_implements_protocol() -> None:
    store: SecretsStore = InMemorySecretsStore()
    store.set("k", "v")
    assert store.get("k") == "v"
