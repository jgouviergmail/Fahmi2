"""Onglet « Génération » — cockpit sources → document consolidé.

Construit le cockpit (barre de titre + bande de stats + matrice sources × phases) et
possède son ``GenerationController``. Le ``LogsDock`` partagé et la fenêtre parente
lui sont injectés.
"""

from __future__ import annotations

from typing import cast

from PySide6.QtCore import QT_TRANSLATE_NOOP, QCoreApplication
from PySide6.QtWidgets import QVBoxLayout, QWidget

from fahmi2.app.hardware_probe import HardwareInfo
from fahmi2.app.project_service import ProjectService
from fahmi2.app.secrets_service import SecretsService
from fahmi2.core.config.paths import AppPaths
from fahmi2.domain.ids import ProjectId
from fahmi2.infra.storage.sqlite_state import SqliteState
from fahmi2.ui.features.feature import FeatureId, FeatureTab
from fahmi2.ui.generation_controller import GenerationController
from fahmi2.ui.widgets.cost_matrix_view import CostMatrixView
from fahmi2.ui.widgets.logs_dock import LogsDock
from fahmi2.ui.widgets.project_header_bar import ProjectHeaderBar
from fahmi2.ui.widgets.stats_strip import StatsStripWidget

#: Stubs PySide6 : ``QT_TRANSLATE_NOOP`` est typé ``object`` ; on caste car
#: la fonction renvoie son argument textuel tel quel.
_TAB_TITLE = cast(str, QT_TRANSLATE_NOOP("GenerationTab", "Génération"))
_EXPORT_TOOLTIP = cast(
    str,
    QT_TRANSLATE_NOOP(
        "GenerationTab",
        "Exporte les livrables de la génération (document consolidé et glossaire) "
        "dans les formats cochés (Markdown / PDF / HTML).",
    ),
)


class GenerationTab(FeatureTab):
    """Onglet de la fonctionnalité Génération."""

    def __init__(
        self,
        *,
        logs_dock: LogsDock,
        window: QWidget,
        project_service: ProjectService,
        secrets_service: SecretsService,
        hardware: HardwareInfo,
        state: SqliteState,
        app_paths: AppPaths,
    ) -> None:
        """Construit le cockpit et son contrôleur.

        Args:
            logs_dock: Dock de logs partagé.
            window: Fenêtre parente (parent des dialogues).
            project_service: Service projets.
            secrets_service: Service secrets.
            hardware: Info matérielle.
            state: Stockage SQLite.
            app_paths: Chemins applicatifs.
        """
        self._widget = QWidget(window)
        layout = QVBoxLayout(self._widget)
        layout.setContentsMargins(0, 0, 0, 0)
        self._header_bar = ProjectHeaderBar(
            self._widget,
            show_export=True,
            export_tooltip=QCoreApplication.translate("GenerationTab", _EXPORT_TOOLTIP),
        )
        self._stats_strip = StatsStripWidget(self._widget)
        self._run_matrix = CostMatrixView(parent=self._widget)
        layout.addWidget(self._header_bar)
        layout.addWidget(self._stats_strip)
        layout.addWidget(self._run_matrix, stretch=1)

        self._controller = GenerationController(
            header_bar=self._header_bar,
            stats_strip=self._stats_strip,
            run_matrix=self._run_matrix,
            logs_dock=logs_dock,
            window=window,
            project_service=project_service,
            secrets_service=secrets_service,
            hardware=hardware,
            state=state,
            app_paths=app_paths,
        )

    @property
    def feature_id(self) -> FeatureId:
        """Identifiant de la fonctionnalité."""
        return FeatureId.GENERATION

    @property
    def title(self) -> str:
        """Libellé de l'onglet (traduit dans la langue active)."""
        return QCoreApplication.translate("GenerationTab", _TAB_TITLE)

    @property
    def widget(self) -> QWidget:
        """Widget racine de l'onglet."""
        return self._widget

    @property
    def controller(self) -> GenerationController:
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
