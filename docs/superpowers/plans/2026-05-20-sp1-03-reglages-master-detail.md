# SP1 · Plan 03 — Réglages master-detail + création minimale

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (exécution
> inline, par lots avec points de contrôle) — pas de subagents (préférence projet).
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Séparer l'identité du projet (nom + emplacement) de ses réglages de
génération : « Nouveau projet » devient **minimal** (nom + emplacement) ; les réglages
de génération s'éditent depuis l'onglet Génération via une **vue master-detail
réutilisable** (catégories à gauche, détail à droite) ; l'état `generation = None`
(« à configurer ») est rendu actionnable.

**Architecture:** Nouveau composant générique `SettingsView` (`QListWidget` +
`QStackedWidget`). Nouveau dialogue `GenerationSettingsView` composant 5 pages de
catégories à partir des champs existants. `NewProjectDialog` réduit à nom + emplacement.
Le cockpit Génération gagne un bouton « ⚙ Réglages » (signal `settings_requested`) qui
ouvre la vue ; le `GenerationController` persiste les réglages et rafraîchit le cockpit.

**Tech Stack:** PySide6 (`QListWidget`, `QStackedWidget`, `QDialog`), pytest-qt, ruff,
mypy `--strict`.

**Rappels directives projet :** pas de magic value (constantes), docstrings Google
(Args/Returns/Raises) + docstring de module, réutiliser les widgets existants
(`PhaseConfigsWidget`), DRY/YAGNI/KISS/SRP/SoC, nommage cohérent. Interpréteur :
`.venv\Scripts\python.exe`.

---

## Task 1 : Composant réutilisable `SettingsView` (master-detail)

**Files:**
- Create: `src/fahmi2/ui/widgets/settings_view.py`
- Test: `tests/unit/ui/test_settings_view.py`

- [ ] **Step 1 : Écrire le test (échoue)**

```python
# tests/unit/ui/test_settings_view.py
"""Tests du composant master-detail ``SettingsView``."""

from __future__ import annotations

from pytestqt.qtbot import QtBot
from PySide6.QtWidgets import QLabel

from fahmi2.ui.widgets.settings_view import SettingsView


def test_settings_view_lists_categories_and_switches(qtbot: QtBot) -> None:
    page_a = QLabel("A")
    page_b = QLabel("B")
    view = SettingsView([("Cat A", page_a), ("Cat B", page_b)])
    qtbot.addWidget(view)

    assert view.category_count() == 2
    assert view.current_index() == 0  # première catégorie sélectionnée par défaut

    view.set_current_index(1)
    assert view.current_index() == 1


def test_settings_view_empty_is_safe(qtbot: QtBot) -> None:
    view = SettingsView([])
    qtbot.addWidget(view)
    assert view.category_count() == 0
    assert view.current_index() == -1
```

- [ ] **Step 2 : Lancer (échoue — module absent)**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/ui/test_settings_view.py -q`
Expected: FAIL — `ModuleNotFoundError: fahmi2.ui.widgets.settings_view`.

- [ ] **Step 3 : Créer `settings_view.py`**

```python
# src/fahmi2/ui/widgets/settings_view.py
"""Composant ``SettingsView`` — réglages en master-detail (catégories + détail).

Liste de catégories à gauche (``QListWidget``), pages de détail à droite
(``QStackedWidget``). Réutilisable par toute fonctionnalité dont les réglages sont
nombreux, pour éviter une fenêtre surchargée.
"""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtWidgets import (
    QHBoxLayout,
    QListWidget,
    QStackedWidget,
    QWidget,
)

_CATEGORY_LIST_WIDTH_PX = 180


class SettingsView(QWidget):
    """Vue de réglages master-detail (catégories à gauche, détail à droite)."""

    def __init__(
        self,
        categories: Sequence[tuple[str, QWidget]],
        parent: QWidget | None = None,
    ) -> None:
        """Construit la vue.

        Args:
            categories: Séquence ordonnée ``(libellé, page)``.
            parent: Parent Qt optionnel.
        """
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._list = QListWidget(self)
        self._list.setObjectName("settingsCategoryList")
        self._list.setFixedWidth(_CATEGORY_LIST_WIDTH_PX)
        self._stack = QStackedWidget(self)

        for label, page in categories:
            self._list.addItem(label)
            self._stack.addWidget(page)

        self._list.currentRowChanged.connect(self._stack.setCurrentIndex)
        layout.addWidget(self._list)
        layout.addWidget(self._stack, stretch=1)

        if categories:
            self._list.setCurrentRow(0)

    def category_count(self) -> int:
        """Retourne le nombre de catégories.

        Returns:
            Le nombre de pages enregistrées.
        """
        return self._list.count()

    def current_index(self) -> int:
        """Retourne l'index de la catégorie courante (``-1`` si vide).

        Returns:
            Index courant.
        """
        return self._list.currentRow()

    def set_current_index(self, index: int) -> None:
        """Sélectionne la catégorie d'index ``index``.

        Args:
            index: Index de catégorie.
        """
        self._list.setCurrentRow(index)
```

- [ ] **Step 4 : Lancer (passe)**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/ui/test_settings_view.py -q`
Expected: PASS (2 tests).

---

## Task 2 : Dialogue `GenerationSettingsView`

**Files:**
- Create: `src/fahmi2/ui/dialogs/generation_settings_view.py`
- Test: `tests/unit/ui/test_generation_settings_view.py`

- [ ] **Step 1 : Écrire le test (échoue)**

```python
# tests/unit/ui/test_generation_settings_view.py
"""Tests du dialogue ``GenerationSettingsView``."""

from __future__ import annotations

from pathlib import Path

from pytestqt.qtbot import QtBot

from fahmi2.app.hardware_probe import HardwareInfo
from fahmi2.domain.enums import Language
from fahmi2.ui.dialogs.generation_settings_view import GenerationSettingsView

_HW = HardwareInfo(cuda_available=False, gpu_name="", cuda_version="")


def test_create_mode_requires_input_folder(qtbot: QtBot) -> None:
    view = GenerationSettingsView(_HW, initial=None)
    qtbot.addWidget(view)
    # Aucun dossier d'entrée renseigné -> _on_accept ne valide pas.
    view._on_accept()  # noqa: SLF001
    assert view.get_generation_settings() is None


def test_edit_mode_prefills_and_returns(
    qtbot: QtBot, make_generation_settings: object
) -> None:
    gen = make_generation_settings(  # type: ignore[operator]
        input_folder=Path("D:/Cours"),
        output_languages=(Language.FR, Language.EN),
    )
    view = GenerationSettingsView(_HW, initial=gen)
    qtbot.addWidget(view)
    view._on_accept()  # noqa: SLF001
    result = view.get_generation_settings()
    assert result is not None
    assert result.input_folder == Path("D:/Cours")
    assert Language.EN in result.output_languages
```

- [ ] **Step 2 : Lancer (échoue — module absent)**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/ui/test_generation_settings_view.py -q`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3 : Créer `generation_settings_view.py`**

```python
# src/fahmi2/ui/dialogs/generation_settings_view.py
"""Dialogue ``GenerationSettingsView`` — réglages de génération (master-detail).

Réorganise les réglages de la fonctionnalité Génération en catégories (Entrée &
langues, Style, Transcription, Modèle & coût, Phases) via le composant
``SettingsView``. Produit un ``GenerationSettings`` (sans nom ni emplacement, qui
relèvent du ``Project``).
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from fahmi2.app.hardware_probe import HardwareInfo
from fahmi2.domain.enums import Language, LLMModel, SttProvider, StylePreset
from fahmi2.domain.generation import GenerationSettings, ParallelismConfig
from fahmi2.ui.widgets.phase_configs_widget import PhaseConfigsWidget
from fahmi2.ui.widgets.settings_view import SettingsView

_DIALOG_WIDTH_PX = 760
_DIALOG_HEIGHT_PX = 620
_DIRECTIVES_HEIGHT_PX = 90
_COST_CEILING_MAX_USD = 10_000.0

_TITLE_CREATE = "Configurer la génération"
_TITLE_EDIT = "Réglages de la génération"

_CAT_INPUT = "Entrée & langues"
_CAT_STYLE = "Style"
_CAT_STT = "Transcription"
_CAT_MODEL = "Modèle & coût"
_CAT_PHASES = "Phases (1–7)"

_DIRECTIVES_PLACEHOLDER = (
    "Directives libres pour orienter la reformulation. Ex : « ton chaleureux mais "
    "rigoureux, exemples concrets, éviter le jargon inutile »."
)


class GenerationSettingsView(QDialog):
    """Dialogue d'édition des réglages de génération (master-detail)."""

    def __init__(
        self,
        hardware: HardwareInfo,
        parent: QWidget | None = None,
        *,
        initial: GenerationSettings | None = None,
    ) -> None:
        """Construit le dialogue.

        Args:
            hardware: Info matérielle (pour bloquer STT local sans GPU CUDA).
            parent: Parent Qt optionnel.
            initial: Réglages pré-remplis (mode édition) ou ``None`` (création).
        """
        super().__init__(parent)
        self._hardware = hardware
        self._is_edit_mode = initial is not None
        self.setWindowTitle(_TITLE_EDIT if self._is_edit_mode else _TITLE_CREATE)
        self.resize(_DIALOG_WIDTH_PX, _DIALOG_HEIGHT_PX)
        self._result: GenerationSettings | None = None

        self._build_fields()
        settings_view = SettingsView(
            [
                (_CAT_INPUT, self._build_input_page()),
                (_CAT_STYLE, self._build_style_page()),
                (_CAT_STT, self._build_stt_page()),
                (_CAT_MODEL, self._build_model_page()),
                (_CAT_PHASES, self._build_phases_page()),
            ],
            self,
        )

        button_label = (
            QDialogButtonBox.StandardButton.Save
            if self._is_edit_mode
            else QDialogButtonBox.StandardButton.Ok
        )
        buttons = QDialogButtonBox(
            button_label | QDialogButtonBox.StandardButton.Cancel, parent=self
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)

        outer = QVBoxLayout(self)
        outer.addWidget(settings_view, stretch=1)
        outer.addWidget(buttons)

        if initial is not None:
            self._populate(initial)

    def get_generation_settings(self) -> GenerationSettings | None:
        """Retourne les réglages construits, ou ``None`` si annulation/invalide.

        Returns:
            ``GenerationSettings`` ou ``None``.
        """
        return self._result

    # ------------------------------------------------------------------ champs

    def _build_fields(self) -> None:
        """Instancie tous les widgets de champ (avant répartition en pages)."""
        self._input_folder_input = QLineEdit(self)
        self._input_folder_input.setReadOnly(True)
        self._browse_btn = QPushButton("Parcourir…", self)
        self._browse_btn.clicked.connect(self._browse_input_folder)

        self._source_lang_combo = QComboBox(self)
        for lang in Language:
            self._source_lang_combo.addItem(lang.value, lang)

        self._output_langs: dict[Language, QCheckBox] = {}
        for lang in Language:
            cb = QCheckBox(lang.value, self)
            cb.setChecked(lang is Language.FR)
            self._output_langs[lang] = cb

        self._style_combo = QComboBox(self)
        for style in StylePreset:
            self._style_combo.addItem(style.value, style)

        self._style_directives_input = QTextEdit(self)
        self._style_directives_input.setPlaceholderText(_DIRECTIVES_PLACEHOLDER)
        self._style_directives_input.setFixedHeight(_DIRECTIVES_HEIGHT_PX)
        self._style_directives_input.setAcceptRichText(False)

        self._stt_combo = QComboBox(self)
        for provider in SttProvider:
            self._stt_combo.addItem(provider.value, provider)
        self._stt_combo.currentIndexChanged.connect(self._on_stt_changed)

        self._llm_combo = QComboBox(self)
        for model in LLMModel:
            self._llm_combo.addItem(model.value, model)

        self._cost_ceiling_input = QDoubleSpinBox(self)
        self._cost_ceiling_input.setRange(0.0, _COST_CEILING_MAX_USD)
        self._cost_ceiling_input.setDecimals(2)
        self._cost_ceiling_input.setValue(0.0)
        self._cost_ceiling_input.setSuffix(" $")
        self._cost_ceiling_input.setSpecialValueText("Pas de plafond")

        self._phase_configs_widget = PhaseConfigsWidget(self)

    # ------------------------------------------------------------------- pages

    def _build_input_page(self) -> QWidget:
        page = QWidget(self)
        form = QFormLayout(page)
        folder_row = QHBoxLayout()
        folder_row.addWidget(self._input_folder_input)
        folder_row.addWidget(self._browse_btn)
        form.addRow("Dossier des vidéos :", folder_row)
        form.addRow("Langue source :", self._source_lang_combo)
        langs_row = QHBoxLayout()
        for cb in self._output_langs.values():
            langs_row.addWidget(cb)
        langs_row.addStretch(1)
        form.addRow("Langues de sortie :", langs_row)
        return page

    def _build_style_page(self) -> QWidget:
        page = QWidget(self)
        form = QFormLayout(page)
        form.addRow("Style :", self._style_combo)
        form.addRow("Directives stylistiques :", self._style_directives_input)
        return page

    def _build_stt_page(self) -> QWidget:
        page = QWidget(self)
        form = QFormLayout(page)
        form.addRow("Provider STT :", self._stt_combo)
        return page

    def _build_model_page(self) -> QWidget:
        page = QWidget(self)
        form = QFormLayout(page)
        form.addRow("Modèle LLM :", self._llm_combo)
        form.addRow("Plafond budget :", self._cost_ceiling_input)
        return page

    def _build_phases_page(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.addWidget(self._phase_configs_widget)
        return page

    # ----------------------------------------------------------------- actions

    def _browse_input_folder(self) -> None:
        """Ouvre un sélecteur de dossier des vidéos."""
        folder = QFileDialog.getExistingDirectory(self, "Dossier des vidéos")
        if folder:
            self._input_folder_input.setText(folder)

    def _on_stt_changed(self, index: int) -> None:
        """Bloque ``faster_whisper_local`` sans GPU CUDA.

        Args:
            index: Index sélectionné dans le combo STT.
        """
        provider = self._stt_combo.itemData(index)
        if (
            provider is SttProvider.FASTER_WHISPER_LOCAL
            and not self._hardware.cuda_available
        ):
            QMessageBox.warning(
                self,
                "GPU NVIDIA introuvable",
                "Le mode de transcription locale nécessite un GPU NVIDIA "
                "compatible CUDA.\n\nVeuillez utiliser le mode OpenAI cloud.",
            )
            cloud_index = self._stt_combo.findData(SttProvider.OPENAI_CLOUD)
            if cloud_index >= 0:
                self._stt_combo.setCurrentIndex(cloud_index)

    def _populate(self, generation: GenerationSettings) -> None:
        """Pré-remplit les champs depuis des réglages existants.

        Args:
            generation: Réglages à éditer.
        """
        self._input_folder_input.setText(str(generation.input_folder))
        src_idx = self._source_lang_combo.findData(generation.source_language)
        if src_idx >= 0:
            self._source_lang_combo.setCurrentIndex(src_idx)
        for lang, cb in self._output_langs.items():
            cb.setChecked(lang in generation.output_languages)
        style_idx = self._style_combo.findData(generation.style_preset)
        if style_idx >= 0:
            self._style_combo.setCurrentIndex(style_idx)
        self._style_directives_input.setPlainText(generation.style_directives)
        stt_idx = self._stt_combo.findData(generation.stt_provider)
        if stt_idx >= 0:
            self._stt_combo.setCurrentIndex(stt_idx)
        llm_idx = self._llm_combo.findData(generation.llm_model)
        if llm_idx >= 0:
            self._llm_combo.setCurrentIndex(llm_idx)
        self._cost_ceiling_input.setValue(generation.cost_ceiling_usd or 0.0)
        self._phase_configs_widget.set_phase_configs(generation.phases_config)

    def _on_accept(self) -> None:
        """Valide la saisie et construit le ``GenerationSettings``."""
        input_folder_text = self._input_folder_input.text().strip()
        if not input_folder_text:
            QMessageBox.warning(
                self,
                "Dossier des vidéos manquant",
                "Veuillez sélectionner le dossier contenant les vidéos.",
            )
            return
        source_lang = self._source_lang_combo.currentData()
        output_langs = tuple(
            lang for lang, cb in self._output_langs.items() if cb.isChecked()
        )
        if source_lang not in output_langs:
            output_langs = (source_lang, *output_langs)
        cost_ceiling = (
            self._cost_ceiling_input.value()
            if self._cost_ceiling_input.value() > 0
            else None
        )
        self._result = GenerationSettings(
            input_folder=Path(input_folder_text),
            source_language=source_lang,
            output_languages=output_langs,
            style_preset=self._style_combo.currentData(),
            style_directives=self._style_directives_input.toPlainText().strip(),
            stt_provider=self._stt_combo.currentData(),
            llm_model=self._llm_combo.currentData(),
            phases_config=self._phase_configs_widget.get_phase_configs(),
            cost_ceiling_usd=cost_ceiling,
            parallelism=ParallelismConfig(),
            delete_audio_after_stt=True,
        )
        self.accept()
```

- [ ] **Step 4 : Lancer (passe)**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/ui/test_generation_settings_view.py -q`
Expected: PASS (2 tests).

---

## Task 3 : `NewProjectDialog` minimal (nom + emplacement)

**Files:**
- Modify (réécriture complète): `src/fahmi2/ui/dialogs/new_project_dialog.py`
- Test: `tests/unit/ui/test_new_project_dialog.py`

- [ ] **Step 1 : Écrire le test (échoue car API change)**

```python
# tests/unit/ui/test_new_project_dialog.py
"""Tests du dialogue minimal ``NewProjectDialog`` (nom + emplacement)."""

from __future__ import annotations

from pathlib import Path

from pytestqt.qtbot import QtBot

from fahmi2.ui.dialogs.new_project_dialog import NewProjectDialog


def test_create_mode_returns_name_and_workspace(qtbot: QtBot) -> None:
    dialog = NewProjectDialog()
    qtbot.addWidget(dialog)
    dialog._name_input.setText("Cours de macro")  # noqa: SLF001
    dialog._workspace_input.setText("D:/Projets/Macro")  # noqa: SLF001
    dialog._on_accept()  # noqa: SLF001
    assert dialog.get_name() == "Cours de macro"
    assert dialog.get_workspace_folder() == Path("D:/Projets/Macro")


def test_create_mode_requires_both_fields(qtbot: QtBot) -> None:
    dialog = NewProjectDialog()
    qtbot.addWidget(dialog)
    dialog._name_input.setText("Sans emplacement")  # noqa: SLF001
    dialog._on_accept()  # noqa: SLF001
    assert dialog.get_name() is None


def test_edit_mode_makes_workspace_read_only(qtbot: QtBot) -> None:
    dialog = NewProjectDialog(
        initial_name="Existant", initial_workspace=Path("D:/WS")
    )
    qtbot.addWidget(dialog)
    assert dialog._workspace_input.isReadOnly()  # noqa: SLF001
    assert dialog._name_input.text() == "Existant"  # noqa: SLF001
```

- [ ] **Step 2 : Lancer (échoue)**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/ui/test_new_project_dialog.py -q`
Expected: FAIL (ancienne API : pas de `_workspace_input` ni constructeur sans `hardware`).

- [ ] **Step 3 : Réécrire `new_project_dialog.py`**

```python
# src/fahmi2/ui/dialogs/new_project_dialog.py
"""Dialogue ``NewProjectDialog`` — création/renommage minimal d'un projet.

Ne porte que l'**identité** du projet : nom + emplacement (``workspace_folder``).
Les réglages de génération s'éditent depuis l'onglet Génération
(``GenerationSettingsView``). En mode édition, l'emplacement est en lecture seule
(immuable après création).
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

_DIALOG_WIDTH_PX = 520
_TITLE_CREATE = "Nouveau projet"
_TITLE_EDIT = "Renommer le projet"


class NewProjectDialog(QDialog):
    """Dialogue minimal : nom + emplacement du projet."""

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        initial_name: str | None = None,
        initial_workspace: Path | None = None,
    ) -> None:
        """Construit le dialogue.

        Args:
            parent: Parent Qt optionnel.
            initial_name: Nom pré-rempli (mode édition).
            initial_workspace: Emplacement pré-rempli (mode édition, lecture seule).
        """
        super().__init__(parent)
        self._is_edit_mode = initial_name is not None
        self.setWindowTitle(_TITLE_EDIT if self._is_edit_mode else _TITLE_CREATE)
        self.setMinimumWidth(_DIALOG_WIDTH_PX)
        self._result_name: str | None = None
        self._result_workspace: Path | None = None

        form = QFormLayout()
        self._name_input = QLineEdit(self)
        form.addRow("Nom :", self._name_input)

        self._workspace_input = QLineEdit(self)
        self._workspace_input.setReadOnly(True)
        self._browse_btn = QPushButton("Parcourir…", self)
        self._browse_btn.clicked.connect(self._browse_workspace)
        ws_row = QHBoxLayout()
        ws_row.addWidget(self._workspace_input)
        ws_row.addWidget(self._browse_btn)
        form.addRow("Emplacement :", ws_row)

        button_label = (
            QDialogButtonBox.StandardButton.Save
            if self._is_edit_mode
            else QDialogButtonBox.StandardButton.Ok
        )
        buttons = QDialogButtonBox(
            button_label | QDialogButtonBox.StandardButton.Cancel, parent=self
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)

        outer = QVBoxLayout(self)
        outer.addLayout(form)
        outer.addWidget(buttons)

        if initial_name is not None:
            self._name_input.setText(initial_name)
        if initial_workspace is not None:
            self._workspace_input.setText(str(initial_workspace))
        if self._is_edit_mode:
            # Emplacement immuable après création : on désactive sa modification.
            self._browse_btn.setEnabled(False)

    def get_name(self) -> str | None:
        """Retourne le nom saisi, ou ``None`` si annulation/invalide.

        Returns:
            Le nom du projet, ou ``None``.
        """
        return self._result_name

    def get_workspace_folder(self) -> Path | None:
        """Retourne l'emplacement, ou ``None`` si annulation/invalide.

        Returns:
            Le ``workspace_folder``, ou ``None``.
        """
        return self._result_workspace

    def _browse_workspace(self) -> None:
        """Ouvre un sélecteur de dossier d'emplacement."""
        folder = QFileDialog.getExistingDirectory(self, "Emplacement du projet")
        if folder:
            self._workspace_input.setText(folder)

    def _on_accept(self) -> None:
        """Valide la saisie (nom + emplacement) et clôt le dialogue."""
        name = self._name_input.text().strip()
        workspace_text = self._workspace_input.text().strip()
        if not name or not workspace_text:
            QMessageBox.warning(
                self,
                "Champs manquants",
                "Veuillez renseigner le nom et l'emplacement du projet.",
            )
            return
        self._result_name = name
        self._result_workspace = Path(workspace_text)
        self.accept()
```

- [ ] **Step 4 : Lancer (passe)**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/ui/test_new_project_dialog.py -q`
Expected: PASS (3 tests).

---

## Task 4 : `ProjectHeaderBar` — bouton « ⚙ Réglages »

**Files:**
- Modify: `src/fahmi2/ui/widgets/project_header_bar.py`

- [ ] **Step 1 : Ajouter le signal + le bouton**

Ajouter le signal après les signaux existants :

```python
    settings_requested = Signal()
```

Dans `__init__`, créer le bouton (avant `self._start_button`) et le brancher :

```python
        self._settings_button = self._make_button("⚙  Réglages", role="default")
        self._settings_button.setToolTip(
            "Configurer les réglages de génération (entrée, langues, style, "
            "transcription, modèle, phases)."
        )
        self._settings_button.clicked.connect(self.settings_requested)
```

Ajouter `self._settings_button` à la boucle d'ajout au layout (en tête, avant
`self._estimate_cost_button`) :

```python
        for btn in (
            self._settings_button,
            self._estimate_cost_button,
            self._start_button,
            self._pause_button,
            self._resume_button,
            self._cancel_button,
            self._open_output_button,
        ):
            layout.addWidget(btn)
```

> Le bouton Réglages reste **toujours actif** (indépendant des états idle/running) :
> ne pas le toucher dans `set_idle/set_running/set_paused/set_finished`.

---

## Task 5 : `GenerationController` — ouvrir/persister les réglages de génération

**Files:**
- Modify: `src/fahmi2/ui/generation_controller.py`

- [ ] **Step 1 : Importer `GenerationSettingsView` et `QDialog`**

Ajouter `QDialog` à l'import `from PySide6.QtWidgets import ...` et :

```python
from fahmi2.ui.dialogs.generation_settings_view import GenerationSettingsView
```

- [ ] **Step 2 : Brancher le signal dans le constructeur**

Après `self._header_bar.estimate_cost_requested.connect(self.estimate_cost)`, ajouter :

```python
        self._header_bar.settings_requested.connect(self.open_generation_settings)
```

- [ ] **Step 3 : Ajouter la méthode `open_generation_settings`**

L'insérer près de `estimate_cost` (zone des slots) :

```python
    def open_generation_settings(self) -> None:
        """Ouvre la vue de réglages de génération et persiste le résultat.

        Si aucun projet n'est sélectionné, affiche un avertissement. Sinon ouvre
        ``GenerationSettingsView`` (pré-rempli si déjà configuré), persiste le
        ``GenerationSettings`` mis à jour sur le projet et rafraîchit le cockpit.
        """
        if self._current_project is None:
            QMessageBox.warning(
                self._window,
                "Aucun projet sélectionné",
                "Sélectionne un projet dans la sidebar avant de configurer la "
                "génération.",
            )
            return
        project = self._current_project
        dialog = GenerationSettingsView(
            self._hardware, parent=self._window, initial=project.generation
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        generation = dialog.get_generation_settings()
        if generation is None:
            return
        updated = Project(
            id=project.id,
            name=project.name,
            workspace_folder=project.workspace_folder,
            created_at=project.created_at,
            last_run_at=project.last_run_at,
            runs=project.runs,
            generation=generation,
        )
        self._project_service.update_project(updated)
        self.on_project_selected(project.id)
```

> `Project` et `QMessageBox` sont déjà importés. `on_project_selected` recharge le
> projet depuis le service et rafraîchit l'aperçu (vidéos désormais configurées).

---

## Task 6 : Câblage `app_main` (création minimale + renommage)

**Files:**
- Modify: `src/fahmi2/ui/app_main.py`

- [ ] **Step 1 : `_open_new_project` — dialogue minimal**

Remplacer le corps par :

```python
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
```

> `create_project` est appelé **sans** `generation` (→ `None`). `hardware` n'est plus
> passé au dialogue (devenu minimal).

- [ ] **Step 2 : `_edit_project` — renommage minimal**

Remplacer le corps par :

```python
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
        updated = Project(
            id=project.id,
            name=new_name,
            workspace_folder=project.workspace_folder,
            created_at=project.created_at,
            last_run_at=project.last_run_at,
            runs=project.runs,
            generation=project.generation,
        )
        project_service.update_project(updated)
        _refresh_sidebar()
        window.projects_sidebar.select_project(updated.id)
```

- [ ] **Step 3 : Nettoyer les imports devenus inutiles**

`hardware` reste utilisé par `GenerationTab` (inchangé). Vérifier qu'aucun import
n'est devenu inutilisé (ruff le signalera). La docstring de module reste valable.

---

## Task 7 : Suite UI + intégration

- [ ] **Step 1 : Lancer la suite UI**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/ui -q`
Expected: PASS (dont les 3 nouveaux fichiers de test).

---

## Task 8 : Passes qualité + commit

- [ ] **Step 1 : Suite complète**

Run: `.venv\Scripts\python.exe -m pytest -q`
Expected: PASS (tout).

- [ ] **Step 2 : Ruff**

Run: `.venv\Scripts\python.exe -m ruff check .`
Expected: `All checks passed!` (corriger imports/longueurs sinon).

- [ ] **Step 3 : Mypy strict**

Run: `.venv\Scripts\python.exe -m mypy src tests`
Expected: `Success`. Vigilance : `currentData()` renvoie `Any` → caster si mypy
réclame un type précis pour `source_lang`/`style`/`stt_provider`/`llm_model`
(utiliser des annotations locales explicites si nécessaire, ex.
`source_lang: Language = self._source_lang_combo.currentData()`).

- [ ] **Step 4 : Fumée manuelle (facultative, non bloquante)**

Run: `.venv\Scripts\python.exe -m fahmi2.ui.app_main`
Vérifier : « Nouveau projet » ne demande que nom + emplacement ; le cockpit affiche
l'état « à configurer » ; « ⚙ Réglages » ouvre la vue master-detail (5 catégories) ;
après configuration, l'aperçu des vidéos apparaît ; « Lancer » fonctionne.

- [ ] **Step 5 : Commit**

```bash
git add -A
git commit -m "feat(ui): reglages generation en master-detail + creation minimale (SP1/03)"
```

---

## Self-review (couverture spec SP1 — périmètre du plan 03)

- **§5.5 composant master-detail réutilisable** → Task 1 (`SettingsView`). **Réglages
  Génération réorganisés** → Task 2 (`GenerationSettingsView`). **Création minimale
  (nom + emplacement)** → Task 3 (`NewProjectDialog`) + Task 6. **État `generation = None`
  actionnable** → Tasks 4-5 (bouton « ⚙ Réglages » + `open_generation_settings`).
- **Immuabilité de l'emplacement** (décision Plan 01) : matérialisée par le champ
  emplacement en lecture seule en mode édition (Task 3).
- **R7 (chapeau)** couvert. Reste au **Plan 04** : câblage final éventuel, docs
  (`docs/`, `README`, `CLAUDE.md`), passes de vérification finales et clôture de la
  matrice de traçabilité SP1.
