"""Tests des libellés pédagogie."""

from __future__ import annotations

from fahmi2.domain.enums import (
    BloomObjective,
    Language,
    SupportDensity,
    TargetAudience,
)
from fahmi2.domain.glossary import Term
from fahmi2.pedagogy.labels import (
    audience_label,
    bloom_label,
    density_label,
    format_glossary_terms,
    language_label,
)


def test_labels_are_french() -> None:
    assert language_label(Language.FR) == "français"
    assert audience_label(TargetAudience.LICENCE)
    assert bloom_label(BloomObjective.AUTO)
    assert density_label(SupportDensity.STANDARD)


def test_all_enum_members_have_labels() -> None:
    for audience in TargetAudience:
        assert audience_label(audience)
    for bloom in BloomObjective:
        assert bloom_label(bloom)
    for density in SupportDensity:
        assert density_label(density)
    for language in Language:
        assert language_label(language)


def test_format_glossary_terms() -> None:
    text = format_glossary_terms(
        (Term(term="PIB", definition="Produit intérieur brut", acronym="PIB"),)
    )
    assert "PIB" in text
    assert "Produit intérieur brut" in text


def test_format_glossary_terms_empty() -> None:
    assert format_glossary_terms(()) == ""
