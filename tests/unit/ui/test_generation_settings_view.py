"""Tests du dialogue ``GenerationSettingsView``."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from pytestqt.qtbot import QtBot

from fahmi2.app.hardware_probe import HardwareInfo
from fahmi2.domain.enums import Language
from fahmi2.ui.dialogs.generation_settings_view import GenerationSettingsView

_HW = HardwareInfo(cuda_available=False, gpu_name="", cuda_version="")


def test_create_mode_requires_input_folder(
    qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
) -> None:
    # ``QMessageBox.warning`` est modal/bloquant : on le neutralise pour le test.
    monkeypatch.setattr(
        "fahmi2.ui.dialogs.generation_settings_view.QMessageBox.warning",
        lambda *a, **k: None,
    )
    view = GenerationSettingsView(_HW, initial=None)
    qtbot.addWidget(view)
    view._on_accept()  # noqa: SLF001
    assert view.get_generation_settings() is None


def test_edit_mode_prefills_and_returns(
    qtbot: QtBot, make_generation_settings: Any
) -> None:
    gen = make_generation_settings(
        input_folder=Path("D:/Cours"),
        output_languages=(Language.FR, Language.EN),
    )
    view = GenerationSettingsView(_HW, initial=gen)
    qtbot.addWidget(view)
    view._on_accept()  # noqa: SLF001
    result = view.get_generation_settings()
    assert result is not None
    assert result.input_folder == Path("D:/Cours")
    assert Language.EN in result.output_languages
