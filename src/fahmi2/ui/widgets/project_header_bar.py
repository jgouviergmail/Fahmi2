"""Widget ``ProjectHeaderBar`` — barre titre du Run + boutons Lancer/Pause/Annuler."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget


class ProjectHeaderBar(QWidget):
    """Barre titre + actions principales d'un Run."""

    start_requested = Signal()
    pause_requested = Signal()
    resume_requested = Signal()
    cancel_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        """Construit la barre.

        Args:
            parent: Parent Qt optionnel.
        """
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        self._title_label = QLabel("Projet : -", self)
        layout.addWidget(self._title_label)
        layout.addStretch(1)

        self._start_button = QPushButton("▶ Lancer", self)
        self._pause_button = QPushButton("⏸ Pause", self)
        self._resume_button = QPushButton("▶ Reprendre", self)
        self._cancel_button = QPushButton("✕ Annuler", self)
        self._start_button.clicked.connect(self.start_requested)
        self._pause_button.clicked.connect(self.pause_requested)
        self._resume_button.clicked.connect(self.resume_requested)
        self._cancel_button.clicked.connect(self.cancel_requested)
        layout.addWidget(self._start_button)
        layout.addWidget(self._pause_button)
        layout.addWidget(self._resume_button)
        layout.addWidget(self._cancel_button)
        self.set_idle()

    def set_title(self, title: str) -> None:
        """Met à jour le titre.

        Args:
            title: Texte du titre.
        """
        self._title_label.setText(f"Projet : {title}")

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
