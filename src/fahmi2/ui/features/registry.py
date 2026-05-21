"""``FeatureRegistry`` — enregistre les onglets de fonctionnalité dans l'ordre.

Calqué sur ``pipeline.phase_registry.PhaseRegistry`` : rejette deux enregistrements
pour le même ``FeatureId`` et restitue les onglets dans l'ordre d'enregistrement.
"""

from __future__ import annotations

from collections.abc import Iterable

from fahmi2.ui.features.feature import FeatureId, FeatureTab


class FeatureRegistry:
    """Enregistre et restitue les ``FeatureTab`` dans l'ordre d'enregistrement."""

    def __init__(self, tabs: Iterable[FeatureTab] = ()) -> None:
        """Construit le registre.

        Args:
            tabs: Onglets à enregistrer initialement.

        Raises:
            ValueError: Si deux onglets déclarent le même ``feature_id``.
        """
        self._by_id: dict[FeatureId, FeatureTab] = {}
        self._order: list[FeatureId] = []
        for tab in tabs:
            self.register(tab)

    def register(self, tab: FeatureTab) -> None:
        """Enregistre un onglet.

        Args:
            tab: Onglet à enregistrer.

        Raises:
            ValueError: Si ``feature_id`` est déjà enregistré.
        """
        if tab.feature_id in self._by_id:
            raise ValueError(f"FeatureTab already registered for {tab.feature_id}")
        self._by_id[tab.feature_id] = tab
        self._order.append(tab.feature_id)

    def ordered(self) -> list[FeatureTab]:
        """Retourne les onglets dans l'ordre d'enregistrement.

        Returns:
            Liste ordonnée des onglets.
        """
        return [self._by_id[fid] for fid in self._order]
