"""Widget ``StatsStripWidget`` — barre de stats agrégées d'un Run."""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from fahmi2.ui.viewmodels.stats_strip import StatsSnapshot


class StatsStripWidget(QWidget):
    """Affiche une bande de statistiques en haut de la vue Run."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Construit le widget.

        Args:
            parent: Parent Qt optionnel.
        """
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        self._status_label = QLabel("Run : -", self)
        self._videos_label = QLabel("0 / 0 vidéos", self)
        self._phases_label = QLabel("0 / 0 phases", self)
        self._cost_label = QLabel("$0.00", self)
        for label in (
            self._status_label,
            self._videos_label,
            self._phases_label,
            self._cost_label,
        ):
            layout.addWidget(label)
        layout.addStretch(1)

    def apply_snapshot(self, snapshot: StatsSnapshot) -> None:
        """Met à jour les labels avec un nouveau snapshot.

        Args:
            snapshot: Snapshot agrégé.
        """
        self._status_label.setText(f"Run : {snapshot.run_status.value}")
        self._videos_label.setText(
            f"{snapshot.videos_completed} / {snapshot.videos_total} vidéos"
        )
        self._phases_label.setText(
            f"{snapshot.phases_completed} / {snapshot.phases_total} phases"
        )
        cost_text = f"${snapshot.cost_usd_so_far:.2f}"
        if snapshot.cost_ceiling_usd is not None:
            cost_text += f" / ${snapshot.cost_ceiling_usd:.2f}"
        self._cost_label.setText(cost_text)
