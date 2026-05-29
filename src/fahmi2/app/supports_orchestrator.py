"""``SupportsOrchestrator`` — service applicatif pilotant la génération des supports.

Orchestrateur dédié **léger** (design §2.1) : ne réutilise pas le ``PipelineEngine``.
Pour chaque langue cible, charge les entrants **sur disque** (chapitres du doc
consolidé d'une langue de contenu résolue + glossaire master), itère les supports
sélectionnés dans l'ordre canonique du registre, invoque le générateur (qui rédige
dans la langue cible), écrit les artefacts (JSON + Markdown), met à jour le
manifeste de fraîcheur (reprise coarse) et émet les événements pédagogie. Gère
pause/annulation aux frontières sûres (entre supports).
"""

from __future__ import annotations

import threading
from datetime import UTC, datetime

from fahmi2.core.concurrency import map_bounded
from fahmi2.core.concurrency.pause_token import PauseToken
from fahmi2.core.errors.error_info import ErrorInfo
from fahmi2.core.errors.exceptions import ConfigError, Fahmi2Error, PausedError
from fahmi2.core.errors.severity import Severity
from fahmi2.core.retry.policy import RetryPolicy
from fahmi2.domain.enums import Language, PhaseStatus, RunStatus, SupportType
from fahmi2.domain.generation import (
    GENERATION_OUTPUT_SUBDIR,
    GENERATION_WORKSPACE_SUBDIR,
)
from fahmi2.domain.glossary import Term, localize_glossary_terms
from fahmi2.domain.pedagogy import PEDAGOGY_WORKSPACE_SUBDIR, PedagogySettings
from fahmi2.domain.project import Project
from fahmi2.domain.supports import SupportArtifact
from fahmi2.infra.llm.interface import LLMProvider
from fahmi2.infra.prompts.loader import PromptLoader
from fahmi2.infra.storage.fs_artifacts import FsArtifactStore
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
from fahmi2.pedagogy.run_state import PedagogyRunState, read_run_state, write_run_state
from fahmi2.pedagogy.sources import (
    load_chapters,
    load_glossary_master_terms,
    resolve_content_language,
    source_mtime_ns,
)
from fahmi2.pedagogy.support_generator import SupportContext
from fahmi2.pedagogy.support_registry import SupportGeneratorRegistry
from fahmi2.pipeline.event_bus import EventBus

#: Statuts d'exécution antérieurs considérés comme « reprise utile » : on
#: rebase le coût cumulé sur l'historique persisté plutôt que de repartir à 0.
#: Symétrique de ``_RESUMABLE_RUN_STATUSES`` dans ``app/run_orchestrator``.
#: - ``FAILED`` : au moins un support a échoué.
#: - ``PAUSED`` : plafond de coût atteint (arrêt safe-boundary).
#: - ``RUNNING`` : crash app pendant un Run (état resté coincé en RUNNING sur
#:   disque), on considère le Run reprenable.
#: Hors ce set (CREATED / COMPLETED / CANCELLED / pas d'état du tout) : on
#: démarre un nouvel agrégat à 0.
_RESUMABLE_PEDAGOGY_STATUSES: frozenset[RunStatus] = frozenset(
    {RunStatus.FAILED, RunStatus.PAUSED, RunStatus.RUNNING}
)


class SupportsOrchestrator:
    """Pilote la génération des supports pédagogiques d'un projet."""

    def __init__(
        self,
        *,
        registry: SupportGeneratorRegistry,
        artifacts: FsArtifactStore,
        llm_provider: LLMProvider,
        prompts: PromptLoader,
        retry_policy: RetryPolicy,
    ) -> None:
        """Construit l'orchestrateur.

        Le glossaire et le document consolidé sont lus **sur disque** (comme le
        pipeline) ; l'orchestrateur n'a donc pas besoin d'accès SQLite.

        Args:
            registry: Registre des générateurs.
            artifacts: Écriture atomique d'artefacts.
            llm_provider: Provider LLM (générateurs LLM).
            prompts: Loader de prompts.
            retry_policy: Politique de retry des appels LLM des générateurs.
        """
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
            ``COMPLETED`` (succès), ``FAILED`` (≥1 support échoué),
            ``CANCELLED`` (annulé par l'utilisateur) ou ``PAUSED`` (plafond de
            coût atteint : génération interrompue à une frontière sûre).

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
        # Base du coût cumulé : si la dernière exécution est dans un état
        # « reprise utile » (FAILED / PAUSED / RUNNING-orphan suite à un crash
        # app), on **part du total persisté** pour ne pas reset le coût
        # historique à zéro. Sinon (CREATED / COMPLETED / CANCELLED / pas
        # d'exécution précédente) on repart à 0 : nouvelle exécution.
        # Symétrique du fix engine côté Génération
        # (cf. ``_RESUMABLE_RUN_STATUSES`` dans ``app/run_orchestrator``) —
        # même cause fonctionnelle (perte du coût cumulé à la reprise), cause
        # technique distincte (la pédagogie n'utilise pas SQLite, le coût est
        # persisté dans ``pedagogy/run_state.json``).
        previous_state = read_run_state(ctx.pedagogy_dir)
        base_cost = (
            previous_state.total_cost_usd
            if previous_state is not None
            and previous_state.status in _RESUMABLE_PEDAGOGY_STATUSES
            else 0.0
        )
        started_at = _now()
        write_run_state(
            ctx.artifacts,
            ctx.pedagogy_dir,
            PedagogyRunState(
                status=RunStatus.RUNNING,
                started_at=started_at,
                finished_at=None,
                total_cost_usd=base_cost,
            ),
        )
        event_bus.publish(SupportGenerationStarted(timestamp=started_at))

        glossary = self._load_glossary(project)
        source_language = (
            project.generation.source_language
            if project.generation is not None
            else None
        )
        # Alignement sur la génération : un ensemble déjà complet (tous les
        # supports présents et frais) est **régénéré** (relance volontaire qui
        # écrase) ; un ensemble incomplet est **repris** (on garde les supports
        # frais et on génère le reste, ex. après un plafond atteint).
        regenerate = self._is_complete(
            ctx,
            pedagogy=pedagogy,
            manifest=manifest,
            settings_hash=settings_hash,
            source_language=source_language,
        )

        # Pré-chargement des entrants par langue (lecture disque + localisation hors
        # threads) : (mtime source, chapitres, glossaire localisé dans la langue de
        # contenu) résolus **une fois** par langue, réutilisés par chaque tâche.
        # Repli sur le glossaire master si aucune langue de contenu n'est résolue.
        per_language: dict[
            Language, tuple[int | None, tuple[Chapter, ...], tuple[Term, ...]]
        ] = {}
        for language in pedagogy.languages:
            content_lang = resolve_content_language(
                ctx.generation_output_dir, language, source_language
            )
            source_mtime = (
                source_mtime_ns(ctx.generation_output_dir, content_lang)
                if content_lang is not None
                else None
            )
            chapters = (
                load_chapters(ctx.generation_output_dir, content_lang)
                if content_lang is not None
                else ()
            )
            localized_glossary = (
                localize_glossary_terms(glossary, content_lang)
                if content_lang is not None
                else glossary
            )
            per_language[language] = (source_mtime, chapters, localized_glossary)

        # Unités indépendantes (langue × support), dérivées du registre :
        # ajouter/retirer un support est pris en compte sans toucher ce code.
        tasks: list[tuple[Language, SupportType]] = [
            (language, support_type)
            for language in pedagogy.languages
            for support_type in self._registry.canonical_order()
            if support_type in pedagogy.selected_supports
            and self._registry.has(support_type)
        ]

        manifest_lock = threading.Lock()
        cost_lock = threading.Lock()
        # Cumul démarré sur la base historique (cf. plus haut) — les coûts des
        # tâches de ce passage s'y ajoutent. Le plafond est évalué sur ce total
        # cumulé, pas seulement sur le passage courant.
        cost_state = {"total": base_cost}

        def _run_task(task: tuple[Language, SupportType]) -> tuple[float, bool, bool]:
            """Exécute une unité (langue, support). Retourne (coût, échec, plafond)."""
            language, support_type = task
            # Plafond best-effort : court-circuit si déjà atteint (léger
            # dépassement toléré par les tâches en vol — cf. design §10.2).
            if pedagogy.cost_ceiling_usd is not None:
                with cost_lock:
                    if _ceiling_reached(pedagogy, cost_state["total"]):
                        return 0.0, False, True
            source_mtime, chapters, localized_glossary = per_language[language]
            cost, failed = self._run_one(
                ctx,
                manifest=manifest,
                manifest_lock=manifest_lock,
                support_type=support_type,
                language=language,
                chapters=chapters,
                glossary=localized_glossary,
                settings_hash=settings_hash,
                source_mtime_ns=source_mtime,
                regenerate=regenerate,
            )
            with cost_lock:
                cost_state["total"] += cost
            return cost, failed, False

        try:
            outcomes = map_bounded(
                _run_task,
                tasks,
                max_workers=pedagogy.llm_workers,
                pause_token=pause_token,
            )
        except PausedError:
            return self._finalize_run(
                ctx,
                event_bus,
                status=RunStatus.CANCELLED,
                started_at=started_at,
                total_cost=cost_state["total"],
            )

        any_failure = any(failed for _, failed, _ in outcomes)
        ceiling_reached = any(skipped for _, _, skipped in outcomes)
        if ceiling_reached:
            final = RunStatus.PAUSED
        elif any_failure:
            final = RunStatus.FAILED
        else:
            final = RunStatus.COMPLETED
        return self._finalize_run(
            ctx,
            event_bus,
            status=final,
            started_at=started_at,
            total_cost=cost_state["total"],
        )

    def _finalize_run(
        self,
        ctx: SupportContext,
        event_bus: EventBus[PedagogyEvent],
        *,
        status: RunStatus,
        started_at: datetime,
        total_cost: float,
    ) -> RunStatus:
        """Persiste l'état final de l'exécution et émet l'événement de fin.

        Args:
            ctx: Contexte d'exécution (store + dossier pédagogie).
            event_bus: Bus d'événements pédagogie.
            status: Statut final (``COMPLETED`` / ``FAILED`` / ``CANCELLED`` /
                ``PAUSED``).
            started_at: Horodatage de démarrage de l'exécution.
            total_cost: Coût LLM cumulé.

        Returns:
            Le ``status`` (pour ``return self._finalize_run(...)``).
        """
        write_run_state(
            ctx.artifacts,
            ctx.pedagogy_dir,
            PedagogyRunState(
                status=status,
                started_at=started_at,
                finished_at=_now(),
                total_cost_usd=total_cost,
            ),
        )
        event_bus.publish(
            SupportGenerationFinished(
                timestamp=_now(), status=status, total_cost_usd=total_cost
            )
        )
        return status

    def _run_one(
        self,
        ctx: SupportContext,
        *,
        manifest: PedagogyManifest,
        manifest_lock: threading.Lock,
        support_type: SupportType,
        language: Language,
        chapters: tuple[Chapter, ...],
        glossary: tuple[Term, ...],
        settings_hash: str,
        source_mtime_ns: int | None,
        regenerate: bool,
    ) -> tuple[float, bool]:
        """Génère (ou skippe) un support pour une langue.

        Args:
            ctx: Contexte d'exécution.
            manifest: Manifeste de fraîcheur (mis à jour + persisté si succès).
            manifest_lock: Verrou sérialisant les accès concurrents au manifeste.
            support_type: Type de support.
            language: Langue.
            chapters: Chapitres du doc consolidé.
            glossary: Glossaire de la langue.
            settings_hash: Hash courant des réglages.
            source_mtime_ns: mtime courant du doc source.
            regenerate: Si ``True`` (ensemble complet → relance volontaire), régénère
                même un support frais ; si ``False`` (reprise), skippe les frais.

        Returns:
            ``(cost_usd, failed)`` : coût LLM et drapeau d'échec.
        """
        ctx.event_bus.publish(
            SupportStarted(
                timestamp=_now(), support_type=support_type, language=language
            )
        )
        json_path = artifact_json_path(ctx.pedagogy_dir, support_type, language)
        with manifest_lock:
            is_fresh = manifest.is_fresh(
                support_type,
                language,
                settings_hash=settings_hash,
                source_mtime_ns=source_mtime_ns,
            )
        if not regenerate and is_fresh and json_path.exists():
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
            with manifest_lock:
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

    def _is_complete(
        self,
        ctx: SupportContext,
        *,
        pedagogy: PedagogySettings,
        manifest: PedagogyManifest,
        settings_hash: str,
        source_language: Language | None,
    ) -> bool:
        """Indique si tous les supports sélectionnés × langues sont présents et frais.

        Sert à choisir, comme la génération, entre **régénération** (ensemble complet
        → relance volontaire qui écrase) et **reprise** (ensemble incomplet → garder
        les supports frais, générer le reste, ex. après un plafond atteint).

        Args:
            ctx: Contexte d'exécution.
            pedagogy: Réglages pédagogie.
            manifest: Manifeste de fraîcheur.
            settings_hash: Hash courant des réglages.
            source_language: Langue source de la génération (repli de contenu).

        Returns:
            ``True`` si chaque ``(support sélectionné, langue)`` a un artefact présent
            et frais ; ``False`` dès qu'un support manque ou est périmé.
        """
        for language in pedagogy.languages:
            content_lang = resolve_content_language(
                ctx.generation_output_dir, language, source_language
            )
            source_mtime = (
                source_mtime_ns(ctx.generation_output_dir, content_lang)
                if content_lang is not None
                else None
            )
            for support_type in self._registry.canonical_order():
                if support_type not in pedagogy.selected_supports:
                    continue
                if not self._registry.has(support_type):
                    continue
                json_path = artifact_json_path(
                    ctx.pedagogy_dir, support_type, language
                )
                if not json_path.exists():
                    return False
                if not manifest.is_fresh(
                    support_type,
                    language,
                    settings_hash=settings_hash,
                    source_mtime_ns=source_mtime,
                ):
                    return False
        return True

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

    def _load_glossary(self, project: Project) -> tuple[Term, ...]:
        """Charge le glossaire master (langue source) depuis le disque.

        Lit ``<workspace>/generation/glossary_master.json`` — comme le pipeline.
        Sert l'injection terminologique des prompts des générateurs LLM.

        Args:
            project: Projet.

        Returns:
            Les termes du glossaire master (vide si absent).
        """
        generation_dir = project.workspace_folder / GENERATION_WORKSPACE_SUBDIR
        return load_glossary_master_terms(generation_dir)


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
