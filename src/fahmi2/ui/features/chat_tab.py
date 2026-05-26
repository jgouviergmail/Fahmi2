"""Onglet « Dialogue » — chat conversationnel ancré sur le corpus.

Construit la vue conversationnelle (`ChatView`) + un bouton de réglages, et possède
son `ChatController`. Calqué sur `PedagogyTab` (abstraction `FeatureTab`).
"""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from fahmi2.app.project_service import ProjectService
from fahmi2.app.secrets_service import SecretsService
from fahmi2.core.config.paths import AppPaths
from fahmi2.domain.ids import ProjectId
from fahmi2.ui._buttons import BUTTON_ROLE_DEFAULT, make_role_button
from fahmi2.ui.chat_controller import ChatController, LlmProviderFactory
from fahmi2.ui.features.feature import FeatureId, FeatureTab
from fahmi2.ui.widgets.chat_view import ChatView

_TAB_TITLE = "Dialogue"
_SETTINGS_LABEL = "⚙️  Réglages"
_SETTINGS_TOOLTIP = "Configurer le dialogue (fidélité, retrieval, modèle, coût)."


class ChatTab(FeatureTab):
    """Onglet de la fonctionnalité Dialogue (chat)."""

    def __init__(
        self,
        *,
        window: QWidget,
        project_service: ProjectService,
        secrets_service: SecretsService,
        app_paths: AppPaths,
        llm_provider_factory: LlmProviderFactory | None = None,
    ) -> None:
        """Construit l'onglet et son contrôleur.

        Args:
            window: Fenêtre parente (parent des dialogues).
            project_service: Service projets.
            secrets_service: Service secrets (clé DeepSeek).
            app_paths: Chemins applicatifs (override des prompts).
            llm_provider_factory: Fabrique de ``LLMProvider`` (injectable, tests).
        """
        self._widget = QWidget(window)
        layout = QVBoxLayout(self._widget)
        layout.setContentsMargins(0, 0, 0, 0)
        settings_button = make_role_button(
            self._widget, _SETTINGS_LABEL, role=BUTTON_ROLE_DEFAULT
        )
        settings_button.setToolTip(_SETTINGS_TOOLTIP)
        settings_row = QHBoxLayout()
        settings_row.setContentsMargins(16, 10, 16, 6)
        settings_row.addWidget(settings_button)
        settings_row.addStretch(1)
        self._view = ChatView(self._widget)
        layout.addLayout(settings_row)
        layout.addWidget(self._view, stretch=1)

        self._controller = ChatController(
            view=self._view,
            window=window,
            project_service=project_service,
            secrets_service=secrets_service,
            app_paths=app_paths,
            llm_provider_factory=llm_provider_factory,
        )
        settings_button.clicked.connect(self._controller.open_chat_settings)

    @property
    def feature_id(self) -> FeatureId:
        """Identifiant de la fonctionnalité."""
        return FeatureId.CHAT

    @property
    def title(self) -> str:
        """Libellé de l'onglet."""
        return _TAB_TITLE

    @property
    def widget(self) -> QWidget:
        """Widget racine de l'onglet."""
        return self._widget

    @property
    def controller(self) -> ChatController:
        """Contrôleur de l'onglet (utilisé par le câblage applicatif)."""
        return self._controller

    def on_project_selected(self, project_id: ProjectId | None) -> None:
        """Délègue la sélection de projet au contrôleur.

        Args:
            project_id: Projet sélectionné, ou ``None``.
        """
        if project_id is not None:
            self._controller.on_project_selected(project_id)

    def on_project_deleted(self, project_id: ProjectId) -> None:
        """Réinitialise l'onglet si le projet supprimé était affiché.

        Args:
            project_id: Projet supprimé.
        """
        if self._controller.current_project_id == project_id:
            self._controller.clear_current_project()
