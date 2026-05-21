"""Entité ``PedagogySettings`` (fonctionnalité Supports pédagogiques).

Regroupe les réglages de génération des supports de révision : types choisis,
corrigés séparés, public cible + objectif Bloom + directives, langues, densité,
modèle LLM + config, plafond de coût et formats d'export. Le nom et l'emplacement
restent portés par ``Project``.
"""

from __future__ import annotations

from dataclasses import dataclass

from fahmi2.domain.enums import (
    BloomObjective,
    ExportFormat,
    Language,
    LLMModel,
    SupportDensity,
    SupportType,
    TargetAudience,
)
from fahmi2.domain.phase import PhaseConfig

#: Sous-dossier du workspace dédié aux supports pédagogiques.
PEDAGOGY_WORKSPACE_SUBDIR = "pedagogy"

#: Nombre de tâches LLM concurrentes par défaut (DeepSeek : limite par
#: concurrence très haute, donc valeur généreuse mais sûre).
DEFAULT_PEDAGOGY_LLM_WORKERS = 16

#: Borne haute proposée dans l'UI pour le réglage « tâches en parallèle ».
MAX_PEDAGOGY_LLM_WORKERS = 64

#: Supports évaluatifs (un corrigé séparé a du sens).
EVALUATIVE_SUPPORTS: frozenset[SupportType] = frozenset(
    {
        SupportType.QCM,
        SupportType.TRUE_FALSE,
        SupportType.CLOZE,
        SupportType.OPEN_QUESTIONS,
        SupportType.MOCK_EXAM,
    }
)

#: Supports produits sans appel LLM. Vide depuis le retrait de
#: ``flashcards_glossary`` ; conservé pour rester générique (le cost estimator
#: filtre dessus).
NO_LLM_SUPPORTS: frozenset[SupportType] = frozenset()


@dataclass(frozen=True)
class PedagogySettings:
    """Réglages de la fonctionnalité Supports pédagogiques.

    Attributes:
        selected_supports: Types de supports à générer (non vide).
        separate_correction: Supports évaluatifs pour lesquels produire un
            corrigé séparé (⊆ ``EVALUATIVE_SUPPORTS`` ∩ ``selected_supports``).
        target_audience: Public cible (exigence + registre).
        bloom_objective: Objectif cognitif Bloom (``AUTO`` = selon le public).
        pedagogy_directives: Directives pédagogiques libres.
        languages: Langues de génération (non vide).
        density: Densité (volume) des supports.
        llm_model: Modèle DeepSeek utilisé.
        llm_config: Config des appels LLM (thinking/effort/température/retries).
        cost_ceiling_usd: Plafond de coût (``None`` = pas de plafond).
        export_formats: Formats d'export demandés.
        llm_workers: Tâches LLM concurrentes (>= 1). Sans effet sur le contenu
            généré : n'entre pas dans le hash de fraîcheur.
    """

    selected_supports: frozenset[SupportType]
    separate_correction: frozenset[SupportType]
    target_audience: TargetAudience
    bloom_objective: BloomObjective
    pedagogy_directives: str
    languages: tuple[Language, ...]
    density: SupportDensity
    llm_model: LLMModel
    llm_config: PhaseConfig
    cost_ceiling_usd: float | None
    export_formats: frozenset[ExportFormat]
    llm_workers: int = DEFAULT_PEDAGOGY_LLM_WORKERS

    def __post_init__(self) -> None:
        if not self.selected_supports:
            raise ValueError("selected_supports must contain at least one support")
        if not self.languages:
            raise ValueError("languages must contain at least one language")
        allowed_correction = EVALUATIVE_SUPPORTS & self.selected_supports
        invalid = self.separate_correction - allowed_correction
        if invalid:
            raise ValueError(
                "separate_correction must be a subset of evaluative selected "
                f"supports. Invalid: {sorted(s.value for s in invalid)}"
            )
        if self.cost_ceiling_usd is not None and self.cost_ceiling_usd < 0:
            raise ValueError(
                f"cost_ceiling_usd must be >= 0 or None, got {self.cost_ceiling_usd}"
            )
        if self.llm_workers < 1:
            raise ValueError(f"llm_workers must be >= 1, got {self.llm_workers}")
