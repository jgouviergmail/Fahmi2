"""Dialogue d'estimation de coût partagé (génération + pédagogie).

Rend une décomposition (par phase / par support) + un total à **fourchette**
(±33 %, format ``≈ $X`` + sous-info) + une ligne de plafond (marge ou
avertissement si le haut de fourchette dépasse le budget).

L'API publique reste :py:func:`show_cost_estimate` (modal dialog) ; le corps
HTML est construit par :py:func:`build_estimate_body` (testable).

i18n : ``pyside6-lupdate`` n'extrait pas les chaînes passées à un wrapper
de fonction (ex. ``_tr(source)``). On appelle donc directement
``QCoreApplication.translate("CostEstimateDialog", "source")`` partout
avec le contexte en littéral — le pattern Qt canonique pour les fonctions
libres.
"""

from __future__ import annotations

from typing import Final

from PySide6.QtCore import QCoreApplication, Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from fahmi2.ui._components import card, localize_button_box

_BREAKDOWN_DECIMALS: Final[int] = 4
_TOTAL_DECIMALS: Final[int] = 2
_RANGE_PCT: Final[int] = 33
_GREEN: Final[str] = "#1a7f37"
_RED: Final[str] = "#cf222e"
_MUTED: Final[str] = "#57606a"

_DIALOG_MIN_WIDTH: Final[int] = 560
_DIALOG_COLUMN_MAX_WIDTH: Final[int] = 540
_DIALOG_MARGIN_HORIZONTAL: Final[int] = 22
_DIALOG_MARGIN_TOP: Final[int] = 22
_DIALOG_MARGIN_BOTTOM: Final[int] = 18
_DIALOG_SPACING: Final[int] = 14


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
    total_label = QCoreApplication.translate("CostEstimateDialog", "Total estimé")
    lines.append(f"<b>{total_label} :</b> ≈ ${total_usd:.{_TOTAL_DECIMALS}f}")
    range_text = QCoreApplication.translate(
        "CostEstimateDialog", "fourchette {low} – {high} (±{pct} %)"
    ).format(
        low=f"${low_usd:.{_TOTAL_DECIMALS}f}",
        high=f"${high_usd:.{_TOTAL_DECIMALS}f}",
        pct=_RANGE_PCT,
    )
    lines.append(f"<span style='color:{_MUTED};'>{range_text}</span>")
    if cost_ceiling_usd is not None:
        lines.append(_ceiling_line(total_usd, high_usd, cost_ceiling_usd))
    footnote = QCoreApplication.translate(
        "CostEstimateDialog",
        "<i>Estimation indicative basée sur des heuristiques DeepSeek "
        "(durées, tokens, multiplicateurs par phase et mode thinking). "
        "Fourchette ±33 %.</i>",
    )
    return "<br>".join(lines) + "<br><br>" + footnote


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
    ceiling_label = QCoreApplication.translate("CostEstimateDialog", "Plafond")
    if margin >= 0:
        margin_text = QCoreApplication.translate(
            "CostEstimateDialog", "(marge ${margin:.2f})"
        ).format(margin=margin)
        base = (
            f"<b>{ceiling_label} :</b> ${ceiling:.2f} "
            f"<span style='color:{_GREEN};'>{margin_text}</span>"
        )
    else:
        excess_text = QCoreApplication.translate(
            "CostEstimateDialog", "(dépassement ${excess:.2f})"
        ).format(excess=-margin)
        base = (
            f"<b>{ceiling_label} :</b> ${ceiling:.2f} "
            f"<span style='color:{_RED};'>{excess_text}</span>"
        )
    if high_usd > ceiling:
        warn_text = QCoreApplication.translate(
            "CostEstimateDialog",
            "⚠ le haut de fourchette (${high:.2f}) peut dépasser le plafond.",
        ).format(high=high_usd)
        base += f"<br><span style='color:{_RED};'>{warn_text}</span>"
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
    """Affiche le dialogue d'estimation (``QDialog`` modal avec carte)."""
    body_html = build_estimate_body(
        header_lines=header_lines,
        breakdown=breakdown,
        total_usd=total_usd,
        low_usd=low_usd,
        high_usd=high_usd,
        cost_ceiling_usd=cost_ceiling_usd,
    )

    dialog = QDialog(parent)
    dialog.setWindowTitle(title)
    dialog.setMinimumWidth(_DIALOG_MIN_WIDTH)

    body_label = QLabel(body_html, dialog)
    body_label.setTextFormat(Qt.TextFormat.RichText)
    body_label.setWordWrap(True)
    body_label.setTextInteractionFlags(
        Qt.TextInteractionFlag.TextSelectableByMouse
    )

    card_frame, card_layout = card(
        dialog,
        title=QCoreApplication.translate("CostEstimateDialog", "Estimation du coût"),
        description=QCoreApplication.translate(
            "CostEstimateDialog",
            "Décomposition par étape et total estimé. La fourchette ±33 % reflète "
            "l'incertitude sur la longueur réelle des sorties IA.",
        ),
    )
    card_layout.addWidget(body_label)

    column = QWidget(dialog)
    column.setMaximumWidth(_DIALOG_COLUMN_MAX_WIDTH)
    column_layout = QVBoxLayout(column)
    column_layout.setContentsMargins(0, 0, 0, 0)
    column_layout.setSpacing(_DIALOG_SPACING)
    column_layout.addWidget(card_frame)

    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok, parent=dialog)
    localize_button_box(buttons)
    ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
    if ok_button is not None:
        ok_button.setText(QCoreApplication.translate("CostEstimateDialog", "Compris"))
    buttons.accepted.connect(dialog.accept)

    outer = QVBoxLayout(dialog)
    outer.setContentsMargins(
        _DIALOG_MARGIN_HORIZONTAL,
        _DIALOG_MARGIN_TOP,
        _DIALOG_MARGIN_HORIZONTAL,
        _DIALOG_MARGIN_BOTTOM,
    )
    outer.setSpacing(_DIALOG_SPACING)
    outer.addWidget(column, alignment=Qt.AlignmentFlag.AlignHCenter)
    outer.addStretch(1)
    outer.addWidget(buttons)

    dialog.exec()
