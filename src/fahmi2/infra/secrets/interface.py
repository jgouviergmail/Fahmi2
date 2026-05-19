"""Interface ``SecretsStore`` et implémentation in-memory pour les tests.

L'implémentation Windows réelle s'appuyant sur DPAPI vit dans
:py:mod:`fahmi2.infra.secrets.dpapi_store` et est testée séparément.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol


class SecretsStore(Protocol):
    """Stockage de secrets clé/valeur (clés API, tokens)."""

    def set(self, key: str, value: str) -> None:
        """Stocke ou écrase une valeur pour la clé donnée.

        Args:
            key: Identifiant de la valeur.
            value: Valeur secrète (clé API par exemple).
        """

    def get(self, key: str) -> str | None:
        """Récupère la valeur associée à ``key`` (``None`` si absente).

        Args:
            key: Identifiant.

        Returns:
            La valeur, ou ``None`` si la clé n'est pas définie.
        """

    def delete(self, key: str) -> None:
        """Supprime l'entrée si elle existe (idempotent).

        Args:
            key: Identifiant à supprimer.
        """

    def keys(self) -> Iterable[str]:
        """Liste les clés actuellement stockées.

        Returns:
            Itérable des clés présentes.
        """


class InMemorySecretsStore:
    """Implémentation en mémoire de ``SecretsStore``.

    Utilisée par les tests et les contextes où la persistance n'est pas
    requise. Non thread-safe (ce n'est pas son rôle ; envelopper avec un Lock
    si besoin).
    """

    def __init__(self) -> None:
        self._data: dict[str, str] = {}

    def set(self, key: str, value: str) -> None:
        """Stocke ou écrase une valeur pour la clé donnée.

        Args:
            key: Identifiant.
            value: Valeur.
        """
        self._data[key] = value

    def get(self, key: str) -> str | None:
        """Récupère la valeur, ou ``None`` si absente.

        Args:
            key: Identifiant.

        Returns:
            La valeur, ou ``None``.
        """
        return self._data.get(key)

    def delete(self, key: str) -> None:
        """Supprime l'entrée (idempotent).

        Args:
            key: Identifiant.
        """
        self._data.pop(key, None)

    def keys(self) -> Iterable[str]:
        """Liste les clés présentes.

        Returns:
            Liste des clés.
        """
        return list(self._data)
