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

    def __init__(
        self, *, dimension: int = _DEFAULT_DIMENSION, cost_per_call: float = 0.0
    ) -> None:
        """Construit le fake.

        Args:
            dimension: Dimension des vecteurs produits.
            cost_per_call: Coût simulé ajouté à chaque appel d'embedding (0 par
                défaut ; > 0 pour exercer la remontée de coût dans les tests).
        """
        self._dimension = dimension
        self._cost_per_call = cost_per_call
        self._consumed_cost_usd = 0.0

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Encode une liste de textes.

        Args:
            texts: Textes à encoder.

        Returns:
            Un vecteur par texte.
        """
        self._consumed_cost_usd += self._cost_per_call
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        """Encode une requête.

        Args:
            text: Texte de la requête.

        Returns:
            Le vecteur.
        """
        self._consumed_cost_usd += self._cost_per_call
        return self._embed(text)

    def consumed_cost_usd(self) -> float:
        """Coût simulé cumulé.

        Returns:
            La somme des coûts simulés des appels d'embedding.
        """
        return self._consumed_cost_usd

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self._dimension
        for word in text.lower().split():
            digest = hashlib.sha256(word.encode("utf-8")).hexdigest()
            vector[int(digest, 16) % self._dimension] += 1.0
        return vector
