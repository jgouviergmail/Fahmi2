"""Diagnostic de la détection de slides sur une vidéo réelle (sans appel vision).

Rejoue l'échantillonnage ffmpeg + le hachage par tuiles + les passes de
regroupement sur une vidéo, puis imprime :

1. la taille du masque de bruit et de la zone dynamique (passe 1) ;
2. chaque transition et sa fraction de zone dynamique (matière première du
   seuil ``F_HIGH``) ;
3. la chronologie finale des slides détectées (toutes passes : coalescence
   des fondus, dédoublonnage des ré-affichages, plafonds).

Usage :

    python scripts/diagnose_slide_detection.py <video> [dossier_frames]

Le dossier de frames par défaut est créé à côté du script ; s'il contient
déjà des frames, l'échantillonnage ffmpeg n'est pas relancé (itération rapide
sur les seuils de ``infra/video/_constants.py``).
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from PIL import Image

from fahmi2.infra.ingestion.slide_merge import format_timestamp
from fahmi2.infra.video._constants import NOISY_TILE_CHANGE_RATIO
from fahmi2.infra.video.frame_extractor import SlideFrameExtractor
from fahmi2.infra.video.tiles import changed_tiles, tile_dhashes

#: Fraction minimale affichée dans le relevé des transitions (le bruit de
#: fond < 5 % n'apporte rien au diagnostic).
_REPORT_MIN_FRACTION = 0.05
#: Nombre minimal d'arguments CLI (script + vidéo).
_MIN_ARGC = 2


class _ReusingExtractor(SlideFrameExtractor):
    """Réutilise les frames déjà échantillonnées (itération sur les seuils)."""

    def _sample_frames(self, video_path: Path, frames_dir: Path) -> None:
        if any(frames_dir.glob("*.jpg")):
            return
        super()._sample_frames(video_path, frames_dir)


def _report_transitions(frames_dir: Path) -> None:
    """Imprime la fraction de zone dynamique de chaque transition.

    Args:
        frames_dir: Dossier des frames échantillonnées.
    """
    paths = sorted(frames_dir.glob("*.jpg"))
    print(f"frames échantillonnées : {len(paths)}")
    samples = []
    for path in paths:
        with Image.open(path) as image:
            samples.append(tile_dhashes(image))
    n_tiles = len(samples[0])
    transitions = [
        changed_tiles(samples[i - 1], samples[i]) for i in range(1, len(samples))
    ]
    counts = [0] * n_tiles
    for changes in transitions:
        for tile, changed in enumerate(changes):
            if changed:
                counts[tile] += 1
    noisy = [
        counts[t] / len(transitions) >= NOISY_TILE_CHANGE_RATIO
        for t in range(n_tiles)
    ]
    dynamic = [counts[t] > 0 and not noisy[t] for t in range(n_tiles)]
    dynamic_count = sum(dynamic)
    print(
        f"tuiles bruyantes : {sum(noisy)} | dynamiques : {dynamic_count}"
        f" / {n_tiles}"
    )
    print(f"--- transitions >= {_REPORT_MIN_FRACTION:.2f} (mm:ss  fraction) ---")
    for i, changes in enumerate(transitions, start=1):
        fraction = (
            sum(1 for t in range(n_tiles) if changes[t] and dynamic[t])
            / dynamic_count
        )
        if fraction >= _REPORT_MIN_FRACTION:
            print(f"{format_timestamp(i * 2.0)}  {fraction:.2f}")


def main() -> None:
    """Point d'entrée du diagnostic."""
    if len(sys.argv) < _MIN_ARGC:
        print(__doc__)
        raise SystemExit(1)
    video = Path(sys.argv[1])
    frames_dir = (
        Path(sys.argv[_MIN_ARGC])
        if len(sys.argv) > _MIN_ARGC
        else Path(tempfile.gettempdir()) / "fahmi2_diag_slides" / video.stem
    )
    frames_dir.mkdir(parents=True, exist_ok=True)

    extractor = _ReusingExtractor()
    result = extractor.extract(video, frames_dir, duration_seconds=0.0)
    _report_transitions(frames_dir)
    print("--- chronologie des slides détectées (toutes passes) ---")
    print(
        f"slides : {len(result.frames)}"
        f" (ignorées par plafonds : {result.dropped_groups})"
    )
    for i, frame in enumerate(result.frames, start=1):
        print(
            f"{i:02d}. {format_timestamp(frame.start_seconds)} -> "
            f"{format_timestamp(frame.end_seconds)}"
        )


if __name__ == "__main__":
    main()
