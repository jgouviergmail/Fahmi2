"""Tests du PhaseRegistry."""

import pytest

from fahmi2.domain.enums import PhaseId, PhaseStatus
from fahmi2.domain.phase import PhaseExecution
from fahmi2.pipeline.phase_handler import PhaseContext, PhaseHandler
from fahmi2.pipeline.phase_registry import PhaseRegistry


class _FakeHandler(PhaseHandler):
    """Handler factice pour tester le registre."""

    def __init__(self, phase_id: PhaseId, per_video: bool = True) -> None:
        self._phase_id = phase_id
        self._per_video = per_video

    @property
    def phase_id(self) -> PhaseId:
        return self._phase_id

    @property
    def is_per_video(self) -> bool:
        return self._per_video

    def execute(self, ctx: PhaseContext, *, source: object | None) -> PhaseExecution:
        del ctx, source
        return PhaseExecution(
            phase_id=self._phase_id, status=PhaseStatus.SUCCEEDED
        )


def test_empty_registry() -> None:
    reg = PhaseRegistry()
    assert reg.ordered_handlers() == []
    assert not reg.has(PhaseId.STT)


def test_register_and_get() -> None:
    handler = _FakeHandler(PhaseId.STT)
    reg = PhaseRegistry([handler])
    assert reg.has(PhaseId.STT)
    assert reg.get(PhaseId.STT) is handler


def test_get_unknown_raises() -> None:
    reg = PhaseRegistry()
    with pytest.raises(KeyError):
        reg.get(PhaseId.STT)


def test_register_twice_raises() -> None:
    reg = PhaseRegistry([_FakeHandler(PhaseId.STT)])
    with pytest.raises(ValueError):
        reg.register(_FakeHandler(PhaseId.STT))


def test_ordered_handlers_respects_canonical_order() -> None:
    handlers = [
        _FakeHandler(PhaseId.CONSOLIDATION),
        _FakeHandler(PhaseId.STT),
        _FakeHandler(PhaseId.TRANSLATION),
    ]
    reg = PhaseRegistry(handlers)
    ordered = reg.ordered_handlers()
    assert [h.phase_id for h in ordered] == [
        PhaseId.STT,
        PhaseId.CONSOLIDATION,
        PhaseId.TRANSLATION,
    ]


def test_canonical_order_contains_all_phases() -> None:
    canonical = PhaseRegistry.canonical_order()
    assert set(canonical) == set(PhaseId)
    assert canonical[0] is PhaseId.STT
    assert canonical[-1] is PhaseId.COHERENCE
