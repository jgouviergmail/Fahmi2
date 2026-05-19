"""Entités ``Project``, ``ProjectSettings``, ``ParallelismConfig``."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from fahmi2.domain.enums import (
    Language,
    LLMModel,
    PhaseId,
    SttProvider,
    StylePreset,
)
from fahmi2.domain.ids import ProjectId, RunId
from fahmi2.domain.phase import PhaseConfig

_DEFAULT_STT_CLOUD_WORKERS = 3
_DEFAULT_LLM_WORKERS = 4
_LLM_PHASES: frozenset[PhaseId] = frozenset(
    p for p in PhaseId if p is not PhaseId.STT
)


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
class ProjectSettings:
    """Paramètres complets d'un Project.

    Les phases LLM (1..7) doivent toutes être configurées dans ``phases_config``.
    ``output_languages`` doit toujours contenir ``source_language``.

    Attributes:
        name: Nom utilisateur du projet.
        input_folder: Dossier d'entrée contenant les vidéos.
        workspace_folder: Dossier de travail (artefacts et sortie).
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

    name: str
    input_folder: Path
    workspace_folder: Path
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


@dataclass(frozen=True)
class Project:
    """Projet utilisateur persistant avec son historique de runs.

    Attributes:
        id: Identifiant stable du projet.
        settings: Paramètres complets du projet.
        created_at: Date de création.
        last_run_at: Date du dernier run terminé (None si jamais lancé).
        runs: Historique des ULID de Run associés au projet.
    """

    id: ProjectId
    settings: ProjectSettings
    created_at: datetime
    last_run_at: datetime | None = None
    runs: tuple[RunId, ...] = ()
