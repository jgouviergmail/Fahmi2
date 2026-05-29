"""Tests du catalogue de prompts pour les templates des Visualisations."""

from __future__ import annotations

from pathlib import Path

from fahmi2.app.prompts_service import PromptsService

_VISUALS_TEMPLATES = {
    "visuals_graph_extraction",
    "visuals_community_report",
    "visuals_idea_chains",
    "visuals_diagram_authoring",
    "visuals_label_translation",
}


def test_visuals_templates_present_and_loadable(tmp_path: Path) -> None:
    service = PromptsService(override_dir=tmp_path)
    names = {meta.name for meta in service.list_templates()}
    assert _VISUALS_TEMPLATES <= names
    # Chaque template par défaut est chargeable (non vide).
    for name in _VISUALS_TEMPLATES:
        assert service.load_default(name).strip()
