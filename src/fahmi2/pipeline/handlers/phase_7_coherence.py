"""Handler Phase 7 — passe de cohérence finale par langue de sortie.

Pour chaque langue de ``settings.output_languages`` :

- Lit ``output_dir/consolidated.{lang}.md``.
- Appelle le LLM avec le prompt ``phase_7_coherence``.
- Réécrit le fichier en place.

Le prompt n'autorise pas la réécriture des contenus de chapitres : il
n'affecte que les méta-éléments (titre global, intro, plan, conclusion,
transitions).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fahmi2.core.concurrency import map_bounded
from fahmi2.core.errors.exceptions import StorageError
from fahmi2.core.errors.severity import Severity
from fahmi2.domain.enums import Language, PhaseId
from fahmi2.domain.generation import consolidated_doc_filename
from fahmi2.domain.phase import PhaseExecution
from fahmi2.domain.video import VideoExecution
from fahmi2.pipeline.handlers._base import (
    build_succeeded_phase,
    invoke_llm,
    language_label,
    style_label,
    utc_now,
)
from fahmi2.pipeline.phase_handler import PhaseContext, PhaseHandler

_TEMPLATE_NAME = "phase_7_coherence"
_GLOSSARY_MASTER_FILENAME = "glossary_master.json"


class Phase7CoherenceHandler(PhaseHandler):
    """Phase 7 — passe finale de cohérence par langue."""

    @property
    def phase_id(self) -> PhaseId:
        """Identifiant de la phase."""
        return PhaseId.COHERENCE

    @property
    def is_per_video(self) -> bool:
        """Phase batch (boucle sur les langues)."""
        return False

    def execute(
        self,
        ctx: PhaseContext,
        *,
        video: VideoExecution | None,
    ) -> PhaseExecution:
        """Réécrit chaque ``consolidated.{lang}.md`` après passe de cohérence.

        Args:
            ctx: Contexte d'exécution.
            video: Doit être ``None``.

        Returns:
            ``PhaseExecution`` ``SUCCEEDED`` pointant vers ``output_dir``.

        Raises:
            ValueError: Si ``video`` est non-None.
            StorageError: Si un fichier consolidé est manquant.
            LLMError: En cas d'échec LLM.
        """
        if video is not None:
            raise ValueError("Phase7CoherenceHandler is batch (video must be None)")
        started_at = utc_now()
        glossary_terms = _load_glossary_terms(ctx.workspace)

        # Les langues sont indépendantes : passe de cohérence parallèle.
        costs = map_bounded(
            lambda target: self._run_for_language(ctx, target, glossary_terms),
            ctx.settings.output_languages,
            max_workers=ctx.settings.parallelism.llm_workers,
            pause_token=ctx.pause_token,
        )
        total_cost = sum(costs)

        return build_succeeded_phase(
            phase_id=self.phase_id,
            artifact_path=ctx.output_dir,
            started_at=started_at,
            cost_usd=total_cost,
        )

    def _run_for_language(
        self,
        ctx: PhaseContext,
        target: Language,
        glossary_terms: list[dict[str, Any]],
    ) -> float:
        """Effectue la passe de cohérence pour une langue donnée.

        Args:
            ctx: Contexte.
            target: Langue cible.
            glossary_terms: Liste des termes du glossaire (pour rappel au LLM).

        Returns:
            Coût en USD.

        Raises:
            StorageError: Si le fichier ``consolidated.{lang}.md`` est manquant.
        """
        path = ctx.output_dir / consolidated_doc_filename(target)
        if not path.exists():
            raise StorageError(
                code="STORAGE.CONSOLIDATED_LANG_MISSING",
                user_message=(
                    f"Le document consolidé en {target.value} est introuvable. "
                    "Relance la phase de traduction."
                ),
                severity=Severity.ERROR,
                technical_details={"path": str(path)},
            )
        current = path.read_text(encoding="utf-8")
        prompt = ctx.prompts.render(
            _TEMPLATE_NAME,
            output_language_label=language_label(target),
            style_label=style_label(ctx.settings.style_preset),
            style_directives=ctx.settings.style_directives,
            glossary_terms=glossary_terms,
            consolidated_markdown=current,
        )
        response = invoke_llm(
            ctx, phase_id=self.phase_id, system_prompt=None, user_prompt=prompt
        )
        ctx.artifacts.write_text_atomic(path, response.content)
        return response.cost_usd


def _load_glossary_terms(workspace: Path) -> list[dict[str, Any]]:
    """Charge la liste brute des termes du glossaire master.

    Args:
        workspace: Dossier de travail.

    Returns:
        Liste des termes (potentiellement vide).
    """
    master_path = workspace / _GLOSSARY_MASTER_FILENAME
    if not master_path.exists():
        return []
    payload = json.loads(master_path.read_text(encoding="utf-8"))
    return list(payload.get("terms", []))
