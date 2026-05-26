"""Libellés descriptifs des modèles (LLM, embeddings, STT) pour les combos UI.

Source **unique** partagée par les dialogues de réglages (Génération, Supports
pédagogiques, Dialogue) : chaque modèle est présenté avec un suffixe explicitant
son compromis (« économique », « capacité supérieure », …), pour un choix éclairé
et cohérent d'un onglet à l'autre.
"""

from __future__ import annotations

from enum import StrEnum
from typing import TypeVar

from PySide6.QtWidgets import QComboBox, QWidget

from fahmi2.domain.enums import (
    CloudSttModel,
    EmbeddingModel,
    LLMModel,
    LocalSttModel,
)

_EnumT = TypeVar("_EnumT", bound=StrEnum)

#: Modèles LLM DeepSeek (réponses, reformulation, supports).
LLM_MODEL_LABELS: dict[LLMModel, str] = {
    LLMModel.DEEPSEEK_V4_FLASH: "DeepSeek V4 Flash (économique)",
    LLMModel.DEEPSEEK_V4_PRO: "DeepSeek V4 Pro (capacité supérieure)",
}

#: Modèles d'embedding OpenAI (retrieval sémantique du Dialogue).
EMBEDDING_MODEL_LABELS: dict[EmbeddingModel, str] = {
    EmbeddingModel.TEXT_EMBEDDING_3_SMALL: "text-embedding-3-small (économique)",
    EmbeddingModel.TEXT_EMBEDDING_3_LARGE: "text-embedding-3-large (précision supérieure)",
    EmbeddingModel.TEXT_EMBEDDING_ADA_002: "text-embedding-ada-002 (génération précédente)",
}

#: Modèles faster-whisper locaux (STT local).
LOCAL_STT_MODEL_LABELS: dict[LocalSttModel, str] = {
    LocalSttModel.LARGE_V3_TURBO: "large-v3-turbo (équilibré)",
    LocalSttModel.LARGE_V3: "large-v3 (précision maximale)",
    LocalSttModel.MEDIUM: "medium (plus léger / rapide)",
    LocalSttModel.SMALL: "small (rapide, faible VRAM)",
}

#: Modèles de transcription cloud OpenAI (STT cloud).
CLOUD_STT_MODEL_LABELS: dict[CloudSttModel, str] = {
    CloudSttModel.WHISPER_1: "whisper-1 (timestamps fins)",
    CloudSttModel.GPT_4O_TRANSCRIBE: "gpt-4o-transcribe (précision supérieure)",
    CloudSttModel.GPT_4O_MINI_TRANSCRIBE: "gpt-4o-mini-transcribe (2× moins cher)",
}


def labeled_enum_combo(
    parent: QWidget | None,
    labels: dict[_EnumT, str],
    *,
    selected: _EnumT | None = None,
) -> QComboBox:
    """Construit un combo (libellé descriptif, valeur en donnée), pré-positionné.

    La donnée stockée est ``member.value`` (str) : ``QComboBox`` ne préserve pas le
    type ``StrEnum`` (sous-classe de ``str``) — relire via
    ``EnumClass(combo.currentData())``.

    Args:
        parent: Parent Qt.
        labels: Mapping membre d'enum → libellé affiché (l'ordre fixe l'ordre des
            items du combo).
        selected: Membre initialement sélectionné (défaut : le premier item).

    Returns:
        Le ``QComboBox`` peuplé et positionné.
    """
    combo = QComboBox(parent)
    for member, label in labels.items():
        combo.addItem(label, member.value)
    if selected is not None:
        index = combo.findData(selected.value)
        if index >= 0:
            combo.setCurrentIndex(index)
    return combo
