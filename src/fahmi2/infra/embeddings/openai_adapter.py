"""``OpenAIEmbeddingProvider`` — embeddings via l'API OpenAI.

Utilise le SDK ``openai`` (déjà présent pour Whisper cloud). Le modèle est
configurable (cf. :class:`fahmi2.domain.enums.EmbeddingModel`), défaut
``text-embedding-3-small``. Réutilise la clé OpenAI gérée par ``SecretsService``.
"""

from __future__ import annotations

from openai import APIError, APIStatusError, AuthenticationError, OpenAI, RateLimitError

from fahmi2.core.errors.exceptions import EmbeddingError
from fahmi2.core.errors.severity import Severity
from fahmi2.domain.enums import EmbeddingModel
from fahmi2.infra.embeddings._pricing import embedding_cost_usd

_MODEL = str(EmbeddingModel.TEXT_EMBEDDING_3_SMALL)
_PROVIDER_NAME = "openai-embeddings"
#: Conseil commun : le retrieval lexical ne dépend pas d'OpenAI (100 % local).
_FALLBACK_HINT = " Tu peux aussi basculer le retrieval en « lexical » (hors-ligne)."


def _map_embedding_error(
    exc: APIStatusError | RateLimitError | AuthenticationError | APIError,
) -> EmbeddingError:
    """Convertit une exception OpenAI en ``EmbeddingError`` typée (message FR).

    Aligné sur le mapping des adapters STT/LLM (homogénéité) : clé refusée,
    limite de débit, ou erreur d'API génériques.

    Args:
        exc: Exception levée par le SDK OpenAI.

    Returns:
        L'``EmbeddingError`` correspondante.
    """
    if isinstance(exc, AuthenticationError):
        return EmbeddingError(
            code="EMBEDDING.AUTH_INVALID",
            user_message=(
                "La clé OpenAI est refusée pour le retrieval sémantique. "
                "Vérifie-la dans Paramètres › Clés API." + _FALLBACK_HINT
            ),
            severity=Severity.ERROR,
            technical_details={"provider": _PROVIDER_NAME},
        )
    if isinstance(exc, RateLimitError):
        return EmbeddingError(
            code="EMBEDDING.RATE_LIMIT",
            user_message="Limite de débit OpenAI atteinte (embeddings)." + _FALLBACK_HINT,
            severity=Severity.WARNING,
            technical_details={"provider": _PROVIDER_NAME},
        )
    return EmbeddingError(
        code="EMBEDDING.API_ERROR",
        user_message="Échec du calcul des embeddings OpenAI." + _FALLBACK_HINT,
        severity=Severity.ERROR,
        technical_details={"provider": _PROVIDER_NAME, "error": str(exc)},
    )


class OpenAIEmbeddingProvider:
    """Fournisseur d'embeddings OpenAI."""

    def __init__(
        self,
        *,
        api_key: str,
        client: OpenAI | None = None,
        model: str = _MODEL,
    ) -> None:
        """Construit l'adaptateur.

        Args:
            api_key: Clé API OpenAI.
            client: Client OpenAI injectable (tests).
            model: Modèle d'embedding.
        """
        self._client = client or OpenAI(api_key=api_key)
        self._model = model
        self._consumed_cost_usd = 0.0

    @property
    def model(self) -> str:
        """Identifiant du modèle d'embedding (pour l'empreinte d'index)."""
        return self._model

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Calcule les vecteurs d'une liste de documents.

        Args:
            texts: Textes à encoder.

        Returns:
            Un vecteur par texte (vide si ``texts`` est vide).

        Raises:
            EmbeddingError: En cas d'échec d'appel (auth, rate-limit, API).
        """
        if not texts:
            return []
        try:
            response = self._client.embeddings.create(model=self._model, input=texts)
        except (APIError, APIStatusError, AuthenticationError, RateLimitError) as exc:
            raise _map_embedding_error(exc) from exc
        self._consumed_cost_usd += embedding_cost_usd(
            model=self._model, total_tokens=response.usage.total_tokens
        )
        return [list(item.embedding) for item in response.data]

    def embed_query(self, text: str) -> list[float]:
        """Calcule le vecteur d'une requête.

        Args:
            text: Texte de la requête.

        Returns:
            Le vecteur.
        """
        return self.embed_documents([text])[0]

    def consumed_cost_usd(self) -> float:
        """Coût cumulé (USD) des embeddings calculés depuis la construction.

        Returns:
            La somme des coûts (selon ``usage`` renvoyé par l'API et la grille
            tarifaire du modèle).
        """
        return self._consumed_cost_usd
