"""Décorateur de query expansion : améliore un retrieval lexical faible.

Si le meilleur score du retrieval direct est sous un seuil, demande au LLM une
reformulation (mots-clés/synonymes) et relance le retrieval, en fusionnant les
résultats (dédup par chunk_id). Évite tout appel LLM systématique.
"""

from __future__ import annotations

from fahmi2.core.retrieval.passages import PassageRetriever
from fahmi2.domain.chat import ChatSettings, RetrievedPassage
from fahmi2.infra.llm.interface import LLMProvider, Message
from fahmi2.infra.prompts.loader import PromptLoader

_PROMPT_QUERY_EXPANSION = "chat_query_expansion"
_WEAK_SCORE_THRESHOLD = 0.15


class QueryExpander:
    """Enveloppe un ``PassageRetriever`` d'une expansion LLM à la demande."""

    def __init__(
        self,
        *,
        inner: PassageRetriever,
        llm_provider: LLMProvider,
        prompt_loader: PromptLoader,
        settings: ChatSettings,
        weak_score_threshold: float = _WEAK_SCORE_THRESHOLD,
    ) -> None:
        """Construit le décorateur.

        Args:
            inner: Retriever sous-jacent (lexical).
            llm_provider: Provider LLM pour la reformulation.
            prompt_loader: Loader de prompts.
            settings: Réglages du chat (modèle, température).
            weak_score_threshold: Seuil sous lequel on déclenche l'expansion.
        """
        self._inner = inner
        self._llm = llm_provider
        self._prompts = prompt_loader
        self._settings = settings
        self._threshold = weak_score_threshold

    def retrieve(self, *, query: str, top_k: int) -> list[RetrievedPassage]:
        """Récupère les passages, avec expansion si le retrieval direct est faible.

        Args:
            query: Question.
            top_k: Nombre maximal de passages.

        Returns:
            Passages (fusion directe + expansion si déclenchée).
        """
        direct = self._inner.retrieve(query=query, top_k=top_k)
        if not self._settings.query_expansion_enabled:
            return direct
        if direct and direct[0].score >= self._threshold:
            return direct
        expanded_query = self._expand(query)
        if not expanded_query:
            return direct
        more = self._inner.retrieve(query=f"{query} {expanded_query}", top_k=top_k)
        return self._merge(direct, more, top_k=top_k)

    def _expand(self, query: str) -> str:
        """Demande au LLM une reformulation en mots-clés.

        Args:
            query: Question d'origine.

        Returns:
            Mots-clés (chaîne), ou vide en cas d'absence.
        """
        prompt = self._prompts.render(_PROMPT_QUERY_EXPANSION, question=query)
        response = self._llm.chat(
            messages=[Message(role="user", content=prompt)],
            model=str(self._settings.model),
            thinking=False,
            temperature=self._settings.temperature,
        )
        return response.content.strip()

    @staticmethod
    def _merge(
        direct: list[RetrievedPassage],
        more: list[RetrievedPassage],
        *,
        top_k: int,
    ) -> list[RetrievedPassage]:
        """Fusionne deux listes de passages (dédup par chunk_id, tri par score).

        Args:
            direct: Résultats du retrieval direct.
            more: Résultats du retrieval enrichi.
            top_k: Borne supérieure.

        Returns:
            Les ``top_k`` meilleurs passages dédupliqués.
        """
        best: dict[str, RetrievedPassage] = {}
        for passage in (*direct, *more):
            current = best.get(passage.chunk.chunk_id)
            if current is None or passage.score > current.score:
                best[passage.chunk.chunk_id] = passage
        ranked = sorted(best.values(), key=lambda passage: -passage.score)
        return ranked[:top_k]
