"""Libellés et accents partagés des statuts de Run (dashboards Génération + Pédagogie).

Centralise le mapping ``RunStatus`` → libellé FR et → clé d'accent visuel, ainsi
que la règle d'accent de la tuile « Coût » selon le plafond. Réutilisé par les deux
bandes de stats (``StatsStripWidget`` et ``PedagogyProgressView``) pour garantir une
présentation homogène (DRY) — les clés d'accent sont interprétées par le QSS global
(``#statCardValue[accent="…"]``).
"""

from __future__ import annotations

from fahmi2.domain.enums import RunStatus

#: Libellé FR par statut de Run.
RUN_STATUS_LABEL: dict[RunStatus, str] = {
    RunStatus.CREATED: "Créé",
    RunStatus.RUNNING: "En cours",
    RunStatus.PAUSED: "En pause",
    RunStatus.COMPLETED: "Terminé",
    RunStatus.FAILED: "Échec",
    RunStatus.CANCELLED: "Annulé",
}

#: Clé d'accent visuel par statut de Run (interprétée par le QSS global).
_RUN_STATUS_ACCENT: dict[RunStatus, str] = {
    RunStatus.RUNNING: "running",
    RunStatus.PAUSED: "warning",
    RunStatus.COMPLETED: "success",
    RunStatus.FAILED: "danger",
    RunStatus.CANCELLED: "danger",
}

#: Glyphe Unicode par statut de Run (tuile Statut, icônes de la sidebar).
_RUN_STATUS_ICON: dict[RunStatus, str] = {
    RunStatus.CREATED: "⏳",
    RunStatus.RUNNING: "▶",
    RunStatus.PAUSED: "⏸",
    RunStatus.COMPLETED: "✓",
    RunStatus.FAILED: "✗",
    RunStatus.CANCELLED: "⊘",
}
#: Glyphe de repli si le statut est inconnu.
_DEFAULT_STATUS_ICON = "●"

#: Accent neutre par défaut (statut sans accent ou inconnu).
ACCENT_NEUTRAL = "neutral"

#: Seuil (ratio coût/plafond) à partir duquel la tuile Coût passe en « warning ».
_COST_WARNING_RATIO = 0.8
#: Seuil (ratio coût/plafond) à partir duquel la tuile Coût passe en « danger ».
_COST_DANGER_RATIO = 1.0


def run_status_label(status: RunStatus) -> str:
    """Libellé FR d'un statut de Run.

    Args:
        status: Statut du Run.

    Returns:
        Le libellé FR (la valeur brute du statut en repli).
    """
    return RUN_STATUS_LABEL.get(status, status.value)


def run_status_accent(status: RunStatus) -> str:
    """Clé d'accent visuel d'un statut de Run.

    Args:
        status: Statut du Run.

    Returns:
        ``"running"`` / ``"warning"`` / ``"success"`` / ``"danger"`` ou
        ``"neutral"`` (statut sans accent dédié).
    """
    return _RUN_STATUS_ACCENT.get(status, ACCENT_NEUTRAL)


def run_status_icon(status: RunStatus) -> str:
    """Glyphe Unicode d'un statut de Run (tuile Statut, sidebar).

    Args:
        status: Statut du Run.

    Returns:
        Le glyphe (``●`` en repli).
    """
    return _RUN_STATUS_ICON.get(status, _DEFAULT_STATUS_ICON)


def cost_accent(cost_usd: float, ceiling_usd: float | None) -> str:
    """Clé d'accent de la tuile « Coût » selon le plafond.

    Args:
        cost_usd: Coût cumulé.
        ceiling_usd: Plafond éventuel (``None`` ou ``<= 0`` = pas de plafond).

    Returns:
        ``"danger"`` si le plafond est atteint/dépassé, ``"warning"`` au-delà de
        80 % du plafond, ``"neutral"`` sinon.
    """
    if ceiling_usd is None or ceiling_usd <= 0:
        return ACCENT_NEUTRAL
    ratio = cost_usd / ceiling_usd
    if ratio >= _COST_DANGER_RATIO:
        return "danger"
    if ratio >= _COST_WARNING_RATIO:
        return "warning"
    return ACCENT_NEUTRAL
