"""Construction des extraits source (langue courante) depuis les unités de texte.

Mutualise, pour les extracteurs (résolution d'entités, diagrammes), l'indexation des
unités par chemin de section et la fabrication d'``SourceExcerpt`` tronqués
proprement. Source unique de cette logique (zéro duplication).
"""

from __future__ import annotations

from dataclasses import dataclass

from fahmi2.domain.visuals import SourceExcerpt
from fahmi2.visuals._constants import EXCERPT_MAX_CHARS
from fahmi2.visuals.sources import TextUnit

_Path = tuple[int, ...]


def truncate_excerpt(text: str) -> str:
    """Normalise les espaces et tronque un extrait à ``EXCERPT_MAX_CHARS``.

    Args:
        text: Texte source.

    Returns:
        Le texte normalisé, suffixé d'une ellipse s'il a été tronqué (à la frontière
        d'un mot).
    """
    cleaned = " ".join(text.split())
    if len(cleaned) <= EXCERPT_MAX_CHARS:
        return cleaned
    cut = cleaned[:EXCERPT_MAX_CHARS].rsplit(" ", 1)[0].rstrip()
    return f"{cut}…"


@dataclass(frozen=True)
class SectionIndex:
    """Index des sections (par chemin structurel) pour fabriquer les extraits source.

    Attributes:
        text_by: Texte (tronqué) par chemin de section.
        title_by: Titre par chemin de section.
        anchor_by: Ancre GFM par chemin de section.
    """

    text_by: dict[_Path, str]
    title_by: dict[_Path, str]
    anchor_by: dict[_Path, str]

    def excerpt(self, path: _Path) -> SourceExcerpt | None:
        """Construit l'extrait source d'une section, ou ``None`` si inconnue.

        Args:
            path: Chemin structurel de la section.

        Returns:
            Le ``SourceExcerpt`` (texte tronqué) ou ``None``.
        """
        if path not in self.text_by:
            return None
        return SourceExcerpt(
            text=self.text_by[path],
            section_path=path,
            chapter_title=self.title_by[path],
            anchor=self.anchor_by[path],
        )

    def anchor(self, path: _Path) -> str | None:
        """Ancre GFM de la section, ou ``None`` si inconnue.

        Args:
            path: Chemin structurel.

        Returns:
            L'ancre ou ``None``.
        """
        return self.anchor_by.get(path)


def build_section_index(units: tuple[TextUnit, ...]) -> SectionIndex:
    """Indexe les unités par chemin de section (texte concaténé + titre + ancre).

    Args:
        units: Unités de texte du document consolidé (langue courante).

    Returns:
        L'``SectionIndex`` correspondant (texte des fragments concaténé puis tronqué).
    """
    text_parts: dict[_Path, list[str]] = {}
    title_by: dict[_Path, str] = {}
    anchor_by: dict[_Path, str] = {}
    for unit in units:
        text_parts.setdefault(unit.section_path, []).append(unit.text)
        title_by.setdefault(unit.section_path, unit.title)
        anchor_by.setdefault(unit.section_path, unit.anchor)
    text_by = {
        path: truncate_excerpt(" ".join(parts)) for path, parts in text_parts.items()
    }
    return SectionIndex(text_by=text_by, title_by=title_by, anchor_by=anchor_by)
