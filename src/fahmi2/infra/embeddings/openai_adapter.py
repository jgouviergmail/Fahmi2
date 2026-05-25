"""``OpenAIEmbeddingProvider`` — embeddings via l'API OpenAI.

Utilise le SDK ``openai`` (déjà présent pour Whisper cloud) avec le modèle
``text-embedding-3-small``. Réutilise la clé OpenAI gérée par ``SecretsService``.
"""

from __future__ import annotations

from openai import OpenAI

_MODEL = "text-embedding-3-small"


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
        """
        if not texts:
            return []
        response = self._client.embeddings.create(model=self._model, input=texts)
        return [list(item.embedding) for item in response.data]

    def embed_query(self, text: str) -> list[float]:
        """Calcule le vecteur d'une requête.

        Args:
            text: Texte de la requête.

        Returns:
            Le vecteur.
        """
        return self.embed_documents([text])[0]
