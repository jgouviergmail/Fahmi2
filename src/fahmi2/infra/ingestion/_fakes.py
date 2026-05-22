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
