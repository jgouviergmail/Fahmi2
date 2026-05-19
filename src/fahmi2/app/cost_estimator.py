"""Estimation pré-run du coût total d'un projet.

L'estimation s'appuie sur :

- La durée audio totale des vidéos (via ffprobe).
- Le provider STT choisi (gratuit en local, 0.006 USD/min en cloud).
- Le modèle LLM choisi et les phases activées (heuristique sur le ratio
  tokens d'entrée / sortie).

Méthodologie heuristique pour les LLM (calibrée pour DeepSeek v4) :

- Hypothèse : 150 mots oraux par minute, ~1.3 tokens / mot.
- Pour chaque vidéo, on estime ``tokens_per_video = duration_minutes * 150 * 1.3``.
- Pour chaque phase, on applique un ``input_multiplier`` et un
  ``output_multiplier`` empirique relatifs au contenu vidéo.

Ces multiplicateurs sont des estimations grossières — l'objectif est de
fournir un ordre de grandeur fiable, pas une prédiction au cent près.
"""

from __future__ import annotations

from dataclasses import dataclass

from fahmi2.domain.enums import LLMModel, PhaseId, SttProvider
from fahmi2.infra.llm._pricing import get_pricing

_USD_PER_MINUTE_OPENAI_WHISPER = 0.006
_SECONDS_PER_MINUTE = 60.0
_WORDS_PER_MINUTE_ORAL = 150.0
_TOKENS_PER_WORD = 1.3


@dataclass(frozen=True)
class _PhaseLoadFactor:
    """Multiplicateurs empiriques d'une phase LLM relatifs au volume vidéo.

    Attributes:
        input_per_video: Tokens d'entrée par vidéo (multiplicateur du base).
        output_per_video: Tokens de sortie par vidéo.
        is_per_video: Si ``False``, la phase est batch (un seul appel pour
            tout le run, plus l'éventuel sous-loop sur les vidéos).
        batch_input_multiplier: Multiplicateur appliqué sur le total vidéo
            pour la phase batch.
        batch_output_factor: Sortie batch fixe en multiples du volume vidéo.
        sub_loop_per_video: Si non-None, multiplicateur d'un sous-appel par
            vidéo (utilisé par phase 5).
    """

    input_per_video: float
    output_per_video: float
    is_per_video: bool
    batch_input_multiplier: float = 0.0
    batch_output_factor: float = 0.0
    sub_loop_per_video: float | None = None


_LOAD_FACTORS: dict[PhaseId, _PhaseLoadFactor] = {
    PhaseId.TERM_EXTRACTION: _PhaseLoadFactor(
        input_per_video=1.0,
        output_per_video=0.15,
        is_per_video=True,
    ),
    PhaseId.GLOSSARY_RECONCILIATION: _PhaseLoadFactor(
        input_per_video=0.0,
        output_per_video=0.0,
        is_per_video=False,
        batch_input_multiplier=0.2,
        batch_output_factor=0.3,
    ),
    PhaseId.REFORMULATION: _PhaseLoadFactor(
        input_per_video=1.2,
        output_per_video=1.0,
        is_per_video=True,
    ),
    PhaseId.STRUCTURATION: _PhaseLoadFactor(
        input_per_video=1.0,
        output_per_video=1.0,
        is_per_video=True,
    ),
    PhaseId.CONSOLIDATION: _PhaseLoadFactor(
        input_per_video=0.0,
        output_per_video=0.0,
        is_per_video=False,
        batch_input_multiplier=0.3,
        batch_output_factor=0.5,
        sub_loop_per_video=0.2,
    ),
    PhaseId.TRANSLATION: _PhaseLoadFactor(
        input_per_video=1.0,
        output_per_video=1.0,
        is_per_video=True,
    ),
    PhaseId.COHERENCE: _PhaseLoadFactor(
        input_per_video=0.0,
        output_per_video=0.0,
        is_per_video=False,
        batch_input_multiplier=1.5,
        batch_output_factor=1.5,
    ),
}


@dataclass(frozen=True)
class CostEstimation:
    """Estimation du coût total d'un Run.

    Attributes:
        stt_usd: Coût USD du STT.
        llm_usd: Coût USD cumulé des phases LLM.
        total_usd: Somme.
        total_audio_seconds: Durée totale audio estimée (entrée).
    """

    stt_usd: float
    llm_usd: float
    total_usd: float
    total_audio_seconds: float


class CostEstimator:
    """Estime le coût total d'un projet à partir des durées vidéo et settings."""

    def estimate(
        self,
        *,
        videos_durations_seconds: list[float],
        stt_provider: SttProvider,
        llm_model: LLMModel,
        active_target_languages_count: int = 1,
        translation_languages_count: int = 0,
    ) -> CostEstimation:
        """Estime le coût total.

        Args:
            videos_durations_seconds: Liste des durées vidéo en secondes.
            stt_provider: Provider STT choisi.
            llm_model: Modèle LLM choisi.
            active_target_languages_count: Nombre total de langues de sortie.
            translation_languages_count: Nombre de langues nécessitant une
                traduction (langues ≠ source).

        Returns:
            ``CostEstimation`` avec détails STT/LLM/total.
        """
        total_audio_seconds = sum(videos_durations_seconds)
        n_videos = len(videos_durations_seconds)
        stt_cost = self._stt_cost(total_audio_seconds, stt_provider)
        llm_cost = self._llm_cost(
            total_audio_seconds=total_audio_seconds,
            n_videos=n_videos,
            llm_model=llm_model,
            target_languages_count=active_target_languages_count,
            translation_languages_count=translation_languages_count,
        )
        return CostEstimation(
            stt_usd=stt_cost,
            llm_usd=llm_cost,
            total_usd=stt_cost + llm_cost,
            total_audio_seconds=total_audio_seconds,
        )

    @staticmethod
    def _stt_cost(total_audio_seconds: float, provider: SttProvider) -> float:
        """Calcule le coût STT pour la durée audio totale.

        Args:
            total_audio_seconds: Durée audio totale (secondes).
            provider: Provider STT.

        Returns:
            Coût USD (0 pour le provider local).
        """
        if provider is SttProvider.OPENAI_CLOUD:
            return (total_audio_seconds / _SECONDS_PER_MINUTE) * _USD_PER_MINUTE_OPENAI_WHISPER
        return 0.0

    def _llm_cost(
        self,
        *,
        total_audio_seconds: float,
        n_videos: int,
        llm_model: LLMModel,
        target_languages_count: int,
        translation_languages_count: int,
    ) -> float:
        """Calcule le coût LLM cumulé sur toutes les phases.

        Args:
            total_audio_seconds: Durée audio totale.
            n_videos: Nombre de vidéos.
            llm_model: Modèle.
            target_languages_count: Nombre de langues de sortie.
            translation_languages_count: Nombre de langues nécessitant traduction.

        Returns:
            Coût USD cumulé.
        """
        pricing = get_pricing(str(llm_model))
        base_tokens_per_video = (
            (total_audio_seconds / _SECONDS_PER_MINUTE)
            / max(n_videos, 1)
            * _WORDS_PER_MINUTE_ORAL
            * _TOKENS_PER_WORD
        )

        total = 0.0
        for phase_id, factor in _LOAD_FACTORS.items():
            if factor.is_per_video:
                multiplier = (
                    translation_languages_count
                    if phase_id is PhaseId.TRANSLATION
                    else 1
                )
                phase_input = (
                    factor.input_per_video * base_tokens_per_video * n_videos
                )
                phase_output = (
                    factor.output_per_video * base_tokens_per_video * n_videos
                )
                total += pricing.cost_for(
                    prompt_tokens=int(phase_input * multiplier),
                    completion_tokens=int(phase_output * multiplier),
                    cached_prompt_tokens=0,
                )
            else:
                batch_input = (
                    factor.batch_input_multiplier
                    * base_tokens_per_video
                    * n_videos
                )
                batch_output = (
                    factor.batch_output_factor
                    * base_tokens_per_video
                    * n_videos
                )
                multiplier = (
                    target_languages_count
                    if phase_id is PhaseId.COHERENCE
                    else 1
                )
                total += pricing.cost_for(
                    prompt_tokens=int(batch_input * multiplier),
                    completion_tokens=int(batch_output * multiplier),
                    cached_prompt_tokens=0,
                )
                if factor.sub_loop_per_video is not None:
                    sub_input = (
                        factor.sub_loop_per_video
                        * base_tokens_per_video
                        * n_videos
                    )
                    sub_output = 0.1 * base_tokens_per_video * n_videos
                    total += pricing.cost_for(
                        prompt_tokens=int(sub_input),
                        completion_tokens=int(sub_output),
                        cached_prompt_tokens=0,
                    )
        return total
