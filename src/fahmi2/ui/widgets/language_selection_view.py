"""Widget de sélection des langues du document (langues livrées + principale).

Fusionne deux notions auparavant présentées séparément :

- ``output_languages`` : les versions produites du document (``consolidated.{lang}.md``) ;
- ``source_language`` : **laquelle est l'originale**, rédigée directement depuis les
  entrées (les autres en sont des **traductions**) — c'est aussi l'indice de langue
  donné au STT pour les médias.

Une ligne par langue : un radio « principale » (exclusif) et une case « incluse ».
La langue principale est **toujours incluse** (sa case est cochée et verrouillée).
Expose ``primary_language`` et ``output_languages`` consommés par
``GenerationSettingsView``.
"""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QGridLayout,
    QLabel,
    QRadioButton,
    QWidget,
)

from fahmi2.domain.enums import Language

_PRIMARY_HEADER = "Principale"
_INCLUDE_HEADER = "Incluse"
_LANGUAGE_LABELS: dict[Language, str] = {
    Language.FR: "Français",
    Language.EN: "Anglais",
}


class LanguageSelectionView(QWidget):
    """Sélecteur unifié : langues livrées + langue principale (originale)."""

    def __init__(
        self, languages: Sequence[Language], parent: QWidget | None = None
    ) -> None:
        """Construit le widget et sélectionne la 1ʳᵉ langue comme principale.

        Args:
            languages: Langues proposées (au moins une).
            parent: Parent Qt optionnel.
        """
        super().__init__(parent)
        self._radios: dict[Language, QRadioButton] = {}
        self._checks: dict[Language, QCheckBox] = {}
        self._primary_group = QButtonGroup(self)
        self._primary_group.setExclusive(True)

        grid = QGridLayout(self)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.addWidget(QLabel(_PRIMARY_HEADER, self), 0, 1)
        grid.addWidget(QLabel(_INCLUDE_HEADER, self), 0, 2)
        for row, lang in enumerate(languages, start=1):
            grid.addWidget(QLabel(_LANGUAGE_LABELS.get(lang, lang.value), self), row, 0)
            radio = QRadioButton(self)
            self._primary_group.addButton(radio)
            self._radios[lang] = radio
            grid.addWidget(radio, row, 1)
            check = QCheckBox(self)
            self._checks[lang] = check
            grid.addWidget(check, row, 2)
            radio.toggled.connect(self._sync_primary_lock)
        grid.setColumnStretch(3, 1)

        first = next(iter(self._radios))
        self.set_selection(primary=first, outputs=(first,))

    def set_selection(
        self, *, primary: Language, outputs: Sequence[Language]
    ) -> None:
        """Pré-remplit la sélection (langues incluses + langue principale).

        Args:
            primary: Langue principale (originale).
            outputs: Langues incluses (la principale y est forcée).
        """
        for lang, check in self._checks.items():
            check.setChecked(lang in outputs)
        if primary in self._radios:
            self._radios[primary].setChecked(True)
        self._sync_primary_lock()

    def primary_language(self) -> Language:
        """Langue principale (originale) sélectionnée.

        Returns:
            La langue dont le radio « principale » est coché (1ʳᵉ langue en repli).
        """
        for lang, radio in self._radios.items():
            if radio.isChecked():
                return lang
        return next(iter(self._radios))

    def output_languages(self) -> tuple[Language, ...]:
        """Langues incluses, la principale étant toujours présente.

        Returns:
            Les langues cochées, garanties de contenir la principale.
        """
        primary = self.primary_language()
        return tuple(
            lang
            for lang, check in self._checks.items()
            if check.isChecked() or lang is primary
        )

    def _sync_primary_lock(self) -> None:
        """Verrouille la case de la principale (toujours incluse), libère les autres."""
        primary = self.primary_language()
        for lang, check in self._checks.items():
            if lang is primary:
                check.setChecked(True)
                check.setEnabled(False)
            else:
                check.setEnabled(True)
