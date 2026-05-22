"""Tests des wrappers d'identifiants typés du domaine."""

from dataclasses import FrozenInstanceError

import pytest

from fahmi2.domain.ids import ProjectId, RunId, SourceId


def test_project_id_wraps_string() -> None:
    pid = ProjectId.new()
    assert isinstance(pid.value, str)
    assert len(pid.value) == 26


def test_run_id_wraps_string() -> None:
    rid = RunId.new()
    assert isinstance(rid.value, str)


def test_source_id_wraps_string() -> None:
    vid = SourceId.new()
    assert isinstance(vid.value, str)


def test_ids_equal_themselves() -> None:
    pid = ProjectId.new()
    same = ProjectId(value=pid.value)
    assert pid == same


def test_ids_are_hashable() -> None:
    pid = ProjectId.new()
    s = {pid, ProjectId(value=pid.value)}
    assert len(s) == 1


def test_ids_validate_format() -> None:
    with pytest.raises(ValueError):
        ProjectId(value="not-a-ulid")
    with pytest.raises(ValueError):
        RunId(value="bad")
    with pytest.raises(ValueError):
        SourceId(value="bad")


def test_ids_are_immutable() -> None:
    pid = ProjectId.new()
    with pytest.raises(FrozenInstanceError):
        pid.value = "other"  # type: ignore[misc]
