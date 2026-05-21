"""Smoke test de la carte de stat réutilisable."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fahmi2.ui.widgets.stat_card import StatCard


def test_stat_card_set_value_and_accent(qtbot: QtBot) -> None:
    card = StatCard(icon="$", title="Coût")
    qtbot.addWidget(card)
    card.set_value("$1.50", "plafond $2.00")
    card.set_accent("warning")
    assert card.value_text() == "$1.50"
