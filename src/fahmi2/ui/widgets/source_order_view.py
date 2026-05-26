"""Widget d'ordonnancement & exclusion des sources (double liste).

« Sources à traiter » (ordonnée, glisser-déposer interne pour réordonner) /
« Exclues » (non traitées). Boutons : ↑ / ↓ (réordonner), Exclure ▼ / Réinclure ▲
(déplacer entre listes), ↻ Rafraîchir (émet ``refresh_requested``), Tout réinclure.
Expose ``source_order()`` et ``excluded_sources()`` (clés stables) consommés par
``GenerationSettingsView``. Composant de **présentation pur** : la réconciliation
ordre/exclusion (fonction pure ``app.input_sources.reconcile_source_order``) est
appliquée par l'appelant, qui transmet les listes déjà réconciliées à ``populate``.
"""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
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
_ORDER_IRRELEVANT_NOTE = (
    "ⓘ Mode refonte thématique : l'ordre des sources est sans effet "
    "(seule l'inclusion / exclusion compte)."
)
_NEW_BADGE = "  • nouveau"
_UP_LABEL = "↑"
_DOWN_LABEL = "↓"
_EXCLUDE_LABEL = "Exclure ▼"
_REINCLUDE_LABEL = "Réinclure ▲"
_REFRESH_LABEL = "↻ Rafraîchir"
_REINCLUDE_ALL_LABEL = "Tout réinclure"
_LIST_MIN_HEIGHT_PX = 110
#: Poids vertical : la liste « à traiter » grandit davantage que les « exclues ».
_INCLUDED_STRETCH = 3
_EXCLUDED_STRETCH = 1


class SourceOrderView(QWidget):
    """Double liste réordonnable pour l'ordre et l'exclusion des sources."""

    refresh_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        """Construit le widget (listes vides ; appeler ``populate``).

        Args:
            parent: Parent Qt optionnel.
        """
        super().__init__(parent)
        # Vertical extensible : suit la hauteur de la fenêtre (beaucoup de sources).
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self._known: set[str] = set()
        self._kinds: dict[str, SourceKind] = {}
        self._included = QListWidget(self)
        self._included.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self._included.setMinimumHeight(_LIST_MIN_HEIGHT_PX)
        self._excluded = QListWidget(self)
        self._excluded.setMinimumHeight(_LIST_MIN_HEIGHT_PX)
        self._order_note = QLabel(_ORDER_IRRELEVANT_NOTE, self)
        self._order_note.setWordWrap(True)
        self._order_note.setVisible(False)
        self._build_layout()

    # ------------------------------------------------------------------ API

    def populate(
        self,
        available: list[InputSource],
        *,
        included: Sequence[str],
        excluded: Sequence[str],
        known: set[str],
    ) -> None:
        """Peuple les deux listes à partir de clés déjà réconciliées.

        Args:
            available: Sources disponibles (renseigne le type affiché et le badge
                « nouveau »).
            included: Clés des sources à traiter, déjà ordonnées et réconciliées.
            excluded: Clés des sources exclues, déjà réconciliées.
            known: Clés présentes dans l'état persisté/courant ; les sources
                absentes de cet ensemble reçoivent le badge « nouveau ».
        """
        self._kinds = {s.order_key(): s.kind for s in available}
        self._known = set(known)
        self._included.clear()
        self._excluded.clear()
        for key in included:
            self._included.addItem(self._make_item(key))
        for key in excluded:
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

    def set_order_irrelevant(self, irrelevant: bool) -> None:
        """Affiche la note quand l'ordre des sources est ignoré (mode thématique).

        L'inclusion / exclusion reste pertinente : seul l'**ordre** n'a pas d'effet.

        Args:
            irrelevant: ``True`` pour signaler que l'ordre n'a pas d'effet.
        """
        self._order_note.setVisible(irrelevant)

    # -------------------------------------------------------------- internes

    @staticmethod
    def _keys(widget: QListWidget) -> tuple[str, ...]:
        """Extrait les clés stockées des items d'une liste, dans l'ordre.

        Args:
            widget: Liste à parcourir.

        Returns:
            Les clés (rôle ``_KEY_ROLE``) dans l'ordre d'affichage.
        """
        keys: list[str] = []
        for i in range(widget.count()):
            item = widget.item(i)
            if item is not None:
                keys.append(str(item.data(_KEY_ROLE)))
        return tuple(keys)

    def _make_item(self, key: str) -> QListWidgetItem:
        """Construit un item d'affichage pour une clé de source.

        Args:
            key: Clé de la source (stockée dans le rôle ``_KEY_ROLE``).

        Returns:
            L'item libellé ``[TYPE] clé`` avec un badge « nouveau » si la clé est
            absente de l'ensemble ``_known``.
        """
        kind = self._kinds.get(key, SourceKind.VIDEO)
        badge = "" if key in self._known else _NEW_BADGE
        item = QListWidgetItem(f"[{_KIND_LABELS[kind]}] {key}{badge}")
        item.setData(_KEY_ROLE, key)
        return item

    @staticmethod
    def _move(src: QListWidget, dst: QListWidget, key: str) -> None:
        """Déplace l'item de clé ``key`` de ``src`` vers la fin de ``dst``.

        Args:
            src: Liste source.
            dst: Liste destination.
            key: Clé de l'item à déplacer (sans effet si introuvable).
        """
        for i in range(src.count()):
            item = src.item(i)
            if item is not None and item.data(_KEY_ROLE) == key:
                dst.addItem(src.takeItem(i))
                return

    def _exclude_selected(self) -> None:
        """Exclut la source actuellement sélectionnée dans la liste des incluses."""
        item = self._included.currentItem()
        if item is not None:
            self.exclude_key(str(item.data(_KEY_ROLE)))

    def _reinclude_selected(self) -> None:
        """Réintègre la source actuellement sélectionnée dans la liste des exclues."""
        item = self._excluded.currentItem()
        if item is not None:
            self._move(self._excluded, self._included, str(item.data(_KEY_ROLE)))

    def _move_selected(self, delta: int) -> None:
        """Déplace la source incluse sélectionnée de ``delta`` positions.

        Args:
            delta: Décalage (``-1`` = monter, ``+1`` = descendre) ; sans effet si
                la cible sort des bornes de la liste.
        """
        row = self._included.currentRow()
        target = row + delta
        if row < 0 or target < 0 or target >= self._included.count():
            return
        item = self._included.takeItem(row)
        self._included.insertItem(target, item)
        self._included.setCurrentRow(target)

    def _build_layout(self) -> None:
        """Assemble les deux listes, les boutons de déplacement et la barre d'actions."""
        outer = QVBoxLayout(self)
        outer.addWidget(self._order_note)
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
        outer.addLayout(included_row, stretch=_INCLUDED_STRETCH)

        outer.addWidget(QLabel(_EXCLUDED_TITLE, self))
        excluded_row = QHBoxLayout()
        excluded_row.addWidget(self._excluded, stretch=1)
        reinclude_btn = QPushButton(_REINCLUDE_LABEL, self)
        reinclude_btn.clicked.connect(self._reinclude_selected)
        excluded_buttons = QVBoxLayout()
        excluded_buttons.addWidget(reinclude_btn)
        excluded_buttons.addStretch(1)
        excluded_row.addLayout(excluded_buttons)
        outer.addLayout(excluded_row, stretch=_EXCLUDED_STRETCH)

        actions_row = QHBoxLayout()
        refresh_btn = QPushButton(_REFRESH_LABEL, self)
        refresh_btn.clicked.connect(self.refresh_requested.emit)
        reinclude_all_btn = QPushButton(_REINCLUDE_ALL_LABEL, self)
        reinclude_all_btn.clicked.connect(self.reinclude_all)
        actions_row.addWidget(refresh_btn)
        actions_row.addWidget(reinclude_all_btn)
        actions_row.addStretch(1)
        outer.addLayout(actions_row)
