"""Entités Term et Glossary (immuables)."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from typing import Any

from fahmi2.domain.enums import Language
from fahmi2.domain.ids import SourceId

_HEADERS_BY_LANGUAGE: dict[Language, tuple[str, str, str, str]] = {
    Language.FR: ("Terme", "Acronyme", "Signification", "Définition"),
    Language.EN: ("Term", "Acronym", "Meaning", "Definition"),
}


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
        sources: Sources d'où le terme a été extrait.
        aliases: Variantes orthographiques ou rédactionnelles connues
            (différentes de l'acronyme).
        cross_lang: Mapping ``Language`` → traduction (alimenté par la phase 6).
    """

    term: str
    definition: str
    acronym: str | None = None
    acronym_expansion: str | None = None
    sources: tuple[SourceId, ...] = ()
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


def parse_glossary_master_terms(payload: dict[str, Any]) -> tuple[Term, ...]:
    """Convertit un payload JSON ``glossary_master`` en termes domaine.

    Args:
        payload: Dictionnaire ``{"terms": [{...}, ...]}`` produit par la phase 2.

    Returns:
        Les ``Term`` (tuple vide si aucun terme).
    """
    raw_terms = payload.get("terms", [])
    result: list[Term] = []
    for raw in raw_terms:
        sources_raw = raw.get("sources", []) or []
        aliases_raw = raw.get("aliases", []) or []
        cross_lang_raw = raw.get("cross_lang", {}) or {}
        acronym = raw.get("acronym")
        expansion = raw.get("acronym_expansion")
        result.append(
            Term(
                term=str(raw.get("term", "")),
                definition=str(raw.get("definition", "")),
                acronym=str(acronym) if acronym else None,
                acronym_expansion=str(expansion) if expansion else None,
                sources=tuple(SourceId(value=str(s)) for s in sources_raw),
                aliases=tuple(str(a) for a in aliases_raw),
                cross_lang={Language(k): str(v) for k, v in cross_lang_raw.items()},
            )
        )
    return tuple(result)


def render_glossary_markdown_table(
    *,
    title: str,
    language: Language,
    terms: Iterable[Term],
) -> str:
    """Rend une liste de ``Term`` au format tableau Markdown 4 colonnes.

    Colonnes ``| Terme | Acronyme | Signification | Définition |`` (FR) ou
    ``| Term | Acronym | Meaning | Definition |`` (EN). La colonne *Signification*
    contient l'expansion littérale de l'acronyme, conservée dans sa langue
    d'origine. Vide si le terme n'a pas d'acronyme.

    Args:
        title: Titre H1 du document.
        language: Langue (libellés d'en-têtes).
        terms: Termes à afficher (déjà triés par l'appelant).

    Returns:
        Le Markdown complet (titre, ligne vide, tableau, saut final).
    """
    headers = _HEADERS_BY_LANGUAGE.get(language, _HEADERS_BY_LANGUAGE[Language.EN])
    lines: list[str] = [f"# {title}", ""]
    lines.append(f"| {headers[0]} | {headers[1]} | {headers[2]} | {headers[3]} |")
    lines.append("|---|---|---|---|")
    for term in terms:
        acronym = term.acronym or ""
        expansion = term.acronym_expansion or ""
        term_cell = term.term.replace("|", "\\|")
        acronym_cell = acronym.replace("|", "\\|")
        expansion_cell = expansion.replace("|", "\\|").replace("\n", " ")
        def_cell = term.definition.replace("|", "\\|").replace("\n", " ")
        lines.append(
            f"| {term_cell} | {acronym_cell} | {expansion_cell} | {def_cell} |"
        )
    return "\n".join(lines) + "\n"
