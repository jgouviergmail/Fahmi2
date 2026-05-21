"""Tests de EventBus."""

from datetime import UTC, datetime

from fahmi2.domain.enums import RunStatus
from fahmi2.domain.ids import RunId
from fahmi2.pipeline.event_bus import EventBus
from fahmi2.pipeline.events import PipelineEvent, RunFinished, RunStarted


def _started(run_id: RunId) -> RunStarted:
    return RunStarted(timestamp=datetime.now(tz=UTC), run_id=run_id)


def _finished(run_id: RunId, status: RunStatus = RunStatus.COMPLETED) -> RunFinished:
    return RunFinished(
        timestamp=datetime.now(tz=UTC), run_id=run_id, final_status=status
    )


def test_publish_distributes_to_subscribers() -> None:
    bus: EventBus[PipelineEvent] = EventBus()
    received: list[PipelineEvent] = []
    bus.subscribe(received.append)

    rid = RunId.new()
    bus.publish(_started(rid))
    bus.publish(_finished(rid))

    assert len(received) == 2
    assert isinstance(received[0], RunStarted)
    assert isinstance(received[1], RunFinished)


def test_multiple_handlers_each_receive_events() -> None:
    bus: EventBus[PipelineEvent] = EventBus()
    h1: list[PipelineEvent] = []
    h2: list[PipelineEvent] = []
    bus.subscribe(h1.append)
    bus.subscribe(h2.append)

    rid = RunId.new()
    bus.publish(_started(rid))
    assert len(h1) == 1
    assert len(h2) == 1


def test_unsubscribe_stops_receiving() -> None:
    bus: EventBus[PipelineEvent] = EventBus()
    received: list[PipelineEvent] = []
    unsubscribe = bus.subscribe(received.append)
    rid = RunId.new()
    bus.publish(_started(rid))
    unsubscribe()
    bus.publish(_finished(rid))
    assert len(received) == 1


def test_handler_exception_does_not_break_chain() -> None:
    bus: EventBus[PipelineEvent] = EventBus()
    h2_received: list[PipelineEvent] = []

    def _boom(_event: PipelineEvent) -> None:
        raise RuntimeError("handler failed")

    bus.subscribe(_boom)
    bus.subscribe(h2_received.append)
    bus.publish(_started(RunId.new()))
    assert len(h2_received) == 1


def test_unsubscribe_twice_is_idempotent() -> None:
    bus: EventBus[PipelineEvent] = EventBus()
    unsubscribe = bus.subscribe(lambda _: None)
    unsubscribe()
    unsubscribe()
