"""Constantes centralisées de la fonctionnalité Visualisations.

Aucune valeur « magique » ne doit apparaître ailleurs dans le paquet ``visuals`` :
seuils, plafonds par densité, tailles d'unité, noms de fichiers et sous-dossiers sont
définis ici (directive « constants centralization »).
"""

from __future__ import annotations

from fahmi2.domain.enums import SupportDensity

#: Sous-dossier du workspace dédié aux artefacts de la fonctionnalité Visualisations.
VISUALS_WORKSPACE_SUBDIR = "visuals"

#: Sous-dossier des livrables HTML finaux (sous le dossier de la fonctionnalité).
VISUALS_OUTPUT_SUBDIR = "output"

#: Nombre de passes de *gleaning* (rappel d'extraction) après l'extraction initiale
#: d'une unité de texte. 1 = un seul re-prompt « as-tu manqué des entités ? ».
GLEANING_ROUNDS = 1

#: Longueur minimale (caractères) du corps d'une section pour être retenue comme
#: unité de texte exploitable (écarte titres orphelins / sections quasi vides).
MIN_UNIT_BODY_CHARS = 40

#: Longueur maximale (caractères) d'une unité de texte ; au-delà, l'unité est
#: découpée en sous-unités contiguës (granularité ~ « text unit » GraphRAG).
MAX_UNIT_CHARS = 6000

#: Plafond de nœuds **sémantiques** (concepts / idées / exemples) extraits par unité
#: de texte, par niveau de densité (les nœuds de glossaire n'y sont pas soumis).
MAX_SEMANTIC_NODES_PER_UNIT: dict[SupportDensity, int] = {
    SupportDensity.LIGHT: 4,
    SupportDensity.STANDARD: 7,
    SupportDensity.DENSE: 12,
}

#: Seuil de similarité cosinus au-dessus duquel deux entités libres (non glossaire)
#: sont considérées comme une même entité et fusionnées (résolution par embeddings).
ENTITY_MERGE_COSINE_THRESHOLD = 0.82

#: Longueur maximale (caractères) d'un extrait source embarqué ; au-delà, l'extrait
#: est tronqué proprement (à la frontière d'un mot) et suffixé d'une ellipse.
EXCERPT_MAX_CHARS = 500

#: Graine fixe du clustering Louvain, pour des communautés **reproductibles** à
#: graphe d'entrée identique.
LOUVAIN_SEED = 17
