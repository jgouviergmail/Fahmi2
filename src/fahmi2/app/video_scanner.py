"""Scanner de vidéos dans un dossier d'entrée.

Identifie les fichiers vidéo supportés (extensions configurées) et produit
les ``SourceExecution`` initiaux pour un ``Run``.

Le tri d'entrée est **naturel** : on extrait le premier token purement
numérique du nom (après suppression de l'extension et découpage sur les
séparateurs usuels ``[\\s\\-_]+``), ce qui permet de gérer correctement
des nommages préfixés du type ``V.1 - 1 - Intro.mp4`` ou ``doc 01 - X.mp4``.
"""

from __future__ import annotations

import math
import re
from pathlib import Path

from fahmi2.core.errors.exceptions import ConfigError, StorageError
from fahmi2.core.errors.severity import Severity
from fahmi2.domain.enums import SourceKind
from fahmi2.domain.ids import SourceId
from fahmi2.domain.source import InputSource, SourceExecution

_SUPPORTED_EXTENSIONS: frozenset[str] = frozenset(
    {".mp4", ".m4v", ".mkv", ".mov", ".webm"}
)

_TOKEN_SPLIT_RE = re.compile(r"[\s\-_]+")


def supported_extensions() -> frozenset[str]:
    """Retourne le set des extensions vidéo supportées.

    Returns:
        Set immuable d'extensions (en minuscules, avec ``.`` initial).
    """
    return _SUPPORTED_EXTENSIONS


def scan_input_folder(input_folder: Path) -> list[SourceExecution]:
    """Liste les vidéos supportées dans ``input_folder``.

    Args:
        input_folder: Dossier à scanner.

    Returns:
        Liste des ``SourceExecution`` initiaux (status PENDING implicite),
        triés par nom de fichier.

    Raises:
        StorageError: Si ``input_folder`` est inaccessible.
        ConfigError: Si aucun fichier vidéo supporté n'est trouvé.
    """
    if not input_folder.exists() or not input_folder.is_dir():
        raise StorageError(
            code="STORAGE.READ_DENIED",
            user_message=(
                f"Le dossier d'entrée est introuvable ou inaccessible : {input_folder}"
            ),
            severity=Severity.ERROR,
            technical_details={"input_folder": str(input_folder)},
        )

    candidates = sorted(
        (
            p
            for p in input_folder.iterdir()
            if p.is_file() and p.suffix.lower() in _SUPPORTED_EXTENSIONS
        ),
        key=_natural_sort_key,
    )

    if not candidates:
        raise ConfigError(
            code="CONFIG.INPUT_FOLDER_EMPTY",
            user_message=(
                "Le dossier d'entrée ne contient aucune vidéo prise en charge "
                f"({', '.join(sorted(_SUPPORTED_EXTENSIONS))})."
            ),
            severity=Severity.ERROR,
            technical_details={
                "input_folder": str(input_folder),
                "supported": sorted(_SUPPORTED_EXTENSIONS),
            },
        )

    return [
        SourceExecution(
            source_id=SourceId.new(),
            source=InputSource(kind=SourceKind.VIDEO, location=str(p)),
        )
        for p in candidates
    ]


def _natural_sort_key(path: Path) -> tuple[float, str]:
    """Construit une clé de tri naturel à partir du nom de fichier.

    L'algorithme :

    1. Retire l'extension.
    2. Découpe le nom sur les séparateurs ``[\\s\\-_]+`` (espaces,
       tirets, underscores).
    3. Cherche le **premier token purement numérique**. C'est typiquement
       le numéro de séquence, ce qui permet d'ignorer un éventuel
       préfixe descriptif comme ``V.1`` (les points ne sont pas des
       séparateurs, donc ``V.1`` reste un token non-numérique).
    4. Si trouvé, retourne ``(int(token), nom_complet_casefold)``.
    5. Sinon, retourne ``(+∞, nom_complet_casefold)`` pour rejeter en
       fin de liste les fichiers sans préfixe numérique, en conservant
       un ordre alphabétique stable entre eux.

    Exemples de comportement :

    - ``"V.1 - 1 - Intro.mp4"``  → ``(1, …)``
    - ``"V.1 - 10 - Conclusion.mp4"`` → ``(10, …)``
    - ``"V.i - 01 - X.mp4"`` → ``(1, …)``
    - ``"doc 1 partie 2.mp4"`` → ``(1, …)`` (premier token numérique)
    - ``"intro.mp4"`` → ``(+∞, …)``

    Args:
        path: Chemin du fichier.

    Returns:
        Tuple ``(numero_extrait, nom_normalise)`` utilisable comme clé
        de ``sorted()``.
    """
    base = path.stem
    tokens = _TOKEN_SPLIT_RE.split(base)
    for token in tokens:
        if token.isdigit():
            return (float(int(token)), base.casefold())
    return (math.inf, base.casefold())
