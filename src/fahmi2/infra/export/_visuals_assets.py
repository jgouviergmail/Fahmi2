"""Chargement et *inlining* des bibliothèques JS vendorisées des Visualisations.

Les livrables HTML des Visualisations sont **pleinement autonomes** : les
bibliothèques JS (Cytoscape + extensions) sont **vendorisées** sous
``_assets/visuals/*.js`` et inlinées dans le HTML produit (aucun CDN). L'ordre
d'inline respecte les dépendances d'enregistrement (les bibliothèques de layout et
``cytoscape`` avant les extensions qui s'y enregistrent).
"""

from __future__ import annotations

from importlib.resources import files

_ASSETS_PACKAGE = "fahmi2.infra.export"
_ASSETS_SUBDIR = "_assets/visuals"

#: Ordre d'inline (= ordre de chargement/enregistrement) des bibliothèques vendorisées.
#: ``layout-base`` → ``cose-base`` → ``dagre`` → ``cytoscape`` (cœur) → extensions
#: (``fcose`` / ``dagre`` / ``expand-collapse``) qui s'enregistrent sur le cœur.
VENDORED_SCRIPTS: tuple[str, ...] = (
    "layout-base.js",
    "cose-base.js",
    "dagre.min.js",
    "cytoscape.min.js",
    "cytoscape-fcose.js",
    "cytoscape-dagre.js",
    "cytoscape-expand-collapse.js",
)

_ENCODING_UTF8 = "utf-8"


def read_visuals_asset(name: str) -> str:
    """Lit le contenu d'un asset des Visualisations (JS vendorisé, CSS, JS, template).

    Args:
        name: Nom de fichier (ex. ``"cytoscape.min.js"``, ``"knowledge_map.css"``).

    Returns:
        Le contenu textuel de l'asset.
    """
    resource = files(_ASSETS_PACKAGE).joinpath(_ASSETS_SUBDIR).joinpath(name)
    return resource.read_text(encoding=_ENCODING_UTF8)


def vendored_scripts_html() -> str:
    """Construit le bloc ``<script>`` inlinant toutes les bibliothèques vendorisées.

    Returns:
        Une concaténation de balises ``<script>`` (une par bibliothèque, dans
        l'ordre d'enregistrement) prête à être insérée dans le ``<head>`` du HTML.
    """
    blocks = [
        f"<script>/* vendored: {name} */\n{read_visuals_asset(name)}\n</script>"
        for name in VENDORED_SCRIPTS
    ]
    return "\n".join(blocks)
