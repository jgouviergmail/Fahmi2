"""Source unique de vérité des libellés humains de ``Language``.

Sépare le **fond** (libellé minuscule injecté dans les prompts LLM) de la
**présentation** (libellé capitalisé affiché dans l'UI). Aucune dépendance Qt,
HTTP ni SQL — module de domaine pur. Les modules ``pipeline.handlers._base`` et
``pedagogy.labels`` ré-exportent ``language_label`` (compat d'API historique).
"""

from __future__ import annotations

from fahmi2.domain.enums import Language

#: Nom humain (minuscule) par langue — source unique de vérité partagée par les
#: prompts (forme minuscule) et l'UI (forme capitalisée dérivée).
_LANGUAGE_NAMES: dict[Language, str] = {
    Language.FR: "français",
    Language.EN: "anglais",
    Language.DE: "allemand",
    Language.ES: "espagnol",
    Language.IT: "italien",
    Language.ZH: "chinois",
    Language.AR: "arabe",
}


def language_label(language: Language) -> str:
    """Libellé minuscule d'une langue, pour injection dans les prompts.

    Args:
        language: Langue.

    Returns:
        Le libellé (ex: ``"français"``).
    """
    return _LANGUAGE_NAMES[language]


def language_display_label(language: Language) -> str:
    """Libellé capitalisé d'une langue, pour affichage UI.

    Args:
        language: Langue.

    Returns:
        Le libellé capitalisé (ex: ``"Français"``).
    """
    return _LANGUAGE_NAMES[language].capitalize()
