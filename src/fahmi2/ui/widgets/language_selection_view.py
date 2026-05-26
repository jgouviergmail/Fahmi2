"""Widget de sélection des langues du document (langues produites + principale).

Fusionne deux notions auparavant présentées séparément :

- ``output_languages`` : les versions produites du document (``consolidated.{lang}.md``) ;
- ``source_language`` : **laquelle est l'originale**, rédigée directement depuis les
  entrées (les autres en sont des **traductions**) — c'est aussi l'indice de langue
  donné au STT pour les médias.

Présentation : une ligne de **cases** « Produites » (langues générées) et un **combo**
« Principale » qui ne propose que les langues produites. La principale est donc
toujours produite, et on peut librement la choisir (y compris une autre que la 1ʳᵉ).
Au moins une langue reste toujours produite. Expose ``primary_language`` et
``output_languages`` consommés par ``GenerationSettingsView``.
"""

from __future__ import annotations

from collections.abc import Sequence
from functools import partial

from PySide6.QtCore import QSignalBlocker
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from fahmi2.domain.enums import Language

_PRODUCED_LABEL = "Produites :"
_PRIMARY_LABEL = "Principale (originale) :"
_LANGUAGE_LABELS: dict[Language, str] = {
    Language.FR: "Français",
    Language.EN: "Anglais",
}


def _language_label(language: Language) -> str:
    """Libellé humain d'une langue (valeur brute en repli)."""
    return _LANGUAGE_LABELS.get(language, language.value)


class LanguageSelectionView(QWidget):
    """Sélecteur unifié : cases « produites » + combo « principale » (originale)."""

    def __init__(
        self, languages: Sequence[Language], parent: QWidget | None = None
    ) -> None:
        """Construit le widget et sélectionne la 1ʳᵉ langue comme principale.

        Args:
            languages: Langues proposées (au moins une).
            parent: Parent Qt optionnel.
        """
        super().__init__(parent)
        self._languages = tuple(languages)
        self._checks: dict[Language, QCheckBox] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        produced_row = QHBoxLayout()
        produced_row.addWidget(QLabel(_PRODUCED_LABEL, self))
        for lang in self._languages:
            check = QCheckBox(_language_label(lang), self)
            check.toggled.connect(partial(self._on_check_toggled, lang))
            self._checks[lang] = check
            produced_row.addWidget(check)
        produced_row.addStretch(1)
        layout.addLayout(produced_row)

        primary_row = QHBoxLayout()
        primary_row.addWidget(QLabel(_PRIMARY_LABEL, self))
        self._primary_combo = QComboBox(self)
        primary_row.addWidget(self._primary_combo)
        primary_row.addStretch(1)
        layout.addLayout(primary_row)

        first = self._languages[0]
        self.set_selection(primary=first, outputs=(first,))

    def set_selection(
        self, *, primary: Language, outputs: Sequence[Language]
    ) -> None:
        """Pré-remplit la sélection (langues produites + langue principale).

        Args:
            primary: Langue principale (originale).
            outputs: Langues produites (la principale y est forcée).
        """
        for lang, check in self._checks.items():
            with QSignalBlocker(check):
                check.setChecked(lang in outputs or lang is primary)
        self._rebuild_primary_combo(preferred=primary)

    def primary_language(self) -> Language:
        """Langue principale (originale) sélectionnée dans le combo.

        Returns:
            La langue choisie comme principale (1ʳᵉ langue en repli).
        """
        data = self._primary_combo.currentData()
        return Language(data) if data is not None else self._languages[0]

    def output_languages(self) -> tuple[Language, ...]:
        """Langues produites, la principale étant toujours présente.

        Returns:
            Les langues cochées, garanties de contenir la principale.
        """
        primary = self.primary_language()
        checked = tuple(
            lang for lang, check in self._checks.items() if check.isChecked()
        )
        return checked if primary in checked else (primary, *checked)

    def _on_check_toggled(self, lang: Language, checked: bool) -> None:
        """Maintient ≥ 1 langue produite et rafraîchit le combo principale.

        Args:
            lang: Langue dont la case vient d'être (dé)cochée.
            checked: Nouvel état de la case.
        """
        if not checked and not any(c.isChecked() for c in self._checks.values()):
            # Au moins une langue doit rester produite : on annule le décochage.
            with QSignalBlocker(self._checks[lang]):
                self._checks[lang].setChecked(True)
            return
        self._rebuild_primary_combo(preferred=self.primary_language())

    def _rebuild_primary_combo(self, *, preferred: Language) -> None:
        """Repeuple le combo « principale » avec les seules langues produites.

        Args:
            preferred: Langue à resélectionner si elle est encore produite ;
                sinon la 1ʳᵉ langue produite.
        """
        produced = [lang for lang in self._languages if self._checks[lang].isChecked()]
        with QSignalBlocker(self._primary_combo):
            self._primary_combo.clear()
            for lang in produced:
                self._primary_combo.addItem(_language_label(lang), lang.value)
            target = preferred if preferred in produced else (
                produced[0] if produced else None
            )
            if target is not None:
                index = self._primary_combo.findData(target.value)
                if index >= 0:
                    self._primary_combo.setCurrentIndex(index)
