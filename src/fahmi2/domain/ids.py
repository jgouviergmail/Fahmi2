"""Wrappers typés pour les identifiants du domaine.

Trois types distincts pour éviter les confusions cross-type au type-check :
``ProjectId``, ``RunId``, ``VideoId``. Tous reposent sur ULID en interne via
:py:mod:`fahmi2.core.ids`.
"""

from __future__ import annotations

from dataclasses import dataclass

from fahmi2.core.ids import new_ulid, parse_ulid


@dataclass(frozen=True)
class ProjectId:
    """Identifiant stable d'un Projet."""

    value: str

    def __post_init__(self) -> None:
        parse_ulid(self.value)

    @classmethod
    def new(cls) -> ProjectId:
        """Génère un nouvel ``ProjectId``."""
        return cls(value=new_ulid())


@dataclass(frozen=True)
class RunId:
    """Identifiant stable d'un Run."""

    value: str

    def __post_init__(self) -> None:
        parse_ulid(self.value)

    @classmethod
    def new(cls) -> RunId:
        """Génère un nouvel ``RunId``."""
        return cls(value=new_ulid())


@dataclass(frozen=True)
class VideoId:
    """Identifiant stable d'une vidéo dans un Project."""

    value: str

    def __post_init__(self) -> None:
        parse_ulid(self.value)

    @classmethod
    def new(cls) -> VideoId:
        """Génère un nouvel ``VideoId``."""
        return cls(value=new_ulid())
