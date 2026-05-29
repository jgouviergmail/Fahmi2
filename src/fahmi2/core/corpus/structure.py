"""Parseur de structure du document consolidé (``consolidated.{lang}.md``).

Module **neutre partagé** (pur Python, sans Qt/HTTP/SQL), consommé par la Pédagogie,
le Dialogue et les Visualisations. Le document consolidé (cf.
``pipeline/handlers/phase_5_consolidation``) place le titre global en ``# <titre>``,
les sections méta (Résumé, Introduction, Sommaire, Conclusion) en ``##``, les
**chapitres** en ``# N. <titre>``, et les **sous-sections** en ``## N.M`` / ``### N.M.K``.

Expose :

- ``Chapter`` / ``parse_chapters`` : découpage **chapitre** (comportement historique,
  inchangé — utilisé par la Pédagogie/Dialogue).
- ``Section`` / ``parse_sections`` : découpage **fin** de toutes les rubriques
  numérotées, avec ``section_path`` **invariant par langue** (dérivé du préfixe
  numérique du titre, ex. ``(2, 1, 1)``) — utilisé par les Visualisations.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from fahmi2.core.slugify import slugify_anchor

# H1 de chapitre : "# 1. Titre", "# 12. Autre". Le préfixe numérique distingue les
# chapitres du titre global (sans numéro) et des sections méta (qui sont en ##).
_RE_CHAPTER_H1 = re.compile(r"^#\s+(\d+)\.\s+(.+?)\s*$")

# Toute rubrique numérotée (H1..H6) : "# 2. T", "## 2.1 T", "### 2.1.1 T".
# Le point final après le dernier nombre est optionnel (présent sur les chapitres).
_RE_NUMBERED_HEADING = re.compile(r"^(#{1,6})\s+(\d+(?:\.\d+)*)\.?\s+(.+?)\s*$")


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


@dataclass(frozen=True)
class Section:
    """Rubrique numérotée du document consolidé (chapitre ou sous-section).

    Attributes:
        section_path: Chemin structurel issu du préfixe numérique du titre
            (ex: ``(2, 1, 1)`` pour « 2.1.1 »). **Invariant par langue** (les
            numéros ne sont pas traduits).
        level: Profondeur du titre (1 = ``#``, 2 = ``##``, 3 = ``###`` …).
        title: Titre sans le préfixe numérique.
        anchor: Ancre GFM (slug) du titre complet (numéro inclus), telle que
            produite par le rendu Markdown.
        body_markdown: Corps Markdown **direct** (jusqu'au prochain titre numéroté
            de **n'importe quel** niveau), hors sous-rubriques.
    """

    section_path: tuple[int, ...]
    level: int
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
                anchor=slugify_anchor(f"{index}. {title}"),
                body_markdown=body,
            )
        )
    return tuple(chapters)


def parse_sections(consolidated_markdown: str) -> tuple[Section, ...]:
    """Découpe le document en toutes les rubriques numérotées (chapitres + sous-sections).

    Args:
        consolidated_markdown: Contenu du fichier ``consolidated.{lang}.md``.

    Returns:
        Tuple ordonné des ``Section``. Vide si aucune rubrique numérotée. Le corps de
        chaque rubrique s'arrête au prochain titre numéroté (tout niveau), de sorte
        qu'une sous-section feuille porte son contenu propre.
    """
    lines = consolidated_markdown.splitlines()
    heads: list[tuple[int, int, tuple[int, ...], str, str]] = []
    for line_idx, line in enumerate(lines):
        match = _RE_NUMBERED_HEADING.match(line)
        if match is None:
            continue
        hashes, number, title = match.group(1), match.group(2), match.group(3).strip()
        path = tuple(int(part) for part in number.split("."))
        anchor = slugify_anchor(line.lstrip("#").strip())
        heads.append((line_idx, len(hashes), path, title, anchor))

    sections: list[Section] = []
    for pos, (line_idx, level, path, title, anchor) in enumerate(heads):
        end = heads[pos + 1][0] if pos + 1 < len(heads) else len(lines)
        body = "\n".join(lines[line_idx + 1 : end]).strip()
        sections.append(
            Section(
                section_path=path,
                level=level,
                title=title,
                anchor=anchor,
                body_markdown=body,
            )
        )
    return tuple(sections)
