"""Estimation pré-run du coût total d'un projet.

L'estimation s'appuie sur :

- La durée audio totale des sources média (via ffprobe), ou les tokens texte
  estimés des documents.
- Le provider STT choisi (gratuit en local, 0.006 USD/min en cloud).
- Le modèle LLM choisi et la configuration par phase, incluant le mode
  ``thinking`` et le niveau ``reasoning_effort``.

Méthodologie heuristique pour les LLM (calibrée pour DeepSeek v4) :

- Hypothèse : 150 mots oraux par minute, ~1.3 tokens / mot.
- Pour chaque source, on estime un volume de tokens « de base »
  (``duration_minutes * 150 * 1.3`` pour un média, tokens texte pour un document).
- Pour chaque phase, on applique un ``input_multiplier`` et un
  ``output_multiplier`` empirique relatifs au volume de contenu.
- Si la phase a ``thinking_enabled = True``, le nombre de tokens de
  sortie est multiplié par un facteur empirique selon ``reasoning_effort``
  (le modèle « raisonne » avant de répondre et ces tokens de raisonnement
  sont facturés au tarif output standard).

Ces multiplicateurs sont des estimations grossières — l'objectif est de
fournir un ordre de grandeur fiable, pas une prédiction au cent près.
"""

from __future__ import annotations

from dataclasses import dataclass

from fahmi2.app._cost_common import (
    TOKENS_PER_WORD,
    WORDS_PER_MINUTE_ORAL,
    cost_range,
    thinking_output_multiplier,
)
from fahmi2.domain.enums import LLMModel, PhaseId, SttProvider
from fahmi2.domain.phase import PhaseConfig
from fahmi2.infra.llm._pricing import get_pricing

_USD_PER_MINUTE_OPENAI_WHISPER = 0.006
_SECONDS_PER_MINUTE = 60.0


@dataclass(frozen=True)
class SourceWeight:
    """Charge estimée d'une source pour le calcul de coût.

    Attributes:
        audio_seconds: Durée audio (vidéo/audio/YouTube ; 0 pour un document).
        text_tokens: Tokens texte estimés (document ; 0 sinon).
        reformulated: ``False`` si la source saute la reformulation (document
            en pass-through).
    """

    audio_seconds: float
    text_tokens: float
    reformulated: bool = True


def _base_tokens(weight: SourceWeight) -> float:
    """Volume de tokens « de base » d'une source (audio converti + texte).

    Args:
        weight: Charge de la source.

    Returns:
        Le volume de tokens estimé (durée audio → mots → tokens, plus les
        tokens texte d'un document).
    """
    audio_tokens = (
        (weight.audio_seconds / _SECONDS_PER_MINUTE)
        * WORDS_PER_MINUTE_ORAL
        * TOKENS_PER_WORD
    )
    return audio_tokens + weight.text_tokens


@dataclass(frozen=True)
class _PhaseLoadFactor:
    """Multiplicateurs empiriques d'une phase LLM relatifs au volume de contenu.

    Attributes:
        input_per_source: Tokens d'entrée par source (multiplicateur du base).
        output_per_source: Tokens de sortie par source.
        is_per_source: Si ``False``, la phase est batch (un seul appel pour
            tout le run, plus l'éventuel sous-loop sur les sources).
        batch_input_multiplier: Multiplicateur appliqué sur le volume total
            pour la phase batch.
        batch_output_factor: Sortie batch fixe en multiples du volume total.
        sub_loop_per_source: Si non-None, multiplicateur d'entrée d'un sous-appel
            par source (utilisé par phase 5).
        sub_loop_output_factor: Multiplicateur de sortie du sous-appel par source
            (relatif au volume de contenu), appliqué quand ``sub_loop_per_source``
            est défini.
    """

    input_per_source: float
    output_per_source: float
    is_per_source: bool
    batch_input_multiplier: float = 0.0
    batch_output_factor: float = 0.0
    sub_loop_per_source: float | None = None
    sub_loop_output_factor: float = 0.0


_LOAD_FACTORS: dict[PhaseId, _PhaseLoadFactor] = {
    PhaseId.TERM_EXTRACTION: _PhaseLoadFactor(
        input_per_source=1.0,
        output_per_source=0.15,
        is_per_source=True,
    ),
    PhaseId.GLOSSARY_RECONCILIATION: _PhaseLoadFactor(
        input_per_source=0.0,
        output_per_source=0.0,
        is_per_source=False,
        batch_input_multiplier=0.2,
        batch_output_factor=0.3,
    ),
    PhaseId.REFORMULATION: _PhaseLoadFactor(
        input_per_source=1.2,
        output_per_source=1.0,
        is_per_source=True,
    ),
    PhaseId.STRUCTURATION: _PhaseLoadFactor(
        input_per_source=1.0,
        output_per_source=1.0,
        is_per_source=True,
    ),
    PhaseId.CONSOLIDATION: _PhaseLoadFactor(
        input_per_source=0.0,
        output_per_source=0.0,
        is_per_source=False,
        batch_input_multiplier=0.3,
        batch_output_factor=0.5,
        sub_loop_per_source=0.2,
        sub_loop_output_factor=0.1,
    ),
    PhaseId.TRANSLATION: _PhaseLoadFactor(
        input_per_source=1.0,
        output_per_source=1.0,
        is_per_source=True,
    ),
    PhaseId.COHERENCE: _PhaseLoadFactor(
        input_per_source=0.0,
        output_per_source=0.0,
        is_per_source=False,
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
        total_usd: Somme (estimation ponctuelle).
        total_audio_seconds: Durée totale audio estimée (entrée).
        per_phase_usd: Coût estimé par phase (STT inclus).
        low_usd: Bas de fourchette d'incertitude (±33 %).
        high_usd: Haut de fourchette d'incertitude (±33 %).
    """

    stt_usd: float
    llm_usd: float
    total_usd: float
    total_audio_seconds: float
    per_phase_usd: dict[PhaseId, float]
    low_usd: float
    high_usd: float


class CostEstimator:
    """Estime le coût total d'un projet à partir de la charge des sources et settings."""

    def estimate(
        self,
        *,
        source_weights: list[SourceWeight],
        stt_provider: SttProvider,
        llm_model: LLMModel,
        active_target_languages_count: int = 1,
        translation_languages_count: int = 0,
        phases_config: dict[PhaseId, PhaseConfig] | None = None,
    ) -> CostEstimation:
        """Estime le coût total.

        Args:
            source_weights: Charge par source (durée audio **ou** tokens texte,
                + drapeau ``reformulated``).
            stt_provider: Provider STT choisi.
            llm_model: Modèle LLM choisi.
            active_target_languages_count: Nombre total de langues de sortie.
            translation_languages_count: Nombre de langues nécessitant une
                traduction (langues ≠ source).
            phases_config: Configuration par phase (notamment
                ``thinking_enabled`` et ``reasoning_effort``). Si ``None``,
                l'estimation est faite **sans** thinking, ce qui sous-estime
                significativement le coût quand le projet active le
                raisonnement étendu.

        Returns:
            ``CostEstimation`` avec détails STT/LLM/total.
        """
        total_audio_seconds = sum(w.audio_seconds for w in source_weights)
        total_base_tokens = sum(_base_tokens(w) for w in source_weights)
        reformulated_base_tokens = sum(
            _base_tokens(w) for w in source_weights if w.reformulated
        )
        stt_cost = self._stt_cost(total_audio_seconds, stt_provider)
        llm_per_phase = self._llm_cost_per_phase(
            total_base_tokens=total_base_tokens,
            reformulated_base_tokens=reformulated_base_tokens,
            llm_model=llm_model,
            target_languages_count=active_target_languages_count,
            translation_languages_count=translation_languages_count,
            phases_config=phases_config or {},
        )
        llm_cost = sum(llm_per_phase.values())
        total = stt_cost + llm_cost
        low, high = cost_range(total)
        return CostEstimation(
            stt_usd=stt_cost,
            llm_usd=llm_cost,
            total_usd=total,
            total_audio_seconds=total_audio_seconds,
            per_phase_usd={PhaseId.STT: stt_cost, **llm_per_phase},
            low_usd=low,
            high_usd=high,
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

    def _llm_cost_per_phase(
        self,
        *,
        total_base_tokens: float,
        reformulated_base_tokens: float,
        llm_model: LLMModel,
        target_languages_count: int,
        translation_languages_count: int,
        phases_config: dict[PhaseId, PhaseConfig],
    ) -> dict[PhaseId, float]:
        """Calcule le coût LLM estimé **par phase**.

        Args:
            total_base_tokens: Volume de tokens de base de toutes les sources.
            reformulated_base_tokens: Volume des seules sources reformulées
                (les documents en pass-through ne contribuent pas à la phase
                de reformulation).
            llm_model: Modèle.
            target_languages_count: Nombre de langues de sortie.
            translation_languages_count: Nombre de langues nécessitant traduction.
            phases_config: Configuration des phases (mapping vide si non fourni).

        Returns:
            Coût USD estimé par ``PhaseId`` (phases LLM uniquement).
        """
        pricing = get_pricing(str(llm_model))

        per_phase: dict[PhaseId, float] = {}
        for phase_id, factor in _LOAD_FACTORS.items():
            thinking_mult = thinking_output_multiplier(phases_config.get(phase_id))
            # La reformulation ne porte que sur les sources effectivement
            # reformulées (un document en pass-through y échappe).
            volume = (
                reformulated_base_tokens
                if phase_id is PhaseId.REFORMULATION
                else total_base_tokens
            )
            if factor.is_per_source:
                multiplier = (
                    translation_languages_count
                    if phase_id is PhaseId.TRANSLATION
                    else 1
                )
                phase_input = factor.input_per_source * volume
                phase_output = factor.output_per_source * volume
                per_phase[phase_id] = per_phase.get(phase_id, 0.0) + pricing.cost_for(
                    prompt_tokens=int(phase_input * multiplier),
                    completion_tokens=int(
                        phase_output * multiplier * thinking_mult
                    ),
                    cached_prompt_tokens=0,
                )
            else:
                batch_input = factor.batch_input_multiplier * volume
                batch_output = factor.batch_output_factor * volume
                multiplier = (
                    target_languages_count
                    if phase_id is PhaseId.COHERENCE
                    else 1
                )
                per_phase[phase_id] = per_phase.get(phase_id, 0.0) + pricing.cost_for(
                    prompt_tokens=int(batch_input * multiplier),
                    completion_tokens=int(
                        batch_output * multiplier * thinking_mult
                    ),
                    cached_prompt_tokens=0,
                )
                if factor.sub_loop_per_source is not None:
                    sub_input = factor.sub_loop_per_source * volume
                    sub_output = factor.sub_loop_output_factor * volume
                    per_phase[phase_id] = per_phase.get(
                        phase_id, 0.0
                    ) + pricing.cost_for(
                        prompt_tokens=int(sub_input),
                        completion_tokens=int(sub_output * thinking_mult),
                        cached_prompt_tokens=0,
                    )
        return per_phase
