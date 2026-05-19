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
        term: Le terme tel qu'il apparaît dans le contenu.
        definition: Définition contextuelle produite par les phases LLM.
        sources: Vidéos d'où le terme a été extrait.
        aliases: Variantes orthographiques ou rédactionnelles connues.
        cross_lang: Mapping ``Language`` → traduction (alimenté par la phase 6).
    """

    term: str
    definition: str
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
