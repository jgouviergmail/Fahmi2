"""Onglet « Visualisations » — cockpit de génération des pages HTML autonomes.

Construit le cockpit (barre d'actions + bandeau d'état + matrice de progression) et
possède son ``VisualsController``. Le ``LogsDock`` partagé et la fenêtre parente lui sont
injectés. Calqué sur ``PedagogyTab``.
"""

from __future__ import annotations

from typing import cast

from PySide6.QtCore import QT_TRANSLATE_NOOP, QCoreApplication
from PySide6.QtWidgets import QVBoxLayout, QWidget

from fahmi2.app.project_service import ProjectService
from fahmi2.app.secrets_service import SecretsService
from fahmi2.core.config.paths import AppPaths
from fahmi2.domain.ids import ProjectId
from fahmi2.infra.storage.sqlite_state import SqliteState
from fahmi2.ui.features.feature import FeatureId, FeatureTab
from fahmi2.ui.visuals_controller import VisualsController
from fahmi2.ui.widgets.logs_dock import LogsDock
from fahmi2.ui.widgets.project_header_bar import ProjectHeaderBar
from fahmi2.ui.widgets.visuals_progress_view import VisualsProgressView

#: Stubs PySide6 : ``QT_TRANSLATE_NOOP`` est typé ``object`` ; on caste car
#: la fonction renvoie son argument textuel tel quel.
_TAB_TITLE = cast(str, QT_TRANSLATE_NOOP("VisualsTab", "Visualisations"))
_SETTINGS_TOOLTIP = cast(
    str,
    QT_TRANSLATE_NOOP(
        "VisualsTab",
        "Configurer les visualisations (livrables, densité, types de diagrammes, "
        "modèle & coût).",
    ),
)
_ESTIMATE_TOOLTIP = cast(
    str,
    QT_TRANSLATE_NOOP(
        "VisualsTab",
        "Estime le coût LLM de production des visualisations (extraction de la "
        "structure + traduction des libellés par langue).",
    ),
)
_OPEN_OUTPUT_TOOLTIP = cast(
    str,
    QT_TRANSLATE_NOOP(
        "VisualsTab",
        "Ouvre le dossier « visuals » contenant les pages HTML autonomes produites "
        "(carte des connaissances et diagrammes, par langue).",
    ),
)


class VisualsTab(FeatureTab):
    """Onglet de la fonctionnalité Visualisations."""

    def __init__(
        self,
        *,
        logs_dock: LogsDock,
        window: QWidget,
        project_service: ProjectService,
        secrets_service: SecretsService,
        state: SqliteState,
        app_paths: AppPaths,
    ) -> None:
        """Construit le cockpit Visualisations et son contrôleur.

        Args:
            logs_dock: Dock de logs partagé.
            window: Fenêtre parente (parent des dialogues).
            project_service: Service projets.
            secrets_service: Service secrets (clés DeepSeek / OpenAI).
            state: Stockage SQLite.
            app_paths: Chemins applicatifs (override des prompts).
        """
        self._widget = QWidget(window)
        layout = QVBoxLayout(self._widget)
        layout.setContentsMargins(0, 0, 0, 0)
        self._header_bar = ProjectHeaderBar(
            self._widget,
            settings_tooltip=QCoreApplication.translate("VisualsTab", _SETTINGS_TOOLTIP),
            estimate_tooltip=QCoreApplication.translate("VisualsTab", _ESTIMATE_TOOLTIP),
            open_output_tooltip=QCoreApplication.translate(
                "VisualsTab", _OPEN_OUTPUT_TOOLTIP
            ),
        )
        self._progress_view = VisualsProgressView(self._widget)
        layout.addWidget(self._header_bar)
        layout.addWidget(self._progress_view, stretch=1)

        self._controller = VisualsController(
            header_bar=self._header_bar,
            progress_view=self._progress_view,
            logs_dock=logs_dock,
            window=window,
            project_service=project_service,
            secrets_service=secrets_service,
            state=state,
            app_paths=app_paths,
        )

    @property
    def feature_id(self) -> FeatureId:
        """Identifiant de la fonctionnalité."""
        return FeatureId.VISUALS

    @property
    def title(self) -> str:
        """Libellé de l'onglet (traduit dans la langue active)."""
        return QCoreApplication.translate("VisualsTab", _TAB_TITLE)

    @property
    def widget(self) -> QWidget:
        """Widget racine de l'onglet."""
        return self._widget

    @property
    def controller(self) -> VisualsController:
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
        """Réinitialise le cockpit si le projet supprimé était affiché.

        Args:
            project_id: Projet supprimé.
        """
        if self._controller.current_project_id == project_id:
            self._controller.clear_current_project()
