"""Widget ``PedagogyProgressView`` — bandeau de fraîcheur + tuiles + matrice.

Aligné sur le dashboard Génération : un **bandeau d'état** (fraîcheur, via la
propriété QSS ``state``), une **bande de tuiles** (Statut / Supports / Langues /
Durée / Coût) et une **matrice de coût** supports × langues (``CostMatrixView``).
Un ``QTimer`` rafraîchit la durée tant que la génération est ``RUNNING``.
"""

from __future__ import annotations

from datetime import UTC, datetime

from PySide6.QtCore import QCoreApplication, QTimer
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from fahmi2.domain.enums import RunStatus
from fahmi2.ui._format import format_duration, format_languages
from fahmi2.ui.status_labels import (
    ACCENT_NEUTRAL,
    cost_accent,
    run_status_accent,
    run_status_label,
)
from fahmi2.ui.viewmodels.cost_matrix import CostMatrixSnapshot
from fahmi2.ui.viewmodels.pedagogy_progress import PedagogyStatsSnapshot
from fahmi2.ui.viewmodels.pedagogy_state import PedagogyStateInfo
from fahmi2.ui.widgets._progress_view import (
    COST_DECIMALS,
    LIVE_REFRESH_INTERVAL_MS,
    STRIP_MARGIN_H,
    STRIP_MARGIN_V,
    STRIP_SPACING,
    apply_banner_state,
    elapsed_seconds,
)
from fahmi2.ui.widgets.cost_matrix_view import CostMatrixView
from fahmi2.ui.widgets.stat_card import StatCard

_BANNER_OBJECT_NAME = "pedagogyStateBanner"


def empty_matrix() -> CostMatrixSnapshot:
    """Retourne un ``CostMatrixSnapshot`` vide avec en-tête traduit."""
    return CostMatrixSnapshot(
        row_header=QCoreApplication.translate("PedagogyProgress", "Support"),
        column_labels=(),
        row_labels=(),
        cells=(),
        row_totals=(),
        column_totals=(),
        grand_total=0.0,
    )


class PedagogyProgressView(QWidget):
    """Bandeau d'état + tuiles + matrice supports × langues."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Construit la vue.

        Args:
            parent: Parent Qt optionnel.
        """
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._banner = QLabel("", self)
        self._banner.setObjectName(_BANNER_OBJECT_NAME)
        self._banner.setWordWrap(True)

        strip = QWidget(self)
        strip.setObjectName("statsStrip")
        strip_layout = QHBoxLayout(strip)
        strip_layout.setContentsMargins(
            STRIP_MARGIN_H, STRIP_MARGIN_V, STRIP_MARGIN_H, STRIP_MARGIN_V
        )
        strip_layout.setSpacing(STRIP_SPACING)
        self._card_status = StatCard(icon="●", title=self.tr("Statut"), parent=strip)
        self._card_supports = StatCard(
            icon="▤", title=self.tr("Supports"), parent=strip
        )
        self._card_languages = StatCard(
            icon="🌐", title=self.tr("Langues"), parent=strip
        )
        self._card_duration = StatCard(
            icon="⏱", title=self.tr("Durée"), parent=strip
        )
        self._card_cost = StatCard(icon="$", title=self.tr("Coût"), parent=strip)
        for card in (
            self._card_status,
            self._card_supports,
            self._card_languages,
            self._card_duration,
            self._card_cost,
        ):
            strip_layout.addWidget(card, stretch=1)

        self._matrix = CostMatrixView(parent=self)
        self._row_count = 0
        self._last_stats: PedagogyStatsSnapshot | None = None
        self._timer = QTimer(self)
        self._timer.setInterval(LIVE_REFRESH_INTERVAL_MS)
        self._timer.timeout.connect(self._on_tick)

        layout.addWidget(self._banner)
        layout.addWidget(strip)
        layout.addWidget(self._matrix, stretch=1)

    def apply_snapshot(
        self, matrix: CostMatrixSnapshot, stats: PedagogyStatsSnapshot
    ) -> None:
        """Met à jour la matrice et les tuiles.

        Args:
            matrix: Grille supports × langues.
            stats: Indicateurs agrégés.
        """
        self._matrix.apply_snapshot(matrix)
        self._row_count = len(matrix.row_labels)
        self._last_stats = stats
        self._render_stats(stats)
        if stats.overall_status is RunStatus.RUNNING:
            if not self._timer.isActive():
                self._timer.start()
        elif self._timer.isActive():
            self._timer.stop()

    def _render_stats(self, stats: PedagogyStatsSnapshot) -> None:
        """Met à jour les 5 tuiles (statut, supports, langues, durée, coût).

        Args:
            stats: Indicateurs agrégés.
        """
        if stats.overall_status is not None:
            self._card_status.set_value(run_status_label(stats.overall_status))
            self._card_status.set_accent(run_status_accent(stats.overall_status))
        else:
            self._card_status.set_value("—")
            self._card_status.set_accent(ACCENT_NEUTRAL)
        self._card_supports.set_value(
            f"{stats.tasks_done} / {stats.tasks_total}", self.tr("tâches")
        )
        self._card_languages.set_value(format_languages(stats.languages))
        self._card_duration.set_value(
            format_duration(
                elapsed_seconds(stats.started_at, stats.finished_at, datetime.now(tz=UTC))
            )
        )
        if stats.cost_ceiling_usd is not None:
            cost_sub = self.tr("plafond ${ceiling:.2f}").format(
                ceiling=stats.cost_ceiling_usd
            )
        else:
            cost_sub = self.tr("sans plafond")
        self._card_cost.set_value(
            f"${stats.total_cost_usd:.{COST_DECIMALS}f}", cost_sub
        )
        self._card_cost.set_accent(
            cost_accent(stats.total_cost_usd, stats.cost_ceiling_usd)
        )

    def _on_tick(self) -> None:
        """Rafraîchit la durée affichée entre deux snapshots (génération active)."""
        if self._last_stats is None:
            return
        self._card_duration.set_value(
            format_duration(
                elapsed_seconds(
                    self._last_stats.started_at,
                    self._last_stats.finished_at,
                    datetime.now(tz=UTC),
                )
            )
        )

    def set_state(self, info: PedagogyStateInfo) -> None:
        """Met à jour le bandeau d'état.

        Args:
            info: État + message.
        """
        self._banner.setText(info.message)
        self._banner.setVisible(bool(info.message))
        apply_banner_state(self._banner, info.state.value)

    def clear(self) -> None:
        """Réinitialise (aucun projet sélectionné)."""
        if self._timer.isActive():
            self._timer.stop()
        self._last_stats = None
        self._matrix.apply_snapshot(empty_matrix())
        self._row_count = 0
        self._banner.setText("")
        self._banner.setVisible(False)
        apply_banner_state(self._banner, "")
        for card in (
            self._card_status,
            self._card_supports,
            self._card_languages,
            self._card_duration,
            self._card_cost,
        ):
            card.set_value("—")
            card.set_accent(ACCENT_NEUTRAL)

    def row_count(self) -> int:
        """Nombre de lignes (supports) affichées dans la matrice.

        Returns:
            Le nombre de supports de la dernière matrice appliquée.
        """
        return self._row_count

    def banner_text(self) -> str:
        """Texte courant du bandeau.

        Returns:
            Le texte du bandeau.
        """
        return self._banner.text()
