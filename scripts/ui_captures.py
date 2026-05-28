"""Banc de capture pérennisé : rend les écrans Fahmi2 en PNG (Qt réel).

Produit des captures fidèles du rendu de l'application en mode clair et en
mode sombre, sans afficher de fenêtre (``widget.grab()`` sur un widget non
montré, moteur Windows utilisé pour que les polices système rendent
correctement).

Usage :

    .venv\\Scripts\\python.exe scripts\\ui_captures.py
    .venv\\Scripts\\python.exe scripts\\ui_captures.py --out .ui-review/lot0

Les captures sont produites dans deux sous-dossiers ``light/`` et ``dark/``
sous le dossier de sortie. Le dossier ``.ui-review/`` est ``.gitignore`` ;
ces captures servent à la validation utilisateur des changements UI, pas à
être versionnées.

Le script importe les écrans réels — il n'a pas besoin de mocker les
services pour les dialogues purement présentationnels (les services « lourds »
restent à venir au fil des lots).
"""

from __future__ import annotations

import argparse
import tempfile
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Final

from PySide6.QtWidgets import (
    QApplication,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from fahmi2.app.hardware_probe import probe_hardware
from fahmi2.app.secrets_service import SecretsService
from fahmi2.app.theme_controller import ThemeController
from fahmi2.domain.enums import Language, PhaseStatus, RunStatus
from fahmi2.infra.secrets.interface import InMemorySecretsStore
from fahmi2.ui.dialogs.chat_settings_view import ChatSettingsView
from fahmi2.ui.dialogs.generation_settings_view import GenerationSettingsView
from fahmi2.ui.dialogs.global_settings_dialog import GlobalSettingsDialog
from fahmi2.ui.dialogs.new_project_dialog import NewProjectDialog
from fahmi2.ui.dialogs.pedagogy_settings_view import PedagogySettingsView
from fahmi2.ui.theme import ThemeMode, apply_theme
from fahmi2.ui.viewmodels.cost_matrix import CostMatrixCell, build_cost_matrix
from fahmi2.ui.viewmodels.stats_strip import StatsSnapshot
from fahmi2.ui.widgets.cost_matrix_view import CostMatrixView
from fahmi2.ui.widgets.project_header_bar import ProjectHeaderBar
from fahmi2.ui.widgets.stats_strip import StatsStripWidget

#: Sous-dossier produit par mode dans le dossier de sortie.
_MODE_SUBDIR: Final[dict[ThemeMode, str]] = {
    ThemeMode.LIGHT: "light",
    ThemeMode.DARK: "dark",
}
#: Dossier de sortie par défaut (rendu .gitignore'd).
_DEFAULT_OUT_DIR: Final[str] = ".ui-review/lot0"
#: Toutes les langues disponibles pour les dialogues qui en attendent une.
_ALL_LANGUAGES: Final[tuple[Language, ...]] = (
    Language.FR,
    Language.EN,
    Language.DE,
)

# ---------------------------------------------------------- exemples cockpit

#: Taille (px) du composite cockpit utilisé pour la capture.
_COCKPIT_WIDTH: Final[int] = 1120
_COCKPIT_HEIGHT: Final[int] = 660
#: Tailles (px) des dialogues capturés (cohérentes avec leurs ``resize()`` réels).
_SETTINGS_DIALOG_WIDTH: Final[int] = 820
_SETTINGS_DIALOG_HEIGHT: Final[int] = 600
_CHAT_SETTINGS_WIDTH: Final[int] = 560
_CHAT_SETTINGS_HEIGHT: Final[int] = 460
_NEW_PROJECT_WIDTH: Final[int] = 640
_NEW_PROJECT_HEIGHT: Final[int] = 360
_GLOBAL_SETTINGS_WIDTH: Final[int] = 640
_GLOBAL_SETTINGS_HEIGHT: Final[int] = 520
#: Données réalistes utilisées par ``_sample_stats_snapshot``.
_SAMPLE_SOURCES_TOTAL: Final[int] = 5
_SAMPLE_SOURCES_DONE: Final[int] = 2
_SAMPLE_PHASES_TOTAL: Final[int] = 40
_SAMPLE_PHASES_DONE: Final[int] = 18
_SAMPLE_COST_USD: Final[float] = 1.23
_SAMPLE_CEILING_USD: Final[float] = 5.0
_SAMPLE_ELAPSED_SECONDS: Final[int] = 432
_SAMPLE_STARTED_DELTA: Final[timedelta] = timedelta(minutes=7, seconds=12)


def _sample_stats_snapshot() -> StatsSnapshot:
    """Construit un ``StatsSnapshot`` réaliste pour les captures (RUNNING)."""
    now = datetime.now(tz=UTC)
    return StatsSnapshot(
        run_status=RunStatus.RUNNING,
        sources_total=_SAMPLE_SOURCES_TOTAL,
        sources_completed=_SAMPLE_SOURCES_DONE,
        phases_total=_SAMPLE_PHASES_TOTAL,
        phases_completed=_SAMPLE_PHASES_DONE,
        cost_usd_so_far=_SAMPLE_COST_USD,
        cost_ceiling_usd=_SAMPLE_CEILING_USD,
        started_at=now - _SAMPLE_STARTED_DELTA,
        finished_at=None,
        elapsed_seconds=float(_SAMPLE_ELAPSED_SECONDS),
        languages=_ALL_LANGUAGES,
    )


def _sample_cost_matrix() -> object:
    """Construit une ``CostMatrixSnapshot`` réaliste (3 sources × 8 phases)."""
    cols = (
        "0 STT",
        "1 Termes",
        "2 Gloss.",
        "3 Reform.",
        "4 Struct.",
        "5 Conso.",
        "6 Trad.",
        "7 Cohér.",
    )
    succeeded = PhaseStatus.SUCCEEDED
    running = PhaseStatus.RUNNING
    pending = PhaseStatus.PENDING
    skipped = PhaseStatus.SKIPPED

    def cell(status: PhaseStatus, cost: float | None) -> CostMatrixCell:
        return CostMatrixCell(status=status, cost_usd=cost)

    rows = (
        (
            "cours_01.mp4",
            (
                cell(succeeded, 0.04),
                cell(succeeded, 0.08),
                cell(skipped, 0.0),
                cell(succeeded, 0.21),
                cell(succeeded, 0.12),
                cell(pending, None),
                cell(pending, None),
                cell(pending, None),
            ),
        ),
        (
            "cours_02.mp4",
            (
                cell(succeeded, 0.05),
                cell(running, 0.03),
                cell(skipped, 0.0),
                cell(pending, None),
                cell(pending, None),
                cell(pending, None),
                cell(pending, None),
                cell(pending, None),
            ),
        ),
        (
            "notes.pdf",
            (
                cell(succeeded, 0.0),
                cell(succeeded, 0.06),
                cell(skipped, 0.0),
                cell(succeeded, 0.18),
                cell(succeeded, 0.10),
                cell(pending, None),
                cell(pending, None),
                cell(pending, None),
            ),
        ),
    )
    return build_cost_matrix(row_header="Source", column_labels=cols, rows=rows)


# ------------------------------------------------------------------ builders


def build_cockpit() -> QWidget:
    """Construit un composite cockpit (header + stats + matrice) pour capture."""
    root = QWidget()
    root.resize(_COCKPIT_WIDTH, _COCKPIT_HEIGHT)
    layout = QVBoxLayout(root)
    layout.setContentsMargins(8, 8, 8, 8)
    tabs = QTabWidget(root)
    page = QWidget()
    page_layout = QVBoxLayout(page)
    page_layout.setContentsMargins(0, 0, 0, 0)
    header = ProjectHeaderBar(page, show_export=True)
    strip = StatsStripWidget(page)
    strip.apply_snapshot(_sample_stats_snapshot())
    matrix = CostMatrixView(parent=page)
    matrix.apply_snapshot(_sample_cost_matrix())  # type: ignore[arg-type]
    page_layout.addWidget(header)
    page_layout.addWidget(strip)
    page_layout.addWidget(matrix, stretch=1)
    tabs.addTab(page, "Génération")
    tabs.addTab(QWidget(), "Supports pédagogiques")
    tabs.addTab(QWidget(), "Dialogue")
    layout.addWidget(tabs)
    return root


def build_generation_settings() -> QWidget:
    """Construit l'écran de réglages Génération (taille standard)."""
    dlg = GenerationSettingsView(probe_hardware())
    dlg.resize(_SETTINGS_DIALOG_WIDTH, _SETTINGS_DIALOG_HEIGHT)
    return dlg


def build_pedagogy_settings() -> QWidget:
    """Construit l'écran de réglages Supports pédagogiques."""
    dlg = PedagogySettingsView(available_languages=_ALL_LANGUAGES)
    dlg.resize(_SETTINGS_DIALOG_WIDTH, _SETTINGS_DIALOG_HEIGHT)
    return dlg


def build_chat_settings() -> QWidget:
    """Construit l'écran de réglages Dialogue."""
    dlg = ChatSettingsView()
    dlg.resize(_CHAT_SETTINGS_WIDTH, _CHAT_SETTINGS_HEIGHT)
    return dlg


def build_new_project() -> QWidget:
    """Construit le dialogue Nouveau projet."""
    dlg = NewProjectDialog()
    dlg.resize(_NEW_PROJECT_WIDTH, _NEW_PROJECT_HEIGHT)
    return dlg


def build_global_settings() -> QWidget:
    """Construit le dialogue Paramètres globaux (avec services en mémoire)."""
    app = QApplication.instance()
    assert isinstance(app, QApplication), (
        "QApplication doit être instanciée avant ce builder."
    )
    secrets = SecretsService(InMemorySecretsStore())
    # ThemeController nécessite un chemin pour la persistance ; on utilise un
    # temporaire (la préférence ne sera pas écrite tant qu'on n'appelle pas
    # set_mode — le builder se contente de construire le dialogue).
    tmp_dir = Path(tempfile.gettempdir())
    controller = ThemeController(app, tmp_dir / "fahmi2_capture_ui_prefs.json")
    dlg = GlobalSettingsDialog(secrets, theme_controller=controller)
    dlg.resize(_GLOBAL_SETTINGS_WIDTH, _GLOBAL_SETTINGS_HEIGHT)
    return dlg


#: Mapping ``nom de capture -> builder du widget``. L'ordre est conservé
#: (Python 3.7+) pour un ordre de génération déterministe.
_SCREEN_BUILDERS: Final[dict[str, Callable[[], QWidget]]] = {
    "cockpit": build_cockpit,
    "settings_generation": build_generation_settings,
    "settings_pedagogy": build_pedagogy_settings,
    "settings_chat": build_chat_settings,
    "settings_global": build_global_settings,
    "dialog_new_project": build_new_project,
}


# ------------------------------------------------------------------ runner


def _capture_widget(widget: QWidget, out: Path) -> None:
    """Force le polish + calcul de layout puis sauvegarde une capture PNG.

    Args:
        widget: Widget à capturer (peut être non montré).
        out: Chemin de sortie du PNG.
    """
    widget.ensurePolished()
    layout = widget.layout()
    if layout is not None:
        layout.activate()
    app = QApplication.instance()
    if app is not None:
        app.processEvents()
    out.parent.mkdir(parents=True, exist_ok=True)
    widget.grab().save(str(out))


def render_all(out_dir: Path) -> None:
    """Rend tous les écrans en clair et en sombre dans ``out_dir``.

    Args:
        out_dir: Dossier de sortie. Les fichiers sont placés sous
            ``out_dir/light/`` et ``out_dir/dark/``.
    """
    app = QApplication.instance() or QApplication([])
    for mode, subdir in _MODE_SUBDIR.items():
        for name, builder in _SCREEN_BUILDERS.items():
            apply_theme(app, mode)
            widget = builder()
            # Certains builders construisent un ``ThemeController`` qui
            # ré-applique le thème depuis la préférence persistée : on
            # ré-applique explicitement le mode désiré juste avant la
            # capture pour garantir la cohérence.
            apply_theme(app, mode)
            _capture_widget(widget, out_dir / subdir / f"{name}.png")
            print(f"Saved: {subdir}/{name}.png")


def main() -> None:
    """Point d'entrée CLI."""
    parser = argparse.ArgumentParser(
        description="Banc de capture UI Fahmi2 (light + dark)."
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(_DEFAULT_OUT_DIR),
        help="Dossier de sortie (défaut : %(default)s).",
    )
    args = parser.parse_args()
    render_all(args.out)


if __name__ == "__main__":
    main()
