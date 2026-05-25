"""Jalon d'évaluation du retrieval (recall lexical déterministe).

Garde-fou de non-régression sur le chunking + le retrieval lexical : un jeu de
questions de référence doit retrouver le passage attendu. Déterministe (sans LLM),
donc intégré à la suite unitaire (cf. spec §14.1).
"""

from __future__ import annotations

from fahmi2.chat.corpus import chunk_consolidated
from fahmi2.core.retrieval.passages import PassageRetriever, TfidfPassageRetriever

_DOC = """# Cours d'économie

# 1. Le produit intérieur brut

Le produit intérieur brut mesure la valeur des biens et services produits.

# 2. L'inflation

L'inflation est la hausse générale et durable des prix à la consommation.

# 3. Le chômage

Le chômage désigne les personnes sans emploi qui cherchent activement du travail.

# 4. Les taux d'intérêt

Les taux d'intérêt sont la rémunération de l'argent prêté, pilotée par la banque centrale.

# 5. La balance commerciale

La balance commerciale compare les exportations et les importations d'un pays.
"""

#: Questions de référence → ancre du chapitre attendu.
_CASES: tuple[tuple[str, str], ...] = (
    ("Qu'est-ce que le produit intérieur brut ?", "1-le-produit-intérieur-brut"),
    ("Qu'est-ce que la hausse durable des prix ?", "2-linflation"),
    ("Qui sont les personnes sans emploi qui cherchent du travail ?", "3-le-chômage"),
    (
        "Comment la banque centrale pilote la rémunération de l'argent prêté ?",
        "4-les-taux-dintérêt",
    ),
    (
        "Quelle est la différence entre exportations et importations ?",
        "5-la-balance-commerciale",
    ),
)


def _recall_at_k(
    retriever: PassageRetriever, cases: tuple[tuple[str, str], ...], k: int
) -> float:
    hits = sum(
        any(
            passage.chunk.anchor == expected
            for passage in retriever.retrieve(query=question, top_k=k)
        )
        for question, expected in cases
    )
    return hits / len(cases)


def test_retrieval_recall_at_1_is_perfect() -> None:
    retriever = TfidfPassageRetriever(chunk_consolidated(_DOC))
    assert _recall_at_k(retriever, _CASES, k=1) == 1.0
