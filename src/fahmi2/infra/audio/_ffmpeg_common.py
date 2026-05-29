"""Constantes partagées entre les adapters ``ffmpeg`` (extraction + préparation).

Source unique pour les noms de binaires (``ffmpeg`` / ``ffprobe`` du PATH par
défaut, surchargeables au constructeur) et la verbosité de log demandée à
ffmpeg. Évite la duplication symétrique entre :class:`FFmpegExtractor` et
:class:`CloudAudioPreparer`.
"""

from __future__ import annotations

#: Nom du binaire ffmpeg cherché dans le PATH (sauf override au constructeur).
DEFAULT_FFMPEG_BINARY = "ffmpeg"
#: Nom du binaire ffprobe cherché dans le PATH (sauf override au constructeur).
DEFAULT_FFPROBE_BINARY = "ffprobe"
#: Niveau de log demandé à ffmpeg/ffprobe (capture stderr propre, sans bruit).
FFMPEG_LOGLEVEL_ERROR = "error"
