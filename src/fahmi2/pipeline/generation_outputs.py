"""Lecture des livrables de la Génération consommés par les fonctionnalités aval.

Helpers **neutres** (chemin du document consolidé, horodatages de fraîcheur, chargement
du glossaire master) partagés par les moteurs **Pédagogie**, **Dialogue** et
**Visualisations** — qui restent indépendants les uns des autres mais lisent tous les
mêmes artefacts produits par le pipeline de génération. Source unique (DRY) : ces
fonctions étaient auparavant dupliquées entre ``pedagogy/sources.py`` et
``visuals/sources.py``.
"""

from __future__ import annotations

import json
from pathlib import Path

from fahmi2.domain.enums import Language
from fahmi2.domain.generation import consolidated_doc_filename
from fahmi2.domain.glossary import Term, parse_glossary_master_terms
from fahmi2.pipeline.workspace_layout import glossary_master_path

_ENCODING_UTF8 = "utf-8"


def consolidated_doc_path(generation_output_dir: Path, language: Language) -> Path:
    """Chemin du document consolidé pour une langue.

    Args:
        generation_output_dir: Dossier des livrables de génération.
        language: Langue.

    Returns:
        Le chemin ``…/consolidated.{lang}.md``.
    """
    return generation_output_dir / consolidated_doc_filename(language)


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

    Sert d'élément de fraîcheur : une régénération du glossaire doit invalider tout
    cache qui en dépend.

    Args:
        generation_dir: Dossier de travail de la génération (contient le master).

    Returns:
        Le ``st_mtime_ns`` du ``glossary_master.json``, ou ``None``.
    """
    path = glossary_master_path(generation_dir)
    if not path.exists():
        return None
    return path.stat().st_mtime_ns


def load_glossary_master_terms(generation_dir: Path) -> tuple[Term, ...]:
    """Charge le glossaire master (langue source) depuis le disque.

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
