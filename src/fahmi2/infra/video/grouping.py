"""Regroupement des frames échantillonnées en slides (2 passes, pur).

Passe 1 — cartographie : statistiques de changement par tuile sur toute la
vidéo → masque de bruit temporel (tuiles changeant en permanence : webcam,
vidéo incrustée) et région dynamique (tuiles ayant changé au moins une fois,
hors masque — de fait, la zone de slide). Passe 2 — regroupement : double
seuil sur la **fraction de la région dynamique** changeant simultanément,
insensible au fenêtrage de la slide. Garde-fous : absorption des groupes
« flash » transitoires, fusion des re-détections parasites consécutives, et
plafond de slides (coût borné).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from fahmi2.infra.video._constants import (
    F_HIGH,
    F_LOW,
    FLASH_GROUP_MAX_SECONDS,
    INTER_SLIDE_DEDUP_MAX_RATIO,
    MAX_SLIDES_ABSOLUTE,
    MAX_SLIDES_PER_MINUTE,
    MIN_SLIDES_FLOOR,
    NOISY_TILE_CHANGE_RATIO,
)
from fahmi2.infra.video.tiles import changed_tiles

_SECONDS_PER_MINUTE = 60.0


@dataclass(frozen=True)
class FrameSample:
    """Un échantillon de frame vidéo haché par tuiles.

    Attributes:
        time_seconds: Horodatage de la frame dans la vidéo.
        tile_hashes: dHash de chaque tuile (cf. ``tiles.tile_dhashes``).
    """

    time_seconds: float
    tile_hashes: tuple[int, ...]


@dataclass(frozen=True)
class SlideGroup:
    """Un groupe de frames formant une slide affichée sur une plage temporelle.

    Attributes:
        start_seconds: Début d'affichage.
        end_seconds: Fin d'affichage.
        representative_index: Index (dans les échantillons) de la frame
            représentative — l'état final de la slide.
    """

    start_seconds: float
    end_seconds: float
    representative_index: int


@dataclass(frozen=True)
class SlideGroupingResult:
    """Résultat du regroupement.

    Attributes:
        groups: Slides détectées, ordonnées temporellement.
        dropped_groups: Groupes ignorés par les plafonds (détection instable).
    """

    groups: tuple[SlideGroup, ...]
    dropped_groups: int


def group_slides(
    samples: Sequence[FrameSample], *, duration_seconds: float
) -> SlideGroupingResult:
    """Regroupe les frames échantillonnées en slides (2 passes).

    Args:
        samples: Échantillons ordonnés temporellement.
        duration_seconds: Durée de la vidéo (clôture du dernier groupe et
            calcul du plafond de slides).

    Returns:
        Le ``SlideGroupingResult`` (groupes plafonnés + nombre d'ignorés).
    """
    if not samples:
        return SlideGroupingResult(groups=(), dropped_groups=0)
    if len(samples) == 1:
        only = SlideGroup(
            start_seconds=samples[0].time_seconds,
            end_seconds=duration_seconds,
            representative_index=0,
        )
        return SlideGroupingResult(groups=(only,), dropped_groups=0)

    # Passe 1 — cartographie des changements par tuile.
    n_tiles = len(samples[0].tile_hashes)
    transitions = [
        changed_tiles(samples[i - 1].tile_hashes, samples[i].tile_hashes)
        for i in range(1, len(samples))
    ]
    change_counts = [0] * n_tiles
    for changes in transitions:
        for tile, changed in enumerate(changes):
            if changed:
                change_counts[tile] += 1
    n_transitions = len(transitions)
    noisy = [
        change_counts[tile] / n_transitions >= NOISY_TILE_CHANGE_RATIO
        for tile in range(n_tiles)
    ]
    dynamic = [
        change_counts[tile] > 0 and not noisy[tile] for tile in range(n_tiles)
    ]
    dynamic_count = sum(dynamic)
    if dynamic_count == 0:
        # Vidéo statique (une seule slide affichée en continu) ou 100 % bruit :
        # un seul groupe couvrant toute la vidéo, état final = dernière frame.
        only = SlideGroup(
            start_seconds=samples[0].time_seconds,
            end_seconds=duration_seconds,
            representative_index=len(samples) - 1,
        )
        return SlideGroupingResult(groups=(only,), dropped_groups=0)

    # Passe 2 — regroupement par fraction de la région dynamique.
    groups: list[SlideGroup] = []
    current_start = samples[0].time_seconds
    current_repr = 0
    for i, changes in enumerate(transitions, start=1):
        changed_dynamic = sum(
            1 for tile in range(n_tiles) if changes[tile] and dynamic[tile]
        )
        fraction = changed_dynamic / dynamic_count
        if fraction < F_LOW:
            continue  # image identique
        if fraction < F_HIGH:
            current_repr = i  # même slide, état plus récent (dévoilement)
            continue
        groups.append(
            SlideGroup(
                start_seconds=current_start,
                end_seconds=samples[i].time_seconds,
                representative_index=max(current_repr, i - 1),
            )
        )
        current_start = samples[i].time_seconds
        current_repr = i
    groups.append(
        SlideGroup(
            start_seconds=current_start,
            end_seconds=duration_seconds,
            representative_index=max(current_repr, len(samples) - 1),
        )
    )

    deduped = _merge_parasitic_groups(groups, samples, dynamic, dynamic_count)
    return _apply_caps(deduped, duration_seconds)


def _dynamic_diff_ratio(
    a: SlideGroup,
    b: SlideGroup,
    samples: Sequence[FrameSample],
    dynamic: list[bool],
    dynamic_count: int,
) -> float:
    """Fraction de la région dynamique différant entre deux représentantes.

    Args:
        a: Premier groupe.
        b: Second groupe.
        samples: Échantillons (accès aux hashes des représentantes).
        dynamic: Masque de la région dynamique.
        dynamic_count: Taille de la région dynamique (> 0).

    Returns:
        La fraction dans ``[0, 1]``.
    """
    diff = changed_tiles(
        samples[a.representative_index].tile_hashes,
        samples[b.representative_index].tile_hashes,
    )
    diff_dynamic = sum(
        1 for tile, changed in enumerate(diff) if changed and dynamic[tile]
    )
    return diff_dynamic / dynamic_count


def _merge_parasitic_groups(
    groups: list[SlideGroup],
    samples: Sequence[FrameSample],
    dynamic: list[bool],
    dynamic_count: int,
) -> list[SlideGroup]:
    """Fusionne les re-détections parasites.

    Deux cas : (1) groupe consécutif au contenu quasi identique au précédent
    (double franchissement de seuil pendant une transition animée) ; (2)
    groupe « flash » très court encadré par deux slides quasi identiques
    (artefact de transition) — le flash est absorbé.

    Args:
        groups: Groupes issus de la passe 2.
        samples: Échantillons (accès aux hashes des représentantes).
        dynamic: Masque de la région dynamique.
        dynamic_count: Taille de la région dynamique (> 0).

    Returns:
        Les groupes fusionnés.
    """
    merged: list[SlideGroup] = []
    for group in groups:
        if merged:
            previous = merged[-1]
            if (
                _dynamic_diff_ratio(previous, group, samples, dynamic, dynamic_count)
                <= INTER_SLIDE_DEDUP_MAX_RATIO
            ):
                merged[-1] = SlideGroup(
                    start_seconds=previous.start_seconds,
                    end_seconds=group.end_seconds,
                    representative_index=group.representative_index,
                )
                continue
        if len(merged) >= 2:  # noqa: PLR2004 — fenêtre « flash » de 2 groupes
            flash = merged[-1]
            anchor = merged[-2]
            flash_duration = flash.end_seconds - flash.start_seconds
            if (
                flash_duration <= FLASH_GROUP_MAX_SECONDS
                and _dynamic_diff_ratio(
                    anchor, group, samples, dynamic, dynamic_count
                )
                <= INTER_SLIDE_DEDUP_MAX_RATIO
            ):
                merged.pop()
                merged[-1] = SlideGroup(
                    start_seconds=anchor.start_seconds,
                    end_seconds=group.end_seconds,
                    representative_index=group.representative_index,
                )
                continue
        merged.append(group)
    return merged


def _apply_caps(
    groups: list[SlideGroup], duration_seconds: float
) -> SlideGroupingResult:
    """Applique les plafonds slides/minute et absolu (coût borné).

    Args:
        groups: Groupes dédoublonnés.
        duration_seconds: Durée de la vidéo.

    Returns:
        Le résultat final (groupes conservés + nombre d'ignorés).
    """
    prorated = int(duration_seconds / _SECONDS_PER_MINUTE * MAX_SLIDES_PER_MINUTE)
    cap = min(MAX_SLIDES_ABSOLUTE, max(MIN_SLIDES_FLOOR, prorated))
    dropped = max(0, len(groups) - cap)
    return SlideGroupingResult(groups=tuple(groups[:cap]), dropped_groups=dropped)
