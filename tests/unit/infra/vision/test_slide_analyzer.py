"""Tests de la façade SlideAnalyzer (extraction stub + vision fake)."""

from pathlib import Path

from PIL import Image

from fahmi2.domain.enums import Language
from fahmi2.infra.video.frame_extractor import (
    SlideExtractionResult,
    SlideFrame,
    SlideFrameExtractor,
)
from fahmi2.infra.vision._fakes import FakeVisionProvider
from fahmi2.infra.vision.slide_analyzer import SlideAnalyzer


class _StubFrameExtractor(SlideFrameExtractor):
    """Renvoie des frames pré-écrites sans appeler ffmpeg."""

    def __init__(self, dropped: int = 0) -> None:
        super().__init__(ffmpeg_binary="inutilise")
        self._dropped = dropped

    def extract(
        self, video_path: Path, frames_dir: Path, *, duration_seconds: float
    ) -> SlideExtractionResult:
        del video_path, duration_seconds
        frames_dir.mkdir(parents=True, exist_ok=True)
        paths = []
        for i in range(3):
            p = frames_dir / f"{i:06d}.jpg"
            Image.new("RGB", (32, 32), (i * 40, 0, 0)).save(p)
            paths.append(p)
        return SlideExtractionResult(
            frames=(
                SlideFrame(0.0, 10.0, paths[0]),
                SlideFrame(10.0, 20.0, paths[1]),
                SlideFrame(20.0, 30.0, paths[2]),
            ),
            dropped_groups=self._dropped,
        )


def _analyzer(*, dropped: int = 0) -> tuple[SlideAnalyzer, FakeVisionProvider]:
    provider = FakeVisionProvider(cost_per_call_usd=0.002)
    analyzer = SlideAnalyzer(
        frame_extractor=_StubFrameExtractor(dropped=dropped),
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
