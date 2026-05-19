"""Interface ``STTProvider`` et types associés.

Définit le contrat commun aux deux adapters STT (FasterWhisper local et OpenAI
cloud) ainsi que les structures immuables ``Transcription`` et
``TranscriptionSegment`` produites en sortie.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from fahmi2.domain.enums import Language


@dataclass(frozen=True)
class TranscriptionSegment:
    """Un segment temporel de transcription audio.

    Attributes:
        start_seconds: Timestamp début (>= 0).
        end_seconds: Timestamp fin (>= start_seconds).
        text: Contenu textuel du segment.
    """

    start_seconds: float
    end_seconds: float
    text: str

    def __post_init__(self) -> None:
        if self.start_seconds < 0:
            raise ValueError(f"start_seconds must be >= 0, got {self.start_seconds}")
        if self.end_seconds < self.start_seconds:
            raise ValueError(
                f"end_seconds ({self.end_seconds}) must be >= start_seconds "
                f"({self.start_seconds})"
            )


@dataclass(frozen=True)
class Transcription:
    """Résultat complet d'une transcription audio.

    Attributes:
        segments: Tuple immuable des segments dans l'ordre temporel.
        detected_language: Langue détectée par le modèle.
        duration_seconds: Durée totale de l'audio source.
    """

    segments: tuple[TranscriptionSegment, ...]
    detected_language: Language
    duration_seconds: float

    def __post_init__(self) -> None:
        if self.duration_seconds < 0:
            raise ValueError(
                f"duration_seconds must be >= 0, got {self.duration_seconds}"
            )

    def full_text(self) -> str:
        """Joint le texte de tous les segments séparés par une espace.

        Returns:
            Texte concaténé.
        """
        return " ".join(s.text for s in self.segments)


ProgressCallback = Callable[[float], None]


class STTProvider(Protocol):
    """Contrat commun aux adapters STT."""

    @property
    def name(self) -> str:
        """Identifiant du provider (utilisé dans logs et tests)."""

    def transcribe(
        self,
        audio_path: Path,
        *,
        language_hint: Language | None = None,
        on_progress: ProgressCallback | None = None,
    ) -> Transcription:
        """Transcrit un fichier audio.

        Args:
            audio_path: Fichier audio à transcrire (idéalement WAV 16 kHz mono).
            language_hint: Indice de langue (None = auto-détection).
            on_progress: Callback de progression ``[0.0, 1.0]``.

        Returns:
            Le résultat ``Transcription``.

        Raises:
            STTError: En cas d'échec.
        """

    def estimate_cost(self, duration_seconds: float) -> float:
        """Estime le coût en USD pour une durée audio donnée.

        Args:
            duration_seconds: Durée de l'audio en secondes.

        Returns:
            Coût estimé en USD (0 pour les providers locaux).
        """
