"""Parsing des marqueurs de citation [§N] d'une réponse en ``Citation``.

Le prompt impose des marqueurs ``[§N]`` référant les passages numérotés fournis.
Le parsing est **tolérant** : un index hors bornes est ignoré, les doublons sont
dédupliqués (par ancre), une réponse sans marqueur donne un tuple vide.
"""

from __future__ import annotations

import re

from fahmi2.domain.chat import Citation, RetrievedPassage

_RE_CITATION = re.compile(r"\[§(\d+)\]")
_SNIPPET_MAX_CHARS = 160


def parse_citations(
    answer: str, passages: tuple[RetrievedPassage, ...]
) -> tuple[Citation, ...]:
    """Extrait les citations d'une réponse et les mappe aux passages.

    Args:
        answer: Texte de la réponse du LLM.
        passages: Passages numérotés fournis au prompt (1-based dans la réponse).

    Returns:
        Citations uniques (dédupliquées par ancre), dans l'ordre d'apparition.
    """
    citations: list[Citation] = []
    seen: set[str] = set()
    for match in _RE_CITATION.finditer(answer):
        index = int(match.group(1))
        if not 1 <= index <= len(passages):
            continue
        chunk = passages[index - 1].chunk
        if chunk.anchor in seen:
            continue
        seen.add(chunk.anchor)
        citations.append(
            Citation(
                chapter_title=chunk.chapter_title,
                section_title=chunk.section_title,
                anchor=chunk.anchor,
                snippet=chunk.text[:_SNIPPET_MAX_CHARS],
            )
        )
    return tuple(citations)
