"""Helpers de formatage partagés pour l'UI (durées, langues).

Mutualisés entre les bandes de stats Génération et Pédagogie pour un affichage
homogène (durée écoulée, liste de langues).
"""

from __future__ import annotations

from fahmi2.domain.enums import Language

_SECONDS_PER_HOUR = 3600
_SECONDS_PER_MINUTE = 60
_LANGUAGE_SEPARATOR = " · "
_EMPTY_PLACEHOLDER = "—"


def format_languages(languages: tuple[Language, ...]) -> str:
    """Formate une liste de langues en libellé court (``FR · EN``).

    Args:
        languages: Langues à afficher.

    Returns:
        Les codes en majuscules joints, ou ``—`` si la liste est vide.
    """
    return (
        _LANGUAGE_SEPARATOR.join(lang.value.upper() for lang in languages)
        or _EMPTY_PLACEHOLDER
    )


def format_duration(seconds: float) -> str:
    """Formate une durée en ``H:MM:SS`` (ou ``MM:SS`` si moins d'une heure).

    Args:
        seconds: Durée en secondes (négative clampée à 0).

    Returns:
        Chaîne compacte adaptée à l'affichage dans une carte.
    """
    total = int(max(0.0, seconds))
    hours, remainder = divmod(total, _SECONDS_PER_HOUR)
    minutes, secs = divmod(remainder, _SECONDS_PER_MINUTE)
    if hours:
        return f"{hours:d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"
