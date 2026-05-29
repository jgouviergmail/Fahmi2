"""Chargement des sources des Visualisations depuis les livrables de la Génération.

Lit le document consolidé (``consolidated.{lang}.md``) et le glossaire master
(``glossary_master.json``) produits par la Génération, et découpe le consolidé en
**unités de texte** (sous-sections, éventuellement fragmentées si trop longues)
soumises à l'extraction sémantique. Compose des primitives **neutres**
(``core/corpus``, ``domain``, ``pipeline/workspace_layout``) sans dépendre des autres
fonctionnalités.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from fahmi2.core.corpus import parse_sections
from fahmi2.domain.enums import Language
from fahmi2.domain.visuals import (
    VISUALS_LANGUAGES,
    VisualsSettings,
    diagrams_filename,
    knowledge_map_filename,
)
from fahmi2.pipeline.generation_outputs import (
    consolidated_doc_path,
    glossary_master_mtime_ns,
    load_glossary_master_terms,
    source_mtime_ns,
)
from fahmi2.visuals._constants import MAX_UNIT_CHARS, MIN_UNIT_BODY_CHARS

#: Helpers de lecture des livrables de génération **partagés** (source unique dans
#: ``pipeline/generation_outputs``), ré-exportés pour compatibilité des appelants.
__all__ = [
    "available_visuals_languages",
    "consolidated_doc_path",
    "glossary_master_mtime_ns",
    "load_glossary_master_terms",
    "load_text_units",
    "outputs_present",
    "source_mtime_ns",
    "structure_language",
]

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


def outputs_present(
    visuals_output_dir: Path, language: Language, settings: VisualsSettings
) -> bool:
    """Indique si les livrables HTML attendus (selon les réglages) existent.

    Args:
        visuals_output_dir: Dossier ``<emplacement>/visuals/output``.
        language: Langue.
        settings: Réglages (quels livrables sont attendus).

    Returns:
        ``True`` si chaque livrable activé est présent sur disque.
    """
    if settings.produce_knowledge_map and not (
        visuals_output_dir / knowledge_map_filename(language)
    ).exists():
        return False
    return not (
        settings.produce_diagrams
        and not (visuals_output_dir / diagrams_filename(language)).exists()
    )


def structure_language(
    source_language: Language | None, available: list[Language]
) -> Language | None:
    """Choisit la langue d'extraction de la structure.

    Préfère la langue source de la génération si elle est disponible, sinon la
    première langue latine disponible (ou ``None`` si aucune).

    Args:
        source_language: Langue source de la génération (``None`` si inconnue).
        available: Langues latines disponibles (ordonnées).

    Returns:
        La langue de structure, ou ``None`` si ``available`` est vide.
    """
    if source_language is not None and source_language in available:
        return source_language
    return available[0] if available else None


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
