# Lot 6 — UI : sélecteur de mode + note d'ordre sans effet

> Sous-skill d'exécution : superpowers:executing-plans. Étapes en `- [ ]`.
> **Dépend de** : Lot 1.

**But du lot :** Exposer le choix `ORDERED` / `THEMATIC` dans les réglages de
génération, et signaler que l'ordre des sources n'a pas d'effet en thématique.

---

### Task 6.1 : Sélecteur de mode dans `GenerationSettingsView`

**Files:**
- Modify: `src/fahmi2/ui/_model_labels.py` (libellés FR du mode)
- Modify: `src/fahmi2/ui/dialogs/generation_settings_view.py`
- Test: `tests/unit/ui/dialogs/test_generation_settings_view.py` (smoke pytest-qt)

- [ ] **Step 1 : Test smoke — choisir THEMATIC produit le bon réglage**

```python
def test_consolidation_mode_selectable(qtbot: Any, make_generation_settings: Any) -> None:
    from fahmi2.domain.enums import ConsolidationMode
    from fahmi2.ui.dialogs.generation_settings_view import GenerationSettingsView

    view = GenerationSettingsView(...)  # mêmes args que les smoke tests existants
    qtbot.addWidget(view)
    view.load_settings(make_generation_settings())  # nom réel de la méthode "from_settings"
    idx = view._consolidation_mode_combo.findData(ConsolidationMode.THEMATIC)
    view._consolidation_mode_combo.setCurrentIndex(idx)
    out = view.to_settings()  # nom réel du builder
    assert out.consolidation_mode is ConsolidationMode.THEMATIC
```

> Adapter `GenerationSettingsView(...)`, `load_settings`/`to_settings` aux noms
> réels (cf. tests smoke existants de ce dialogue).

- [ ] **Step 2 : Lancer → échec**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/ui/dialogs/test_generation_settings_view.py -k consolidation_mode -v`

- [ ] **Step 3 : Libellés FR**

Dans `src/fahmi2/ui/_model_labels.py`, ajouter :

```python
from fahmi2.domain.enums import ConsolidationMode

CONSOLIDATION_MODE_LABELS: dict[ConsolidationMode, str] = {
    ConsolidationMode.ORDERED: "Ordonné (1 source = 1 chapitre)",
    ConsolidationMode.THEMATIC: "Refonte thématique (synthèse transversale)",
}
```

- [ ] **Step 4 : Combobox + intégration**

Dans `generation_settings_view.py` :

1. Importer `ConsolidationMode` (enums) et `CONSOLIDATION_MODE_LABELS` (_model_labels).
2. Dans `_build_style_page` (ou `_build_model_page`), construire le combo selon le
   patron existant :

```python
        self._consolidation_mode_combo = QComboBox(self)
        for mode in ConsolidationMode:
            self._consolidation_mode_combo.addItem(CONSOLIDATION_MODE_LABELS[mode], mode)
        self._consolidation_mode_combo.setToolTip(
            "Ordonné : assemble les sources dans l'ordre choisi (contenu recopié). "
            "Refonte thématique : le LLM agrège et restructure les contenus par thème "
            "(fidélité du fond préservée, forme retravaillée)."
        )
```
   Ajouter une ligne au `QFormLayout` correspondant : `form.addRow("Mode de
   consolidation :", self._consolidation_mode_combo)`.

3. Dans la méthode de chargement (autour des `setCurrentIndex` existants) :

```python
        mode_idx = self._consolidation_mode_combo.findData(settings.consolidation_mode)
        if mode_idx >= 0:
            self._consolidation_mode_combo.setCurrentIndex(mode_idx)
```

4. Dans le builder `GenerationSettings(...)` (autour de la ligne 537), ajouter :

```python
            consolidation_mode=ConsolidationMode(
                self._consolidation_mode_combo.currentData()
            ),
```
   (le `ConsolidationMode(...)` re-coerce le `currentData`, cohérent avec le
   traitement des autres combos — cf. commit `a7197f3`/`a6e923f`).

- [ ] **Step 5 : Lancer → succès**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/ui/dialogs/test_generation_settings_view.py -k consolidation_mode -v`
Expected: PASS.

- [ ] **Step 6 : Commit**

```powershell
git add src/fahmi2/ui/_model_labels.py src/fahmi2/ui/dialogs/generation_settings_view.py
git add tests/unit/ui/dialogs/test_generation_settings_view.py
git commit -m "feat(ui): selecteur du mode de consolidation (ordonne / thematique)"
```

---

### Task 6.2 : Note « ordre sans effet » sur `SourceOrderView`

**Files:**
- Modify: `src/fahmi2/ui/widgets/source_order_view.py`
- Modify: `src/fahmi2/ui/dialogs/generation_settings_view.py` (connexion du signal)
- Test: `tests/unit/ui/widgets/test_source_order_view.py`

- [ ] **Step 1 : Test — la note est visible quand le mode est thématique**

```python
def test_order_note_visible_in_thematic_mode(qtbot: Any) -> None:
    from fahmi2.ui.widgets.source_order_view import SourceOrderView

    view = SourceOrderView()
    qtbot.addWidget(view)
    view.set_order_irrelevant(True)
    assert view._order_note.isVisible() is True
    view.set_order_irrelevant(False)
    assert view._order_note.isVisible() is False
```

> Adapter au constructeur réel de `SourceOrderView`.

- [ ] **Step 2 : Lancer → échec**

- [ ] **Step 3 : Implémenter**

Dans `source_order_view.py` :

1. Ajouter un `QLabel` `self._order_note` (masqué par défaut) avec le texte :
   « En mode refonte thématique, l'ordre des sources n'a pas d'effet (seule
   l'inclusion/exclusion compte). » Style discret (réutiliser une classe QSS info
   si elle existe).
2. Ajouter une méthode publique :

```python
    def set_order_irrelevant(self, irrelevant: bool) -> None:
        """Affiche la note quand l'ordre des sources est ignoré (mode thématique).

        Args:
            irrelevant: ``True`` pour signaler que l'ordre n'a pas d'effet.
        """
        self._order_note.setVisible(irrelevant)
```

Dans `generation_settings_view.py` : connecter le combo de mode pour appeler
`source_order_view.set_order_irrelevant(mode is ConsolidationMode.THEMATIC)` au
changement et au chargement des réglages :

```python
        self._consolidation_mode_combo.currentIndexChanged.connect(
            self._sync_order_irrelevant
        )
```
avec :
```python
    def _sync_order_irrelevant(self) -> None:
        mode = ConsolidationMode(self._consolidation_mode_combo.currentData())
        self._source_order_view.set_order_irrelevant(mode is ConsolidationMode.THEMATIC)
```
(adapter `self._source_order_view` au nom réel de l'attribut ; appeler aussi
`_sync_order_irrelevant()` en fin de chargement des réglages.)

- [ ] **Step 4 : Lancer → succès**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/ui/widgets/test_source_order_view.py -k order_note -v`
Expected: PASS.

- [ ] **Step 5 : Vérifs de lot + commit**

```powershell
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m mypy src tests
git add src/fahmi2/ui/widgets/source_order_view.py
git add src/fahmi2/ui/dialogs/generation_settings_view.py
git add tests/unit/ui/widgets/test_source_order_view.py
git commit -m "feat(ui): note 'ordre sans effet' en mode consolidation thematique"
```
