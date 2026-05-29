"""Chargement des sources des Visualisations depuis les livrables de la Génération.

Lit le document consolidé (``consolidated.{lang}.md``) et le glossaire master
(``glossary_master.json``) produits par la Génération, et découpe le consolidé en
**unités de texte** (sous-sections, éventuellement fragmentées si trop longues)
soumises à l'extraction sémantique. Compose des primitives **neutres**
(``core/corpus``, ``domain``, ``pipeline/workspace_layout``) sans dépendre des autres
fonctionnalités.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from fahmi2.core.corpus import parse_sections
from fahmi2.domain.enums import Language
from fahmi2.domain.generation import consolidated_doc_filename
from fahmi2.domain.glossary import Term, parse_glossary_master_terms
from fahmi2.domain.visuals import VISUALS_LANGUAGES
from fahmi2.pipeline.workspace_layout import glossary_master_path
from fahmi2.visuals._constants import MAX_UNIT_CHARS, MIN_UNIT_BODY_CHARS

_ENCODING_UTF8 = "utf-8"


@dataclass(frozen=True)
class TextUnit:
    """Unité de texte soumise à l'extraction sémantique (une sous-section ou fragment).

    Attributes:
        section_path: Chemin structurel **invariant par langue** (ex. ``(2, 1, 1)``).
        title: Titre de la section (sans préfixe numérique).
        anchor: Ancre GFM de la section (langue du document lu).
        text: Corps Markdown de l'unité (fragment si la section a été découpée).
        part: Index du fragment (0 si la section n'a pas été découpée, 1, 2… sinon).
    """

    section_path: tuple[int, ...]
    title: str
    anchor: str
    text: str
    part: int


def consolidated_doc_path(generation_output_dir: Path, language: Language) -> Path:
    """Chemin du document consolidé pour une langue.

    Args:
        generation_output_dir: Dossier des livrables de génération.
        language: Langue.

    Returns:
        Le chemin ``…/consolidated.{lang}.md``.
    """
    return generation_output_dir / consolidated_doc_filename(language)


def _chunk_paragraphs(text: str, *, max_chars: int) -> tuple[str, ...]:
    """Découpe un texte en fragments contigus bornés, aux frontières de paragraphe.

    Accumule les paragraphes (séparés par une ligne vide) jusqu'à ``max_chars`` ; un
    paragraphe à lui seul plus long que ``max_chars`` forme son propre fragment (jamais
    coupé en plein milieu d'un mot).

    Args:
        text: Texte à découper.
        max_chars: Longueur cible maximale d'un fragment.

    Returns:
        Les fragments (au moins un si ``text`` n'est pas vide).
    """
    paragraphs = [p for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        candidate = paragraph if not current else f"{current}\n\n{paragraph}"
        if current and len(candidate) > max_chars:
            chunks.append(current)
            current = paragraph
        else:
            current = candidate
    if current:
        chunks.append(current)
    return tuple(chunks)


def load_text_units(
    generation_output_dir: Path, language: Language
) -> tuple[TextUnit, ...]:
    """Charge les unités de texte du consolidé d'une langue.

    Parse le document en sections numérotées (``core/corpus.parse_sections``), écarte
    celles dont le corps est trop court (``MIN_UNIT_BODY_CHARS``) et fragmente celles
    dont le corps dépasse ``MAX_UNIT_CHARS``.

    Args:
        generation_output_dir: Dossier des livrables de génération.
        language: Langue du document à lire.

    Returns:
        Les unités de texte (vide si le document n'existe pas).
    """
    doc = consolidated_doc_path(generation_output_dir, language)
    if not doc.exists():
        return ()
    units: list[TextUnit] = []
    for section in parse_sections(doc.read_text(encoding=_ENCODING_UTF8)):
        body = section.body_markdown.strip()
        if len(body) < MIN_UNIT_BODY_CHARS:
            continue
        fragments = _chunk_paragraphs(body, max_chars=MAX_UNIT_CHARS)
        single = len(fragments) == 1
        for index, fragment in enumerate(fragments):
            units.append(
                TextUnit(
                    section_path=section.section_path,
                    title=section.title,
                    anchor=section.anchor,
                    text=fragment,
                    part=0 if single else index + 1,
                )
            )
    return tuple(units)


def source_mtime_ns(generation_output_dir: Path, language: Language) -> int | None:
    """mtime (ns) du document consolidé d'une langue, ou ``None`` s'il est absent.

    Args:
        generation_output_dir: Dossier des livrables de génération.
        language: Langue.

    Returns:
        Le ``st_mtime_ns`` du ``consolidated.{lang}.md``, ou ``None``.
    """
    doc = consolidated_doc_path(generation_output_dir, language)
    if not doc.exists():
        return None
    return doc.stat().st_mtime_ns


def glossary_master_mtime_ns(generation_dir: Path) -> int | None:
    """mtime (ns) du glossaire master, ou ``None`` s'il est absent.

    Args:
        generation_dir: Dossier de travail de la génération (contient le master).

    Returns:
        Le ``st_mtime_ns`` du ``glossary_master.json``, ou ``None``.
    """
    path = glossary_master_path(generation_dir)
    if not path.exists():
        return None
    return path.stat().st_mtime_ns


def available_visuals_languages(generation_output_dir: Path) -> list[Language]:
    """Langues **latines** dont un document consolidé existe (ordre de l'enum).

    Restreint aux langues supportées par les Visualisations (``VISUALS_LANGUAGES`` :
    zh/ar exclus) et réellement produites par la Génération.

    Args:
        generation_output_dir: Dossier des livrables de génération.

    Returns:
        Liste ordonnée des ``Language`` exploitables (vide si aucune).
    """
    return [
        language
        for language in Language
        if language in VISUALS_LANGUAGES
        and consolidated_doc_path(generation_output_dir, language).exists()
    ]


def load_glossary_master_terms(generation_dir: Path) -> tuple[Term, ...]:
    """Charge les termes du glossaire master (langue source) depuis le disque.

    Lit ``<generation_dir>/glossary_master.json`` (produit par la phase 2) et le parse
    en termes du domaine.

    Args:
        generation_dir: Dossier de travail de la génération (contient le master).

    Returns:
        Les termes (tuple vide si le master n'existe pas).
    """
    path = glossary_master_path(generation_dir)
    if not path.exists():
        return ()
    payload = json.loads(path.read_text(encoding=_ENCODING_UTF8))
    return parse_glossary_master_terms(payload)
