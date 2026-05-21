"""Dialogue d'estimation de coût partagé (génération + pédagogie).

Rend une décomposition (par phase / par support) + un total à **fourchette**
(±33 %, format ``≈ $X`` + sous-info) + une ligne de plafond (marge ou avertissement
si le haut de fourchette dépasse le budget). Présentation unifiée des deux dialogues.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox, QWidget

_BREAKDOWN_DECIMALS = 4
_TOTAL_DECIMALS = 2
_RANGE_PCT = 33
_FOOTNOTE = (
    "<i>Estimation indicative basée sur des heuristiques DeepSeek (durées, "
    "tokens, multiplicateurs par phase et mode thinking). Fourchette ±33 %.</i>"
)
_GREEN = "#1a7f37"
_RED = "#cf222e"
_MUTED = "#57606a"


def build_estimate_body(
    *,
    header_lines: list[str],
    breakdown: list[tuple[str, float]],
    total_usd: float,
    low_usd: float,
    high_usd: float,
    cost_ceiling_usd: float | None,
) -> str:
    """Construit le corps HTML du dialogue d'estimation.

    Args:
        header_lines: Lignes d'en-tête (déjà formatées HTML).
        breakdown: Décomposition ``(libellé, coût ponctuel)``.
        total_usd: Total estimé (ponctuel).
        low_usd: Bas de fourchette.
        high_usd: Haut de fourchette.
        cost_ceiling_usd: Plafond éventuel.

    Returns:
        Corps HTML (lignes jointes par ``<br>``).
    """
    lines: list[str] = list(header_lines)
    if header_lines:
        lines.append("")
    lines.extend(
        f"<b>{label} :</b> ${cost:.{_BREAKDOWN_DECIMALS}f}"
        for label, cost in breakdown
    )
    lines.append("")
    lines.append(f"<b>Total estimé :</b> ≈ ${total_usd:.{_TOTAL_DECIMALS}f}")
    lines.append(
        f"<span style='color:{_MUTED};'>fourchette "
        f"${low_usd:.{_TOTAL_DECIMALS}f} – ${high_usd:.{_TOTAL_DECIMALS}f} "
        f"(±{_RANGE_PCT} %)</span>"
    )
    if cost_ceiling_usd is not None:
        lines.append(_ceiling_line(total_usd, high_usd, cost_ceiling_usd))
    return "<br>".join(lines) + "<br><br>" + _FOOTNOTE


def _ceiling_line(total_usd: float, high_usd: float, ceiling: float) -> str:
    """Ligne de plafond : marge sur le point estimé + avertissement fourchette.

    Args:
        total_usd: Total ponctuel.
        high_usd: Haut de fourchette.
        ceiling: Plafond.

    Returns:
        Ligne HTML.
    """
    margin = ceiling - total_usd
    if margin >= 0:
        base = (
            f"<b>Plafond :</b> ${ceiling:.2f} "
            f"<span style='color:{_GREEN};'>(marge ${margin:.2f})</span>"
        )
    else:
        base = (
            f"<b>Plafond :</b> ${ceiling:.2f} "
            f"<span style='color:{_RED};'>(dépassement ${-margin:.2f})</span>"
        )
    if high_usd > ceiling:
        base += (
            f"<br><span style='color:{_RED};'>⚠ le haut de fourchette "
            f"(${high_usd:.2f}) peut dépasser le plafond.</span>"
        )
    return base


def show_cost_estimate(
    parent: QWidget,
    *,
    title: str,
    header_lines: list[str],
    breakdown: list[tuple[str, float]],
    total_usd: float,
    low_usd: float,
    high_usd: float,
    cost_ceiling_usd: float | None,
) -> None:
    """Affiche le dialogue d'estimation (``QMessageBox`` RichText).

    Args:
        parent: Fenêtre parente.
        title: Titre de la fenêtre.
        header_lines: Lignes d'en-tête HTML.
        breakdown: Décomposition ``(libellé, coût)``.
        total_usd: Total ponctuel.
        low_usd: Bas de fourchette.
        high_usd: Haut de fourchette.
        cost_ceiling_usd: Plafond éventuel.
    """
    msg = QMessageBox(parent)
    msg.setWindowTitle(title)
    msg.setIcon(QMessageBox.Icon.Information)
    msg.setTextFormat(Qt.TextFormat.RichText)
    msg.setText(
        build_estimate_body(
            header_lines=header_lines,
            breakdown=breakdown,
            total_usd=total_usd,
            low_usd=low_usd,
            high_usd=high_usd,
            cost_ceiling_usd=cost_ceiling_usd,
        )
    )
    msg.exec()
