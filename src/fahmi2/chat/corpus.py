"""Chargement et découpage (chunking) du corpus interrogeable du chat.

Le corpus = document consolidé (chunké par section, cf. spec §5.1) + entrées de
glossaire (un chunk par terme). Réutilise ``pedagogy.chapters`` et
``pedagogy.sources``. Toutes les valeurs de découpage sont des constantes.
"""

from __future__ import annotations

import re
from pathlib import Path

from fahmi2.core.slugify import slugify_anchor
from fahmi2.core.text_metrics import estimate_tokens
from fahmi2.domain.chat import CorpusChunk
from fahmi2.domain.enums import Language
from fahmi2.domain.glossary import Term
from fahmi2.pedagogy.chapters import Chapter, parse_chapters
from fahmi2.pedagogy.sources import load_chapters, load_glossary_master_terms

_CHUNK_TARGET_TOKENS = 700
_CHUNK_MIN_TOKENS = 120
_CHUNK_OVERLAP_BLOCKS = 1
_MIN_CHUNKS_TO_MERGE_TAIL = 2  # il faut >= 2 chunks pour fusionner un reliquat court
_ORIGIN_CONSOLIDATED = "consolidated"
_ORIGIN_GLOSSARY = "glossary"
_GLOSSARY_CHAPTER_TITLE = "Glossaire"
_CHUNK_ID_SEPARATOR = "::"  # namespace::clé (consolidé : ancre::ordinal ; glossaire)
_FENCE = "```"
_RE_SUBHEADING = re.compile(r"^#{2,}\s+(.+?)\s*$")


def _match_subheading(line: str) -> str | None:
    """Retourne le titre d'une sous-section (``##``+), ou ``None``.

    Args:
        line: Ligne Markdown.

    Returns:
        Le titre nettoyé, ou ``None`` si la ligne n'est pas un sous-titre.
    """
    match = _RE_SUBHEADING.match(line)
    return match.group(1).strip() if match is not None else None


def _split_blocks(body: str) -> list[tuple[str, str]]:
    """Découpe le corps d'un chapitre en ``(section_title, bloc)``.

    Les titres ``##``/``###`` fixent la section courante (non émis comme bloc). Les
    blocs sont séparés par lignes vides ; un bloc de code ``` reste entier
    (préservation de l'intégrité).

    Args:
        body: Corps Markdown du chapitre.

    Returns:
        Liste ordonnée de ``(section_title, texte_du_bloc)``.
    """
    blocks: list[tuple[str, str]] = []
    current_section = ""
    buffer: list[str] = []
    in_fence = False

    def flush() -> None:
        nonlocal buffer
        text = "\n".join(buffer).strip()
        if text:
            blocks.append((current_section, text))
        buffer = []

    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith(_FENCE):
            in_fence = not in_fence
            buffer.append(line)
            continue
        if not in_fence:
            heading = _match_subheading(line)
            if heading is not None:
                flush()
                current_section = heading
                continue
            if stripped == "":
                flush()
                continue
        buffer.append(line)
    flush()
    return blocks


def _pack_blocks(blocks: list[str]) -> list[str]:
    """Regroupe des blocs en textes ``<= cible`` (+ chevauchement, + fusion finale).

    Args:
        blocks: Blocs d'une même section, dans l'ordre.

    Returns:
        Textes de chunks (un bloc de chevauchement entre voisins ; un reliquat
        trop court est fusionné avec le chunk précédent).
    """
    packed: list[str] = []
    accumulated: list[str] = []
    accumulated_tokens = 0
    for block in blocks:
        block_tokens = estimate_tokens(block)
        if accumulated and accumulated_tokens + block_tokens > _CHUNK_TARGET_TOKENS:
            packed.append("\n\n".join(accumulated))
            accumulated = (
                accumulated[-_CHUNK_OVERLAP_BLOCKS:] if _CHUNK_OVERLAP_BLOCKS else []
            )
            accumulated_tokens = sum(estimate_tokens(b) for b in accumulated)
        accumulated.append(block)
        accumulated_tokens += block_tokens
    if accumulated:
        packed.append("\n\n".join(accumulated))
    if (
        len(packed) >= _MIN_CHUNKS_TO_MERGE_TAIL
        and estimate_tokens(packed[-1]) < _CHUNK_MIN_TOKENS
    ):
        tail = packed.pop()
        packed[-1] = f"{packed[-1]}\n\n{tail}"
    return packed


def _chunk_chapter(chapter: Chapter) -> list[CorpusChunk]:
    """Découpe un chapitre en ``CorpusChunk`` (par section, taille bornée).

    Args:
        chapter: Chapitre parsé du consolidé.

    Returns:
        Chunks du chapitre.
    """
    sections: list[tuple[str, list[str]]] = []
    for section, block in _split_blocks(chapter.body_markdown):
        if sections and sections[-1][0] == section:
            sections[-1][1].append(block)
        else:
            sections.append((section, [block]))

    chunks: list[CorpusChunk] = []
    ordinal = 0
    for section, blocks in sections:
        section_title = section or chapter.title
        anchor = slugify_anchor(section) if section else chapter.anchor
        for text in _pack_blocks(blocks):
            chunks.append(
                CorpusChunk(
                    chunk_id=f"{chapter.anchor}{_CHUNK_ID_SEPARATOR}{ordinal}",
                    chapter_title=chapter.title,
                    section_title=section_title,
                    anchor=anchor,
                    text=text,
                    origin=_ORIGIN_CONSOLIDATED,
                )
            )
            ordinal += 1
    return chunks


def chunk_consolidated(consolidated_markdown: str) -> tuple[CorpusChunk, ...]:
    """Découpe un document consolidé entier en chunks.

    Args:
        consolidated_markdown: Contenu d'un ``consolidated.{lang}.md``.

    Returns:
        Chunks de tous les chapitres (vide si aucun chapitre numéroté).
    """
    chunks: list[CorpusChunk] = []
    for chapter in parse_chapters(consolidated_markdown):
        chunks.extend(_chunk_chapter(chapter))
    return tuple(chunks)


def _glossary_chunks(terms: tuple[Term, ...]) -> list[CorpusChunk]:
    """Convertit les termes du glossaire en chunks (un par terme).

    Args:
        terms: Termes du glossaire master.

    Returns:
        Chunks de glossaire.
    """
    chunks: list[CorpusChunk] = []
    for term in terms:
        header_parts = [term.term]
        if term.acronym:
            header_parts.append(f"({term.acronym})")
        if term.acronym_expansion:
            header_parts.append(f"— {term.acronym_expansion}")
        header = " ".join(header_parts)
        slug = slugify_anchor(term.term)
        chunks.append(
            CorpusChunk(
                chunk_id=f"{_ORIGIN_GLOSSARY}{_CHUNK_ID_SEPARATOR}{slug}",
                chapter_title=_GLOSSARY_CHAPTER_TITLE,
                section_title=term.term,
                anchor=f"{_ORIGIN_GLOSSARY}-{slug}",
                text=f"{header}\n\n{term.definition}".strip(),
                origin=_ORIGIN_GLOSSARY,
            )
        )
    return chunks


def load_corpus_chunks(
    *,
    generation_output_dir: Path,
    generation_dir: Path,
    language: Language,
) -> tuple[CorpusChunk, ...]:
    """Charge et découpe le corpus interrogeable (consolidé + glossaire).

    Args:
        generation_output_dir: Dossier des livrables (``consolidated.{lang}.md``).
        generation_dir: Dossier de travail génération (``glossary_master.json``).
        language: Langue du corpus.

    Returns:
        Tuple de chunks (consolidé puis glossaire ; vide si aucune source).
    """
    chunks: list[CorpusChunk] = []
    for chapter in load_chapters(generation_output_dir, language):
        chunks.extend(_chunk_chapter(chapter))
    chunks.extend(_glossary_chunks(load_glossary_master_terms(generation_dir)))
    return tuple(chunks)
