"""``PipelineEngine`` — moteur d'exécution pur du pipeline.

Itère sur les phases enregistrées dans ``PhaseRegistry`` (dans l'ordre
canonique), pour chaque phase :

- Vérifie le checkpoint SQLite (``SUCCEEDED`` → ``SKIPPED``).
- Pour les phases per-source, itère sur les sources du run ; pour les phases
  batch, exécute une seule fois.
- Invoque le handler avec retry policy (mapping erreur → décision).
- Persiste l'exécution dans SQLite.
- Émet des événements (``PhaseStarted``, ``PhaseFinished``, ``RetryAttempt``).
- Respecte le ``PauseToken`` aux frontières sûres.

Ce composant ne connaît pas la notion de "Projet utilisateur" : il opère sur
un ``Run`` déjà persisté. Le ``RunOrchestrator`` (app/) lui passe le ``Run``
+ ``PhaseContext`` et écoute les événements.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fahmi2.core.concurrency import map_bounded
from fahmi2.core.errors.error_info import ErrorInfo
from fahmi2.core.errors.exceptions import (
    BudgetExceededError,
    Fahmi2Error,
    PausedError,
)
from fahmi2.core.retry.classification import default_classify
from fahmi2.core.retry.policy import RetryDecision, RetryPolicy
from fahmi2.core.retry.runner import with_retry
from fahmi2.domain.enums import PhaseStatus, RunStatus
from fahmi2.domain.phase import PhaseExecution
from fahmi2.domain.source import SourceExecution
from fahmi2.pipeline.events import (
    PhaseFinished,
    PhaseStarted,
    RetryAttempt,
    RunFinished,
    RunStarted,
)
from fahmi2.pipeline.phase_handler import PhaseContext, PhaseHandler
from fahmi2.pipeline.phase_registry import PhaseRegistry


class PipelineEngine:
    """Moteur d'exécution des phases du pipeline."""

    def __init__(self, *, registry: PhaseRegistry, retry_policy: RetryPolicy) -> None:
        """Construit le moteur.

        Args:
            registry: Registre des handlers.
            retry_policy: Politique de retry à appliquer.
        """
        self._registry = registry
        self._retry_policy = retry_policy

    def execute(self, ctx: PhaseContext) -> RunStatus:
        """Exécute le pipeline complet pour le ``Run`` porté par ``ctx``.

        Args:
            ctx: Contexte d'exécution complet.

        Returns:
            Le ``RunStatus`` final atteint (``COMPLETED``, ``FAILED``,
            ``CANCELLED``, ou ``PAUSED``).
        """
        run = ctx.run
        ctx.event_bus.publish(RunStarted(timestamp=_now(), run_id=run.id))

        final_status = RunStatus.COMPLETED
        try:
            for handler in self._registry.ordered_handlers():
                self._raise_if_paused_or_cancelled(ctx)
                self._execute_phase(handler, ctx)
        except PausedError as exc:
            final_status = (
                RunStatus.CANCELLED
                if exc.code == "RUN.CANCELLED"
                else RunStatus.PAUSED
            )
        except BudgetExceededError:
            final_status = RunStatus.PAUSED
        except Fahmi2Error:
            final_status = RunStatus.FAILED

        ctx.event_bus.publish(
            RunFinished(timestamp=_now(), run_id=run.id, final_status=final_status)
        )
        return final_status

    def _execute_phase(self, handler: PhaseHandler, ctx: PhaseContext) -> None:
        """Exécute une phase complète (toutes ses sources si per-source).

        Args:
            handler: Handler de la phase.
            ctx: Contexte.
        """
        if handler.is_per_source:
            workers = handler.max_parallel_workers(ctx)
            map_bounded(
                lambda source: self._execute_one(handler, ctx, source=source),
                ctx.run.sources,
                max_workers=workers,
                pause_token=ctx.pause_token,
            )
        else:
            self._execute_one(handler, ctx, source=None)

    def _execute_one(
        self,
        handler: PhaseHandler,
        ctx: PhaseContext,
        *,
        source: SourceExecution | None,
    ) -> None:
        """Exécute une occurrence (source ou batch) avec checkpoint + retry + events.

        Args:
            handler: Handler.
            ctx: Contexte.
            source: Source associée (None pour batch).
        """
        source_id = source.source_id if source is not None else None
        current_status = ctx.state.get_phase_status(
            ctx.run.id, handler.phase_id, source_id=source_id
        )
        if current_status is PhaseStatus.SUCCEEDED:
            skipped = PhaseExecution(
                phase_id=handler.phase_id,
                status=PhaseStatus.SKIPPED,
                started_at=_now(),
                finished_at=_now(),
            )
            ctx.state.upsert_phase_execution(ctx.run.id, skipped, source_id=source_id)
            ctx.event_bus.publish(
                PhaseFinished(
                    timestamp=_now(),
                    run_id=ctx.run.id,
                    phase_id=handler.phase_id,
                    source_id=source_id,
                    final_status=PhaseStatus.SKIPPED,
                    cost_usd=0.0,
                    error=None,
                )
            )
            return

        ctx.event_bus.publish(
            PhaseStarted(
                timestamp=_now(),
                run_id=ctx.run.id,
                phase_id=handler.phase_id,
                source_id=source_id,
            )
        )

        running = PhaseExecution(
            phase_id=handler.phase_id,
            status=PhaseStatus.RUNNING,
            started_at=_now(),
        )
        ctx.state.upsert_phase_execution(ctx.run.id, running, source_id=source_id)

        attempts = {"n": 0}

        def _try_once() -> PhaseExecution:
            attempts["n"] += 1
            try:
                return handler.execute(ctx, source=source)
            except Fahmi2Error as exc:
                if default_classify(exc) is RetryDecision.RETRY:
                    ctx.event_bus.publish(
                        RetryAttempt(
                            timestamp=_now(),
                            run_id=ctx.run.id,
                            phase_id=handler.phase_id,
                            source_id=source_id,
                            attempt=attempts["n"],
                            delay_seconds=self._retry_policy.compute_delay(
                                attempt=attempts["n"]
                            ),
                            error=ErrorInfo.from_exception(exc),
                        )
                    )
                raise

        try:
            result = with_retry(
                _try_once,
                policy=self._retry_policy,
                classify=default_classify,
            )
        except Fahmi2Error as exc:
            error_info = ErrorInfo.from_exception(exc)
            failed = PhaseExecution(
                phase_id=handler.phase_id,
                status=PhaseStatus.FAILED,
                started_at=running.started_at,
                finished_at=_now(),
                retry_count=attempts["n"] - 1,
                error=error_info,
            )
            ctx.state.upsert_phase_execution(ctx.run.id, failed, source_id=source_id)
            ctx.event_bus.publish(
                PhaseFinished(
                    timestamp=_now(),
                    run_id=ctx.run.id,
                    phase_id=handler.phase_id,
                    source_id=source_id,
                    final_status=PhaseStatus.FAILED,
                    cost_usd=0.0,
                    error=error_info,
                )
            )
            raise

        finalized = PhaseExecution(
            phase_id=result.phase_id,
            status=result.status,
            started_at=result.started_at or running.started_at,
            finished_at=result.finished_at or _now(),
            artifact_path=result.artifact_path,
            retry_count=attempts["n"] - 1,
            cost_usd=result.cost_usd,
            error=result.error,
        )
        ctx.state.upsert_phase_execution(ctx.run.id, finalized, source_id=source_id)
        ctx.event_bus.publish(
            PhaseFinished(
                timestamp=_now(),
                run_id=ctx.run.id,
                phase_id=handler.phase_id,
                source_id=source_id,
                final_status=finalized.status,
                cost_usd=finalized.cost_usd,
                error=finalized.error,
            )
        )

    def _raise_if_paused_or_cancelled(self, ctx: PhaseContext) -> None:
        """Frontière sûre : block si pause, raise si cancel.

        Args:
            ctx: Contexte (porteur du ``PauseToken``).
        """
        ctx.pause_token.raise_if_cancelled()
        if ctx.pause_token.is_paused():
            ctx.pause_token.wait_if_paused(timeout=None)
            ctx.pause_token.raise_if_cancelled()


def _now() -> datetime:
    """Retourne l'horodatage UTC courant.

    Returns:
        ``datetime`` UTC aware.
    """
    return datetime.now(tz=UTC)
