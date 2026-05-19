"""Entité ``VideoExecution`` — état d'exécution d'une vidéo dans un Run."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from fahmi2.domain.enums import Language, PhaseId, PhaseStatus
from fahmi2.domain.ids import VideoId
from fahmi2.domain.phase import PhaseExecution


@dataclass(frozen=True)
class VideoExecution:
    """État d'exécution d'une vidéo dans un Run.

    Attributes:
        video_id: Identifiant stable de la vidéo dans le projet.
        source_path: Chemin du fichier source.
        detected_language: Langue détectée par Whisper (``None`` tant que STT
            non exécuté).
        phase_executions: Mapping ``PhaseId → PhaseExecution`` pour les phases
            par-vidéo (0, 1, 3, 4, 6, 7). Les phases batch (2, 5) sont au niveau
            du ``Run``.
    """

    video_id: VideoId
    source_path: Path
    detected_language: Language | None = None
    phase_executions: dict[PhaseId, PhaseExecution] = field(default_factory=dict)

    def phase_status(self, phase_id: PhaseId) -> PhaseStatus:
        """Retourne le statut de la phase pour cette vidéo.

        Args:
            phase_id: Phase à inspecter.

        Returns:
            Le statut, ou ``PhaseStatus.PENDING`` si la phase n'a pas commencé.
        """
        pe = self.phase_executions.get(phase_id)
        return pe.status if pe is not None else PhaseStatus.PENDING
