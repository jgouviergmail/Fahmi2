# SP1 · Plan 02 — Coquille à onglets (abstraction fonctionnalité)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (exécution
> inline, par lots avec points de contrôle) — pas de subagents (préférence projet).
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transformer la zone projet en **onglets horizontaux** via une abstraction
« fonctionnalité » générique : onglet **Génération** (cockpit actuel déplacé,
`RunController` → `GenerationController` découplé du `MainWindow`) + onglet **Supports
pédagogiques** *stub*, sans changer le comportement de la génération.

**Architecture:** Nouveau package `ui/features/` (`FeatureId`, `FeatureTab`,
`FeatureRegistry` — calqué sur `PhaseRegistry`). `MainWindow` ne porte plus le cockpit :
il expose une `QTabWidget` peuplée par un `FeatureRegistry`, garde la sidebar + le
`LogsDock` partagés, et **dispatche** la sélection projet à chaque onglet
(`FeatureTab.on_project_selected`). Le `GenerationController` reçoit explicitement les
widgets qu'il pilote (header/stats/matrix/logs) + une fenêtre parente pour les dialogues.

**Tech Stack:** PySide6 (`QTabWidget`, `QWidget`), pytest-qt, ruff, mypy `--strict`.

**Rappels directives projet :** pas de magic value (constantes), docstrings Google
(Args/Returns/Raises) + docstring de module, réutiliser les patterns existants
(`PhaseRegistry`), DRY/YAGNI/KISS/SRP/SoC, nommage cohérent. Interpréteur :
`.venv\Scripts\python.exe`.

---

## Task 1 : Abstraction fonctionnalité (`FeatureId`, `FeatureTab`, `FeatureRegistry`)

**Files:**
- Create: `src/fahmi2/ui/features/__init__.py`
- Create: `src/fahmi2/ui/features/feature.py`
- Create: `src/fahmi2/ui/features/registry.py`
- Test: `tests/unit/ui/features/__init__.py`, `tests/unit/ui/features/test_feature_registry.py`

- [ ] **Step 1 : Écrire le test du registre (échoue)**

```python
# tests/unit/ui/features/test_feature_registry.py
"""Tests du ``FeatureRegistry``."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QLabel, QWidget

from fahmi2.domain.ids import ProjectId
from fahmi2.ui.features.feature import FeatureId, FeatureTab
from fahmi2.ui.features.registry import FeatureRegistry


class _StubTab(FeatureTab):
    def __init__(self, feature_id: FeatureId, title: str) -> None:
        self._feature_id = feature_id
        self._title = title
        self._widget = QLabel(title)
        self.selected: list[ProjectId | None] = []

    @property
    def feature_id(self) -> FeatureId:
        return self._feature_id

    @property
    def title(self) -> str:
        return self._title

    @property
    def widget(self) -> QWidget:
        return self._widget

    def on_project_selected(self, project_id: ProjectId | None) -> None:
        self.selected.append(project_id)


def test_registry_preserves_registration_order(qapp: object) -> None:
    del qapp
    gen = _StubTab(FeatureId.GENERATION, "Génération")
    ped = _StubTab(FeatureId.PEDAGOGY, "Supports")
    registry = FeatureRegistry([gen, ped])
    assert [t.feature_id for t in registry.ordered()] == [
        FeatureId.GENERATION,
        FeatureId.PEDAGOGY,
    ]


def test_registry_rejects_duplicate_feature_id(qapp: object) -> None:
    del qapp
    a = _StubTab(FeatureId.GENERATION, "A")
    b = _StubTab(FeatureId.GENERATION, "B")
    with pytest.raises(ValueError, match="already registered"):
        FeatureRegistry([a, b])


def test_default_on_project_selected_is_noop(qapp: object) -> None:
    del qapp

    class _Minimal(FeatureTab):
        @property
        def feature_id(self) -> FeatureId:
            return FeatureId.PEDAGOGY

        @property
        def title(self) -> str:
            return "X"

        @property
        def widget(self) -> QWidget:
            return QLabel("X")

    # Ne lève pas : implémentation par défaut = no-op.
    _Minimal().on_project_selected(ProjectId.new())
```

- [ ] **Step 2 : Lancer (échoue — modules absents)**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/ui/features/test_feature_registry.py -q`
Expected: FAIL — `ModuleNotFoundError: fahmi2.ui.features.feature`.

- [ ] **Step 3 : Créer `ui/features/__init__.py`**

```python
# src/fahmi2/ui/features/__init__.py
"""Abstraction des fonctionnalités de l'application (un onglet = une fonctionnalité)."""
```

- [ ] **Step 4 : Créer `feature.py`**

```python
# src/fahmi2/ui/features/feature.py
"""Contrats de l'abstraction « fonctionnalité » : ``FeatureId`` et ``FeatureTab``.

Chaque fonctionnalité de l'application (Génération, Supports pédagogiques, …) est
exposée comme un onglet implémentant ``FeatureTab``. Ajouter une fonctionnalité
revient à créer un ``FeatureTab`` et à l'enregistrer dans le ``FeatureRegistry`` —
sans modifier ``MainWindow`` ni l'entité ``Project``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import StrEnum

from PySide6.QtWidgets import QWidget

from fahmi2.domain.ids import ProjectId


class FeatureId(StrEnum):
    """Identifiants stables des fonctionnalités exposées en onglets."""

    GENERATION = "generation"
    PEDAGOGY = "pedagogy"


class FeatureTab(ABC):
    """Contrat d'un onglet de fonctionnalité.

    Une implémentation construit son propre widget et, le cas échéant, son
    contrôleur. ``on_project_selected`` est appelée par ``MainWindow`` à chaque
    changement de projet dans la sidebar ; l'implémentation par défaut est un
    no-op (les onglets qui n'en ont pas besoin n'ont rien à écrire).
    """

    @property
    @abstractmethod
    def feature_id(self) -> FeatureId:
        """Identifiant de la fonctionnalité."""

    @property
    @abstractmethod
    def title(self) -> str:
        """Libellé de l'onglet."""

    @property
    @abstractmethod
    def widget(self) -> QWidget:
        """Widget racine affiché dans l'onglet."""

    def on_project_selected(self, project_id: ProjectId | None) -> None:
        """Réagit à la sélection d'un projet dans la sidebar.

        Args:
            project_id: Projet sélectionné, ou ``None`` si désélection.
        """
```

- [ ] **Step 5 : Créer `registry.py`** (calqué sur `PhaseRegistry`)

```python
# src/fahmi2/ui/features/registry.py
"""``FeatureRegistry`` — enregistre les onglets de fonctionnalité dans l'ordre.

Calqué sur ``pipeline.phase_registry.PhaseRegistry`` : rejette deux enregistrements
pour le même ``FeatureId`` et restitue les onglets dans l'ordre d'enregistrement.
"""

from __future__ import annotations

from collections.abc import Iterable

from fahmi2.ui.features.feature import FeatureId, FeatureTab


class FeatureRegistry:
    """Enregistre et restitue les ``FeatureTab`` dans l'ordre d'enregistrement."""

    def __init__(self, tabs: Iterable[FeatureTab] = ()) -> None:
        """Construit le registre.

        Args:
            tabs: Onglets à enregistrer initialement.

        Raises:
            ValueError: Si deux onglets déclarent le même ``feature_id``.
        """
        self._by_id: dict[FeatureId, FeatureTab] = {}
        self._order: list[FeatureId] = []
        for tab in tabs:
            self.register(tab)

    def register(self, tab: FeatureTab) -> None:
        """Enregistre un onglet.

        Args:
            tab: Onglet à enregistrer.

        Raises:
            ValueError: Si ``feature_id`` est déjà enregistré.
        """
        if tab.feature_id in self._by_id:
            raise ValueError(
                f"FeatureTab already registered for {tab.feature_id}"
            )
        self._by_id[tab.feature_id] = tab
        self._order.append(tab.feature_id)

    def ordered(self) -> list[FeatureTab]:
        """Retourne les onglets dans l'ordre d'enregistrement.

        Returns:
            Liste ordonnée des onglets.
        """
        return [self._by_id[fid] for fid in self._order]
```

- [ ] **Step 6 : Créer `tests/unit/ui/features/__init__.py`** (paquet de test vide)

```python
```

- [ ] **Step 7 : Lancer (passe)**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/ui/features/test_feature_registry.py -q`
Expected: PASS (3 tests).

---

## Task 2 : Renommer `RunController` → `GenerationController` (découplé du `MainWindow`)

**Files:**
- Rename: `src/fahmi2/ui/run_controller.py` → `src/fahmi2/ui/generation_controller.py`
- Modify: `tests/unit/ui/test_log_event_mapping.py` (import)

- [ ] **Step 1 : Renommer le fichier (git mv)**

```bash
git mv src/fahmi2/ui/run_controller.py src/fahmi2/ui/generation_controller.py
```

- [ ] **Step 2 : Renommer la classe et le module-docstring**

Dans `generation_controller.py` : docstring de module `"""``RunController`` …"""` →
`"""``GenerationController`` — orchestration du lifecycle Run de l'onglet Génération.`
(garder le reste de la docstring). Remplacer `class RunController(QObject):` par
`class GenerationController(QObject):`. Mettre à jour `__all__` (dernière ligne) :
`__all__ = ["GenerationController", "build_default_registry", "build_ffmpeg_from_runtime"]`.

- [ ] **Step 3 : Réécrire le constructeur (widgets explicites, plus de `MainWindow`)**

Remplacer la signature + le corps du `__init__` (de `def __init__(` jusqu'à la fin du
bloc « Branchements UI ») par :

```python
    def __init__(
        self,
        *,
        header_bar: ProjectHeaderBar,
        stats_strip: StatsStripWidget,
        run_matrix: RunMatrixView,
        logs_dock: LogsDock,
        window: QWidget,
        project_service: ProjectService,
        secrets_service: SecretsService,
        hardware: HardwareInfo,
        state: SqliteState,
        app_paths: AppPaths,
    ) -> None:
        """Construit le contrôleur et branche les signaux du cockpit Génération.

        Args:
            header_bar: Barre de titre + actions du cockpit.
            stats_strip: Bande de statistiques.
            run_matrix: Matrice vidéos × phases.
            logs_dock: Dock de logs partagé (alimenté par cet onglet quand actif).
            window: Fenêtre parente, utilisée comme parent des dialogues modaux.
            project_service: Service projets.
            secrets_service: Service secrets.
            hardware: Info matérielle (pour valider STT local).
            state: Stockage SQLite.
            app_paths: Chemins applicatifs (cache modèles, override prompts).
        """
        super().__init__(window)
        self._header_bar = header_bar
        self._stats_strip = stats_strip
        self._run_matrix = run_matrix
        self._logs_dock = logs_dock
        self._window = window
        self._project_service = project_service
        self._secrets_service = secrets_service
        self._hardware = hardware
        self._state = state
        self._app_paths = app_paths

        self._current_project: Project | None = None
        self._active_worker_project_id: ProjectId | None = None
        self._current_run: Run | None = None
        self._current_pause_token: PauseToken | None = None
        self._worker: _RunWorker | None = None
        self._thread: QThread | None = None
        self._registry = build_default_registry()
        self._cleanup_after_cancel_requested: bool = False

        # Branchements UI (la sélection de projet est dispatchée par MainWindow
        # vers ``on_project_selected``).
        self._header_bar.start_requested.connect(self.start_run)
        self._header_bar.pause_requested.connect(self.pause_run)
        self._header_bar.resume_requested.connect(self.resume_run)
        self._header_bar.cancel_requested.connect(self.cancel_run)
        self._header_bar.open_output_requested.connect(self.open_output_folder)
        self._header_bar.estimate_cost_requested.connect(self.estimate_cost)
```

> Ce bloc **supprime** l'abonnement direct à la sidebar
> (`projects_sidebar.set_on_project_selected(...)`) : la sélection est désormais
> dispatchée par `MainWindow`. Les commentaires de doc des attributs
> `_current_project`/`_active_worker_project_id` restent valables (les recopier si on
> souhaite les conserver, sinon les omettre — comportement inchangé).

- [ ] **Step 4 : Rendre `_on_project_selected` public**

Renommer la méthode `def _on_project_selected(self, project_id: ProjectId) -> None:` en
`def on_project_selected(self, project_id: ProjectId) -> None:` (le `GenerationTab` y
délègue). Aucune autre référence interne n'existe (l'abonnement a été retiré).

- [ ] **Step 5 : Mettre à jour les imports du contrôleur**

Ajouter les imports des widgets désormais référencés directement et retirer celui de
`MainWindow` :

```python
from PySide6.QtWidgets import QApplication, QMessageBox, QWidget
...
from fahmi2.ui.widgets.logs_dock import LogsDock
from fahmi2.ui.widgets.project_header_bar import ProjectHeaderBar
from fahmi2.ui.widgets.run_matrix_view import RunMatrixView
from fahmi2.ui.widgets.stats_strip import StatsStripWidget
```

Retirer `from fahmi2.ui.main_window import MainWindow` et son usage (plus aucune
référence à `MainWindow` dans ce fichier après les remplacements du Step 6). Les
fonctions module-level `_show_cost_estimation_dialog(parent: MainWindow, ...)` et
`_to_log_event` : remplacer l'annotation `parent: MainWindow` par `parent: QWidget`.

- [ ] **Step 6 : Remplacer les accès `self._main_window.*` (remplacements globaux ordonnés)**

Dans l'ordre (chaque ligne = un `Edit replace_all` sur `generation_controller.py`) :

1. `self._main_window.header_bar` → `self._header_bar`
2. `self._main_window.run_matrix` → `self._run_matrix`
3. `self._main_window.stats_strip` → `self._stats_strip`
4. `self._main_window.logs_dock` → `self._logs_dock`
5. `self._main_window` → `self._window` *(ne reste plus que les parents de `QMessageBox` ; l'assignation et l'abonnement sidebar ont été supprimés au Step 3)*

- [ ] **Step 7 : Mettre à jour l'import du test de mapping**

Dans `tests/unit/ui/test_log_event_mapping.py` : remplacer
`from fahmi2.ui.run_controller import _format_technical_details, _to_log_event` par
`from fahmi2.ui.generation_controller import _format_technical_details, _to_log_event`.
(Idem la mention « run_controller » de la docstring du module → « generation_controller ».)

- [ ] **Step 8 : Vérifier l'import isolé**

Run: `.venv\Scripts\python.exe -c "import fahmi2.ui.generation_controller as m; print(m.GenerationController.__name__)"`
Expected: `GenerationController` (aucune `ImportError`). *(L'app ne se câble pas encore : `app_main` est mis à jour au Task 6.)*

---

## Task 3 : Onglet Génération (`GenerationTab`)

**Files:**
- Create: `src/fahmi2/ui/features/generation_tab.py`

- [ ] **Step 1 : Créer `generation_tab.py`**

```python
# src/fahmi2/ui/features/generation_tab.py
"""Onglet « Génération » — cockpit vidéos → document consolidé.

Construit le cockpit (barre de titre + bande de stats + matrice vidéos × phases) et
possède son ``GenerationController``. Le ``LogsDock`` partagé et la fenêtre parente
lui sont injectés.
"""

from __future__ import annotations

from PySide6.QtWidgets import QVBoxLayout, QWidget

from fahmi2.app.hardware_probe import HardwareInfo
from fahmi2.app.project_service import ProjectService
from fahmi2.app.secrets_service import SecretsService
from fahmi2.core.config.paths import AppPaths
from fahmi2.domain.ids import ProjectId
from fahmi2.infra.storage.sqlite_state import SqliteState
from fahmi2.ui.features.feature import FeatureId, FeatureTab
from fahmi2.ui.generation_controller import GenerationController
from fahmi2.ui.widgets.logs_dock import LogsDock
from fahmi2.ui.widgets.project_header_bar import ProjectHeaderBar
from fahmi2.ui.widgets.run_matrix_view import RunMatrixView
from fahmi2.ui.widgets.stats_strip import StatsStripWidget

_TAB_TITLE = "Génération"


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
        self._header_bar = ProjectHeaderBar(self._widget)
        self._stats_strip = StatsStripWidget(self._widget)
        self._run_matrix = RunMatrixView(parent=self._widget)
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
        """Libellé de l'onglet."""
        return _TAB_TITLE

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
```

---

## Task 4 : Onglet Supports pédagogiques (*stub*)

**Files:**
- Create: `src/fahmi2/ui/features/pedagogy_tab.py`

- [ ] **Step 1 : Créer `pedagogy_tab.py`**

```python
# src/fahmi2/ui/features/pedagogy_tab.py
"""Onglet « Supports pédagogiques » — stub (implémenté au sous-projet SP2).

Affiche un état « bientôt disponible » et un rappel du prérequis (un document
consolidé doit avoir été généré). Aucune logique ni réglage à ce stade.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from fahmi2.ui.features.feature import FeatureId, FeatureTab

_TAB_TITLE = "Supports pédagogiques"
_PLACEHOLDER_TITLE = "Bientôt disponible"
_PLACEHOLDER_HINT = (
    "Cette fonctionnalité générera des supports de révision (flashcards, QCM, "
    "fiches…) à partir du document consolidé produit par la Génération."
)


class PedagogyTab(FeatureTab):
    """Onglet stub de la fonctionnalité Supports pédagogiques."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Construit le widget stub.

        Args:
            parent: Parent Qt optionnel.
        """
        self._widget = QWidget(parent)
        layout = QVBoxLayout(self._widget)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title = QLabel(_PLACEHOLDER_TITLE, self._widget)
        title.setObjectName("pedagogyPlaceholderTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint = QLabel(_PLACEHOLDER_HINT, self._widget)
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(hint)

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
```

---

## Task 5 : `MainWindow` — zone centrale en `QTabWidget` + dispatch de sélection

**Files:**
- Modify: `src/fahmi2/ui/main_window.py`

- [ ] **Step 1 : Réécrire `main_window.py`**

```python
# src/fahmi2/ui/main_window.py
"""``MainWindow`` — cockpit principal (sidebar projets + onglets de fonctionnalité).

Layout :

- Sidebar gauche : liste des projets (transverse à toutes les fonctionnalités).
- Centre : ``QTabWidget`` peuplé par un ``FeatureRegistry`` (Génération, Supports
  pédagogiques, …).
- Dock bas : ``LogsDock`` partagé.
- Menus : Fichier, Édition, Affichage, ?.

La sélection d'un projet dans la sidebar est **dispatchée** à chaque onglet
(``FeatureTab.on_project_selected``).
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QMainWindow,
    QSplitter,
    QTabWidget,
    QWidget,
)

from fahmi2.domain.ids import ProjectId
from fahmi2.ui.features.registry import FeatureRegistry
from fahmi2.ui.widgets.logs_dock import LogsDock
from fahmi2.ui.widgets.projects_sidebar import ProjectsSidebar

_WINDOW_TITLE = "Fahmi2"
_SIDEBAR_WIDTH_PX = 220
_CENTRAL_WIDTH_PX = 980


class MainWindow(QMainWindow):
    """Fenêtre principale (sidebar projets + onglets de fonctionnalité)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Construit la fenêtre (onglets ajoutés ensuite via ``set_feature_tabs``).

        Args:
            parent: Parent Qt optionnel.
        """
        super().__init__(parent)
        self.setWindowTitle(_WINDOW_TITLE)
        self.resize(1200, 800)

        self._feature_registry: FeatureRegistry | None = None

        self._projects_sidebar = ProjectsSidebar(self)
        self._projects_sidebar.set_on_project_selected(self._dispatch_project_selected)

        self._tabs = QTabWidget(self)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.addWidget(self._projects_sidebar)
        splitter.addWidget(self._tabs)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([_SIDEBAR_WIDTH_PX, _CENTRAL_WIDTH_PX])
        self.setCentralWidget(splitter)

        self._logs_dock = LogsDock(self)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self._logs_dock)

        self._build_menus()

    def set_feature_tabs(self, registry: FeatureRegistry) -> None:
        """Peuple la zone centrale avec les onglets de fonctionnalité.

        Args:
            registry: Registre ordonné des onglets à afficher.
        """
        self._feature_registry = registry
        self._tabs.clear()
        for tab in registry.ordered():
            self._tabs.addTab(tab.widget, tab.title)

    @property
    def projects_sidebar(self) -> ProjectsSidebar:
        """Accès à la sidebar projets (lecture seule).

        Returns:
            La sidebar.
        """
        return self._projects_sidebar

    @property
    def logs_dock(self) -> LogsDock:
        """Accès au dock logs partagé.

        Returns:
            Le dock.
        """
        return self._logs_dock

    def _dispatch_project_selected(self, project_id: ProjectId) -> None:
        """Notifie chaque onglet de la sélection d'un projet.

        Args:
            project_id: Projet sélectionné dans la sidebar.
        """
        if self._feature_registry is None:
            return
        for tab in self._feature_registry.ordered():
            tab.on_project_selected(project_id)

    def set_on_open_settings(self, callback: Callable[[], None]) -> None:
        """Définit le callback du menu Édition > Paramètres globaux.

        Args:
            callback: Fonction sans argument.
        """
        self._open_settings_action.triggered.connect(callback)

    def set_on_open_prompts_editor(self, callback: Callable[[], None]) -> None:
        """Définit le callback du menu Édition > Modifier les prompts.

        Args:
            callback: Fonction sans argument.
        """
        self._open_prompts_action.triggered.connect(callback)

    def set_on_new_project(self, callback: Callable[[], None]) -> None:
        """Définit le callback du menu Fichier > Nouveau projet.

        Args:
            callback: Fonction sans argument.
        """
        self._new_project_action.triggered.connect(callback)

    def _build_menus(self) -> None:
        """Construit les menus principaux."""
        menubar = self.menuBar()
        assert menubar is not None

        file_menu = menubar.addMenu("Fichier")
        assert file_menu is not None
        self._new_project_action = QAction("Nouveau projet…", self)
        file_menu.addAction(self._new_project_action)
        file_menu.addSeparator()
        quit_action = QAction("Quitter", self)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        edit_menu = menubar.addMenu("Édition")
        assert edit_menu is not None
        self._open_settings_action = QAction("Paramètres globaux…", self)
        edit_menu.addAction(self._open_settings_action)
        self._open_prompts_action = QAction("Modifier les prompts…", self)
        edit_menu.addAction(self._open_prompts_action)

        help_menu = menubar.addMenu("?")
        assert help_menu is not None
        about_action = QAction("À propos", self)
        help_menu.addAction(about_action)
```

> Les propriétés `header_bar` / `stats_strip` / `run_matrix` **disparaissent** du
> `MainWindow` (elles vivent dans le `GenerationTab`). `_SIDEBAR_WIDTH_PX` /
> `_CENTRAL_WIDTH_PX` remplacent les valeurs en dur `220`/`980`.

---

## Task 6 : Câblage `app_main`

**Files:**
- Modify: `src/fahmi2/ui/app_main.py`

- [ ] **Step 1 : Mettre à jour les imports**

Remplacer `from fahmi2.ui.run_controller import RunController` par :

```python
from fahmi2.ui.features.generation_tab import GenerationTab
from fahmi2.ui.features.pedagogy_tab import PedagogyTab
from fahmi2.ui.features.registry import FeatureRegistry
```

- [ ] **Step 2 : Construire les onglets + le registre + brancher la fenêtre**

Remplacer le bloc de création du `RunController` (≈ lignes 65-75 : `window = MainWindow()`
… `run_controller = RunController(...)`) par :

```python
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
    pedagogy_tab = PedagogyTab(window)
    window.set_feature_tabs(FeatureRegistry([generation_tab, pedagogy_tab]))
    window.projects_sidebar.set_projects(project_service.list_projects())
```

> `apply_theme`/`window.show()`/`app.exec()` restent ; déplacer la création de
> `QApplication`/`window` ici si elle était plus bas (conserver un seul point de
> création). Le `generation_tab` doit rester référencé (cf. Step 4).

- [ ] **Step 3 : Adapter `_delete_project` au contrôleur de l'onglet**

Remplacer les usages de `run_controller` :

```python
            was_current = (
                generation_tab.controller.current_project_id == project_id
            )
            project_service.delete_project(project_id)
            _refresh_sidebar()
            if was_current:
                generation_tab.controller.clear_current_project()
```

- [ ] **Step 4 : Référence anti-GC**

Remplacer `window._run_controller = run_controller  # ...` par :

```python
    # Garde une référence pour éviter la collection par le GC PySide.
    window._generation_tab = generation_tab  # type: ignore[attr-defined]  # noqa: SLF001
```

- [ ] **Step 5 : Mettre à jour la docstring de module** : « ``MainWindow`` +
  ``RunController`` » → « ``MainWindow`` + onglets de fonctionnalité ».

---

## Task 7 : Tests UI (smoke onglets + mise à jour du smoke MainWindow)

**Files:**
- Modify: `tests/unit/ui/test_main_window_smoke.py`
- Create: `tests/unit/ui/features/test_tabs_smoke.py`

- [ ] **Step 1 : Mettre à jour `test_main_window_smoke.py`**

Remplacer `test_main_window_constructs_and_shows` (qui asserte `window.header_bar`
etc.) par une version cohérente avec la coquille :

```python
def test_main_window_constructs_and_shows(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    assert window.projects_sidebar is not None
    assert window.logs_dock is not None
```

(Conserver `test_main_window_exposes_prompts_editor_callback` et
`test_qt_event_bus_publishes_and_emits` tels quels.)

- [ ] **Step 2 : Écrire un smoke des onglets**

```python
# tests/unit/ui/features/test_tabs_smoke.py
"""Smoke tests des onglets de fonctionnalité (pytest-qt)."""

from __future__ import annotations

from pathlib import Path

from pytestqt.qtbot import QtBot

from fahmi2.app.hardware_probe import HardwareInfo
from fahmi2.app.project_service import ProjectService
from fahmi2.app.secrets_service import SecretsService
from fahmi2.core.config.paths import AppPaths
from fahmi2.infra.secrets.interface import InMemorySecretsStore
from fahmi2.infra.storage.sqlite_state import SqliteState
from fahmi2.ui.features.feature import FeatureId
from fahmi2.ui.features.generation_tab import GenerationTab
from fahmi2.ui.features.pedagogy_tab import PedagogyTab
from fahmi2.ui.features.registry import FeatureRegistry
from fahmi2.ui.main_window import MainWindow


def test_main_window_shows_two_feature_tabs(qtbot: QtBot, tmp_path: Path) -> None:
    state = SqliteState(tmp_path / "t.db")
    window = MainWindow()
    qtbot.addWidget(window)
    generation_tab = GenerationTab(
        logs_dock=window.logs_dock,
        window=window,
        project_service=ProjectService(state),
        secrets_service=SecretsService(InMemorySecretsStore()),
        hardware=HardwareInfo(cuda_available=False, gpu_name=None),
        state=state,
        app_paths=AppPaths.default(),
    )
    pedagogy_tab = PedagogyTab(window)
    window.set_feature_tabs(FeatureRegistry([generation_tab, pedagogy_tab]))

    assert generation_tab.feature_id is FeatureId.GENERATION
    assert pedagogy_tab.feature_id is FeatureId.PEDAGOGY
    assert window._tabs.count() == 2  # noqa: SLF001 — smoke d'assemblage


def test_pedagogy_tab_on_project_selected_is_noop(qtbot: QtBot) -> None:
    tab = PedagogyTab()
    qtbot.addWidget(tab.widget)
    tab.on_project_selected(None)  # ne lève pas
```

> Vérifier la signature réelle de `HardwareInfo` (champs `cuda_available`, `gpu_name`)
> dans `app/hardware_probe.py` et ajuster l'instanciation si besoin. Si `AppPaths.default()`
> a des effets de bord indésirables en test, remplacer par un `AppPaths` pointant sur
> `tmp_path` (constructeur réel à vérifier).

- [ ] **Step 3 : Lancer la suite UI**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/ui -q`
Expected: PASS.

---

## Task 8 : Passes qualité + commit

- [ ] **Step 1 : Suite complète**

Run: `.venv\Scripts\python.exe -m pytest -q`
Expected: PASS (tout).

- [ ] **Step 2 : Ruff**

Run: `.venv\Scripts\python.exe -m ruff check .`
Expected: `All checks passed!` (corriger sinon, notamment l'ordre des imports).

- [ ] **Step 3 : Mypy strict**

Run: `.venv\Scripts\python.exe -m mypy src tests`
Expected: `Success`. Vigilance : `window: QWidget` accepté comme parent `QObject`/dialog ;
`FeatureRegistry | None` narrowing dans `_dispatch_project_selected`.

- [ ] **Step 4 : Fumée manuelle (facultative, non bloquante)**

Run: `.venv\Scripts\python.exe -m fahmi2.ui.app_main`
Vérifier : deux onglets (Génération / Supports pédagogiques) ; l'onglet Génération se
comporte comme avant (sélection projet, aperçu, estimation, lancement, ouverture dossier) ;
l'onglet Supports affiche le placeholder.

- [ ] **Step 5 : Commit**

```bash
git add -A
git commit -m "feat(ui): coquille a onglets + GenerationController decouple (SP1/02)"
```

---

## Self-review (couverture spec SP1 — périmètre du plan 02)

- **§5.1 abstraction fonctionnalité** → Task 1. **§5.2 `MainWindow` en `QTabWidget` +
  sidebar/logs partagés** → Task 5. **§5.3 onglet Génération = cockpit déplacé +
  `RunController`→`GenerationController`** → Tasks 2-3. **§5.4 onglet pédagogique stub**
  → Task 4. **R1/R5 (chapeau)** couverts. La **vue de réglages master-detail** (§5.5) et
  la **création minimale** restent au **Plan 03**.
- Découplage : le `GenerationController` ne référence plus `MainWindow` ; la sélection
  projet passe par le dispatch générique → ajout d'un futur onglet = enregistrement dans
  le `FeatureRegistry`, sans toucher `MainWindow`.
