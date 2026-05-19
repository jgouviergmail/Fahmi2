"""Store d'artefacts sur le système de fichiers avec writes atomiques.

Le pattern atomique consiste à écrire d'abord dans ``<chemin>.tmp`` puis à
renommer vers le chemin final via ``os.replace``. ``os.replace`` est atomique
sur la plupart des systèmes de fichiers et garantit que le fichier final reste
inchangé en cas d'erreur d'écriture en cours de route — c'est essentiel pour
préserver les artefacts du pipeline en cas de crash en plein milieu.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

_TMP_SUFFIX = ".tmp"
_JSON_INDENT = 2
_ENCODING_UTF8 = "utf-8"


class FsArtifactStore:
    """Écrit des artefacts texte / binaires / JSON de manière atomique.

    Toutes les méthodes créent automatiquement le dossier parent si nécessaire.
    En cas d'erreur d'écriture, le fichier final reste inchangé : le fichier
    temporaire est créé puis renommé en une seule opération atomique en fin de
    parcours.
    """

    def write_text_atomic(self, path: Path, content: str) -> None:
        """Écrit ``content`` dans ``path`` en utf-8 de manière atomique.

        Args:
            path: Chemin cible.
            content: Texte à écrire.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._tmp_path_for(path)
        try:
            tmp.write_text(content, encoding=_ENCODING_UTF8)
            os.replace(tmp, path)
        finally:
            self._cleanup_tmp(tmp)

    def write_bytes_atomic(self, path: Path, content: bytes) -> None:
        """Écrit ``content`` dans ``path`` (binaire) de manière atomique.

        Args:
            path: Chemin cible.
            content: Bytes à écrire.
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._tmp_path_for(path)
        try:
            tmp.write_bytes(content)
            os.replace(tmp, path)
        finally:
            self._cleanup_tmp(tmp)

    def write_json_atomic(self, path: Path, data: Any) -> None:  # noqa: ANN401
        """Écrit ``data`` en JSON utf-8 indenté, sans échappement Unicode.

        Args:
            path: Chemin cible.
            data: Structure JSON-sérialisable.
        """
        content = json.dumps(data, ensure_ascii=False, indent=_JSON_INDENT)
        self.write_text_atomic(path, content)

    @staticmethod
    def _tmp_path_for(path: Path) -> Path:
        """Retourne le chemin de l'artefact temporaire associé à ``path``."""
        return path.with_suffix(path.suffix + _TMP_SUFFIX)

    @staticmethod
    def _cleanup_tmp(tmp: Path) -> None:
        """Supprime le fichier temporaire s'il existe encore (post-erreur)."""
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                # Best-effort : on ne masque pas l'erreur initiale.
                pass
