"""Dialogue de réglages de l'onglet Dialogue (chat).

Formulaire simple (peu de réglages → un master-detail serait surdimensionné) :
fidélité, stratégie de retrieval, query expansion, modèle LLM, modèle d'embedding,
raisonnement, température, top-K. ``get_chat_settings`` reconstruit un
``ChatSettings`` immuable. Le combo modèle d'embedding n'est actif qu'en mode cloud
(retrieval ``AUTO``/``SEMANTIC``) : il est sans effet en lexical (100 % local).
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QSpinBox,
    QWidget,
)

from fahmi2.domain.chat import ChatSettings
from fahmi2.domain.enums import (
    ChatGroundingMode,
    EmbeddingModel,
    LLMModel,
    ReasoningEffort,
    RetrievalStrategy,
)
from fahmi2.ui._model_labels import (
    EMBEDDING_MODEL_LABELS,
    LLM_MODEL_LABELS,
    labeled_enum_combo,
)

_DIALOG_TITLE = "Réglages — Dialogue"
_TEMPERATURE_MIN = 0.0
_TEMPERATURE_MAX = 2.0
_TEMPERATURE_STEP = 0.1
_TOP_K_MIN = 1
_TOP_K_MAX = 20
_NO_REASONING_LABEL = "Auto (serveur)"

_GROUNDING_LABELS = {
    ChatGroundingMode.STRICT: "Ancré strict (citations, refus hors-corpus)",
    ChatGroundingMode.AUGMENTED: "Augmenté (complément « Au-delà du cours »)",
}
_STRATEGY_LABELS = {
    RetrievalStrategy.AUTO: "Auto (sémantique si possible, sinon lexical)",
    RetrievalStrategy.LEXICAL: "Lexical (TF-IDF, hors-ligne)",
    RetrievalStrategy.SEMANTIC: "Sémantique (embeddings OpenAI)",
}
_REASONING_LABELS = {
    ReasoningEffort.HIGH: "Élevé (high)",
    ReasoningEffort.MAX: "Maximal (max)",
}


class ChatSettingsView(QDialog):
    """Dialogue de configuration du chat de dialogue."""

    def __init__(
        self, *, parent: QWidget | None = None, initial: ChatSettings | None = None
    ) -> None:
        """Construit le dialogue.

        Args:
            parent: Fenêtre parente.
            initial: Réglages à pré-remplir (défaut ``ChatSettings()``).
        """
        super().__init__(parent)
        self.setWindowTitle(_DIALOG_TITLE)
        settings = initial or ChatSettings()
        form = QFormLayout(self)

        self._grounding = labeled_enum_combo(
            self, _GROUNDING_LABELS, selected=settings.grounding_mode
        )
        self._strategy = labeled_enum_combo(
            self, _STRATEGY_LABELS, selected=settings.retrieval_strategy
        )
        self._query_expansion = QCheckBox(self)
        self._query_expansion.setChecked(settings.query_expansion_enabled)
        self._model = labeled_enum_combo(self, LLM_MODEL_LABELS, selected=settings.model)
        self._embedding_model = labeled_enum_combo(
            self, EMBEDDING_MODEL_LABELS, selected=settings.embedding_model
        )
        self._thinking = QCheckBox(self)
        self._thinking.setChecked(settings.thinking_enabled)
        self._reasoning = self._build_reasoning_combo(settings.reasoning_effort)
        self._temperature = QDoubleSpinBox(self)
        self._temperature.setRange(_TEMPERATURE_MIN, _TEMPERATURE_MAX)
        self._temperature.setSingleStep(_TEMPERATURE_STEP)
        self._temperature.setValue(settings.temperature)
        self._top_k = QSpinBox(self)
        self._top_k.setRange(_TOP_K_MIN, _TOP_K_MAX)
        self._top_k.setValue(settings.top_k)

        form.addRow("Fidélité", self._grounding)
        form.addRow("Retrieval", self._strategy)
        form.addRow("Modèle d'embedding", self._embedding_model)
        form.addRow("Expansion de requête", self._query_expansion)
        form.addRow("Modèle LLM", self._model)
        form.addRow("Mode raisonnement", self._thinking)
        form.addRow("Effort de raisonnement", self._reasoning)
        form.addRow("Température", self._temperature)
        form.addRow("Passages (top-K)", self._top_k)

        # Le modèle d'embedding n'a d'effet qu'en retrieval cloud (AUTO/SEMANTIC).
        self._strategy.currentIndexChanged.connect(self._sync_embedding_enabled)
        self._sync_embedding_enabled()

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def get_chat_settings(self) -> ChatSettings:
        """Reconstruit les réglages depuis les widgets.

        Returns:
            Le ``ChatSettings`` saisi.
        """
        return ChatSettings(
            grounding_mode=ChatGroundingMode(self._grounding.currentData()),
            retrieval_strategy=RetrievalStrategy(self._strategy.currentData()),
            query_expansion_enabled=self._query_expansion.isChecked(),
            model=LLMModel(self._model.currentData()),
            embedding_model=EmbeddingModel(self._embedding_model.currentData()),
            thinking_enabled=self._thinking.isChecked(),
            reasoning_effort=self._selected_reasoning(),
            temperature=self._temperature.value(),
            top_k=self._top_k.value(),
        )

    def _sync_embedding_enabled(self) -> None:
        """Active le combo d'embedding hors mode lexical (cloud uniquement)."""
        is_cloud = self._strategy.currentData() != str(RetrievalStrategy.LEXICAL)
        self._embedding_model.setEnabled(is_cloud)

    def _build_reasoning_combo(self, initial: ReasoningEffort | None) -> QComboBox:
        combo = QComboBox(self)
        combo.addItem(_NO_REASONING_LABEL, None)
        for effort, label in _REASONING_LABELS.items():
            combo.addItem(label, effort.value)
        if initial is not None:
            index = combo.findData(initial.value)
            if index >= 0:
                combo.setCurrentIndex(index)
        return combo

    def _selected_reasoning(self) -> ReasoningEffort | None:
        data = self._reasoning.currentData()
        return ReasoningEffort(data) if data is not None else None
