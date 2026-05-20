"""Entités structurées des supports de révision (immuables).

Représentations consommées par les exports SP3 (Anki, Markdown/PDF) et écrites
sur disque (JSON + Markdown rendu). Les entités spécifiques aux supports
évaluatifs (``QcmItem``, ``ClozeItem``…) sont ajoutées par leurs tranches
respectives (SP2/03). Le ``source_ref`` trace l'origine (terme de glossaire ou
ancre/chapitre du document consolidé).
"""

from __future__ import annotations

from dataclasses import dataclass

from fahmi2.domain.enums import Language, SupportType


@dataclass(frozen=True)
class Flashcard:
    """Carte recto/verso.

    Attributes:
        front: Recto (terme / acronyme / question).
        back: Verso (définition / réponse).
        source_ref: Référence d'origine (terme de glossaire ou ancre de chapitre).
        tags: Étiquettes (type de support, langue…), pour l'export Anki.
    """

    front: str
    back: str
    source_ref: str
    tags: tuple[str, ...] = ()


#: Union des entités structurées portées par un ``SupportArtifact``. S'étend au SP2/03.
SupportItem = Flashcard


@dataclass(frozen=True)
class SupportArtifact:
    """Enveloppe unifiée d'un support généré (écrite en JSON + Markdown).

    Attributes:
        support_type: Type de support.
        language: Langue du support.
        items: Entités structurées (cartes, questions…).
        rendered_markdown: Rendu Markdown lisible du support.
        cost_usd: Coût LLM de génération (0.0 pour les supports sans LLM).
    """

    support_type: SupportType
    language: Language
    items: tuple[SupportItem, ...]
    rendered_markdown: str
    cost_usd: float = 0.0

    def __post_init__(self) -> None:
        if self.cost_usd < 0:
            raise ValueError(f"cost_usd must be >= 0, got {self.cost_usd}")
