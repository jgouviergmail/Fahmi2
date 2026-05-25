"""``FakeEmbeddingProvider`` déterministe (tests, sans réseau).

Encode un texte en « sac de mots haché » : chaque mot incrémente une dimension
choisie par son hash. Deux textes partageant du vocabulaire ont donc des vecteurs
proches (cosine), ce qui rend le retrieval sémantique **testable de façon
déterministe**.
"""

from __future__ import annotations

import hashlib

_DEFAULT_DIMENSION = 32


class FakeEmbeddingProvider:
    """Fournisseur d'embeddings factice (sac de mots haché)."""

    def __init__(self, *, dimension: int = _DEFAULT_DIMENSION) -> None:
        """Construit le fake.

        Args:
            dimension: Dimension des vecteurs produits.
        """
        self._dimension = dimension

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Encode une liste de textes.

        Args:
            texts: Textes à encoder.

        Returns:
            Un vecteur par texte.
        """
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        """Encode une requête.

        Args:
            text: Texte de la requête.

        Returns:
            Le vecteur.
        """
        return self._embed(text)

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self._dimension
        for word in text.lower().split():
            digest = hashlib.sha256(word.encode("utf-8")).hexdigest()
            vector[int(digest, 16) % self._dimension] += 1.0
        return vector
