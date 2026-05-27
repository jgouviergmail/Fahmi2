"""Handler Phase 6 — production des artefacts finaux par langue de sortie.

Deux étapes pour les langues de ``settings.output_languages`` :

1. **Localisation du glossaire** (par langue cible ≠ source) : appel LLM structuré
   (``_localize_glossary``) qui traduit chaque terme vers son équivalent métier
   consacré (ou le garde si international) et traduit sa définition. On rend
   ``glossary.{lang}.md`` de façon **déterministe**, on dérive les équivalents
   ``terme_source -> terme_localisé`` (en mémoire) et on **persiste** ``cross_lang``
   dans ``glossary_master.json`` (pour l'aval : Pédagogie, Dialogue). Le glossaire de
   la **langue source** est rendu tel quel (sans appel LLM).
2. **Traduction documentaire** : la langue source **copie** les docs par source +
   consolidé ; les autres langues les **traduisent** via le LLM, avec les équivalents
   de glossaire injectés comme indice terminologique.

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
    parse_json_response,
    style_label,
    utc_now,
)
from fahmi2.pipeline.phase_handler import PhaseContext, PhaseHandler

_STRUCTURED_SUBDIR = "structured"
_CONSOLIDATED_MASTER_FILENAME = "consolidated_master.md"
_GLOSSARY_MASTER_FILENAME = "glossary_master.json"
_PER_VIDEO_OUTPUT_SUBDIR = "per-video"
_TEMPLATE_NAME = "phase_6_translation"
_GLOSSARY_LOCALIZATION_TEMPLATE = "phase_6_glossary_localization"


@dataclass(frozen=True)
class _TranslationTask:
    """Une traduction LLM à effectuer : document source → fichier cible."""

    source_markdown: str
    target: Language
    target_path: Path


@dataclass(frozen=True)
class _LocalizedTerm:
    """Terme localisé : forme source (appariement), forme cible, définition cible."""

    source: str
    term: str
    definition: str


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

        # Étape 1 — localisation parallèle des glossaires (1 appel LLM par langue
        # cible ≠ source). map_bounded préserve l'ordre et honore le pause_token.
        non_source_targets = [
            t
            for t in ctx.settings.output_languages
            if t is not ctx.settings.source_language
        ]
        localization_results = map_bounded(
            lambda target: (
                target,
                *self._localize_glossary(ctx, target=target, payload=glossary_master),
            ),
            non_source_targets,
            max_workers=ctx.settings.parallelism.llm_workers,
            pause_token=ctx.pause_token,
        )
        cross_lang_by_language: dict[Language, dict[str, str]] = {}
        localization_cost = 0.0
        for target, localized, cost in localization_results:
            localization_cost += cost
            cross_lang_by_language[target] = {loc.source: loc.term for loc in localized}
            ctx.artifacts.write_text_atomic(
                ctx.output_dir / glossary_doc_filename(target),
                _render_localized_glossary(localized, glossary_master, target),
            )
        # Glossaire de la langue source (si produite) : rendu master, aucun appel LLM.
        if ctx.settings.source_language in ctx.settings.output_languages:
            ctx.artifacts.write_text_atomic(
                ctx.output_dir / glossary_doc_filename(ctx.settings.source_language),
                _render_master_glossary(glossary_master, ctx.settings.source_language),
            )
        # Persistance pour l'aval : seulement s'il y a des équivalents (sinon pas de
        # réécriture inutile du master ni de churn de mtime côté Pédagogie/Dialogue).
        if cross_lang_by_language:
            _persist_cross_lang(ctx, glossary_master, cross_lang_by_language)

        # Étape 2 — traductions documentaires (per-source + consolidé) en parallèle ;
        # l'indice « équivalents » provient de cross_lang_by_language.
        tasks: list[_TranslationTask] = []
        for target in ctx.settings.output_languages:
            self._collect_doc_tasks(
                ctx,
                target=target,
                consolidated_master_md=consolidated_master,
                per_source_structured=per_source_structured,
                tasks=tasks,
            )
        costs = map_bounded(
            lambda task: self._run_translation(ctx, task, cross_lang_by_language),
            tasks,
            max_workers=ctx.settings.parallelism.llm_workers,
            pause_token=ctx.pause_token,
        )
        return build_succeeded_phase(
            phase_id=self.phase_id,
            artifact_path=ctx.output_dir,
            started_at=started_at,
            cost_usd=localization_cost + sum(costs),
        )

    def _collect_doc_tasks(
        self,
        ctx: PhaseContext,
        *,
        target: Language,
        consolidated_master_md: str,
        per_source_structured: dict[str, str],
        tasks: list[_TranslationTask],
    ) -> None:
        """Écrit les copies (langue source) et empile les traductions per-source +
        consolidé (langues ≠ source). Le glossaire est traité en amont (localisation).

        Args:
            ctx: Contexte.
            target: Langue cible.
            consolidated_master_md: Document consolidé en langue source.
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
            ctx.artifacts.write_text_atomic(consolidated_target, consolidated_master_md)
        else:
            tasks.append(
                _TranslationTask(consolidated_master_md, target, consolidated_target)
            )

    def _run_translation(
        self,
        ctx: PhaseContext,
        task: _TranslationTask,
        cross_lang_by_language: dict[Language, dict[str, str]],
    ) -> float:
        """Traduit une tâche via le LLM et écrit le fichier cible.

        Args:
            ctx: Contexte.
            task: Tâche de traduction (source + langue + chemin cible).
            cross_lang_by_language: Équivalents ``terme_source -> terme_localisé``
                par langue (issus de la localisation du glossaire).

        Returns:
            Le coût LLM (USD).
        """
        translated, cost = self._translate(
            ctx, task.source_markdown, task.target, cross_lang_by_language
        )
        ctx.artifacts.write_text_atomic(task.target_path, translated)
        return cost

    def _translate(
        self,
        ctx: PhaseContext,
        source_markdown: str,
        target: Language,
        cross_lang_by_language: dict[Language, dict[str, str]],
    ) -> tuple[str, float]:
        """Traduit un document Markdown vers la langue cible via le LLM.

        Args:
            ctx: Contexte.
            source_markdown: Document source.
            target: Langue cible.
            cross_lang_by_language: Équivalents ``terme_source -> terme_localisé``
                par langue (injectés comme indice terminologique dans le prompt).

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
                cross_lang_by_language.get(target, {})
            ),
            source_markdown=source_markdown,
        )
        response = invoke_llm(
            ctx, phase_id=self.phase_id, system_prompt=None, user_prompt=prompt
        )
        return response.content, response.cost_usd

    def _localize_glossary(
        self,
        ctx: PhaseContext,
        *,
        target: Language,
        payload: dict[str, Any],
    ) -> tuple[list[_LocalizedTerm], float]:
        """Localise les termes du glossaire master vers ``target`` via le LLM.

        Args:
            ctx: Contexte d'exécution.
            target: Langue cible (≠ langue source).
            payload: Payload JSON du glossaire master.

        Returns:
            ``(localized, cost)`` : un ``_LocalizedTerm`` par terme master (ordre
            préservé ; repli sur la forme/définition source si l'entrée LLM manque),
            et le coût LLM. ``([], 0.0)`` si le glossaire est vide.

        Raises:
            LLMError / ValidationError: via ``parse_json_response`` si JSON invalide.
        """
        master_terms = payload.get("terms", [])
        if not master_terms:
            return [], 0.0
        prompt = ctx.prompts.render(
            _GLOSSARY_LOCALIZATION_TEMPLATE,
            source_language_label=language_label(ctx.settings.source_language),
            target_language_label=language_label(target),
            style_label=style_label(ctx.settings.style_preset),
            style_directives=ctx.settings.style_directives,
            terms=[
                {
                    "term": str(t.get("term", "")),
                    "acronym": t.get("acronym"),
                    "definition": str(t.get("definition", "")),
                }
                for t in master_terms
            ],
        )
        response = invoke_llm(
            ctx, phase_id=self.phase_id, system_prompt=None, user_prompt=prompt
        )
        entries = parse_json_response(response.content, phase_id=self.phase_id)
        dict_entries = (
            [e for e in entries if isinstance(e, dict)]
            if isinstance(entries, list)
            else []
        )
        # Appariement **par position** quand le LLM a renvoyé un objet par terme dans
        # l'ordre demandé (cas normal) : robuste à une réémission imparfaite du champ
        # ``source`` (les termes acronymes voyaient leur définition tomber en langue
        # source). Repli sur l'appariement par terme source sinon, puis per-terme.
        aligned = len(dict_entries) == len(master_terms)
        by_source: dict[str, dict[str, Any]] = {
            str(e.get("source", "")).strip(): e for e in dict_entries
        }
        localized: list[_LocalizedTerm] = []
        for index, t in enumerate(master_terms):
            source = str(t.get("term", ""))
            entry = dict_entries[index] if aligned else by_source.get(source.strip(), {})
            localized.append(
                _LocalizedTerm(
                    source=source,
                    term=str(entry.get("term") or source),
                    definition=str(entry.get("definition") or t.get("definition", "")),
                )
            )
        return localized, response.cost_usd


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


def _glossary_terms_for_template(cross_lang: dict[str, str]) -> list[dict[str, str]]:
    """Construit la liste ``[{source, target}]`` injectée dans le prompt de traduction.

    Args:
        cross_lang: Mapping ``terme_source -> terme_localisé`` d'une langue cible.

    Returns:
        Liste de ``{"source": "...", "target": "..."}`` (vide si aucun équivalent).
    """
    return [{"source": source, "target": term} for source, term in cross_lang.items()]


def _render_master_glossary(payload: dict[str, Any], language: Language) -> str:
    """Rend le glossaire master tel quel (termes/définitions source) en Markdown.

    Utilisé pour la **langue source** (aucune localisation). L'``acronym_expansion``
    reste dans sa langue d'origine (invariant phase 1/2).

    Args:
        payload: JSON master.
        language: Langue (titre H1 + en-têtes).

    Returns:
        Le glossaire au format tableau Markdown.
    """
    from fahmi2.domain.glossary import (  # noqa: PLC0415
        parse_glossary_master_terms,
        render_glossary_markdown_table,
    )

    return render_glossary_markdown_table(
        language=language, terms=parse_glossary_master_terms(payload)
    )


def _render_localized_glossary(
    localized: list[_LocalizedTerm], payload: dict[str, Any], language: Language
) -> str:
    """Rend ``glossary.{language}.md`` à partir des termes localisés.

    Termes et définitions localisés ; ``acronym`` + ``acronym_expansion`` repris du
    master (invariants). Aligné par ordre sur ``payload['terms']``.

    Args:
        localized: Termes localisés (un par terme master, même ordre).
        payload: JSON master (acronyme + expansion conservés).
        language: Langue cible (titre H1 + en-têtes).

    Returns:
        Le glossaire localisé au format tableau Markdown.
    """
    from fahmi2.domain.glossary import (  # noqa: PLC0415
        Term,
        render_glossary_markdown_table,
    )

    master = payload.get("terms", [])
    terms = [
        Term(
            term=loc.term,
            definition=loc.definition,
            acronym=str(raw["acronym"]) if raw.get("acronym") else None,
            acronym_expansion=(
                str(raw["acronym_expansion"]) if raw.get("acronym_expansion") else None
            ),
        )
        for loc, raw in zip(localized, master, strict=True)
    ]
    return render_glossary_markdown_table(language=language, terms=terms)


def _persist_cross_lang(
    ctx: PhaseContext,
    payload: dict[str, Any],
    cross_lang_by_language: dict[Language, dict[str, str]],
) -> None:
    """Réécrit ``glossary_master.json`` en ajoutant ``cross_lang`` à chaque terme.

    Écriture atomique. Clés = codes langue (round-trip ``parse_glossary_master_terms``).
    Sert l'aval (Pédagogie/Dialogue) ; les étapes de la phase 6 utilisent, elles, le
    mapping en mémoire.

    Args:
        ctx: Contexte (artifact store + workspace).
        payload: Payload master (muté : ajout de ``cross_lang`` par terme).
        cross_lang_by_language: Équivalents ``terme_source -> terme_localisé`` par langue.
    """
    for raw in payload.get("terms", []):
        source = str(raw.get("term", ""))
        raw["cross_lang"] = {
            lang.value: mapping[source]
            for lang, mapping in cross_lang_by_language.items()
            if source in mapping
        }
    ctx.artifacts.write_json_atomic(
        ctx.workspace / _GLOSSARY_MASTER_FILENAME, payload
    )
