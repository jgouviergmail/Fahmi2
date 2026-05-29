"""Fabrique de ``PassageRetriever`` : résout ``AUTO``, repli, query expansion.

Centralise le choix de la stratégie de retrieval (cf. spec §4.5) :

- ``AUTO`` → sémantique si un ``EmbeddingProvider`` est disponible (clé OpenAI),
  sinon lexical ;
- ``SEMANTIC`` sans provider → **repli lexical** (jamais d'échec dur) ;
- ``LEXICAL`` → lexical.

Le retriever lexical est enveloppé d'un ``QueryExpander`` si la query expansion est
activée (le sémantique n'en a pas besoin).
"""

from __future__ import annotations

from pathlib import Path

from fahmi2.chat.query_expander import QueryExpander
from fahmi2.core.retrieval.passages import PassageRetriever, TfidfPassageRetriever
from fahmi2.domain.chat import ChatSettings, CorpusChunk
from fahmi2.domain.enums import Language, RetrievalStrategy
from fahmi2.infra.embeddings.interface import EmbeddingProvider
from fahmi2.infra.llm.interface import LLMProvider
from fahmi2.infra.prompts.loader import PromptLoader
from fahmi2.infra.retrieval.semantic import (
    SemanticPassageRetriever,
    build_index_fingerprint,
)
from fahmi2.infra.storage.fs_artifacts import FsArtifactStore


def build_passage_retriever(
    *,
    chunks: tuple[CorpusChunk, ...],
    settings: ChatSettings,
    prompts: PromptLoader,
    llm: LLMProvider,
    embedding_provider: EmbeddingProvider | None,
    embedding_model: str,
    index_path: Path,
    source_mtime_ns: int | None,
    language: Language,
    artifacts: FsArtifactStore,
    glossary_mtime_ns: int | None = None,
) -> PassageRetriever:
    """Construit le retriever adapté à la stratégie configurée.

    Args:
        chunks: Passages du corpus.
        settings: Réglages du chat (stratégie, query expansion).
        prompts: Loader de prompts (pour la query expansion).
        llm: Provider LLM (pour la query expansion).
        embedding_provider: Fournisseur d'embeddings, ou ``None`` (pas de clé OpenAI).
        embedding_model: Identifiant du modèle d'embedding (empreinte d'index).
        index_path: Chemin de l'index sémantique persisté.
        source_mtime_ns: mtime (ns) du consolidé (empreinte d'index).
        language: Langue du corpus.
        artifacts: Store d'écriture atomique.
        glossary_mtime_ns: mtime (ns) du glossaire master (empreinte d'index).
            ``None`` si absent. Une édition du glossaire qui ne change pas le
            nombre de chunks (ex. définition modifiée) doit invalider l'index
            sémantique pour éviter des embeddings périmés.

    Returns:
        Le ``PassageRetriever`` (sémantique, ou lexical éventuellement enveloppé).
    """
    if _should_use_semantic(settings.retrieval_strategy, embedding_provider):
        assert embedding_provider is not None  # garanti par _should_use_semantic
        return SemanticPassageRetriever(
            chunks=chunks,
            embedding_provider=embedding_provider,
            index_path=index_path,
            fingerprint=build_index_fingerprint(
                model=embedding_model,
                source_mtime_ns=source_mtime_ns,
                glossary_mtime_ns=glossary_mtime_ns,
                language=language,
            ),
            artifacts=artifacts,
        )
    base = TfidfPassageRetriever(chunks)
    if settings.query_expansion_enabled:
        return QueryExpander(
            inner=base, llm_provider=llm, prompt_loader=prompts, settings=settings
        )
    return base


def _should_use_semantic(
    strategy: RetrievalStrategy, embedding_provider: EmbeddingProvider | None
) -> bool:
    """Indique si le retrieval sémantique doit être utilisé.

    Args:
        strategy: Stratégie configurée.
        embedding_provider: Fournisseur d'embeddings, ou ``None``.

    Returns:
        ``True`` si sémantique (provider requis) ; ``False`` = lexical (repli inclus).
    """
    if embedding_provider is None:
        return False
    return strategy in (RetrievalStrategy.AUTO, RetrievalStrategy.SEMANTIC)
