"""Libellés descriptifs des combos UI (modèles + paramètres d'enum partagés).

Source **unique** partagée par les dialogues de réglages (Génération, Supports
pédagogiques, Dialogue) : chaque modèle est présenté avec un suffixe explicitant
son compromis (« économique », « capacité supérieure », …), pour un choix éclairé
et cohérent d'un onglet à l'autre. La même logique s'applique aux paramètres
non-modèles (ex. ``ReasoningEffort``) pour garantir une terminologie homogène
d'un écran à l'autre.

i18n : les libellés sont exposés par des **fonctions** qui retournent un dict
traduit dans la langue active à l'appel. Le pattern Qt
``QCoreApplication.translate("ModelLabels", source)`` est utilisé pour les
chaînes sources (marquées par ``QT_TRANSLATE_NOOP`` afin que lupdate les
extraie sans nécessiter d'instance de ``QObject``).
"""

from __future__ import annotations

from enum import StrEnum
from typing import TypeVar, cast

from PySide6.QtCore import QT_TRANSLATE_NOOP, QCoreApplication
from PySide6.QtWidgets import QComboBox, QWidget

from fahmi2.domain.enums import (
    CloudSttModel,
    EmbeddingModel,
    LLMModel,
    LocalSttModel,
    ReasoningEffort,
)

_EnumT = TypeVar("_EnumT", bound=StrEnum)

#: Chaînes sources des libellés de modèles LLM. ``cast(str, …)`` corrige
#: l'annotation ``object`` des stubs PySide6 ; le contexte ``"ModelLabels"``
#: est passé en littéral car ``pyside6-lupdate`` n'extrait pas les chaînes
#: quand l'argument context est une variable.
_LLM_MODEL_SOURCES: dict[LLMModel, str] = {
    LLMModel.DEEPSEEK_V4_FLASH: cast(
        str, QT_TRANSLATE_NOOP("ModelLabels", "DeepSeek V4 Flash (économique)")
    ),
    LLMModel.DEEPSEEK_V4_PRO: cast(
        str,
        QT_TRANSLATE_NOOP("ModelLabels", "DeepSeek V4 Pro (capacité supérieure)"),
    ),
}

_EMBEDDING_MODEL_SOURCES: dict[EmbeddingModel, str] = {
    EmbeddingModel.TEXT_EMBEDDING_3_SMALL: cast(
        str,
        QT_TRANSLATE_NOOP("ModelLabels", "text-embedding-3-small (économique)"),
    ),
    EmbeddingModel.TEXT_EMBEDDING_3_LARGE: cast(
        str,
        QT_TRANSLATE_NOOP(
            "ModelLabels", "text-embedding-3-large (précision supérieure)"
        ),
    ),
    EmbeddingModel.TEXT_EMBEDDING_ADA_002: cast(
        str,
        QT_TRANSLATE_NOOP(
            "ModelLabels", "text-embedding-ada-002 (génération précédente)"
        ),
    ),
}

_LOCAL_STT_MODEL_SOURCES: dict[LocalSttModel, str] = {
    LocalSttModel.LARGE_V3_TURBO: cast(
        str, QT_TRANSLATE_NOOP("ModelLabels", "large-v3-turbo (équilibré)")
    ),
    LocalSttModel.LARGE_V3: cast(
        str, QT_TRANSLATE_NOOP("ModelLabels", "large-v3 (précision maximale)")
    ),
    LocalSttModel.MEDIUM: cast(
        str, QT_TRANSLATE_NOOP("ModelLabels", "medium (plus léger / rapide)")
    ),
    LocalSttModel.SMALL: cast(
        str, QT_TRANSLATE_NOOP("ModelLabels", "small (rapide, faible VRAM)")
    ),
}

_CLOUD_STT_MODEL_SOURCES: dict[CloudSttModel, str] = {
    CloudSttModel.WHISPER_1: cast(
        str, QT_TRANSLATE_NOOP("ModelLabels", "whisper-1 (timestamps fins)")
    ),
    CloudSttModel.GPT_4O_TRANSCRIBE: cast(
        str,
        QT_TRANSLATE_NOOP("ModelLabels", "gpt-4o-transcribe (précision supérieure)"),
    ),
    CloudSttModel.GPT_4O_MINI_TRANSCRIBE: cast(
        str,
        QT_TRANSLATE_NOOP("ModelLabels", "gpt-4o-mini-transcribe (2× moins cher)"),
    ),
}

_NO_REASONING_SOURCE: str = cast(
    str, QT_TRANSLATE_NOOP("ModelLabels", "Automatique (serveur)")
)

_REASONING_EFFORT_SOURCES: dict[ReasoningEffort, str] = {
    ReasoningEffort.HIGH: cast(str, QT_TRANSLATE_NOOP("ModelLabels", "Élevée")),
    ReasoningEffort.MAX: cast(str, QT_TRANSLATE_NOOP("ModelLabels", "Maximale")),
}


def _tr(source: str) -> str:
    """Traduit ``source`` dans la langue active via le contexte ``ModelLabels``."""
    return QCoreApplication.translate("ModelLabels", source)


def llm_model_labels() -> dict[LLMModel, str]:
    """Libellés traduits des modèles LLM (combo « Modèle » des dialogues)."""
    return {model: _tr(source) for model, source in _LLM_MODEL_SOURCES.items()}


def embedding_model_labels() -> dict[EmbeddingModel, str]:
    """Libellés traduits des modèles d'embedding."""
    return {model: _tr(source) for model, source in _EMBEDDING_MODEL_SOURCES.items()}


def local_stt_model_labels() -> dict[LocalSttModel, str]:
    """Libellés traduits des modèles STT locaux (faster-whisper)."""
    return {model: _tr(source) for model, source in _LOCAL_STT_MODEL_SOURCES.items()}


def cloud_stt_model_labels() -> dict[CloudSttModel, str]:
    """Libellés traduits des modèles STT cloud (OpenAI)."""
    return {model: _tr(source) for model, source in _CLOUD_STT_MODEL_SOURCES.items()}


def no_reasoning_label() -> str:
    """Libellé traduit du choix par défaut du combo « Intensité de réflexion »."""
    return _tr(_NO_REASONING_SOURCE)


def reasoning_effort_labels() -> dict[ReasoningEffort, str]:
    """Libellés traduits des niveaux d'intensité de réflexion."""
    return {level: _tr(source) for level, source in _REASONING_EFFORT_SOURCES.items()}


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
