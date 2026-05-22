"""Source d'entrée de la génération.

Définit le value object ``InputSource`` (fichier local ou URL distante), qui
porte le type et l'emplacement d'une source — là où un simple ``Path`` ne
saurait représenter une URL — et l'entité ``SourceExecution`` (état d'exécution
d'une source dans un Run).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from fahmi2.domain.enums import Language, PhaseId, PhaseStatus, SourceKind
from fahmi2.domain.ids import SourceId
from fahmi2.domain.phase import PhaseExecution


@dataclass(frozen=True)
class InputSource:
    """Une source d'entrée de la génération (fichier local ou URL distante).

    Attributes:
        kind: Type de source (vidéo, audio, document, YouTube).
        location: Chemin de fichier (POSIX/Windows) **ou** URL, selon ``kind``.
    """

    kind: SourceKind
    location: str

    @property
    def is_remote(self) -> bool:
        """``True`` pour une source distante (YouTube), ``False`` pour un fichier."""
        return self.kind is SourceKind.YOUTUBE

    @property
    def as_path(self) -> Path:
        """Chemin local de la source.

        Returns:
            Le ``Path`` de la source fichier.

        Raises:
            ValueError: Si la source est distante (pas de chemin local).
        """
        if self.is_remote:
            raise ValueError("Une source distante (YouTube) n'a pas de chemin local")
        return Path(self.location)

    def order_key(self) -> str:
        """Clé stable d'ordonnancement : nom de fichier (local) ou URL (distant).

        Returns:
            Le nom de fichier pour une source locale, l'URL pour une source
            distante.
        """
        return self.location if self.is_remote else Path(self.location).name

    def display_name(self) -> str:
        """Libellé court pour l'UI et les logs.

        Returns:
            Le nom de fichier ou l'URL.
        """
        return self.order_key()


@dataclass(frozen=True)
class SourceExecution:
    """État d'exécution d'une source d'entrée dans un Run.

    Attributes:
        source_id: Identifiant stable de la source dans le projet.
        source: La source d'entrée (fichier ou URL).
        detected_language: Langue détectée (``None`` tant que l'ingestion STT
            n'a pas tourné ; pour un document, posée à la langue source).
        phase_executions: Mapping ``PhaseId → PhaseExecution`` pour les phases
            par-source (0, 1, 3, 4, 6, 7). Les phases batch (2, 5) sont au niveau
            du ``Run``.
    """

    source_id: SourceId
    source: InputSource
    detected_language: Language | None = None
    phase_executions: dict[PhaseId, PhaseExecution] = field(default_factory=dict)

    def phase_status(self, phase_id: PhaseId) -> PhaseStatus:
        """Retourne le statut de la phase pour cette source.

        Args:
            phase_id: Phase à inspecter.

        Returns:
            Le statut, ou ``PhaseStatus.PENDING`` si la phase n'a pas commencé.
        """
        pe = self.phase_executions.get(phase_id)
        return pe.status if pe is not None else PhaseStatus.PENDING
