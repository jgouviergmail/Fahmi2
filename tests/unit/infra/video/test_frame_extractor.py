"""Tests de l'extracteur de frames (échantillonnage ffmpeg simulé)."""

from pathlib import Path

from PIL import Image

from fahmi2.infra.video.frame_extractor import SlideFrameExtractor


class _StubExtractor(SlideFrameExtractor):
    """Remplace l'appel ffmpeg par l'écriture de frames synthétiques."""

    def __init__(self, frames: list[Image.Image]) -> None:
        super().__init__(ffmpeg_binary="ffmpeg-inutilise")
        self._frames = frames

    def _sample_frames(self, video_path: Path, frames_dir: Path) -> None:
        del video_path
        for i, img in enumerate(self._frames, start=1):
            img.save(frames_dir / f"{i:06d}.jpg")


def _vertical_stripes() -> Image.Image:
    """Rayures verticales : gradients horizontaux marqués (dHash non nul)."""
    img = Image.new("L", (320, 180), 255)
    for x0 in range(0, 320, 40):
        img.paste(0, (x0, 0, x0 + 20, 180))
    return img.convert("RGB")


def _horizontal_stripes() -> Image.Image:
    """Rayures horizontales : lignes uniformes (dHash très différent)."""
    img = Image.new("L", (320, 180), 255)
    for y0 in range(0, 180, 40):
        img.paste(0, (0, y0, 320, y0 + 20))
    return img.convert("RGB")


def test_extract_deux_slides(tmp_path: Path) -> None:
    """5 frames « slide A » puis 5 « slide B » : 2 slides détectées."""
    frames = [_vertical_stripes()] * 5 + [_horizontal_stripes()] * 5
    extractor = _StubExtractor(frames)
    result = extractor.extract(
        tmp_path / "video.mp4", tmp_path / "frames", duration_seconds=20.0
    )
    assert len(result.frames) == 2
    first, second = result.frames
    assert first.start_seconds == 0.0
    assert second.end_seconds == 20.0
    assert first.image_path.exists()
    assert second.image_path.exists()


def test_extract_aucune_frame(tmp_path: Path) -> None:
    """ffmpeg n'a rien produit (vidéo sans piste vidéo) : résultat vide."""
    extractor = _StubExtractor([])
    result = extractor.extract(
        tmp_path / "video.mp4", tmp_path / "frames", duration_seconds=20.0
    )
    assert result.frames == ()
    assert result.dropped_groups == 0


def test_extract_duree_audio_plus_courte_que_la_video(tmp_path: Path) -> None:
    """Piste audio (durée STT) plus courte que la vidéo : les plages restent
    croissantes (bornées par la couverture réelle des échantillons)."""
    frames = [_vertical_stripes()] * 5 + [_horizontal_stripes()] * 5
    extractor = _StubExtractor(frames)
    result = extractor.extract(
        tmp_path / "video.mp4", tmp_path / "frames", duration_seconds=4.0
    )
    assert len(result.frames) == 2
    for frame in result.frames:
        assert frame.end_seconds >= frame.start_seconds
    assert result.frames[-1].end_seconds == 10 * 2.0  # couverture des frames


def test_commande_ffmpeg_borne_les_deux_axes(tmp_path: Path) -> None:
    """Le filtre d'échelle borne largeur ET hauteur (vidéos portrait incluses)."""
    from fahmi2.infra.video.frame_extractor import (  # noqa: PLC0415
        build_sampling_command,
    )

    cmd = build_sampling_command("ffmpeg", tmp_path / "v.mp4", tmp_path / "frames")
    vf = cmd[cmd.index("-vf") + 1]
    assert "min(1280,iw)" in vf
    assert "min(1280,ih)" in vf
    assert "force_original_aspect_ratio=decrease" in vf
