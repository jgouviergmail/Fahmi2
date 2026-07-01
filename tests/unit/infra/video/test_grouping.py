"""Tests du regroupement de frames en slides (tuiles, 2 passes, plafonds)."""

from fahmi2.infra.video._constants import TILE_GRID_SIZE
from fahmi2.infra.video.grouping import FrameSample, group_slides

_N_TILES = TILE_GRID_SIZE * TILE_GRID_SIZE
#: Valeurs de hash « très différentes » (64 bits opposés) pour forcer un
#: changement de tuile, et identiques pour l'absence de changement.
_A = 0
_B = (1 << 64) - 1


def _sample(
    t: float, changed: set[int], base: dict[int, int] | None = None
) -> FrameSample:
    """Frame dont les tuiles de ``changed`` valent ``_B`` (les autres ``_A``)."""
    hashes = [(base or {}).get(i, _A) for i in range(_N_TILES)]
    for i in changed:
        hashes[i] = _B
    return FrameSample(time_seconds=t, tile_hashes=tuple(hashes))


def test_video_statique_donne_une_seule_slide() -> None:
    samples = [_sample(t=2.0 * i, changed=set()) for i in range(10)]
    result = group_slides(samples, duration_seconds=20.0)
    assert len(result.groups) == 1
    assert result.groups[0].start_seconds == 0.0
    assert result.groups[0].end_seconds == 20.0
    assert result.dropped_groups == 0


def test_deux_slides_plein_ecran() -> None:
    """Transition franche à t=10 s : 2 groupes, représentative = état final."""
    all_tiles = set(range(_N_TILES))
    samples = [_sample(2.0 * i, set()) for i in range(5)]
    samples += [_sample(10.0 + 2.0 * i, all_tiles) for i in range(5)]
    result = group_slides(samples, duration_seconds=20.0)
    assert len(result.groups) == 2
    first, second = result.groups
    assert first.start_seconds == 0.0
    assert first.end_seconds == 10.0
    assert second.start_seconds == 10.0
    assert second.end_seconds == 20.0
    assert first.representative_index == 4  # dernière frame avant transition
    assert second.representative_index == 9  # état final de la 2e slide


def test_devoilement_progressif_reste_une_slide() -> None:
    """Une puce (1 tuile) apparaît à chaque frame : 1 groupe, repr = dernière."""
    samples = [_sample(2.0 * i, set(range(i))) for i in range(5)]
    result = group_slides(samples, duration_seconds=10.0)
    assert len(result.groups) == 1
    assert result.groups[0].representative_index == 4


def test_slide_fenetree_petite_fenetre_detectee() -> None:
    """Seules les tuiles 0..7 bougent (fenêtre ~12 %) : le flip complet de la
    fenêtre est bien une nouvelle slide (fraction relative à la région
    dynamique, pas à la frame entière)."""
    window = set(range(8))
    samples = [_sample(2.0 * i, set()) for i in range(5)]
    samples += [_sample(10.0 + 2.0 * i, window) for i in range(5)]
    result = group_slides(samples, duration_seconds=20.0)
    assert len(result.groups) == 2


def test_webcam_bruyante_exclue_du_masque() -> None:
    """Les tuiles 60..63 changent à chaque frame (webcam) : pas de fausses
    slides ; une vraie transition sur les autres tuiles reste détectée."""
    noisy = set(range(60, 64))
    slide_zone = set(range(32))
    samples = []
    for i in range(5):
        samples.append(_sample(2.0 * i, noisy if i % 2 else set()))
    for i in range(5):
        changed = slide_zone | (noisy if i % 2 else set())
        samples.append(_sample(10.0 + 2.0 * i, changed))
    result = group_slides(samples, duration_seconds=20.0)
    assert len(result.groups) == 2


def test_plafond_de_slides() -> None:
    """Détection instable (nouvelle slide toutes les 6 s) : plafond appliqué.

    La bascule toutes les 3 frames (1 changement sur 3 transitions par tuile)
    reste sous le seuil de bruit — c'est bien la passe de plafonnement qui
    borne le coût, pas le masque de bruit.
    """
    all_tiles = set(range(_N_TILES))
    samples = [
        _sample(2.0 * i, all_tiles if (i // 3) % 2 else set()) for i in range(240)
    ]
    result = group_slides(samples, duration_seconds=480.0)  # 8 min → cap 32
    assert result.dropped_groups > 0
    assert len(result.groups) <= 32


def test_tout_change_en_permanence_est_du_bruit() -> None:
    """Caméra/écran entièrement instable : tout est masqué comme bruit → une
    seule slide (état final), pas une cascade de fausses détections."""
    all_tiles = set(range(_N_TILES))
    samples = [
        _sample(2.0 * i, all_tiles if i % 2 else set()) for i in range(20)
    ]
    result = group_slides(samples, duration_seconds=40.0)
    assert len(result.groups) == 1
    assert result.dropped_groups == 0


def test_dedoublonnage_slides_consecutives_identiques() -> None:
    """Flash transitoire (frame unique très différente puis retour) : les deux
    groupes au contenu identique sont fusionnés."""
    all_tiles = set(range(_N_TILES))
    samples = [_sample(2.0 * i, set()) for i in range(4)]
    samples.append(_sample(8.0, all_tiles))  # flash
    samples += [_sample(10.0 + 2.0 * i, set()) for i in range(4)]
    result = group_slides(samples, duration_seconds=18.0)
    # le flash crée au plus un groupe distinct ; les groupes « même contenu »
    # (avant/après) ne sont pas dupliqués
    assert len(result.groups) <= 2
