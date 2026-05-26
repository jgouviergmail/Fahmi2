# Lot 1 — Fondations domaine & persistance

> Sous-skill d'exécution : superpowers:executing-plans. Étapes en `- [ ]`.

**But du lot :** Introduire `ConsolidationMode`, le champ
`GenerationSettings.consolidation_mode` (défaut `ORDERED`), et sa (dé)sérialisation
*lenient* (les projets existants restent en `ORDERED`).

---

### Task 1.1 : Enum `ConsolidationMode`

**Files:**
- Modify: `src/fahmi2/domain/enums.py`
- Test: `tests/unit/domain/test_enums.py`

- [ ] **Step 1 : Test d'existence des membres**

Ajouter dans `tests/unit/domain/test_enums.py` (créer le fichier s'il n'existe pas,
avec l'en-tête de module) :

```python
def test_consolidation_mode_members() -> None:
    from fahmi2.domain.enums import ConsolidationMode

    assert ConsolidationMode.ORDERED.value == "ordered"
    assert ConsolidationMode.THEMATIC.value == "thematic"
    assert {m.value for m in ConsolidationMode} == {"ordered", "thematic"}
```

- [ ] **Step 2 : Lancer le test → échec**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/domain/test_enums.py::test_consolidation_mode_members -v`
Expected: FAIL (`ImportError: cannot import name 'ConsolidationMode'`).

- [ ] **Step 3 : Implémenter l'enum**

Dans `src/fahmi2/domain/enums.py`, après `class StylePreset(StrEnum)` (groupé avec
les enums de génération) :

```python
class ConsolidationMode(StrEnum):
    """Mode d'assemblage du document consolidé (phase 5).

    ``ORDERED`` (défaut) : 1 source = 1 chapitre, contenu recopié dans l'ordre
    choisi. ``THEMATIC`` : refonte thématique transversale — le LLM agrège et
    structure les contenus de tous les entrants (rigueur sur le fond, souplesse
    sur la forme).
    """

    ORDERED = "ordered"
    THEMATIC = "thematic"
```

- [ ] **Step 4 : Lancer le test → succès**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/domain/test_enums.py::test_consolidation_mode_members -v`
Expected: PASS.

- [ ] **Step 5 : Commit**

```powershell
git add src/fahmi2/domain/enums.py tests/unit/domain/test_enums.py
git commit -m "feat(domain): enum ConsolidationMode (ORDERED/THEMATIC)"
```

---

### Task 1.2 : Champ `GenerationSettings.consolidation_mode`

**Files:**
- Modify: `src/fahmi2/domain/generation.py`
- Test: `tests/unit/domain/test_generation_settings.py`

- [ ] **Step 1 : Test du défaut et de l'override**

```python
def test_consolidation_mode_defaults_to_ordered(make_generation_settings: Any) -> None:
    from fahmi2.domain.enums import ConsolidationMode

    gen = make_generation_settings()
    assert gen.consolidation_mode is ConsolidationMode.ORDERED


def test_consolidation_mode_can_be_thematic(make_generation_settings: Any) -> None:
    from fahmi2.domain.enums import ConsolidationMode

    gen = make_generation_settings(consolidation_mode=ConsolidationMode.THEMATIC)
    assert gen.consolidation_mode is ConsolidationMode.THEMATIC
```

> Note : `make_generation_settings` accepte des kwargs de surcharge (cf.
> `tests/conftest.py`). Aucun changement de la fixture n'est requis : le champ a
> une valeur par défaut.

- [ ] **Step 2 : Lancer → échec**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/domain/test_generation_settings.py -k consolidation_mode -v`
Expected: FAIL (`TypeError: ... unexpected keyword argument 'consolidation_mode'`).

- [ ] **Step 3 : Ajouter le champ + import + docstring**

Dans `src/fahmi2/domain/generation.py` :

1. Ajouter `ConsolidationMode` à l'import depuis `fahmi2.domain.enums`.
2. Ajouter le champ (avec les autres champs à défaut, après `excluded_sources`) :

```python
    consolidation_mode: ConsolidationMode = ConsolidationMode.ORDERED
```

3. Compléter le bloc `Attributes:` de la docstring de classe :

```
        consolidation_mode: Mode d'assemblage du consolidé (phase 5).
            ``ORDERED`` (défaut) : 1 source = 1 chapitre dans l'ordre choisi.
            ``THEMATIC`` : refonte thématique transversale par le LLM (en ce mode,
            ``source_order`` n'a pas d'effet et ``reformulate_documents`` est
            ignoré — tout entrant est matière première).
```

- [ ] **Step 4 : Lancer → succès**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/domain/test_generation_settings.py -k consolidation_mode -v`
Expected: PASS.

- [ ] **Step 5 : Commit**

```powershell
git add src/fahmi2/domain/generation.py tests/unit/domain/test_generation_settings.py
git commit -m "feat(domain): GenerationSettings.consolidation_mode (defaut ORDERED)"
```

---

### Task 1.3 : (Dé)sérialisation *lenient*

**Files:**
- Modify: `src/fahmi2/infra/storage/sqlite_state.py`
- Test: `tests/unit/infra/storage/test_sqlite_state.py` (ou le fichier de test
  existant couvrant `_serialize_generation_settings` / `_deserialize_generation_settings`)

- [ ] **Step 1 : Test round-trip + migration d'un blob sans le champ**

```python
def test_generation_settings_roundtrip_consolidation_mode(
    make_generation_settings: Any,
) -> None:
    from fahmi2.domain.enums import ConsolidationMode
    from fahmi2.infra.storage.sqlite_state import (
        _deserialize_generation_settings,
        _serialize_generation_settings,
    )

    gen = make_generation_settings(consolidation_mode=ConsolidationMode.THEMATIC)
    payload = _serialize_generation_settings(gen)
    assert payload["consolidation_mode"] == "thematic"
    restored = _deserialize_generation_settings(payload)
    assert restored.consolidation_mode is ConsolidationMode.THEMATIC


def test_deserialize_without_consolidation_mode_defaults_ordered(
    make_generation_settings: Any,
) -> None:
    from fahmi2.domain.enums import ConsolidationMode
    from fahmi2.infra.storage.sqlite_state import (
        _deserialize_generation_settings,
        _serialize_generation_settings,
    )

    payload = _serialize_generation_settings(make_generation_settings())
    del payload["consolidation_mode"]  # simule un ancien blob
    restored = _deserialize_generation_settings(payload)
    assert restored.consolidation_mode is ConsolidationMode.ORDERED
```

- [ ] **Step 2 : Lancer → échec**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/infra/storage/test_sqlite_state.py -k consolidation_mode -v`
Expected: FAIL (`KeyError: 'consolidation_mode'` ou `AttributeError`).

- [ ] **Step 3 : Sérialiser**

Dans `_serialize_generation_settings` (`sqlite_state.py`), ajouter au dict retourné
(à la fin, après `"excluded_sources"`) :

```python
        "consolidation_mode": str(gen.consolidation_mode),
```

- [ ] **Step 4 : Désérialiser (lenient)**

Dans `_deserialize_generation_settings`, ajouter au constructeur `GenerationSettings(...)`
(après `excluded_sources=...`) :

```python
        consolidation_mode=ConsolidationMode(
            payload.get("consolidation_mode", ConsolidationMode.ORDERED)
        ),
```

Ajouter `ConsolidationMode` à l'import depuis `fahmi2.domain.enums` en tête de
`sqlite_state.py`.

- [ ] **Step 5 : Lancer → succès**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/infra/storage/test_sqlite_state.py -k consolidation_mode -v`
Expected: PASS.

- [ ] **Step 6 : Vérifs de lot + commit**

```powershell
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m mypy src tests
git add src/fahmi2/infra/storage/sqlite_state.py tests/unit/infra/storage/test_sqlite_state.py
git commit -m "feat(storage): (de)serialise consolidation_mode (migration lenient)"
```

Expected : suite complète verte (le champ a un défaut → aucun test existant cassé).
