"""Résolution des marqueurs de citation [§N] d'une réponse.

Le prompt impose des marqueurs ``[§N]`` (N = index 1-based du passage fourni). On
réécrit chaque marqueur **valide** en lien Markdown ``[[K]](ancre)`` (K = numéro
d'affichage séquentiel, dédupliqué par ancre) et on **retire** les marqueurs hors
bornes. La liaison est matérialisée à la réécriture : le rendu Markdown produit
ensuite des liens cliquables sans risque de confondre un ``[3]`` littéral du cours.
"""

from __future__ import annotations

import re

from fahmi2.domain.chat import Citation, RetrievedPassage

#: Marqueur de citation, avec une espace optionnelle capturée en amont (pour ne
#: pas laisser de double espace quand un marqueur invalide est retiré).
_RE_CITATION = re.compile(r" ?\[§(\d+)\]")
#: Gabarit du lien Markdown de citation : texte ``[K]`` pointant vers l'ancre GFM.
_CITATION_LINK_TEMPLATE = "[[{number}]]({anchor})"
_SNIPPET_MAX_CHARS = 160


def resolve_citations(
    answer: str, passages: tuple[RetrievedPassage, ...]
) -> tuple[str, tuple[Citation, ...]]:
    """Réécrit les marqueurs ``[§N]`` en liens numérotés et extrait les citations.

    Args:
        answer: Texte de la réponse du LLM (marqueurs ``[§N]``, 1-based).
        passages: Passages numérotés fournis au prompt.

    Returns:
        ``(contenu_réécrit, citations)`` : le contenu où chaque ``[§N]`` valide est
        remplacé par ``[[K]](ancre)`` (les invalides retirés), et les citations
        uniques (dédupliquées par ancre) numérotées dans l'ordre d'apparition.
    """
    citations: list[Citation] = []
    number_by_anchor: dict[str, int] = {}

    def _replace(match: re.Match[str]) -> str:
        leading_space = " " if match.group(0).startswith(" ") else ""
        index = int(match.group(1))
        if not 1 <= index <= len(passages):
            return ""  # marqueur hors bornes : retiré avec l'espace adjacente
        chunk = passages[index - 1].chunk
        number = number_by_anchor.get(chunk.anchor)
        if number is None:
            number = len(number_by_anchor) + 1
            number_by_anchor[chunk.anchor] = number
            citations.append(
                Citation(
                    number=number,
                    chapter_title=chunk.chapter_title,
                    section_title=chunk.section_title,
                    anchor=chunk.anchor,
                    snippet=chunk.text[:_SNIPPET_MAX_CHARS],
                )
            )
        link = _CITATION_LINK_TEMPLATE.format(number=number, anchor=chunk.anchor)
        return f"{leading_space}{link}"

    rewritten = _RE_CITATION.sub(_replace, answer)
    return rewritten, tuple(citations)
