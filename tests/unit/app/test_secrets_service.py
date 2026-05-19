"""Tests de SecretsService."""

from fahmi2.app.secrets_service import (
    KEY_DEEPSEEK,
    KEY_OPENAI,
    SecretsService,
)
from fahmi2.core.logging.sink import SecretRedactor, unregister_secret
from fahmi2.infra.secrets.interface import InMemorySecretsStore


def test_set_and_get_openai_key() -> None:
    store = InMemorySecretsStore()
    service = SecretsService(store)
    service.set_openai_api_key("sk-openai-value-12345")
    assert service.get_openai_api_key() == "sk-openai-value-12345"
    assert store.get(KEY_OPENAI) == "sk-openai-value-12345"


def test_set_and_get_deepseek_key() -> None:
    store = InMemorySecretsStore()
    service = SecretsService(store)
    service.set_deepseek_api_key("sk-deepseek-value-12345")
    assert service.get_deepseek_api_key() == "sk-deepseek-value-12345"
    assert store.get(KEY_DEEPSEEK) == "sk-deepseek-value-12345"


def test_has_keys_distinguishes_present_absent() -> None:
    store = InMemorySecretsStore()
    service = SecretsService(store)
    assert not service.has_openai_key()
    assert not service.has_deepseek_key()
    service.set_openai_api_key("sk-x-12345")
    assert service.has_openai_key()
    assert not service.has_deepseek_key()


def test_delete_removes_key() -> None:
    store = InMemorySecretsStore()
    service = SecretsService(store)
    service.set_openai_api_key("sk-x-12345")
    service.delete_openai_api_key()
    assert not service.has_openai_key()


def test_keys_returns_internal_names_only() -> None:
    store = InMemorySecretsStore()
    service = SecretsService(store)
    service.set_openai_api_key("sk-secret-value-1")
    service.set_deepseek_api_key("sk-secret-value-2")
    names = set(service.keys())
    assert names == {KEY_OPENAI, KEY_DEEPSEEK}


def test_secret_is_registered_for_log_redaction() -> None:
    store = InMemorySecretsStore()
    service = SecretsService(store)
    secret = "sk-redaction-target-99999"
    try:
        service.set_openai_api_key(secret)
        redacted = SecretRedactor().redact(f"contient {secret} secret")
        assert secret not in redacted
    finally:
        unregister_secret(secret)
