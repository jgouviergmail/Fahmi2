"""``OpenAIVisionAdapter`` — analyse de slides via l'API vision OpenAI.

Utilise le SDK ``openai`` (déjà présent pour Whisper cloud et les
embeddings). Le modèle est configurable (cf.
:class:`fahmi2.domain.enums.VisionModel`), défaut ``gpt-5-mini``. Sortie en
**JSON mode** (objet ``{"texte", "visuels"}``), parsing *lenient* (clés
manquantes = chaînes vides). Le prompt est chargé via ``PromptLoader``
(défaut bundlé ``phase_0_slide_analysis.j2``, override ``%APPDATA%``).
"""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

from openai import APIError, APIStatusError, AuthenticationError, OpenAI, RateLimitError

from fahmi2.core.errors.exceptions import VisionError
from fahmi2.core.errors.severity import Severity
from fahmi2.domain.enums import Language, VisionModel
from fahmi2.domain.languages import language_label
from fahmi2.infra.prompts.loader import PromptLoader
from fahmi2.infra.vision._pricing import vision_cost_usd
from fahmi2.infra.vision.interface import SlideAnalysis, SlideContent

_MODEL = str(VisionModel.GPT_5_MINI)
_PROVIDER_NAME = "openai-vision"
_PROMPT_NAME = "phase_0_slide_analysis"
_JSON_RESPONSE_FORMAT: dict[str, str] = {"type": "json_object"}
_IMAGE_MIME = "image/jpeg"
_TEXT_KEY = "texte"
_VISUALS_KEY = "visuels"
#: Longueur maximale de la réponse brute remontée dans les détails d'erreur.
_RAW_EXCERPT_MAX_CHARS = 500


def _map_vision_error(
    exc: APIStatusError | RateLimitError | AuthenticationError | APIError,
) -> VisionError:
    """Convertit une exception OpenAI en ``VisionError`` typée (message FR).

    Aligné sur le mapping des adapters STT/LLM/embeddings (homogénéité) :
    clé refusée, limite de débit, ou erreur d'API générique.

    Args:
        exc: Exception levée par le SDK OpenAI.

    Returns:
        La ``VisionError`` correspondante.
    """
    if isinstance(exc, AuthenticationError):
        return VisionError(
            code="VISION.AUTH_INVALID",
            user_message=(
                "La clé OpenAI est refusée pour l'analyse des slides. "
                "Vérifie-la dans Paramètres › Clés API."
            ),
            severity=Severity.ERROR,
            technical_details={"provider": _PROVIDER_NAME},
        )
    if isinstance(exc, RateLimitError):
        return VisionError(
            code="VISION.RATE_LIMIT",
            user_message="Limite de débit OpenAI atteinte (analyse des slides).",
            severity=Severity.WARNING,
            technical_details={"provider": _PROVIDER_NAME},
        )
    return VisionError(
        code="VISION.API_ERROR",
        user_message="Échec de l'analyse vision d'une slide.",
        severity=Severity.ERROR,
        technical_details={"provider": _PROVIDER_NAME, "error": str(exc)},
    )


class OpenAIVisionAdapter:
    """Fournisseur d'analyse vision de slides (OpenAI)."""

    def __init__(
        self,
        *,
        api_key: str,
        prompts: PromptLoader,
        client: Any | None = None,  # noqa: ANN401 — client factice en tests
        model: str = _MODEL,
    ) -> None:
        """Construit l'adaptateur.

        Args:
            api_key: Clé API OpenAI.
            prompts: Loader de templates (défauts bundlés + overrides).
            client: Client OpenAI injectable (tests).
            model: Identifiant du modèle vision.
        """
        self._client = client or OpenAI(api_key=api_key)
        self._prompts = prompts
        self._model = model

    def analyze_slide(
        self, image_path: Path, *, language: Language
    ) -> SlideAnalysis:
        """Analyse l'image d'une slide (cf. ``SlideVisionProvider``).

        Args:
            image_path: Image JPEG de la frame représentative.
            language: Langue de sortie (langue détectée par le STT).

        Returns:
            Le ``SlideAnalysis`` (contenu + coût réel USD).

        Raises:
            VisionError: Échec d'appel API ou réponse non-JSON.
        """
        prompt = self._prompts.render(
            _PROMPT_NAME, language_label=language_label(language)
        )
        encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                response_format=_JSON_RESPONSE_FORMAT,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{_IMAGE_MIME};base64,{encoded}"
                                },
                            },
                        ],
                    }
                ],
            )
        except (APIError, APIStatusError, AuthenticationError, RateLimitError) as exc:
            raise _map_vision_error(exc) from exc
        raw = response.choices[0].message.content or ""
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise VisionError(
                code="VISION.INVALID_RESPONSE",
                user_message="Le modèle vision a renvoyé une réponse illisible.",
                severity=Severity.ERROR,
                technical_details={
                    "provider": _PROVIDER_NAME,
                    "raw": raw[:_RAW_EXCERPT_MAX_CHARS],
                },
            ) from exc
        content = SlideContent(
            text=str(payload.get(_TEXT_KEY, "")),
            visuals_description=str(payload.get(_VISUALS_KEY, "")),
        )
        usage = response.usage
        cost = vision_cost_usd(
            model=self._model,
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
        )
        return SlideAnalysis(content=content, cost_usd=cost)
