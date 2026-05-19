"""Stockage des secrets chiffrés via Windows DPAPI (``CryptProtectData``).

Le chiffrement est lié à l'utilisateur Windows courant : seul ce profil
utilisateur peut déchiffrer le fichier (avec l'entropie applicative fixe).
Format binaire du fichier : un header magic suivi du blob chiffré renfermant
un JSON ``{"key": "value", ...}``.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Iterable
from pathlib import Path

from fahmi2.infra.storage.fs_artifacts import FsArtifactStore

if sys.platform == "win32":
    import win32crypt
else:  # pragma: no cover — module utilisable uniquement sous Windows
    win32crypt = None  # type: ignore[assignment]


_HEADER_MAGIC = b"FAHMI2SEC\x01"
_HEADER_LEN = len(_HEADER_MAGIC)
_DPAPI_ENTROPY = b"fahmi2-secrets-v1"
_DPAPI_DESCRIPTION = "Fahmi2 secrets store"
_DPAPI_FLAGS = 0


class DPAPISecretsStore:
    """Stockage de secrets chiffrés via Windows DPAPI.

    Charge le fichier au démarrage (s'il existe), maintient le mapping en
    mémoire, et réécrit après chaque mutation via ``FsArtifactStore`` pour la
    durabilité atomique.

    Raises:
        RuntimeError: Si instancié sur une plateforme non-Windows.
    """

    def __init__(self, secrets_path: Path) -> None:
        """Ouvre le fichier (le charge s'il existe).

        Args:
            secrets_path: Chemin du fichier ``secrets.dat``.

        Raises:
            RuntimeError: Si la plateforme n'est pas Windows.
        """
        if sys.platform != "win32":
            raise RuntimeError("DPAPISecretsStore is only available on Windows")
        self._path = secrets_path
        self._artifacts = FsArtifactStore()
        self._data: dict[str, str] = self._load()

    def set(self, key: str, value: str) -> None:
        """Stocke ou écrase une valeur pour la clé donnée.

        Args:
            key: Identifiant.
            value: Valeur secrète.
        """
        self._data[key] = value
        self._save()

    def get(self, key: str) -> str | None:
        """Récupère la valeur associée à ``key`` (``None`` si absente).

        Args:
            key: Identifiant.

        Returns:
            La valeur, ou ``None``.
        """
        return self._data.get(key)

    def delete(self, key: str) -> None:
        """Supprime l'entrée si elle existe (idempotent).

        Args:
            key: Identifiant.
        """
        if key in self._data:
            del self._data[key]
            self._save()

    def keys(self) -> Iterable[str]:
        """Liste les clés actuellement stockées.

        Returns:
            Liste des clés.
        """
        return list(self._data)

    def _load(self) -> dict[str, str]:
        """Lit le fichier et déchiffre son contenu.

        Returns:
            Le mapping ``key -> value``, ou un dict vide si le fichier
            n'existe pas.
        """
        if not self._path.exists():
            return {}
        raw = self._path.read_bytes()
        if not raw.startswith(_HEADER_MAGIC):
            raise ValueError(
                f"Invalid secrets file at {self._path}: bad magic header"
            )
        encrypted = raw[_HEADER_LEN:]
        _, plaintext = win32crypt.CryptUnprotectData(
            encrypted, _DPAPI_ENTROPY, None, None, _DPAPI_FLAGS
        )
        loaded = json.loads(plaintext.decode("utf-8"))
        if not isinstance(loaded, dict):
            raise ValueError(f"Invalid secrets payload in {self._path}")
        return {str(k): str(v) for k, v in loaded.items()}

    def _save(self) -> None:
        """Chiffre l'état courant et l'écrit atomiquement sur disque."""
        plaintext = json.dumps(self._data, ensure_ascii=False).encode("utf-8")
        encrypted = win32crypt.CryptProtectData(
            plaintext,
            _DPAPI_DESCRIPTION,
            _DPAPI_ENTROPY,
            None,
            None,
            _DPAPI_FLAGS,
        )
        self._artifacts.write_bytes_atomic(self._path, _HEADER_MAGIC + encrypted)
