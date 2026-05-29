"""Tests du chargement/inlining des bibliothèques JS vendorisées des Visualisations."""

from __future__ import annotations

from fahmi2.infra.export._visuals_assets import (
    VENDORED_SCRIPTS,
    read_visuals_asset,
    vendored_scripts_html,
)


def test_tous_les_assets_vendorises_sont_presents_et_non_vides() -> None:
    for name in VENDORED_SCRIPTS:
        content = read_visuals_asset(name)
        assert content.strip(), f"asset vide : {name}"


def test_scripts_html_inline_toutes_les_bibliotheques() -> None:
    html = vendored_scripts_html()
    for name in VENDORED_SCRIPTS:
        assert f"vendored: {name}" in html
    assert "cytoscape" in html
    # bundle conséquent (les libs réelles, pas des stubs).
    assert len(html) > 500_000


def test_ordre_d_enregistrement_respecte() -> None:
    html = vendored_scripts_html()
    layout = html.index("vendored: layout-base.js")
    core = html.index("vendored: cytoscape.min.js")
    fcose = html.index("vendored: cytoscape-fcose.js")
    # dépendances de layout + cœur avant les extensions.
    assert layout < core < fcose


def test_aucune_reference_externe_dans_le_bloc_scripts() -> None:
    # les libs sont inlinées : le bloc ne doit pas charger de ``src`` externe.
    html = vendored_scripts_html()
    assert 'src="http' not in html
