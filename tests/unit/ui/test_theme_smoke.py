"""Smoke tests du thème global (chargement QSS)."""

from __future__ import annotations

from fahmi2.ui.theme import load_theme_qss


def test_load_theme_qss_returns_non_empty_string() -> None:
    qss = load_theme_qss()
    assert isinstance(qss, str)
    assert len(qss) > 100
    # Quelques object names attendus pour garantir la coordination Python/QSS
    assert "#statCard" in qss
    assert "#projectHeaderBar" in qss
    assert "#runMatrix" in qss
    assert "#logsDockArea" in qss


def test_theme_defines_status_accents() -> None:
    qss = load_theme_qss()
    # Variantes d'accent utilisées par StatsStripWidget._StatCard
    for accent in ("running", "success", "warning", "danger"):
        assert f'accent="{accent}"' in qss
