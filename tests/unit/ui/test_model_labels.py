"""Tests des libellés de modèles partagés et du combo associé."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fahmi2.domain.enums import (
    CloudSttModel,
    EmbeddingModel,
    LLMModel,
    LocalSttModel,
)
from fahmi2.ui._model_labels import (
    CLOUD_STT_MODEL_LABELS,
    EMBEDDING_MODEL_LABELS,
    LLM_MODEL_LABELS,
    LOCAL_STT_MODEL_LABELS,
    labeled_enum_combo,
)


def test_every_model_has_a_label() -> None:
    # Complétude : un membre sans libellé serait absent du combo (bug silencieux).
    assert set(LLM_MODEL_LABELS) == set(LLMModel)
    assert set(EMBEDDING_MODEL_LABELS) == set(EmbeddingModel)
    assert set(LOCAL_STT_MODEL_LABELS) == set(LocalSttModel)
    assert set(CLOUD_STT_MODEL_LABELS) == set(CloudSttModel)


def test_labels_carry_descriptive_suffix() -> None:
    # Style « comme le Dialogue » : valeur + parenthèse descriptive.
    assert LLM_MODEL_LABELS[LLMModel.DEEPSEEK_V4_FLASH] == "DeepSeek V4 Flash (économique)"
    assert all("(" in label for label in CLOUD_STT_MODEL_LABELS.values())
    assert all("(" in label for label in LOCAL_STT_MODEL_LABELS.values())


def test_labeled_combo_shows_label_and_stores_value(qtbot: QtBot) -> None:
    combo = labeled_enum_combo(
        None, LLM_MODEL_LABELS, selected=LLMModel.DEEPSEEK_V4_PRO
    )
    qtbot.addWidget(combo)
    # Le texte affiché est le libellé descriptif…
    assert combo.currentText() == LLM_MODEL_LABELS[LLMModel.DEEPSEEK_V4_PRO]
    # …et la donnée est la valeur (str), recoercible vers l'enum.
    assert LLMModel(combo.currentData()) is LLMModel.DEEPSEEK_V4_PRO
