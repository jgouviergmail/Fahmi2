"""Socle partagé des stratégies de consolidation (phase 5).

Regroupe :

- ``ConsolidationResult`` (markdown consolidé + coût cumulé) et l'ABC
  ``ConsolidationStrategy`` que chaque mode implémente.
- Les helpers **déterministes** réutilisés par les modes ``ORDERED`` et
  ``THEMATIC`` : chargement des structurés par source, renumérotation
  hiérarchique (``1``, ``1.1``, ``1.1.1``), construction du sommaire avec ancres
  GitHub-compatibles, assemblage du document final.

Aucun appel LLM ici : ce module ne contient que de la logique pure (hors
``load_all_structured`` qui lit le disque).
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fahmi2.core.errors.exceptions import StorageError
from fahmi2.core.errors.severity import Severity
from fahmi2.core.slugify import slugify_anchor
from fahmi2.domain.source import SourceExecution
from fahmi2.pipeline.phase_handler import PhaseContext

#: Sous-dossier du workspace contenant les Markdown structurés (phase 4).
STRUCTURED_SUBDIR = "structured"
#: Nom de fichier du document consolidé en langue source.
CONSOLIDATED_MASTER_FILENAME = "consolidated_master.md"
#: Libellé de la section résumé exécutif (sous le titre, avant l'intro).
SUMMARY_HEADING = "Résumé"
#: Profondeur maximale incluse dans le sommaire et la numérotation
#: (les ``####``+ restent dans le corps mais ne sont ni numérotés ni listés).
TOC_MAX_DEPTH = 3

_RE_CODE_FENCE = re.compile(r"^\s*```")
_RE_H1 = re.compile(r"^#\s+(.+?)\s*$")
_RE_H2 = re.compile(r"^##\s+(.+?)\s*$")
_RE_H3 = re.compile(r"^###\s+(.+?)\s*$")
# Titres au-delà de la profondeur numérotée (####+) : non renumérotés, mais on
# retire toute numérotation héritée de la source pour éviter un mélange incohérent.
# Groupe 1 = dièses, groupe 2 = titre.
_RE_H4_PLUS = re.compile(r"^(#{4,})\s+(.+?)\s*$")
# Préfixe numérotation déjà présent (ex: "1. ", "1.2 ", "1.2.3 - ", "1) ").
_RE_EXISTING_NUMBERING = re.compile(r"^\d+(?:\.\d+)*[.\-)\s]+")


@dataclass(frozen=True)
class ConsolidationResult:
    """Résultat d'une stratégie de consolidation.

    Attributes:
        consolidated_markdown: Document consolidé final en langue source.
        cost_usd: Coût cumulé de tous les appels LLM de la stratégie.
    """

    consolidated_markdown: str
    cost_usd: float


@dataclass(frozen=True)
class _Subheading:
    """Sous-titre détecté dans le corps d'un chapitre.

    Attributes:
        level: ``2`` pour ``##``, ``3`` pour ``###``.
        number: Numérotation hiérarchique (``"1.2"``, ``"1.2.3"``).
        title: Texte du titre, débarrassé de toute numérotation existante.
    """

    level: int
    number: str
    title: str


@dataclass(frozen=True)
class _Chapter:
    """Chapitre consolidé : titre numéroté + corps renuméroté + sous-titres.

    Attributes:
        index: Numéro du chapitre (1, 2, …).
        title: Titre du chapitre (sans le préfixe ``"N. "``).
        body: Corps Markdown du chapitre, déjà renuméroté.
        subheadings: Liste ordonnée des sous-titres ## et ### du chapitre.
    """

    index: int
    title: str
    body: str
    subheadings: tuple[_Subheading, ...]


class ConsolidationStrategy(ABC):
    """Stratégie d'assemblage du document consolidé (phase 5)."""

    @abstractmethod
    def consolidate(
        self,
        ctx: PhaseContext,
        structured_by_source: dict[str, str],
    ) -> ConsolidationResult:
        """Produit le document consolidé à partir des structurés par source.

        Args:
            ctx: Contexte d'exécution de la phase.
            structured_by_source: Markdown structuré par ``source_id`` (ordre =
                ordre des sources du run).

        Returns:
            ``ConsolidationResult`` (markdown + coût cumulé).
        """


def load_all_structured(
    workspace: Path, sources: tuple[SourceExecution, ...]
) -> dict[str, str]:
    """Charge tous les documents Markdown structurés (phase 4) en ordre.

    Args:
        workspace: Dossier de travail.
        sources: Sources du run (ordre de l'input folder).

    Returns:
        Mapping ``source_id -> structured_markdown`` préservant l'ordre.

    Raises:
        StorageError: Si un fichier structuré manque.
    """
    result: dict[str, str] = {}
    for source in sources:
        path = workspace / STRUCTURED_SUBDIR / f"{source.source_id.value}.md"
        if not path.exists():
            raise StorageError(
                code="STORAGE.STRUCTURED_MISSING",
                user_message=(
                    f"Le document structuré pour {source.source_id.value} est introuvable. "
                    "Relance la phase de structuration."
                ),
                severity=Severity.ERROR,
                technical_details={"path": str(path)},
            )
        result[source.source_id.value] = path.read_text(encoding="utf-8")
    return result


def assemble_document(meta: dict[str, Any], chapters: list[_Chapter]) -> str:
    """Assemble le document consolidé final (méta + sommaire + chapitres).

    Le document final est structuré ainsi :

    1. ``# <titre global>``
    2. ``## Résumé`` (abstract du LLM, non numéroté ; omis si vide)
    3. ``## Introduction générale`` (non numéroté ; omis si vide)
    4. ``## Sommaire`` (liste hiérarchique avec ancres GitHub)
    5. Chapitres : ``# N. <titre>`` + corps déjà renuméroté
    6. ``## Conclusion générale`` (non numéroté ; omis si vide)

    Args:
        meta: Méta-éléments (``global_title``, ``summary_markdown``,
            ``introduction_markdown``, ``conclusion_markdown``).
        chapters: Chapitres déjà numérotés/renumérotés (ordre = ordre final).

    Returns:
        Le document Markdown consolidé complet.
    """
    title = str(meta.get("global_title", "Document consolidé"))
    summary = str(meta.get("summary_markdown", "")).strip()
    introduction = str(meta.get("introduction_markdown", "")).strip()
    conclusion = str(meta.get("conclusion_markdown", "")).strip()

    parts: list[str] = [f"# {title}", ""]
    if summary:
        parts.extend([f"## {SUMMARY_HEADING}", "", summary, ""])
    if introduction:
        parts.extend(["## Introduction générale", "", introduction, ""])
    if chapters:
        parts.append("## Sommaire")
        parts.append("")
        parts.extend(build_toc_lines(chapters))
        parts.append("")
    for chapter in chapters:
        parts.append(f"# {chapter.index}. {chapter.title}")
        parts.append("")
        if chapter.body:
            parts.append(chapter.body)
            parts.append("")
    if conclusion:
        parts.extend(["## Conclusion générale", "", conclusion, ""])
    return "\n".join(parts).rstrip() + "\n"


def build_toc_lines(chapters: list[_Chapter]) -> list[str]:
    """Construit la table des matières (chapitres + sous-titres numérotés).

    Args:
        chapters: Liste des chapitres déjà renumérotés.

    Returns:
        Liste de lignes Markdown (sans saut de ligne final).
    """
    lines: list[str] = []
    for chap in chapters:
        anchor = slugify_anchor(f"{chap.index}. {chap.title}")
        lines.append(f"{chap.index}. [{chap.title}](#{anchor})")
        for sub in chap.subheadings:
            if sub.level > TOC_MAX_DEPTH:
                continue
            sub_anchor = slugify_anchor(f"{sub.number} {sub.title}")
            indent = "    " * (sub.level - 1)
            lines.append(f"{indent}- [{sub.number} {sub.title}](#{sub_anchor})")
    return lines


def renumber_subheadings(
    body: str, chapter_index: int
) -> tuple[str, list[_Subheading]]:
    """Renumérote les ``##`` et ``###`` d'un chapitre selon ``chapter_index``.

    Les numérotations préexistantes en tête de titre sont supprimées avant
    écriture de la nouvelle. Les titres plus profonds (``####``+) ne sont **pas**
    numérotés (cf. ``TOC_MAX_DEPTH``) mais sont eux aussi débarrassés de toute
    numérotation héritée. Les blocs ``fence`` (``\\`\\`\\``) sont laissés intacts.

    Args:
        body: Corps du chapitre (sans son H1, déjà ``demote_chapter_h1``).
        chapter_index: Numéro du chapitre racine (1, 2, …).

    Returns:
        ``(body_renuméroté, sous-titres détectés)``.
    """
    h2_counter = 0
    h3_counter = 0
    in_code_block = False
    subheadings: list[_Subheading] = []
    out_lines: list[str] = []
    for line in body.splitlines():
        if _RE_CODE_FENCE.match(line):
            in_code_block = not in_code_block
            out_lines.append(line)
            continue
        if in_code_block:
            out_lines.append(line)
            continue
        m_h3 = _RE_H3.match(line)
        m_h2 = _RE_H2.match(line) if not m_h3 else None
        m_deep = _RE_H4_PLUS.match(line) if not (m_h2 or m_h3) else None
        if m_h2 is not None:
            h2_counter += 1
            h3_counter = 0
            clean_title = strip_existing_numbering(m_h2.group(1))
            number = f"{chapter_index}.{h2_counter}"
            out_lines.append(f"## {number} {clean_title}")
            subheadings.append(_Subheading(level=2, number=number, title=clean_title))
        elif m_h3 is not None:
            h3_counter += 1
            clean_title = strip_existing_numbering(m_h3.group(1))
            # Si un ### apparaît avant tout ##, on l'accroche au chapitre racine.
            parent = h2_counter if h2_counter > 0 else 0
            if parent == 0:
                h2_counter = 1
                parent = 1
            number = f"{chapter_index}.{parent}.{h3_counter}"
            out_lines.append(f"### {number} {clean_title}")
            subheadings.append(_Subheading(level=3, number=number, title=clean_title))
        elif m_deep is not None:
            # ####+ : non numéroté, mais débarrassé de toute numérotation héritée.
            out_lines.append(
                f"{m_deep.group(1)} {strip_existing_numbering(m_deep.group(2))}"
            )
        else:
            out_lines.append(line)
    return "\n".join(out_lines), subheadings


def subheadings_of(body: str) -> tuple[_Subheading, ...]:
    """Dérive les sous-titres (déjà numérotés) d'un corps de chapitre.

    Source unique pour le sommaire, qu'un chapitre soit fraîchement renuméroté ou
    rechargé depuis le disque (reprise intra-phase). Parse les lignes
    ``## N.M …`` et ``### N.M.P …`` hors blocs ``fence``. La numérotation en tête
    est séparée du titre.

    Args:
        body: Corps Markdown déjà renuméroté.

    Returns:
        Les sous-titres détectés, dans l'ordre d'apparition.
    """
    in_code_block = False
    subheadings: list[_Subheading] = []
    for line in body.splitlines():
        if _RE_CODE_FENCE.match(line):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue
        m_h3 = _RE_H3.match(line)
        m_h2 = _RE_H2.match(line) if not m_h3 else None
        match = m_h3 or m_h2
        if match is None:
            continue
        level = 3 if m_h3 is not None else 2
        number, title = _split_leading_number(match.group(1))
        subheadings.append(_Subheading(level=level, number=number, title=title))
    return tuple(subheadings)


def _split_leading_number(heading: str) -> tuple[str, str]:
    """Sépare la numérotation hiérarchique de tête du reste du titre.

    Args:
        heading: Titre tel que ``"1.2 Alpha"`` (numérotation déjà posée).

    Returns:
        ``(number, title)`` ; ``number`` vide si aucune numérotation n'est présente.
    """
    match = _RE_EXISTING_NUMBERING.match(heading)
    if match is None:
        return "", heading.strip()
    number = re.match(r"\d+(?:\.\d+)*", heading)
    number_str = number.group(0) if number is not None else ""
    return number_str, heading[match.end() :].strip()


def strip_existing_numbering(title: str) -> str:
    """Retire une éventuelle numérotation hiérarchique en tête de titre.

    Exemples : ``"1. Titre"`` → ``"Titre"`` ; ``"1.2 Titre"`` → ``"Titre"`` ;
    ``"1.2.3 - Titre"`` → ``"Titre"``.

    Args:
        title: Titre brut, possiblement déjà numéroté.

    Returns:
        Titre débarrassé de sa numérotation.
    """
    return _RE_EXISTING_NUMBERING.sub("", title.strip()).strip()


def demote_chapter_h1(structured_markdown: str) -> str:
    """Supprime le premier H1 du chapitre.

    Le chapitre reçoit son propre H1 numéroté lors de l'assemblage ; on retire le
    premier titre H1 d'origine pour éviter la duplication visuelle. Les H2/H3
    suivants sont conservés (la renumérotation a lieu après).

    Args:
        structured_markdown: Markdown du chapitre.

    Returns:
        Le Markdown avec le premier H1 supprimé.
    """
    lines = structured_markdown.splitlines()
    skipped_h1 = False
    out: list[str] = []
    for line in lines:
        if not skipped_h1 and _RE_H1.match(line):
            skipped_h1 = True
            continue
        out.append(line)
    return "\n".join(out).strip("\n")
