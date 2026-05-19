"""Widget ``ProjectHeaderBar`` — barre titre du Run + boutons principaux."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget


class ProjectHeaderBar(QWidget):
    """Barre titre + actions principales d'un Run."""

    start_requested = Signal()
    pause_requested = Signal()
    resume_requested = Signal()
    cancel_requested = Signal()
    open_output_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        """Construit la barre.

        Args:
            parent: Parent Qt optionnel.
        """
        super().__init__(parent)
        self.setObjectName("projectHeaderBar")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(8)

        self._title_label = QLabel("Projet : —", self)
        self._title_label.setObjectName("projectHeaderBarTitle")
        layout.addWidget(self._title_label)
        layout.addStretch(1)

        self._start_button = self._make_button("▶  Lancer", role="primary")
        self._pause_button = self._make_button("⏸  Pause", role="default")
        self._resume_button = self._make_button("▶  Reprendre", role="primary")
        self._cancel_button = self._make_button("✕  Annuler", role="danger")
        self._open_output_button = self._make_button(
            "📂  Dossier de sortie", role="default"
        )
        self._open_output_button.setToolTip(
            "Ouvre dans l'explorateur le dossier contenant les fichiers Markdown "
            "produits (consolidated, glossary, per-video par langue)."
        )

        self._start_button.clicked.connect(self.start_requested)
        self._pause_button.clicked.connect(self.pause_requested)
        self._resume_button.clicked.connect(self.resume_requested)
        self._cancel_button.clicked.connect(self.cancel_requested)
        self._open_output_button.clicked.connect(self.open_output_requested)

        for btn in (
            self._start_button,
            self._pause_button,
            self._resume_button,
            self._cancel_button,
            self._open_output_button,
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
        btn = QPushButton(text, self)
        btn.setProperty("role", role)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        return btn

    def set_title(self, title: str) -> None:
        """Met à jour le titre.

        Args:
            title: Texte du titre.
        """
        self._title_label.setText(f"Projet : {title}")

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

    def set_running(self) -> None:
        """Affichage état running."""
        self._start_button.setEnabled(False)
        self._pause_button.setEnabled(True)
        self._resume_button.setEnabled(False)
        self._cancel_button.setEnabled(True)

    def set_paused(self) -> None:
        """Affichage état paused."""
        self._start_button.setEnabled(False)
        self._pause_button.setEnabled(False)
        self._resume_button.setEnabled(True)
        self._cancel_button.setEnabled(True)

    def set_finished(self) -> None:
        """Affichage état terminé."""
        self._start_button.setEnabled(True)
        self._pause_button.setEnabled(False)
        self._resume_button.setEnabled(False)
        self._cancel_button.setEnabled(False)
