"""Socle des générateurs de supports LLM.

Mutualise : l'appel LLM avec retry (parité moteur via ``default_classify`` +
émission de ``SupportRetryAttempt``), et un template-method par chapitre (boucle →
prompt → LLM → parse → items → rendu). Le contexte de prompt commun
(public/Bloom/densité/directives/langue/glossaire + chapitre) est construit ici :
un générateur concret ne déclare que son ``_template_name``, son parsing et son
rendu.

Les helpers de parsing JSON typé (``schema_error``, ``require_*``) vivent désormais
dans le module neutre ``infra/llm/json_schema`` (source unique, partagée avec les
extracteurs des Visualisations) ; ils sont **ré-exposés** ici pour les générateurs
concrets (rétro-compatibilité d'import).

Les bases sont **génériques** sur le type d'item produit (``_ItemT``), ce qui
évite tout ``cast``/``assert`` dans les générateurs concrets.
"""

from __future__ import annotations

from abc import abstractmethod
from datetime import UTC, datetime
from typing import Any, Generic, TypeVar

from fahmi2.core.corpus import Chapter
from fahmi2.core.errors.error_info import ErrorInfo
from fahmi2.domain.enums import Language, SupportType
from fahmi2.domain.glossary import Term
from fahmi2.domain.supports import SupportArtifact, SupportItem
from fahmi2.infra.llm.interface import JSON_OBJECT_RESPONSE_FORMAT, LLMResponse
from fahmi2.infra.llm.invocation import invoke_llm_chat_with_retry, parse_llm_json

# Helpers de parsing JSON typé — source unique dans ``infra/llm/json_schema`` ;
# **ré-exportés** ici (cf. ``__all__``) pour les générateurs concrets.
from fahmi2.infra.llm.json_schema import (
    require_bool,
    require_int,
    require_list,
    require_mapping,
    require_str,
    require_str_list,
    schema_error,
)
from fahmi2.pedagogy.events import SupportRetryAttempt
from fahmi2.pedagogy.labels import (
    audience_label,
    bloom_label,
    density_label,
    format_glossary_terms,
    language_label,
)
from fahmi2.pedagogy.support_generator import SupportContext, SupportGenerator

# Ré-export explicite des helpers de parsing JSON typé (source : ``infra/llm/json_schema``)
# pour les générateurs concrets qui les importent depuis ce socle.
__all__ = [
    "require_bool",
    "require_int",
    "require_list",
    "require_mapping",
    "require_str",
    "require_str_list",
    "schema_error",
]

_ItemT = TypeVar("_ItemT", bound=SupportItem)


def _now() -> datetime:
    """Horodatage UTC courant.

    Returns:
        ``datetime`` UTC aware.
    """
    return datetime.now(tz=UTC)


def invoke_support_llm(
    ctx: SupportContext,
    *,
    support_type: SupportType,
    language: Language,
    system_prompt: str | None,
    user_prompt: str,
    response_format: dict[str, str] | None = None,
) -> LLMResponse:
    """Appelle le LLM avec retry et émission de ``SupportRetryAttempt``.

    Args:
        ctx: Contexte d'exécution.
        support_type: Support en cours (pour les events).
        language: Langue (pour les events).
        system_prompt: Prompt système optionnel.
        user_prompt: Prompt utilisateur.
        response_format: Contrainte de format provider (cf. ``invoke_llm_chat``).
            À passer ``JSON_OBJECT_RESPONSE_FORMAT`` pour tout support dont la
            sortie est parsée en JSON par ``parse_llm_json``.

    Returns:
        La ``LLMResponse``.

    Raises:
        Fahmi2Error: La dernière erreur si toutes les tentatives échouent.
    """

    def _on_retry(attempt: int, delay_seconds: float, error: ErrorInfo) -> None:
        ctx.event_bus.publish(
            SupportRetryAttempt(
                timestamp=_now(),
                support_type=support_type,
                language=language,
                attempt=attempt,
                delay_seconds=delay_seconds,
                error=error,
            )
        )

    return invoke_llm_chat_with_retry(
        ctx.llm_provider,
        model=str(ctx.pedagogy.llm_model),
        config=ctx.pedagogy.llm_config,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        retry_policy=ctx.retry_policy,
        on_retry=_on_retry,
        response_format=response_format,
    )


class _PerChapterLlmGenerator(SupportGenerator, Generic[_ItemT]):
    """Base des générateurs LLM produisant des items **par chapitre**."""

    @property
    def uses_llm(self) -> bool:
        """Générateur LLM."""
        return True

    @property
    @abstractmethod
    def _template_name(self) -> str:
        """Nom du template Jinja2 (sans extension)."""

    @abstractmethod
    def _parse_items(
        self, payload: Any, *, chapter: Chapter  # noqa: ANN401
    ) -> tuple[_ItemT, ...]:
        """Convertit la réponse JSON d'un chapitre en items typés."""

    @abstractmethod
    def _render_content(
        self, items: tuple[_ItemT, ...], *, language: Language
    ) -> str:
        """Rend le support en Markdown (vue combinée, avec réponses si évaluatif)."""

    def generate(
        self,
        ctx: SupportContext,
        *,
        language: Language,
        chapters: tuple[Chapter, ...],
        glossary: tuple[Term, ...],
    ) -> SupportArtifact:
        """Génère le support par chapitre (cf. ``SupportGenerator.generate``).

        Args:
            ctx: Contexte d'exécution.
            language: Langue cible.
            chapters: Chapitres du document consolidé.
            glossary: Termes du glossaire de la langue.

        Returns:
            Le ``SupportArtifact`` (items + rendu + corrigé éventuel + coût).
        """
        items: list[_ItemT] = []
        total_cost = 0.0
        for chapter in chapters:
            ctx.pause_token.wait_if_paused()
            ctx.pause_token.raise_if_cancelled()
            user_prompt = ctx.prompts.render(
                self._template_name,
                **self._chapter_context(
                    ctx, chapter=chapter, language=language, glossary=glossary
                ),
            )
            response = invoke_support_llm(
                ctx,
                support_type=self.support_type,
                language=language,
                system_prompt=None,
                user_prompt=user_prompt,
                response_format=JSON_OBJECT_RESPONSE_FORMAT,
            )
            total_cost += response.cost_usd
            payload = parse_llm_json(
                response.content,
                context_label=f"{self.support_type.value}:{chapter.index}",
                finish_reason=response.finish_reason,
            )
            items.extend(self._parse_items(payload, chapter=chapter))
        items_t = tuple(items)
        subject, correction = self._finalize_render(ctx, items_t, language=language)
        return SupportArtifact(
            support_type=self.support_type,
            language=language,
            items=items_t,
            rendered_markdown=subject,
            correction_markdown=correction,
            cost_usd=total_cost,
        )

    def _chapter_context(
        self,
        ctx: SupportContext,
        *,
        chapter: Chapter,
        language: Language,
        glossary: tuple[Term, ...],
    ) -> dict[str, Any]:
        """Contexte Jinja2 commun à tous les prompts par chapitre.

        Args:
            ctx: Contexte d'exécution.
            chapter: Chapitre courant.
            language: Langue cible.
            glossary: Glossaire de la langue.

        Returns:
            Le mapping de variables du template.
        """
        ped = ctx.pedagogy
        return {
            "output_language_label": language_label(language),
            "audience_label": audience_label(ped.target_audience),
            "bloom_label": bloom_label(ped.bloom_objective),
            "density_label": density_label(ped.density),
            "pedagogy_directives": ped.pedagogy_directives,
            "glossary_terms": format_glossary_terms(glossary),
            "chapter_title": chapter.title,
            "chapter_markdown": chapter.body_markdown,
        }

    def _finalize_render(
        self,
        ctx: SupportContext,
        items: tuple[_ItemT, ...],
        *,
        language: Language,
    ) -> tuple[str, str | None]:
        """Rendu final : (sujet, corrigé). Par défaut : combiné, sans corrigé.

        Args:
            ctx: Contexte d'exécution.
            items: Items générés.
            language: Langue cible.

        Returns:
            ``(sujet_markdown, corrige_markdown | None)``.
        """
        del ctx
        return self._render_content(items, language=language), None


class _EvaluativePerChapterLlmGenerator(_PerChapterLlmGenerator[_ItemT]):
    """Base des générateurs **évaluatifs** par chapitre (corrigé séparable)."""

    @abstractmethod
    def _render_subject(
        self, items: tuple[_ItemT, ...], *, language: Language
    ) -> str:
        """Rend le **sujet** seul (sans réponses)."""

    @abstractmethod
    def _render_correction(
        self, items: tuple[_ItemT, ...], *, language: Language
    ) -> str:
        """Rend le **corrigé** (réponses + justifications)."""

    def _finalize_render(
        self,
        ctx: SupportContext,
        items: tuple[_ItemT, ...],
        *,
        language: Language,
    ) -> tuple[str, str | None]:
        """Sujet+corrigé séparés si demandé, sinon rendu combiné.

        Args:
            ctx: Contexte d'exécution.
            items: Items générés.
            language: Langue cible.

        Returns:
            ``(sujet, corrigé)`` si ``separate_correction``, sinon ``(combiné, None)``.
        """
        if self.support_type in ctx.pedagogy.separate_correction:
            return (
                self._render_subject(items, language=language),
                self._render_correction(items, language=language),
            )
        return self._render_content(items, language=language), None
