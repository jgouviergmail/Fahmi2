"""Tests du ``FeatureRegistry`` et du contrat ``FeatureTab``."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QLabel, QWidget

from fahmi2.domain.ids import ProjectId
from fahmi2.ui.features.feature import FeatureId, FeatureTab
from fahmi2.ui.features.registry import FeatureRegistry
from fahmi2.ui.main_window import MainWindow


class _StubTab(FeatureTab):
    def __init__(self, feature_id: FeatureId, title: str) -> None:
        self._feature_id = feature_id
        self._title = title
        self._widget = QLabel(title)
        self.selected: list[ProjectId | None] = []
        self.deleted: list[ProjectId] = []

    @property
    def feature_id(self) -> FeatureId:
        return self._feature_id

    @property
    def title(self) -> str:
        return self._title

    @property
    def widget(self) -> QWidget:
        return self._widget

    def on_project_selected(self, project_id: ProjectId | None) -> None:
        self.selected.append(project_id)

    def on_project_deleted(self, project_id: ProjectId) -> None:
        self.deleted.append(project_id)


def test_registry_preserves_registration_order(qapp: object) -> None:
    del qapp
    gen = _StubTab(FeatureId.GENERATION, "Génération")
    ped = _StubTab(FeatureId.PEDAGOGY, "Supports")
    registry = FeatureRegistry([gen, ped])
    assert [t.feature_id for t in registry.ordered()] == [
        FeatureId.GENERATION,
        FeatureId.PEDAGOGY,
    ]


def test_registry_rejects_duplicate_feature_id(qapp: object) -> None:
    del qapp
    a = _StubTab(FeatureId.GENERATION, "A")
    b = _StubTab(FeatureId.GENERATION, "B")
    with pytest.raises(ValueError, match="already registered"):
        FeatureRegistry([a, b])


def test_default_on_project_selected_is_noop(qapp: object) -> None:
    del qapp

    class _Minimal(FeatureTab):
        @property
        def feature_id(self) -> FeatureId:
            return FeatureId.PEDAGOGY

        @property
        def title(self) -> str:
            return "X"

        @property
        def widget(self) -> QWidget:
            return QLabel("X")

    _Minimal().on_project_selected(ProjectId.new())
    _Minimal().on_project_deleted(ProjectId.new())


def test_notify_project_deleted_dispatches_to_all_tabs(qapp: object) -> None:
    del qapp
    gen = _StubTab(FeatureId.GENERATION, "Génération")
    ped = _StubTab(FeatureId.PEDAGOGY, "Supports")
    window = MainWindow()
    window.set_feature_tabs(FeatureRegistry([gen, ped]))
    pid = ProjectId.new()
    window.notify_project_deleted(pid)
    assert gen.deleted == [pid]
    assert ped.deleted == [pid]
