"""Tests de la façade SlideAnalyzer (extraction fake + vision fake)."""

from pathlib import Path

from fahmi2.domain.enums import Language
from fahmi2.infra.video._fakes import FakeSlideFrameExtractor
from fahmi2.infra.vision._fakes import FakeVisionProvider
from fahmi2.infra.vision.slide_analyzer import SlideAnalyzer


def _analyzer(*, dropped: int = 0) -> tuple[SlideAnalyzer, FakeVisionProvider]:
    provider = FakeVisionProvider(cost_per_call_usd=0.002)
    analyzer = SlideAnalyzer(
        frame_extractor=FakeSlideFrameExtractor(
            slide_count=3, dropped_groups=dropped
        ),
        vision_provider=provider,
        llm_workers=2,
    )
    return analyzer, provider


def test_analyze_produit_slides_horodatees_et_cout(tmp_path: Path) -> None:
    analyzer, provider = _analyzer()
    report = analyzer.analyze(
        tmp_path / "v.mp4",
        "src-1",
        workspace=tmp_path,
        language=Language.FR,
        duration_seconds=30.0,
    )
    assert len(report.slides) == 3
    assert report.slides[0].start_seconds == 0.0
    assert report.slides[2].end_seconds == 30.0
    assert report.cost_usd == 3 * 0.002
    assert len(provider.calls) == 3
    assert analyzer.consumed_cost_usd_for("src-1") == report.cost_usd
    assert analyzer.consumed_cost_usd_for("inconnu") == 0.0


def test_analyze_nettoie_les_frames(tmp_path: Path) -> None:
    analyzer, _ = _analyzer()
    analyzer.analyze(
        tmp_path / "v.mp4",
        "src-1",
        workspace=tmp_path,
        language=Language.FR,
        duration_seconds=30.0,
    )
    assert not (tmp_path / "frames" / "src-1").exists()


def test_analyses_paralleles_bornees_globalement(tmp_path: Path) -> None:
    """Deux analyze() concurrents : la concurrence vision réelle reste bornée
    par llm_workers (sémaphore global), pas par sources × llm_workers."""
    import threading  # noqa: PLC0415

    from fahmi2.infra.vision.interface import (  # noqa: PLC0415
        SlideAnalysis,
        SlideContent,
    )

    lock = threading.Lock()
    state = {"current": 0, "max": 0}

    class _CountingProvider:
        def analyze_slide(self, image_path: Path, *, language: Language) -> SlideAnalysis:
            del image_path, language
            with lock:
                state["current"] += 1
                state["max"] = max(state["max"], state["current"])
            # Laisse le temps aux appels concurrents de se chevaucher.
            threading.Event().wait(0.02)
            with lock:
                state["current"] -= 1
            return SlideAnalysis(
                content=SlideContent(text="x", visuals_description=""),
                cost_usd=0.0,
            )

    analyzer = SlideAnalyzer(
        frame_extractor=FakeSlideFrameExtractor(slide_count=6),
        vision_provider=_CountingProvider(),
        llm_workers=2,
    )

    def _run(source_id: str) -> None:
        analyzer.analyze(
            tmp_path / f"{source_id}.mp4",
            source_id,
            workspace=tmp_path / source_id,
            language=Language.FR,
            duration_seconds=60.0,
        )

    threads = [
        threading.Thread(target=_run, args=(f"src-{i}",)) for i in range(3)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert state["max"] <= 2  # borné par llm_workers, pas 3 × 2


def test_analyze_expose_les_groupes_ignores(tmp_path: Path) -> None:
    analyzer, _ = _analyzer(dropped=7)
    report = analyzer.analyze(
        tmp_path / "v.mp4",
        "src-1",
        workspace=tmp_path,
        language=Language.FR,
        duration_seconds=30.0,
    )
    assert report.dropped_groups == 7
    assert analyzer.dropped_groups_for("src-1") == 7
    assert analyzer.dropped_groups_for("inconnu") == 0
