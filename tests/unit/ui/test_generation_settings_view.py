"""Tests du dialogue ``GenerationSettingsView``."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from pytestqt.qtbot import QtBot

from fahmi2.app.hardware_probe import HardwareInfo
from fahmi2.domain.enums import (
    CloudSttModel,
    ConsolidationMode,
    ExportFormat,
    Language,
    LocalSttModel,
    SttProvider,
    StylePreset,
)
from fahmi2.domain.generation import ParallelismConfig
from fahmi2.ui.dialogs.generation_settings_view import GenerationSettingsView

_HW = HardwareInfo(cuda_available=False, gpu_name="", cuda_version="")
_HW_CUDA = HardwareInfo(cuda_available=True, gpu_name="RTX", cuda_version="12.1")


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


def test_export_page_roundtrip(qtbot: QtBot, make_generation_settings: Any) -> None:
    gen = make_generation_settings(
        input_folder=Path("D:/Cours"),
        export_formats=frozenset({ExportFormat.PDF, ExportFormat.HTML}),
    )
    view = GenerationSettingsView(_HW, initial=gen)
    qtbot.addWidget(view)
    # Les cases reflètent les réglages…
    assert view._export_checks[ExportFormat.PDF].isChecked()  # noqa: SLF001
    assert view._export_checks[ExportFormat.HTML].isChecked()  # noqa: SLF001
    assert ExportFormat.APKG not in view._export_checks  # noqa: SLF001
    # …et to_settings les relit.
    view._on_accept()  # noqa: SLF001
    out = view.get_generation_settings()
    assert out is not None
    assert out.export_formats == frozenset({ExportFormat.PDF, ExportFormat.HTML})


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


def test_built_settings_are_enums_not_str(
    qtbot: QtBot, make_generation_settings: Any
) -> None:
    # Robustesse : QComboBox peut dégrader un StrEnum en str ; les réglages
    # construits doivent toujours porter de vrais enums (sinon les comparaisons
    # `is` en aval — build_stt_provider, phase 0… — échouent silencieusement).
    gen = make_generation_settings(input_folder=Path("D:/Cours"))
    view = GenerationSettingsView(_HW, initial=gen)
    qtbot.addWidget(view)
    view._on_accept()  # noqa: SLF001
    result = view.get_generation_settings()
    assert result is not None
    assert isinstance(result.stt_provider, SttProvider)
    assert isinstance(result.style_preset, StylePreset)


def test_local_stt_without_gpu_reverts_to_cloud(
    qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Quand l'utilisateur sélectionne le STT local sans GPU CUDA, l'avertissement
    # doit se déclencher et re-basculer sur le cloud. (Avant le recoerce en enum,
    # la comparaison d'identité était toujours fausse → bascule jamais déclenchée.)
    monkeypatch.setattr(
        "fahmi2.ui.dialogs.generation_settings_view.QMessageBox.warning",
        lambda *a, **k: None,
    )
    view = GenerationSettingsView(_HW, initial=None)  # _HW : pas de CUDA
    qtbot.addWidget(view)
    view._input_folder_input.setText("D:/Cours")  # noqa: SLF001
    combo = view._stt_combo  # noqa: SLF001
    combo.setCurrentIndex(combo.findData(SttProvider.OPENAI_CLOUD))
    # L'utilisateur tente le local → doit re-basculer sur le cloud.
    combo.setCurrentIndex(combo.findData(SttProvider.FASTER_WHISPER_LOCAL))
    view._on_accept()  # noqa: SLF001
    result = view.get_generation_settings()
    assert result is not None
    assert result.stt_provider is SttProvider.OPENAI_CLOUD


def test_stt_models_round_trip(
    qtbot: QtBot, make_generation_settings: Any
) -> None:
    gen = make_generation_settings(
        stt_local_model=LocalSttModel.SMALL,
        stt_cloud_model=CloudSttModel.GPT_4O_MINI_TRANSCRIBE,
    )
    view = GenerationSettingsView(_HW, initial=gen)
    qtbot.addWidget(view)
    view._on_accept()  # noqa: SLF001
    result = view.get_generation_settings()
    assert result is not None
    assert result.stt_local_model is LocalSttModel.SMALL
    assert result.stt_cloud_model is CloudSttModel.GPT_4O_MINI_TRANSCRIBE


def test_stt_model_combo_enabled_by_provider(
    qtbot: QtBot, make_generation_settings: Any
) -> None:
    # Cloud sélectionné → combo cloud actif, combo local grisé.
    cloud = make_generation_settings(stt_provider=SttProvider.OPENAI_CLOUD)
    cloud_view = GenerationSettingsView(_HW, initial=cloud)
    qtbot.addWidget(cloud_view)
    assert cloud_view._stt_cloud_model_combo.isEnabled()  # noqa: SLF001
    assert not cloud_view._stt_local_model_combo.isEnabled()  # noqa: SLF001
    # Local sélectionné (GPU présent) → l'inverse.
    local = make_generation_settings(stt_provider=SttProvider.FASTER_WHISPER_LOCAL)
    local_view = GenerationSettingsView(_HW_CUDA, initial=local)
    qtbot.addWidget(local_view)
    assert local_view._stt_local_model_combo.isEnabled()  # noqa: SLF001
    assert not local_view._stt_cloud_model_combo.isEnabled()  # noqa: SLF001


def test_consolidation_mode_defaults_ordered_and_note_hidden(qtbot: QtBot) -> None:
    view = GenerationSettingsView(_HW, initial=None)
    qtbot.addWidget(view)
    view._input_folder_input.setText("D:/Cours")  # noqa: SLF001
    view._on_accept()  # noqa: SLF001
    result = view.get_generation_settings()
    assert result is not None
    assert result.consolidation_mode is ConsolidationMode.ORDERED
    # Mode ordonné → la note « ordre sans effet » reste masquée.
    assert view._source_order_view._order_note.isHidden() is True  # noqa: SLF001


def test_consolidation_mode_thematic_round_trip_and_note(
    qtbot: QtBot, make_generation_settings: Any
) -> None:
    gen = make_generation_settings(
        input_folder=Path("D:/Cours"),
        consolidation_mode=ConsolidationMode.THEMATIC,
    )
    view = GenerationSettingsView(_HW, initial=gen)
    qtbot.addWidget(view)
    # Le combo reflète le réglage, et la note d'ordre est affichée.
    combo = view._consolidation_mode_combo  # noqa: SLF001
    assert ConsolidationMode(combo.currentData()) is ConsolidationMode.THEMATIC
    assert view._source_order_view._order_note.isHidden() is False  # noqa: SLF001
    # …et to_settings le relit.
    view._on_accept()  # noqa: SLF001
    out = view.get_generation_settings()
    assert out is not None
    assert out.consolidation_mode is ConsolidationMode.THEMATIC


def test_consolidation_mode_built_is_enum_not_str(
    qtbot: QtBot, make_generation_settings: Any
) -> None:
    gen = make_generation_settings(input_folder=Path("D:/Cours"))
    view = GenerationSettingsView(_HW, initial=gen)
    qtbot.addWidget(view)
    view._on_accept()  # noqa: SLF001
    result = view.get_generation_settings()
    assert result is not None
    assert isinstance(result.consolidation_mode, ConsolidationMode)


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
