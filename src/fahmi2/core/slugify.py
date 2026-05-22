"""Slug d'ancre GitHub-compatible pour les titres Markdown.

Source **unique de vérité** partagée par la génération (sommaire du document
consolidé), le parseur de chapitres pédagogiques et l'export HTML (ids de titres
de l'extension ``toc``). Les ancres GFM sont en minuscules ; espaces et ``/``
deviennent des tirets ; seuls les caractères de mot (accents Unicode conservés) et
les tirets sont gardés ; les tirets multiples sont réduits et ceux de bord retirés.
"""

from __future__ import annotations

import re

_RE_SPACES_SLASHES = re.compile(r"[\s/]+")
_RE_NON_WORD = re.compile(r"[^\w\-]+", re.UNICODE)
_RE_DASHES = re.compile(r"-+")


def slugify_anchor(text: str) -> str:
    """Convertit un titre Markdown en ancre slug GitHub-compatible.

    Args:
        text: Titre source (ex: ``"1. Bases / Outils"``).

    Returns:
        Le slug (ex: ``"1-bases-outils"``).
    """
    cleaned = text.lower().strip()
    cleaned = _RE_SPACES_SLASHES.sub("-", cleaned)
    cleaned = _RE_NON_WORD.sub("", cleaned)
    cleaned = _RE_DASHES.sub("-", cleaned)
    return cleaned.strip("-")
