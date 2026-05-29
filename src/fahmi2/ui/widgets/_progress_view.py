"""Constantes et helpers partagés des vues de progression (Pédagogie / Visualisations).

Mutualise ce qui était dupliqué mot pour mot entre ``PedagogyProgressView`` et
``VisualsProgressView`` (et la bande de tuiles ``StatsStripWidget``) : intervalle de
rafraîchissement live, décimales de coût, marges/espacement de la bande de tuiles,
application de l'état QSS du bandeau, durée écoulée. Les **libellés traduits** restent
définis dans chaque vue (le contexte Linguist d'un ``self.tr(...)`` est le nom de la
classe : les mutualiser changerait le contexte et casserait les traductions).
"""

from __future__ import annotations

from datetime import datetime
from typing import Final

from PySide6.QtWidgets import QLabel

#: Intervalle (ms) du rafraîchissement « live » de la durée tant qu'un run est en cours.
LIVE_REFRESH_INTERVAL_MS: Final[int] = 1000
#: Nombre de décimales d'affichage des coûts USD dans les tuiles.
COST_DECIMALS: Final[int] = 2
#: Marges horizontale / verticale (px) de la bande de tuiles.
STRIP_MARGIN_H: Final[int] = 12
STRIP_MARGIN_V: Final[int] = 8
#: Espacement (px) entre tuiles de la bande.
STRIP_SPACING: Final[int] = 10


def apply_banner_state(banner: QLabel, state: str) -> None:
    """Applique la propriété QSS dynamique ``state`` au bandeau et force le re-style.

    Args:
        banner: Label du bandeau d'état (fraîcheur).
        state: Valeur de l'état (``""`` pour réinitialiser).
    """
    banner.setProperty("state", state)
    style = banner.style()
    if style is not None:
        style.unpolish(banner)
        style.polish(banner)


def elapsed_seconds(
    started_at: datetime | None, finished_at: datetime | None, now: datetime
) -> float:
    """Durée écoulée d'une exécution (helper partagé des vues de progression).

    Args:
        started_at: Démarrage de l'exécution, ou ``None`` (jamais lancée).
        finished_at: Fin de l'exécution, ou ``None`` (en cours).
        now: Instant de référence (pour une exécution en cours).

    Returns:
        ``finished_at - started_at`` si terminé, ``now - started_at`` si en cours,
        ``0`` si jamais lancé.
    """
    if started_at is None:
        return 0.0
    end = finished_at or now
    return max(0.0, (end - started_at).total_seconds())
