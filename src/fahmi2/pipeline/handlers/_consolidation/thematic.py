"""Stratégie de consolidation ``THEMATIC`` (refonte thématique transversale).

Map-reduce à *provenance*, modèle du journaliste : extraire des notes fidèles,
les agencer par thème, puis rédiger à partir des notes. La fidélité du fond
circule via des identifiants traçables.

Étapes internes :

- **T1** — relevé factuel par source (parallélisé) : pour chaque source, le LLM
  extrait les *éléments à préserver* (faits, chiffres, données, raisonnements,
  affirmations) avec un id stable ``<source_id>#<n>`` et un *extrait verbatim*
  (vérité de terrain). Artefacts conservés : ``facts_master.json`` + ``facts.md``.
- **T2** — plan thématique (un appel) : rattache chaque élément à au moins un
  chapitre. **Contrôle déterministe #1** : tout id orphelin est réinjecté dans un
  chapitre de fin « Éléments complémentaires ». Artefact : ``thematic_plan.json``.
- **T3** — rédaction par chapitre (parallélisée) : chaque chapitre reçoit ses
  éléments assignés (énoncé + données + extrait verbatim) et rédige la synthèse
  (fusion, déduplication, transitions, conflits présentés par source).
  **Contrôle déterministe #2** : ids assignés non rendus → ``coverage.json``.
- **T4** — méta-éléments (titre/intro/conclusion) + assemblage déterministe.

Reprise intra-phase : un *hash de cohérence* (réglages + empreinte des sources)
permet de **réutiliser** les artefacts frais (sans toucher au ``PipelineEngine``).
"""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from fahmi2.core.concurrency import map_bounded
from fahmi2.domain.enums import PhaseId
from fahmi2.infra.llm.interface import JSON_OBJECT_RESPONSE_FORMAT
from fahmi2.pipeline.handlers._base import (
    invoke_llm,
    language_label,
    parse_json_response,
    style_label,
)
from fahmi2.pipeline.handlers._consolidation._base import (
    ConsolidationResult,
    ConsolidationStrategy,
    _Chapter,
    assemble_document,
    renumber_subheadings,
    strip_existing_numbering,
    subheadings_of,
)
from fahmi2.pipeline.phase_handler import PhaseContext

#: Sous-dossier du workspace dédié aux artefacts de la consolidation thématique.
CONSOLIDATION_SUBDIR = "consolidation"
FACTS_MASTER_FILENAME = "facts_master.json"
FACTS_READABLE_FILENAME = "facts.md"
THEMATIC_PLAN_FILENAME = "thematic_plan.json"
COVERAGE_FILENAME = "coverage.json"
MANIFEST_FILENAME = "_manifest.json"
CHAPTERS_SUBDIR = "chapters"
#: Chapitre déterministe accueillant les éléments orphelins (filet anti-perte).
COMPLEMENTARY_CHAPTER_TITLE = "Éléments complémentaires"

TEMPLATE_FACT_LEDGER = "phase_5_fact_ledger"
TEMPLATE_THEMATIC_PLAN = "phase_5_thematic_plan"
TEMPLATE_THEMATIC_CHAPTER = "phase_5_thematic_chapter"
#: Méta-éléments : réutilise le prompt de consolidation ORDERED.
TEMPLATE_CONSOLIDATION = "phase_5_consolidation"


@dataclass(frozen=True)
class _FactElement:
    """Élément de contenu tracé (relevé factuel T1).

    Attributes:
        id: Identifiant global stable ``<source_id>#<n>``.
        source_id: Source d'origine.
        type: ``fait`` | ``chiffre`` | ``donnee`` | ``raisonnement`` | ``affirmation``.
        enonce: Énoncé fidèle (reformulable).
        donnees: Chiffres/données brutes associés (``""`` si aucun).
        extrait_verbatim: Extrait littéral de la source (vérité de terrain).
    """

    id: str
    source_id: str
    type: str
    enonce: str
    donnees: str
    extrait_verbatim: str


@dataclass(frozen=True)
class _PlannedChapter:
    """Chapitre planifié (T2).

    Attributes:
        title: Titre du chapitre.
        order: Ordre de lecture (1-based).
        element_ids: Ids des éléments rattachés (peut chevaucher d'autres chapitres).
    """

    title: str
    order: int
    element_ids: tuple[str, ...]


def _elements_from_payload(
    payload: dict[str, Any], *, source_id: str
) -> list[_FactElement]:
    """Construit les éléments tracés d'une source (id global = ``source_id#n``).

    Args:
        payload: Réponse JSON de T1 (clé ``elements``).
        source_id: Source d'origine.

    Returns:
        Les éléments, dans l'ordre du relevé. L'identifiant ``n`` est attribué par
        **énumération** (1-based), pas lu du LLM : ids uniques garantis et aucune
        dépendance à un champ que le modèle pourrait omettre.
    """
    out: list[_FactElement] = []
    for n, raw in enumerate(payload.get("elements", []), start=1):
        out.append(
            _FactElement(
                id=f"{source_id}#{n}",
                source_id=source_id,
                type=str(raw.get("type", "")),
                enonce=str(raw.get("enonce", "")),
                donnees=str(raw.get("donnees", "")),
                extrait_verbatim=str(raw.get("extrait_verbatim", "")),
            )
        )
    return out


def _extract_ledger_one(
    ctx: PhaseContext, item: tuple[str, str]
) -> tuple[list[_FactElement], float]:
    """T1 pour une source : ``(source_id, structured_md)`` → ``(éléments, coût)``.

    Args:
        ctx: Contexte d'exécution.
        item: Couple ``(source_id, structured_markdown)``.

    Returns:
        ``(éléments, cost_usd)``.
    """
    source_id, structured_md = item
    prompt = ctx.prompts.render(
        TEMPLATE_FACT_LEDGER,
        output_language_label=language_label(ctx.settings.source_language),
        structured_markdown=structured_md,
    )
    response = invoke_llm(
        ctx,
        phase_id=PhaseId.CONSOLIDATION,
        system_prompt=None,
        user_prompt=prompt,
        response_format=JSON_OBJECT_RESPONSE_FORMAT,
    )
    payload = parse_json_response(
        response.content,
        phase_id=PhaseId.CONSOLIDATION,
        finish_reason=response.finish_reason,
    )
    return _elements_from_payload(dict(payload), source_id=source_id), response.cost_usd


def _source_labels(structured_by_source: dict[str, str]) -> dict[str, str]:
    """Libellés lisibles par source (« Source 1 », « Source 2 »…), dans l'ordre.

    Les identifiants internes (ULID) ne doivent **jamais** apparaître dans le
    document final : le LLM ne reçoit que ces libellés pour attribuer un contenu
    à sa source.

    Args:
        structured_by_source: Markdown structuré par ``source_id`` (ordre du run).

    Returns:
        Mapping ``source_id -> libellé lisible``.
    """
    return {
        source_id: f"Source {index}"
        for index, source_id in enumerate(structured_by_source, start=1)
    }


def _render_facts_md(
    elements: list[_FactElement], source_labels: dict[str, str]
) -> str:
    """Rendu lisible du relevé factuel, groupé par source.

    Args:
        elements: Tous les éléments tracés.
        source_labels: Libellés lisibles par ``source_id`` (pas d'ULID affiché).

    Returns:
        Markdown consultable (un bloc par source).
    """
    lines: list[str] = ["# Relevé factuel", ""]
    by_source: dict[str, list[_FactElement]] = {}
    for el in elements:
        by_source.setdefault(el.source_id, []).append(el)
    for source_id, els in by_source.items():
        lines.append(f"## {source_labels.get(source_id, source_id)}")
        lines.append("")
        for el in els:
            data = f" — _{el.donnees}_" if el.donnees else ""
            lines.append(f"- ({el.type}) {el.enonce}{data}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _build_elements_listing(elements: list[_FactElement]) -> str:
    """Listing compact (``id — énoncé``), groupé par source, pour le plan.

    Args:
        elements: Tous les éléments tracés.

    Returns:
        Texte compact destiné au prompt T2.
    """
    by_source: dict[str, list[_FactElement]] = {}
    for el in elements:
        by_source.setdefault(el.source_id, []).append(el)
    lines: list[str] = []
    for source_id, els in by_source.items():
        lines.append(f"Source {source_id} :")
        lines.extend(f"  {el.id} — {el.enonce}" for el in els)
    return "\n".join(lines)


def _plan_thematic(
    ctx: PhaseContext, elements: list[_FactElement]
) -> tuple[str, list[_PlannedChapter], float]:
    """T2 : appelle le LLM, renvoie ``(global_title, chapitres, coût)``.

    Args:
        ctx: Contexte d'exécution.
        elements: Tous les éléments tracés.

    Returns:
        ``(global_title, chapitres planifiés triés par ordre, cost_usd)``.
    """
    prompt = ctx.prompts.render(
        TEMPLATE_THEMATIC_PLAN,
        output_language_label=language_label(ctx.settings.source_language),
        elements_listing=_build_elements_listing(elements),
    )
    response = invoke_llm(
        ctx,
        phase_id=PhaseId.CONSOLIDATION,
        system_prompt=None,
        user_prompt=prompt,
        response_format=JSON_OBJECT_RESPONSE_FORMAT,
    )
    payload = dict(
        parse_json_response(
            response.content,
            phase_id=PhaseId.CONSOLIDATION,
            finish_reason=response.finish_reason,
        )
    )
    global_title = str(payload.get("global_title", "Document consolidé"))
    planned = [
        _PlannedChapter(
            title=str(chap.get("title", "")).strip() or f"Chapitre {i}",
            order=int(chap.get("order", i)),
            element_ids=tuple(str(x) for x in chap.get("element_ids", [])),
        )
        for i, chap in enumerate(payload.get("chapters", []), start=1)
    ]
    planned.sort(key=lambda c: c.order)
    return global_title, planned, response.cost_usd


def _reconcile_coverage(
    planned: list[_PlannedChapter], *, all_ids: list[str]
) -> tuple[list[_PlannedChapter], list[str]]:
    """Contrôle #1 : rattache les ids orphelins à un chapitre complémentaire.

    Args:
        planned: Chapitres issus du plan LLM.
        all_ids: Tous les ids extraits en T1 (ordre stable).

    Returns:
        ``(chapitres_avec_filet, ids_orphelins)``. Les ids inconnus produits par
        le LLM (hors ``all_ids``) sont ignorés (ne peuvent rien rendre).
    """
    known = set(all_ids)
    assigned: set[str] = set()
    cleaned: list[_PlannedChapter] = []
    for chap in planned:
        kept = tuple(eid for eid in chap.element_ids if eid in known)
        assigned.update(kept)
        cleaned.append(
            _PlannedChapter(title=chap.title, order=chap.order, element_ids=kept)
        )
    orphans = [eid for eid in all_ids if eid not in assigned]
    if orphans:
        cleaned.append(
            _PlannedChapter(
                title=COMPLEMENTARY_CHAPTER_TITLE,
                order=len(cleaned) + 1,
                element_ids=tuple(orphans),
            )
        )
    return cleaned, orphans


def _elements_payload_for_chapter(
    element_ids: tuple[str, ...],
    by_id: dict[str, _FactElement],
    source_labels: dict[str, str],
) -> list[dict[str, str]]:
    """Construit la charge JSON des éléments assignés à un chapitre.

    Le champ ``source`` porte le **libellé lisible** (pas l'ULID) : c'est ce que
    le LLM citera pour attribuer un contenu. ``id`` reste l'identifiant technique
    (le LLM le ré-émet dans ``used_element_ids`` mais ne doit pas l'écrire dans
    le texte).

    Args:
        element_ids: Ids assignés au chapitre.
        by_id: Index ``id -> élément``.
        source_labels: Libellés lisibles par ``source_id``.

    Returns:
        Liste de dicts sérialisables (ordre des ids assignés).
    """
    return [
        {
            "id": by_id[eid].id,
            "source": source_labels.get(by_id[eid].source_id, by_id[eid].source_id),
            "type": by_id[eid].type,
            "enonce": by_id[eid].enonce,
            "donnees": by_id[eid].donnees,
            "extrait_verbatim": by_id[eid].extrait_verbatim,
        }
        for eid in element_ids
        if eid in by_id
    ]


def _strip_provenance_ids(
    body: str, *, by_id: dict[str, _FactElement], source_labels: dict[str, str]
) -> str:
    """Filet déterministe : retire tout identifiant technique résiduel du corps.

    Le prompt interdit déjà d'écrire les ``id``/ULID, mais on **garantit**
    qu'aucun n'atteint le document final : chaque id d'élément (« ULID#n ») et
    chaque ULID de source est remplacé par le libellé lisible de sa source.

    Args:
        body: Corps Markdown produit par le LLM.
        by_id: Index ``id -> élément`` (tous les éléments connus).
        source_labels: Libellés lisibles par ``source_id``.

    Returns:
        Le corps débarrassé des identifiants techniques.
    """
    out = body
    # Les ids d'élément (« ULID#n ») d'abord : ils contiennent l'ULID de source.
    for eid, el in by_id.items():
        out = out.replace(eid, source_labels.get(el.source_id, el.source_id))
    # Puis les ULID de source bruts éventuellement cités seuls.
    for source_id, label in source_labels.items():
        out = out.replace(source_id, label)
    return out


def _write_chapter_body(
    ctx: PhaseContext,
    chapter: _PlannedChapter,
    by_id: dict[str, _FactElement],
    source_labels: dict[str, str],
) -> tuple[str, list[str], float]:
    """T3 pour un chapitre : ``→ (body_markdown, used_ids, coût)``.

    Args:
        ctx: Contexte d'exécution.
        chapter: Chapitre planifié.
        by_id: Index ``id -> élément``.
        source_labels: Libellés lisibles par ``source_id``.

    Returns:
        ``(corps Markdown brut, ids utilisés, cost_usd)``. L'assainissement des
        identifiants techniques est fait par ``_resolve_chapter`` (couvre aussi
        la relecture d'un chapitre en cache).
    """
    elements_payload = _elements_payload_for_chapter(
        chapter.element_ids, by_id, source_labels
    )
    prompt = ctx.prompts.render(
        TEMPLATE_THEMATIC_CHAPTER,
        output_language_label=language_label(ctx.settings.source_language),
        style_label=style_label(ctx.settings.style_preset),
        style_directives=ctx.settings.style_directives,
        chapter_title=chapter.title,
        elements_json=json.dumps(elements_payload, ensure_ascii=False, indent=2),
    )
    response = invoke_llm(
        ctx,
        phase_id=PhaseId.CONSOLIDATION,
        system_prompt=None,
        user_prompt=prompt,
        response_format=JSON_OBJECT_RESPONSE_FORMAT,
    )
    payload = dict(
        parse_json_response(
            response.content,
            phase_id=PhaseId.CONSOLIDATION,
            finish_reason=response.finish_reason,
        )
    )
    body = str(payload.get("body_markdown", "")).strip()
    used = [str(x) for x in payload.get("used_element_ids", [])]
    return body, used, response.cost_usd


def _chapter_coverage_gaps(
    *, assigned: tuple[str, ...], used: tuple[str, ...]
) -> list[str]:
    """Contrôle #2 : ids assignés mais non rendus (``assigned - used``).

    Args:
        assigned: Ids assignés au chapitre.
        used: Ids déclarés utilisés par le LLM.

    Returns:
        Les ids manquants (ordre des assignés).
    """
    used_set = set(used)
    return [eid for eid in assigned if eid not in used_set]


def _resolve_chapter(
    ctx: PhaseContext,
    base_dir: Path,
    index: int,
    chapter: _PlannedChapter,
    by_id: dict[str, _FactElement],
    source_labels: dict[str, str],
    *,
    fresh: bool,
) -> tuple[_Chapter, list[str], float]:
    """Rédige (ou recharge si frais) un chapitre. ``→ (_Chapter, gaps, coût)``.

    L'écriture du fichier ``chapters/<index>.md`` est faite ICI (et non après le
    pool) pour une **reprise par chapitre** : un chapitre déjà frais est relu
    sans appel LLM.

    Args:
        ctx: Contexte d'exécution.
        base_dir: Dossier ``consolidation/`` du workspace.
        index: Numéro de chapitre (1-based).
        chapter: Chapitre planifié.
        by_id: Index ``id -> élément``.
        source_labels: Libellés lisibles par ``source_id``.
        fresh: ``True`` si les artefacts existants sont réutilisables.

    Returns:
        ``(_Chapter assemblable, ids manquants, cost_usd)``.
    """
    chapter_path = base_dir / CHAPTERS_SUBDIR / f"{index}.md"
    if fresh and chapter_path.exists():
        renumbered = chapter_path.read_text(encoding="utf-8")
        gaps: list[str] = []  # couverture #2 déjà journalisée au run initial
        cost = 0.0
    else:
        body, used, cost = _write_chapter_body(ctx, chapter, by_id, source_labels)
        renumbered, _ = renumber_subheadings(body, index)
        gaps = _chapter_coverage_gaps(
            assigned=chapter.element_ids, used=tuple(used)
        )
    # Assainissement systématique : aucun identifiant technique dans le livrable,
    # y compris pour un chapitre relu depuis un cache écrit par une version
    # antérieure (auto-cicatrisant). L'artefact est réécrit assaini.
    renumbered = _strip_provenance_ids(
        renumbered, by_id=by_id, source_labels=source_labels
    )
    ctx.artifacts.write_text_atomic(chapter_path, renumbered)
    # Le titre vient du plan (qui voit les ids) : on l'assainit aussi, sinon un id
    # glissé dans un titre fuiterait dans le sommaire et les méta-éléments (T4).
    title = _strip_provenance_ids(
        strip_existing_numbering(chapter.title),
        by_id=by_id,
        source_labels=source_labels,
    )
    chapter_obj = _Chapter(
        index=index,
        title=title or f"Chapitre {index}",
        body=renumbered,
        subheadings=subheadings_of(renumbered),
    )
    return chapter_obj, gaps, cost


def _produce_meta(
    ctx: PhaseContext, global_title: str, chapters: list[_PlannedChapter]
) -> tuple[dict[str, Any], float]:
    """T4 : méta-éléments (réutilise le prompt ``phase_5_consolidation``).

    On nourrit le prompt méta avec les **titres** de chapitres (le plan lisible du
    document), PAS les ids bruts d'éléments : sinon le LLM rédige titre/intro/
    conclusion à partir de jetons illisibles et la qualité s'effondre.

    Args:
        ctx: Contexte d'exécution.
        global_title: Titre proposé par le plan (repli).
        chapters: Chapitres planifiés (avec filet).

    Returns:
        ``(meta_dict, cost_usd)``.
    """
    summaries = [
        {"source_id": "", "title": c.title, "outline": [], "key_ideas": []}
        for c in chapters
    ]
    prompt = ctx.prompts.render(
        TEMPLATE_CONSOLIDATION,
        output_language_label=language_label(ctx.settings.source_language),
        style_label=style_label(ctx.settings.style_preset),
        style_directives=ctx.settings.style_directives,
        summaries_json=json.dumps(summaries, ensure_ascii=False, indent=2),
    )
    response = invoke_llm(
        ctx,
        phase_id=PhaseId.CONSOLIDATION,
        system_prompt=None,
        user_prompt=prompt,
        response_format=JSON_OBJECT_RESPONSE_FORMAT,
    )
    payload = dict(
        parse_json_response(
            response.content,
            phase_id=PhaseId.CONSOLIDATION,
            finish_reason=response.finish_reason,
        )
    )
    payload["global_title"] = payload.get("global_title") or global_title
    return payload, response.cost_usd


def _consistency_hash(
    ctx: PhaseContext, structured_by_source: dict[str, str]
) -> str:
    """Empreinte (mode + modèle + style + langue + contenu structuré).

    Args:
        ctx: Contexte d'exécution.
        structured_by_source: Markdown structuré par source.

    Returns:
        Empreinte SHA-256 hexadécimale.
    """
    payload = {
        "mode": str(ctx.settings.consolidation_mode),
        "model": str(ctx.settings.llm_model),
        "style": str(ctx.settings.style_preset),
        "style_directives": ctx.settings.style_directives,
        "source_language": str(ctx.settings.source_language),
        "sources": {
            sid: hashlib.sha256(md.encode("utf-8")).hexdigest()
            for sid, md in structured_by_source.items()
        },
    }
    blob = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


class ThematicConsolidationStrategy(ConsolidationStrategy):
    """Mode THEMATIC : refonte thématique transversale (map-reduce à provenance)."""

    def consolidate(
        self, ctx: PhaseContext, structured_by_source: dict[str, str]
    ) -> ConsolidationResult:
        """Produit le document consolidé thématique.

        Args:
            ctx: Contexte d'exécution.
            structured_by_source: Markdown structuré par ``source_id``.

        Returns:
            ``ConsolidationResult`` (markdown + coût cumulé).
        """
        base_dir = ctx.workspace / CONSOLIDATION_SUBDIR
        total_cost = 0.0
        # Libellés lisibles : aucun ULID ne doit atteindre le document final.
        source_labels = _source_labels(structured_by_source)

        # Reprise intra-phase : artefacts d'un run incompatible → on repart à neuf.
        current_hash = _consistency_hash(ctx, structured_by_source)
        manifest_path = base_dir / MANIFEST_FILENAME
        stale = (
            not manifest_path.exists()
            or json.loads(manifest_path.read_text(encoding="utf-8")).get("hash")
            != current_hash
        )
        if stale and base_dir.exists():
            shutil.rmtree(base_dir)
        ctx.artifacts.write_json_atomic(manifest_path, {"hash": current_hash})
        fresh = not stale

        # T1 — relevé factuel par source (ou rechargement si frais).
        facts_path = base_dir / FACTS_MASTER_FILENAME
        if fresh and facts_path.exists():
            payload = json.loads(facts_path.read_text(encoding="utf-8"))
            elements = [_FactElement(**raw) for raw in payload.get("elements", [])]
        else:
            ledger_results = map_bounded(
                lambda kv: _extract_ledger_one(ctx, kv),
                list(structured_by_source.items()),
                max_workers=ctx.settings.parallelism.llm_workers,
                pause_token=ctx.pause_token,
            )
            elements = []
            for els, cost in ledger_results:
                elements.extend(els)
                total_cost += cost
            ctx.artifacts.write_json_atomic(
                facts_path, {"elements": [asdict(el) for el in elements]}
            )
            ctx.artifacts.write_text_atomic(
                base_dir / FACTS_READABLE_FILENAME,
                _render_facts_md(elements, source_labels),
            )

        all_ids = [el.id for el in elements]

        # T2 — plan thématique + couverture #1 (ou rechargement si frais).
        plan_path = base_dir / THEMATIC_PLAN_FILENAME
        if fresh and plan_path.exists():
            plan_payload = json.loads(plan_path.read_text(encoding="utf-8"))
            global_title = str(plan_payload.get("global_title", "Document consolidé"))
            chapters_plan = [
                _PlannedChapter(
                    title=str(c["title"]),
                    order=int(c["order"]),
                    element_ids=tuple(str(x) for x in c["element_ids"]),
                )
                for c in plan_payload.get("chapters", [])
            ]
            orphans: list[str] = []
        else:
            global_title, planned, plan_cost = _plan_thematic(ctx, elements)
            total_cost += plan_cost
            chapters_plan, orphans = _reconcile_coverage(planned, all_ids=all_ids)
            ctx.artifacts.write_json_atomic(
                plan_path,
                {
                    "global_title": global_title,
                    "chapters": [
                        {
                            "title": c.title,
                            "order": c.order,
                            "element_ids": list(c.element_ids),
                        }
                        for c in chapters_plan
                    ],
                },
            )

        # T3 — rédaction par chapitre (parallélisée) + couverture #2.
        by_id = {el.id: el for el in elements}
        resolved = map_bounded(
            lambda ic: _resolve_chapter(
                ctx, base_dir, ic[0], ic[1], by_id, source_labels, fresh=fresh
            ),
            list(enumerate(chapters_plan, start=1)),
            max_workers=ctx.settings.parallelism.llm_workers,
            pause_token=ctx.pause_token,
        )
        chapters: list[_Chapter] = []
        chapter_gaps: dict[str, list[str]] = {}
        for (chapter_obj, gaps, cost), planned_chapter in zip(
            resolved, chapters_plan, strict=True
        ):
            total_cost += cost
            if gaps:
                chapter_gaps[planned_chapter.title] = gaps
            chapters.append(chapter_obj)
        ctx.artifacts.write_json_atomic(
            base_dir / COVERAGE_FILENAME,
            {"orphans": orphans, "chapter_gaps": chapter_gaps},
        )

        # T4 — méta + assemblage déterministe.
        meta, meta_cost = _produce_meta(ctx, global_title, chapters_plan)
        total_cost += meta_cost
        markdown = assemble_document(meta, chapters)
        return ConsolidationResult(consolidated_markdown=markdown, cost_usd=total_cost)
