"""Tests du générateur de flashcards glossaire (sans LLM)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fahmi2.core.retry.policy import RetryPolicy
from fahmi2.domain.enums import Language, SupportType
from fahmi2.domain.glossary import Term
from fahmi2.domain.supports import Flashcard
from fahmi2.infra.llm._fakes import FakeLLMProvider
from fahmi2.infra.prompts.loader import PromptLoader
from fahmi2.infra.storage.fs_artifacts import FsArtifactStore
from fahmi2.pedagogy.events import PedagogyEvent
from fahmi2.pedagogy.generators.flashcards_glossary import FlashcardsGlossaryGenerator
from fahmi2.pedagogy.support_generator import SupportContext
from fahmi2.pipeline.event_bus import EventBus
from fahmi2.pipeline.pause_token import PauseToken


def _ctx(tmp_path: Path, make_pedagogy_settings: Any) -> SupportContext:
    return SupportContext(
        pedagogy=make_pedagogy_settings(),
        generation_output_dir=tmp_path / "generation" / "output",
        pedagogy_dir=tmp_path / "pedagogy",
        llm_provider=FakeLLMProvider(),
        prompts=PromptLoader(),
        artifacts=FsArtifactStore(),
        event_bus=EventBus[PedagogyEvent](),
        pause_token=PauseToken(),
        retry_policy=RetryPolicy(jitter=False),
    )


def test_generates_one_card_per_term(
    tmp_path: Path, make_pedagogy_settings: Any
) -> None:
    gen = FlashcardsGlossaryGenerator()
    glossary = (
        Term(
            term="Produit intérieur brut",
            definition="Somme des valeurs ajoutées",
            acronym="PIB",
        ),
        Term(term="Inflation", definition="Hausse générale des prix"),
    )
    artifact = gen.generate(
        _ctx(tmp_path, make_pedagogy_settings),
        language=Language.FR,
        chapters=(),
        glossary=glossary,
    )
    assert gen.support_type is SupportType.FLASHCARDS_GLOSSARY
    assert gen.uses_llm is False
    assert len(artifact.items) == 2
    first, second = artifact.items
    assert isinstance(first, Flashcard)
    assert isinstance(second, Flashcard)
    assert first.front == "Produit intérieur brut (PIB)"
    assert first.back == "Somme des valeurs ajoutées"
    assert second.front == "Inflation"
    assert artifact.cost_usd == 0.0
    assert "Produit intérieur brut" in artifact.rendered_markdown


def test_empty_glossary_yields_empty_deck(
    tmp_path: Path, make_pedagogy_settings: Any
) -> None:
    artifact = FlashcardsGlossaryGenerator().generate(
        _ctx(tmp_path, make_pedagogy_settings),
        language=Language.FR,
        chapters=(),
        glossary=(),
    )
    assert artifact.items == ()
