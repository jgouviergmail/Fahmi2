"""Port ``PassageRetriever`` + implémentation TF-IDF (passages du corpus).

Distinct de :py:class:`GlossaryRetriever` (qui sélectionne des *termes*) : ici on
récupère des *passages* (``CorpusChunk``) pertinents pour une question en langage
naturel. Réutilise la stack ``scikit-learn`` déjà présente (cf. ``tfidf.py``).
"""

from __future__ import annotations

from typing import Any, Protocol

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from fahmi2.domain.chat import CorpusChunk, RetrievedPassage

# Tokenizer : mots Unicode (accents conservés), comme le retriever du glossaire.
_TOKEN_PATTERN = r"(?u)\b\w+\b"  # noqa: S105 — motif tokenizer, pas un secret


class PassageRetriever(Protocol):
    """Récupère les passages du corpus les plus pertinents pour une question."""

    def retrieve(self, *, query: str, top_k: int) -> list[RetrievedPassage]:
        """Retourne au plus ``top_k`` passages, triés par pertinence décroissante.

        Args:
            query: Question en langage naturel.
            top_k: Nombre maximal de passages.

        Returns:
            Liste de ``RetrievedPassage`` (taille <= ``top_k``).
        """

    def consumed_cost_usd(self) -> float:
        """Coût (USD) consommé par le retrieval depuis la construction.

        Returns:
            Le coût (0 pour un retrieval purement local ; > 0 si embeddings ou
            reformulation LLM).
        """


class TfidfPassageRetriever:
    """Retriever top-K par similarité TF-IDF (cosine) sur les chunks du corpus.

    La matrice TF-IDF est construite à l'instanciation (corpus d'un cours = petit,
    coût négligeable).
    """

    def __init__(self, chunks: tuple[CorpusChunk, ...]) -> None:
        """Construit l'index TF-IDF des chunks.

        Args:
            chunks: Passages du corpus à indexer.
        """
        self._chunks = chunks
        self._vectorizer = TfidfVectorizer(
            lowercase=True,
            token_pattern=_TOKEN_PATTERN,
        )
        self._matrix: Any = (
            self._vectorizer.fit_transform([chunk.text for chunk in chunks])
            if chunks
            else None
        )

    def retrieve(self, *, query: str, top_k: int) -> list[RetrievedPassage]:
        """Retourne au plus ``top_k`` passages triés par pertinence décroissante.

        Args:
            query: Question en langage naturel.
            top_k: Nombre maximal de passages.

        Returns:
            Liste de ``RetrievedPassage``.
        """
        if not self._chunks or top_k <= 0 or not query.strip():
            return []
        query_vec = self._vectorizer.transform([query])
        similarities = cosine_similarity(query_vec, self._matrix)[0]
        ranked = sorted(
            enumerate(similarities),
            key=lambda pair: (-pair[1], pair[0]),
        )
        return [
            RetrievedPassage(chunk=self._chunks[index], score=float(score))
            for index, score in ranked[:top_k]
        ]

    def consumed_cost_usd(self) -> float:
        """Retrieval lexical : entièrement local, coût nul.

        Returns:
            ``0.0``.
        """
        return 0.0
