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
    """Une puce (1 tuile) apparaît à chaque frame sur une slide dont la zone
    dynamique est réaliste (20 tuiles) : 1 groupe, repr = dernière frame."""
    # La zone dynamique est établie par une transition initiale large
    # (slide de titre → slide de contenu), puis les puces 1..4 apparaissent.
    zone = set(range(20))
    samples = [_sample(2.0 * i, set()) for i in range(3)]  # titre (3 échant.)
    samples.append(_sample(6.0, zone))
    samples += [_sample(8.0 + 2.0 * i, zone | set(range(20, 21 + i))) for i in range(4)]
    result = group_slides(samples, duration_seconds=16.0)
    # 2 groupes : la slide de titre, puis la slide de contenu dévoilée
    # progressivement (les puces ne créent pas de nouveaux groupes).
    assert len(result.groups) == 2
    assert result.groups[1].representative_index == len(samples) - 1


def test_changement_de_slide_a_gabarit_partage_detecte() -> None:
    """Deux slides partageant bandeau/pied (le changement ne bascule que ~40 %
    de la zone dynamique) : détecté comme nouvelle slide (cas réel mesuré à
    0.29–0.49 sur corpus, raté avec l'ancien seuil 0.55)."""
    zone = set(range(30))  # zone dynamique établie
    slide_a = zone
    slide_b = set(range(12))  # 12/30 = 0.40 de la zone changent
    samples = [_sample(2.0 * i, slide_a if i < 4 else slide_a ^ slide_b) for i in range(8)]
    result = group_slides(samples, duration_seconds=16.0)
    assert len(result.groups) == 2


def test_fondu_de_transition_coalesce() -> None:
    """Un changement de slide étalé sur 2 échantillons (frame de fondu
    intermédiaire) ne crée pas de micro-groupe « mi-transition »."""
    zone = set(range(30))
    fade = set(range(15))  # état intermédiaire du fondu
    samples = [_sample(2.0 * i, set()) for i in range(4)]
    samples.append(_sample(8.0, fade))  # fondu (crossing 1)
    samples += [_sample(10.0 + 2.0 * i, zone) for i in range(4)]  # slide B (crossing 2)
    result = group_slides(samples, duration_seconds=18.0)
    assert len(result.groups) == 2
    first, second = result.groups
    # Le micro-groupe du fondu (8.0 → 10.0) est absorbé par la slide suivante.
    assert second.start_seconds == 8.0
    assert second.representative_index == len(samples) - 1


def test_slide_reaffichee_non_reanalysee() -> None:
    """Une slide ré-affichée plus tard (A → B → A) n'est pas ré-analysée : le
    groupe dupliqué est retiré (contenu déjà présent dans la transcription)."""
    slide_a = set(range(30))
    slide_b = set(range(30, 45))
    samples = [_sample(2.0 * i, slide_a) for i in range(4)]
    samples += [_sample(8.0 + 2.0 * i, slide_b) for i in range(4)]
    samples += [_sample(16.0 + 2.0 * i, slide_a) for i in range(4)]
    result = group_slides(samples, duration_seconds=24.0)
    reprs = [g.representative_index for g in result.groups]
    assert len(result.groups) == 2
    # Les représentatives conservées : slide A (1re plage) et slide B.
    assert reprs[0] <= 3
    assert 4 <= reprs[1] <= 7


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
    """Détection instable (slide distincte toutes les 6 s) : plafond appliqué.

    Chaque bloc de 3 frames porte un contenu **unique** (hash déterministe
    pairwise distant → ni bruit, ni ré-affichage) sur une zone fixe — c'est
    bien la passe de plafonnement qui borne le coût.
    """
    import hashlib  # noqa: PLC0415

    zone = range(20)
    samples = []
    for i in range(240):
        block = i // 3
        value = int.from_bytes(
            hashlib.sha256(str(block).encode()).digest()[:8], "big"
        )
        hashes = [value if t in zone else _A for t in range(_N_TILES)]
        samples.append(FrameSample(time_seconds=2.0 * i, tile_hashes=tuple(hashes)))
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
