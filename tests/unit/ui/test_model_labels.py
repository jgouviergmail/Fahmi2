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
    cloud_stt_model_labels,
    embedding_model_labels,
    labeled_enum_combo,
    llm_model_labels,
    local_stt_model_labels,
)


def test_every_model_has_a_label() -> None:
    """Un membre sans libellé serait absent du combo (bug silencieux)."""
    assert set(llm_model_labels()) == set(LLMModel)
    assert set(embedding_model_labels()) == set(EmbeddingModel)
    assert set(local_stt_model_labels()) == set(LocalSttModel)
    assert set(cloud_stt_model_labels()) == set(CloudSttModel)


def test_labels_carry_descriptive_suffix() -> None:
    """Style « comme le Dialogue » : valeur + parenthèse descriptive."""
    assert (
        llm_model_labels()[LLMModel.DEEPSEEK_V4_FLASH]
        == "DeepSeek V4 Flash (économique)"
    )
    assert all("(" in label for label in cloud_stt_model_labels().values())
    assert all("(" in label for label in local_stt_model_labels().values())


def test_labeled_combo_shows_label_and_stores_value(qtbot: QtBot) -> None:
    labels = llm_model_labels()
    combo = labeled_enum_combo(None, labels, selected=LLMModel.DEEPSEEK_V4_PRO)
    qtbot.addWidget(combo)
    # Le texte affiché est le libellé descriptif…
    assert combo.currentText() == labels[LLMModel.DEEPSEEK_V4_PRO]
    # …et la donnée est la valeur (str), recoercible vers l'enum.
    assert LLMModel(combo.currentData()) is LLMModel.DEEPSEEK_V4_PRO
