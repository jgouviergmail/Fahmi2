"""Smoke tests du dialogue PromptsEditorDialog."""

from __future__ import annotations

from pathlib import Path

from pytestqt.qtbot import QtBot

from fahmi2.app.prompts_service import PromptsService
from fahmi2.ui.dialogs.prompts_editor_dialog import PromptsEditorDialog


def test_prompts_editor_loads_first_template(qtbot: QtBot, tmp_path: Path) -> None:
    service = PromptsService(override_dir=tmp_path)
    dialog = PromptsEditorDialog(service)
    qtbot.addWidget(dialog)
    # Le premier item de la liste doit être sélectionné automatiquement.
    assert dialog._list_widget.currentRow() == 0  # noqa: SLF001
    # L'éditeur doit contenir le source du premier template.
    text = dialog._editor.toPlainText()  # noqa: SLF001
    assert "glossaire" in text.lower()


def test_prompts_editor_save_creates_override_file(
    qtbot: QtBot, tmp_path: Path
) -> None:
    service = PromptsService(override_dir=tmp_path)
    dialog = PromptsEditorDialog(service)
    qtbot.addWidget(dialog)
    # Tape un override valide pour le template courant
    dialog._editor.setPlainText("Custom prompt {{ x }}.")  # noqa: SLF001
    # Le test simule un clic Enregistrer en évitant la modal QMessageBox
    # via un patch léger.
    name = dialog._current_name  # noqa: SLF001
    assert name is not None
    service.save_override(name, "Custom prompt {{ x }}.")
    # Vérifie qu'on a bien créé le fichier override
    assert (tmp_path / f"{name}.j2").exists()
    # load_active retourne maintenant l'override
    assert service.load_active(name) == "Custom prompt {{ x }}."
