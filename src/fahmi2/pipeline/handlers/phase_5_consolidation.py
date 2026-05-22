"""Handler Phase 5 — consolidation du document final en langue source.

Cette phase est batch et opère en deux sous-étapes internes (transparentes pour
l'UI qui ne voit qu'un bloc dans la matrice) :

1. **Pré-consolidation** : pour chaque vidéo, on appelle le LLM avec le prompt
   ``phase_5_video_summary`` pour produire un résumé condensé (titre, plan,
   idées-clés) — **uniquement** une carte mentale pour le rédacteur en chef ;
   ce résumé n'est pas inséré dans le document final.
2. **Consolidation globale** : un unique appel LLM ``phase_5_consolidation``
   reçoit tous les résumés condensés et produit les *méta-éléments* (titre,
   résumé exécutif, introduction générale, plan d'ensemble, conclusion
   générale).

Le document final ``workspace/consolidated_master.md`` est assemblé à partir
de ces méta-éléments **plus** les contenus structurés de chaque vidéo
**recopiés tels quels** : aucune perte de fidélité, le LLM ne réécrit jamais
les contenus. Le module renumérote ensuite les titres (``#``, ``##``, ``###``)
de manière hiérarchique (1, 1.1, 1.1.1…) et construit un sommaire déterministe
avec ancres GitHub-compatibles.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fahmi2.core.concurrency import map_bounded
from fahmi2.core.errors.exceptions import StorageError
from fahmi2.core.errors.severity import Severity
from fahmi2.core.slugify import slugify_anchor
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

# Libellé de la section résumé exécutif (placée sous le titre, avant l'intro).
_SUMMARY_HEADING = "Résumé"

# Profondeur maximale incluse dans le sommaire et dans la numérotation.
# (les ####+ restent dans le corps mais ne sont ni numérotés ni listés.)
_TOC_MAX_DEPTH = 3

_RE_CODE_FENCE = re.compile(r"^\s*```")
_RE_H1 = re.compile(r"^#\s+(.+?)\s*$")
_RE_H2 = re.compile(r"^##\s+(.+?)\s*$")
_RE_H3 = re.compile(r"^###\s+(.+?)\s*$")
# Préfixe numérotation déjà présent (ex: "1. ", "1.2 ", "1.2.3 - ", "1) ").
# La numérotation est suivie d'au moins un séparateur (point, tiret,
# parenthèse fermante ou whitespace), répété autant que nécessaire.
_RE_EXISTING_NUMBERING = re.compile(r"^\d+(?:\.\d+)*[.\-)\s]+")


@dataclass(frozen=True)
class _Subheading:
    """Sous-titre détecté dans le corps d'un chapitre.

    Attributes:
        level: ``2`` pour ``##``, ``3`` pour ``###``.
        number: Numérotation hiérarchique (``"1.2"``, ``"1.2.3"``).
        title: Texte du titre, débarrassé de toute numérotation existante.
    """

    level: int
    number: str
    title: str


@dataclass(frozen=True)
class _Chapter:
    """Chapitre consolidé : titre numéroté + corps renuméroté + sous-titres.

    Attributes:
        index: Numéro du chapitre (1, 2, …).
        title: Titre du chapitre (sans le préfixe ``"N. "``).
        body: Corps Markdown du chapitre, déjà renuméroté.
        subheadings: Liste ordonnée des sous-titres ## et ### du chapitre.
    """

    index: int
    title: str
    body: str
    subheadings: tuple[_Subheading, ...]


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

        # Les résumés par vidéo sont indépendants : exécution parallèle bornée
        # (ordre des résultats préservé → assemblage déterministe).
        summary_results = map_bounded(
            lambda kv: self._summarize_one(ctx, kv),
            list(structured_by_video.items()),
            max_workers=ctx.settings.parallelism.llm_workers,
            pause_token=ctx.pause_token,
        )
        summaries = [summary for summary, _ in summary_results]
        total_cost = sum(cost for _, cost in summary_results)

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

    def _summarize_one(
        self, ctx: PhaseContext, item: tuple[str, str]
    ) -> tuple[dict[str, Any], float]:
        """Résume une vidéo (clé = ``video_id``), pour exécution parallèle.

        Args:
            ctx: Contexte.
            item: Couple ``(video_id, structured_markdown)``.

        Returns:
            ``(summary_avec_video_id, cost_usd)``.
        """
        video_id, structured_md = item
        summary, cost = self._summarize_video(ctx, structured_md)
        summary["video_id"] = video_id
        return summary, cost

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

    Le document final est structuré ainsi :

    1. ``# <titre global>``
    2. ``## Résumé`` (abstract synthétique du LLM, non numéroté ; omis si
       ``summary_markdown`` est vide ou absent)
    3. ``## Introduction générale`` (texte narratif du LLM, non numéroté)
    4. ``## Sommaire`` (liste hiérarchique avec ancres GitHub vers chaque
       titre numéroté : chapitres + sections ## et sous-sections ###)
    5. Chapitres : ``# 1. <titre>``, ``# 2. <titre>``…  À l'intérieur d'un
       chapitre, les ``##`` deviennent ``## N.M <titre>`` et les ``###``
       deviennent ``### N.M.P <titre>``. Les numérotations posées
       précédemment par le LLM (« 1. », « 1.1 »…) sont systématiquement
       décapées avant d'écrire la nouvelle.
    6. ``## Conclusion générale`` (non numéroté)

    Args:
        meta: Méta-éléments produits par la consolidation (title, summary,
            intro, plan, conclusion). ``plan_markdown`` est ignoré : le
            sommaire est déterministe.
        structured_by_video: Documents structurés par vidéo (ordre = ordre
            des chapitres).
        summaries: Résumés (utilisés pour les titres de chapitres).

    Returns:
        Le document Markdown consolidé complet.
    """
    title = str(meta.get("global_title", "Document consolidé"))
    summary = str(meta.get("summary_markdown", "")).strip()
    introduction = str(meta.get("introduction_markdown", "")).strip()
    conclusion = str(meta.get("conclusion_markdown", "")).strip()
    titles_by_video = {s.get("video_id", ""): s.get("title", "") for s in summaries}

    chapters = _build_chapters(structured_by_video, titles_by_video)

    parts: list[str] = [f"# {title}", ""]
    if summary:
        parts.extend([f"## {_SUMMARY_HEADING}", "", summary, ""])
    if introduction:
        parts.extend(["## Introduction générale", "", introduction, ""])

    if chapters:
        parts.append("## Sommaire")
        parts.append("")
        parts.extend(_build_toc_lines(chapters))
        parts.append("")

    for chapter in chapters:
        parts.append(f"# {chapter.index}. {chapter.title}")
        parts.append("")
        if chapter.body:
            parts.append(chapter.body)
            parts.append("")

    if conclusion:
        parts.extend(["## Conclusion générale", "", conclusion, ""])
    return "\n".join(parts).rstrip() + "\n"


def _build_chapters(
    structured_by_video: dict[str, str],
    titles_by_video: dict[str, Any],
) -> list[_Chapter]:
    """Construit la liste ordonnée des chapitres consolidés et renumérotés.

    Args:
        structured_by_video: Markdown structuré par vidéo (ordre préservé).
        titles_by_video: Titres extraits des résumés (clé = video_id).

    Returns:
        Liste de ``_Chapter`` prêts à être sérialisés.
    """
    chapters: list[_Chapter] = []
    for index, (video_id, structured) in enumerate(
        structured_by_video.items(), start=1
    ):
        raw_title = str(titles_by_video.get(video_id, "")).strip()
        title = _strip_existing_numbering(raw_title) or f"Chapitre {index}"
        demoted = _demote_chapter_h1(structured)
        renumbered_body, subheadings = _renumber_subheadings(demoted, index)
        chapters.append(
            _Chapter(
                index=index,
                title=title,
                body=renumbered_body,
                subheadings=tuple(subheadings),
            )
        )
    return chapters


def _build_toc_lines(chapters: list[_Chapter]) -> list[str]:
    """Construit la table des matières (chapitres + sous-titres numérotés).

    Args:
        chapters: Liste des chapitres déjà renumérotés.

    Returns:
        Liste de lignes Markdown (sans saut de ligne final).
    """
    lines: list[str] = []
    for chap in chapters:
        anchor = slugify_anchor(f"{chap.index}. {chap.title}")
        lines.append(f"{chap.index}. [{chap.title}](#{anchor})")
        for sub in chap.subheadings:
            if sub.level > _TOC_MAX_DEPTH:
                continue
            sub_anchor = slugify_anchor(f"{sub.number} {sub.title}")
            indent = "    " * (sub.level - 1)
            lines.append(
                f"{indent}- [{sub.number} {sub.title}](#{sub_anchor})"
            )
    return lines


def _renumber_subheadings(
    body: str, chapter_index: int
) -> tuple[str, list[_Subheading]]:
    """Renumérote les ``##`` et ``###`` d'un chapitre selon ``chapter_index``.

    Les numérotations préexistantes en tête de titre sont supprimées avant
    écriture de la nouvelle. Les blocs ``fence`` (``\\`\\`\\``) sont laissés
    intacts pour éviter de réécrire du code qui contiendrait ``##``.

    Args:
        body: Corps du chapitre (sans son H1, déjà ``_demote_chapter_h1``).
        chapter_index: Numéro du chapitre racine (1, 2, …).

    Returns:
        ``(body_renumeroté, sous-titres détectés)``.
    """
    h2_counter = 0
    h3_counter = 0
    in_code_block = False
    subheadings: list[_Subheading] = []
    out_lines: list[str] = []
    for line in body.splitlines():
        if _RE_CODE_FENCE.match(line):
            in_code_block = not in_code_block
            out_lines.append(line)
            continue
        if in_code_block:
            out_lines.append(line)
            continue
        m_h3 = _RE_H3.match(line)
        m_h2 = _RE_H2.match(line) if not m_h3 else None
        if m_h2 is not None:
            h2_counter += 1
            h3_counter = 0
            clean_title = _strip_existing_numbering(m_h2.group(1))
            number = f"{chapter_index}.{h2_counter}"
            out_lines.append(f"## {number} {clean_title}")
            subheadings.append(_Subheading(level=2, number=number, title=clean_title))
        elif m_h3 is not None:
            h3_counter += 1
            clean_title = _strip_existing_numbering(m_h3.group(1))
            # Si un ### apparaît avant tout ##, on l'accroche au chapitre racine.
            parent = h2_counter if h2_counter > 0 else 0
            if parent == 0:
                h2_counter = 1
                parent = 1
            number = f"{chapter_index}.{parent}.{h3_counter}"
            out_lines.append(f"### {number} {clean_title}")
            subheadings.append(_Subheading(level=3, number=number, title=clean_title))
        else:
            out_lines.append(line)
    return "\n".join(out_lines), subheadings


def _strip_existing_numbering(title: str) -> str:
    """Retire une éventuelle numérotation hiérarchique en tête de titre.

    Exemples : ``"1. Titre"`` → ``"Titre"`` ; ``"1.2 Titre"`` → ``"Titre"`` ;
    ``"1.2.3 - Titre"`` → ``"Titre"``.

    Args:
        title: Titre brut, possiblement déjà numéroté par le LLM.

    Returns:
        Titre débarrassé de sa numérotation.
    """
    return _RE_EXISTING_NUMBERING.sub("", title.strip()).strip()


def _demote_chapter_h1(structured_markdown: str) -> str:
    """Supprime le premier H1 du chapitre.

    Le chapitre a déjà reçu son propre H1 numéroté lors de l'assemblage ;
    on retire le premier titre H1 d'origine pour éviter la duplication
    visuelle. Les H2/H3 suivants sont conservés tels quels (la
    renumérotation a lieu après).

    Args:
        structured_markdown: Markdown du chapitre produit par la phase 4.

    Returns:
        Le Markdown avec le premier H1 supprimé.
    """
    lines = structured_markdown.splitlines()
    skipped_h1 = False
    out: list[str] = []
    for line in lines:
        if not skipped_h1 and _RE_H1.match(line):
            skipped_h1 = True
            continue
        out.append(line)
    return "\n".join(out).strip("\n")
