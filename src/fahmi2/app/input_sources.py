"""Construction de la liste des sources d'entrée d'un Run.

Collecte les sources disponibles (fichiers reconnus du dossier d'entrée + liens
YouTube), puis applique l'**ordonnancement** et l'**exclusion** définis par
l'utilisateur via ``reconcile_source_order`` (fonction pure, partagée avec l'UI
d'édition de l'ordre).

Les types de fichiers reconnus sont centralisés dans ``infra.ingestion.classify``.
Le tri d'entrée par défaut est **naturel** : on extrait le premier token purement
numérique du nom (après suppression de l'extension et découpage sur les
séparateurs usuels ``[\\s\\-_]+``), ce qui gère les nommages préfixés du type
``V.1 - 1 - Intro.mp4`` ou ``doc 01 - X.mp4``.
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


def reconcile_source_order(
    available_keys: list[str],
    source_order: tuple[str, ...],
    excluded: tuple[str, ...],
) -> tuple[list[str], list[str]]:
    """Réconcilie l'ordre/exclusion persistés avec les sources réellement présentes.

    Args:
        available_keys: Clés des sources présentes, dans l'ordre de collecte
            (fichiers triés naturellement puis URLs).
        source_order: Clés ordonnées des sources à inclure (persistées).
        excluded: Clés des sources exclues (persistées).

    Returns:
        ``(included_keys, excluded_keys)`` : les incluses ordonnées (clés de
        ``source_order`` encore présentes d'abord, puis les nouvelles dans
        l'ordre de collecte), et les exclues encore présentes. Les clés
        obsolètes (absentes de ``available_keys``) sont ignorées.
    """
    excluded_set = set(excluded)
    excluded_keys = [k for k in available_keys if k in excluded_set]
    non_excluded = [k for k in available_keys if k not in excluded_set]
    non_excluded_set = set(non_excluded)
    ordered = [k for k in source_order if k in non_excluded_set]
    ordered_set = set(ordered)
    ordered += [k for k in non_excluded if k not in ordered_set]
    return ordered, excluded_keys


def collect_available_sources_from(
    input_folder: Path | None, youtube_urls: tuple[str, ...]
) -> list[InputSource]:
    """Liste les sources disponibles (fichiers + URLs), sans ordre ni exclusion.

    Les URLs YouTube sont **dédupliquées** en préservant l'ordre de saisie
    (``dict.fromkeys``) : c'est ce qui garantit l'unicité des ``order_key`` —
    invariant exploité par ``build_input_sources`` (cf. son indexation ``by_key``).

    Args:
        input_folder: Dossier d'entrée à scanner, ou ``None`` si aucun dossier
            n'est sélectionné (seules les URLs sont alors collectées).
        youtube_urls: Liens YouTube saisis (doublons tolérés en entrée).

    Returns:
        Les ``InputSource`` dans l'ordre de collecte (fichiers triés naturellement
        puis URLs uniques).

    Raises:
        StorageError: ``STORAGE.READ_DENIED`` si le dossier est fourni mais
            inaccessible, et qu'aucune URL n'est fournie.
    """
    file_sources = (
        _scan_file_sources(input_folder, has_urls=bool(youtube_urls))
        if input_folder is not None
        else []
    )
    youtube_sources = [
        InputSource(kind=SourceKind.YOUTUBE, location=url)
        for url in dict.fromkeys(youtube_urls)
    ]
    return file_sources + youtube_sources


def collect_available_sources(settings: GenerationSettings) -> list[InputSource]:
    """Liste les sources disponibles depuis les réglages (cf. ``_from``).

    Args:
        settings: Réglages de génération.

    Returns:
        Les ``InputSource`` disponibles, dans l'ordre de collecte.
    """
    return collect_available_sources_from(settings.input_folder, settings.youtube_urls)


def build_input_sources(settings: GenerationSettings) -> list[SourceExecution]:
    """Construit la liste ordonnée des sources d'entrée incluses d'un Run.

    Collecte les sources disponibles, applique l'ordre (``source_order``) et
    l'exclusion (``excluded_sources``) via ``reconcile_source_order``, puis
    matérialise les ``SourceExecution`` (un ``SourceId`` frais par source).

    Args:
        settings: Réglages de génération.

    Returns:
        Liste ordonnée des ``SourceExecution`` **incluses**.

    Raises:
        StorageError: Si le dossier est inaccessible et qu'aucune URL n'est fournie.
        ConfigError: ``CONFIG.NO_INPUT_SOURCE`` si aucune source incluse (rien de
            présent, ou tout est exclu).
    """
    available = collect_available_sources(settings)
    # ``order_key`` est unique par construction : les fichiers d'un même dossier
    # ont des noms distincts et les URLs sont dédupliquées par
    # ``collect_available_sources_from``. L'indexation ``by_key`` est donc sûre.
    by_key = {source.order_key(): source for source in available}
    available_keys = [source.order_key() for source in available]
    included_keys, _ = reconcile_source_order(
        available_keys, settings.source_order, settings.excluded_sources
    )
    result = [
        SourceExecution(source_id=SourceId.new(), source=by_key[key])
        for key in included_keys
    ]
    if not result:
        raise ConfigError(
            code="CONFIG.NO_INPUT_SOURCE",
            user_message=(
                "Aucune source à traiter : le dossier d'entrée ne contient aucun "
                "fichier pris en charge (vidéos, audios, documents), aucun lien "
                "YouTube n'a été saisi, ou toutes les sources sont exclues."
            ),
            severity=Severity.ERROR,
            technical_details={
                "input_folder": str(settings.input_folder),
                "supported": sorted(supported_file_extensions()),
            },
        )
    return result


def _scan_file_sources(input_folder: Path, *, has_urls: bool) -> list[InputSource]:
    """Scanne les fichiers reconnus du dossier d'entrée, triés naturellement.

    Args:
        input_folder: Dossier à scanner.
        has_urls: ``True`` si des liens YouTube sont par ailleurs fournis (alors
            un dossier inaccessible est toléré : projet YouTube seul).

    Returns:
        Liste des ``InputSource`` fichier (vide si dossier absent + ``has_urls``).

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
        InputSource(kind=_kind_of(p), location=str(p)) for p in candidates
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
    assert kind is not None  # garanti par le filtre de _scan_file_sources  # noqa: S101
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
