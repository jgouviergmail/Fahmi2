"""Doubles de test du sous-système vision."""

from __future__ import annotations

from pathlib import Path

from fahmi2.domain.enums import Language
from fahmi2.infra.vision.interface import SlideAnalysis, SlideContent

_DEFAULT_CONTENT = SlideContent(
    text="Texte de slide factice", visuals_description="Un schéma factice"
)
_DEFAULT_COST_USD = 0.001


class FakeVisionProvider:
    """Provider vision déterministe pour les tests.

    Attributes:
        calls: Chemins d'images reçus, dans l'ordre des appels.
    """

    def __init__(
        self,
        *,
        content: SlideContent = _DEFAULT_CONTENT,
        cost_per_call_usd: float = _DEFAULT_COST_USD,
        empty_names: frozenset[str] = frozenset(),
    ) -> None:
        """Construit le fake.

        Args:
            content: Contenu renvoyé pour chaque image analysée.
            cost_per_call_usd: Coût simulé par appel.
            empty_names: Noms de fichiers (``Path.name``) pour lesquels un
                contenu vide est renvoyé (simule une frame sans slide).
        """
        self._content = content
        self._cost = cost_per_call_usd
        self._empty_names = empty_names
        self.calls: list[Path] = []

    def analyze_slide(
        self, image_path: Path, *, language: Language
    ) -> SlideAnalysis:
        """Renvoie le contenu configuré (cf. ``SlideVisionProvider``).

        Args:
            image_path: Image reçue (enregistrée dans ``calls``).
            language: Langue demandée (ignorée).

        Returns:
            Le ``SlideAnalysis`` simulé.
        """
        del language
        self.calls.append(image_path)
        if image_path.name in self._empty_names:
            return SlideAnalysis(
                content=SlideContent(text="", visuals_description=""),
                cost_usd=self._cost,
            )
        return SlideAnalysis(content=self._content, cost_usd=self._cost)
