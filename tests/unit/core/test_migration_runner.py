"""Tests du MigrationRunner."""

from dataclasses import dataclass, field

import pytest

from fahmi2.core.migrations.runner import Migration, MigrationRunner


@dataclass
class _MutableState:
    """État mutable factice pour exercer les migrations."""

    schema_version: int = 0
    applied: list[int] = field(default_factory=list)


def _make_migration(from_v: int, to_v: int) -> Migration[_MutableState]:
    def _apply(s: _MutableState) -> None:
        s.applied.append(to_v)
        s.schema_version = to_v

    return Migration(from_version=from_v, to_version=to_v, apply=_apply)


def test_runner_applies_no_migration_when_uptodate() -> None:
    state = _MutableState(schema_version=2)
    runner = MigrationRunner[_MutableState](
        migrations=[_make_migration(1, 2), _make_migration(2, 3)],
        target_version=2,
    )
    runner.run(state)
    assert state.applied == []


def test_runner_applies_one_migration() -> None:
    state = _MutableState(schema_version=1)
    runner = MigrationRunner[_MutableState](
        migrations=[_make_migration(1, 2)],
        target_version=2,
    )
    runner.run(state)
    assert state.applied == [2]
    assert state.schema_version == 2


def test_runner_applies_chain() -> None:
    state = _MutableState(schema_version=1)
    runner = MigrationRunner[_MutableState](
        migrations=[
            _make_migration(1, 2),
            _make_migration(2, 3),
            _make_migration(3, 4),
        ],
        target_version=4,
    )
    runner.run(state)
    assert state.applied == [2, 3, 4]
    assert state.schema_version == 4


def test_runner_raises_when_no_path() -> None:
    state = _MutableState(schema_version=1)
    runner = MigrationRunner[_MutableState](
        migrations=[_make_migration(2, 3)],
        target_version=3,
    )
    with pytest.raises(RuntimeError):
        runner.run(state)


def test_runner_refuses_downgrade() -> None:
    state = _MutableState(schema_version=5)
    runner = MigrationRunner[_MutableState](
        migrations=[_make_migration(1, 2)],
        target_version=2,
    )
    with pytest.raises(RuntimeError):
        runner.run(state)


def test_runner_raises_when_migration_does_not_advance() -> None:
    state = _MutableState(schema_version=1)

    def _bad_apply(s: _MutableState) -> None:
        # ne met pas schema_version à jour
        s.applied.append(2)

    runner = MigrationRunner[_MutableState](
        migrations=[Migration(from_version=1, to_version=2, apply=_bad_apply)],
        target_version=2,
    )
    with pytest.raises(RuntimeError, match="did not advance"):
        runner.run(state)
