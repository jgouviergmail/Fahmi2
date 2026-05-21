# Lot 1a — Finitions UI (case audio + visibilité des onglets)

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (inline, sans subagents).
> **Spec** : [`../specs/2026-05-21-corrections-lot1-design.md`](../specs/2026-05-21-corrections-lot1-design.md) §2.
> Steps en checkbox. Tout en français (accents). Travail directement sur `main`.

**Goal:** Exposer une case « Conserver les fichiers audio extraits » dans les
réglages de génération (#1) et styler la barre d'onglets pour distinguer les
onglets inactifs (#2).

**Architecture:** Deux changements UI indépendants, sans impact pipeline/domaine.
#1 = un `QCheckBox` câblé sur `GenerationSettings.delete_audio_after_stt` (champ déjà
existant). #2 = un bloc QSS `QTabWidget`/`QTabBar` dans le thème Clair Fluent.

**Tech Stack:** PySide6 (Qt Widgets), QSS, pytest-qt.

---

## Task 1 : #1 — Case « Conserver les fichiers audio extraits »

**Files:**
- Modify : `src/fahmi2/ui/dialogs/generation_settings_view.py`
- Test : `tests/unit/ui/test_generation_settings_view.py`

Contexte : `delete_audio_after_stt` est déjà un champ de `GenerationSettings`,
respecté par `Phase0SttHandler`. Le dialogue le code en dur à `True`
(`generation_settings_view.py:331`). On ajoute une case (libellé **positif** :
cocher = conserver), décochée par défaut (= comportement actuel : suppression).

- [ ] **Step 1 : Écrire les tests qui échouent**

Ajouter à la fin de `tests/unit/ui/test_generation_settings_view.py` :

```python
def test_create_mode_deletes_audio_by_default(qtbot: QtBot) -> None:
    view = GenerationSettingsView(_HW, initial=None)
    qtbot.addWidget(view)
    view._input_folder_input.setText("D:/Cours")  # noqa: SLF001 — satisfait la validation
    assert view._keep_audio_checkbox.isChecked() is False  # noqa: SLF001
    view._on_accept()  # noqa: SLF001
    result = view.get_generation_settings()
    assert result is not None
    assert result.delete_audio_after_stt is True  # case décochée → suppression


def test_keep_audio_checkbox_preserves_audio(qtbot: QtBot) -> None:
    view = GenerationSettingsView(_HW, initial=None)
    qtbot.addWidget(view)
    view._input_folder_input.setText("D:/Cours")  # noqa: SLF001
    view._keep_audio_checkbox.setChecked(True)  # noqa: SLF001
    view._on_accept()  # noqa: SLF001
    result = view.get_generation_settings()
    assert result is not None
    assert result.delete_audio_after_stt is False  # case cochée → conservation


def test_edit_mode_reflects_keep_audio(
    qtbot: QtBot, make_generation_settings: Any
) -> None:
    gen = make_generation_settings(delete_audio_after_stt=False)
    view = GenerationSettingsView(_HW, initial=gen)
    qtbot.addWidget(view)
    assert view._keep_audio_checkbox.isChecked() is True  # noqa: SLF001
```

- [ ] **Step 2 : Lancer les tests, vérifier l'échec**

Run : `.venv\Scripts\python.exe -m pytest tests/unit/ui/test_generation_settings_view.py -v`
Attendu : ÉCHEC (`AttributeError: ... '_keep_audio_checkbox'`).

- [ ] **Step 3 : Ajouter la constante de libellé**

Dans `generation_settings_view.py`, après `_DIRECTIVES_PLACEHOLDER` (ligne ~53),
ajouter :

```python
_KEEP_AUDIO_LABEL = "Conserver les fichiers audio extraits"
_KEEP_AUDIO_TOOLTIP = (
    "Si coché, les fichiers .wav extraits des vidéos ne sont pas supprimés "
    "après la transcription (utile pour réécouter / déboguer)."
)
```

- [ ] **Step 4 : Instancier la case dans `_build_fields`**

Dans `_build_fields`, juste après le bloc du `self._stt_combo`
(après `self._stt_combo.currentIndexChanged.connect(self._on_stt_changed)`),
ajouter :

```python
        self._keep_audio_checkbox = QCheckBox(_KEEP_AUDIO_LABEL, self)
        self._keep_audio_checkbox.setToolTip(_KEEP_AUDIO_TOOLTIP)
```

- [ ] **Step 5 : Ajouter la case à la page Transcription**

Dans `_build_stt_page`, après `form.addRow("Provider STT :", self._stt_combo)` :

```python
        form.addRow(self._keep_audio_checkbox)
```

- [ ] **Step 6 : Refléter l'état en mode édition (`_populate`)**

Dans `_populate`, après la ligne `stt_idx`/`setCurrentIndex` du combo STT
(avant `llm_idx`), ajouter :

```python
        self._keep_audio_checkbox.setChecked(not generation.delete_audio_after_stt)
```

- [ ] **Step 7 : Câbler la valeur dans `_on_accept`**

Dans `_on_accept`, remplacer la ligne :

```python
            delete_audio_after_stt=True,
```

par :

```python
            delete_audio_after_stt=not self._keep_audio_checkbox.isChecked(),
```

- [ ] **Step 8 : Lancer les tests, vérifier le succès**

Run : `.venv\Scripts\python.exe -m pytest tests/unit/ui/test_generation_settings_view.py -v`
Attendu : PASS (5 tests).

- [ ] **Step 9 : Vérifs qualité + commit**

```powershell
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m mypy src tests
```
Tous verts, puis :

```powershell
git add src/fahmi2/ui/dialogs/generation_settings_view.py tests/unit/ui/test_generation_settings_view.py
git commit -m @'
feat(ui): case « Conserver les fichiers audio extraits » dans les reglages

Expose le champ existant delete_audio_after_stt (decoche par defaut =
comportement actuel : suppression apres STT ; cocher conserve les .wav).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
'@
```

---

## Task 2 : #2 — Style des onglets (QSS)

**Files:**
- Modify : `src/fahmi2/ui/theme/light_fluent.qss`

Contexte : le QSS ne style pas `QTabBar` → les onglets inactifs se fondent dans le
fond. Le `QTabWidget` de `main_window` est le seul de l'app (la barre d'onglets de
fonctionnalité). QSS non testable unitairement : la vérification est la suite verte
+ un contrôle visuel.

- [ ] **Step 1 : Ajouter le bloc QSS des onglets**

Dans `light_fluent.qss`, insérer ce bloc **après** la section
« ===== Logs dock ===== » (juste avant « /* ===== Inputs, combobox, spinbox ===== */ ») :

```css
/* ===== Onglets de fonctionnalité (QTabWidget) ===== */
QTabWidget::pane {
    background-color: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    top: -1px;
}
QTabBar {
    background-color: transparent;
    qproperty-drawBase: 0;
}
QTabBar::tab {
    background-color: #eef0f4;
    color: #57606a;
    border: 1px solid #e5e7eb;
    border-bottom: none;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    padding: 8px 18px;
    margin-right: 4px;
    font-weight: 600;
}
QTabBar::tab:hover {
    background-color: #e3f0fb;
    color: #0a4f93;
}
QTabBar::tab:selected {
    background-color: #ffffff;
    color: #0078d4;
    border-color: #e5e7eb;
    border-bottom: 2px solid #0078d4;
}
```

- [ ] **Step 2 : Vérifier la non-régression (smoke tests + suite)**

Run : `.venv\Scripts\python.exe -m pytest tests/unit/ui -q`
Attendu : PASS (les smoke tests d'onglets/fenêtre instancient les widgets sans
erreur ; le QSS ne modifie pas le comportement).

- [ ] **Step 3 : Contrôle visuel (manuel)**

Lancer `.venv\Scripts\python.exe -m fahmi2.ui.app_main`, vérifier que l'onglet
inactif (« Supports pédagogiques » quand « Génération » est actif, et inversement)
est visuellement distinct (fond gris clair, libellé en gris) et que l'onglet actif
est blanc avec un soulignement accent bleu.

- [ ] **Step 4 : Vérifs qualité + commit**

```powershell
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m mypy src tests
```
Tous verts (aucun code Python modifié), puis :

```powershell
git add src/fahmi2/ui/theme/light_fluent.qss
git commit -m @'
feat(ui): styler la barre d'onglets (onglets inactifs visibles)

Ajoute des regles QSS QTabWidget/QTabBar au theme Clair Fluent : onglet inactif
sur fond gris clair, onglet selectionne blanc + soulignement accent.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
'@
```

---

## Clôture du Lot 1a

- [ ] Mettre à jour `CHANGELOG.md` (section « Non publié ») : entrées « Ajouté »
  (case conserver l'audio) et « Corrigé » (visibilité des onglets). Commit
  `docs(changelog): Lot 1a (case audio + onglets)`.
- [ ] Le **Lot 1b** (glossaire homogène) fera l'objet de son propre plan, rédigé
  contre le code à jour (cf. spec §3).

## Self-review

Couvre §2 du spec (#1 case audio dans les deux sens + reflet en édition ; #2 QSS
onglets). Pas de placeholder : code exact et chemins exacts. Types cohérents
(`_keep_audio_checkbox: QCheckBox`, `delete_audio_after_stt: bool`). `QCheckBox` est
déjà importé dans le module. Aucune dépendance vers un symbole non défini.
