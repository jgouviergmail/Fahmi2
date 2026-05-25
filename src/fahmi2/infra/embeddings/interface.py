"""Port ``EmbeddingProvider`` : transforme du texte en vecteurs.

Port distinct (ports/adapters) permettant de brancher OpenAI (production) ou un
fake déterministe (tests). DeepSeek n'expose pas d'endpoint d'embeddings (cf. spec
§6.0), d'où le choix d'OpenAI côté production.
"""

from __future__ import annotations

from typing import Protocol


class EmbeddingProvider(Protocol):
    """Contrat d'un fournisseur d'embeddings de texte."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Calcule les vecteurs d'une liste de documents.

        Args:
            texts: Textes à encoder.

        Returns:
            Un vecteur par texte (même ordre).
        """

    def embed_query(self, text: str) -> list[float]:
        """Calcule le vecteur d'une requête.

        Args:
            text: Texte de la requête.

        Returns:
            Le vecteur correspondant.
        """
