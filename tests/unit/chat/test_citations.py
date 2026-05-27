"""Tests de la résolution des citations [§N] → liens numérotés [[K]](ancre)."""

from __future__ import annotations

from fahmi2.chat.citations import resolve_citations
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


def test_resolve_renumbers_sequentially_by_appearance() -> None:
    passages = (_passage(1), _passage(2), _passage(3))
    # Le LLM cite les passages 3 puis 1 → numérotés 1 puis 2 (ordre d'apparition).
    content, citations = resolve_citations("D'abord [§3] puis [§1].", passages)
    assert content == "D'abord [[1]](a3) puis [[2]](a1)."
    assert [c.number for c in citations] == [1, 2]
    assert [c.anchor for c in citations] == ["a3", "a1"]


def test_resolve_dedup_same_anchor_keeps_number() -> None:
    passages = (_passage(1),)
    content, citations = resolve_citations("Voir [§1] et encore [§1].", passages)
    assert content == "Voir [[1]](a1) et encore [[1]](a1)."
    assert len(citations) == 1
    assert citations[0].number == 1


def test_resolve_drops_out_of_range_without_double_space() -> None:
    passages = (_passage(1),)
    content, citations = resolve_citations("Le PIB [§9] augmente.", passages)
    assert content == "Le PIB augmente."  # marqueur + espace adjacente retirés
    assert citations == ()


def test_resolve_marker_at_start_has_no_leading_space() -> None:
    passages = (_passage(1),)
    content, _ = resolve_citations("[§1] ouvre la phrase.", passages)
    assert content == "[[1]](a1) ouvre la phrase."


def test_resolve_no_marker_returns_text_unchanged() -> None:
    content, citations = resolve_citations("Aucune citation ici.", (_passage(1),))
    assert content == "Aucune citation ici."
    assert citations == ()
