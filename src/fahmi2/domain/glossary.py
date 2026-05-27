"""Entités Term et Glossary (immuables), localisation et rendu Markdown du glossaire.

Source unique des en-têtes/titres localisés du glossaire (``_HEADERS_BY_LANGUAGE`` /
``_TITLE_BY_LANGUAGE``), des helpers de localisation des termes par langue cible
(``cross_lang``) et du rendu en tableau Markdown. Module de domaine pur (ni Qt, ni HTTP,
ni SQL).
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field, replace
from typing import Any

from fahmi2.domain.enums import Language
from fahmi2.domain.ids import SourceId

_HEADERS_BY_LANGUAGE: dict[Language, tuple[str, str, str, str]] = {
    Language.FR: ("Terme", "Acronyme", "Signification", "Définition"),
    Language.EN: ("Term", "Acronym", "Meaning", "Definition"),
    Language.DE: ("Begriff", "Akronym", "Bedeutung", "Definition"),
    Language.ES: ("Término", "Acrónimo", "Significado", "Definición"),
    Language.IT: ("Termine", "Acronimo", "Significato", "Definizione"),
    Language.ZH: ("术语", "缩写", "含义", "定义"),
    Language.AR: ("المصطلح", "الاختصار", "المعنى", "التعريف"),
}

#: Titre H1 localisé du glossaire par langue (cohérent avec les en-têtes).
_TITLE_BY_LANGUAGE: dict[Language, str] = {
    Language.FR: "Glossaire",
    Language.EN: "Glossary",
    Language.DE: "Glossar",
    Language.ES: "Glosario",
    Language.IT: "Glossario",
    Language.ZH: "术语表",
    Language.AR: "مسرد المصطلحات",
}


def glossary_title(language: Language) -> str:
    """Titre H1 localisé du glossaire pour une langue.

    Args:
        language: Langue cible.

    Returns:
        Le titre localisé (ex: ``"Glossaire"``) ; repli anglais si la langue est
        hors périmètre.
    """
    return _TITLE_BY_LANGUAGE.get(language, _TITLE_BY_LANGUAGE[Language.EN])


@dataclass(frozen=True)
class LocalizedTerm:
    """Forme localisée d'un terme du glossaire dans une langue cible.

    Conservée dans ``Term.cross_lang`` (persistée par la phase 6). Porte la **forme
    traduite du terme** et sa **définition traduite** ; l'``acronym_expansion`` (colonne
    *Signification*) reste, elle, invariante par langue (intrinsèque à l'acronyme, jamais
    traduite).

    Attributes:
        term: Terme traduit dans la langue cible.
        definition: Définition traduite dans la langue cible.
    """

    term: str
    definition: str


def glossary_term_for_language(term: Term, language: Language) -> str:
    """Forme localisée d'un terme pour une langue (repli sur le terme source).

    Args:
        term: Terme du glossaire master.
        language: Langue cible.

    Returns:
        ``term.cross_lang[language].term`` s'il existe, sinon ``term.term``.
    """
    localized = term.cross_lang.get(language)
    return localized.term if localized is not None else term.term


def localize_glossary_terms(
    terms: Iterable[Term], language: Language
) -> tuple[Term, ...]:
    """Vue du glossaire pour une langue : remplace **terme et définition** par leur
    localisation (``cross_lang[language]``) ; ``acronym`` et ``acronym_expansion``
    restent inchangés (l'expansion d'acronyme est invariante par langue). Repli sur la
    forme/définition source si la langue n'est pas localisée.

    Args:
        terms: Termes du glossaire master.
        language: Langue de la vue voulue.

    Returns:
        Un tuple de ``Term`` dont ``term`` **et** ``definition`` sont localisés (repli
        sur la source si la langue manque).
    """
    localized_terms: list[Term] = []
    for t in terms:
        loc = t.cross_lang.get(language)
        if loc is None:
            localized_terms.append(t)
        else:
            localized_terms.append(
                replace(t, term=loc.term, definition=loc.definition)
            )
    return tuple(localized_terms)


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
        cross_lang: Mapping ``Language`` → ``LocalizedTerm`` (terme **et** définition
            traduits ; alimenté par la phase 6).
    """

    term: str
    definition: str
    acronym: str | None = None
    acronym_expansion: str | None = None
    sources: tuple[SourceId, ...] = ()
    aliases: tuple[str, ...] = ()
    cross_lang: dict[Language, LocalizedTerm] = field(default_factory=dict)


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
        source_definition = str(raw.get("definition", ""))
        result.append(
            Term(
                term=str(raw.get("term", "")),
                definition=source_definition,
                acronym=str(acronym) if acronym else None,
                acronym_expansion=str(expansion) if expansion else None,
                sources=tuple(SourceId(value=str(s)) for s in sources_raw),
                aliases=tuple(str(a) for a in aliases_raw),
                cross_lang=_parse_cross_lang(cross_lang_raw, source_definition),
            )
        )
    return tuple(result)


def _parse_cross_lang(
    raw: dict[str, Any], source_definition: str
) -> dict[Language, LocalizedTerm]:
    """Parse le mapping ``cross_lang`` (tolérant au format legacy terme-seul).

    Args:
        raw: Mapping brut ``code_langue -> valeur`` ; valeur = objet
            ``{"term", "definition"}`` (format courant) ou chaîne (legacy = terme seul,
            définition restée en langue source).
        source_definition: Définition source, repli quand seul le terme est connu.

    Returns:
        Mapping ``Language -> LocalizedTerm`` (définition repliée sur la source en legacy).
    """
    result: dict[Language, LocalizedTerm] = {}
    for code, value in raw.items():
        if isinstance(value, dict):
            result[Language(code)] = LocalizedTerm(
                term=str(value.get("term", "")),
                definition=str(value.get("definition", source_definition)),
            )
        else:  # legacy : chaîne = terme localisé seul (définition source conservée)
            result[Language(code)] = LocalizedTerm(
                term=str(value), definition=source_definition
            )
    return result


def _escape_table_cell(value: str) -> str:
    """Échappe une valeur pour une cellule de tableau Markdown.

    Échappe les barres verticales (sinon elles découperaient la cellule) et aplatit
    les sauts de ligne (sinon ils casseraient la ligne du tableau).

    Args:
        value: Valeur brute de la cellule.

    Returns:
        La valeur sûre pour insertion dans une cellule de tableau pipe.
    """
    return value.replace("|", "\\|").replace("\n", " ")


def render_glossary_markdown_table(
    *,
    language: Language,
    terms: Iterable[Term],
) -> str:
    """Rend une liste de ``Term`` au format tableau Markdown 4 colonnes.

    Le **titre H1 et les en-têtes** sont localisés depuis ``language`` (titre via
    :func:`glossary_title`, en-têtes via ``_HEADERS_BY_LANGUAGE``) : impossible de
    désaligner titre et colonnes. La colonne *Signification* contient l'expansion
    littérale de l'acronyme, conservée dans sa langue d'origine (vide si le terme
    n'a pas d'acronyme).

    Args:
        language: Langue cible (pilote le titre H1 et les libellés d'en-têtes).
        terms: Termes à afficher (déjà triés par l'appelant).

    Returns:
        Le Markdown complet (titre, ligne vide, tableau, saut final).
    """
    headers = _HEADERS_BY_LANGUAGE.get(language, _HEADERS_BY_LANGUAGE[Language.EN])
    lines: list[str] = [f"# {glossary_title(language)}", ""]
    lines.append(f"| {headers[0]} | {headers[1]} | {headers[2]} | {headers[3]} |")
    lines.append("|---|---|---|---|")
    for term in terms:
        term_cell = _escape_table_cell(term.term)
        acronym_cell = _escape_table_cell(term.acronym or "")
        expansion_cell = _escape_table_cell(term.acronym_expansion or "")
        def_cell = _escape_table_cell(term.definition)
        lines.append(
            f"| {term_cell} | {acronym_cell} | {expansion_cell} | {def_cell} |"
        )
    return "\n".join(lines) + "\n"
