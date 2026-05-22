"""Tests du catalogue de prompts pour les templates du chat de dialogue."""

from __future__ import annotations

from pathlib import Path

from fahmi2.app.prompts_service import PromptsService


def test_chat_templates_present_and_loadable(tmp_path: Path) -> None:
    service = PromptsService(override_dir=tmp_path)
    names = {meta.name for meta in service.list_templates()}
    assert {"chat_strict", "chat_augmented", "chat_query_expansion"} <= names
    assert "Extraits du cours" in service.load_default("chat_strict")
    assert "Au-delà du cours" in service.load_default("chat_augmented")
    assert "mots-clés" in service.load_default("chat_query_expansion")
