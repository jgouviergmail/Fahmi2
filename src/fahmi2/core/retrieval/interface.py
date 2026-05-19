"""Interface stable pour le retrieval top-K du glossaire injecté en contexte LLM.

L'implémentation TF-IDF concrète vit dans un autre module (livraison Plan 04).
Cette interface permet de tester les phases LLM sans dépendre encore de
``scikit-learn`` et autorise un swap futur vers embeddings.
"""

from __future__ import annotations

from typing import Protocol


class GlossaryRetriever(Protocol):
    """Sélectionne les termes du glossaire les plus pertinents pour un contenu."""

    def retrieve(self, *, query: str, terms: list[str], top_k: int) -> list[str]:
        """Retourne au plus ``top_k`` termes du glossaire, classés par pertinence.

        Args:
            query: Texte (chunk de contenu) pour lequel on cherche des termes
                pertinents.
            terms: Liste candidate des termes du glossaire.
            top_k: Nombre maximal de termes à retourner.

        Returns:
            Sous-liste de ``terms``, triée par pertinence décroissante, taille
            inférieure ou égale à ``top_k``.
        """


class PassthroughRetriever:
    """Implémentation triviale qui renvoie les premiers ``top_k`` termes inchangés.

    Utile pour les tests et pour les contextes où le glossaire est petit
    (pas besoin de retrieval réel).
    """

    def retrieve(self, *, query: str, terms: list[str], top_k: int) -> list[str]:
        """Retourne ``terms[:top_k]`` (copie défensive, ignore ``query``).

        Args:
            query: Ignoré (interface uniformisée).
            terms: Liste candidate.
            top_k: Borne supérieure.

        Returns:
            Une copie des ``top_k`` premiers éléments de ``terms``.
        """
        del query
        return list(terms[:top_k])
