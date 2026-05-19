"""Point d'entrée de l'application Fahmi2.

Construit l'``AppContext`` (dépendances injectées), instancie la
``MainWindow`` + ``RunController``, branche les menus aux services et lance
la boucle Qt.
"""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from fahmi2.app.hardware_probe import probe_hardware
from fahmi2.app.project_service import ProjectService
from fahmi2.app.secrets_service import SecretsService
from fahmi2.core.config.paths import AppPaths
from fahmi2.infra.secrets.interface import InMemorySecretsStore, SecretsStore
from fahmi2.infra.storage.sqlite_state import SqliteState
from fahmi2.ui.dialogs.global_settings_dialog import GlobalSettingsDialog
from fahmi2.ui.dialogs.new_project_dialog import NewProjectDialog
from fahmi2.ui.main_window import MainWindow
from fahmi2.ui.run_controller import RunController

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


def main() -> int:
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
    hardware = probe_hardware()

    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()
    window.projects_sidebar.set_projects(project_service.list_projects())

    run_controller = RunController(
        main_window=window,
        project_service=project_service,
        secrets_service=secrets_service,
        hardware=hardware,
        state=state,
        app_paths=paths,
    )

    def _open_settings() -> None:
        dialog = GlobalSettingsDialog(secrets_service, parent=window)
        dialog.exec()

    def _open_new_project() -> None:
        dialog = NewProjectDialog(hardware, parent=window)
        if dialog.exec() == NewProjectDialog.DialogCode.Accepted:
            settings = dialog.get_settings()
            if settings is not None:
                project_service.create_project(settings)
                window.projects_sidebar.set_projects(project_service.list_projects())

    window.set_on_open_settings(_open_settings)
    window.set_on_new_project(_open_new_project)
    # Garde une référence pour éviter la collection par le GC PySide
    window._run_controller = run_controller  # type: ignore[attr-defined]  # noqa: SLF001
    window.show()
    return int(app.exec())


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
