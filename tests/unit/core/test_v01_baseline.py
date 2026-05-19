"""Tests de la migration baseline v0 -> v1."""

from fahmi2.core.migrations.runner import MigrationRunner
from fahmi2.core.migrations.v01_baseline import _BaselineState, baseline_migration


def test_baseline_migration_advances_state_to_v1() -> None:
    state = _BaselineState(schema_version=0)
    runner = MigrationRunner[_BaselineState](
        migrations=[baseline_migration()], target_version=1
    )
    runner.run(state)
    assert state.schema_version == 1


def test_baseline_migration_metadata() -> None:
    mig = baseline_migration()
    assert mig.from_version == 0
    assert mig.to_version == 1
