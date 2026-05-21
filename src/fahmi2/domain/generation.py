"""Entités de la fonctionnalité Génération : ``GenerationSettings``, ``ParallelismConfig``.

``GenerationSettings`` regroupe tous les paramètres métier de la génération (vidéos →
document consolidé). Le nom et l'emplacement du projet n'en font **pas** partie : ils
sont portés par ``Project`` (identité minimale, cf. ``domain.project``).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from fahmi2.domain.enums import (
    Language,
    LLMModel,
    PhaseId,
    SttProvider,
    StylePreset,
)
from fahmi2.domain.phase import PhaseConfig

_DEFAULT_STT_CLOUD_WORKERS = 3
_DEFAULT_LLM_WORKERS = 16

#: Bornes hautes proposées dans l'UI. La limite DeepSeek est par concurrence
#: (très au-dessus), donc le LLM peut monter haut ; OpenAI Whisper (STT cloud) a
#: de vraies limites RPM → borne plus basse.
MAX_STT_CLOUD_WORKERS = 8
MAX_LLM_WORKERS = 64
_LLM_PHASES: frozenset[PhaseId] = frozenset(
    p for p in PhaseId if p is not PhaseId.STT
)

#: Sous-dossier du workspace dédié aux artefacts de la fonctionnalité Génération.
GENERATION_WORKSPACE_SUBDIR = "generation"

#: Sous-dossier des livrables finaux de la génération (sous le dossier feature).
GENERATION_OUTPUT_SUBDIR = "output"


def consolidated_doc_filename(language: Language) -> str:
    """Nom de fichier du document consolidé pour une langue.

    Args:
        language: Langue cible.

    Returns:
        Le nom de fichier (ex: ``"consolidated.fr.md"``).
    """
    return f"consolidated.{language}.md"


@dataclass(frozen=True)
class ParallelismConfig:
    """Configuration de parallélisme du pipeline.

    Note:
        STT local est toujours séquentiel (1 GPU). Seuls STT cloud et LLM sont
        parallélisables.

    Attributes:
        stt_cloud_workers: Workers concurrents pour le STT cloud (>= 1).
        llm_workers: Workers concurrents pour les appels LLM (>= 1).
    """

    stt_cloud_workers: int = _DEFAULT_STT_CLOUD_WORKERS
    llm_workers: int = _DEFAULT_LLM_WORKERS

    def __post_init__(self) -> None:
        if self.stt_cloud_workers < 1:
            raise ValueError("stt_cloud_workers must be >= 1")
        if self.llm_workers < 1:
            raise ValueError("llm_workers must be >= 1")


@dataclass(frozen=True)
class GenerationSettings:
    """Paramètres de la fonctionnalité Génération (vidéos → document consolidé).

    Les phases LLM (1..7) doivent toutes être configurées dans ``phases_config``.
    ``output_languages`` doit toujours contenir ``source_language``.

    Attributes:
        input_folder: Dossier d'entrée contenant les vidéos.
        source_language: Langue source du contenu.
        output_languages: Tuple des langues de sortie demandées.
        style_preset: Style de rendu.
        style_directives: Directives stylistiques libres (peuvent être vides).
        stt_provider: Provider STT (local ou cloud).
        llm_model: Modèle DeepSeek utilisé.
        phases_config: Configuration des phases LLM 1..7.
        cost_ceiling_usd: Plafond de coût (``None`` = pas de plafond).
        parallelism: Configuration de parallélisme.
        delete_audio_after_stt: Si ``True``, l'audio extrait est supprimé après STT.
    """

    input_folder: Path
    source_language: Language
    output_languages: tuple[Language, ...]
    style_preset: StylePreset
    style_directives: str
    stt_provider: SttProvider
    llm_model: LLMModel
    phases_config: dict[PhaseId, PhaseConfig]
    cost_ceiling_usd: float | None
    parallelism: ParallelismConfig
    delete_audio_after_stt: bool

    def __post_init__(self) -> None:
        if not self.output_languages:
            raise ValueError("output_languages must contain at least one language")
        if self.source_language not in self.output_languages:
            raise ValueError(
                f"output_languages must contain source_language "
                f"({self.source_language})"
            )
        configured = set(self.phases_config)
        expected = set(_LLM_PHASES)
        if configured != expected:
            missing = sorted(expected - configured)
            extra = sorted(configured - expected)
            raise ValueError(
                "phases_config must cover exactly LLM phases (1..7). "
                f"Missing: {missing}, Extra: {extra}"
            )
        if self.cost_ceiling_usd is not None and self.cost_ceiling_usd < 0:
            raise ValueError(
                f"cost_ceiling_usd must be >= 0 or None, got {self.cost_ceiling_usd}"
            )
