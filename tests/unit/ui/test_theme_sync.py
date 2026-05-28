"""Garde-fou : les QSS clair et sombre exposent **exactement** les mêmes sélecteurs.

Empêche la dérive de structure entre ``light_fluent.qss`` et ``dark_fluent.qss``
au fil des évolutions : tout sélecteur stylé d'un côté seulement fait échouer la
CI (oubli de mirroring), ce qui garantit qu'un changement de thème ne laissera
jamais un widget non stylé (fond gris résiduel, texte illisible…).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Final

#: Regex de nettoyage des commentaires QSS (`/* ... */`), non greedy multiligne.
_COMMENT_RE: Final[re.Pattern[str]] = re.compile(r"/\*.*?\*/", re.DOTALL)
#: Regex extrayant les groupes de sélecteurs précédant chaque accolade ouvrante.
_SELECTOR_BLOCK_RE: Final[re.Pattern[str]] = re.compile(r"([^{}]+)\{")

_QSS_DIR: Final[Path] = Path(__file__).resolve().parents[3] / "src" / "fahmi2" / "ui" / "theme"
_LIGHT_QSS: Final[Path] = _QSS_DIR / "light_fluent.qss"
_DARK_QSS: Final[Path] = _QSS_DIR / "dark_fluent.qss"


def _normalize_selector(raw: str) -> str:
    """Normalise un sélecteur QSS pour la comparaison ensembliste.

    Args:
        raw: Sélecteur brut extrait du QSS (peut contenir des sauts de ligne
            et espaces multiples).

    Returns:
        Le sélecteur sur une ligne, espaces internes condensés, trim.
    """
    return re.sub(r"\s+", " ", raw).strip()


def extract_selectors(qss_path: Path) -> frozenset[str]:
    """Extrait l'ensemble des sélecteurs d'un fichier QSS.

    Les commentaires sont retirés en amont, les sélecteurs sont normalisés
    (espaces) puis splittés par ``,`` (un sélecteur composé déclare en
    réalité plusieurs sélecteurs simples).

    Args:
        qss_path: Chemin du fichier QSS.

    Returns:
        L'ensemble (frozen) des sélecteurs normalisés.
    """
    source = qss_path.read_text(encoding="utf-8")
    cleaned = _COMMENT_RE.sub("", source)
    selectors: set[str] = set()
    for block_match in _SELECTOR_BLOCK_RE.finditer(cleaned):
        for part in block_match.group(1).split(","):
            normalized = _normalize_selector(part)
            if normalized:
                selectors.add(normalized)
    return frozenset(selectors)


def test_light_and_dark_qss_have_identical_selector_sets() -> None:
    """Les deux feuilles QSS doivent styler exactement les mêmes sélecteurs.

    Toute différence (sélecteur présent dans une seule feuille) fait échouer
    le test avec un diff lisible des deux côtés.
    """
    light = extract_selectors(_LIGHT_QSS)
    dark = extract_selectors(_DARK_QSS)
    only_light = light - dark
    only_dark = dark - light
    assert not only_light and not only_dark, (
        f"Sélecteurs présents uniquement dans light_fluent.qss : {sorted(only_light)}\n"
        f"Sélecteurs présents uniquement dans dark_fluent.qss : {sorted(only_dark)}"
    )


def test_both_qss_define_minimal_required_selectors() -> None:
    """Sanity check : les sélecteurs critiques sont bien présents des deux côtés.

    On dérive le jeu attendu directement des **constantes Python** réservées
    aux briques UI (cf. ``ui/_components.py``) plus quelques sélecteurs
    « historiques » utilisés par les widgets existants. S'ils disparaissent
    par accident d'un côté ou de l'autre, ce test attrape l'oubli.
    """
    from fahmi2.ui._components import (  # noqa: PLC0415 — importé localement pour rester insensible aux ordres d'import
        CARD_DESC_OBJECT_NAME,
        CARD_OBJECT_NAME,
        CARD_TITLE_OBJECT_NAME,
        FIELD_HINT_OBJECT_NAME,
        HSEP_OBJECT_NAME,
        PAGE_DESC_OBJECT_NAME,
        PAGE_TITLE_OBJECT_NAME,
        SECTION_LABEL_OBJECT_NAME,
    )

    component_object_names = (
        CARD_OBJECT_NAME,
        CARD_TITLE_OBJECT_NAME,
        CARD_DESC_OBJECT_NAME,
        PAGE_TITLE_OBJECT_NAME,
        PAGE_DESC_OBJECT_NAME,
        FIELD_HINT_OBJECT_NAME,
        SECTION_LABEL_OBJECT_NAME,
        HSEP_OBJECT_NAME,
    )
    legacy_object_names = (
        "statCard",
        "projectHeaderBar",
        "costMatrix",
        "logsDockArea",
        "settingsCategoryList",
        "pedagogyStateBanner",
    )
    expected = {f"#{name}" for name in (*component_object_names, *legacy_object_names)}
    light = extract_selectors(_LIGHT_QSS)
    dark = extract_selectors(_DARK_QSS)
    missing_light = expected - light
    missing_dark = expected - dark
    assert not missing_light, f"Manquants dans light_fluent.qss : {missing_light}"
    assert not missing_dark, f"Manquants dans dark_fluent.qss : {missing_dark}"
