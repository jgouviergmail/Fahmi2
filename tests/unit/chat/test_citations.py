"""Tests du parsing des citations [§N]."""

from __future__ import annotations

from fahmi2.chat.citations import parse_citations
from fahmi2.domain.chat import CorpusChunk, RetrievedPassage


def _passage(idx: int) -> RetrievedPassage:
    chunk = CorpusChunk(
        chunk_id=f"c::{idx}",
        chapter_title=f"Chap {idx}",
        section_title=f"Sec {idx}",
        anchor=f"a{idx}",
        text=f"Texte du passage {idx} avec du contenu.",
        origin="consolidated",
    )
    return RetrievedPassage(chunk=chunk, score=1.0)


def test_parse_citations_maps_indices() -> None:
    passages = (_passage(1), _passage(2))
    citations = parse_citations("Le PIB [§1] et l'inflation [§2].", passages)
    assert {c.anchor for c in citations} == {"a1", "a2"}


def test_parse_citations_dedup_and_ignores_out_of_range() -> None:
    passages = (_passage(1),)
    citations = parse_citations("Voir [§1] et encore [§1] et [§9].", passages)
    assert len(citations) == 1
    assert citations[0].anchor == "a1"


def test_parse_citations_none() -> None:
    assert parse_citations("Aucune citation ici.", (_passage(1),)) == ()
