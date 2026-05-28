"""Widget ``ProjectHeaderBar`` — barre d'actions du Run (boutons principaux).

i18n : tous les libellés et tooltips passent par :py:meth:`QObject.tr` à
l'instanciation. Les défauts de tooltips acceptent ``None`` : la valeur
traduite par défaut est calculée dans ``__init__`` (impossible à
l'évaluation de la signature de la classe).
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QWidget

from fahmi2.ui._buttons import make_role_button


class ProjectHeaderBar(QWidget):
    """Barre d'actions principales d'un Run."""

    start_requested = Signal()
    pause_requested = Signal()
    resume_requested = Signal()
    cancel_requested = Signal()
    open_output_requested = Signal()
    estimate_cost_requested = Signal()
    settings_requested = Signal()
    export_requested = Signal()
    reset_requested = Signal()

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        settings_tooltip: str | None = None,
        estimate_tooltip: str | None = None,
        open_output_tooltip: str | None = None,
        show_export: bool = False,
        export_tooltip: str = "",
        reset_tooltip: str | None = None,
    ) -> None:
        """Construit la barre.

        Args:
            parent: Parent Qt optionnel.
            settings_tooltip: Infobulle du bouton « Réglages » (contexte de
                la fonctionnalité). ``None`` = défaut traduit.
            estimate_tooltip: Infobulle du bouton « Estimer le coût ».
                ``None`` = défaut traduit.
            open_output_tooltip: Infobulle du bouton « Dossier de sortie ».
                ``None`` = défaut traduit.
            show_export: Affiche le bouton « Exporter » (masqué par défaut).
            export_tooltip: Infobulle du bouton « Exporter ».
            reset_tooltip: Infobulle du bouton « Réinitialiser ».
                ``None`` = défaut traduit.
        """
        super().__init__(parent)
        self.setObjectName("projectHeaderBar")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(8)

        # Défauts traduits : les calculer ici (et non comme constantes de
        # module) garantit qu'ils suivent la langue active au moment de la
        # construction du widget — pas celle au moment du chargement du
        # module Python.
        if settings_tooltip is None:
            settings_tooltip = self.tr(
                "Configurer les réglages de génération (entrée, langues, style, "
                "transcription, modèle, phases)."
            )
        if estimate_tooltip is None:
            estimate_tooltip = self.tr(
                "Estime à l'avance le coût total du Run en analysant la durée "
                "des sources du dossier d'entrée (STT + LLM)."
            )
        if open_output_tooltip is None:
            open_output_tooltip = self.tr(
                "Ouvre dans l'explorateur le dossier contenant les fichiers Markdown "
                "produits (consolidated, glossary, per-video par langue)."
            )
        if reset_tooltip is None:
            reset_tooltip = self.tr(
                "Supprime tout ce qui a été généré pour cette fonctionnalité (livrables sur "
                "disque et état en base). Action irréversible."
            )

        self._settings_button = self._make_button(self.tr("⚙️  Réglages"), role="default")
        self._settings_button.setToolTip(settings_tooltip)
        self._estimate_cost_button = self._make_button(
            self.tr("💵  Estimer le coût"), role="default"
        )
        self._estimate_cost_button.setToolTip(estimate_tooltip)
        # Hiérarchie : un seul bouton « plein » (Lancer) attire l'œil ; les actions
        # négatives (Annuler / Réinitialiser) sont en rouge discret ; tout le reste
        # en contour neutre. Reprendre, Pause… restent neutres (un seul accent).
        # Icônes : emojis colorés homogènes (le sélecteur U+FE0F force le rendu
        # couleur des glyphes média ▶️/⏸️ sous Segoe UI Emoji).
        self._start_button = self._make_button(self.tr("🚀  Lancer"), role="primary")
        self._pause_button = self._make_button(self.tr("⏸️  Pause"), role="default")
        self._resume_button = self._make_button(self.tr("▶️  Reprendre"), role="default")
        self._cancel_button = self._make_button(self.tr("❌  Annuler"), role="danger")
        self._open_output_button = self._make_button(
            self.tr("📂  Dossier de sortie"), role="default"
        )
        self._open_output_button.setToolTip(open_output_tooltip)
        self._export_button = self._make_button(self.tr("📦  Exporter"), role="default")
        self._export_button.setToolTip(export_tooltip)
        self._export_button.setVisible(show_export)
        self._reset_button = self._make_button(self.tr("🗑️  Réinitialiser"), role="danger")
        self._reset_button.setToolTip(reset_tooltip)

        self._settings_button.clicked.connect(self.settings_requested)
        self._estimate_cost_button.clicked.connect(self.estimate_cost_requested)
        self._start_button.clicked.connect(self.start_requested)
        self._pause_button.clicked.connect(self.pause_requested)
        self._resume_button.clicked.connect(self.resume_requested)
        self._cancel_button.clicked.connect(self.cancel_requested)
        self._open_output_button.clicked.connect(self.open_output_requested)
        self._export_button.clicked.connect(self.export_requested)
        self._reset_button.clicked.connect(self.reset_requested)

        # Groupe gauche : préparation + contrôles d'exécution.
        for btn in (
            self._settings_button,
            self._estimate_cost_button,
            self._start_button,
            self._pause_button,
            self._resume_button,
            self._cancel_button,
        ):
            layout.addWidget(btn)
        layout.addStretch(1)
        # Groupe droite : actions sur les résultats + réinitialisation (destructive),
        # isolées des contrôles principaux.
        for btn in (
            self._open_output_button,
            self._export_button,
            self._reset_button,
        ):
            layout.addWidget(btn)
        self.set_idle()

    def _make_button(self, text: str, *, role: str) -> QPushButton:
        """Crée un ``QPushButton`` avec une propriété ``role`` pour le QSS.

        Args:
            text: Libellé du bouton.
            role: ``primary``, ``default`` ou ``danger``. Utilisé par la
                feuille de style globale pour différencier visuellement les
                actions.

        Returns:
            Le bouton instancié, sans connexion (à brancher par l'appelant).
        """
        return make_role_button(self, text, role=role)

    def set_open_output_enabled(self, enabled: bool) -> None:
        """Active ou désactive le bouton « Dossier de sortie ».

        Args:
            enabled: ``True`` si un dossier de sortie est disponible (typiquement
                quand un run a déjà été lancé pour ce projet).
        """
        self._open_output_button.setEnabled(enabled)

    def set_idle(self) -> None:
        """Affichage état idle (avant démarrage)."""
        self._start_button.setEnabled(True)
        self._pause_button.setEnabled(False)
        self._resume_button.setEnabled(False)
        self._cancel_button.setEnabled(False)
        self._reset_button.setEnabled(True)

    def set_running(self) -> None:
        """Affichage état running."""
        self._start_button.setEnabled(False)
        self._pause_button.setEnabled(True)
        self._resume_button.setEnabled(False)
        self._cancel_button.setEnabled(True)
        self._reset_button.setEnabled(False)

    def set_paused(self) -> None:
        """Affichage état paused."""
        self._start_button.setEnabled(False)
        self._pause_button.setEnabled(False)
        self._resume_button.setEnabled(True)
        self._cancel_button.setEnabled(True)
        self._reset_button.setEnabled(False)

    def set_finished(self) -> None:
        """Affichage état terminé."""
        self._start_button.setEnabled(True)
        self._pause_button.setEnabled(False)
        self._resume_button.setEnabled(False)
        self._cancel_button.setEnabled(False)
        self._reset_button.setEnabled(True)
