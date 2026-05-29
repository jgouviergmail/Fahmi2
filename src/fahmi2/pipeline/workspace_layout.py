"""Source unique des chemins du workspace de la Génération.

Centralise les noms des sous-dossiers et fichiers produits par le pipeline
sous ``<workspace>/generation/`` :

- transcriptions brutes (phase 0) ;
- candidats du glossaire par source (phase 1) ;
- glossaire master réconcilié (phase 2) ;
- contenu reformulé par source (phase 3) ;
- contenu structuré par source (phase 4) ;
- document consolidé en langue source (phase 5).

Ces constantes étaient historiquement dupliquées dans 5+ modules (handlers
de phase, ``pedagogy/sources``, ``chat/corpus``). Un seul module garantit
la cohérence — renommer un artefact se fait ici, pas dans 5 endroits.

Module **pur Python sans dépendance** (ni Qt, ni HTTP, ni SQL) pour pouvoir
être importé partout (handlers, pédagogie, dialogue, app, tests).
"""

from __future__ import annotations

from pathlib import Path

#: Sous-dossier des transcriptions brutes (phase 0).
TRANSCRIPTS_SUBDIR = "transcripts"
#: Sous-dossier des candidats du glossaire (phase 1).
CANDIDATES_SUBDIR = "candidates"
#: Sous-dossier des documents reformulés (phase 3).
REFORMULATED_SUBDIR = "reformulated"
#: Sous-dossier des documents structurés (phase 4).
STRUCTURED_SUBDIR = "structured"
#: Sous-dossier des livrables per-source par langue dans ``output_dir`` (phase 6).
PER_SOURCE_OUTPUT_SUBDIR = "per-video"

#: Nom de fichier du glossaire master réconcilié (phase 2).
GLOSSARY_MASTER_FILENAME = "glossary_master.json"
#: Nom de fichier du document consolidé en langue source (phase 5).
CONSOLIDATED_MASTER_FILENAME = "consolidated_master.md"

#: Extension des transcriptions et candidats (JSON).
_JSON_EXTENSION = ".json"
#: Extension des documents Markdown.
_MD_EXTENSION = ".md"


def transcript_path(workspace: Path, source_id: str) -> Path:
    """Chemin de la transcription brute d'une source (phase 0).

    Args:
        workspace: Dossier de travail du run.
        source_id: Identifiant ULID de la source.

    Returns:
        ``<workspace>/transcripts/<source_id>.json``.
    """
    return workspace / TRANSCRIPTS_SUBDIR / f"{source_id}{_JSON_EXTENSION}"


def candidates_path(workspace: Path, source_id: str) -> Path:
    """Chemin des candidats du glossaire d'une source (phase 1).

    Args:
        workspace: Dossier de travail du run.
        source_id: Identifiant ULID de la source.

    Returns:
        ``<workspace>/candidates/<source_id>.json``.
    """
    return workspace / CANDIDATES_SUBDIR / f"{source_id}{_JSON_EXTENSION}"


def reformulated_path(workspace: Path, source_id: str) -> Path:
    """Chemin du Markdown reformulé d'une source (phase 3).

    Args:
        workspace: Dossier de travail du run.
        source_id: Identifiant ULID de la source.

    Returns:
        ``<workspace>/reformulated/<source_id>.md``.
    """
    return workspace / REFORMULATED_SUBDIR / f"{source_id}{_MD_EXTENSION}"


def structured_path(workspace: Path, source_id: str) -> Path:
    """Chemin du Markdown structuré d'une source (phase 4).

    Args:
        workspace: Dossier de travail du run.
        source_id: Identifiant ULID de la source.

    Returns:
        ``<workspace>/structured/<source_id>.md``.
    """
    return workspace / STRUCTURED_SUBDIR / f"{source_id}{_MD_EXTENSION}"


def glossary_master_path(workspace: Path) -> Path:
    """Chemin du glossaire master (phase 2).

    Args:
        workspace: Dossier de travail du run.

    Returns:
        ``<workspace>/glossary_master.json``.
    """
    return workspace / GLOSSARY_MASTER_FILENAME


def consolidated_master_path(workspace: Path) -> Path:
    """Chemin du document consolidé en langue source (phase 5).

    Args:
        workspace: Dossier de travail du run.

    Returns:
        ``<workspace>/consolidated_master.md``.
    """
    return workspace / CONSOLIDATED_MASTER_FILENAME
