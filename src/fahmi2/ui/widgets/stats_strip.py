"""Widget ``StatsStripWidget`` — bandeau d'indicateurs agrégés d'un Run.

Présenté sous forme de 5 cartes côte-à-côte (Statut, Vidéos, Phases, Durée,
Coût). Chaque carte affiche une icône, un titre, une valeur principale en gros
et une sous-information. Un ``QTimer`` interne incrémente l'affichage de la
durée pendant que le Run est ``RUNNING`` ou ``PAUSED`` sans solliciter le
viewmodel (la valeur est calculée à partir du dernier snapshot connu).
"""

from __future__ import annotations

from datetime import UTC, datetime

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QHBoxLayout,
    QWidget,
)

from fahmi2.domain.enums import RunStatus
from fahmi2.ui._format import format_duration, format_languages
from fahmi2.ui.status_labels import cost_accent, run_status_accent, run_status_label
from fahmi2.ui.viewmodels.stats_strip import StatsSnapshot
from fahmi2.ui.widgets.stat_card import StatCard

_LIVE_REFRESH_INTERVAL_MS = 1000
# Tolérance pour considérer deux ``started_at`` identiques (réception de
# deux snapshots successifs du même Run sans décalage suspect).
_SAME_RUN_TIMESTAMP_TOLERANCE_S = 0.1

_RUN_STATUS_ICON: dict[RunStatus, str] = {
    RunStatus.CREATED: "⏳",
    RunStatus.RUNNING: "▶",
    RunStatus.PAUSED: "⏸",
    RunStatus.COMPLETED: "✓",
    RunStatus.FAILED: "✗",
    RunStatus.CANCELLED: "⊘",
}

_LIVE_STATUSES: frozenset[RunStatus] = frozenset({RunStatus.RUNNING})


class StatsStripWidget(QWidget):
    """Bandeau d'indicateurs (Statut, Vidéos, Phases, Durée, Coût)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Construit le widget.

        Args:
            parent: Parent Qt optionnel.
        """
        super().__init__(parent)
        self.setObjectName("statsStrip")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(10)

        self._card_status = StatCard(icon="●", title="Statut", parent=self)
        self._card_videos = StatCard(icon="🎬", title="Vidéos", parent=self)
        self._card_phases = StatCard(icon="▤", title="Phases", parent=self)
        self._card_languages = StatCard(icon="🌐", title="Langues", parent=self)
        self._card_duration = StatCard(icon="⏱", title="Durée", parent=self)
        self._card_cost = StatCard(icon="$", title="Coût", parent=self)

        for card in (
            self._card_status,
            self._card_videos,
            self._card_phases,
            self._card_languages,
            self._card_duration,
            self._card_cost,
        ):
            layout.addWidget(card, stretch=1)

        self._last_snapshot: StatsSnapshot | None = None
        # Tracking local des pauses : l'horodatage d'entrée dans la pause
        # courante (None si pas en pause), et le cumul du temps déjà passé en
        # pause depuis le démarrage de la session UI. On retire ce cumul du
        # temps écoulé absolu pour afficher la durée « active » réelle.
        self._paused_at: datetime | None = None
        self._paused_offset_seconds: float = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(_LIVE_REFRESH_INTERVAL_MS)
        self._timer.timeout.connect(self._on_tick)

    def apply_snapshot(self, snapshot: StatsSnapshot) -> None:
        """Met à jour les cartes avec un nouveau snapshot.

        Args:
            snapshot: Snapshot agrégé du Run courant.
        """
        self._update_pause_tracking(snapshot)
        self._last_snapshot = snapshot
        self._render(snapshot)
        if snapshot.run_status is RunStatus.RUNNING:
            if not self._timer.isActive():
                self._timer.start()
        elif self._timer.isActive():
            self._timer.stop()

    def _update_pause_tracking(self, snapshot: StatsSnapshot) -> None:
        """Met à jour le compteur local de temps en pause à chaque snapshot.

        Logique :

        - Changement de Run (``started_at`` différent à l'epsilon près) →
          reset complet du tracking.
        - Entrée dans ``PAUSED`` (snapshot en pause, ``_paused_at`` absent) →
          mémorise l'horodatage local de pause.
        - Sortie de ``PAUSED`` (snapshot non-pause, ``_paused_at`` présent) →
          cumule la durée de pause dans ``_paused_offset_seconds`` et
          libère ``_paused_at``.

        Args:
            snapshot: Snapshot reçu.
        """
        prev = self._last_snapshot
        if prev is not None:
            delta = abs((snapshot.started_at - prev.started_at).total_seconds())
            if delta > _SAME_RUN_TIMESTAMP_TOLERANCE_S:
                self._paused_at = None
                self._paused_offset_seconds = 0.0

        now = datetime.now(tz=UTC)
        if snapshot.run_status is RunStatus.PAUSED:
            if self._paused_at is None:
                self._paused_at = now
        elif self._paused_at is not None:
            elapsed_paused = (now - self._paused_at).total_seconds()
            self._paused_offset_seconds += max(0.0, elapsed_paused)
            self._paused_at = None

    def _on_tick(self) -> None:
        """Met à jour la carte « Durée » entre deux snapshots (Run actif)."""
        if self._last_snapshot is None:
            return
        snapshot = self._last_snapshot
        elapsed = self._compute_displayed_elapsed(snapshot, datetime.now(tz=UTC))
        self._card_duration.set_value(
            format_duration(elapsed),
            run_status_label(snapshot.run_status),
        )

    def _compute_displayed_elapsed(
        self, snapshot: StatsSnapshot, now: datetime
    ) -> float:
        """Calcule la durée à afficher à l'instant ``now``.

        - ``RUNNING`` : ``(now - started_at) - paused_offset`` (temps actif
          live, croissant).
        - ``PAUSED`` : figé à l'instant d'entrée en pause, en retirant les
          pauses cumulées avant celle-ci.
        - ``COMPLETED`` / ``FAILED`` / ``CANCELLED`` : ``elapsed_seconds``
          du snapshot moins l'offset cumulé (approximé : la précision
          dépend de la durée des transitions vues par le widget).
        - ``CREATED`` : 0.

        Args:
            snapshot: Snapshot.
            now: Horodatage de référence (typiquement ``datetime.now``).

        Returns:
            La durée à afficher (>= 0), en secondes.
        """
        if snapshot.run_status is RunStatus.RUNNING:
            absolute = (now - snapshot.started_at).total_seconds()
            return max(0.0, absolute - self._paused_offset_seconds)
        if snapshot.run_status is RunStatus.PAUSED:
            pause_start = self._paused_at or now
            absolute = (pause_start - snapshot.started_at).total_seconds()
            return max(0.0, absolute - self._paused_offset_seconds)
        if snapshot.run_status is RunStatus.CREATED:
            return 0.0
        # Terminé (COMPLETED, FAILED, CANCELLED) : valeur du snapshot
        # corrigée du temps en pause cumulé pendant la session.
        return max(0.0, snapshot.elapsed_seconds - self._paused_offset_seconds)

    def _render(self, snapshot: StatsSnapshot) -> None:
        """Met à jour les 6 cartes à partir d'un snapshot complet.

        Args:
            snapshot: Snapshot à rendre.
        """
        status_label = run_status_label(snapshot.run_status)
        status_icon = _RUN_STATUS_ICON.get(snapshot.run_status, "●")
        self._card_status.set_value(f"{status_icon} {status_label}")
        self._card_status.set_accent(run_status_accent(snapshot.run_status))

        self._card_videos.set_value(
            f"{snapshot.videos_completed} / {snapshot.videos_total}",
            "vidéos terminées",
        )
        self._card_videos.set_accent("neutral")

        self._card_phases.set_value(
            f"{snapshot.phases_completed} / {snapshot.phases_total}",
            "phases terminées",
        )
        self._card_phases.set_accent("neutral")

        self._card_languages.set_value(format_languages(snapshot.languages))
        self._card_languages.set_accent("neutral")

        duration_seconds = self._compute_displayed_elapsed(
            snapshot, datetime.now(tz=UTC)
        )
        if snapshot.finished_at is not None:
            duration_sub = "terminé"
        elif snapshot.run_status is RunStatus.PAUSED:
            duration_sub = "en pause (figée)"
        else:
            duration_sub = status_label
        self._card_duration.set_value(
            format_duration(duration_seconds), duration_sub
        )
        self._card_duration.set_accent("neutral")

        cost_value = f"${snapshot.cost_usd_so_far:.2f}"
        if snapshot.cost_ceiling_usd is not None:
            cost_sub = f"plafond ${snapshot.cost_ceiling_usd:.2f}"
        else:
            cost_sub = "sans plafond"
        self._card_cost.set_value(cost_value, cost_sub)
        self._card_cost.set_accent(
            cost_accent(snapshot.cost_usd_so_far, snapshot.cost_ceiling_usd)
        )
