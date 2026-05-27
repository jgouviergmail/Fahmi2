"""Libellés humains (FR) des réglages pédagogie + formatage du glossaire pour prompts.

Tables de correspondance dédiées à la pédagogie (le pipeline a les siennes dans
``pipeline/handlers/_base``) : public cible, objectif Bloom, densité, langue.
"""

from __future__ import annotations

from fahmi2.domain.enums import (
    BloomObjective,
    Language,
    SupportDensity,
    TargetAudience,
)
from fahmi2.domain.glossary import Term
from fahmi2.domain.languages import language_label as _language_label

_AUDIENCE_LABELS_FR: dict[TargetAudience, str] = {
    TargetAudience.DISCOVERY: "grand public (découverte)",
    TargetAudience.HIGH_SCHOOL: "lycée",
    TargetAudience.LICENCE: "licence (premier cycle universitaire)",
    TargetAudience.MASTER_EXPERT: "master / expert",
}

_BLOOM_LABELS_FR: dict[BloomObjective, str] = {
    BloomObjective.AUTO: "automatique (adapté au public cible)",
    BloomObjective.RESTITUTE: "restituer (mémorisation, définitions)",
    BloomObjective.UNDERSTAND_APPLY: "comprendre et appliquer",
    BloomObjective.ANALYZE_BEYOND: "analyser et au-delà (synthèse, évaluation)",
}

_DENSITY_LABELS_FR: dict[SupportDensity, str] = {
    SupportDensity.LIGHT: "légère",
    SupportDensity.STANDARD: "standard",
    SupportDensity.DENSE: "dense",
}


def language_label(language: Language) -> str:
    """Libellé FR (minuscule) d'une langue.

    Délègue à la source unique ``domain.languages`` (ré-export pour compat des
    modules qui importent ``language_label`` depuis ce module).

    Args:
        language: Langue.

    Returns:
        Le libellé (ex: ``"français"``).
    """
    return _language_label(language)


def audience_label(audience: TargetAudience) -> str:
    """Libellé FR d'un public cible.

    Args:
        audience: Public cible.

    Returns:
        Le libellé humain.
    """
    return _AUDIENCE_LABELS_FR[audience]


def bloom_label(bloom: BloomObjective) -> str:
    """Libellé FR d'un objectif Bloom.

    Args:
        bloom: Objectif cognitif.

    Returns:
        Le libellé humain.
    """
    return _BLOOM_LABELS_FR[bloom]


def density_label(density: SupportDensity) -> str:
    """Libellé FR d'une densité.

    Args:
        density: Densité.

    Returns:
        Le libellé humain.
    """
    return _DENSITY_LABELS_FR[density]


def format_glossary_terms(glossary: tuple[Term, ...]) -> str:
    """Formate le glossaire en bloc texte injectable dans un prompt.

    Args:
        glossary: Termes du glossaire.

    Returns:
        Une ligne ``- terme (acronyme) : définition`` par terme ; ``""`` si vide.
    """
    lines: list[str] = []
    for term in glossary:
        head = f"{term.term} ({term.acronym})" if term.acronym else term.term
        lines.append(f"- {head} : {term.definition}")
    return "\n".join(lines)
