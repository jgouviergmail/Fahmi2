"""Handler Phase 6 — production des artefacts finaux par langue de sortie.

Pour chaque langue de ``settings.output_languages`` :

- Si la langue est la langue source : on **copie** les artefacts master sans
  appel LLM (documents structurés par source + consolidated_master + glossaire
  master rendu en Markdown).
- Sinon : on **traduit** chaque artefact via le LLM.

Les artefacts produits vivent dans ``output_dir`` :

- ``output_dir/per-video/{lang}/{source_id}.md``
- ``output_dir/consolidated.{lang}.md``
- ``output_dir/glossary.{lang}.md``
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fahmi2.core.concurrency import map_bounded
from fahmi2.core.errors.exceptions import StorageError
from fahmi2.core.errors.severity import Severity
from fahmi2.domain.enums import Language, PhaseId
from fahmi2.domain.generation import consolidated_doc_filename, glossary_doc_filename
from fahmi2.domain.phase import PhaseExecution
from fahmi2.domain.source import SourceExecution
from fahmi2.pipeline.handlers._base import (
    build_succeeded_phase,
    invoke_llm,
    language_label,
    style_label,
    utc_now,
)
from fahmi2.pipeline.phase_handler import PhaseContext, PhaseHandler

_STRUCTURED_SUBDIR = "structured"
_CONSOLIDATED_MASTER_FILENAME = "consolidated_master.md"
_GLOSSARY_MASTER_FILENAME = "glossary_master.json"
_PER_VIDEO_OUTPUT_SUBDIR = "per-video"
_TEMPLATE_NAME = "phase_6_translation"


@dataclass(frozen=True)
class _TranslationTask:
    """Une traduction LLM à effectuer : document source → fichier cible."""

    source_markdown: str
    target: Language
    target_path: Path


class Phase6TranslationHandler(PhaseHandler):
    """Phase 6 — production des artefacts finaux par langue de sortie."""

    @property
    def phase_id(self) -> PhaseId:
        """Identifiant de la phase."""
        return PhaseId.TRANSLATION

    @property
    def is_per_source(self) -> bool:
        """Phase batch (traite toutes les sources et toutes les langues)."""
        return False

    def execute(
        self,
        ctx: PhaseContext,
        *,
        source: SourceExecution | None,
    ) -> PhaseExecution:
        """Produit les artefacts finaux par langue.

        Args:
            ctx: Contexte d'exécution.
            source: Doit être ``None`` (phase batch).

        Returns:
            ``PhaseExecution`` ``SUCCEEDED`` pointant vers ``output_dir``.

        Raises:
            ValueError: Si ``source`` est non-None.
            StorageError: Si un artefact master est manquant.
            LLMError: En cas d'échec LLM.
        """
        if source is not None:
            raise ValueError("Phase6TranslationHandler is batch (source must be None)")
        started_at = utc_now()

        consolidated_master = _load_required(
            ctx.workspace / _CONSOLIDATED_MASTER_FILENAME,
            "STORAGE.CONSOLIDATED_MISSING",
            "Le document consolidé master est introuvable.",
        )
        glossary_master = json.loads(
            _load_required(
                ctx.workspace / _GLOSSARY_MASTER_FILENAME,
                "STORAGE.GLOSSARY_MISSING",
                "Le glossaire master est introuvable.",
            )
        )
        per_source_structured = _load_per_source_structured(
            ctx.workspace, ctx.run.sources
        )

        # Les copies (langue source) sont écrites directement ; les traductions
        # LLM (langues ≠ source) sont collectées puis exécutées en parallèle au
        # grain (langue × document).
        tasks: list[_TranslationTask] = []
        for target in ctx.settings.output_languages:
            self._collect_for_language(
                ctx,
                target=target,
                consolidated_master_md=consolidated_master,
                glossary_master_payload=glossary_master,
                per_source_structured=per_source_structured,
                tasks=tasks,
            )
        costs = map_bounded(
            lambda task: self._run_translation(ctx, task, glossary_master),
            tasks,
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

    def _collect_for_language(
        self,
        ctx: PhaseContext,
        *,
        target: Language,
        consolidated_master_md: str,
        glossary_master_payload: dict[str, Any],
        per_source_structured: dict[str, str],
        tasks: list[_TranslationTask],
    ) -> None:
        """Écrit les copies (langue source) et empile les traductions (sinon).

        Args:
            ctx: Contexte.
            target: Langue cible.
            consolidated_master_md: Document consolidé en langue source.
            glossary_master_payload: Glossaire JSON master.
            per_source_structured: Mapping ``source_id -> markdown structuré``.
            tasks: Liste de tâches de traduction à compléter (effet de bord).
        """
        is_source = target is ctx.settings.source_language

        for source_id, structured_md in per_source_structured.items():
            target_path = (
                ctx.output_dir
                / _PER_VIDEO_OUTPUT_SUBDIR
                / target.value
                / f"{source_id}.md"
            )
            if is_source:
                ctx.artifacts.write_text_atomic(target_path, structured_md)
            else:
                tasks.append(_TranslationTask(structured_md, target, target_path))

        consolidated_target = ctx.output_dir / consolidated_doc_filename(target)
        if is_source:
            ctx.artifacts.write_text_atomic(
                consolidated_target, consolidated_master_md
            )
        else:
            tasks.append(
                _TranslationTask(consolidated_master_md, target, consolidated_target)
            )

        glossary_target = ctx.output_dir / glossary_doc_filename(target)
        glossary_md = _render_glossary_md(glossary_master_payload, target)
        if is_source:
            ctx.artifacts.write_text_atomic(glossary_target, glossary_md)
        else:
            tasks.append(_TranslationTask(glossary_md, target, glossary_target))

    def _run_translation(
        self,
        ctx: PhaseContext,
        task: _TranslationTask,
        glossary_master_payload: dict[str, Any],
    ) -> float:
        """Traduit une tâche via le LLM et écrit le fichier cible.

        Args:
            ctx: Contexte.
            task: Tâche de traduction (source + langue + chemin cible).
            glossary_master_payload: Glossaire master JSON.

        Returns:
            Le coût LLM (USD).
        """
        translated, cost = self._translate(
            ctx, task.source_markdown, task.target, glossary_master_payload
        )
        ctx.artifacts.write_text_atomic(task.target_path, translated)
        return cost

    def _translate(
        self,
        ctx: PhaseContext,
        source_markdown: str,
        target: Language,
        glossary_master_payload: dict[str, Any],
    ) -> tuple[str, float]:
        """Traduit un document Markdown vers la langue cible via le LLM.

        Args:
            ctx: Contexte.
            source_markdown: Document source.
            target: Langue cible.
            glossary_master_payload: Glossaire master JSON.

        Returns:
            ``(markdown_traduit, cost_usd)``.
        """
        prompt = ctx.prompts.render(
            _TEMPLATE_NAME,
            source_language_label=language_label(ctx.settings.source_language),
            target_language_label=language_label(target),
            style_label=style_label(ctx.settings.style_preset),
            style_directives=ctx.settings.style_directives,
            glossary_terms=_glossary_terms_for_template(
                glossary_master_payload, target=target
            ),
            source_markdown=source_markdown,
        )
        response = invoke_llm(
            ctx, phase_id=self.phase_id, system_prompt=None, user_prompt=prompt
        )
        return response.content, response.cost_usd


def _load_required(path: Path, code: str, user_message: str) -> str:
    """Lit un fichier ou lève ``StorageError``.

    Args:
        path: Chemin.
        code: Code d'erreur.
        user_message: Message utilisateur.

    Returns:
        Contenu texte UTF-8.

    Raises:
        StorageError: Si le fichier n'existe pas.
    """
    if not path.exists():
        raise StorageError(
            code=code,
            user_message=user_message,
            severity=Severity.ERROR,
            technical_details={"path": str(path)},
        )
    return path.read_text(encoding="utf-8")


def _load_per_source_structured(
    workspace: Path, sources: tuple[SourceExecution, ...]
) -> dict[str, str]:
    """Charge tous les documents structurés indexés par ``source_id``.

    Args:
        workspace: Dossier de travail.
        sources: Sources du run.

    Returns:
        Mapping ordonné ``source_id -> markdown``.

    Raises:
        StorageError: Si un fichier structuré manque.
    """
    result: dict[str, str] = {}
    for source in sources:
        path = workspace / _STRUCTURED_SUBDIR / f"{source.source_id.value}.md"
        if not path.exists():
            raise StorageError(
                code="STORAGE.STRUCTURED_MISSING",
                user_message=(
                    f"Le document structuré pour {source.source_id.value} est introuvable."
                ),
                severity=Severity.ERROR,
                technical_details={"path": str(path)},
            )
        result[source.source_id.value] = path.read_text(encoding="utf-8")
    return result


def _glossary_terms_for_template(
    glossary_payload: dict[str, Any], *, target: Language
) -> list[dict[str, str]]:
    """Construit la liste des équivalents glossaire à injecter dans le prompt.

    Args:
        glossary_payload: Payload JSON du glossaire master.
        target: Langue cible.

    Returns:
        Liste de ``{"source": "...", "target": "..."}``.
    """
    terms = glossary_payload.get("terms", [])
    result: list[dict[str, str]] = []
    for t in terms:
        source = str(t.get("term", ""))
        cross_lang = t.get("cross_lang", {}) or {}
        target_str = str(cross_lang.get(str(target), source))
        result.append({"source": source, "target": target_str})
    return result


def _render_glossary_md(payload: dict[str, Any], language: Language) -> str:
    """Rend le glossaire master en tableau Markdown pour une langue donnée.

    L'``acronym_expansion`` est intentionnellement conservée dans sa langue
    d'origine — c'est l'invariant produit par la phase 1 et préservé par la
    phase 2. Ce rendu se contente de la recopier dans la colonne
    *Signification* / *Meaning*.

    Args:
        payload: JSON master.
        language: Langue cible (utilisée pour le titre H1 et les en-têtes).

    Returns:
        Le glossaire au format tableau Markdown ``| Terme | Acronyme |
        Signification | Définition |``.
    """
    from fahmi2.domain.glossary import (  # noqa: PLC0415
        Term,
        render_glossary_markdown_table,
    )

    raw_terms = payload.get("terms", [])
    terms = [
        Term(
            term=str(raw.get("term", "")),
            definition=str(raw.get("definition", "")),
            acronym=str(raw["acronym"]) if raw.get("acronym") else None,
            acronym_expansion=(
                str(raw["acronym_expansion"])
                if raw.get("acronym_expansion")
                else None
            ),
        )
        for raw in raw_terms
    ]
    return render_glossary_markdown_table(
        language=language,
        terms=terms,
    )
