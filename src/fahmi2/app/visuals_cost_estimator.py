"""Estimation pré-génération du coût des Visualisations (heuristique).

Reflète les étapes réelles de l'orchestrateur (``VisualsOrchestrator``) : la
**structure** (graphe + diagrammes) est extraite **une seule fois** en langue de
structure, puis les **libellés** sont traduits pour chaque langue latine
supplémentaire. Trois postes de coût en découlent :

* **Carte des connaissances** : extraction sémantique (initiale + *gleaning*) par
  unité de texte, *reports* de communauté, puis enchaînements d'idées.
* **Diagrammes** : génération typée par unité de texte.
* **Traduction des libellés** : localisation du graphe et du board pour chaque langue
  latine au-delà de la langue de structure.

Objectif : un ordre de grandeur (fourchette ±33 %), pas une prédiction au cent près.
"""

from __future__ import annotations

from dataclasses import dataclass

from fahmi2.app._cost_common import (
    TOKENS_PER_WORD,
    cost_range,
    thinking_output_multiplier,
)
from fahmi2.domain.visuals import VisualsSettings
from fahmi2.infra.llm._pricing import ModelPricing, get_pricing
from fahmi2.visuals._constants import (
    GLEANING_ROUNDS,
    MAX_DIAGRAMS_PER_UNIT,
    MAX_SEMANTIC_NODES_PER_UNIT,
    MIN_COMMUNITIES_FOR_IDEA_CHAINS,
)
from fahmi2.visuals.sources import TextUnit

#: Tokens de sortie estimés par nœud sémantique extrait (objet JSON id/label/type/déf).
_OUTPUT_TOKENS_PER_NODE = 60
#: Tokens d'entrée fixes d'un appel d'extraction (instructions + épine glossaire).
_EXTRACTION_OVERHEAD_TOKENS = 400
#: Nœuds sémantiques estimés par communauté (pour déduire un nombre de communautés).
_NODES_PER_COMMUNITY = 8
#: Tokens d'entrée fixes d'un *report* de communauté (contexte nœuds + arêtes).
_COMMUNITY_REPORT_INPUT_TOKENS = 800
#: Tokens de sortie estimés d'un *report* de communauté.
_COMMUNITY_REPORT_OUTPUT_TOKENS = 400
#: Tokens de sortie estimés de la passe d'enchaînements d'idées (un appel map-reduce).
_IDEA_CHAINS_OUTPUT_TOKENS = 600
#: Tokens d'entrée fixes d'un appel de génération de diagrammes pour une unité.
_DIAGRAM_OVERHEAD_TOKENS = 400
#: Tokens de sortie estimés par diagramme typé généré.
_OUTPUT_TOKENS_PER_DIAGRAM = 250
#: Tokens (entrée ≈ sortie) de traduction par nœud (libellé + définition).
_TRANSLATE_TOKENS_PER_NODE = 40
#: Tokens (entrée ≈ sortie) de traduction par diagramme (titre + libellés).
_TRANSLATE_TOKENS_PER_DIAGRAM = 120


@dataclass(frozen=True)
class VisualsCostEstimation:
    """Estimation de coût des Visualisations.

    Attributes:
        knowledge_map_usd: Coût estimé de la carte des connaissances (extraction +
            reports + enchaînements), 0 si le livrable est désactivé.
        diagrams_usd: Coût estimé des diagrammes, 0 si le livrable est désactivé.
        translation_usd: Coût estimé de la traduction des libellés (langues
            supplémentaires).
        total_usd: Coût total estimé (ponctuel).
        units_total: Nombre d'unités de texte de la langue de structure.
        low_usd: Bas de fourchette d'incertitude (±33 %).
        high_usd: Haut de fourchette d'incertitude (±33 %).
    """

    knowledge_map_usd: float
    diagrams_usd: float
    translation_usd: float
    total_usd: float
    units_total: int
    low_usd: float
    high_usd: float


class VisualsCostEstimator:
    """Estime le coût LLM des visualisations sélectionnées (ordre de grandeur)."""

    def estimate(
        self,
        *,
        visuals: VisualsSettings,
        structure_units: tuple[TextUnit, ...],
        language_count: int,
    ) -> VisualsCostEstimation:
        """Estime le coût total.

        Args:
            visuals: Réglages Visualisations.
            structure_units: Unités de texte de la langue de structure (extraction).
            language_count: Nombre de langues latines disponibles (>= 1 si une
                structure est produite ; 0 toléré → coût nul).

        Returns:
            ``VisualsCostEstimation`` (coût par poste + total + fourchette).
        """
        pricing = get_pricing(str(visuals.llm_model))
        thinking_mult = thinking_output_multiplier(visuals.llm_config)
        max_nodes = MAX_SEMANTIC_NODES_PER_UNIT[visuals.density]
        max_diagrams = MAX_DIAGRAMS_PER_UNIT[visuals.density]
        unit_inputs = [
            int(len(unit.text.split()) * TOKENS_PER_WORD) for unit in structure_units
        ]
        total_semantic_nodes = len(structure_units) * max_nodes
        total_diagrams = len(structure_units) * max_diagrams
        extra_languages = max(0, language_count - 1)

        knowledge_map = (
            self._knowledge_map_cost(
                unit_inputs=unit_inputs,
                max_nodes=max_nodes,
                total_semantic_nodes=total_semantic_nodes,
                thinking_mult=thinking_mult,
                pricing=pricing,
            )
            if visuals.produce_knowledge_map
            else 0.0
        )
        diagrams = (
            self._diagrams_cost(
                unit_inputs=unit_inputs,
                max_diagrams=max_diagrams,
                thinking_mult=thinking_mult,
                pricing=pricing,
            )
            if visuals.produce_diagrams
            else 0.0
        )
        translation = self._translation_cost(
            visuals=visuals,
            total_semantic_nodes=total_semantic_nodes,
            total_diagrams=total_diagrams,
            extra_languages=extra_languages,
            thinking_mult=thinking_mult,
            pricing=pricing,
        )
        total = knowledge_map + diagrams + translation
        low, high = cost_range(total)
        return VisualsCostEstimation(
            knowledge_map_usd=knowledge_map,
            diagrams_usd=diagrams,
            translation_usd=translation,
            total_usd=total,
            units_total=len(structure_units),
            low_usd=low,
            high_usd=high,
        )

    @staticmethod
    def _knowledge_map_cost(
        *,
        unit_inputs: list[int],
        max_nodes: int,
        total_semantic_nodes: int,
        thinking_mult: float,
        pricing: ModelPricing,
    ) -> float:
        """Coût de la carte (extraction + reports + enchaînements).

        Args:
            unit_inputs: Tokens d'entrée estimés par unité de texte.
            max_nodes: Plafond de nœuds sémantiques par unité (densité).
            total_semantic_nodes: Nombre total estimé de nœuds sémantiques.
            thinking_mult: Multiplicateur thinking sur les tokens de sortie.
            pricing: Grille tarifaire du modèle.

        Returns:
            Coût USD de la carte des connaissances.
        """
        extraction_calls = 1 + GLEANING_ROUNDS
        node_output = int(max_nodes * _OUTPUT_TOKENS_PER_NODE * thinking_mult)
        extraction = extraction_calls * sum(
            pricing.cost_for(
                prompt_tokens=unit_input + _EXTRACTION_OVERHEAD_TOKENS,
                completion_tokens=node_output,
                cached_prompt_tokens=0,
            )
            for unit_input in unit_inputs
        )
        communities = total_semantic_nodes // _NODES_PER_COMMUNITY
        reports = communities * pricing.cost_for(
            prompt_tokens=_COMMUNITY_REPORT_INPUT_TOKENS,
            completion_tokens=int(_COMMUNITY_REPORT_OUTPUT_TOKENS * thinking_mult),
            cached_prompt_tokens=0,
        )
        chains = (
            pricing.cost_for(
                prompt_tokens=communities * _COMMUNITY_REPORT_OUTPUT_TOKENS,
                completion_tokens=int(_IDEA_CHAINS_OUTPUT_TOKENS * thinking_mult),
                cached_prompt_tokens=0,
            )
            if communities >= MIN_COMMUNITIES_FOR_IDEA_CHAINS
            else 0.0
        )
        return extraction + reports + chains

    @staticmethod
    def _diagrams_cost(
        *,
        unit_inputs: list[int],
        max_diagrams: int,
        thinking_mult: float,
        pricing: ModelPricing,
    ) -> float:
        """Coût de la génération de diagrammes (un appel par unité de texte).

        Args:
            unit_inputs: Tokens d'entrée estimés par unité de texte.
            max_diagrams: Plafond de diagrammes par unité (densité).
            thinking_mult: Multiplicateur thinking sur les tokens de sortie.
            pricing: Grille tarifaire du modèle.

        Returns:
            Coût USD des diagrammes.
        """
        diagram_output = int(max_diagrams * _OUTPUT_TOKENS_PER_DIAGRAM * thinking_mult)
        return sum(
            pricing.cost_for(
                prompt_tokens=unit_input + _DIAGRAM_OVERHEAD_TOKENS,
                completion_tokens=diagram_output,
                cached_prompt_tokens=0,
            )
            for unit_input in unit_inputs
        )

    @staticmethod
    def _translation_cost(
        *,
        visuals: VisualsSettings,
        total_semantic_nodes: int,
        total_diagrams: int,
        extra_languages: int,
        thinking_mult: float,
        pricing: ModelPricing,
    ) -> float:
        """Coût de la traduction des libellés pour les langues supplémentaires.

        Args:
            visuals: Réglages (livrables activés).
            total_semantic_nodes: Nombre total estimé de nœuds sémantiques.
            total_diagrams: Nombre total estimé de diagrammes.
            extra_languages: Nombre de langues au-delà de la langue de structure.
            thinking_mult: Multiplicateur thinking sur les tokens de sortie.
            pricing: Grille tarifaire du modèle.

        Returns:
            Coût USD de la traduction des libellés.
        """
        if extra_languages == 0:
            return 0.0
        graph_tokens = total_semantic_nodes * _TRANSLATE_TOKENS_PER_NODE
        board_tokens = total_diagrams * _TRANSLATE_TOKENS_PER_DIAGRAM
        per_language = 0.0
        if visuals.produce_knowledge_map:
            per_language += pricing.cost_for(
                prompt_tokens=graph_tokens,
                completion_tokens=int(graph_tokens * thinking_mult),
                cached_prompt_tokens=0,
            )
        if visuals.produce_diagrams:
            per_language += pricing.cost_for(
                prompt_tokens=board_tokens,
                completion_tokens=int(board_tokens * thinking_mult),
                cached_prompt_tokens=0,
            )
        return extra_languages * per_language
