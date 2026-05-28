"""Widget d'ordonnancement & exclusion des sources (double liste).

Présentation :

- *Sources à traiter* (liste ordonnée, glisser-déposer interne pour réordonner)
  avec une barre d'actions **sous** la liste (▲ monter, ▼ descendre, Exclure).
- *Sources exclues* (non traitées) avec une barre d'actions **sous** la liste
  (Réinclure).
- En bas, deux boutons globaux : « ↻ Rafraîchir » et « Tout réinclure ».

Expose ``source_order()`` et ``excluded_sources()`` (clés stables) consommés
par ``GenerationSettingsView``. Composant de **présentation pur** : la
réconciliation ordre/exclusion (fonction pure
``app.input_sources.reconcile_source_order``) est appliquée par l'appelant,
qui transmet les listes déjà réconciliées à ``populate``.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final

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

_KEY_ROLE: Final[int] = int(Qt.ItemDataRole.UserRole)
#: Codes courts de type de source affichés en préfixe — universels (pas
#: traduits ; restent stables d'une langue à l'autre).
_KIND_LABELS: Final[dict[SourceKind, str]] = {
    SourceKind.VIDEO: "VID",
    SourceKind.AUDIO: "AUD",
    SourceKind.DOCUMENT: "DOC",
    SourceKind.YOUTUBE: "YT",
}

# Hauteurs des listes (px) — bornées pour éviter l'étirement infini dans une
# carte qui aurait du ``stretch=1`` côté layout parent.
_INCLUDED_LIST_MIN_HEIGHT: Final[int] = 160
_INCLUDED_LIST_MAX_HEIGHT: Final[int] = 280
_EXCLUDED_LIST_MIN_HEIGHT: Final[int] = 90
_EXCLUDED_LIST_MAX_HEIGHT: Final[int] = 160

# Espacements internes.
_OUTER_SPACING: Final[int] = 10
_LIST_TO_ACTIONS_SPACING: Final[int] = 6
_ACTIONS_ROW_SPACING: Final[int] = 6
_SECTION_TOP_SPACING: Final[int] = 8


class SourceOrderView(QWidget):
    """Double liste réordonnable pour l'ordre et l'exclusion des sources."""

    refresh_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        """Construit le widget (listes vides ; appeler ``populate``).

        Args:
            parent: Parent Qt optionnel.
        """
        super().__init__(parent)
        # Politique : grandir si besoin mais ne pas se réclamer plus de place
        # que nécessaire (les listes ont leurs propres min/max).
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self._known: set[str] = set()
        self._kinds: dict[str, SourceKind] = {}

        self._included = QListWidget(self)
        self._included.setObjectName("sourceOrderList")
        self._included.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self._included.setMinimumHeight(_INCLUDED_LIST_MIN_HEIGHT)
        self._included.setMaximumHeight(_INCLUDED_LIST_MAX_HEIGHT)

        self._excluded = QListWidget(self)
        self._excluded.setObjectName("sourceOrderList")
        self._excluded.setMinimumHeight(_EXCLUDED_LIST_MIN_HEIGHT)
        self._excluded.setMaximumHeight(_EXCLUDED_LIST_MAX_HEIGHT)

        self._order_note = QLabel(
            self.tr(
                "ⓘ Mode refonte thématique : l'ordre des sources est sans effet "
                "(seule l'inclusion / exclusion compte)."
            ),
            self,
        )
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

        L'inclusion / exclusion reste pertinente : seul l'**ordre** n'a pas
        d'effet.

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
            L'item libellé ``[TYPE] clé`` avec un badge « nouveau » si la clé
            est absente de l'ensemble ``_known``.
        """
        kind = self._kinds.get(key, SourceKind.VIDEO)
        badge = "" if key in self._known else self.tr("  • nouveau")
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
            delta: Décalage (``-1`` = monter, ``+1`` = descendre) ; sans effet
                si la cible sort des bornes de la liste.
        """
        row = self._included.currentRow()
        target = row + delta
        if row < 0 or target < 0 or target >= self._included.count():
            return
        item = self._included.takeItem(row)
        self._included.insertItem(target, item)
        self._included.setCurrentRow(target)

    def _build_layout(self) -> None:
        """Assemble titres + listes + barres d'actions horizontales sous chaque liste."""
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(_OUTER_SPACING)

        outer.addWidget(self._order_note)
        outer.addWidget(
            self._make_section_title(
                self.tr("Sources à traiter — ordre des chapitres")
            )
        )
        outer.addWidget(self._included)
        outer.addWidget(self._build_included_actions())
        outer.addSpacing(_SECTION_TOP_SPACING)
        outer.addWidget(self._make_section_title(self.tr("Sources exclues")))
        outer.addWidget(self._excluded)
        outer.addWidget(self._build_excluded_actions())
        outer.addSpacing(_SECTION_TOP_SPACING)
        outer.addWidget(self._build_global_actions())

    def _make_section_title(self, text: str) -> QLabel:
        """Construit un titre de section (libellé en gras au-dessus d'une liste).

        Args:
            text: Texte du titre.

        Returns:
            Le ``QLabel`` configuré.
        """
        label = QLabel(text, self)
        label.setStyleSheet("font-weight: 600;")
        return label

    def _build_included_actions(self) -> QWidget:
        """Barre d'actions sous la liste « Sources à traiter » (Monter/Descendre/Exclure).

        Returns:
            Le conteneur prêt à être ajouté au layout vertical externe.
        """
        wrap = QWidget(self)
        # Les barres d'actions sont placées dans une carte blanche ; on évite
        # que le wrapper hérite du fond gris global ``QWidget`` via le QSS.
        wrap.setStyleSheet("background: transparent;")
        row = QHBoxLayout(wrap)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(_ACTIONS_ROW_SPACING)
        up_btn = QPushButton(self.tr("▲ Monter"), wrap)
        up_btn.setToolTip(self.tr("Monter la source sélectionnée d'une position"))
        up_btn.clicked.connect(lambda: self._move_selected(-1))
        down_btn = QPushButton(self.tr("▼ Descendre"), wrap)
        down_btn.setToolTip(
            self.tr("Descendre la source sélectionnée d'une position")
        )
        down_btn.clicked.connect(lambda: self._move_selected(1))
        exclude_btn = QPushButton(self.tr("Exclure"), wrap)
        exclude_btn.setToolTip(self.tr("Exclure la source sélectionnée du traitement"))
        exclude_btn.clicked.connect(self._exclude_selected)
        row.addWidget(up_btn)
        row.addWidget(down_btn)
        row.addWidget(exclude_btn)
        row.addStretch(1)
        return wrap

    def _build_excluded_actions(self) -> QWidget:
        """Barre d'actions sous la liste « Sources exclues » (Réinclure).

        Returns:
            Le conteneur prêt à être ajouté au layout vertical externe.
        """
        wrap = QWidget(self)
        # Les barres d'actions sont placées dans une carte blanche ; on évite
        # que le wrapper hérite du fond gris global ``QWidget`` via le QSS.
        wrap.setStyleSheet("background: transparent;")
        row = QHBoxLayout(wrap)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(_ACTIONS_ROW_SPACING)
        reinclude_btn = QPushButton(self.tr("Réinclure"), wrap)
        reinclude_btn.setToolTip(self.tr("Réintégrer la source sélectionnée"))
        reinclude_btn.clicked.connect(self._reinclude_selected)
        row.addWidget(reinclude_btn)
        row.addStretch(1)
        return wrap

    def _build_global_actions(self) -> QWidget:
        """Barre d'actions globales (Rafraîchir, Tout réinclure).

        Returns:
            Le conteneur prêt à être ajouté au layout vertical externe.
        """
        wrap = QWidget(self)
        # Les barres d'actions sont placées dans une carte blanche ; on évite
        # que le wrapper hérite du fond gris global ``QWidget`` via le QSS.
        wrap.setStyleSheet("background: transparent;")
        row = QHBoxLayout(wrap)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(_ACTIONS_ROW_SPACING)
        refresh_btn = QPushButton(self.tr("↻ Rafraîchir"), wrap)
        refresh_btn.setToolTip(
            self.tr(
                "Re-scanner le dossier d'entrée pour détecter les nouvelles sources"
            )
        )
        refresh_btn.clicked.connect(self.refresh_requested.emit)
        reinclude_all_btn = QPushButton(self.tr("Tout réinclure"), wrap)
        reinclude_all_btn.setToolTip(self.tr("Réintégrer toutes les sources exclues"))
        reinclude_all_btn.clicked.connect(self.reinclude_all)
        row.addWidget(refresh_btn)
        row.addWidget(reinclude_all_btn)
        row.addStretch(1)
        return wrap
