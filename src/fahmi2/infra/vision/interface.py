"""Port ``SlideVisionProvider`` et types associés.

Contrat du fournisseur d'analyse vision de slides (adapter OpenAI en
production, fake déterministe en tests) et structures immuables échangées
avec l'ingestion : contenu extrait d'une slide, résultat d'appel (contenu +
coût), slide analysée horodatée.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from fahmi2.domain.enums import Language


@dataclass(frozen=True)
class SlideContent:
    """Contenu extrait d'une slide par le modèle vision.

    Attributes:
        text: Transcription fidèle du texte visible (vide si aucun).
        visuals_description: Description synthétique des éléments visuels
            porteurs de sens (vide si aucun).
    """

    text: str
    visuals_description: str

    def is_empty(self) -> bool:
        """``True`` si la slide n'a produit aucun contenu exploitable.

        Returns:
            ``True`` quand texte et description sont vides (frame sans slide).
        """
        return not self.text.strip() and not self.visuals_description.strip()


@dataclass(frozen=True)
class SlideAnalysis:
    """Résultat d'un appel vision sur une image de slide.

    Attributes:
        content: Contenu extrait.
        cost_usd: Coût réel de l'appel (USD) — porté par appel pour permettre
            l'attribution per-source sous parallélisme.
    """

    content: SlideContent
    cost_usd: float


@dataclass(frozen=True)
class AnalyzedSlide:
    """Une slide analysée, horodatée sur sa plage d'affichage dans la vidéo.

    Attributes:
        start_seconds: Début d'affichage de la slide (s).
        end_seconds: Fin d'affichage (s, >= start_seconds).
        content: Contenu extrait par le modèle vision.
    """

    start_seconds: float
    end_seconds: float
    content: SlideContent


class SlideVisionProvider(Protocol):
    """Contrat d'un fournisseur d'analyse vision de slides."""

    def analyze_slide(
        self, image_path: Path, *, language: Language
    ) -> SlideAnalysis:
        """Analyse l'image d'une slide (texte fidèle + description des visuels).

        Args:
            image_path: Image JPEG/PNG de la frame représentative de la slide.
            language: Langue de sortie (langue détectée par le STT — le
                transcript fusionné reste monolingue).

        Returns:
            Le ``SlideAnalysis`` (contenu, éventuellement vide, + coût USD).

        Raises:
            VisionError: En cas d'échec d'appel (auth, rate-limit, API).
        """
