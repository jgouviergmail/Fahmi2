"""Service applicatif ``GlossaryReconciler``.

Ce service fournit une API stable au-dessus du glossaire master produit par la
phase 2 :

- Importer un payload JSON ``{terms: [...]}`` en termes ``Glossary`` (langue
  donnée) et le persister dans SQLite via ``SqliteState``.
- Exposer le glossaire d'un run sous forme d'entité domaine ``Glossary`` pour
  l'UI / l'export.
- Rendre le glossaire au format Markdown sous forme de tableau
  ``| Terme | Acronyme | Signification | Définition |`` trié
  alphabétiquement. La colonne *Signification* contient l'expansion
  littérale de l'acronyme dans sa langue d'origine.

L'injection top-K dans les prompts LLM est gérée plus bas par le
:py:class:`~fahmi2.core.retrieval.interface.GlossaryRetriever` (TF-IDF en v1).
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from fahmi2.domain.enums import Language
from fahmi2.domain.glossary import Glossary, Term
from fahmi2.domain.ids import RunId, VideoId
from fahmi2.infra.storage.sqlite_state import SqliteState

_TERMS_KEY = "terms"
_TITLE_BY_LANGUAGE: dict[Language, str] = {
    Language.FR: "Glossaire",
    Language.EN: "Glossary",
}
_HEADERS_BY_LANGUAGE: dict[Language, tuple[str, str, str, str]] = {
    Language.FR: ("Terme", "Acronyme", "Signification", "Définition"),
    Language.EN: ("Term", "Acronym", "Meaning", "Definition"),
}


class GlossaryReconciler:
    """Service applicatif de gestion du glossaire d'un Run."""

    def __init__(self, state: SqliteState) -> None:
        """Construit le service.

        Args:
            state: Accès au stockage SQLite.
        """
        self._state = state

    def import_master_payload(
        self,
        *,
        run_id: RunId,
        language: Language,
        payload: dict[str, Any],
    ) -> int:
        """Importe un payload JSON ``glossary_master`` en SQLite pour un Run.

        Args:
            run_id: Run propriétaire.
            language: Langue du glossaire.
            payload: Dictionnaire ``{"terms": [{...}, ...]}``.

        Returns:
            Nombre de termes effectivement importés.
        """
        terms = self._extract_terms(payload)
        for term in terms:
            self._state.upsert_glossary_term(run_id, language, term)
        return len(terms)

    def load_glossary(self, run_id: RunId, language: Language) -> Glossary:
        """Charge le glossaire d'un run pour une langue.

        Args:
            run_id: Run.
            language: Langue.

        Returns:
            ``Glossary`` (possiblement vide).
        """
        terms = self._state.list_glossary_terms(run_id, language)
        return Glossary(language=language, terms=tuple(terms))

    def render_markdown(self, run_id: RunId, language: Language) -> str:
        """Rend le glossaire d'un run en tableau Markdown.

        Args:
            run_id: Run.
            language: Langue.

        Returns:
            Markdown : titre H1 + tableau ``| Terme | Acronyme | Définition |``
            trié alphabétiquement par terme.
        """
        glossary = self.load_glossary(run_id, language)
        title = _TITLE_BY_LANGUAGE.get(language, "Glossary")
        sorted_terms = sorted(glossary, key=lambda t: t.term.casefold())
        return render_glossary_markdown_table(
            title=title,
            language=language,
            terms=sorted_terms,
        )

    @staticmethod
    def _extract_terms(payload: dict[str, Any]) -> list[Term]:
        """Convertit un payload JSON master en liste de ``Term``.

        Args:
            payload: Dictionnaire ``{"terms": [{...}, ...]}``.

        Returns:
            Liste de ``Term`` domaine.
        """
        raw_terms = payload.get(_TERMS_KEY, [])
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
                    sources=tuple(VideoId(value=str(s)) for s in sources_raw),
                    aliases=tuple(str(a) for a in aliases_raw),
                    cross_lang={
                        Language(k): str(v) for k, v in cross_lang_raw.items()
                    },
                )
            )
        return result


def render_glossary_markdown_table(
    *,
    title: str,
    language: Language,
    terms: Iterable[Term],
) -> str:
    """Rend une liste de ``Term`` au format tableau Markdown.

    Le tableau a 4 colonnes :
    ``| Terme | Acronyme | Signification | Définition |`` en français, et
    ``| Term | Acronym | Meaning | Definition |`` en anglais. La colonne
    *Signification* / *Meaning* contient l'expansion littérale de
    l'acronyme dans sa langue d'origine (ex. *ROI* → *Return On Investment*
    en anglais même dans un glossaire en français). Elle reste vide si
    le terme n'a pas d'acronyme.

    Args:
        title: Titre H1 du document.
        language: Langue (pour les libellés d'en-têtes).
        terms: Termes à afficher (déjà triés par l'appelant).

    Returns:
        Le Markdown complet avec titre, ligne vide, tableau, ligne finale.
    """
    headers = _HEADERS_BY_LANGUAGE.get(language, _HEADERS_BY_LANGUAGE[Language.EN])
    lines: list[str] = [f"# {title}", ""]
    lines.append(
        f"| {headers[0]} | {headers[1]} | {headers[2]} | {headers[3]} |"
    )
    lines.append("|---|---|---|---|")
    for term in terms:
        acronym = term.acronym or ""
        expansion = term.acronym_expansion or ""
        # Échappement des pipes dans les contenus pour ne pas casser le tableau
        term_cell = term.term.replace("|", "\\|")
        acronym_cell = acronym.replace("|", "\\|")
        expansion_cell = expansion.replace("|", "\\|").replace("\n", " ")
        def_cell = term.definition.replace("|", "\\|").replace("\n", " ")
        lines.append(
            f"| {term_cell} | {acronym_cell} | {expansion_cell} | {def_cell} |"
        )
    return "\n".join(lines) + "\n"
