"""Construction de la liste des sources d'entrée d'un Run.

Scanne le dossier d'entrée des réglages de génération et produit les
``SourceExecution`` initiaux. Les types de fichiers reconnus sont centralisés
dans ``infra.ingestion.classify`` (vidéo + audio au Lot 1B ; documents au Lot 2).

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
from fahmi2.domain.generation import GenerationSettings
from fahmi2.domain.ids import SourceId
from fahmi2.domain.source import InputSource, SourceExecution
from fahmi2.infra.ingestion.classify import classify_file, supported_file_extensions

_TOKEN_SPLIT_RE = re.compile(r"[\s\-_]+")


def build_input_sources(settings: GenerationSettings) -> list[SourceExecution]:
    """Construit la liste ordonnée des sources d'entrée d'un Run.

    Combine les fichiers reconnus du dossier d'entrée (vidéo/audio/document,
    triés naturellement) et les liens YouTube saisis (ajoutés **après** les
    fichiers, dans l'ordre de saisie).

    Args:
        settings: Réglages de génération (dossier d'entrée + ``youtube_urls``).

    Returns:
        Liste ordonnée des ``SourceExecution`` initiaux (fichiers puis YouTube).

    Raises:
        StorageError: Si le dossier d'entrée est inaccessible **et** qu'aucun
            lien YouTube n'est fourni.
        ConfigError: ``CONFIG.NO_INPUT_SOURCE`` si aucune source au total.
    """
    has_urls = bool(settings.youtube_urls)
    file_sources = _scan_files(settings.input_folder, has_urls=has_urls)
    youtube_sources = [
        SourceExecution(
            source_id=SourceId.new(),
            source=InputSource(kind=SourceKind.YOUTUBE, location=url),
        )
        for url in settings.youtube_urls
    ]
    all_sources = file_sources + youtube_sources
    if not all_sources:
        raise ConfigError(
            code="CONFIG.NO_INPUT_SOURCE",
            user_message=(
                "Aucune source à traiter : le dossier d'entrée ne contient aucun "
                "fichier pris en charge (vidéos, audios, documents) et aucun lien "
                "YouTube n'a été saisi."
            ),
            severity=Severity.ERROR,
            technical_details={
                "input_folder": str(settings.input_folder),
                "supported": sorted(supported_file_extensions()),
            },
        )
    return all_sources


def _scan_files(input_folder: Path, *, has_urls: bool) -> list[SourceExecution]:
    """Scanne les fichiers reconnus du dossier d'entrée, triés naturellement.

    Args:
        input_folder: Dossier à scanner.
        has_urls: ``True`` si des liens YouTube sont par ailleurs fournis (alors
            un dossier inaccessible est toléré : projet YouTube seul).

    Returns:
        Liste des ``SourceExecution`` fichier (vide si dossier absent + ``has_urls``).

    Raises:
        StorageError: ``STORAGE.READ_DENIED`` si le dossier est inaccessible et
            qu'aucune URL n'est fournie.
    """
    if not input_folder.exists() or not input_folder.is_dir():
        if has_urls:
            return []
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
            if p.is_file() and classify_file(p) is not None
        ),
        key=_natural_sort_key,
    )
    return [
        SourceExecution(
            source_id=SourceId.new(),
            source=InputSource(kind=_kind_of(p), location=str(p)),
        )
        for p in candidates
    ]


def _kind_of(path: Path) -> SourceKind:
    """Retourne le ``SourceKind`` d'un fichier déjà filtré comme supporté.

    Args:
        path: Fichier supporté (``classify_file`` non ``None``, garanti par le
            filtre amont).

    Returns:
        Le ``SourceKind`` du fichier.
    """
    kind = classify_file(path)
    assert kind is not None  # garanti par le filtre de build_input_sources  # noqa: S101
    return kind


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
