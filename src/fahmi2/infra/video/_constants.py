"""Constantes du sous-système d'extraction de slides.

Tous les nombres magiques de la détection sont centralisés ici (directive
n° 1) : ajustables sans toucher à la logique — c'est le levier de correction
prévu pour les vidéos atypiques (cf. spec, « risque résiduel assumé »).
"""

#: Intervalle d'échantillonnage des frames (secondes).
SAMPLE_INTERVAL_SECONDS = 2.0
#: Côté maximal des frames extraites (px) — lisibilité des slides vs tokens image.
MAX_FRAME_DIMENSION_PX = 1280
#: Qualité JPEG des frames extraites (échelle ffmpeg ``-q:v``, 2-5 = très bonne).
FFMPEG_JPEG_QUALITY = 3
#: Taille de la grille de tuiles (N × N) du hachage perceptuel localisé.
TILE_GRID_SIZE = 8
#: Taille du dHash par tuile (le hash porte ``taille²`` bits).
TILE_HASH_SIZE = 8
#: Distance de Hamming minimale pour considérer une tuile comme « changée ».
TILE_CHANGED_MIN_BITS = 6
#: Fraction des transitions au-delà de laquelle une tuile est jugée bruyante
#: (webcam incrustée, vidéo dans la slide) et exclue de la mesure.
NOISY_TILE_CHANGE_RATIO = 0.5
#: Sous cette fraction de la région dynamique : image identique.
F_LOW = 0.05
#: Au-delà de cette fraction de la région dynamique : nouvelle slide.
#: Entre les deux : même slide en dévoilement progressif.
F_HIGH = 0.55
#: Plafond de slides analysées par minute de vidéo (garde-fou de coût).
MAX_SLIDES_PER_MINUTE = 4.0
#: Plancher du plafond proratisé : une vidéo courte peut quand même contenir
#: plusieurs slides (le coût reste négligeable à cette échelle).
MIN_SLIDES_FLOOR = 10
#: Plafond absolu de slides analysées par vidéo.
MAX_SLIDES_ABSOLUTE = 300
#: Durée maximale (s) d'un groupe « flash » transitoire : un groupe plus
#: court, encadré par deux slides quasi identiques, est absorbé (artefact de
#: transition, pas une vraie slide).
FLASH_GROUP_MAX_SECONDS = 3.0
#: Fraction maximale de région dynamique différente entre les représentantes
#: de deux slides consécutives pour les fusionner (re-détection parasite).
INTER_SLIDE_DEDUP_MAX_RATIO = 0.05
