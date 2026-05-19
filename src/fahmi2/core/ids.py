"""Identifiants stables (ULID) pour les entités du domaine.

Les ULID combinent un timestamp en millisecondes et une partie aléatoire, ce qui
garantit à la fois l'unicité et un ordre chronologique naturel — utile pour le
tri stable des projets/runs/vidéos sans index supplémentaire.
"""

from __future__ import annotations

from datetime import UTC, datetime

from ulid import ULID


def new_ulid() -> str:
    """Génère un nouvel identifiant ULID encodé Crockford base32.

    Returns:
        Chaîne de 26 caractères correspondant à un ULID monotonement croissant.
    """
    return str(ULID())


def parse_ulid(value: str) -> str:
    """Valide qu'une chaîne est un ULID et la retourne normalisée.

    Args:
        value: Chaîne candidate.

    Returns:
        L'ULID validé sous forme de chaîne normalisée.

    Raises:
        ValueError: Si la chaîne n'est pas un ULID valide.
    """
    try:
        return str(ULID.from_str(value))
    except (ValueError, TypeError) as exc:
        raise ValueError(f"Invalid ULID: {value!r}") from exc


def ulid_to_datetime(value: str) -> datetime:
    """Extrait le timestamp encodé dans un ULID.

    Args:
        value: ULID valide (sera validé en interne).

    Returns:
        Datetime UTC correspondant à la portion timestamp du ULID.

    Raises:
        ValueError: Si la chaîne n'est pas un ULID valide.
    """
    ulid_obj = ULID.from_str(parse_ulid(value))
    return datetime.fromtimestamp(ulid_obj.timestamp, tz=UTC)
