"""Implémentation factice de ``STTProvider`` pour les tests cross-couche.

Lookup par nom de fichier dans un dictionnaire de scénarios. Si le nom n'est
pas trouvé, retourne une transcription générique paramétrable. Permet aussi
d'injecter une exception via ``failures`` pour exercer les chemins d'erreur.
"""

from __future__ import annotations

from pathlib import Path

from fahmi2.core.errors.exceptions import Fahmi2Error
from fahmi2.domain.enums import Language
from fahmi2.infra.stt.interface import (
    ProgressCallback,
    Transcription,
    TranscriptionSegment,
)

_DEFAULT_TRANSCRIPTION = Transcription(
    segments=(
        TranscriptionSegment(
            start_seconds=0.0,
            end_seconds=2.0,
            text="contenu de test généré par FakeSTTProvider",
        ),
    ),
    detected_language=Language.FR,
    duration_seconds=2.0,
)


class FakeSTTProvider:
    """STT factice scénarisable pour les tests."""

    def __init__(
        self,
        *,
        scenarios: dict[str, Transcription] | None = None,
        failures: dict[str, Fahmi2Error] | None = None,
        default_transcription: Transcription = _DEFAULT_TRANSCRIPTION,
    ) -> None:
        """Construit un ``FakeSTTProvider``.

        Args:
            scenarios: Mapping ``nom_de_fichier -> Transcription`` à retourner.
            failures: Mapping ``nom_de_fichier -> exception`` à lever.
            default_transcription: Retour si aucun scénario ne matche.
        """
        self._scenarios = dict(scenarios or {})
        self._failures = dict(failures or {})
        self._default = default_transcription

    @property
    def name(self) -> str:
        """Identifiant stable du provider."""
        return "fake-stt"

    def transcribe(
        self,
        audio_path: Path,
        *,
        language_hint: Language | None = None,
        on_progress: ProgressCallback | None = None,
    ) -> Transcription:
        """Retourne la transcription scénarisée ou un défaut.

        Args:
            audio_path: Chemin de l'audio (seul ``audio_path.name`` est utilisé
                pour le lookup).
            language_hint: Indice de langue (utilisé seulement par les vrais
                adapters).
            on_progress: Callback de progression.

        Returns:
            ``Transcription``.

        Raises:
            Fahmi2Error: Si un scénario d'échec est associé au fichier.
        """
        del language_hint
        key = audio_path.name
        if key in self._failures:
            raise self._failures[key]
        if on_progress is not None:
            on_progress(0.0)
            on_progress(1.0)
        return self._scenarios.get(key, self._default)

    def estimate_cost(self, duration_seconds: float) -> float:
        """Retourne 0 : le fake n'a pas de coût.

        Args:
            duration_seconds: Durée audio (ignorée).

        Returns:
            ``0.0``.
        """
        del duration_seconds
        return 0.0
