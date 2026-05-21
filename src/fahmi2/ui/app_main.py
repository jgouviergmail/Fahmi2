"""Point d'entrée de l'application Fahmi2.

Construit l'``AppContext`` (dépendances injectées), instancie la
``MainWindow`` + les onglets de fonctionnalité (Génération, Supports
pédagogiques), branche les menus et les callbacks de la sidebar (édition,
suppression de projet), puis lance la boucle Qt.
"""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication, QMessageBox

from fahmi2.app.hardware_probe import probe_hardware
from fahmi2.app.project_service import ProjectService
from fahmi2.app.prompts_service import PromptsService
from fahmi2.app.secrets_service import SecretsService
from fahmi2.core.config.paths import AppPaths
from fahmi2.domain.ids import ProjectId
from fahmi2.infra.secrets.interface import InMemorySecretsStore, SecretsStore
from fahmi2.infra.storage.sqlite_state import SqliteState
from fahmi2.pedagogy.default_registry import build_default_support_registry
from fahmi2.ui.dialogs.global_settings_dialog import GlobalSettingsDialog
from fahmi2.ui.dialogs.new_project_dialog import NewProjectDialog
from fahmi2.ui.dialogs.prompts_editor_dialog import PromptsEditorDialog
from fahmi2.ui.features.generation_tab import GenerationTab
from fahmi2.ui.features.pedagogy_tab import PedagogyTab
from fahmi2.ui.features.registry import FeatureRegistry
from fahmi2.ui.main_window import MainWindow
from fahmi2.ui.theme import apply_theme

_DB_FILENAME = "projects.db"


def _build_secrets_store() -> SecretsStore:
    """Construit le ``SecretsStore`` adapté à la plateforme.

    Returns:
        DPAPI sur Windows, InMemory sinon (fallback pour dev hors Windows).
    """
    if sys.platform == "win32":
        from fahmi2.infra.secrets.dpapi_store import DPAPISecretsStore  # noqa: PLC0415

        paths = AppPaths.default()
        paths.ensure_dirs()
        return DPAPISecretsStore(paths.secrets_file)
    return InMemorySecretsStore()  # type: ignore[unreachable]


def main() -> int:  # noqa: PLR0915, C901
    """Point d'entrée Qt principal.

    Returns:
        Code de sortie du processus.
    """
    paths = AppPaths.default()
    paths.ensure_dirs()
    state = SqliteState(paths.appdata / _DB_FILENAME)
    secrets_store = _build_secrets_store()
    secrets_service = SecretsService(secrets_store)
    project_service = ProjectService(state)
    prompts_service = PromptsService(override_dir=paths.prompts_override_dir)
    hardware = probe_hardware()

    app = QApplication.instance() or QApplication(sys.argv)
    apply_theme(app)  # type: ignore[arg-type]
    window = MainWindow()

    generation_tab = GenerationTab(
        logs_dock=window.logs_dock,
        window=window,
        project_service=project_service,
        secrets_service=secrets_service,
        hardware=hardware,
        state=state,
        app_paths=paths,
    )
    pedagogy_tab = PedagogyTab(
        logs_dock=window.logs_dock,
        window=window,
        project_service=project_service,
        secrets_service=secrets_service,
        state=state,
        app_paths=paths,
        registry=build_default_support_registry(),
    )
    window.set_feature_tabs(FeatureRegistry([generation_tab, pedagogy_tab]))
    window.projects_sidebar.set_projects(project_service.list_projects())

    def _refresh_sidebar() -> None:
        window.projects_sidebar.set_projects(project_service.list_projects())

    def _open_settings() -> None:
        dialog = GlobalSettingsDialog(secrets_service, parent=window)
        dialog.exec()

    def _open_prompts_editor() -> None:
        dialog = PromptsEditorDialog(prompts_service, parent=window)
        dialog.exec()

    def _open_new_project() -> None:
        dialog = NewProjectDialog(parent=window)
        if dialog.exec() == NewProjectDialog.DialogCode.Accepted:
            name = dialog.get_name()
            workspace = dialog.get_workspace_folder()
            if name and workspace is not None:
                created = project_service.create_project(
                    name=name, workspace_folder=workspace
                )
                _refresh_sidebar()
                # Sélection automatique : le cockpit affiche l'état « à configurer »
                # (génération non renseignée) ; l'utilisateur clique « ⚙ Réglages ».
                window.projects_sidebar.select_project(created.id)

    def _edit_project(project_id: ProjectId) -> None:
        project = project_service.get_project(project_id)
        if project is None:
            return
        dialog = NewProjectDialog(
            parent=window,
            initial_name=project.name,
            initial_workspace=project.workspace_folder,
        )
        if dialog.exec() != NewProjectDialog.DialogCode.Accepted:
            return
        new_name = dialog.get_name()
        if not new_name:
            return
        project_service.update_project(project.with_name(new_name))
        _refresh_sidebar()
        window.projects_sidebar.select_project(project.id)

    def _delete_project(project_id: ProjectId) -> None:
        project = project_service.get_project(project_id)
        if project is None:
            return
        reply = QMessageBox.question(
            window,
            "Supprimer le projet ?",
            (
                f"Supprimer le projet « {project.name} » ?\n\n"
                "Cette action supprime également TOUS ses runs et leurs "
                "métadonnées en base de données. Les fichiers du dossier "
                "d'entrée et du workspace ne sont PAS supprimés sur disque.\n\n"
                "Cette action est irréversible."
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        # QMessageBox.question retourne un IntEnum reconstruit cote C++ -> Python a
        # chaque appel : l'identite ('is') avec QMessageBox.StandardButton.Yes n'est
        # pas garantie. On compare donc explicitement avec '=='.
        if reply == QMessageBox.StandardButton.Yes:
            project_service.delete_project(project_id)
            _refresh_sidebar()
            # Notifie tous les onglets (pas seulement la Génération) pour qu'aucun
            # ne conserve une référence au projet supprimé.
            window.notify_project_deleted(project_id)

    window.projects_sidebar.set_on_edit_requested(_edit_project)
    window.projects_sidebar.set_on_delete_requested(_delete_project)
    window.set_on_open_settings(_open_settings)
    window.set_on_open_prompts_editor(_open_prompts_editor)
    window.set_on_new_project(_open_new_project)
    # Garde une référence pour éviter la collection par le GC PySide.
    window._generation_tab = generation_tab  # type: ignore[attr-defined]  # noqa: SLF001
    window._pedagogy_tab = pedagogy_tab  # type: ignore[attr-defined]  # noqa: SLF001
    window.show()
    return int(app.exec())


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
