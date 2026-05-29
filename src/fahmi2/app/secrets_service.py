"""Service applicatif de gestion des secrets (clés API).

Wrapper léger au-dessus de :py:class:`SecretsStore` qui expose des clés
stables et explicitement nommées :

- ``openai_api_key`` : clé OpenAI pour Whisper cloud.
- ``deepseek_api_key`` : clé DeepSeek pour les phases LLM.

Le service enregistre également chaque valeur stockée dans le redactor de
logs global pour qu'elle soit masquée dans tous les futurs ``LogEvent``.
"""

from __future__ import annotations

from collections.abc import Iterable

from fahmi2.core.logging.sink import MIN_SECRET_LENGTH, register_secret
from fahmi2.infra.secrets.interface import SecretsStore

KEY_OPENAI = "openai_api_key"
KEY_DEEPSEEK = "deepseek_api_key"


class SecretsService:
    """Gère les secrets utilisateur (clés API) avec redaction globale."""

    def __init__(self, store: SecretsStore) -> None:
        """Construit le service.

        Args:
            store: ``SecretsStore`` (DPAPI en prod, InMemory en tests).
        """
        self._store = store
        self._register_existing_secrets()

    def set_openai_api_key(self, value: str) -> None:
        """Stocke la clé OpenAI et l'inscrit pour la redaction des logs.

        Args:
            value: Clé API.
        """
        self._set(KEY_OPENAI, value)

    def set_deepseek_api_key(self, value: str) -> None:
        """Stocke la clé DeepSeek et l'inscrit pour la redaction des logs.

        Args:
            value: Clé API.
        """
        self._set(KEY_DEEPSEEK, value)

    def get_openai_api_key(self) -> str | None:
        """Récupère la clé OpenAI (``None`` si absente).

        Returns:
            La clé, ou ``None``.
        """
        return self._store.get(KEY_OPENAI)

    def get_deepseek_api_key(self) -> str | None:
        """Récupère la clé DeepSeek (``None`` si absente).

        Returns:
            La clé, ou ``None``.
        """
        return self._store.get(KEY_DEEPSEEK)

    def delete_openai_api_key(self) -> None:
        """Supprime la clé OpenAI."""
        self._store.delete(KEY_OPENAI)

    def delete_deepseek_api_key(self) -> None:
        """Supprime la clé DeepSeek."""
        self._store.delete(KEY_DEEPSEEK)

    def has_openai_key(self) -> bool:
        """Indique si la clé OpenAI est configurée.

        Returns:
            ``True`` si présente.
        """
        return self._store.get(KEY_OPENAI) is not None

    def has_deepseek_key(self) -> bool:
        """Indique si la clé DeepSeek est configurée.

        Returns:
            ``True`` si présente.
        """
        return self._store.get(KEY_DEEPSEEK) is not None

    def keys(self) -> Iterable[str]:
        """Liste les clés actuellement stockées (noms internes uniquement).

        Returns:
            Les noms internes (jamais les valeurs).
        """
        return self._store.keys()

    def _set(self, key: str, value: str) -> None:
        self._store.set(key, value)
        register_secret(value)

    def _register_existing_secrets(self) -> None:
        for key in self._store.keys():
            value = self._store.get(key)
            if value is not None and len(value) >= MIN_SECRET_LENGTH:
                register_secret(value)
