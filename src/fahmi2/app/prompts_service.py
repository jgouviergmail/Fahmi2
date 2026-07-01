"""Service applicatif ``PromptsService``.

Couche fine au-dessus du mécanisme d'override de :py:class:`PromptLoader`.
Permet à l'UI de :

- Lister les templates LLM disponibles (12 prompts de génération — phases 1 à 7,
  sous-prompts 5a/5b, 3 prompts 5c/5d/5e du mode thématique, et localisation
  glossaire 6b — ; 8 supports pédagogiques ; 3 prompts du Dialogue ; 5 prompts des
  Visualisations).
- Lire le contenu **par défaut** (bundlé) d'un template.
- Lire le contenu **actuellement actif** (override utilisateur si présent,
  défaut sinon).
- Enregistrer / supprimer un override utilisateur dans
  ``%APPDATA%/Fahmi2/prompts/``.

La syntaxe Jinja2 est validée à l'enregistrement : un override syntaxiquement
invalide est refusé pour éviter de casser le pipeline ; l'utilisateur doit
corriger ou cliquer « Réinitialiser au défaut ».
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path

from jinja2 import Environment, TemplateSyntaxError, select_autoescape

from fahmi2.core.errors.exceptions import ConfigError
from fahmi2.core.errors.severity import Severity

_DEFAULTS_RESOURCE_PACKAGE = "fahmi2.infra.prompts.defaults"
_TEMPLATE_EXTENSION = ".j2"


@dataclass(frozen=True)
class PromptTemplateMeta:
    """Métadonnées d'affichage d'un template LLM.

    Attributes:
        name: Identifiant interne du template (sans extension).
        display_name: Libellé court adapté à l'UI.
        description: Description en une phrase.
    """

    name: str
    display_name: str
    description: str


# Ordre d'affichage dans l'UI : suit l'ordre logique du pipeline.
_TEMPLATE_METADATA: tuple[PromptTemplateMeta, ...] = (
    PromptTemplateMeta(
        name="phase_0_slide_analysis",
        display_name="Phase 0 — Analyse des slides (vision)",
        description=(
            "Analyse vision d'une image de slide : transcription fidèle du "
            "texte + description des éléments visuels. Utilisé quand "
            "l'option « analyser les slides » est activée sur une source "
            "vidéo/YouTube."
        ),
    ),
    PromptTemplateMeta(
        name="phase_1_term_extraction",
        display_name="Phase 1 — Extraction des termes",
        description=(
            "Extrait les termes techniques d'une transcription en candidats "
            "pour le glossaire (par vidéo)."
        ),
    ),
    PromptTemplateMeta(
        name="phase_2_glossary_reconciliation",
        display_name="Phase 2 — Réconciliation glossaire",
        description=(
            "Consolide les candidats de toutes les vidéos en un glossaire "
            "master cohérent (batch)."
        ),
    ),
    PromptTemplateMeta(
        name="phase_3_reformulation",
        display_name="Phase 3 — Reformulation",
        description=(
            "Reformule la transcription brute dans le style attendu, sans "
            "modifier le sens (par vidéo)."
        ),
    ),
    PromptTemplateMeta(
        name="phase_4_structuration",
        display_name="Phase 4 — Structuration",
        description=(
            "Structure le texte reformulé en chapitres / sections / "
            "admonitions Markdown (par vidéo)."
        ),
    ),
    PromptTemplateMeta(
        name="phase_5_video_summary",
        display_name="Phase 5a — Résumé condensé par vidéo",
        description=(
            "Sous-prompt de la phase 5 : produit un mini-résumé d'une vidéo "
            "(titre, plan, idées clés) pour la consolidation."
        ),
    ),
    PromptTemplateMeta(
        name="phase_5_consolidation",
        display_name="Phase 5b — Consolidation finale",
        description=(
            "Assemble les méta-éléments du document final (titre global, "
            "introduction, conclusion)."
        ),
    ),
    PromptTemplateMeta(
        name="phase_5_fact_ledger",
        display_name="Phase 5c — Relevé factuel (thématique)",
        description=(
            "Mode thématique : extrait par source le relevé exhaustif des "
            "éléments à préserver (faits, chiffres, données, raisonnements) "
            "avec extraits verbatim."
        ),
    ),
    PromptTemplateMeta(
        name="phase_5_thematic_plan",
        display_name="Phase 5d — Plan thématique",
        description=(
            "Mode thématique : conçoit le plan transversal (chapitres par "
            "thème) en rattachant chaque élément à au moins un chapitre."
        ),
    ),
    PromptTemplateMeta(
        name="phase_5_thematic_chapter",
        display_name="Phase 5e — Rédaction de chapitre thématique",
        description=(
            "Mode thématique : rédige un chapitre à partir des éléments "
            "assignés (fusion, déduplication, transitions, conflits par source)."
        ),
    ),
    PromptTemplateMeta(
        name="phase_6_translation",
        display_name="Phase 6 — Traduction",
        description=(
            "Traduit chaque artefact Markdown dans une langue cible en "
            "préservant la structure."
        ),
    ),
    PromptTemplateMeta(
        name="phase_6_glossary_localization",
        display_name="Phase 6 — Localisation du glossaire",
        description=(
            "Localise chaque terme du glossaire dans la langue cible (traduit "
            "l'équivalent métier consacré, garde les termes internationaux) et "
            "traduit les définitions. Sortie JSON."
        ),
    ),
    PromptTemplateMeta(
        name="phase_7_coherence",
        display_name="Phase 7 — Cohérence finale",
        description=(
            "Passe de cohérence finale (transitions, harmonisation "
            "stylistique) sur le document consolidé."
        ),
    ),
    PromptTemplateMeta(
        name="pedagogy_flashcards_concepts",
        display_name="Pédagogie — Flashcards concepts",
        description=(
            "Cartes recto/verso sur les idées clés d'un chapitre "
            "(supports de révision)."
        ),
    ),
    PromptTemplateMeta(
        name="pedagogy_qcm",
        display_name="Pédagogie — QCM",
        description=(
            "Questions à choix multiples avec distracteurs plausibles et "
            "justification, par chapitre."
        ),
    ),
    PromptTemplateMeta(
        name="pedagogy_true_false",
        display_name="Pédagogie — Vrai / Faux",
        description="Affirmations vrai/faux justifiées, par chapitre.",
    ),
    PromptTemplateMeta(
        name="pedagogy_cloze",
        display_name="Pédagogie — Textes à trous",
        description="Phrases lacunaires (cloze) avec réponses, par chapitre.",
    ),
    PromptTemplateMeta(
        name="pedagogy_open_questions",
        display_name="Pédagogie — Questions ouvertes",
        description=(
            "Questions ouvertes avec éléments de réponse attendus, par chapitre."
        ),
    ),
    PromptTemplateMeta(
        name="pedagogy_revision_sheet",
        display_name="Pédagogie — Fiche de révision",
        description="Synthèse Markdown structurée d'un chapitre.",
    ),
    PromptTemplateMeta(
        name="pedagogy_key_points",
        display_name="Pédagogie — Points clés",
        description="3 à 5 idées clés à retenir, par chapitre.",
    ),
    PromptTemplateMeta(
        name="pedagogy_mock_exam",
        display_name="Pédagogie — Examen blanc",
        description=(
            "Examen blanc composite (sujet + barème) couvrant tout le document."
        ),
    ),
    PromptTemplateMeta(
        name="chat_strict",
        display_name="Dialogue — Réponse ancrée (strict)",
        description=(
            "Chat : répond uniquement à partir du corpus, avec citations [§N]."
        ),
    ),
    PromptTemplateMeta(
        name="chat_augmented",
        display_name="Dialogue — Réponse augmentée",
        description=(
            "Chat : corpus prioritaire + complément balisé « Au-delà du cours »."
        ),
    ),
    PromptTemplateMeta(
        name="chat_query_expansion",
        display_name="Dialogue — Expansion de requête",
        description=(
            "Chat : reformule une question en mots-clés pour le retrieval lexical."
        ),
    ),
    PromptTemplateMeta(
        name="visuals_graph_extraction",
        display_name="Visualisations — Extraction du graphe",
        description=(
            "Extrait concepts, idées et exemples (+ relations) d'une unité de "
            "texte pour la carte des connaissances."
        ),
    ),
    PromptTemplateMeta(
        name="visuals_community_report",
        display_name="Visualisations — Rapport de communauté",
        description=(
            "Résume une communauté de nœuds en un titre + une synthèse "
            "(thématique de la carte)."
        ),
    ),
    PromptTemplateMeta(
        name="visuals_idea_chains",
        display_name="Visualisations — Enchaînements d'idées",
        description=(
            "Relie les communautés en enchaînements d'idées transversaux "
            "(map-reduce sur les rapports)."
        ),
    ),
    PromptTemplateMeta(
        name="visuals_diagram_authoring",
        display_name="Visualisations — Génération de diagrammes",
        description=(
            "Produit des diagrammes typés (organigramme, cycle, chronologie…) "
            "à partir d'une unité de texte."
        ),
    ),
    PromptTemplateMeta(
        name="visuals_label_translation",
        display_name="Visualisations — Traduction des libellés",
        description=(
            "Traduit les libellés du graphe et des diagrammes dans une langue "
            "cible (structure inchangée)."
        ),
    ),
)


class PromptsService:
    """Gère lecture, écriture et validation des overrides utilisateur."""

    def __init__(self, *, override_dir: Path) -> None:
        """Construit le service.

        Args:
            override_dir: Dossier de stockage des overrides (typiquement
                ``%APPDATA%/Fahmi2/prompts/``). Créé à la demande.
        """
        self._override_dir = override_dir
        self._env = Environment(
            autoescape=select_autoescape(default=False, default_for_string=False),
            keep_trailing_newline=True,
            trim_blocks=False,
            lstrip_blocks=False,
        )

    def list_templates(self) -> tuple[PromptTemplateMeta, ...]:
        """Liste les templates LLM disponibles, dans l'ordre du pipeline.

        Returns:
            Tuple immuable de ``PromptTemplateMeta``.
        """
        return _TEMPLATE_METADATA

    def load_default(self, name: str) -> str:
        """Lit le contenu **par défaut** (bundlé) d'un template.

        Args:
            name: Nom du template (sans extension).

        Returns:
            Le source Jinja2 d'origine.

        Raises:
            ConfigError: Si le template n'existe pas dans les défauts.
        """
        try:
            return (
                files(_DEFAULTS_RESOURCE_PACKAGE)
                .joinpath(f"{name}{_TEMPLATE_EXTENSION}")
                .read_text(encoding="utf-8")
            )
        except FileNotFoundError as exc:
            raise ConfigError(
                code="PROMPT.NOT_FOUND",
                user_message=f"Template introuvable : {name}",
                severity=Severity.ERROR,
                technical_details={"name": name},
            ) from exc

    def load_active(self, name: str) -> str:
        """Lit le contenu **actuellement actif** : override si présent, sinon défaut.

        Args:
            name: Nom du template.

        Returns:
            Le source Jinja2 actuellement utilisé par le pipeline.
        """
        override = self.load_override(name)
        if override is not None:
            return override
        return self.load_default(name)

    def load_override(self, name: str) -> str | None:
        """Lit l'override utilisateur d'un template, ou ``None`` s'il n'y en a pas.

        Args:
            name: Nom du template.

        Returns:
            Le source Jinja2 override, ou ``None`` si aucun override n'est
            défini.
        """
        path = self._override_path(name)
        if not path.exists():
            return None
        return path.read_text(encoding="utf-8")

    def has_override(self, name: str) -> bool:
        """Indique si un override existe pour ce template.

        Args:
            name: Nom du template.

        Returns:
            ``True`` si un fichier override est présent sur disque.
        """
        return self._override_path(name).exists()

    def save_override(self, name: str, content: str) -> None:
        """Enregistre un override utilisateur après validation Jinja2.

        Args:
            name: Nom du template.
            content: Nouveau contenu Jinja2.

        Raises:
            ConfigError: Si le contenu n'est pas un Jinja2 valide.
        """
        try:
            self._env.from_string(content)
        except TemplateSyntaxError as exc:
            raise ConfigError(
                code="PROMPT.INVALID_TEMPLATE",
                user_message=(
                    f"Template Jinja2 invalide pour « {name} » : {exc.message}"
                ),
                severity=Severity.ERROR,
                technical_details={"name": name, "error": str(exc)},
            ) from exc
        self._override_dir.mkdir(parents=True, exist_ok=True)
        self._override_path(name).write_text(content, encoding="utf-8")

    def reset_override(self, name: str) -> None:
        """Supprime l'override utilisateur (revient au défaut bundlé).

        Idempotent : si aucun override n'existe, ne fait rien.

        Args:
            name: Nom du template.
        """
        path = self._override_path(name)
        if path.exists():
            path.unlink()

    def _override_path(self, name: str) -> Path:
        """Chemin attendu d'un fichier override pour ``name``.

        Args:
            name: Nom du template.

        Returns:
            Le chemin absolu (le fichier peut ne pas exister).
        """
        return self._override_dir / f"{name}{_TEMPLATE_EXTENSION}"
