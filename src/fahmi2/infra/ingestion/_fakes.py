"""Doubles de test pour la couche d'ingestion."""

from __future__ import annotations

from pathlib import Path


class FakeTextExtractor:
    """``TextExtractor`` factice : renvoie un texte fixe (ou par nom de fichier)."""

    def __init__(
        self,
        *,
        default_text: str = "Texte de document.",
        by_name: dict[str, str] | None = None,
    ) -> None:
        """Construit le fake.

        Args:
            default_text: Texte retourné par défaut.
            by_name: Mapping ``nom_de_fichier -> texte`` prioritaire sur le défaut.
        """
        self._default = default_text
        self._by_name = dict(by_name or {})

    def extract(self, path: Path) -> str:
        """Retourne le texte scénarisé pour ``path`` (ou le défaut).

        Args:
            path: Document (seul ``path.name`` sert au lookup).

        Returns:
            Le texte associé, ou ``default_text``.
        """
        return self._by_name.get(path.name, self._default)


class FakeYoutubeDownloader:
    """``YoutubeDownloader`` factice : « télécharge » en créant un fichier local."""

    def __init__(
        self,
        *,
        duration_seconds: float = 60.0,
        fail_with: Exception | None = None,
    ) -> None:
        """Construit le fake.

        Args:
            duration_seconds: Durée retournée par ``probe_duration``.
            fail_with: Exception levée par ``download_audio`` (scénario d'échec).
        """
        self._duration = duration_seconds
        self._fail_with = fail_with

    def download_audio(self, url: str, dest_dir: Path, stem: str) -> Path:
        """Crée un fichier audio factice (ou lève le scénario d'échec).

        Args:
            url: URL (ignorée).
            dest_dir: Dossier de destination (créé si absent).
            stem: Nom de base du fichier.

        Returns:
            Le chemin du fichier factice créé.

        Raises:
            Exception: Le ``fail_with`` configuré, le cas échéant.
        """
        if self._fail_with is not None:
            raise self._fail_with
        dest_dir.mkdir(parents=True, exist_ok=True)
        out = dest_dir / f"{stem}.m4a"
        out.write_bytes(b"fake-audio")
        return out

    def probe_duration(self, url: str) -> float:
        """Retourne la durée factice configurée.

        Args:
            url: URL (ignorée).

        Returns:
            La durée en secondes.
        """
        del url
        return self._duration
