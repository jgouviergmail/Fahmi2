"""Entités Term et Glossary (immuables)."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field

from fahmi2.domain.enums import Language
from fahmi2.domain.ids import VideoId


@dataclass(frozen=True)
class Term:
    """Terme du glossaire avec définition contextualisée.

    Attributes:
        term: Le terme tel qu'il apparaît dans le contenu (forme longue
            préférable, ex: « Produit intérieur brut »).
        definition: Définition contextuelle produite par les phases LLM.
        acronym: Acronyme officiel associé au terme (ex: « PIB »), ou
            ``None`` si le terme n'en a pas.
        acronym_expansion: Signification littérale de l'acronyme dans sa
            langue d'origine (ex: « ROI » → « Return On Investment »,
            « PIB » → « Produit Intérieur Brut »). Ce champ est intrinsèque
            à l'acronyme : il n'est jamais traduit (les acronymes
            techniques gardent leur signification dans leur langue
            d'origine quelle que soit la langue du glossaire). ``None``
            si l'acronyme n'a pas d'expansion connue.
        sources: Vidéos d'où le terme a été extrait.
        aliases: Variantes orthographiques ou rédactionnelles connues
            (différentes de l'acronyme).
        cross_lang: Mapping ``Language`` → traduction (alimenté par la phase 6).
    """

    term: str
    definition: str
    acronym: str | None = None
    acronym_expansion: str | None = None
    sources: tuple[VideoId, ...] = ()
    aliases: tuple[str, ...] = ()
    cross_lang: dict[Language, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Glossary:
    """Glossaire pour une langue donnée."""

    language: Language
    terms: tuple[Term, ...]

    def __len__(self) -> int:
        return len(self.terms)

    def __iter__(self) -> Iterator[Term]:
        return iter(self.terms)

    def find(self, term: str) -> Term | None:
        """Retourne le ``Term`` correspondant exactement (case-sensitive) ou ``None``.

        Args:
            term: Chaîne exacte à chercher.

        Returns:
            Le terme trouvé, ou ``None``.
        """
        for t in self.terms:
            if t.term == term:
                return t
        return None

    def with_added_term(self, term: Term) -> Glossary:
        """Retourne un nouveau ``Glossary`` avec ce terme ajouté en fin.

        Args:
            term: Terme à ajouter.

        Returns:
            Nouvelle instance immuable.
        """
        return Glossary(language=self.language, terms=(*self.terms, term))
