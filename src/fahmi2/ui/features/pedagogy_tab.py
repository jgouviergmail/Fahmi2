"""Onglet « Supports pédagogiques » — cockpit de génération des supports.

Construit le cockpit (barre d'actions + bandeau d'état + table de progression) et
possède son ``PedagogyController``. Le ``LogsDock`` partagé et la fenêtre parente
lui sont injectés. Calqué sur ``GenerationTab``.
"""

from __future__ import annotations

from PySide6.QtWidgets import QVBoxLayout, QWidget

from fahmi2.app.project_service import ProjectService
from fahmi2.app.secrets_service import SecretsService
from fahmi2.core.config.paths import AppPaths
from fahmi2.domain.ids import ProjectId
from fahmi2.infra.storage.sqlite_state import SqliteState
from fahmi2.pedagogy.support_registry import SupportGeneratorRegistry
from fahmi2.ui.features.feature import FeatureId, FeatureTab
from fahmi2.ui.pedagogy_controller import PedagogyController
from fahmi2.ui.widgets.logs_dock import LogsDock
from fahmi2.ui.widgets.pedagogy_progress_view import PedagogyProgressView
from fahmi2.ui.widgets.project_header_bar import ProjectHeaderBar

_TAB_TITLE = "Supports pédagogiques"
_SETTINGS_TOOLTIP = (
    "Configurer les supports pédagogiques (supports, difficulté, langues, "
    "modèle & coût)."
)
_ESTIMATE_TOOLTIP = (
    "Estime le coût LLM de génération des supports sélectionnés "
    "(par support × langue × chapitre)."
)
_OPEN_OUTPUT_TOOLTIP = (
    "Ouvre le dossier « pedagogy » contenant les supports générés "
    "(JSON + Markdown)."
)


class PedagogyTab(FeatureTab):
    """Onglet de la fonctionnalité Supports pédagogiques."""

    def __init__(
        self,
        *,
        logs_dock: LogsDock,
        window: QWidget,
        project_service: ProjectService,
        secrets_service: SecretsService,
        state: SqliteState,
        app_paths: AppPaths,
        registry: SupportGeneratorRegistry,
    ) -> None:
        """Construit le cockpit pédagogie et son contrôleur.

        Args:
            logs_dock: Dock de logs partagé.
            window: Fenêtre parente (parent des dialogues).
            project_service: Service projets.
            secrets_service: Service secrets (clé DeepSeek).
            state: Stockage SQLite.
            app_paths: Chemins applicatifs (override des prompts).
            registry: Registre des générateurs de supports.
        """
        self._widget = QWidget(window)
        layout = QVBoxLayout(self._widget)
        layout.setContentsMargins(0, 0, 0, 0)
        self._header_bar = ProjectHeaderBar(
            self._widget,
            settings_tooltip=_SETTINGS_TOOLTIP,
            estimate_tooltip=_ESTIMATE_TOOLTIP,
            open_output_tooltip=_OPEN_OUTPUT_TOOLTIP,
        )
        self._progress_view = PedagogyProgressView(self._widget)
        layout.addWidget(self._header_bar)
        layout.addWidget(self._progress_view, stretch=1)

        self._controller = PedagogyController(
            header_bar=self._header_bar,
            progress_view=self._progress_view,
            logs_dock=logs_dock,
            window=window,
            project_service=project_service,
            secrets_service=secrets_service,
            state=state,
            app_paths=app_paths,
            registry=registry,
        )

    @property
    def feature_id(self) -> FeatureId:
        """Identifiant de la fonctionnalité."""
        return FeatureId.PEDAGOGY

    @property
    def title(self) -> str:
        """Libellé de l'onglet."""
        return _TAB_TITLE

    @property
    def widget(self) -> QWidget:
        """Widget racine de l'onglet."""
        return self._widget

    @property
    def controller(self) -> PedagogyController:
        """Contrôleur de l'onglet (utilisé par le câblage applicatif)."""
        return self._controller

    def on_project_selected(self, project_id: ProjectId | None) -> None:
        """Délègue la sélection de projet au contrôleur.

        Args:
            project_id: Projet sélectionné, ou ``None``.
        """
        if project_id is not None:
            self._controller.on_project_selected(project_id)
