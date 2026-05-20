"""Parseur de chapitres du document consolidé (``consolidated.{lang}.md``).

Le document consolidé (cf. ``pipeline/handlers/phase_5_consolidation``) place le
titre global en ``# <titre>``, les sections méta (Résumé, Introduction, Sommaire,
Conclusion) en ``##``, et chaque **chapitre** en ``# N. <titre>``. Ce parseur
isole donc uniquement les ``#`` à préfixe numérique comme frontières de chapitre.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# H1 de chapitre : "# 1. Titre", "# 12. Autre". Le préfixe numérique distingue les
# chapitres du titre global (sans numéro) et des sections méta (qui sont en ##).
_RE_CHAPTER_H1 = re.compile(r"^#\s+(\d+)\.\s+(.+?)\s*$")
_RE_ANCHOR_STRIP = re.compile(r"[^\w\s-]", flags=re.UNICODE)
_RE_ANCHOR_SPACES = re.compile(r"\s+")


@dataclass(frozen=True)
class Chapter:
    """Chapitre extrait du document consolidé.

    Attributes:
        index: Numéro du chapitre (1, 2, …).
        title: Titre sans le préfixe ``"N. "``.
        anchor: Ancre GFM (slug) vers le titre numéroté (ex: ``"1-bases"``).
        body_markdown: Corps Markdown du chapitre (jusqu'au chapitre suivant).
    """

    index: int
    title: str
    anchor: str
    body_markdown: str


def parse_chapters(consolidated_markdown: str) -> tuple[Chapter, ...]:
    """Découpe le document consolidé en chapitres (``# N. …``).

    Args:
        consolidated_markdown: Contenu du fichier ``consolidated.{lang}.md``.

    Returns:
        Tuple ordonné des chapitres. Vide si aucun chapitre numéroté.
    """
    lines = consolidated_markdown.splitlines()
    starts: list[tuple[int, int, str]] = []  # (line_idx, index, title)
    for line_idx, line in enumerate(lines):
        match = _RE_CHAPTER_H1.match(line)
        if match is not None:
            starts.append((line_idx, int(match.group(1)), match.group(2).strip()))

    chapters: list[Chapter] = []
    for pos, (line_idx, index, title) in enumerate(starts):
        end = starts[pos + 1][0] if pos + 1 < len(starts) else len(lines)
        body = "\n".join(lines[line_idx + 1 : end]).strip()
        chapters.append(
            Chapter(
                index=index,
                title=title,
                anchor=_slugify(f"{index}. {title}"),
                body_markdown=body,
            )
        )
    return tuple(chapters)


def _slugify(text: str) -> str:
    """Construit une ancre GFM (minuscules, tirets) à partir d'un titre.

    Args:
        text: Texte du titre (ex: ``"1. Bases"``).

    Returns:
        Slug GFM (ex: ``"1-bases"``).
    """
    lowered = text.strip().lower()
    cleaned = _RE_ANCHOR_STRIP.sub("", lowered)
    return _RE_ANCHOR_SPACES.sub("-", cleaned).strip("-")
