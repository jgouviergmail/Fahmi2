"""``SupportsOrchestrator`` — service applicatif pilotant la génération des supports.

Orchestrateur dédié **léger** (design §2.1) : ne réutilise pas le ``PipelineEngine``.
Pour chaque langue, charge les entrants (chapitres du doc consolidé + glossaire du
dernier run COMPLETED), itère les supports sélectionnés dans l'ordre canonique du
registre, invoque le générateur, écrit les artefacts (JSON + Markdown), met à jour
le manifeste de fraîcheur (reprise coarse) et émet les événements pédagogie. Gère
pause/annulation aux frontières sûres (entre supports).
"""

from __future__ import annotations

from datetime import UTC, datetime

from fahmi2.app.project_service import ProjectService
from fahmi2.core.errors.error_info import ErrorInfo
from fahmi2.core.errors.exceptions import ConfigError, Fahmi2Error, PausedError
from fahmi2.core.errors.severity import Severity
from fahmi2.core.retry.policy import RetryPolicy
from fahmi2.domain.enums import Language, PhaseStatus, RunStatus, SupportType
from fahmi2.domain.generation import (
    GENERATION_OUTPUT_SUBDIR,
    GENERATION_WORKSPACE_SUBDIR,
)
from fahmi2.domain.glossary import Term
from fahmi2.domain.pedagogy import PEDAGOGY_WORKSPACE_SUBDIR, PedagogySettings
from fahmi2.domain.project import Project
from fahmi2.domain.supports import SupportArtifact
from fahmi2.infra.llm.interface import LLMProvider
from fahmi2.infra.prompts.loader import PromptLoader
from fahmi2.infra.storage.fs_artifacts import FsArtifactStore
from fahmi2.infra.storage.sqlite_state import SqliteState
from fahmi2.pedagogy.artifact_writer import (
    artifact_correction_markdown_path,
    artifact_json_path,
    artifact_markdown_path,
    serialize_artifact,
)
from fahmi2.pedagogy.chapters import Chapter
from fahmi2.pedagogy.events import (
    PedagogyEvent,
    SupportFinished,
    SupportGenerationFinished,
    SupportGenerationStarted,
    SupportStarted,
)
from fahmi2.pedagogy.manifest import (
    PedagogyManifest,
    compute_settings_hash,
    read_manifest,
    write_manifest,
)
from fahmi2.pedagogy.sources import load_chapters, source_mtime_ns
from fahmi2.pedagogy.support_generator import SupportContext
from fahmi2.pedagogy.support_registry import SupportGeneratorRegistry
from fahmi2.pipeline.event_bus import EventBus
from fahmi2.pipeline.pause_token import PauseToken


class SupportsOrchestrator:
    """Pilote la génération des supports pédagogiques d'un projet."""

    def __init__(
        self,
        *,
        state: SqliteState,
        project_service: ProjectService,
        registry: SupportGeneratorRegistry,
        artifacts: FsArtifactStore,
        llm_provider: LLMProvider,
        prompts: PromptLoader,
        retry_policy: RetryPolicy,
    ) -> None:
        """Construit l'orchestrateur.

        Args:
            state: Stockage SQLite (lecture glossaire).
            project_service: Service projet (dernier run COMPLETED).
            registry: Registre des générateurs.
            artifacts: Écriture atomique d'artefacts.
            llm_provider: Provider LLM (générateurs LLM).
            prompts: Loader de prompts.
            retry_policy: Politique de retry des appels LLM des générateurs.
        """
        self._state = state
        self._project_service = project_service
        self._registry = registry
        self._artifacts = artifacts
        self._llm_provider = llm_provider
        self._prompts = prompts
        self._retry_policy = retry_policy

    def generate(
        self,
        project: Project,
        *,
        pause_token: PauseToken,
        event_bus: EventBus[PedagogyEvent],
    ) -> RunStatus:
        """Génère les supports sélectionnés pour toutes les langues.

        Args:
            project: Projet (doit avoir ``pedagogy`` configuré).
            pause_token: Jeton coopératif pause/annulation.
            event_bus: Bus d'événements pédagogie.

        Returns:
            ``COMPLETED`` (succès), ``FAILED`` (≥1 support échoué) ou
            ``CANCELLED`` (annulé par l'utilisateur).

        Raises:
            ConfigError: Si la pédagogie n'est pas configurée sur le projet.
        """
        pedagogy = project.pedagogy
        if pedagogy is None:
            raise ConfigError(
                code="PEDAGOGY.NOT_CONFIGURED",
                user_message=(
                    "La fonctionnalité Supports pédagogiques n'est pas configurée."
                ),
                severity=Severity.ERROR,
                technical_details={"project_id": project.id.value},
            )

        ctx = self._build_context(project, pedagogy, pause_token, event_bus)
        settings_hash = compute_settings_hash(pedagogy)
        manifest = read_manifest(ctx.pedagogy_dir)
        event_bus.publish(SupportGenerationStarted(timestamp=_now()))

        any_failure = False
        total_cost = 0.0
        try:
            for language in pedagogy.languages:
                source_mtime = source_mtime_ns(ctx.generation_output_dir, language)
                chapters = load_chapters(ctx.generation_output_dir, language)
                glossary = self._load_glossary(project, language)
                for support_type in self._registry.canonical_order():
                    if support_type not in pedagogy.selected_supports:
                        continue
                    if not self._registry.has(support_type):
                        continue
                    pause_token.wait_if_paused()
                    pause_token.raise_if_cancelled()
                    if _ceiling_reached(pedagogy, total_cost):
                        event_bus.publish(
                            SupportGenerationFinished(
                                timestamp=_now(),
                                status=RunStatus.PAUSED,
                                total_cost_usd=total_cost,
                            )
                        )
                        return RunStatus.PAUSED
                    cost, failed = self._run_one(
                        ctx,
                        manifest=manifest,
                        support_type=support_type,
                        language=language,
                        chapters=chapters,
                        glossary=glossary,
                        settings_hash=settings_hash,
                        source_mtime_ns=source_mtime,
                    )
                    total_cost += cost
                    any_failure = any_failure or failed
        except PausedError:
            event_bus.publish(
                SupportGenerationFinished(
                    timestamp=_now(),
                    status=RunStatus.CANCELLED,
                    total_cost_usd=total_cost,
                )
            )
            return RunStatus.CANCELLED

        final = RunStatus.FAILED if any_failure else RunStatus.COMPLETED
        event_bus.publish(
            SupportGenerationFinished(
                timestamp=_now(), status=final, total_cost_usd=total_cost
            )
        )
        return final

    def _run_one(
        self,
        ctx: SupportContext,
        *,
        manifest: PedagogyManifest,
        support_type: SupportType,
        language: Language,
        chapters: tuple[Chapter, ...],
        glossary: tuple[Term, ...],
        settings_hash: str,
        source_mtime_ns: int | None,
    ) -> tuple[float, bool]:
        """Génère (ou skippe) un support pour une langue.

        Args:
            ctx: Contexte d'exécution.
            manifest: Manifeste de fraîcheur (mis à jour + persisté si succès).
            support_type: Type de support.
            language: Langue.
            chapters: Chapitres du doc consolidé.
            glossary: Glossaire de la langue.
            settings_hash: Hash courant des réglages.
            source_mtime_ns: mtime courant du doc source.

        Returns:
            ``(cost_usd, failed)`` : coût LLM et drapeau d'échec.
        """
        ctx.event_bus.publish(
            SupportStarted(
                timestamp=_now(), support_type=support_type, language=language
            )
        )
        json_path = artifact_json_path(ctx.pedagogy_dir, support_type, language)
        is_fresh = manifest.is_fresh(
            support_type,
            language,
            settings_hash=settings_hash,
            source_mtime_ns=source_mtime_ns,
        )
        if is_fresh and json_path.exists():
            ctx.event_bus.publish(
                SupportFinished(
                    timestamp=_now(),
                    support_type=support_type,
                    language=language,
                    status=PhaseStatus.SKIPPED,
                    cost_usd=0.0,
                    error=None,
                )
            )
            return 0.0, False

        try:
            artifact = self._registry.get(support_type).generate(
                ctx, language=language, chapters=chapters, glossary=glossary
            )
            self._write_artifact(ctx, artifact)
            manifest.record(
                support_type,
                language,
                settings_hash=settings_hash,
                source_mtime_ns=source_mtime_ns,
            )
            write_manifest(ctx.artifacts, ctx.pedagogy_dir, manifest)
            ctx.event_bus.publish(
                SupportFinished(
                    timestamp=_now(),
                    support_type=support_type,
                    language=language,
                    status=PhaseStatus.SUCCEEDED,
                    cost_usd=artifact.cost_usd,
                    error=None,
                )
            )
            return artifact.cost_usd, False
        except Fahmi2Error as exc:
            ctx.event_bus.publish(
                SupportFinished(
                    timestamp=_now(),
                    support_type=support_type,
                    language=language,
                    status=PhaseStatus.FAILED,
                    cost_usd=0.0,
                    error=ErrorInfo.from_exception(exc),
                )
            )
            return 0.0, True

    def _write_artifact(self, ctx: SupportContext, artifact: SupportArtifact) -> None:
        """Écrit l'artefact (JSON + Markdown) sous ``pedagogy/``.

        Args:
            ctx: Contexte (dossier pédagogie + store).
            artifact: Artefact à persister.
        """
        json_path = artifact_json_path(
            ctx.pedagogy_dir, artifact.support_type, artifact.language
        )
        md_path = artifact_markdown_path(
            ctx.pedagogy_dir, artifact.support_type, artifact.language
        )
        ctx.artifacts.write_json_atomic(json_path, serialize_artifact(artifact))
        ctx.artifacts.write_text_atomic(md_path, artifact.rendered_markdown)
        if artifact.correction_markdown is not None:
            correction_path = artifact_correction_markdown_path(
                ctx.pedagogy_dir, artifact.support_type, artifact.language
            )
            ctx.artifacts.write_text_atomic(
                correction_path, artifact.correction_markdown
            )

    def _build_context(
        self,
        project: Project,
        pedagogy: PedagogySettings,
        pause_token: PauseToken,
        event_bus: EventBus[PedagogyEvent],
    ) -> SupportContext:
        """Construit le ``SupportContext`` (dépendances stables).

        Args:
            project: Projet.
            pedagogy: Réglages pédagogie (non None).
            pause_token: Jeton de pause.
            event_bus: Bus d'événements.

        Returns:
            Le contexte d'exécution.
        """
        generation_output_dir = (
            project.workspace_folder
            / GENERATION_WORKSPACE_SUBDIR
            / GENERATION_OUTPUT_SUBDIR
        )
        return SupportContext(
            pedagogy=pedagogy,
            generation_output_dir=generation_output_dir,
            pedagogy_dir=project.workspace_folder / PEDAGOGY_WORKSPACE_SUBDIR,
            llm_provider=self._llm_provider,
            prompts=self._prompts,
            artifacts=self._artifacts,
            event_bus=event_bus,
            pause_token=pause_token,
            retry_policy=self._retry_policy,
        )

    def _load_glossary(self, project: Project, language: Language) -> tuple[Term, ...]:
        """Charge le glossaire de la langue depuis le dernier run COMPLETED.

        Args:
            project: Projet.
            language: Langue.

        Returns:
            Les termes (vide si aucun run COMPLETED).
        """
        run = self._project_service.get_last_completed_run(project.id)
        if run is None:
            return ()
        return tuple(self._state.list_glossary_terms(run.id, language))


def _ceiling_reached(pedagogy: PedagogySettings, total_cost: float) -> bool:
    """Indique si le plafond de coût est atteint (frontière sûre).

    Args:
        pedagogy: Réglages pédagogie (plafond éventuel).
        total_cost: Coût cumulé jusqu'ici.

    Returns:
        ``True`` si un plafond est défini et atteint/dépassé.
    """
    ceiling = pedagogy.cost_ceiling_usd
    return ceiling is not None and total_cost >= ceiling


def _now() -> datetime:
    """Horodatage UTC courant.

    Returns:
        ``datetime`` UTC aware.
    """
    return datetime.now(tz=UTC)
