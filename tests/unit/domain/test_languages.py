"""Tests de la source unique des libellés de langue."""

from __future__ import annotations

from fahmi2.domain.enums import Language
from fahmi2.domain.languages import language_display_label, language_label


def test_language_label_is_lowercase_for_prompts() -> None:
    assert language_label(Language.FR) == "français"
    assert language_label(Language.ZH) == "chinois"
    assert language_label(Language.AR) == "arabe"


def test_language_display_label_is_capitalized_for_ui() -> None:
    assert language_display_label(Language.EN) == "Anglais"
    assert language_display_label(Language.DE) == "Allemand"


def test_every_language_has_a_label() -> None:
    for lang in Language:
        assert language_label(lang)
        assert language_display_label(lang)[0].isupper()
