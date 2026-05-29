"""Interface ``SupportGenerator`` et ``SupportContext`` (injection de dépendances).

Chaque type de support de révision est produit par une sous-classe de
``SupportGenerator``. Le ``SupportContext`` regroupe les dépendances stables
injectées par l'orchestrateur (réglages, dossiers, provider LLM, prompts,
artifacts, bus d'événements, jeton de pause) — **pas** de STT/ffmpeg.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from fahmi2.core.concurrency.pause_token import PauseToken
from fahmi2.core.retry.policy import RetryPolicy
from fahmi2.domain.enums import Language, SupportType
from fahmi2.domain.glossary import Term
from fahmi2.domain.pedagogy import PedagogySettings
from fahmi2.domain.supports import SupportArtifact
from fahmi2.infra.llm.interface import LLMProvider
from fahmi2.infra.prompts.loader import PromptLoader
from fahmi2.infra.storage.fs_artifacts import FsArtifactStore
from fahmi2.pedagogy.chapters import Chapter
from fahmi2.pedagogy.events import PedagogyEvent
from fahmi2.pipeline.event_bus import EventBus


@dataclass(frozen=True)
class SupportContext:
    """Dépendances injectées à un ``SupportGenerator``.

    Attributes:
        pedagogy: Réglages pédagogie du projet.
        generation_output_dir: Dossier des livrables de génération (source).
        pedagogy_dir: Dossier de sortie des supports (``<emplacement>/pedagogy``).
        llm_provider: Provider LLM (utilisé par les générateurs LLM, SP2/03).
        prompts: Loader de prompts (défauts bundlés + override ``%APPDATA%``).
        artifacts: Écriture atomique d'artefacts.
        event_bus: Bus d'événements pédagogie.
        pause_token: Jeton coopératif pause/annulation.
        retry_policy: Politique de retry des appels LLM.
    """

    pedagogy: PedagogySettings
    generation_output_dir: Path
    pedagogy_dir: Path
    llm_provider: LLMProvider
    prompts: PromptLoader
    artifacts: FsArtifactStore
    event_bus: EventBus[PedagogyEvent]
    pause_token: PauseToken
    retry_policy: RetryPolicy


class SupportGenerator(ABC):
    """Base abstraite d'un générateur de support de révision."""

    @property
    @abstractmethod
    def support_type(self) -> SupportType:
        """Type de support produit."""

    @property
    @abstractmethod
    def uses_llm(self) -> bool:
        """Indique si le générateur appelle le LLM (``True``) ou non (``False``)."""

    @abstractmethod
    def generate(
        self,
        ctx: SupportContext,
        *,
        language: Language,
        chapters: tuple[Chapter, ...],
        glossary: tuple[Term, ...],
    ) -> SupportArtifact:
        """Génère le support pour une langue donnée.

        Args:
            ctx: Contexte d'exécution (dépendances stables).
            language: Langue cible.
            chapters: Chapitres du document consolidé (vide si non disponible).
            glossary: Termes du glossaire pour cette langue.

        Returns:
            Le ``SupportArtifact`` produit (items structurés + Markdown rendu + coût).

        Raises:
            Fahmi2Error: Toute erreur métier doit être typée (capturée par
                l'orchestrateur et convertie en ``ErrorInfo``).
        """
