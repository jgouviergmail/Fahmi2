"""Chargement et *inlining* des bibliothèques JS vendorisées des Visualisations.

Les livrables HTML des Visualisations sont **pleinement autonomes** : les
bibliothèques JS (Cytoscape + extensions) sont **vendorisées** sous
``_assets/visuals/*.js`` et inlinées dans le HTML produit (aucun CDN). L'ordre
d'inline respecte les dépendances d'enregistrement (les bibliothèques de layout et
``cytoscape`` avant les extensions qui s'y enregistrent).
"""

from __future__ import annotations

import hashlib
from importlib.resources import files

_ASSETS_PACKAGE = "fahmi2.infra.export"
_ASSETS_SUBDIR = "_assets/visuals"

#: Feuille de tokens de design partagée par les deux livrables (source unique des
#: couleurs clair/sombre), concaténée en tête de chaque CSS par les renderers.
VISUALS_TOKENS_CSS = "visuals_tokens.css"

#: Module JS partagé de **persistance des positions** (localStorage), inliné par les
#: deux renderers avant leur JS applicatif.
LAYOUT_STORE_JS = "_layout_store.js"

#: Persistance des dispositions : version de schéma de la clé (invalidation propre si le
#: format change) et longueur du hash de structure embarqué dans la clé.
_STORAGE_KEY_VERSION = "v1"
_STORAGE_KEY_HASH_LEN = 8

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


def build_storage_key(prefix: str, lang: str, hash_source: str) -> str:
    """Construit une clé localStorage namespacée + hashée pour un livrable Visualisations.

    Centralise le format de clé (partagé par la carte et la galerie) pour éviter la
    duplication de la version/longueur de hash entre renderers.

    Args:
        prefix: Préfixe namespacé du livrable (ex. ``fahmi2:visuals:knowledge_map``).
        lang: Code langue (ex. ``fr``).
        hash_source: Texte identifiant le contenu (ids triés) ; son hash invalide les
            positions périmées après régénération.

    Returns:
        ``<prefix>:<lang>:<hash8>:<version>``.
    """
    digest = hashlib.sha256(hash_source.encode(_ENCODING_UTF8)).hexdigest()[
        :_STORAGE_KEY_HASH_LEN
    ]
    return f"{prefix}:{lang}:{digest}:{_STORAGE_KEY_VERSION}"


def read_visuals_asset(name: str) -> str:
    """Lit le contenu d'un asset des Visualisations (JS vendorisé, CSS, JS, template).

    Args:
        name: Nom de fichier (ex. ``"cytoscape.min.js"``, ``"knowledge_map.css"``).

    Returns:
        Le contenu textuel de l'asset.
    """
    resource = files(_ASSETS_PACKAGE).joinpath(_ASSETS_SUBDIR).joinpath(name)
    return resource.read_text(encoding=_ENCODING_UTF8)


def vendored_scripts_html(names: tuple[str, ...] = VENDORED_SCRIPTS) -> str:
    """Construit le bloc ``<script>`` inlinant les bibliothèques vendorisées.

    Args:
        names: Sous-ensemble (ordonné) des scripts à inliner. Par défaut
            ``VENDORED_SCRIPTS`` (toutes les bibliothèques) ; un livrable qui n'utilise
            qu'une partie (ex. la galerie de schémas : cytoscape + dagre) en passe un
            sous-ensemble pour un fichier plus léger.

    Returns:
        Une concaténation de balises ``<script>`` (une par bibliothèque, dans l'ordre
        fourni) prête à être insérée dans le HTML.
    """
    blocks = [
        f"<script>/* vendored: {name} */\n{read_visuals_asset(name)}\n</script>"
        for name in names
    ]
    return "\n".join(blocks)
