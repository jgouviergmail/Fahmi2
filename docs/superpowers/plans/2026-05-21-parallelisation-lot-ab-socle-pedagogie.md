# Parallélisation — Lot A (socle) + Lot B (pédagogie) — Plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task (exécution **inline**, pas de subagents — préférence projet). Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduire un primitif de concurrence borné partagé (`map_bounded`) et l'utiliser pour paralléliser la génération des supports pédagogiques `(langue × support)`, avec réglage du nombre de workers et plafond de coût best-effort.

**Architecture:** Un helper pur `core/concurrency/map_bounded` (ThreadPoolExecutor borné, ordre préservé, fail-fast, honore le `PauseToken` entre soumissions). L'orchestrateur pédagogie aplatit ses unités et les passe à `map_bounded` ; les états partagés (manifeste, compteur de coût) sont protégés par verrous, le coût/échec agrégés après collecte. Réglages exposés via un champ `llm_workers` sur `PedagogySettings`.

**Tech Stack:** Python 3.12, `concurrent.futures`, PySide6, pytest, ruff, mypy --strict.

**Spec de référence:** [docs/superpowers/specs/2026-05-21-parallelisation-traitements-design.md](../specs/2026-05-21-parallelisation-traitements-design.md) (Lots A et B ; §4, §7, §8, §9, §10).

**Interpréteur:** `.venv\Scripts\python.exe` (toutes les commandes ci-dessous l'utilisent).

---

## Vue d'ensemble des fichiers

| Fichier | Rôle | Action |
|---|---|---|
| `src/fahmi2/core/concurrency/__init__.py` | Réexporte `map_bounded` | Créer |
| `src/fahmi2/core/concurrency/_executor.py` | Primitif `map_bounded` | Créer |
| `src/fahmi2/infra/storage/fs_artifacts.py` | `.tmp` unique (uuid) | Modifier |
| `src/fahmi2/infra/llm/deepseek_adapter.py` | Timeout client explicite | Modifier |
| `src/fahmi2/domain/pedagogy.py` | Champ `llm_workers` + constantes | Modifier |
| `src/fahmi2/infra/storage/sqlite_state.py` | (Dé)sérialisation `llm_workers` (lenient) | Modifier |
| `src/fahmi2/ui/dialogs/pedagogy_settings_view.py` | Saisie « Tâches en parallèle » | Modifier |
| `src/fahmi2/app/supports_orchestrator.py` | Aplatissement + `map_bounded` + verrous | Modifier |
| `tests/unit/core/concurrency/test_executor.py` | Tests du primitif | Créer |

---

## Task 1 : Primitif `map_bounded`

**Files:**
- Create: `src/fahmi2/core/concurrency/__init__.py`
- Create: `src/fahmi2/core/concurrency/_executor.py`
- Test: `tests/unit/core/concurrency/test_executor.py`

- [ ] **Step 1 : Écrire les tests qui échouent**

Créer `tests/unit/core/concurrency/test_executor.py` :

```python
"""Tests du primitif map_bounded."""

from __future__ import annotations

import threading
import time

import pytest

from fahmi2.core.concurrency import map_bounded
from fahmi2.core.errors.exceptions import LLMError, PausedError
from fahmi2.core.errors.severity import Severity
from fahmi2.pipeline.pause_token import PauseToken


def test_preserves_result_order() -> None:
    assert map_bounded(lambda x: x * 2, [1, 2, 3, 4, 5], max_workers=3) == [
        2, 4, 6, 8, 10
    ]


def test_empty_items_returns_empty() -> None:
    assert map_bounded(lambda x: x, [], max_workers=4) == []


def test_sequential_when_single_worker() -> None:
    calls: list[int] = []
    map_bounded(calls.append, [1, 2, 3], max_workers=1)
    assert calls == [1, 2, 3]


def test_bounds_concurrency() -> None:
    lock = threading.Lock()
    state = {"current": 0, "max": 0}

    def work(_: int) -> int:
        with lock:
            state["current"] += 1
            state["max"] = max(state["max"], state["current"])
        time.sleep(0.02)
        with lock:
            state["current"] -= 1
        return 0

    map_bounded(work, list(range(20)), max_workers=4)
    assert state["max"] <= 4


def test_fail_fast_propagates_first_exception() -> None:
    def work(x: int) -> int:
        if x == 3:
            raise LLMError(
                code="LLM.X", user_message="boom", severity=Severity.ERROR
            )
        return x

    with pytest.raises(LLMError):
        map_bounded(work, [1, 2, 3, 4, 5], max_workers=2)


def test_cancellation_raises_paused_error() -> None:
    token = PauseToken()
    token.request_cancel()
    with pytest.raises(PausedError):
        map_bounded(lambda x: x, [1, 2, 3], max_workers=4, pause_token=token)
```

- [ ] **Step 2 : Lancer les tests pour vérifier qu'ils échouent**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/core/concurrency/test_executor.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'fahmi2.core.concurrency'`

- [ ] **Step 3 : Créer le package**

Créer `src/fahmi2/core/concurrency/__init__.py` :

```python
"""Primitifs de concurrence transverses (sans Qt, HTTP ni SQL)."""

from __future__ import annotations

from fahmi2.core.concurrency._executor import map_bounded

__all__ = ["map_bounded"]
```

- [ ] **Step 4 : Implémenter `map_bounded`**

Créer `src/fahmi2/core/concurrency/_executor.py` :

```python
"""Exécution bornée et concurrente d'une fonction sur une séquence d'items.

Primitif partagé par le moteur de génération et l'orchestrateur pédagogie.
Borne la concurrence à ``max_workers`` threads (adapté aux appels I/O-bound :
LLM, STT cloud — le GIL est libéré pendant l'attente réseau). Préserve l'ordre
des résultats, applique une politique *fail-fast*, et honore un ``PauseToken``
coopératif **entre les soumissions** (pause/annulation prises en compte sans
interrompre les tâches déjà démarrées).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from typing import TypeVar

from fahmi2.pipeline.pause_token import PauseToken

_T = TypeVar("_T")
_R = TypeVar("_R")


def map_bounded(
    fn: Callable[[_T], _R],
    items: Sequence[_T],
    *,
    max_workers: int,
    pause_token: PauseToken | None = None,
) -> list[_R]:
    """Applique ``fn`` à chaque item, au plus ``max_workers`` à la fois.

    Args:
        fn: Fonction appliquée à chaque item (peut lever : *fail-fast*).
        items: Items à traiter.
        max_workers: Concurrence maximale (>= 1). ``1`` => séquentiel.
        pause_token: Jeton coopératif consulté avant chaque soumission
            (bloque si pause, lève ``PausedError`` si annulation).

    Returns:
        Les résultats dans l'ordre des ``items``.

    Raises:
        BaseException: La première exception levée par ``fn`` (les tâches non
            démarrées sont annulées ; les démarrées vont au bout).
        PausedError: Si ``pause_token`` signale une annulation.
    """
    work = list(items)
    n = len(work)
    if n == 0:
        return []
    collected: dict[int, _R] = {}
    if max_workers <= 1:
        for index, item in enumerate(work):
            _wait_or_cancel(pause_token)
            collected[index] = fn(item)
        return [collected[i] for i in range(n)]

    next_index = 0
    in_flight: dict[Future[_R], int] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        try:
            while next_index < n and len(in_flight) < max_workers:
                _wait_or_cancel(pause_token)
                in_flight[executor.submit(fn, work[next_index])] = next_index
                next_index += 1
            while in_flight:
                done_set, _ = wait(set(in_flight), return_when=FIRST_COMPLETED)
                for done in done_set:
                    index = in_flight.pop(done)
                    collected[index] = done.result()  # fail-fast : propage
                    if next_index < n:
                        _wait_or_cancel(pause_token)
                        in_flight[
                            executor.submit(fn, work[next_index])
                        ] = next_index
                        next_index += 1
        except BaseException:
            for pending in in_flight:
                pending.cancel()
            raise
    return [collected[i] for i in range(n)]


def _wait_or_cancel(pause_token: PauseToken | None) -> None:
    """Bloque si pause demandée, lève ``PausedError`` si annulation.

    Args:
        pause_token: Jeton coopératif (``None`` => no-op).
    """
    if pause_token is None:
        return
    pause_token.wait_if_paused()
    pause_token.raise_if_cancelled()
```

- [ ] **Step 5 : Lancer les tests (doivent passer)**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/core/concurrency/test_executor.py -v`
Expected: PASS (6 tests)

- [ ] **Step 6 : Qualité + commit**

```bash
.venv\Scripts\python.exe -m ruff check src/fahmi2/core/concurrency tests/unit/core/concurrency
.venv\Scripts\python.exe -m mypy src/fahmi2/core/concurrency
git add src/fahmi2/core/concurrency tests/unit/core/concurrency
git commit -m "feat(core): primitif map_bounded (concurrence bornée, fail-fast, pause)"
```

---

## Task 2 : `FsArtifactStore` — fichier temporaire unique

**Files:**
- Modify: `src/fahmi2/infra/storage/fs_artifacts.py`
- Test: `tests/unit/infra/storage/test_fs_artifacts.py`

- [ ] **Step 1 : Écrire le test qui échoue**

Ajouter à `tests/unit/infra/storage/test_fs_artifacts.py` :

```python
def test_tmp_path_is_unique_across_calls() -> None:
    from fahmi2.infra.storage.fs_artifacts import FsArtifactStore

    store = FsArtifactStore()
    path = Path("dir/file.json")
    a = store._tmp_path_for(path)
    b = store._tmp_path_for(path)
    assert a != b
    assert a.name.endswith(".tmp")
    assert b.name.endswith(".tmp")
```

(Ajouter `from pathlib import Path` en tête du fichier s'il n'y est pas déjà.)

- [ ] **Step 2 : Lancer le test pour vérifier qu'il échoue**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/infra/storage/test_fs_artifacts.py::test_tmp_path_is_unique_across_calls -v`
Expected: FAIL (les deux noms sont identiques)

- [ ] **Step 3 : Rendre le suffixe `.tmp` unique**

Dans `src/fahmi2/infra/storage/fs_artifacts.py`, ajouter l'import et modifier `_tmp_path_for` :

```python
import os
import uuid
from pathlib import Path
```

```python
    @staticmethod
    def _tmp_path_for(path: Path) -> Path:
        """Retourne un chemin temporaire **unique** associé à ``path``.

        Le composant aléatoire (uuid4) évite toute collision entre deux
        écritures concurrentes (défense en profondeur pour la parallélisation).
        """
        return path.with_suffix(f"{path.suffix}.{uuid.uuid4().hex}{_TMP_SUFFIX}")
```

- [ ] **Step 4 : Lancer tous les tests du fichier (régression incluse)**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/infra/storage/test_fs_artifacts.py -v`
Expected: PASS (tous les tests existants + le nouveau)

- [ ] **Step 5 : Qualité + commit**

```bash
.venv\Scripts\python.exe -m ruff check src/fahmi2/infra/storage/fs_artifacts.py tests/unit/infra/storage/test_fs_artifacts.py
.venv\Scripts\python.exe -m mypy src/fahmi2/infra/storage/fs_artifacts.py
git add src/fahmi2/infra/storage/fs_artifacts.py tests/unit/infra/storage/test_fs_artifacts.py
git commit -m "feat(infra): nom de fichier temporaire unique (defense concurrence)"
```

---

## Task 3 : Timeout explicite du client DeepSeek

**Files:**
- Modify: `src/fahmi2/infra/llm/deepseek_adapter.py`
- Test: `tests/unit/infra/llm/test_deepseek_adapter.py`

- [ ] **Step 1 : Écrire le test qui échoue**

Ajouter à `tests/unit/infra/llm/test_deepseek_adapter.py` :

```python
def test_client_is_created_with_explicit_timeout(monkeypatch: Any) -> None:
    import fahmi2.infra.llm.deepseek_adapter as mod
    from fahmi2.infra.llm.deepseek_adapter import (
        _REQUEST_TIMEOUT_SECONDS,
        DeepSeekAdapter,
    )

    captured: dict[str, Any] = {}

    def _fake_openai(**kwargs: Any) -> object:
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(mod, "OpenAI", _fake_openai)
    DeepSeekAdapter(api_key="k")
    assert captured["timeout"] == _REQUEST_TIMEOUT_SECONDS
```

(S'assurer que `from typing import Any` est importé dans le fichier de test.)

- [ ] **Step 2 : Lancer le test pour vérifier qu'il échoue**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/infra/llm/test_deepseek_adapter.py::test_client_is_created_with_explicit_timeout -v`
Expected: FAIL — `ImportError: cannot import name '_REQUEST_TIMEOUT_SECONDS'`

- [ ] **Step 3 : Ajouter la constante et passer le timeout**

Dans `src/fahmi2/infra/llm/deepseek_adapter.py`, après les constantes existantes :

```python
# DeepSeek garde la connexion ouverte (keep-alive) et ne la ferme qu'après ~10
# minutes sans démarrage d'inférence : timeout client large pour absorber les
# requêtes lentes sous charge (notamment reasoning_effort élevé).
_REQUEST_TIMEOUT_SECONDS = 600.0
```

Modifier la signature et l'instanciation du client :

```python
    def __init__(
        self,
        *,
        api_key: str,
        client: OpenAI | None = None,
        base_url: str = _PROVIDER_BASE_URL,
        timeout: float = _REQUEST_TIMEOUT_SECONDS,
    ) -> None:
        """Construit l'adaptateur.

        Args:
            api_key: Clé API DeepSeek.
            client: Client OpenAI injectable (utile pour les tests).
            base_url: URL de base de l'API.
            timeout: Timeout des requêtes en secondes (absorbe le keep-alive).
        """
        self._client = client or OpenAI(
            api_key=api_key, base_url=base_url, timeout=timeout
        )
```

- [ ] **Step 4 : Lancer les tests du fichier**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/infra/llm/test_deepseek_adapter.py -v`
Expected: PASS (existants + nouveau)

- [ ] **Step 5 : Qualité + commit**

```bash
.venv\Scripts\python.exe -m ruff check src/fahmi2/infra/llm/deepseek_adapter.py tests/unit/infra/llm/test_deepseek_adapter.py
.venv\Scripts\python.exe -m mypy src/fahmi2/infra/llm/deepseek_adapter.py
git add src/fahmi2/infra/llm/deepseek_adapter.py tests/unit/infra/llm/test_deepseek_adapter.py
git commit -m "feat(infra): timeout explicite du client DeepSeek (600s, keep-alive)"
```

---

## Task 4 : Champ `llm_workers` sur `PedagogySettings`

**Files:**
- Modify: `src/fahmi2/domain/pedagogy.py`
- Test: `tests/unit/domain/test_pedagogy.py`

- [ ] **Step 1 : Écrire les tests qui échouent**

Ajouter à `tests/unit/domain/test_pedagogy.py` :

```python
def test_llm_workers_defaults_to_16(make_pedagogy_settings: Any) -> None:
    from fahmi2.domain.pedagogy import DEFAULT_PEDAGOGY_LLM_WORKERS

    assert make_pedagogy_settings().llm_workers == DEFAULT_PEDAGOGY_LLM_WORKERS
    assert DEFAULT_PEDAGOGY_LLM_WORKERS == 16


def test_llm_workers_must_be_positive(make_pedagogy_settings: Any) -> None:
    with pytest.raises(ValueError, match="llm_workers"):
        make_pedagogy_settings(llm_workers=0)


def test_llm_workers_not_in_settings_hash(make_pedagogy_settings: Any) -> None:
    from fahmi2.pedagogy.manifest import compute_settings_hash

    a = compute_settings_hash(make_pedagogy_settings(llm_workers=4))
    b = compute_settings_hash(make_pedagogy_settings(llm_workers=32))
    assert a == b
```

(S'assurer que `import pytest` et `from typing import Any` sont présents.)

- [ ] **Step 2 : Lancer les tests pour vérifier qu'ils échouent**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/domain/test_pedagogy.py -k llm_workers -v`
Expected: FAIL — `TypeError: __init__() got an unexpected keyword argument 'llm_workers'`

- [ ] **Step 3 : Ajouter le champ et la validation**

Dans `src/fahmi2/domain/pedagogy.py`, après les constantes de tête de module :

```python
#: Nombre de tâches LLM concurrentes par défaut (DeepSeek : limite par
#: concurrence très haute, donc valeur généreuse mais sûre).
DEFAULT_PEDAGOGY_LLM_WORKERS = 16

#: Borne haute proposée dans l'UI pour le réglage « tâches en parallèle ».
MAX_PEDAGOGY_LLM_WORKERS = 64
```

Ajouter le champ **en dernier** (champ avec défaut) dans la dataclass :

```python
    cost_ceiling_usd: float | None
    export_formats: frozenset[ExportFormat]
    llm_workers: int = DEFAULT_PEDAGOGY_LLM_WORKERS
```

Mettre à jour la docstring `Attributes:` (ajouter `llm_workers: Tâches LLM
concurrentes (>= 1).`) et compléter `__post_init__` :

```python
        if self.llm_workers < 1:
            raise ValueError(f"llm_workers must be >= 1, got {self.llm_workers}")
```

- [ ] **Step 4 : Lancer les tests (domaine + manifeste)**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/domain/test_pedagogy.py -v`
Expected: PASS

> Note : `compute_settings_hash` (`pedagogy/manifest.py`) construit son payload champ par champ et **n'inclut pas** `llm_workers` — aucune modification requise ; le test `test_llm_workers_not_in_settings_hash` le verrouille.

- [ ] **Step 5 : Qualité + commit**

```bash
.venv\Scripts\python.exe -m ruff check src/fahmi2/domain/pedagogy.py tests/unit/domain/test_pedagogy.py
.venv\Scripts\python.exe -m mypy src/fahmi2/domain/pedagogy.py
git add src/fahmi2/domain/pedagogy.py tests/unit/domain/test_pedagogy.py
git commit -m "feat(domain): champ llm_workers sur PedagogySettings (defaut 16)"
```

---

## Task 5 : (Dé)sérialisation SQLite de `llm_workers` (migration lenient)

**Files:**
- Modify: `src/fahmi2/infra/storage/sqlite_state.py`
- Test: `tests/unit/infra/storage/test_sqlite_state.py`

- [ ] **Step 1 : Écrire les tests qui échouent**

Ajouter à `tests/unit/infra/storage/test_sqlite_state.py` (s'assurer que `from typing import Any` est importé) :

```python
def test_pedagogy_llm_workers_round_trip(make_pedagogy_settings: Any) -> None:
    from fahmi2.infra.storage.sqlite_state import (
        _deserialize_pedagogy_settings,
        _serialize_pedagogy_settings,
    )

    ped = make_pedagogy_settings(llm_workers=8)
    payload = _serialize_pedagogy_settings(ped)
    assert payload["llm_workers"] == 8
    assert _deserialize_pedagogy_settings(payload).llm_workers == 8


def test_pedagogy_llm_workers_missing_uses_default(
    make_pedagogy_settings: Any,
) -> None:
    from fahmi2.domain.pedagogy import DEFAULT_PEDAGOGY_LLM_WORKERS
    from fahmi2.infra.storage.sqlite_state import (
        _deserialize_pedagogy_settings,
        _serialize_pedagogy_settings,
    )

    payload = _serialize_pedagogy_settings(make_pedagogy_settings())
    del payload["llm_workers"]  # simule un blob écrit avant l'ajout du champ
    restored = _deserialize_pedagogy_settings(payload)
    assert restored.llm_workers == DEFAULT_PEDAGOGY_LLM_WORKERS
```

- [ ] **Step 2 : Lancer les tests pour vérifier qu'ils échouent**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/infra/storage/test_sqlite_state.py -k llm_workers -v`
Expected: FAIL — `KeyError: 'llm_workers'` à la sérialisation

- [ ] **Step 3 : Sérialiser + désérialiser le champ**

Dans `_serialize_pedagogy_settings`, ajouter au dict retourné (avant la fermeture) :

```python
        "cost_ceiling_usd": ped.cost_ceiling_usd,
        "export_formats": sorted(f.value for f in ped.export_formats),
        "llm_workers": ped.llm_workers,
    }
```

Dans `_deserialize_pedagogy_settings`, étendre l'import du domaine. La ligne d'import actuelle est `from fahmi2.domain.pedagogy import PedagogySettings` — la remplacer par :

```python
from fahmi2.domain.pedagogy import DEFAULT_PEDAGOGY_LLM_WORKERS, PedagogySettings
```

Puis, dans le `return PedagogySettings(...)`, **insérer une seule ligne** juste après `export_formats=...` (les deux lignes précédentes existent déjà telles quelles, ne pas les modifier) :

```python
        cost_ceiling_usd=payload["cost_ceiling_usd"],
        export_formats=frozenset(ExportFormat(f) for f in payload["export_formats"]),
        llm_workers=int(payload.get("llm_workers", DEFAULT_PEDAGOGY_LLM_WORKERS)),
    )
```

- [ ] **Step 4 : Lancer les tests SQLite (régression incluse)**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/infra/storage/test_sqlite_state.py -v`
Expected: PASS

- [ ] **Step 5 : Qualité + commit**

```bash
.venv\Scripts\python.exe -m ruff check src/fahmi2/infra/storage/sqlite_state.py tests/unit/infra/storage/test_sqlite_state.py
.venv\Scripts\python.exe -m mypy src/fahmi2/infra/storage/sqlite_state.py
git add src/fahmi2/infra/storage/sqlite_state.py tests/unit/infra/storage/test_sqlite_state.py
git commit -m "feat(infra): persistance lenient de PedagogySettings.llm_workers"
```

---

## Task 6 : Saisie UI « Tâches en parallèle »

**Files:**
- Modify: `src/fahmi2/ui/dialogs/pedagogy_settings_view.py`
- Test: `tests/unit/ui/test_pedagogy_settings_view.py`

- [ ] **Step 1 : Écrire le test qui échoue**

Ajouter à `tests/unit/ui/test_pedagogy_settings_view.py` :

```python
def test_llm_workers_round_trips_through_view(
    qtbot: Any, make_pedagogy_settings: Any
) -> None:
    from fahmi2.domain.enums import Language
    from fahmi2.ui.dialogs.pedagogy_settings_view import PedagogySettingsView

    initial = make_pedagogy_settings(llm_workers=24)
    view = PedagogySettingsView(
        available_languages=(Language.FR,), initial=initial
    )
    qtbot.addWidget(view)
    built = view.build_settings()
    assert built is not None
    assert built.llm_workers == 24
```

- [ ] **Step 2 : Lancer le test pour vérifier qu'il échoue**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/ui/test_pedagogy_settings_view.py::test_llm_workers_round_trips_through_view -v`
Expected: FAIL — `build_settings()` produit un `PedagogySettings` avec `llm_workers` par défaut (≠ 24)

- [ ] **Step 3 : Ajouter le widget, le câbler en lecture et en pré-remplissage**

Dans `src/fahmi2/ui/dialogs/pedagogy_settings_view.py` :

Imports — ajouter `QSpinBox` à l'import PySide6 et les constantes du domaine :

```python
from fahmi2.domain.pedagogy import (
    DEFAULT_PEDAGOGY_LLM_WORKERS,
    EVALUATIVE_SUPPORTS,
    MAX_PEDAGOGY_LLM_WORKERS,
    PedagogySettings,
)
```

Dans `_build_fields`, après le bloc `_cost_ceiling_input` :

```python
        self._workers_input = QSpinBox(self)
        self._workers_input.setRange(1, MAX_PEDAGOGY_LLM_WORKERS)
        self._workers_input.setValue(DEFAULT_PEDAGOGY_LLM_WORKERS)
```

Dans `_build_model_page`, ajouter une ligne au `QFormLayout` (après « Plafond budget ») :

```python
        form.addRow("Tâches en parallèle :", self._workers_input)
```

Dans `build_settings`, ajouter le champ au constructeur `PedagogySettings` :

```python
                cost_ceiling_usd=ceiling,
                export_formats=export_formats,
                llm_workers=self._workers_input.value(),
            )
```

Dans `_populate`, ajouter :

```python
        self._workers_input.setValue(pedagogy.llm_workers)
```

- [ ] **Step 4 : Lancer les tests UI (régression incluse)**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/ui/test_pedagogy_settings_view.py -v`
Expected: PASS

- [ ] **Step 5 : Qualité + commit**

```bash
.venv\Scripts\python.exe -m ruff check src/fahmi2/ui/dialogs/pedagogy_settings_view.py tests/unit/ui/test_pedagogy_settings_view.py
.venv\Scripts\python.exe -m mypy src/fahmi2/ui/dialogs/pedagogy_settings_view.py
git add src/fahmi2/ui/dialogs/pedagogy_settings_view.py tests/unit/ui/test_pedagogy_settings_view.py
git commit -m "feat(ui): saisie du nombre de taches paralleles (pedagogie)"
```

---

## Task 7 : Paralléliser `SupportsOrchestrator.generate`

**Files:**
- Modify: `src/fahmi2/app/supports_orchestrator.py`
- Test: `tests/unit/app/test_supports_orchestrator.py`

**Conception** : on aplatit les unités `(langue, support)`, pré-charge les chapitres par langue, et exécute via `map_bounded(max_workers=pedagogy.llm_workers)`. Le manifeste est protégé par un verrou ; un compteur de coût partagé court-circuite les tâches au-delà du plafond (léger dépassement toléré) ; coût/échec agrégés après collecte.

- [ ] **Step 1 : Écrire les tests qui échouent**

Ajouter à `tests/unit/app/test_supports_orchestrator.py` :

```python
def test_parallel_generation_two_languages(
    tmp_path: Path, make_generation_settings: Any, make_pedagogy_settings: Any
) -> None:
    registry = SupportGeneratorRegistry([_StubGen(SupportType.FLASHCARDS_CONCEPTS)])
    orchestrator, state, project_service = _build(tmp_path, registry)
    ws = tmp_path / "ws"
    project = project_service.create_project(
        name="P",
        workspace_folder=ws,
        generation=make_generation_settings(output_languages=(Language.FR, Language.EN)),
        pedagogy=make_pedagogy_settings(
            languages=(Language.FR, Language.EN), llm_workers=4
        ),
    )
    _seed_completed_run_with_glossary(
        state, project, make_generation_settings(output_languages=(Language.FR, Language.EN))
    )
    # Sources consolidées pour les deux langues.
    for lang in (Language.FR, Language.EN):
        FsArtifactStore().write_text_atomic(
            ws / GENERATION_WORKSPACE_SUBDIR / GENERATION_OUTPUT_SUBDIR
            / consolidated_doc_filename(lang),
            "# Titre\n\n## 1. Chapitre\n\nContenu.\n",
        )

    bus: EventBus[PedagogyEvent] = EventBus()
    status = orchestrator.generate(project, pause_token=PauseToken(), event_bus=bus)

    assert status is RunStatus.COMPLETED
    pedagogy_dir = ws / "pedagogy"
    for lang in (Language.FR, Language.EN):
        assert artifact_json_path(
            pedagogy_dir, SupportType.FLASHCARDS_CONCEPTS, lang
        ).exists()


def test_ceiling_pauses_when_exceeded(
    tmp_path: Path, make_generation_settings: Any, make_pedagogy_settings: Any
) -> None:
    registry = SupportGeneratorRegistry(
        [_StubGen(SupportType.FLASHCARDS_CONCEPTS, cost=1.0)]
    )
    orchestrator, state, project_service = _build(tmp_path, registry)
    ws = tmp_path / "ws"
    project = project_service.create_project(
        name="P",
        workspace_folder=ws,
        generation=make_generation_settings(output_languages=(Language.FR, Language.EN)),
        pedagogy=make_pedagogy_settings(
            languages=(Language.FR, Language.EN),
            llm_workers=1,
            cost_ceiling_usd=0.5,
        ),
    )
    _seed_completed_run_with_glossary(
        state, project, make_generation_settings(output_languages=(Language.FR, Language.EN))
    )
    for lang in (Language.FR, Language.EN):
        FsArtifactStore().write_text_atomic(
            ws / GENERATION_WORKSPACE_SUBDIR / GENERATION_OUTPUT_SUBDIR
            / consolidated_doc_filename(lang),
            "# Titre\n\n## 1. Chapitre\n\nContenu.\n",
        )

    bus: EventBus[PedagogyEvent] = EventBus()
    status = orchestrator.generate(project, pause_token=PauseToken(), event_bus=bus)
    assert status is RunStatus.PAUSED
```

Le stub de générateur (ajouter en haut du fichier de test s'il n'existe pas déjà avec un coût paramétrable) :

```python
class _StubGen(SupportGenerator):
    def __init__(self, support_type: SupportType, *, cost: float = 0.0) -> None:
        self._support_type = support_type
        self._cost = cost

    @property
    def support_type(self) -> SupportType:
        return self._support_type

    @property
    def uses_llm(self) -> bool:
        return True

    def generate(
        self, ctx: SupportContext, *, language: Language,
        chapters: tuple[Chapter, ...], glossary: tuple[Term, ...]
    ) -> SupportArtifact:
        return SupportArtifact(
            support_type=self._support_type,
            language=language,
            items=(),
            rendered_markdown="# stub",
            correction_markdown=None,
            cost_usd=self._cost,
        )
```

> Si un `_StubGen` existe déjà dans le fichier, lui ajouter le paramètre `cost` (défaut `0.0`) plutôt que d'en créer un second.

- [ ] **Step 2 : Lancer les nouveaux tests pour vérifier qu'ils échouent**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/app/test_supports_orchestrator.py -k "parallel or ceiling" -v`
Expected: FAIL (le ceiling renvoie aujourd'hui `PAUSED` via un autre chemin ; le test parallèle peut passer ou non — l'objectif est de basculer sur `map_bounded`)

- [ ] **Step 3 : Réécrire `generate` avec `map_bounded`**

Dans `src/fahmi2/app/supports_orchestrator.py`, ajouter les imports :

```python
import threading

from fahmi2.core.concurrency import map_bounded
```

Remplacer le corps de la boucle de `generate` (depuis `glossary = self._load_glossary(project)` jusqu'au `return self._finalize_run(...)` final) par :

```python
        glossary = self._load_glossary(project)
        source_language = (
            project.generation.source_language
            if project.generation is not None
            else None
        )
        regenerate = self._is_complete(
            ctx,
            pedagogy=pedagogy,
            manifest=manifest,
            settings_hash=settings_hash,
            source_language=source_language,
        )

        # Pré-chargement des entrants par langue (lecture disque hors threads).
        per_language: dict[Language, tuple[int | None, tuple[Chapter, ...]]] = {}
        for language in pedagogy.languages:
            content_lang = resolve_content_language(
                ctx.generation_output_dir, language, source_language
            )
            source_mtime = (
                source_mtime_ns(ctx.generation_output_dir, content_lang)
                if content_lang is not None
                else None
            )
            chapters = (
                load_chapters(ctx.generation_output_dir, content_lang)
                if content_lang is not None
                else ()
            )
            per_language[language] = (source_mtime, chapters)

        tasks: list[tuple[Language, SupportType]] = [
            (language, support_type)
            for language in pedagogy.languages
            for support_type in self._registry.canonical_order()
            if support_type in pedagogy.selected_supports
            and self._registry.has(support_type)
        ]

        manifest_lock = threading.Lock()
        cost_lock = threading.Lock()
        cost_state = {"total": 0.0}
        ceiling = pedagogy.cost_ceiling_usd

        def _run_task(task: tuple[Language, SupportType]) -> tuple[float, bool, bool]:
            language, support_type = task
            if ceiling is not None:
                with cost_lock:
                    if cost_state["total"] >= ceiling:
                        return 0.0, False, True  # court-circuit plafond
            source_mtime, chapters = per_language[language]
            cost, failed = self._run_one(
                ctx,
                manifest=manifest,
                manifest_lock=manifest_lock,
                support_type=support_type,
                language=language,
                chapters=chapters,
                glossary=glossary,
                settings_hash=settings_hash,
                source_mtime_ns=source_mtime,
                regenerate=regenerate,
            )
            with cost_lock:
                cost_state["total"] += cost
            return cost, failed, False

        try:
            outcomes = map_bounded(
                _run_task,
                tasks,
                max_workers=pedagogy.llm_workers,
                pause_token=pause_token,
            )
        except PausedError:
            return self._finalize_run(
                ctx,
                event_bus,
                status=RunStatus.CANCELLED,
                started_at=started_at,
                total_cost=cost_state["total"],
            )

        any_failure = any(failed for _, failed, _ in outcomes)
        ceiling_reached = any(skipped for _, _, skipped in outcomes)
        if ceiling_reached:
            final = RunStatus.PAUSED
        elif any_failure:
            final = RunStatus.FAILED
        else:
            final = RunStatus.COMPLETED
        return self._finalize_run(
            ctx,
            event_bus,
            status=final,
            started_at=started_at,
            total_cost=cost_state["total"],
        )
```

- [ ] **Step 4 : Protéger le manifeste dans `_run_one`**

Modifier la signature de `_run_one` pour accepter `manifest_lock` et protéger les accès au manifeste. Nouvelle signature (ajouter le paramètre keyword `manifest_lock: threading.Lock`) :

```python
    def _run_one(
        self,
        ctx: SupportContext,
        *,
        manifest: PedagogyManifest,
        manifest_lock: threading.Lock,
        support_type: SupportType,
        language: Language,
        chapters: tuple[Chapter, ...],
        glossary: tuple[Term, ...],
        settings_hash: str,
        source_mtime_ns: int | None,
        regenerate: bool,
    ) -> tuple[float, bool]:
```

Dans le corps, encadrer la lecture de fraîcheur par le verrou :

```python
        json_path = artifact_json_path(ctx.pedagogy_dir, support_type, language)
        with manifest_lock:
            is_fresh = manifest.is_fresh(
                support_type,
                language,
                settings_hash=settings_hash,
                source_mtime_ns=source_mtime_ns,
            )
```

Et encadrer l'enregistrement + écriture du manifeste après succès :

```python
            self._write_artifact(ctx, artifact)
            with manifest_lock:
                manifest.record(
                    support_type,
                    language,
                    settings_hash=settings_hash,
                    source_mtime_ns=source_mtime_ns,
                )
                write_manifest(ctx.artifacts, ctx.pedagogy_dir, manifest)
```

(Le reste de `_run_one` — émissions `SupportStarted`/`SupportFinished`, gestion d'erreur `Fahmi2Error` → `(0.0, True)` — est inchangé.)

- [ ] **Step 5 : Lancer toute la suite de l'orchestrateur (régression)**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/app/test_supports_orchestrator.py -v`
Expected: PASS.

> Si un test existant **assertait l'ordre des events** (ex. `events[0]`, `events[1]`) et échoue en parallèle, le rendre insensible à l'ordre : filtrer par type et/ou par clé `(support_type, language)` au lieu d'indexer. Exemple de transformation :
> ```python
> # AVANT (fragile en parallèle) :
> assert events[1].support_type is SupportType.QCM
> # APRÈS (robuste) :
> finished = {e.support_type for e in events if isinstance(e, SupportFinished)}
> assert SupportType.QCM in finished
> ```
> Les invariants déterministes restent valides : `events[-1]` est toujours `SupportGenerationFinished` (émis par `generate` après le `map_bounded`), et le premier event est `SupportGenerationStarted`.

- [ ] **Step 6 : Qualité + commit**

```bash
.venv\Scripts\python.exe -m ruff check src/fahmi2/app/supports_orchestrator.py tests/unit/app/test_supports_orchestrator.py
.venv\Scripts\python.exe -m mypy src/fahmi2/app/supports_orchestrator.py
git add src/fahmi2/app/supports_orchestrator.py tests/unit/app/test_supports_orchestrator.py
git commit -m "feat(pedagogy): generation parallele (langue x support) via map_bounded"
```

---

## Task 8 : Vérification finale (suite complète + qualité globale)

**Files:** aucun (validation).

- [ ] **Step 1 : Suite complète**

Run: `.venv\Scripts\python.exe -m pytest`
Expected: PASS (zéro échec)

- [ ] **Step 2 : Lint global**

Run: `.venv\Scripts\python.exe -m ruff check .`
Expected: `All checks passed!`

- [ ] **Step 3 : Typage global**

Run: `.venv\Scripts\python.exe -m mypy src tests`
Expected: `Success: no issues found`

- [ ] **Step 4 : Mise à jour documentation**

Mettre à jour `CLAUDE.md` (section « Mécanismes transverses ») et `docs/` :
- mentionner `core/concurrency/map_bounded` (primitif partagé) ;
- noter que la pédagogie parallélise `(langue × support)` via `pedagogy.llm_workers` (défaut 16, plage 1–64) et que le plafond de coût est *best-effort* en parallèle ;
- renvoyer au spec [2026-05-21-parallelisation-traitements-design.md](../specs/2026-05-21-parallelisation-traitements-design.md).

- [ ] **Step 5 : Commit final**

```bash
git add CLAUDE.md docs
git commit -m "docs: parallelisation pedagogie (map_bounded, llm_workers)"
```

---

## Self-review (couverture spec Lots A+B)

- **§4 `map_bounded`** → Task 1 (ordre, fail-fast, pause, séquentiel si workers=1). ✓
- **§7 aplatissement `(langue × support)` + verrous** → Task 7 (map_bounded, manifest_lock, compteur coût). ✓
- **§8 réglages** → Task 4 (domaine), Task 5 (persistance lenient), Task 6 (UI), Task 3 (timeout DeepSeek). ✓
- **§9 thread-safety (`.tmp` unique)** → Task 2. ✓
- **§10.2 plafond best-effort** → Task 7 (court-circuit + statut PAUSED). ✓
- **§10.1 pause non instantanée** → Task 1 (`_wait_or_cancel` entre soumissions). ✓

**Hors de ce plan (lot ultérieur)** : Lot C (pipeline per-video : `max_parallel_workers`, câblage moteur, `ParallelismConfig` en UI) et Lot D (phases batch internes 5/6/7). Ils feront l'objet d'un plan séparé une fois A+B livrés et validés.
