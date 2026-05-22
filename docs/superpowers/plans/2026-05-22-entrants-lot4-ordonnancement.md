# Lot 4 — Ordonnancement & exclusion des sources (plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Donner un **contrôle d'ordre explicite** des sources (dans tous les cas) et la possibilité d'**exclure/réinclure** une source, via une **double liste** (« Sources à traiter » ordonnée / « Exclues ») dans les réglages de génération.

**Architecture:** Une **fonction pure** `reconcile_source_order(available_keys, source_order, excluded)` (testable sans Qt) est **partagée** entre `build_input_sources` (ordre/exclusion au niveau Run) et l'UI (peuplement de la double liste). `GenerationSettings` gagne `source_order` (clés ordonnées des incluses) et `excluded_sources` (clés exclues), clés stables = `InputSource.order_key()` (nom de fichier / URL). Le widget `SourceOrderView` (double `QListWidget`) édite l'état (glisser-déposer interne pour réordonner ; boutons Exclure/Réinclure/Rafraîchir/Tout réinclure) et expose `source_order()` / `excluded_sources()`.

**Tech Stack:** Python 3.12, PySide6 (`QListWidget` InternalMove), pytest + pytest-qt (smoke), ruff (line-length 100), mypy --strict. Interpréteur : `.venv\Scripts\python.exe`.

**Prérequis:** Lots 1A/1B/2/3 (toutes les familles de sources + `build_input_sources` fichiers+URLs).

**Spec de référence:** `docs/superpowers/specs/2026-05-22-entrants-generation-elargis-design.md` (§7, §8.1, §8.2, §8.3). Maquette validée : `.superpowers/brainstorm/.../sources-ordering-v2.html`.

**Limite assumée :** la **durée** par source (montrée dans la maquette) est **omise** dans le widget (sonder ffmpeg/yt-dlp à l'ouverture du dialogue serait lent) ; chaque ligne affiche rang + type + nom/URL + badge « nouveau ».

---

## Tâche 1 : `source_order` + `excluded_sources` (domain + persistance + fixture)

**Files:** Modify `src/fahmi2/domain/generation.py`, `src/fahmi2/infra/storage/sqlite_state.py`, `tests/conftest.py` ; Test `tests/unit/domain/test_generation.py`

- [ ] **Step 1: Domaine** — `GenerationSettings` : après `youtube_urls`, ajouter
```python
    source_order: tuple[str, ...] = ()
    excluded_sources: tuple[str, ...] = ()
```
+ docstring (`source_order`: ordre des clés stables des sources incluses ; `excluded_sources`: clés des sources exclues. Clés = nom de fichier ou URL.).

- [ ] **Step 2: Persistance** — `_serialize_generation_settings` : `"source_order": list(gen.source_order), "excluded_sources": list(gen.excluded_sources),`. `_deserialize_generation_settings` : `source_order=tuple(payload.get("source_order", [])), excluded_sources=tuple(payload.get("excluded_sources", [])),`.

- [ ] **Step 3: Fixture** — `conftest.py` : `"source_order": (), "excluded_sources": (),`.

- [ ] **Step 4: Test** :
```python
def test_source_order_and_excluded_default_empty() -> None:
    s = _make()
    assert s.source_order == ()
    assert s.excluded_sources == ()
    s2 = _make(source_order=("b.mp4", "a.mp4"), excluded_sources=("c.mp4",))
    assert s2.source_order == ("b.mp4", "a.mp4")
    assert s2.excluded_sources == ("c.mp4",)
```

- [ ] **Step 5: Lancer** — `pytest tests/unit/domain/test_generation.py tests/unit/infra/storage -q` → PASS
- [ ] **Step 6: Commit** — `git commit -m "feat(generation): source_order + excluded_sources (domain + persistance)"`

---

## Tâche 2 : Réconciliation pure + `build_input_sources`

**Files:** Modify `src/fahmi2/app/input_sources.py` ; Test `tests/unit/app/test_input_sources.py`

- [ ] **Step 1: Écrire les tests de réconciliation**

```python
# tests/unit/app/test_input_sources.py — ajouter
from fahmi2.app.input_sources import reconcile_source_order


def test_reconcile_orders_and_appends_new() -> None:
    available = ["a.mp4", "b.mp4", "c.mp4"]
    included, excluded = reconcile_source_order(
        available, source_order=("c.mp4", "a.mp4"), excluded=()
    )
    # c, a explicitement ordonnées ; b (nouvelle) ajoutée en fin
    assert included == ["c.mp4", "a.mp4", "b.mp4"]
    assert excluded == []


def test_reconcile_filters_excluded_and_ignores_stale() -> None:
    available = ["a.mp4", "b.mp4"]
    included, excluded = reconcile_source_order(
        available, source_order=("a.mp4",), excluded=("b.mp4", "obsolete.mp4")
    )
    assert included == ["a.mp4"]
    assert excluded == ["b.mp4"]  # obsolete.mp4 (absente) ignorée


def test_reconcile_empty_order_keeps_available_order() -> None:
    available = ["a.mp4", "b.mp4"]
    included, excluded = reconcile_source_order(available, source_order=(), excluded=())
    assert included == ["a.mp4", "b.mp4"]
```

Et pour `build_input_sources` :
```python
def test_build_respects_source_order_and_exclusion(tmp_path, make_generation_settings):
    (tmp_path / "a.mp4").write_bytes(b"x")
    (tmp_path / "b.mp4").write_bytes(b"x")
    (tmp_path / "c.mp4").write_bytes(b"x")
    settings = make_generation_settings(
        input_folder=tmp_path,
        source_order=("c.mp4", "a.mp4"),
        excluded_sources=("b.mp4",),
    )
    sources = build_input_sources(settings)
    assert [s.source.order_key() for s in sources] == ["c.mp4", "a.mp4"]
```

- [ ] **Step 2: Lancer (échec)** — `reconcile_source_order` absente ; `build_input_sources` ignore l'ordre.

- [ ] **Step 3: Implémenter** dans `input_sources.py` :

```python
def reconcile_source_order(
    available_keys: list[str],
    source_order: tuple[str, ...],
    excluded: tuple[str, ...],
) -> tuple[list[str], list[str]]:
    """Réconcilie l'ordre/exclusion persistés avec les sources réellement présentes.

    Args:
        available_keys: Clés des sources présentes, dans l'ordre de collecte
            (fichiers triés naturellement puis URLs).
        source_order: Clés ordonnées des sources à inclure (persistées).
        excluded: Clés des sources exclues (persistées).

    Returns:
        ``(included_keys, excluded_keys)`` : les incluses ordonnées (clés de
        ``source_order`` présentes d'abord, puis les nouvelles dans l'ordre de
        collecte), et les exclues encore présentes. Les clés obsolètes (absentes
        de ``available_keys``) sont ignorées.
    """
    excluded_set = set(excluded)
    excluded_keys = [k for k in available_keys if k in excluded_set]
    non_excluded = [k for k in available_keys if k not in excluded_set]
    non_excluded_set = set(non_excluded)
    ordered = [k for k in source_order if k in non_excluded_set]
    ordered_set = set(ordered)
    ordered += [k for k in non_excluded if k not in ordered_set]
    return ordered, excluded_keys
```

`build_input_sources` (après collecte de `file_sources + youtube_sources` → `collected`) :
```python
    by_key = {s.source.order_key(): s for s in collected}
    available_keys = [s.source.order_key() for s in collected]
    included_keys, _ = reconcile_source_order(
        available_keys, settings.source_order, settings.excluded_sources
    )
    result = [by_key[k] for k in included_keys]
    if not result:
        raise ConfigError(... NO_INPUT_SOURCE ...)  # message existant
    return result
```
(Extraire la collecte `file_sources + youtube_sources` ; supprimer l'ancien test `if not all_sources` au profit de `if not result`. Note : si toutes les sources sont exclues, `result` est vide → `NO_INPUT_SOURCE` — adapter le message : « …ou toutes les sources sont exclues ».) Ajouter `collect_available_sources(settings) -> list[InputSource]` (collecte brute, sans reconcile ni lever) réutilisée par l'UI :
```python
def collect_available_sources(settings: GenerationSettings) -> list[InputSource]:
    """Liste les sources présentes (fichiers + URLs), sans ordre/exclusion appliqués."""
    file_sources = _scan_files(settings.input_folder, has_urls=bool(settings.youtube_urls))
    youtube = [InputSource(kind=SourceKind.YOUTUBE, location=u) for u in settings.youtube_urls]
    return [s.source for s in file_sources] + youtube
```
(et `build_input_sources` se factorise pour réutiliser cette collecte — au choix : garder `_scan_files` interne et construire `collected` de `SourceExecution`.)

- [ ] **Step 4: Lancer (succès)** — `pytest tests/unit/app/test_input_sources.py -q` → PASS
- [ ] **Step 5: Commit** — `git commit -m "feat(ingestion): reconcile_source_order (ordre + exclusion) dans build_input_sources"`

---

## Tâche 3 : Widget `SourceOrderView` (double liste)

**Files:** Create `src/fahmi2/ui/widgets/source_order_view.py` ; Test `tests/unit/ui/test_source_order_view.py`

- [ ] **Step 1: Écrire le smoke test (pytest-qt)**

```python
# tests/unit/ui/test_source_order_view.py
from fahmi2.domain.enums import SourceKind
from fahmi2.domain.source import InputSource
from fahmi2.ui.widgets.source_order_view import SourceOrderView


def _src(name: str, kind: SourceKind = SourceKind.VIDEO) -> InputSource:
    return InputSource(kind=kind, location=name)


def test_populate_and_getters(qtbot) -> None:
    view = SourceOrderView()
    qtbot.addWidget(view)
    available = [_src("a.mp4"), _src("b.mp4"), _src("c.mp4")]
    view.populate(available, source_order=("c.mp4", "a.mp4"), excluded=("b.mp4",))
    assert view.source_order() == ("c.mp4", "a.mp4")
    assert view.excluded_sources() == ("b.mp4",)


def test_exclude_and_reinclude(qtbot) -> None:
    view = SourceOrderView()
    qtbot.addWidget(view)
    view.populate([_src("a.mp4"), _src("b.mp4")], source_order=(), excluded=())
    view.exclude_key("a.mp4")
    assert "a.mp4" in view.excluded_sources()
    assert "a.mp4" not in view.source_order()
    view.reinclude_all()
    assert view.excluded_sources() == ()
    assert set(view.source_order()) == {"a.mp4", "b.mp4"}
```

- [ ] **Step 2: Lancer (échec)** — module absent.

- [ ] **Step 3: Implémenter `source_order_view.py`**

Squelette (PySide6) — chaque item porte sa **clé** en `Qt.UserRole`, son **type** est affiché via une pastille texte. La liste « incluses » est en `InternalMove` (réordonnancement par glisser). Méthodes publiques : `populate(available, source_order, excluded)`, `source_order()`, `excluded_sources()`, `exclude_key(key)`, `reinclude_all()` ; signal `refreshRequested`.

```python
"""Widget d'ordonnancement & exclusion des sources (double liste).

« Sources à traiter » (ordonnée, glisser-déposer interne pour réordonner) /
« Exclues » (non traitées). Boutons : Exclure ▼ / Réinclure ▲ / ↻ Rafraîchir /
Tout réinclure. Expose ``source_order()`` et ``excluded_sources()`` (clés
stables) consommés par ``GenerationSettingsView``.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QPushButton, QVBoxLayout, QWidget,
)

from fahmi2.domain.enums import SourceKind
from fahmi2.domain.source import InputSource

_KEY_ROLE = Qt.ItemDataRole.UserRole
_KIND_LABELS: dict[SourceKind, str] = {
    SourceKind.VIDEO: "VID", SourceKind.AUDIO: "AUD",
    SourceKind.DOCUMENT: "DOC", SourceKind.YOUTUBE: "YT",
}
_INCLUDED_TITLE = "Sources à traiter — ordre des chapitres"
_EXCLUDED_TITLE = "Exclues — non traitées"
_NEW_BADGE = "  • nouveau"


class SourceOrderView(QWidget):
    """Double liste réordonnable pour l'ordre/exclusion des sources."""

    refreshRequested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._known: set[str] = set()
        self._kinds: dict[str, SourceKind] = {}
        self._included = QListWidget(self)
        self._included.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self._excluded = QListWidget(self)
        self._build_layout()

    # — API publique —
    def populate(
        self,
        available: list[InputSource],
        source_order: tuple[str, ...],
        excluded: tuple[str, ...],
    ) -> None:
        """Peuple les deux listes via la réconciliation pure."""
        from fahmi2.app.input_sources import reconcile_source_order  # noqa: PLC0415

        self._kinds = {s.order_key(): s.kind for s in available}
        self._known = set(source_order) | set(excluded)
        keys = [s.order_key() for s in available]
        included, excluded_keys = reconcile_source_order(keys, source_order, excluded)
        self._included.clear()
        self._excluded.clear()
        for k in included:
            self._included.addItem(self._make_item(k))
        for k in excluded_keys:
            self._excluded.addItem(self._make_item(k))

    def source_order(self) -> tuple[str, ...]:
        """Clés des sources incluses, dans l'ordre courant de la liste."""
        return tuple(
            self._included.item(i).data(_KEY_ROLE) for i in range(self._included.count())
        )

    def excluded_sources(self) -> tuple[str, ...]:
        """Clés des sources exclues."""
        return tuple(
            self._excluded.item(i).data(_KEY_ROLE) for i in range(self._excluded.count())
        )

    def exclude_key(self, key: str) -> None:
        """Déplace une source vers les exclues (testable sans interaction)."""
        self._move(self._included, self._excluded, key)

    def reinclude_all(self) -> None:
        """Réintègre toutes les sources exclues (dans les incluses)."""
        while self._excluded.count():
            item = self._excluded.takeItem(0)
            self._included.addItem(item)

    # — internes —
    def _make_item(self, key: str) -> QListWidgetItem:
        kind = self._kinds.get(key, SourceKind.VIDEO)
        badge = "" if key in self._known else _NEW_BADGE
        item = QListWidgetItem(f"[{_KIND_LABELS[kind]}] {key}{badge}")
        item.setData(_KEY_ROLE, key)
        return item

    @staticmethod
    def _move(src: QListWidget, dst: QListWidget, key: str) -> None:
        for i in range(src.count()):
            if src.item(i).data(_KEY_ROLE) == key:
                dst.addItem(src.takeItem(i))
                return

    def _build_layout(self) -> None:
        # ... boutons (Exclure/Réinclure sélection, ↑/↓, Rafraîchir, Tout réinclure)
        # connectés aux méthodes ci-dessus ; layout vertical
        # (Rafraîchir émet refreshRequested ; Tout réinclure → reinclude_all).
        ...
```
> Implémenter `_build_layout` complètement (titres `QLabel`, les 2 `QListWidget`,
> une rangée de boutons : « Exclure ▼ » → `exclude_key` sur l'item sélectionné des
> incluses ; « Réinclure ▲ » → déplacer la sélection des exclues vers incluses ;
> « ↑ »/« ↓ » → réordonner la sélection des incluses ; « ↻ Rafraîchir » →
> `self.refreshRequested.emit()` ; « Tout réinclure » → `reinclude_all`).

- [ ] **Step 4: Lancer (succès)** — `pytest tests/unit/ui/test_source_order_view.py -q` → PASS
- [ ] **Step 5: Commit** — `git commit -m "feat(ui): widget SourceOrderView (double liste ordre/exclusion)"`

---

## Tâche 4 : Intégration dans `GenerationSettingsView`

**Files:** Modify `src/fahmi2/ui/dialogs/generation_settings_view.py` ; Modify `tests/unit/ui/test_generation_settings_view.py`

- [ ] **Step 1: Champ + page** — `_build_fields` : `self._source_order_view = SourceOrderView(self)` ; connecter `self._source_order_view.refreshRequested` à `self._refresh_source_order`. Ajouter le widget à la page « Entrée & langues » (sous les URLs) via `form.addRow(self._source_order_view)` (ou une page dédiée « Ordre des sources »).

- [ ] **Step 2: Peuplement** — méthode `_refresh_source_order(self)` : construit un `GenerationSettings` *partiel* impossible ; à la place, appeler un helper qui scanne **depuis les champs courants** (input_folder + URLs). Réutiliser `collect_available_sources` en fabriquant un `GenerationSettings` minimal **n'est pas idéal** → exposer plutôt une surcharge `collect_available_sources_from(input_folder: Path, youtube_urls: tuple[str, ...])`. Le `_refresh_source_order` lit `self._input_folder_input.text()` + parse les URLs, appelle le helper, puis `self._source_order_view.populate(available, source_order_courant, excluded_courant)`.
  - À l'ouverture (`_populate`) : appeler `_refresh_source_order` avec `generation.source_order` / `generation.excluded_sources` comme état initial.
  - Au **Rafraîchir** : ré-appeler avec l'état **courant** du widget (`source_order()` / `excluded_sources()`).

- [ ] **Step 3: Sauvegarde** — `_on_accept` : `source_order=self._source_order_view.source_order(), excluded_sources=self._source_order_view.excluded_sources(),` passés au constructeur `GenerationSettings`.

- [ ] **Step 4: Helper de collecte** — dans `app/input_sources.py`, refactor : `collect_available_sources(settings)` délègue à `collect_available_sources_from(settings.input_folder, settings.youtube_urls)` (signature directe pour l'UI qui n'a pas encore de `GenerationSettings` complet).

- [ ] **Step 5: Lancer** — `pytest tests/unit/ui/test_generation_settings_view.py -q` → PASS (adapter le test si besoin : le widget doit être peuplé après `_populate`).

- [ ] **Step 6: Commit** — `git commit -m "feat(ui): double liste ordre/exclusion dans les reglages de generation"`

---

## Tâche 5 : Repasse qualité finale + doc

- [ ] **Step 1: Suite + lint + types**

Run:
```
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m mypy src tests
```
Expected: tout vert.

- [ ] **Step 2: Documentation**
- `CLAUDE.md` : mécanisme entrants — ajouter `source_order`/`excluded_sources` (réconciliés au scan via `reconcile_source_order`) + double liste UI.
- Marquer le chantier « entrants élargis » complet (les 4 lots) si une note de suivi existe.

- [ ] **Step 3: Commit doc** — `git commit -m "docs: ordonnancement & exclusion des sources (Lot 4)"`

---

## Self-review (rédacteur)
- **Spec §7.1** : `source_order` + `excluded_sources` (T1) ✓.
- **Spec §7.2** : `reconcile_source_order` (filtre exclues, ordonne, nouveaux en fin, clés obsolètes ignorées) + `build_input_sources` (T2) ✓.
- **Spec §7.3** : widget double liste (T3) + intégration + Rafraîchir conserve les exclusions / Tout réinclure (T4) ✓.
- **DRY** : `reconcile_source_order` partagée build_input_sources ↔ widget ✓.
- **Type consistency** : clés = `InputSource.order_key()` partout ✓.
- **Constantes** : `_KEY_ROLE`, `_KIND_LABELS`, titres, badge ✓.

## Clôture du chantier « entrants élargis »
Après ce lot : vidéo, audio, documents, YouTube + ordonnancement/exclusion — fonctionnalité complète. Reste hors périmètre (backlog) : `2026-05-22-modes-consolidation-backlog.md` (modes de consolidation intelligent/thématique).
