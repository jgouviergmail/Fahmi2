"""Implémentation TF-IDF de :py:class:`GlossaryRetriever`.

Vectorise les termes du glossaire + le contenu requête via ``TfidfVectorizer``
puis classe les termes par cosine similarity décroissante. Conserve les
``top_k`` meilleurs.

Coût modéré (< 50 ms pour 500 termes), pas de dépendance modèle externe à
télécharger, qualité suffisante pour le matching lexical du glossaire en v1.
"""

from __future__ import annotations

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

_MIN_TOKEN_LENGTH = 1


class TfidfGlossaryRetriever:
    """Retriever top-K par similarité TF-IDF (cosine).

    Le vectorizer est instancié par appel (configuration légère) ; pour de
    gros glossaires fréquemment interrogés, un cache pourra être ajouté.
    """

    def retrieve(self, *, query: str, terms: list[str], top_k: int) -> list[str]:
        """Retourne au plus ``top_k`` termes triés par pertinence décroissante.

        Args:
            query: Texte de référence (le contenu pour lequel on cherche des
                termes pertinents).
            terms: Liste candidate des termes du glossaire.
            top_k: Nombre maximal de termes à retourner.

        Returns:
            Sous-liste de ``terms`` (jamais plus de ``top_k`` éléments).
        """
        if not terms:
            return []
        if top_k <= 0:
            return []
        if not query.strip():
            return list(terms[:top_k])

        vectorizer = TfidfVectorizer(
            lowercase=True,
            token_pattern=r"(?u)\b\w+\b",  # noqa: S106 — tokenizer regex, pas un secret
            min_df=_MIN_TOKEN_LENGTH,
        )
        # On fit sur l'union (query + terms) pour partager le vocabulaire.
        corpus = [query, *terms]
        matrix = vectorizer.fit_transform(corpus)
        query_vec = matrix[0:1]
        term_vecs = matrix[1:]
        similarities = cosine_similarity(query_vec, term_vecs)[0]
        # Tri stable : on indexe puis trie par (-similarité, position).
        ranked = sorted(
            enumerate(similarities),
            key=lambda pair: (-pair[1], pair[0]),
        )
        return [terms[i] for i, _ in ranked[:top_k]]
