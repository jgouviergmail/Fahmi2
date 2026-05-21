"""Tests du dialogue ``GenerationSettingsView``."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from pytestqt.qtbot import QtBot

from fahmi2.app.hardware_probe import HardwareInfo
from fahmi2.domain.enums import Language
from fahmi2.domain.generation import ParallelismConfig
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


def test_create_mode_deletes_audio_by_default(qtbot: QtBot) -> None:
    view = GenerationSettingsView(_HW, initial=None)
    qtbot.addWidget(view)
    view._input_folder_input.setText("D:/Cours")  # noqa: SLF001 — satisfait la validation
    assert view._keep_audio_checkbox.isChecked() is False  # noqa: SLF001
    view._on_accept()  # noqa: SLF001
    result = view.get_generation_settings()
    assert result is not None
    assert result.delete_audio_after_stt is True  # case décochée → suppression


def test_keep_audio_checkbox_preserves_audio(qtbot: QtBot) -> None:
    view = GenerationSettingsView(_HW, initial=None)
    qtbot.addWidget(view)
    view._input_folder_input.setText("D:/Cours")  # noqa: SLF001
    view._keep_audio_checkbox.setChecked(True)  # noqa: SLF001
    view._on_accept()  # noqa: SLF001
    result = view.get_generation_settings()
    assert result is not None
    assert result.delete_audio_after_stt is False  # case cochée → conservation


def test_edit_mode_reflects_keep_audio(
    qtbot: QtBot, make_generation_settings: Any
) -> None:
    gen = make_generation_settings(delete_audio_after_stt=False)
    view = GenerationSettingsView(_HW, initial=gen)
    qtbot.addWidget(view)
    assert view._keep_audio_checkbox.isChecked() is True  # noqa: SLF001


def test_parallelism_round_trips(
    qtbot: QtBot, make_generation_settings: Any
) -> None:
    gen = make_generation_settings(
        parallelism=ParallelismConfig(stt_cloud_workers=5, llm_workers=20)
    )
    view = GenerationSettingsView(_HW, initial=gen)
    qtbot.addWidget(view)
    view._on_accept()  # noqa: SLF001
    result = view.get_generation_settings()
    assert result is not None
    assert result.parallelism.stt_cloud_workers == 5
    assert result.parallelism.llm_workers == 20
