"""Dialogue ``ChatSettingsView`` — réglages de l'onglet Dialogue (chat).

Présenté en master-detail (composant :class:`~fahmi2.ui.widgets.settings_view.SettingsView`)
à trois catégories pour rester cohérent avec les autres écrans de réglages
de l'application :

- **Mode de réponse** : ``ChatGroundingMode`` (strict / étendu) + nombre de
  passages cités (``top_k``).
- **Recherche de passages** : ``RetrievalStrategy`` (méthode de recherche) +
  reformulation automatique de la question + ``EmbeddingModel`` (modèle de
  vectorisation, désactivé en mode hors-ligne).
- **Génération IA** : modèle LLM + réflexion approfondie + intensité de
  réflexion + température.

L'API publique (``get_chat_settings``, paramètre ``initial``) et les attributs
privés référencés par les tests existants (``_grounding`` / ``_strategy`` /
``_embedding_model`` / etc.) sont **strictement préservés** : seule la
présentation change.
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
    frenchify_button_box,
    settings_form,
    settings_page,
)
from fahmi2.ui._model_labels import (
    EMBEDDING_MODEL_LABELS,
    LLM_MODEL_LABELS,
    labeled_enum_combo,
)
from fahmi2.ui.widgets.settings_view import SettingsView

# ---------------------------------------------------------------- constantes

#: Titre du dialogue.
_DIALOG_TITLE: Final[str] = "Réglages — Dialogue"
#: Dimensions par défaut du dialogue (px).
_DIALOG_WIDTH: Final[int] = 780
_DIALOG_HEIGHT: Final[int] = 560
#: Marges externes.
_OUTER_MARGIN: Final[int] = 0  # SettingsView occupe toute la fenêtre
_OUTER_SPACING: Final[int] = 12

#: Bornes des champs numériques.
_TEMPERATURE_MIN: Final[float] = 0.0
_TEMPERATURE_MAX: Final[float] = 2.0
_TEMPERATURE_STEP: Final[float] = 0.1
_TOP_K_MIN: Final[int] = 1
_TOP_K_MAX: Final[int] = 20

#: Libellé de l'option « aucun effort de raisonnement explicite ».
_NO_REASONING_LABEL: Final[str] = "Automatique (serveur)"

# ---------------------------------------------------------------- catégories

_CAT_RESPONSE: Final[str] = "Mode de réponse"
_CAT_RETRIEVAL: Final[str] = "Recherche de passages"
_CAT_GENERATION: Final[str] = "Génération IA"

# ---------------------------------------------------------------- libellés

_GROUNDING_LABELS: Final[dict[ChatGroundingMode, str]] = {
    ChatGroundingMode.STRICT: "Strict — réponses tirées du cours uniquement",
    ChatGroundingMode.AUGMENTED: "Étendu — complète au-delà du cours",
}
_STRATEGY_LABELS: Final[dict[RetrievalStrategy, str]] = {
    RetrievalStrategy.AUTO: "Automatique (sens si clé OpenAI, mots-clés sinon)",
    RetrievalStrategy.LEXICAL: "Mots-clés (hors ligne, TF-IDF)",
    RetrievalStrategy.SEMANTIC: "Sens (en ligne, OpenAI)",
}
_REASONING_LABELS: Final[dict[ReasoningEffort, str]] = {
    ReasoningEffort.HIGH: "Élevée",
    ReasoningEffort.MAX: "Maximale",
}

# ---------------------------------------------------------------- libellés UI

_RESPONSE_CARD_TITLE: Final[str] = "Comportement des réponses"
_RESPONSE_CARD_DESC: Final[str] = (
    "Définit jusqu'où l'assistant peut s'éloigner du cours dans ses réponses."
)
_RESPONSE_MODE_LABEL: Final[str] = "Mode de réponse"

_CITATIONS_CARD_TITLE: Final[str] = "Passages cités"
_CITATIONS_CARD_DESC: Final[str] = (
    "Nombre de passages du cours utilisés pour étayer chaque réponse."
)
_TOP_K_LABEL: Final[str] = "Nombre de passages cités"

_METHOD_CARD_TITLE: Final[str] = "Méthode de recherche"
_METHOD_CARD_DESC: Final[str] = (
    "Comment l'assistant retrouve les passages pertinents dans le cours."
)
_STRATEGY_LABEL: Final[str] = "Méthode"
_QUERY_EXPANSION_LABEL: Final[str] = "Reformulation automatique des questions"
_QUERY_EXPANSION_HINT: Final[str] = (
    "L'assistant reformule la question pour améliorer la recherche. Recommandé."
)

_VECTORIZATION_CARD_TITLE: Final[str] = "Modèle de vectorisation"
_VECTORIZATION_CARD_DESC: Final[str] = (
    "Modèle OpenAI utilisé pour la recherche par sens. Sans effet en mode "
    "« mots-clés » (entièrement hors ligne)."
)
_EMBEDDING_LABEL: Final[str] = "Modèle"

_MODEL_CARD_TITLE: Final[str] = "Modèle de génération"
_MODEL_CARD_DESC: Final[str] = (
    "Modèle DeepSeek qui rédige les réponses à partir des passages cités."
)
_LLM_LABEL: Final[str] = "Modèle"
_TEMPERATURE_LABEL: Final[str] = "Température"

_THINKING_CARD_TITLE: Final[str] = "Réflexion approfondie"
_THINKING_CARD_DESC: Final[str] = (
    "Active un raisonnement étendu avant la réponse — meilleure qualité, "
    "coût plus élevé."
)
_THINKING_LABEL: Final[str] = "Activer la réflexion approfondie"
_REASONING_EFFORT_LABEL: Final[str] = "Intensité de réflexion"


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
        self.setWindowTitle(_DIALOG_TITLE)
        self.resize(_DIALOG_WIDTH, _DIALOG_HEIGHT)
        settings = initial or ChatSettings()

        # Construction des contrôles (ordre stable pour les tests / lecture).
        self._grounding = labeled_enum_combo(
            self, _GROUNDING_LABELS, selected=settings.grounding_mode
        )
        self._strategy = labeled_enum_combo(
            self, _STRATEGY_LABELS, selected=settings.retrieval_strategy
        )
        self._query_expansion = QCheckBox(_QUERY_EXPANSION_LABEL, self)
        self._query_expansion.setChecked(settings.query_expansion_enabled)
        self._embedding_model = labeled_enum_combo(
            self, EMBEDDING_MODEL_LABELS, selected=settings.embedding_model
        )
        self._model = labeled_enum_combo(self, LLM_MODEL_LABELS, selected=settings.model)
        self._thinking = QCheckBox(_THINKING_LABEL, self)
        self._thinking.setChecked(settings.thinking_enabled)
        self._reasoning = self._build_reasoning_combo(settings.reasoning_effort)
        self._temperature = QDoubleSpinBox(self)
        self._temperature.setRange(_TEMPERATURE_MIN, _TEMPERATURE_MAX)
        self._temperature.setSingleStep(_TEMPERATURE_STEP)
        self._temperature.setValue(settings.temperature)
        self._top_k = QSpinBox(self)
        self._top_k.setRange(_TOP_K_MIN, _TOP_K_MAX)
        self._top_k.setValue(settings.top_k)

        # Pages master-detail.
        settings_view = SettingsView(
            [
                (_CAT_RESPONSE, self._build_response_page()),
                (_CAT_RETRIEVAL, self._build_retrieval_page()),
                (_CAT_GENERATION, self._build_generation_page()),
            ],
            self,
        )

        # Le modèle de vectorisation n'a d'effet qu'en retrieval cloud (AUTO/SEMANTIC) :
        # on désactive le combo en mode lexical pour une UX claire (le réglage est
        # conservé et restitué — voir le test smoke dédié).
        self._strategy.currentIndexChanged.connect(self._sync_embedding_enabled)
        self._sync_embedding_enabled()

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        frenchify_button_box(buttons)
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

    # --------------------------------------------------------------- pages

    def _build_response_page(self) -> QWidget:
        """Construit la page « Mode de réponse » (comportement + citations)."""
        page, page_layout = settings_page(self)

        response_card, response_layout = card(
            page, title=_RESPONSE_CARD_TITLE, description=_RESPONSE_CARD_DESC
        )
        response_form = settings_form()
        response_form.addRow(_RESPONSE_MODE_LABEL, self._grounding)
        response_layout.addLayout(response_form)
        page_layout.addWidget(response_card)

        citations_card, citations_layout = card(
            page, title=_CITATIONS_CARD_TITLE, description=_CITATIONS_CARD_DESC
        )
        citations_form = settings_form()
        citations_form.addRow(_TOP_K_LABEL, self._top_k)
        citations_layout.addLayout(citations_form)
        page_layout.addWidget(citations_card)

        page_layout.addStretch(1)
        return page

    def _build_retrieval_page(self) -> QWidget:
        """Construit la page « Recherche de passages »."""
        page, page_layout = settings_page(self)

        method_card, method_layout = card(
            page, title=_METHOD_CARD_TITLE, description=_METHOD_CARD_DESC
        )
        method_form = settings_form()
        method_form.addRow(_STRATEGY_LABEL, self._strategy)
        method_layout.addLayout(method_form)
        method_layout.addWidget(self._query_expansion)
        method_layout.addWidget(field_hint(method_card, _QUERY_EXPANSION_HINT))
        page_layout.addWidget(method_card)

        vector_card, vector_layout = card(
            page, title=_VECTORIZATION_CARD_TITLE, description=_VECTORIZATION_CARD_DESC
        )
        vector_form = settings_form()
        vector_form.addRow(_EMBEDDING_LABEL, self._embedding_model)
        vector_layout.addLayout(vector_form)
        page_layout.addWidget(vector_card)

        page_layout.addStretch(1)
        return page

    def _build_generation_page(self) -> QWidget:
        """Construit la page « Génération IA » (modèle + réflexion)."""
        page, page_layout = settings_page(self)

        model_card, model_layout = card(
            page, title=_MODEL_CARD_TITLE, description=_MODEL_CARD_DESC
        )
        model_form = settings_form()
        model_form.addRow(_LLM_LABEL, self._model)
        model_form.addRow(_TEMPERATURE_LABEL, self._temperature)
        model_layout.addLayout(model_form)
        page_layout.addWidget(model_card)

        thinking_card, thinking_layout = card(
            page, title=_THINKING_CARD_TITLE, description=_THINKING_CARD_DESC
        )
        thinking_layout.addWidget(self._thinking)
        thinking_form = settings_form()
        thinking_form.addRow(_REASONING_EFFORT_LABEL, self._reasoning)
        thinking_layout.addLayout(thinking_form)
        page_layout.addWidget(thinking_card)

        page_layout.addStretch(1)
        return page

    # ------------------------------------------------------------ API publique

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

    # ---------------------------------------------------------- private logic

    def _sync_embedding_enabled(self) -> None:
        """Active le combo de vectorisation hors mode lexical (cloud uniquement)."""
        is_cloud = self._strategy.currentData() != str(RetrievalStrategy.LEXICAL)
        self._embedding_model.setEnabled(is_cloud)

    def _build_reasoning_combo(self, initial: ReasoningEffort | None) -> QComboBox:
        """Construit le combo d'intensité de réflexion (option « Automatique » en tête).

        Args:
            initial: Effort initial (``None`` = automatique).

        Returns:
            Le ``QComboBox`` peuplé et positionné.
        """
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
        """Lit l'effort de raisonnement sélectionné (``None`` = automatique)."""
        data = self._reasoning.currentData()
        return ReasoningEffort(data) if data is not None else None
