"""Handler Phase 2 — réconciliation du glossaire à partir des candidats par vidéo.

Charge tous les artefacts ``candidates/{vid}.json`` produits par la phase 1,
les agrège dans un format ``{source_id: payload}``, appelle le LLM avec le
prompt de réconciliation, et persiste le glossaire master dans
``workspace/glossary_master.json``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fahmi2.core.errors.exceptions import StorageError
from fahmi2.core.errors.severity import Severity
from fahmi2.domain.enums import PhaseId
from fahmi2.domain.phase import PhaseExecution
from fahmi2.domain.source import SourceExecution
from fahmi2.pipeline.handlers._base import (
    build_succeeded_phase,
    invoke_llm,
    language_label,
    parse_json_response,
    style_label,
    utc_now,
)
from fahmi2.pipeline.phase_handler import PhaseContext, PhaseHandler

_CANDIDATES_SUBDIR = "candidates"
_GLOSSARY_MASTER_FILENAME = "glossary_master.json"
_TEMPLATE_NAME = "phase_2_glossary_reconciliation"


class Phase2GlossaryReconciliationHandler(PhaseHandler):
    """Phase 2 — réconciliation du glossaire (batch)."""

    @property
    def phase_id(self) -> PhaseId:
        """Identifiant de la phase."""
        return PhaseId.GLOSSARY_RECONCILIATION

    @property
    def is_per_source(self) -> bool:
        """Phase batch (un seul appel pour tout le run)."""
        return False

    def execute(
        self,
        ctx: PhaseContext,
        *,
        source: SourceExecution | None,
    ) -> PhaseExecution:
        """Réconcilie le glossaire à partir de tous les candidats.

        Args:
            ctx: Contexte d'exécution.
            source: Doit être ``None`` (phase batch).

        Returns:
            ``PhaseExecution`` ``SUCCEEDED`` pointant vers
            ``workspace/glossary_master.json``.

        Raises:
            ValueError: Si ``source`` est non-None.
            StorageError: Si aucun fichier candidates n'a été trouvé.
            LLMError: Si la réponse LLM n'est pas du JSON valide.
        """
        if source is not None:
            raise ValueError(
                "Phase2GlossaryReconciliationHandler is batch (source must be None)"
            )
        started_at = utc_now()
        candidates = _load_all_candidates(ctx.workspace, ctx.run.sources)
        prompt = ctx.prompts.render(
            _TEMPLATE_NAME,
            source_language_label=language_label(ctx.settings.source_language),
            style_label=style_label(ctx.settings.style_preset),
            style_directives=ctx.settings.style_directives,
            candidates_json=json.dumps(candidates, ensure_ascii=False, indent=2),
        )
        response = invoke_llm(
            ctx, phase_id=self.phase_id, system_prompt=None, user_prompt=prompt
        )
        payload = parse_json_response(response.content, phase_id=self.phase_id)
        out_path = ctx.workspace / _GLOSSARY_MASTER_FILENAME
        ctx.artifacts.write_json_atomic(out_path, payload)
        return build_succeeded_phase(
            phase_id=self.phase_id,
            artifact_path=out_path,
            started_at=started_at,
            cost_usd=response.cost_usd,
        )


def _load_all_candidates(
    workspace: Path, videos: tuple[SourceExecution, ...]
) -> dict[str, Any]:
    """Charge tous les fichiers candidates et les agrège par ``source_id``.

    Args:
        workspace: Dossier de travail.
        videos: Vidéos du run à itérer.

    Returns:
        Dictionnaire ``{source_id: payload_candidates}``.

    Raises:
        StorageError: Si aucun candidat n'a été trouvé pour aucune vidéo.
    """
    aggregated: dict[str, Any] = {}
    for v in videos:
        path = workspace / _CANDIDATES_SUBDIR / f"{v.source_id.value}.json"
        if path.exists():
            aggregated[v.source_id.value] = json.loads(path.read_text(encoding="utf-8"))
    if not aggregated:
        raise StorageError(
            code="STORAGE.NO_CANDIDATES",
            user_message=(
                "Aucun fichier de candidats glossaire trouvé. "
                "La phase 1 doit avoir produit au moins un artefact."
            ),
            severity=Severity.ERROR,
            technical_details={"workspace": str(workspace)},
        )
    return aggregated
