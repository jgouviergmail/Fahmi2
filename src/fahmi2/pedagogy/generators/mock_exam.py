"""Générateur « Examen blanc » : sujet composite + barème (LLM, document entier).

Contrairement aux autres générateurs LLM, l'examen blanc consomme **tout** le
document (chapitres concaténés) en un seul appel, pour produire un sujet cohérent
et transversal. Il reste évaluatif : le barème/corrigé est séparable.
"""

from __future__ import annotations

from fahmi2.domain.enums import Language, SupportType
from fahmi2.domain.glossary import Term
from fahmi2.domain.supports import (
    MockExam,
    MockExamSection,
    SupportArtifact,
)
from fahmi2.infra.llm.invocation import parse_llm_json
from fahmi2.pedagogy.chapters import Chapter
from fahmi2.pedagogy.generators._base import (
    invoke_support_llm,
    require_list,
    require_mapping,
    require_str,
)
from fahmi2.pedagogy.labels import (
    audience_label,
    bloom_label,
    density_label,
    format_glossary_terms,
    language_label,
)
from fahmi2.pedagogy.support_generator import SupportContext, SupportGenerator

_TEMPLATE_NAME = "pedagogy_mock_exam"
_HEADING_GRADING = "Barème"
_CHAPTER_JOIN = "\n\n"


def _parse_exam(content: str, *, context_label: str) -> MockExam:
    """Parse la réponse JSON en un ``MockExam``.

    Args:
        content: Contenu JSON renvoyé par le LLM.
        context_label: Libellé de contexte (messages d'erreur).

    Returns:
        Le ``MockExam`` reconstruit.

    Raises:
        LLMError: Si le JSON est invalide ou de schéma inattendu.
    """
    mapping = require_mapping(
        parse_llm_json(content, context_label=context_label),
        context_label=context_label,
    )
    sections: list[MockExamSection] = []
    for raw in require_list(mapping, "sections", context_label=context_label):
        section = require_mapping(raw, context_label=context_label)
        sections.append(
            MockExamSection(
                title=require_str(section, "title", context_label=context_label),
                statement_markdown=require_str(
                    section, "statement_markdown", context_label=context_label
                ),
            )
        )
    return MockExam(
        title=require_str(mapping, "title", context_label=context_label),
        sections=tuple(sections),
        grading_markdown=require_str(
            mapping, "grading_markdown", context_label=context_label
        ),
    )


def _render_subject(exam: MockExam, *, language: Language) -> str:
    """Rend le sujet de l'examen (titre + sections, sans barème).

    Args:
        exam: Examen blanc.
        language: Langue (ignorée hors titre éventuel).

    Returns:
        Le Markdown du sujet.
    """
    del language
    parts = [f"# {exam.title}", ""]
    for number, section in enumerate(exam.sections, start=1):
        parts.append(f"## {number}. {section.title}")
        parts.append("")
        parts.append(section.statement_markdown.strip())
        parts.append("")
    return "\n".join(parts).rstrip() + "\n"


def _render_combined(exam: MockExam, *, language: Language) -> str:
    """Rend le sujet suivi du barème.

    Args:
        exam: Examen blanc.
        language: Langue.

    Returns:
        Le Markdown sujet + barème.
    """
    subject = _render_subject(exam, language=language)
    return f"{subject}\n## {_HEADING_GRADING}\n\n{exam.grading_markdown.strip()}\n"


class MockExamGenerator(SupportGenerator):
    """Produit un examen blanc composite (sujet + barème) sur tout le document."""

    @property
    def support_type(self) -> SupportType:
        """Type de support."""
        return SupportType.MOCK_EXAM

    @property
    def uses_llm(self) -> bool:
        """Générateur LLM."""
        return True

    def generate(
        self,
        ctx: SupportContext,
        *,
        language: Language,
        chapters: tuple[Chapter, ...],
        glossary: tuple[Term, ...],
    ) -> SupportArtifact:
        """Génère l'examen blanc (cf. ``SupportGenerator.generate``).

        Args:
            ctx: Contexte d'exécution.
            language: Langue cible.
            chapters: Chapitres (concaténés en document complet).
            glossary: Glossaire de la langue.

        Returns:
            Le ``SupportArtifact`` (un ``MockExam`` + rendu + corrigé éventuel).
        """
        consolidated = _CHAPTER_JOIN.join(
            f"# {chapter.index}. {chapter.title}\n\n{chapter.body_markdown}"
            for chapter in chapters
        )
        ped = ctx.pedagogy
        prompt = ctx.prompts.render(
            _TEMPLATE_NAME,
            output_language_label=language_label(language),
            audience_label=audience_label(ped.target_audience),
            bloom_label=bloom_label(ped.bloom_objective),
            density_label=density_label(ped.density),
            pedagogy_directives=ped.pedagogy_directives,
            glossary_terms=format_glossary_terms(glossary),
            consolidated_markdown=consolidated,
        )
        response = invoke_support_llm(
            ctx,
            support_type=self.support_type,
            language=language,
            system_prompt=None,
            user_prompt=prompt,
        )
        exam = _parse_exam(response.content, context_label=self.support_type.value)
        separate = self.support_type in ped.separate_correction
        rendered = (
            _render_subject(exam, language=language)
            if separate
            else _render_combined(exam, language=language)
        )
        correction = exam.grading_markdown if separate else None
        return SupportArtifact(
            support_type=self.support_type,
            language=language,
            items=(exam,),
            rendered_markdown=rendered,
            correction_markdown=correction,
            cost_usd=response.cost_usd,
        )
