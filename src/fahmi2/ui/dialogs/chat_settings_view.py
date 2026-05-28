"""Dialogue ``ChatSettingsView`` — réglages de l'onglet Dialogue (chat).

Présenté en master-detail (composant :class:`~fahmi2.ui.widgets.settings_view.SettingsView`)
à trois catégories :

- **Mode de réponse** : ``ChatGroundingMode`` (strict / étendu) + nombre de
  passages cités (``top_k``).
- **Recherche de passages** : ``RetrievalStrategy`` (méthode de recherche) +
  reformulation automatique de la question + ``EmbeddingModel``.
- **Génération IA** : modèle LLM + réflexion approfondie + intensité de
  réflexion + température.

i18n : tous les libellés passent par :py:meth:`QObject.tr` à l'usage.
"""

from __future__ import annotations

from typing import Final

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QSpinBox,
    QVBoxLayout,
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
from fahmi2.ui._components import (
    card,
    dialog_footer,
    field_hint,
    localize_button_box,
    settings_form,
    settings_page,
)
from fahmi2.ui._model_labels import (
    embedding_model_labels,
    labeled_enum_combo,
    llm_model_labels,
    no_reasoning_label,
    reasoning_effort_labels,
)
from fahmi2.ui.widgets.settings_view import SettingsView

_DIALOG_WIDTH: Final[int] = 780
_DIALOG_HEIGHT: Final[int] = 560
_OUTER_MARGIN: Final[int] = 0
_TEMPERATURE_MIN: Final[float] = 0.0
_TEMPERATURE_MAX: Final[float] = 2.0
_TEMPERATURE_STEP: Final[float] = 0.1
_TOP_K_MIN: Final[int] = 1
_TOP_K_MAX: Final[int] = 20


class ChatSettingsView(QDialog):
    """Dialogue de configuration du chat de dialogue (master-detail)."""

    def __init__(
        self, *, parent: QWidget | None = None, initial: ChatSettings | None = None
    ) -> None:
        """Construit le dialogue.

        Args:
            parent: Fenêtre parente.
            initial: Réglages à pré-remplir (défaut ``ChatSettings()``).
        """
        super().__init__(parent)
        self.setWindowTitle(self.tr("Réglages — Dialogue"))
        self.resize(_DIALOG_WIDTH, _DIALOG_HEIGHT)
        settings = initial or ChatSettings()

        self._grounding = labeled_enum_combo(
            self, self._grounding_labels(), selected=settings.grounding_mode
        )
        self._strategy = labeled_enum_combo(
            self, self._strategy_labels(), selected=settings.retrieval_strategy
        )
        self._query_expansion = QCheckBox(
            self.tr("Reformulation automatique des questions"), self
        )
        self._query_expansion.setChecked(settings.query_expansion_enabled)
        self._embedding_model = labeled_enum_combo(
            self, embedding_model_labels(), selected=settings.embedding_model
        )
        self._model = labeled_enum_combo(self, llm_model_labels(), selected=settings.model)
        self._thinking = QCheckBox(self.tr("Activer la réflexion approfondie"), self)
        self._thinking.setChecked(settings.thinking_enabled)
        self._reasoning = self._build_reasoning_combo(settings.reasoning_effort)
        self._temperature = QDoubleSpinBox(self)
        self._temperature.setRange(_TEMPERATURE_MIN, _TEMPERATURE_MAX)
        self._temperature.setSingleStep(_TEMPERATURE_STEP)
        self._temperature.setValue(settings.temperature)
        self._top_k = QSpinBox(self)
        self._top_k.setRange(_TOP_K_MIN, _TOP_K_MAX)
        self._top_k.setValue(settings.top_k)

        settings_view = SettingsView(
            [
                (self.tr("Mode de réponse"), self._build_response_page()),
                (self.tr("Recherche de passages"), self._build_retrieval_page()),
                (self.tr("Génération IA"), self._build_generation_page()),
            ],
            self,
        )

        self._strategy.currentIndexChanged.connect(self._sync_embedding_enabled)
        self._sync_embedding_enabled()

        self._thinking.toggled.connect(self._reasoning.setEnabled)
        self._reasoning.setEnabled(self._thinking.isChecked())

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        localize_button_box(buttons)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(
            _OUTER_MARGIN, _OUTER_MARGIN, _OUTER_MARGIN, _OUTER_MARGIN
        )
        outer.setSpacing(0)
        outer.addWidget(settings_view, stretch=1)
        outer.addWidget(dialog_footer(self, buttons))
        self.setSizeGripEnabled(True)

    def _grounding_labels(self) -> dict[ChatGroundingMode, str]:
        """Libellés traduits des modes d'ancrage du chat."""
        return {
            ChatGroundingMode.STRICT: self.tr(
                "Strict — réponses tirées du cours uniquement"
            ),
            ChatGroundingMode.AUGMENTED: self.tr(
                "Étendu — complète au-delà du cours"
            ),
        }

    def _strategy_labels(self) -> dict[RetrievalStrategy, str]:
        """Libellés traduits des stratégies de retrieval."""
        return {
            RetrievalStrategy.AUTO: self.tr(
                "Automatique (sens si clé OpenAI, mots-clés sinon)"
            ),
            RetrievalStrategy.LEXICAL: self.tr("Mots-clés (hors ligne, TF-IDF)"),
            RetrievalStrategy.SEMANTIC: self.tr("Sens (en ligne, OpenAI)"),
        }

    def _build_response_page(self) -> QWidget:
        """Construit la page « Mode de réponse »."""
        page, page_layout = settings_page(self)

        response_card, response_layout = card(
            page,
            title=self.tr("Comportement des réponses"),
            description=self.tr(
                "Définit jusqu'où l'assistant peut s'éloigner du cours dans ses réponses."
            ),
        )
        response_form = settings_form()
        response_form.addRow(self.tr("Mode de réponse"), self._grounding)
        response_layout.addLayout(response_form)
        page_layout.addWidget(response_card)

        citations_card, citations_layout = card(
            page,
            title=self.tr("Passages cités"),
            description=self.tr(
                "Nombre de passages du cours utilisés pour étayer chaque réponse."
            ),
        )
        citations_form = settings_form()
        citations_form.addRow(self.tr("Nombre de passages cités"), self._top_k)
        citations_layout.addLayout(citations_form)
        page_layout.addWidget(citations_card)

        page_layout.addStretch(1)
        return page

    def _build_retrieval_page(self) -> QWidget:
        """Construit la page « Recherche de passages »."""
        page, page_layout = settings_page(self)

        method_card, method_layout = card(
            page,
            title=self.tr("Méthode de recherche"),
            description=self.tr(
                "Comment l'assistant retrouve les passages pertinents dans le cours."
            ),
        )
        method_form = settings_form()
        method_form.addRow(self.tr("Méthode"), self._strategy)
        method_layout.addLayout(method_form)
        method_layout.addWidget(self._query_expansion)
        method_layout.addWidget(
            field_hint(
                method_card,
                self.tr(
                    "L'assistant reformule la question pour améliorer la recherche. Recommandé."
                ),
            )
        )
        page_layout.addWidget(method_card)

        vector_card, vector_layout = card(
            page,
            title=self.tr("Modèle de vectorisation"),
            description=self.tr(
                "Modèle OpenAI utilisé pour la recherche par sens. Sans effet en mode "
                "« mots-clés » (entièrement hors ligne)."
            ),
        )
        vector_form = settings_form()
        vector_form.addRow(self.tr("Modèle"), self._embedding_model)
        vector_layout.addLayout(vector_form)
        page_layout.addWidget(vector_card)

        page_layout.addStretch(1)
        return page

    def _build_generation_page(self) -> QWidget:
        """Construit la page « Génération IA »."""
        page, page_layout = settings_page(self)

        model_card, model_layout = card(
            page,
            title=self.tr("Modèle de génération"),
            description=self.tr(
                "Modèle DeepSeek qui rédige les réponses à partir des passages cités."
            ),
        )
        model_form = settings_form()
        model_form.addRow(self.tr("Modèle"), self._model)
        model_form.addRow(self.tr("Température"), self._temperature)
        model_layout.addLayout(model_form)
        page_layout.addWidget(model_card)

        thinking_card, thinking_layout = card(
            page,
            title=self.tr("Réflexion approfondie"),
            description=self.tr(
                "Active un raisonnement étendu avant la réponse — meilleure qualité, "
                "coût plus élevé."
            ),
        )
        thinking_layout.addWidget(self._thinking)
        thinking_form = settings_form()
        thinking_form.addRow(self.tr("Intensité de réflexion"), self._reasoning)
        thinking_layout.addLayout(thinking_form)
        page_layout.addWidget(thinking_card)

        page_layout.addStretch(1)
        return page

    def get_chat_settings(self) -> ChatSettings:
        """Reconstruit les réglages depuis les widgets."""
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
        """Active le combo de vectorisation hors mode lexical (cloud uniquement)."""
        is_cloud = self._strategy.currentData() != str(RetrievalStrategy.LEXICAL)
        self._embedding_model.setEnabled(is_cloud)

    def _build_reasoning_combo(self, initial: ReasoningEffort | None) -> QComboBox:
        """Construit le combo d'intensité de réflexion (option « Automatique » en tête)."""
        combo = QComboBox(self)
        combo.addItem(no_reasoning_label(), None)
        for effort, label in reasoning_effort_labels().items():
            combo.addItem(label, effort.value)
        if initial is not None:
            index = combo.findData(initial.value)
            if index >= 0:
                combo.setCurrentIndex(index)
        return combo

    def _selected_reasoning(self) -> ReasoningEffort | None:
        """Lit l'effort de raisonnement sélectionné (``None`` = automatique)."""
        data = self._reasoning.currentData()
        return ReasoningEffort(data) if data is not None else None
