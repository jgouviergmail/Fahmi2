"""``VisualsOrchestrator`` — service applicatif pilotant la génération des visuels.

Orchestrateur **léger** (modèle Pédagogie, sans ``PipelineEngine``). Lit les livrables
de la Génération **sur disque**, **extrait la structure une seule fois** (langue de
structure) — graphe (extraction → résolution → communautés → reports → idea-chains) et
diagrammes — puis, **par langue latine** disponible, localise la structure et rend les
deux pages HTML autonomes. Gère manifeste de fraîcheur (reprise *coarse*), ``run_state``,
plafond de coût best-effort et parallélisme par langue. Pause/annulation aux frontières.
"""

from __future__ import annotations

import threading
from datetime import UTC, datetime
from pathlib import Path

from fahmi2.core.concurrency import map_bounded
from fahmi2.core.concurrency.pause_token import PauseToken
from fahmi2.core.errors.error_info import ErrorInfo
from fahmi2.core.errors.exceptions import ConfigError, Fahmi2Error, PausedError
from fahmi2.core.errors.severity import Severity
from fahmi2.core.retry.policy import RetryPolicy
from fahmi2.domain.enums import Language, PhaseStatus, RunStatus
from fahmi2.domain.generation import (
    GENERATION_OUTPUT_SUBDIR,
    GENERATION_WORKSPACE_SUBDIR,
)
from fahmi2.domain.glossary import Term, localize_glossary_terms
from fahmi2.domain.project import Project
from fahmi2.domain.visuals import (
    VISUALS_OUTPUT_SUBDIR,
    VISUALS_WORKSPACE_SUBDIR,
    DiagramBoard,
    KnowledgeGraph,
    VisualsSettings,
    diagrams_filename,
    knowledge_map_filename,
)
from fahmi2.infra.embeddings.interface import EmbeddingProvider
from fahmi2.infra.export.diagram_board_html import render_diagram_board_html
from fahmi2.infra.export.knowledge_map_html import render_knowledge_map_html
from fahmi2.infra.llm.interface import LLMProvider
from fahmi2.infra.prompts.loader import PromptLoader
from fahmi2.infra.storage.feature_run_state import (
    FeatureRunState,
    read_run_state,
    write_run_state,
)
from fahmi2.infra.storage.fs_artifacts import FsArtifactStore
from fahmi2.pipeline.event_bus import EventBus
from fahmi2.visuals._pruning import prune_knowledge_graph
from fahmi2.visuals.community import assemble_graph
from fahmi2.visuals.events import (
    VisualsEvent,
    VisualsGenerationFinished,
    VisualsGenerationStarted,
    VisualsLanguageFinished,
    VisualsLanguageStarted,
    VisualsStructureFinished,
    VisualsStructureStarted,
)
from fahmi2.visuals.extractors._base import VisualsContext
from fahmi2.visuals.extractors.community_reporter import generate_community_reports
from fahmi2.visuals.extractors.diagram_author import extract_diagrams
from fahmi2.visuals.extractors.entity_resolver import resolve_graph
from fahmi2.visuals.extractors.graph_extractor import extract_graph
from fahmi2.visuals.extractors.idea_chains import generate_idea_chains
from fahmi2.visuals.extractors.label_translator import localize_board, localize_graph
from fahmi2.visuals.manifest import (
    VisualsManifest,
    compute_settings_hash,
    read_manifest,
    write_manifest,
)
from fahmi2.visuals.sources import (
    available_visuals_languages,
    glossary_master_mtime_ns,
    load_glossary_master_terms,
    load_text_units,
    outputs_present,
    source_mtime_ns,
    structure_language,
)

#: Statuts d'exécution antérieurs considérés comme « reprise utile » : on rebase le
#: coût cumulé sur l'historique persisté plutôt que de repartir de 0. Symétrique de
#: ``_RESUMABLE_PEDAGOGY_STATUSES`` (``app/supports_orchestrator``) et
#: ``_RESUMABLE_RUN_STATUSES`` (``app/run_orchestrator``).
#: - ``FAILED`` : au moins une langue a échoué.
#: - ``PAUSED`` : plafond de coût atteint (arrêt à une frontière sûre).
#: - ``RUNNING`` : crash de l'app pendant un run (état resté coincé en RUNNING sur
#:   disque) — on considère le run reprenable.
#: Hors ce set (CREATED / COMPLETED / CANCELLED / aucun état) : nouvel agrégat à 0.
_RESUMABLE_VISUALS_STATUSES: frozenset[RunStatus] = frozenset(
    {RunStatus.FAILED, RunStatus.PAUSED, RunStatus.RUNNING}
)


def _now() -> datetime:
    """Horodatage UTC courant.

    Returns:
        ``datetime`` UTC aware.
    """
    return datetime.now(tz=UTC)


def _ceiling_reached(settings: VisualsSettings, total_cost: float) -> bool:
    """Indique si le plafond de coût est atteint.

    Args:
        settings: Réglages (plafond éventuel).
        total_cost: Coût cumulé.

    Returns:
        ``True`` si un plafond est défini et atteint/dépassé.
    """
    ceiling = settings.cost_ceiling_usd
    return ceiling is not None and total_cost >= ceiling


class VisualsOrchestrator:
    """Pilote la génération des visualisations d'un projet."""

    def __init__(
        self,
        *,
        artifacts: FsArtifactStore,
        llm_provider: LLMProvider,
        prompts: PromptLoader,
        retry_policy: RetryPolicy,
        embedding_provider: EmbeddingProvider | None,
    ) -> None:
        """Construit l'orchestrateur.

        Args:
            artifacts: Écriture atomique d'artefacts.
            llm_provider: Provider LLM.
            prompts: Loader de prompts.
            retry_policy: Politique de retry des appels LLM.
            embedding_provider: Fournisseur d'embeddings pour la résolution d'entités,
                ou ``None`` (fallback AUTO par libellé — pas de clé OpenAI).
        """
        self._artifacts = artifacts
        self._llm_provider = llm_provider
        self._prompts = prompts
        self._retry_policy = retry_policy
        self._embedding_provider = embedding_provider

    def generate(
        self,
        project: Project,
        *,
        pause_token: PauseToken,
        event_bus: EventBus[VisualsEvent],
    ) -> RunStatus:
        """Génère les visualisations pour toutes les langues latines disponibles.

        Args:
            project: Projet (doit avoir ``visuals`` configuré).
            pause_token: Jeton coopératif pause/annulation.
            event_bus: Bus d'événements Visualisations.

        Returns:
            ``COMPLETED`` / ``FAILED`` / ``CANCELLED`` / ``PAUSED``.

        Raises:
            ConfigError: Si la fonctionnalité Visualisations n'est pas configurée.
        """
        settings = project.visuals
        if settings is None:
            raise ConfigError(
                code="VISUALS.NOT_CONFIGURED",
                user_message="La fonctionnalité Visualisations n'est pas configurée.",
                severity=Severity.ERROR,
                technical_details={"project_id": project.id.value},
            )
        output_dir = (
            project.workspace_folder
            / GENERATION_WORKSPACE_SUBDIR
            / GENERATION_OUTPUT_SUBDIR
        )
        generation_dir = project.workspace_folder / GENERATION_WORKSPACE_SUBDIR
        visuals_dir = project.workspace_folder / VISUALS_WORKSPACE_SUBDIR
        ctx = VisualsContext(
            settings=settings,
            llm_provider=self._llm_provider,
            prompts=self._prompts,
            event_bus=event_bus,
            pause_token=pause_token,
            retry_policy=self._retry_policy,
        )

        settings_hash = compute_settings_hash(settings)
        manifest = read_manifest(visuals_dir)
        previous = read_run_state(visuals_dir)
        base_cost = (
            previous.total_cost_usd
            if previous is not None and previous.status in _RESUMABLE_VISUALS_STATUSES
            else 0.0
        )
        started_at = _now()
        self._write_state(visuals_dir, RunStatus.RUNNING, started_at, base_cost)
        event_bus.publish(VisualsGenerationStarted(timestamp=started_at))

        languages = available_visuals_languages(output_dir)
        if not languages:
            return self._finalize(
                event_bus, visuals_dir, RunStatus.COMPLETED, started_at, base_cost
            )

        glossary = load_glossary_master_terms(generation_dir)
        glossary_mtime = glossary_master_mtime_ns(generation_dir)
        structure_lang = self._structure_language(project, languages)
        structure_mtime = source_mtime_ns(output_dir, structure_lang)
        regenerate = self._is_complete(
            languages,
            manifest=manifest,
            settings=settings,
            visuals_dir=visuals_dir,
            output_dir=output_dir,
            settings_hash=settings_hash,
            structure_mtime=structure_mtime,
            glossary_mtime=glossary_mtime,
        )

        if _ceiling_reached(settings, base_cost):
            return self._finalize(
                event_bus, visuals_dir, RunStatus.PAUSED, started_at, base_cost
            )
        event_bus.publish(VisualsStructureStarted(timestamp=_now()))
        try:
            graph_source, board_source, struct_cost = self._build_structure(
                ctx, structure_lang, output_dir, glossary
            )
        except PausedError:
            # Annulation pendant l'extraction de structure (hors map_bounded) :
            # PausedError est une sous-classe de Fahmi2Error, on la laisse donc
            # remonter ici pour rapporter CANCELLED plutôt qu'un FAILED erroné.
            return self._finalize(
                event_bus, visuals_dir, RunStatus.CANCELLED, started_at, base_cost
            )
        except Fahmi2Error:
            return self._finalize(
                event_bus, visuals_dir, RunStatus.FAILED, started_at, base_cost
            )
        event_bus.publish(VisualsStructureFinished(timestamp=_now()))
        return self._run_languages(
            ctx,
            languages,
            structure_lang=structure_lang,
            graph_source=graph_source,
            board_source=board_source,
            glossary=glossary,
            output_dir=output_dir,
            visuals_dir=visuals_dir,
            manifest=manifest,
            settings_hash=settings_hash,
            structure_mtime=structure_mtime,
            glossary_mtime=glossary_mtime,
            regenerate=regenerate,
            started_at=started_at,
            total_cost=base_cost + struct_cost,
        )

    def _run_languages(
        self,
        ctx: VisualsContext,
        languages: list[Language],
        *,
        structure_lang: Language,
        graph_source: KnowledgeGraph | None,
        board_source: DiagramBoard | None,
        glossary: tuple[Term, ...],
        output_dir: Path,
        visuals_dir: Path,
        manifest: VisualsManifest,
        settings_hash: str,
        structure_mtime: int | None,
        glossary_mtime: int | None,
        regenerate: bool,
        started_at: datetime,
        total_cost: float,
    ) -> RunStatus:
        """Localise + rend les livrables de chaque langue (en parallèle), puis finalise.

        Args:
            ctx: Contexte d'exécution.
            languages: Langues latines disponibles.
            structure_lang: Langue d'extraction de la structure.
            graph_source: Graphe source (ou ``None`` si Doc A désactivé).
            board_source: Board source (ou ``None`` si Doc B désactivé).
            glossary: Termes du glossaire master.
            output_dir: Dossier des livrables de génération.
            visuals_dir: Dossier de la fonctionnalité.
            manifest: Manifeste de fraîcheur (muté + persisté).
            settings_hash: Hash courant des réglages.
            structure_mtime: mtime du doc de structure.
            glossary_mtime: mtime du glossaire master.
            regenerate: Régénérer (ensemble complet) ou reprendre (incomplet).
            started_at: Horodatage de démarrage.
            total_cost: Coût cumulé après la structure.

        Returns:
            Le statut final (``COMPLETED`` / ``FAILED`` / ``CANCELLED`` / ``PAUSED``).
        """
        settings = ctx.settings
        manifest_lock = threading.Lock()
        cost_lock = threading.Lock()
        cost_state = {"total": total_cost}

        def _run_lang(language: Language) -> tuple[bool, bool]:
            """Produit les livrables d'une langue. Retourne (échec, plafond)."""
            if settings.cost_ceiling_usd is not None:
                with cost_lock:
                    if _ceiling_reached(settings, cost_state["total"]):
                        return False, True
            cost, failed = self._produce_language(
                ctx,
                language,
                structure_lang=structure_lang,
                graph_source=graph_source,
                board_source=board_source,
                glossary=glossary,
                output_dir=output_dir,
                visuals_dir=visuals_dir,
                manifest=manifest,
                manifest_lock=manifest_lock,
                settings_hash=settings_hash,
                structure_mtime=structure_mtime,
                glossary_mtime=glossary_mtime,
                regenerate=regenerate,
            )
            with cost_lock:
                cost_state["total"] += cost
            return failed, False

        try:
            outcomes = map_bounded(
                _run_lang,
                languages,
                max_workers=settings.llm_workers,
                pause_token=ctx.pause_token,
            )
        except PausedError:
            return self._finalize(
                ctx.event_bus, visuals_dir, RunStatus.CANCELLED, started_at,
                cost_state["total"],
            )

        if any(ceiling for _, ceiling in outcomes):
            final = RunStatus.PAUSED
        elif any(failed for failed, _ in outcomes):
            final = RunStatus.FAILED
        else:
            final = RunStatus.COMPLETED
        return self._finalize(
            ctx.event_bus, visuals_dir, final, started_at, cost_state["total"]
        )

    def _structure_language(
        self, project: Project, languages: list[Language]
    ) -> Language:
        """Choisit la langue d'extraction de la structure (``languages`` non vide).

        Args:
            project: Projet.
            languages: Langues latines disponibles (non vide).

        Returns:
            La langue de structure.
        """
        source = (
            project.generation.source_language
            if project.generation is not None
            else None
        )
        chosen = structure_language(source, languages)
        assert chosen is not None  # garanti : ``languages`` non vide  # noqa: S101
        return chosen

    def _build_structure(
        self,
        ctx: VisualsContext,
        structure_lang: Language,
        output_dir: Path,
        glossary: tuple[Term, ...],
    ) -> tuple[KnowledgeGraph | None, DiagramBoard | None, float]:
        """Extrait la structure (graphe + diagrammes) une fois, en langue de structure.

        Args:
            ctx: Contexte d'exécution.
            structure_lang: Langue d'extraction.
            output_dir: Dossier des livrables de génération.
            glossary: Termes du glossaire master.

        Returns:
            ``(graphe | None, board | None, coût)`` — ``None`` si la production du
            livrable correspondant est désactivée.
        """
        units = load_text_units(output_dir, structure_lang)
        glossary_struct = localize_glossary_terms(glossary, structure_lang)
        graph: KnowledgeGraph | None = None
        board: DiagramBoard | None = None
        cost = 0.0
        if ctx.settings.produce_knowledge_map:
            extraction = extract_graph(
                ctx, language=structure_lang, units=units, glossary=glossary_struct
            )
            cost += extraction.total_cost_usd
            nodes, edges = resolve_graph(
                extraction,
                glossary=glossary_struct,
                units=units,
                embedding_provider=self._embedding_provider,
            )
            # Le coût des embeddings de résolution d'entités (appel unique par run)
            # est porté par le provider : on l'agrège au total (cf. pattern Dialogue).
            if self._embedding_provider is not None:
                cost += self._embedding_provider.consumed_cost_usd()
            # Élagage par densité : la carte ne garde que les nœuds les plus
            # structurants (cf. _pruning) → communautés/rapports/idea-chains opèrent
            # sur le graphe réduit.
            nodes, edges = prune_knowledge_graph(
                nodes, edges, density=ctx.settings.density
            )
            graph = assemble_graph(nodes, edges, language=structure_lang)
            graph, report_cost = generate_community_reports(
                ctx, graph, language=structure_lang
            )
            graph, chain_cost = generate_idea_chains(
                ctx, graph, language=structure_lang
            )
            cost += report_cost + chain_cost
        if ctx.settings.produce_diagrams:
            diagrams = extract_diagrams(ctx, language=structure_lang, units=units)
            board = DiagramBoard(
                diagrams=diagrams.diagrams, language=structure_lang
            )
            cost += diagrams.total_cost_usd
        return graph, board, cost

    def _produce_language(
        self,
        ctx: VisualsContext,
        language: Language,
        *,
        structure_lang: Language,
        graph_source: KnowledgeGraph | None,
        board_source: DiagramBoard | None,
        glossary: tuple[Term, ...],
        output_dir: Path,
        visuals_dir: Path,
        manifest: VisualsManifest,
        manifest_lock: threading.Lock,
        settings_hash: str,
        structure_mtime: int | None,
        glossary_mtime: int | None,
        regenerate: bool,
    ) -> tuple[float, bool]:
        """Produit (ou skippe) les livrables HTML d'une langue.

        Args:
            ctx: Contexte d'exécution (LLM, prompts, retry, pause token, bus).
            language: Langue cible à produire.
            structure_lang: Langue d'extraction de la structure (saut de traduction si
                identique).
            graph_source: Graphe source à localiser, ou ``None`` si Doc A désactivé.
            board_source: Board source à localiser, ou ``None`` si Doc B désactivé.
            glossary: Termes du glossaire master (langue source).
            output_dir: Dossier des livrables de génération.
            visuals_dir: Dossier de la fonctionnalité (écriture du manifeste).
            manifest: Manifeste de fraîcheur (muté + persisté sous ``manifest_lock``).
            manifest_lock: Verrou protégeant les accès concurrents au manifeste.
            settings_hash: Hash courant des réglages.
            structure_mtime: mtime du doc de structure (entrée du manifeste).
            glossary_mtime: mtime du glossaire master (entrée du manifeste).
            regenerate: Si ``True``, ignore la fraîcheur et produit même si frais.

        Returns:
            ``(cost_usd, failed)``.
        """
        ctx.event_bus.publish(
            VisualsLanguageStarted(timestamp=_now(), language=language)
        )
        content_mtime = source_mtime_ns(output_dir, language)
        out_dir = visuals_dir / VISUALS_OUTPUT_SUBDIR
        with manifest_lock:
            fresh = manifest.is_fresh(
                language,
                settings_hash=settings_hash,
                structure_mtime_ns=structure_mtime,
                glossary_mtime_ns=glossary_mtime,
                content_mtime_ns=content_mtime,
            )
        if not regenerate and fresh and outputs_present(out_dir, language, ctx.settings):
            ctx.event_bus.publish(
                VisualsLanguageFinished(
                    timestamp=_now(), language=language,
                    status=PhaseStatus.SKIPPED, cost_usd=0.0, error=None,
                )
            )
            return 0.0, False
        try:
            cost = self._localize_and_write(
                ctx, language, structure_lang=structure_lang,
                graph_source=graph_source, board_source=board_source,
                glossary=glossary, output_dir=output_dir, out_dir=out_dir,
            )
            with manifest_lock:
                manifest.record(
                    language, settings_hash=settings_hash,
                    structure_mtime_ns=structure_mtime,
                    glossary_mtime_ns=glossary_mtime, content_mtime_ns=content_mtime,
                )
                write_manifest(self._artifacts, visuals_dir, manifest)
            ctx.event_bus.publish(
                VisualsLanguageFinished(
                    timestamp=_now(), language=language,
                    status=PhaseStatus.SUCCEEDED, cost_usd=cost, error=None,
                )
            )
            return cost, False
        except Fahmi2Error as exc:
            ctx.event_bus.publish(
                VisualsLanguageFinished(
                    timestamp=_now(), language=language, status=PhaseStatus.FAILED,
                    cost_usd=0.0, error=ErrorInfo.from_exception(exc),
                )
            )
            return 0.0, True

    def _localize_and_write(
        self,
        ctx: VisualsContext,
        language: Language,
        *,
        structure_lang: Language,
        graph_source: KnowledgeGraph | None,
        board_source: DiagramBoard | None,
        glossary: tuple[Term, ...],
        output_dir: Path,
        out_dir: Path,
    ) -> float:
        """Localise la structure dans une langue et écrit les HTML.

        Args:
            ctx: Contexte d'exécution (LLM, prompts, retry, pause token).
            language: Langue cible de la localisation.
            structure_lang: Langue d'extraction de la structure source.
            graph_source: Graphe source à localiser, ou ``None`` si Doc A désactivé.
            board_source: Board source à localiser, ou ``None`` si Doc B désactivé.
            glossary: Termes du glossaire master (langue source).
            output_dir: Dossier des livrables de génération (chargement des unités).
            out_dir: Dossier de sortie des HTML (``visuals/output``).

        Returns:
            Le coût LLM cumulé (USD) de la localisation (0.0 si ``language`` est la
            langue de structure : aucun appel de traduction).

        Raises:
            Fahmi2Error: Si un appel LLM de localisation échoue après les retries.
        """
        units = load_text_units(output_dir, language)
        cost = 0.0
        if graph_source is not None:
            if language == structure_lang:
                graph = graph_source
            else:
                graph, graph_cost = localize_graph(
                    ctx, graph_source, target_language=language,
                    glossary=glossary, target_units=units,
                )
                cost += graph_cost
            self._artifacts.write_text_atomic(
                out_dir / knowledge_map_filename(language),
                render_knowledge_map_html(graph),
            )
        if board_source is not None:
            if language == structure_lang:
                board = board_source
            else:
                board, board_cost = localize_board(
                    ctx, board_source, target_language=language, target_units=units
                )
                cost += board_cost
            self._artifacts.write_text_atomic(
                out_dir / diagrams_filename(language),
                render_diagram_board_html(board),
            )
        return cost

    def _is_complete(
        self,
        languages: list[Language],
        *,
        manifest: VisualsManifest,
        settings: VisualsSettings,
        visuals_dir: Path,
        output_dir: Path,
        settings_hash: str,
        structure_mtime: int | None,
        glossary_mtime: int | None,
    ) -> bool:
        """Indique si toutes les langues sont présentes et fraîches.

        Args:
            languages: Langues latines disponibles.
            manifest: Manifeste de fraîcheur.
            settings: Réglages.
            visuals_dir: Dossier de la fonctionnalité.
            output_dir: Dossier des livrables de génération.
            settings_hash: Hash courant des réglages.
            structure_mtime: mtime du doc de structure.
            glossary_mtime: mtime du glossaire master.

        Returns:
            ``True`` si chaque langue a ses livrables présents et frais.
        """
        out_dir = visuals_dir / VISUALS_OUTPUT_SUBDIR
        for language in languages:
            content_mtime = source_mtime_ns(output_dir, language)
            if not manifest.is_fresh(
                language, settings_hash=settings_hash,
                structure_mtime_ns=structure_mtime, glossary_mtime_ns=glossary_mtime,
                content_mtime_ns=content_mtime,
            ):
                return False
            if not outputs_present(out_dir, language, settings):
                return False
        return True

    def _write_state(
        self, visuals_dir: Path, status: RunStatus, started_at: datetime, cost: float
    ) -> None:
        """Persiste l'état d'exécution.

        Args:
            visuals_dir: Dossier de la fonctionnalité.
            status: Statut.
            started_at: Horodatage de démarrage.
            cost: Coût cumulé.
        """
        write_run_state(
            self._artifacts,
            visuals_dir,
            FeatureRunState(
                status=status, started_at=started_at,
                finished_at=None if status is RunStatus.RUNNING else _now(),
                total_cost_usd=cost,
            ),
        )

    def _finalize(
        self,
        event_bus: EventBus[VisualsEvent],
        visuals_dir: Path,
        status: RunStatus,
        started_at: datetime,
        total_cost: float,
    ) -> RunStatus:
        """Persiste l'état final et émet l'événement de fin.

        Args:
            event_bus: Bus d'événements.
            visuals_dir: Dossier de la fonctionnalité.
            status: Statut final.
            started_at: Horodatage de démarrage.
            total_cost: Coût cumulé.

        Returns:
            Le ``status`` (pour ``return self._finalize(...)``).
        """
        self._write_state(visuals_dir, status, started_at, total_cost)
        event_bus.publish(
            VisualsGenerationFinished(
                timestamp=_now(), status=status, total_cost_usd=total_cost
            )
        )
        return status
