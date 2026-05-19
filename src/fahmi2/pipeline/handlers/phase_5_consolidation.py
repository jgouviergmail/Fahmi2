"""Handler Phase 5 — consolidation du document final en langue source.

Cette phase est batch et opère en deux sous-étapes internes (transparentes pour
l'UI qui ne voit qu'un bloc dans la matrice) :

1. **Pré-consolidation** : pour chaque vidéo, on appelle le LLM avec le prompt
   ``phase_5_video_summary`` pour produire un résumé condensé (titre, plan,
   idées-clés) — **uniquement** une carte mentale pour le rédacteur en chef ;
   ce résumé n'est pas inséré dans le document final.
2. **Consolidation globale** : un unique appel LLM ``phase_5_consolidation``
   reçoit tous les résumés condensés et produit les *méta-éléments* (titre,
   introduction générale, plan d'ensemble, conclusion générale).

Le document final ``workspace/consolidated_master.md`` est assemblé à partir
de ces méta-éléments **plus** les contenus structurés de chaque vidéo
**recopiés tels quels** : aucune perte de fidélité, le LLM ne réécrit jamais
les contenus.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fahmi2.core.errors.exceptions import StorageError
from fahmi2.core.errors.severity import Severity
from fahmi2.domain.enums import PhaseId
from fahmi2.domain.phase import PhaseExecution
from fahmi2.domain.video import VideoExecution
from fahmi2.pipeline.handlers._base import (
    build_succeeded_phase,
    invoke_llm,
    language_label,
    parse_json_response,
    style_label,
    utc_now,
)
from fahmi2.pipeline.phase_handler import PhaseContext, PhaseHandler

_STRUCTURED_SUBDIR = "structured"
_CONSOLIDATED_MASTER_FILENAME = "consolidated_master.md"
_TEMPLATE_VIDEO_SUMMARY = "phase_5_video_summary"
_TEMPLATE_CONSOLIDATION = "phase_5_consolidation"


class Phase5ConsolidationHandler(PhaseHandler):
    """Phase 5 — consolidation finale en langue source."""

    @property
    def phase_id(self) -> PhaseId:
        """Identifiant de la phase."""
        return PhaseId.CONSOLIDATION

    @property
    def is_per_video(self) -> bool:
        """Phase batch."""
        return False

    def execute(
        self,
        ctx: PhaseContext,
        *,
        video: VideoExecution | None,
    ) -> PhaseExecution:
        """Consolide le document final.

        Args:
            ctx: Contexte d'exécution.
            video: Doit être ``None`` (phase batch).

        Returns:
            ``PhaseExecution`` ``SUCCEEDED`` pointant vers
            ``workspace/consolidated_master.md``.

        Raises:
            ValueError: Si ``video`` est non-None.
            StorageError: Si un fichier structured manque.
            LLMError: Si une réponse LLM est invalide.
        """
        if video is not None:
            raise ValueError(
                "Phase5ConsolidationHandler is batch (video must be None)"
            )
        started_at = utc_now()
        structured_by_video = _load_all_structured(ctx.workspace, ctx.run.videos)

        total_cost = 0.0
        summaries: list[dict[str, Any]] = []
        for video_id, structured_md in structured_by_video.items():
            summary, summary_cost = self._summarize_video(ctx, structured_md)
            summary["video_id"] = video_id
            summaries.append(summary)
            total_cost += summary_cost

        meta, meta_cost = self._produce_meta(ctx, summaries)
        total_cost += meta_cost

        consolidated_md = _assemble_consolidated(meta, structured_by_video, summaries)
        out_path = ctx.workspace / _CONSOLIDATED_MASTER_FILENAME
        ctx.artifacts.write_text_atomic(out_path, consolidated_md)
        return build_succeeded_phase(
            phase_id=self.phase_id,
            artifact_path=out_path,
            started_at=started_at,
            cost_usd=total_cost,
        )

    def _summarize_video(
        self, ctx: PhaseContext, structured_md: str
    ) -> tuple[dict[str, Any], float]:
        """Sous-étape : produit le résumé condensé d'une vidéo via le LLM.

        Args:
            ctx: Contexte.
            structured_md: Document Markdown structuré de la vidéo.

        Returns:
            ``(payload_dict, cost_usd)``.
        """
        prompt = ctx.prompts.render(
            _TEMPLATE_VIDEO_SUMMARY,
            output_language_label=language_label(ctx.settings.source_language),
            structured_markdown=structured_md,
        )
        response = invoke_llm(
            ctx, phase_id=self.phase_id, system_prompt=None, user_prompt=prompt
        )
        payload = parse_json_response(response.content, phase_id=self.phase_id)
        return dict(payload), response.cost_usd

    def _produce_meta(
        self, ctx: PhaseContext, summaries: list[dict[str, Any]]
    ) -> tuple[dict[str, Any], float]:
        """Sous-étape : produit les méta-éléments du document consolidé.

        Args:
            ctx: Contexte.
            summaries: Résumés par vidéo.

        Returns:
            ``(meta_dict, cost_usd)``.
        """
        prompt = ctx.prompts.render(
            _TEMPLATE_CONSOLIDATION,
            output_language_label=language_label(ctx.settings.source_language),
            style_label=style_label(ctx.settings.style_preset),
            style_directives=ctx.settings.style_directives,
            summaries_json=json.dumps(summaries, ensure_ascii=False, indent=2),
        )
        response = invoke_llm(
            ctx, phase_id=self.phase_id, system_prompt=None, user_prompt=prompt
        )
        payload = parse_json_response(response.content, phase_id=self.phase_id)
        return dict(payload), response.cost_usd


def _load_all_structured(
    workspace: Path, videos: tuple[VideoExecution, ...]
) -> dict[str, str]:
    """Charge tous les documents Markdown structurés (phase 4) en ordre.

    Args:
        workspace: Dossier de travail.
        videos: Vidéos du run (ordre de l'input folder).

    Returns:
        Mapping ``video_id -> structured_markdown`` préservant l'ordre.

    Raises:
        StorageError: Si un fichier structuré manque.
    """
    result: dict[str, str] = {}
    for v in videos:
        path = workspace / _STRUCTURED_SUBDIR / f"{v.video_id.value}.md"
        if not path.exists():
            raise StorageError(
                code="STORAGE.STRUCTURED_MISSING",
                user_message=(
                    f"Le document structuré pour {v.video_id.value} est introuvable. "
                    "Relance la phase de structuration."
                ),
                severity=Severity.ERROR,
                technical_details={"path": str(path)},
            )
        result[v.video_id.value] = path.read_text(encoding="utf-8")
    return result


def _assemble_consolidated(
    meta: dict[str, Any],
    structured_by_video: dict[str, str],
    summaries: list[dict[str, Any]],
) -> str:
    """Assemble le document consolidé final en Markdown.

    Args:
        meta: Méta-éléments produits par la consolidation (title, intro, plan,
            conclusion).
        structured_by_video: Documents structurés par vidéo.
        summaries: Résumés (utilisés pour les titres de chapitres).

    Returns:
        Le document Markdown consolidé complet.
    """
    title = str(meta.get("global_title", "Document consolidé"))
    introduction = str(meta.get("introduction_markdown", "")).strip()
    plan = str(meta.get("plan_markdown", "")).strip()
    conclusion = str(meta.get("conclusion_markdown", "")).strip()

    titles_by_video = {s.get("video_id", ""): s.get("title", "") for s in summaries}

    parts: list[str] = [f"# {title}", ""]
    if introduction:
        parts.extend(["## Introduction générale", "", introduction, ""])
    if plan:
        parts.extend(["## Plan d'ensemble", "", plan, ""])
    for video_id, structured in structured_by_video.items():
        chapter_title = str(titles_by_video.get(video_id, "")).strip()
        if chapter_title:
            parts.append(f"# {chapter_title}")
            parts.append("")
        parts.append(structured.rstrip())
        parts.append("")
    if conclusion:
        parts.extend(["## Conclusion générale", "", conclusion, ""])
    return "\n".join(parts).rstrip() + "\n"
