"""Hachage perceptuel par tuiles (dHash) d'une frame vidéo.

Un dHash *global* dilue un changement de slide fenêtrée ; la frame est donc
découpée en grille de tuiles, chacune hachée indépendamment. Les fonctions
sont pures (Pillow uniquement, aucun I/O).
"""

from __future__ import annotations

from PIL import Image

from fahmi2.infra.video._constants import (
    TILE_CHANGED_MIN_BITS,
    TILE_GRID_SIZE,
    TILE_HASH_SIZE,
)


def tile_dhashes(
    image: Image.Image,
    *,
    grid_size: int = TILE_GRID_SIZE,
    hash_size: int = TILE_HASH_SIZE,
) -> tuple[int, ...]:
    """Calcule le dHash de chaque tuile d'une grille ``grid_size × grid_size``.

    Args:
        image: Frame à hacher (tout mode Pillow ; convertie en niveaux de gris).
        grid_size: Nombre de tuiles par côté.
        hash_size: Côté du dHash (le hash d'une tuile porte ``hash_size²`` bits).

    Returns:
        Un entier de hash par tuile, ordre ligne par ligne.
    """
    gray = image.convert("L")
    width, height = gray.size
    hashes: list[int] = []
    for row in range(grid_size):
        for col in range(grid_size):
            box = (
                col * width // grid_size,
                row * height // grid_size,
                (col + 1) * width // grid_size,
                (row + 1) * height // grid_size,
            )
            tile = gray.crop(box).resize(
                (hash_size + 1, hash_size), Image.Resampling.LANCZOS
            )
            # ``tobytes`` sur un mode « L » = pixels aplatis ligne par ligne
            # (évite ``getdata``, déprécié par Pillow 12+).
            pixels = tile.tobytes()
            bits = 0
            for y in range(hash_size):
                for x in range(hash_size):
                    left = pixels[y * (hash_size + 1) + x]
                    right = pixels[y * (hash_size + 1) + x + 1]
                    bits = (bits << 1) | (1 if left > right else 0)
            hashes.append(bits)
    return tuple(hashes)


def hamming_distance(a: int, b: int) -> int:
    """Distance de Hamming entre deux hashes.

    Args:
        a: Premier hash.
        b: Second hash.

    Returns:
        Le nombre de bits différents.
    """
    return (a ^ b).bit_count()


def changed_tiles(
    previous: tuple[int, ...],
    current: tuple[int, ...],
    *,
    min_bits: int = TILE_CHANGED_MIN_BITS,
) -> tuple[bool, ...]:
    """Marque les tuiles ayant significativement changé entre deux frames.

    Args:
        previous: Hashes par tuile de la frame précédente.
        current: Hashes par tuile de la frame courante (même taille).
        min_bits: Distance de Hamming minimale pour marquer un changement.

    Returns:
        Un booléen par tuile (``True`` = changée).
    """
    return tuple(
        hamming_distance(p, c) >= min_bits
        for p, c in zip(previous, current, strict=True)
    )
