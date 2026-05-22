"""Wrappers typés pour les identifiants du domaine.

Trois types distincts pour éviter les confusions cross-type au type-check :
``ProjectId``, ``RunId``, ``SourceId``. Tous reposent sur ULID en interne via
:py:mod:`fahmi2.core.ids` et partagent leur logique via une base ``_UlidIdBase``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Self

from fahmi2.core.ids import new_ulid, parse_ulid


@dataclass(frozen=True)
class _UlidIdBase:
    """Base partagée pour les identifiants typés ULID.

    Les sous-classes vides ``ProjectId``/``RunId``/``SourceId`` héritent du
    comportement (validation + factory) tout en restant des types distincts au
    sens de mypy (évite ``ProjectId`` interchangeable avec ``RunId``).

    Attributes:
        value: Représentation textuelle ULID (26 caractères).
    """

    value: str

    def __post_init__(self) -> None:
        parse_ulid(self.value)

    @classmethod
    def new(cls) -> Self:
        """Génère un nouvel identifiant du type appelant.

        Returns:
            Une instance fraîche avec un ULID aléatoire.
        """
        return cls(value=new_ulid())


@dataclass(frozen=True)
class ProjectId(_UlidIdBase):
    """Identifiant stable d'un Projet."""


@dataclass(frozen=True)
class RunId(_UlidIdBase):
    """Identifiant stable d'un Run."""


@dataclass(frozen=True)
class SourceId(_UlidIdBase):
    """Identifiant stable d'une source d'entrée dans un Run."""
