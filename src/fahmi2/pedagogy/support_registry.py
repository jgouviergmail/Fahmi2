"""Registre des générateurs de supports indexés par ``SupportType``.

Calqué sur ``pipeline/phase_registry.py`` : enregistre/retrouve un générateur par
type, et expose l'ordre canonique des supports.
"""

from __future__ import annotations

from collections.abc import Iterable

from fahmi2.domain.enums import SupportType
from fahmi2.pedagogy.support_generator import SupportGenerator

_SUPPORT_ORDER: tuple[SupportType, ...] = (
    SupportType.FLASHCARDS_CONCEPTS,
    SupportType.QCM,
    SupportType.TRUE_FALSE,
    SupportType.CLOZE,
    SupportType.OPEN_QUESTIONS,
    SupportType.REVISION_SHEET,
    SupportType.KEY_POINTS,
    SupportType.MOCK_EXAM,
)


class SupportGeneratorRegistry:
    """Enregistre et retrouve les générateurs de supports."""

    def __init__(self, generators: Iterable[SupportGenerator] = ()) -> None:
        """Construit le registre.

        Args:
            generators: Générateurs à enregistrer initialement.

        Raises:
            ValueError: Si deux générateurs déclarent le même ``support_type``.
        """
        self._by_type: dict[SupportType, SupportGenerator] = {}
        for generator in generators:
            self.register(generator)

    def register(self, generator: SupportGenerator) -> None:
        """Enregistre un générateur.

        Args:
            generator: Générateur à enregistrer.

        Raises:
            ValueError: Si ``support_type`` est déjà enregistré.
        """
        if generator.support_type in self._by_type:
            raise ValueError(
                f"Generator already registered for support {generator.support_type}"
            )
        self._by_type[generator.support_type] = generator

    def get(self, support_type: SupportType) -> SupportGenerator:
        """Retourne le générateur d'un type, ou lève ``KeyError``.

        Args:
            support_type: Type de support.

        Returns:
            Le générateur enregistré.

        Raises:
            KeyError: Si aucun générateur n'est enregistré pour ce type.
        """
        try:
            return self._by_type[support_type]
        except KeyError as exc:
            raise KeyError(
                f"No generator registered for support {support_type}"
            ) from exc

    def has(self, support_type: SupportType) -> bool:
        """Indique si un générateur est enregistré pour ce type.

        Args:
            support_type: Type de support.

        Returns:
            ``True`` si présent.
        """
        return support_type in self._by_type

    def ordered_generators(self) -> list[SupportGenerator]:
        """Retourne les générateurs enregistrés dans l'ordre canonique.

        Returns:
            Liste ordonnée des générateurs présents (les types absents sont omis).
        """
        return [self._by_type[st] for st in _SUPPORT_ORDER if st in self._by_type]

    @staticmethod
    def canonical_order() -> tuple[SupportType, ...]:
        """Retourne l'ordre canonique des supports.

        Returns:
            Tuple immuable des ``SupportType``.
        """
        return _SUPPORT_ORDER
