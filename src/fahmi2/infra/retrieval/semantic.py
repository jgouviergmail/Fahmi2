"""Retrieval sémantique : embeddings + index numpy local persisté.

L'index (matrice d'embeddings des chunks) est mis en cache sur disque
(``chat/index.{lang}.npz``) avec une **empreinte de validité** (modèle d'embedding
+ mtime du consolidé + langue). Tant que l'empreinte est inchangée, l'index est
réutilisé ; sinon il est reconstruit. Le corpus d'un cours étant petit, la
similarité cosine est calculée en **brute-force numpy** (pas de base vectorielle).
"""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

import numpy as np

from fahmi2.domain.chat import CorpusChunk, RetrievedPassage
from fahmi2.domain.enums import Language
from fahmi2.infra.embeddings.interface import EmbeddingProvider
from fahmi2.infra.storage.fs_artifacts import FsArtifactStore

_EMBEDDINGS_KEY = "embeddings"
_META_KEY = "meta"
_EPSILON = 1e-12


def build_index_fingerprint(
    *, model: str, source_mtime_ns: int | None, language: Language
) -> str:
    """Construit l'empreinte de validité d'un index sémantique.

    Args:
        model: Identifiant du modèle d'embedding.
        source_mtime_ns: mtime (ns) du document consolidé source (``None`` si absent).
        language: Langue du corpus.

    Returns:
        Une chaîne JSON déterministe (clés triées).
    """
    return json.dumps(
        {
            "model": model,
            "source_mtime_ns": source_mtime_ns,
            "language": str(language),
        },
        sort_keys=True,
    )


def purge_index(index_path: Path) -> None:
    """Supprime un index sémantique persisté (idempotent).

    Args:
        index_path: Chemin de l'index ``.npz``.
    """
    if index_path.exists():
        index_path.unlink()


class SemanticPassageRetriever:
    """Retriever top-K par similarité cosine sur des embeddings persistés."""

    def __init__(
        self,
        *,
        chunks: tuple[CorpusChunk, ...],
        embedding_provider: EmbeddingProvider,
        index_path: Path,
        fingerprint: str,
        artifacts: FsArtifactStore,
    ) -> None:
        """Construit le retriever (charge l'index frais, sinon (ré)indexe).

        Args:
            chunks: Passages du corpus à indexer.
            embedding_provider: Fournisseur d'embeddings.
            index_path: Chemin de l'index ``.npz`` persisté.
            fingerprint: Empreinte de validité attendue (cf.
                :func:`build_index_fingerprint`).
            artifacts: Store d'écriture atomique.
        """
        self._chunks = chunks
        self._provider = embedding_provider
        self._matrix = self._load_or_build(chunks, index_path, fingerprint, artifacts)

    def _load_or_build(
        self,
        chunks: tuple[CorpusChunk, ...],
        index_path: Path,
        fingerprint: str,
        artifacts: FsArtifactStore,
    ) -> Any:  # noqa: ANN401 — matrice numpy (typage souple, cf. tfidf)
        cached = _load_index(index_path)
        if cached is not None:
            matrix, meta = cached
            if meta == fingerprint and matrix.shape[0] == len(chunks):
                return matrix
        if not chunks:
            return np.zeros((0, 0), dtype=np.float32)
        vectors = self._provider.embed_documents([chunk.text for chunk in chunks])
        matrix = np.array(vectors, dtype=np.float32)
        _save_index(index_path, matrix, fingerprint, artifacts)
        return matrix

    def retrieve(self, *, query: str, top_k: int) -> list[RetrievedPassage]:
        """Retourne au plus ``top_k`` passages triés par similarité décroissante.

        Args:
            query: Question en langage naturel.
            top_k: Nombre maximal de passages.

        Returns:
            Liste de ``RetrievedPassage``.
        """
        if (
            not self._chunks
            or top_k <= 0
            or not query.strip()
            or self._matrix.shape[0] == 0
        ):
            return []
        query_vec = np.array(self._provider.embed_query(query), dtype=np.float32)
        scores = _cosine(query_vec, self._matrix)
        order = np.argsort(-scores)[:top_k]
        return [
            RetrievedPassage(chunk=self._chunks[int(i)], score=float(scores[int(i)]))
            for i in order
        ]

    def consumed_cost_usd(self) -> float:
        """Coût (USD) des embeddings consommés (indexation + requêtes).

        Returns:
            Le coût cumulé du fournisseur d'embeddings.
        """
        return self._provider.consumed_cost_usd()


def _cosine(query: Any, matrix: Any) -> Any:  # noqa: ANN401 — vecteurs numpy
    """Similarités cosine entre un vecteur requête et chaque ligne de la matrice."""
    query_norm = query / (float(np.linalg.norm(query)) + _EPSILON)
    matrix_norms = np.linalg.norm(matrix, axis=1, keepdims=True) + _EPSILON
    normalized = matrix / matrix_norms
    return normalized @ query_norm


def _save_index(
    index_path: Path, matrix: Any, fingerprint: str, artifacts: FsArtifactStore  # noqa: ANN401
) -> None:
    """Sauve la matrice + l'empreinte en ``.npz`` (écriture atomique)."""
    buffer = io.BytesIO()
    np.savez(buffer, **{_EMBEDDINGS_KEY: matrix, _META_KEY: np.array(fingerprint)})
    artifacts.write_bytes_atomic(index_path, buffer.getvalue())


def _load_index(index_path: Path) -> tuple[Any, str] | None:
    """Charge la matrice + l'empreinte d'un index, ou ``None`` s'il est absent."""
    if not index_path.exists():
        return None
    with np.load(index_path, allow_pickle=False) as data:
        return data[_EMBEDDINGS_KEY], str(data[_META_KEY])
