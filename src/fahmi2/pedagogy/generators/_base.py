"""Socle des générateurs de supports LLM.

Mutualise : l'appel LLM avec retry (parité moteur via ``default_classify`` +
émission de ``SupportRetryAttempt``), des helpers de parsing JSON typé, et un
template-method par chapitre (boucle → prompt → LLM → parse → items → rendu).
Le contexte de prompt commun (public/Bloom/densité/directives/langue/glossaire +
chapitre) est construit ici : un générateur concret ne déclare que son
``_template_name``, son parsing et son rendu.

Les bases sont **génériques** sur le type d'item produit (``_ItemT``), ce qui
évite tout ``cast``/``assert`` dans les générateurs concrets.
"""

from __future__ import annotations

from abc import abstractmethod
from datetime import UTC, datetime
from typing import Any, Generic, TypeVar

from fahmi2.core.errors.error_info import ErrorInfo
from fahmi2.core.errors.exceptions import Fahmi2Error, LLMError
from fahmi2.core.errors.severity import Severity
from fahmi2.core.retry.classification import default_classify
from fahmi2.core.retry.policy import RetryDecision
from fahmi2.core.retry.runner import with_retry
from fahmi2.domain.enums import Language, SupportType
from fahmi2.domain.glossary import Term
from fahmi2.domain.supports import SupportArtifact, SupportItem
from fahmi2.infra.llm.interface import JSON_OBJECT_RESPONSE_FORMAT, LLMResponse
from fahmi2.infra.llm.invocation import invoke_llm_chat, parse_llm_json
from fahmi2.pedagogy.chapters import Chapter
from fahmi2.pedagogy.events import SupportRetryAttempt
from fahmi2.pedagogy.labels import (
    audience_label,
    bloom_label,
    density_label,
    format_glossary_terms,
    language_label,
)
from fahmi2.pedagogy.support_generator import SupportContext, SupportGenerator

_INVALID_SCHEMA_CODE = "LLM.INVALID_SCHEMA"

_ItemT = TypeVar("_ItemT", bound=SupportItem)


def _now() -> datetime:
    """Horodatage UTC courant.

    Returns:
        ``datetime`` UTC aware.
    """
    return datetime.now(tz=UTC)


def schema_error(context_label: str, detail: str) -> LLMError:
    """Construit une ``LLMError`` de schéma invalide (non retryable).

    Args:
        context_label: Libellé de contexte (ex: ``"qcm:1"``).
        detail: Détail du problème de schéma.

    Returns:
        L'``LLMError`` (``LLM.INVALID_SCHEMA``).
    """
    return LLMError(
        code=_INVALID_SCHEMA_CODE,
        user_message=f"Réponse du LLM inattendue pour {context_label} : {detail}",
        severity=Severity.ERROR,
        technical_details={"context_label": context_label, "detail": detail},
    )


def require_mapping(value: Any, *, context_label: str) -> dict[str, Any]:  # noqa: ANN401
    """Exige un objet JSON (dict).

    Args:
        value: Valeur décodée.
        context_label: Libellé de contexte (messages d'erreur).

    Returns:
        Le dict.

    Raises:
        LLMError: Si ``value`` n'est pas un dict.
    """
    if not isinstance(value, dict):
        raise schema_error(context_label, "objet JSON attendu")
    return value


def require_list(
    mapping: dict[str, Any], key: str, *, context_label: str
) -> list[Any]:
    """Exige une liste à ``key``.

    Args:
        mapping: Objet JSON.
        key: Clé attendue.
        context_label: Libellé de contexte.

    Returns:
        La liste.

    Raises:
        LLMError: Si la valeur n'est pas une liste.
    """
    value = mapping.get(key)
    if not isinstance(value, list):
        raise schema_error(context_label, f"liste attendue pour « {key} »")
    return value


def require_str(mapping: dict[str, Any], key: str, *, context_label: str) -> str:
    """Exige une chaîne non vide à ``key``.

    Args:
        mapping: Objet JSON.
        key: Clé attendue.
        context_label: Libellé de contexte.

    Returns:
        La chaîne.

    Raises:
        LLMError: Si la valeur n'est pas une chaîne non vide.
    """
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        raise schema_error(context_label, f"chaîne attendue pour « {key} »")
    return value


def require_int(mapping: dict[str, Any], key: str, *, context_label: str) -> int:
    """Exige un entier à ``key`` (rejette ``bool``).

    Args:
        mapping: Objet JSON.
        key: Clé attendue.
        context_label: Libellé de contexte.

    Returns:
        L'entier.

    Raises:
        LLMError: Si la valeur n'est pas un entier.
    """
    value = mapping.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise schema_error(context_label, f"entier attendu pour « {key} »")
    return value


def require_bool(mapping: dict[str, Any], key: str, *, context_label: str) -> bool:
    """Exige un booléen à ``key``.

    Args:
        mapping: Objet JSON.
        key: Clé attendue.
        context_label: Libellé de contexte.

    Returns:
        Le booléen.

    Raises:
        LLMError: Si la valeur n'est pas un booléen.
    """
    value = mapping.get(key)
    if not isinstance(value, bool):
        raise schema_error(context_label, f"booléen attendu pour « {key} »")
    return value


def require_str_list(
    mapping: dict[str, Any], key: str, *, context_label: str
) -> tuple[str, ...]:
    """Exige une liste de chaînes non vide à ``key``.

    Args:
        mapping: Objet JSON.
        key: Clé attendue.
        context_label: Libellé de contexte.

    Returns:
        Le tuple de chaînes (vides écartées).

    Raises:
        LLMError: Si aucune chaîne exploitable n'est trouvée.
    """
    raw = require_list(mapping, key, context_label=context_label)
    out = [str(x) for x in raw if str(x).strip()]
    if not out:
        raise schema_error(context_label, f"liste de chaînes attendue pour « {key} »")
    return tuple(out)


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
    attempts = {"n": 0}

    def _once() -> LLMResponse:
        attempts["n"] += 1
        try:
            return invoke_llm_chat(
                ctx.llm_provider,
                model=str(ctx.pedagogy.llm_model),
                config=ctx.pedagogy.llm_config,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response_format=response_format,
            )
        except Fahmi2Error as exc:
            if default_classify(exc) is RetryDecision.RETRY:
                ctx.event_bus.publish(
                    SupportRetryAttempt(
                        timestamp=_now(),
                        support_type=support_type,
                        language=language,
                        attempt=attempts["n"],
                        delay_seconds=ctx.retry_policy.compute_delay(
                            attempt=attempts["n"]
                        ),
                        error=ErrorInfo.from_exception(exc),
                    )
                )
            raise

    return with_retry(_once, policy=ctx.retry_policy, classify=default_classify)


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
