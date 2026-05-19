"""Niveaux de sévérité utilisés par la hiérarchie d'exceptions et les logs."""

from __future__ import annotations

from enum import IntEnum


class Severity(IntEnum):
    """Niveau de sévérité d'une erreur ou d'un événement de log.

    L'ordre est significatif : INFO < WARNING < ERROR < FATAL. Les sinks de log
    et les filtres comparent directement les valeurs entières.
    """

    INFO = 10
    WARNING = 20
    ERROR = 30
    FATAL = 40

    def __str__(self) -> str:
        return self.name.lower()

    @classmethod
    def _missing_(cls, value: object) -> Severity | None:
        """Accepte une chaîne (case-insensitive) en plus des valeurs entières.

        Args:
            value: Valeur candidate (généralement str ou int).

        Returns:
            La valeur de l'énumération correspondante, ou ``None`` si introuvable
            (laisse `IntEnum` lever ``ValueError`` standard).
        """
        if isinstance(value, str):
            for member in cls:
                if member.name.lower() == value.lower():
                    return member
        return None
