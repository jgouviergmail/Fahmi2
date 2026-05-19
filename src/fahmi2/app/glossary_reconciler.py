"""Service applicatif ``GlossaryReconciler``.

Ce service fournit une API stable au-dessus du glossaire master produit par la
phase 2 :

- Importer un payload JSON ``{terms: [...]}`` en termes ``Glossary`` (langue
  donnée) et le persister dans SQLite via ``SqliteState``.
- Exposer le glossaire d'un run sous forme d'entité domaine ``Glossary`` pour
  l'UI / l'export.
- Rendre le glossaire au format Markdown (titre + liste alphabétique).

L'injection top-K dans les prompts LLM est gérée plus bas par le
:py:class:`~fahmi2.core.retrieval.interface.GlossaryRetriever` (TF-IDF en v1).
"""

from __future__ import annotations

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
        """Rend le glossaire d'un run en Markdown.

        Args:
            run_id: Run.
            language: Langue.

        Returns:
            Markdown : titre H1 + liste triée alphabétiquement de termes.
        """
        glossary = self.load_glossary(run_id, language)
        title = _TITLE_BY_LANGUAGE.get(language, "Glossary")
        lines: list[str] = [f"# {title}", ""]
        sorted_terms = sorted(glossary, key=lambda t: t.term.casefold())
        for term in sorted_terms:
            lines.append(f"- **{term.term}** : {term.definition}")
        return "\n".join(lines) + "\n"

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
            result.append(
                Term(
                    term=str(raw.get("term", "")),
                    definition=str(raw.get("definition", "")),
                    sources=tuple(VideoId(value=str(s)) for s in sources_raw),
                    aliases=tuple(str(a) for a in aliases_raw),
                    cross_lang={Language(k): str(v) for k, v in cross_lang_raw.items()},
                )
            )
        return result
