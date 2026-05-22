"""Widget d'ordonnancement & exclusion des sources (double liste).

« Sources à traiter » (ordonnée, glisser-déposer interne pour réordonner) /
« Exclues » (non traitées). Boutons : ↑ / ↓ (réordonner), Exclure ▼ / Réinclure ▲
(déplacer entre listes), ↻ Rafraîchir (émet ``refresh_requested``), Tout réinclure.
Expose ``source_order()`` et ``excluded_sources()`` (clés stables) consommés par
``GenerationSettingsView``. La logique de réconciliation est déléguée à la
fonction pure ``app.input_sources.reconcile_source_order``.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from fahmi2.domain.enums import SourceKind
from fahmi2.domain.source import InputSource

_KEY_ROLE = Qt.ItemDataRole.UserRole
_KIND_LABELS: dict[SourceKind, str] = {
    SourceKind.VIDEO: "VID",
    SourceKind.AUDIO: "AUD",
    SourceKind.DOCUMENT: "DOC",
    SourceKind.YOUTUBE: "YT",
}
_INCLUDED_TITLE = "Sources à traiter — ordre des chapitres"
_EXCLUDED_TITLE = "Exclues — non traitées"
_NEW_BADGE = "  • nouveau"
_UP_LABEL = "↑"
_DOWN_LABEL = "↓"
_EXCLUDE_LABEL = "Exclure ▼"
_REINCLUDE_LABEL = "Réinclure ▲"
_REFRESH_LABEL = "↻ Rafraîchir"
_REINCLUDE_ALL_LABEL = "Tout réinclure"
_LIST_MIN_HEIGHT_PX = 110


class SourceOrderView(QWidget):
    """Double liste réordonnable pour l'ordre et l'exclusion des sources."""

    refresh_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        """Construit le widget (listes vides ; appeler ``populate``).

        Args:
            parent: Parent Qt optionnel.
        """
        super().__init__(parent)
        self._known: set[str] = set()
        self._kinds: dict[str, SourceKind] = {}
        self._included = QListWidget(self)
        self._included.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self._included.setMinimumHeight(_LIST_MIN_HEIGHT_PX)
        self._excluded = QListWidget(self)
        self._excluded.setMinimumHeight(_LIST_MIN_HEIGHT_PX)
        self._build_layout()

    # ------------------------------------------------------------------ API

    def populate(
        self,
        available: list[InputSource],
        source_order: tuple[str, ...],
        excluded: tuple[str, ...],
    ) -> None:
        """Peuple les deux listes via la réconciliation pure.

        Args:
            available: Sources disponibles (dans l'ordre de collecte).
            source_order: Clés ordonnées des incluses (état persisté/courant).
            excluded: Clés des exclues (état persisté/courant).
        """
        from fahmi2.app.input_sources import (  # noqa: PLC0415 — éviter cycle app↔ui
            reconcile_source_order,
        )

        self._kinds = {s.order_key(): s.kind for s in available}
        self._known = set(source_order) | set(excluded)
        keys = [s.order_key() for s in available]
        included, excluded_keys = reconcile_source_order(keys, source_order, excluded)
        self._included.clear()
        self._excluded.clear()
        for key in included:
            self._included.addItem(self._make_item(key))
        for key in excluded_keys:
            self._excluded.addItem(self._make_item(key))

    def source_order(self) -> tuple[str, ...]:
        """Clés des sources incluses, dans l'ordre courant de la liste."""
        return self._keys(self._included)

    def excluded_sources(self) -> tuple[str, ...]:
        """Clés des sources exclues."""
        return self._keys(self._excluded)

    def exclude_key(self, key: str) -> None:
        """Déplace la source ``key`` des incluses vers les exclues."""
        self._move(self._included, self._excluded, key)

    def reinclude_all(self) -> None:
        """Réintègre toutes les sources exclues (en fin de liste des incluses)."""
        while self._excluded.count():
            item = self._excluded.takeItem(0)
            if item is not None:
                self._included.addItem(item)

    # -------------------------------------------------------------- internes

    @staticmethod
    def _keys(widget: QListWidget) -> tuple[str, ...]:
        keys: list[str] = []
        for i in range(widget.count()):
            item = widget.item(i)
            if item is not None:
                keys.append(str(item.data(_KEY_ROLE)))
        return tuple(keys)

    def _make_item(self, key: str) -> QListWidgetItem:
        kind = self._kinds.get(key, SourceKind.VIDEO)
        badge = "" if key in self._known else _NEW_BADGE
        item = QListWidgetItem(f"[{_KIND_LABELS[kind]}] {key}{badge}")
        item.setData(_KEY_ROLE, key)
        return item

    @staticmethod
    def _move(src: QListWidget, dst: QListWidget, key: str) -> None:
        for i in range(src.count()):
            item = src.item(i)
            if item is not None and item.data(_KEY_ROLE) == key:
                dst.addItem(src.takeItem(i))
                return

    def _exclude_selected(self) -> None:
        item = self._included.currentItem()
        if item is not None:
            self.exclude_key(str(item.data(_KEY_ROLE)))

    def _reinclude_selected(self) -> None:
        item = self._excluded.currentItem()
        if item is not None:
            self._move(self._excluded, self._included, str(item.data(_KEY_ROLE)))

    def _move_selected(self, delta: int) -> None:
        row = self._included.currentRow()
        target = row + delta
        if row < 0 or target < 0 or target >= self._included.count():
            return
        item = self._included.takeItem(row)
        self._included.insertItem(target, item)
        self._included.setCurrentRow(target)

    def _build_layout(self) -> None:
        outer = QVBoxLayout(self)
        outer.addWidget(QLabel(_INCLUDED_TITLE, self))

        included_row = QHBoxLayout()
        included_row.addWidget(self._included, stretch=1)
        included_buttons = QVBoxLayout()
        up_btn = QPushButton(_UP_LABEL, self)
        up_btn.clicked.connect(lambda: self._move_selected(-1))
        down_btn = QPushButton(_DOWN_LABEL, self)
        down_btn.clicked.connect(lambda: self._move_selected(1))
        exclude_btn = QPushButton(_EXCLUDE_LABEL, self)
        exclude_btn.clicked.connect(self._exclude_selected)
        for btn in (up_btn, down_btn, exclude_btn):
            included_buttons.addWidget(btn)
        included_buttons.addStretch(1)
        included_row.addLayout(included_buttons)
        outer.addLayout(included_row)

        outer.addWidget(QLabel(_EXCLUDED_TITLE, self))
        excluded_row = QHBoxLayout()
        excluded_row.addWidget(self._excluded, stretch=1)
        reinclude_btn = QPushButton(_REINCLUDE_LABEL, self)
        reinclude_btn.clicked.connect(self._reinclude_selected)
        excluded_buttons = QVBoxLayout()
        excluded_buttons.addWidget(reinclude_btn)
        excluded_buttons.addStretch(1)
        excluded_row.addLayout(excluded_buttons)
        outer.addLayout(excluded_row)

        actions_row = QHBoxLayout()
        refresh_btn = QPushButton(_REFRESH_LABEL, self)
        refresh_btn.clicked.connect(self.refresh_requested.emit)
        reinclude_all_btn = QPushButton(_REINCLUDE_ALL_LABEL, self)
        reinclude_all_btn.clicked.connect(self.reinclude_all)
        actions_row.addWidget(refresh_btn)
        actions_row.addWidget(reinclude_all_btn)
        actions_row.addStretch(1)
        outer.addLayout(actions_row)
