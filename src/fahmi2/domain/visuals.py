"""Entités immuables de la fonctionnalité Visualisations.

Carte de connaissances (graphe typé + communautés) et galerie de diagrammes (modèles
**typés**, jamais de DSL de rendu). Toutes les entités sont des ``@dataclass(frozen=True)``
pures (aucun import Qt/HTTP/SQL), validées dans ``__post_init__``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fahmi2.domain.enums import (
    DiagramType,
    EdgeType,
    Language,
    LLMModel,
    NodeType,
    SupportDensity,
)
from fahmi2.domain.phase import PhaseConfig

#: Types de diagramme dont la charge utile est un graphe (nodes + links).
GRAPH_DIAGRAM_TYPES: frozenset[DiagramType] = frozenset(
    {
        DiagramType.FLOWCHART,
        DiagramType.HIERARCHY,
        DiagramType.DECISION_TREE,
        DiagramType.CYCLE,
    }
)

#: Langues (scripts latins) supportées par la fonctionnalité Visualisations. Le chinois
#: et l'arabe sont **volontairement écartés** (décision produit : ne pas brider le rendu
#: interactif par les contraintes RTL/CJK).
VISUALS_LANGUAGES: frozenset[Language] = frozenset(
    {Language.FR, Language.EN, Language.DE, Language.ES, Language.IT}
)

#: Sous-dossier du workspace dédié aux artefacts de la fonctionnalité Visualisations.
VISUALS_WORKSPACE_SUBDIR = "visuals"

#: Sous-dossier des livrables HTML finaux (sous le dossier de la fonctionnalité).
VISUALS_OUTPUT_SUBDIR = "output"

#: Nombre de workers LLM par défaut (aligné sur la Pédagogie).
DEFAULT_VISUALS_LLM_WORKERS = 16

#: Borne supérieure du nombre de workers LLM concurrents (alignée sur la Pédagogie).
MAX_VISUALS_LLM_WORKERS = 64


def knowledge_map_filename(language: Language) -> str:
    """Nom de fichier de la carte de connaissances pour une langue.

    Args:
        language: Langue cible.

    Returns:
        Le nom de fichier (ex. ``"knowledge_map.fr.html"``).
    """
    return f"knowledge_map.{language}.html"


def diagrams_filename(language: Language) -> str:
    """Nom de fichier de la galerie de schémas pour une langue.

    Args:
        language: Langue cible.

    Returns:
        Le nom de fichier (ex. ``"diagrams.fr.html"``).
    """
    return f"diagrams.{language}.html"


@dataclass(frozen=True)
class SourceExcerpt:
    """Extrait source verbatim rattaché à un nœud/diagramme.

    Attributes:
        text: Passage de la sous-section, dans la langue rendue.
        section_path: Chemin structurel **invariant par langue** (ex. ``(2, 1, 1)``).
        chapter_title: Titre de la rubrique (langue rendue).
        anchor: Ancre GFM de la rubrique **dans la langue rendue**.
    """

    text: str
    section_path: tuple[int, ...]
    chapter_title: str
    anchor: str


@dataclass(frozen=True)
class GraphNode:
    """Nœud de la carte de connaissances.

    Attributes:
        id: Identifiant stable et unique (``f"{node_type}:{slug}"`` + désambiguïsation).
        label: Libellé affiché (langue rendue).
        node_type: Type du nœud.
        definition: Définition (termes/concepts) ou ``None``.
        excerpts: Extraits sources rattachés.
        chapter_anchor: Ancre du chapitre d'origine (langue rendue) ou ``None``.
        community_path: Chemin dans la hiérarchie de communautés (rempli par Louvain).
    """

    id: str
    label: str
    node_type: NodeType
    definition: str | None
    excerpts: tuple[SourceExcerpt, ...]
    chapter_anchor: str | None
    community_path: tuple[int, ...]


@dataclass(frozen=True)
class GraphEdge:
    """Relation typée entre deux nœuds.

    Attributes:
        source_id: Id du nœud source.
        target_id: Id du nœud cible.
        edge_type: Type de relation (enchaînement).
        label: Libellé optionnel (langue rendue).
    """

    source_id: str
    target_id: str
    edge_type: EdgeType
    label: str | None


@dataclass(frozen=True)
class Community:
    """Communauté thématique (cluster Louvain) avec son rapport.

    Attributes:
        id: Identifiant entier de la communauté.
        label: Étiquette lisible (langue rendue).
        report: Synthèse courte + idée-clé (double usage UI/raisonnement).
        level: Niveau dans la hiérarchie (0 = plus fin).
        member_ids: Ids des nœuds membres directs.
        parent_id: Id de la communauté parente ou ``None`` (racine).
    """

    id: int
    label: str
    report: str
    level: int
    member_ids: tuple[str, ...]
    parent_id: int | None


@dataclass(frozen=True)
class KnowledgeGraph:
    """Graphe de connaissances complet pour une langue.

    Attributes:
        nodes: Nœuds.
        edges: Relations (référencent des ids de ``nodes``).
        communities: Communautés thématiques.
        language: Langue des libellés/extraits.

    Raises:
        ValueError: Si une arête référence un id de nœud inconnu, ou si des ids de
            nœuds sont dupliqués.
    """

    nodes: tuple[GraphNode, ...]
    edges: tuple[GraphEdge, ...]
    communities: tuple[Community, ...]
    language: Language

    def __post_init__(self) -> None:
        ids = [n.id for n in self.nodes]
        if len(ids) != len(set(ids)):
            raise ValueError("KnowledgeGraph: ids de nœuds dupliqués")
        known = set(ids)
        for edge in self.edges:
            if edge.source_id not in known or edge.target_id not in known:
                raise ValueError(
                    f"KnowledgeGraph: arête vers un nœud inconnu "
                    f"({edge.source_id} -> {edge.target_id})"
                )


@dataclass(frozen=True)
class DiagramNode:
    """Nœud d'un diagramme « graphe ».

    Attributes:
        id: Identifiant local au diagramme.
        label: Libellé (langue rendue).
        role: Rôle optionnel (ex. décision/début/fin) ou ``None``.
    """

    id: str
    label: str
    role: str | None


@dataclass(frozen=True)
class DiagramLink:
    """Lien orienté d'un diagramme « graphe ».

    Attributes:
        from_id: Id du nœud source (dans le diagramme).
        to_id: Id du nœud cible (dans le diagramme).
        label: Libellé d'arête optionnel (ex. « oui »/« non ») ou ``None``.
    """

    from_id: str
    to_id: str
    label: str | None


@dataclass(frozen=True)
class TimelineEvent:
    """Évènement d'une chronologie.

    Attributes:
        date_label: Repère temporel affiché (ex. « 2001 »).
        title: Intitulé de l'évènement.
        detail: Détail optionnel ou ``None``.
    """

    date_label: str
    title: str
    detail: str | None


@dataclass(frozen=True)
class ComparisonTable:
    """Tableau de comparaison.

    Attributes:
        columns: En-têtes de colonnes.
        rows: Lignes (chaque ligne a ``len(columns)`` cellules).

    Raises:
        ValueError: Si une ligne n'a pas le bon nombre de cellules.
    """

    columns: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]

    def __post_init__(self) -> None:
        width = len(self.columns)
        for row in self.rows:
            if len(row) != width:
                raise ValueError(
                    f"ComparisonTable: ligne de largeur {len(row)} != {width}"
                )


@dataclass(frozen=True)
class Diagram:
    """Diagramme typé (charge utile selon ``diagram_type``).

    Types « graphe » (``FLOWCHART``/``HIERARCHY``/``DECISION_TREE``/``CYCLE``) →
    ``nodes`` non vide. ``TIMELINE`` → ``events`` non vide. ``COMPARISON`` →
    ``comparison`` non ``None``. Les champs non pertinents restent vides/``None``.

    Attributes:
        id: Identifiant stable du diagramme.
        title: Titre (langue rendue).
        diagram_type: Type du diagramme.
        nodes: Nœuds (types « graphe »).
        links: Liens (types « graphe »).
        events: Évènements (``TIMELINE``).
        comparison: Tableau (``COMPARISON``) ou ``None``.
        caption: Légende (langue rendue).
        chapter_anchor: Ancre du chapitre d'origine (langue rendue).
        excerpts: Extraits sources rattachés.

    Raises:
        ValueError: Si la charge utile ne correspond pas au ``diagram_type``.
    """

    id: str
    title: str
    diagram_type: DiagramType
    nodes: tuple[DiagramNode, ...]
    links: tuple[DiagramLink, ...]
    events: tuple[TimelineEvent, ...]
    comparison: ComparisonTable | None
    caption: str
    chapter_anchor: str
    excerpts: tuple[SourceExcerpt, ...]

    def __post_init__(self) -> None:
        if self.diagram_type in GRAPH_DIAGRAM_TYPES:
            if not self.nodes:
                raise ValueError(f"Diagram {self.diagram_type}: nodes requis")
        elif self.diagram_type is DiagramType.TIMELINE:
            if not self.events:
                raise ValueError("Diagram TIMELINE: events requis")
        elif self.diagram_type is DiagramType.COMPARISON:
            if self.comparison is None:
                raise ValueError("Diagram COMPARISON: comparison requis")


@dataclass(frozen=True)
class DiagramBoard:
    """Galerie de diagrammes pour une langue.

    Attributes:
        diagrams: Diagrammes.
        language: Langue des libellés.
    """

    diagrams: tuple[Diagram, ...]
    language: Language


@dataclass(frozen=True)
class VisualsSettings:
    """Paramètres de la fonctionnalité Visualisations.

    Attributes:
        produce_knowledge_map: Produire la carte de connaissances (Doc A).
        produce_diagrams: Produire la galerie de diagrammes (Doc B).
        density: Densité (volume) des nœuds/diagrammes ; réutilise ``SupportDensity``.
        diagram_types: Types de diagrammes autorisés (sous-ensemble de ``DiagramType``).
        llm_model: Modèle DeepSeek utilisé pour l'extraction/traduction.
        llm_config: Config des appels LLM (thinking / effort / température / retries).
        llm_workers: Workers LLM concurrents (>= 1).
        cost_ceiling_usd: Plafond de coût (``None`` = pas de plafond).

    Raises:
        ValueError: Si ``llm_workers < 1`` ou ``cost_ceiling_usd < 0``.
    """

    produce_knowledge_map: bool = True
    produce_diagrams: bool = True
    density: SupportDensity = SupportDensity.STANDARD
    diagram_types: frozenset[DiagramType] = frozenset(DiagramType)
    llm_model: LLMModel = LLMModel.DEEPSEEK_V4_FLASH
    llm_config: PhaseConfig = field(default_factory=PhaseConfig)
    llm_workers: int = DEFAULT_VISUALS_LLM_WORKERS
    cost_ceiling_usd: float | None = None

    def __post_init__(self) -> None:
        if self.llm_workers < 1:
            raise ValueError("llm_workers must be >= 1")
        if self.cost_ceiling_usd is not None and self.cost_ceiling_usd < 0:
            raise ValueError(
                f"cost_ceiling_usd must be >= 0 or None, got {self.cost_ceiling_usd}"
            )
