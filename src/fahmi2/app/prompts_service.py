"""Service applicatif ``PromptsService``.

Couche fine au-dessus du mécanisme d'override de :py:class:`PromptLoader`.
Permet à l'UI de :

- Lister les templates LLM disponibles (phases 1 à 7 + sous-prompt 5).
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
        name="phase_6_translation",
        display_name="Phase 6 — Traduction",
        description=(
            "Traduit chaque artefact Markdown dans une langue cible en "
            "préservant la structure."
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
