"""État de la dernière exécution d'une fonctionnalité « légère » (sur disque).

Les fonctionnalités modelées sur la Pédagogie (orchestrateur léger, tout sur disque,
sans Run SQLite) persistent le statut, les horodatages et le coût de leur dernière
exécution dans un ``run_state.json`` placé dans leur dossier de feature. Cela expose un
**statut homogène avec la Génération** (sidebar, tuiles) même hors session active.

Module **partagé** (source unique) : réutilisé par la Pédagogie et les Visualisations.
L'orchestrateur écrit ``RUNNING`` au démarrage puis le statut final à la fin.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from fahmi2.domain.enums import RunStatus
from fahmi2.infra.storage.fs_artifacts import FsArtifactStore

_RUN_STATE_FILENAME = "run_state.json"
_ENCODING_UTF8 = "utf-8"
_STATE_VERSION = 1

_KEY_VERSION = "version"
_KEY_STATUS = "status"
_KEY_STARTED_AT = "started_at"
_KEY_FINISHED_AT = "finished_at"
_KEY_TOTAL_COST = "total_cost_usd"


@dataclass(frozen=True)
class FeatureRunState:
    """Statut de la dernière exécution d'une fonctionnalité.

    Attributes:
        status: Statut de l'exécution (``RUNNING`` en cours, puis ``COMPLETED`` /
            ``FAILED`` / ``CANCELLED`` / ``PAUSED``).
        started_at: Horodatage de démarrage (UTC aware).
        finished_at: Horodatage de fin (``None`` tant que ``RUNNING``).
        total_cost_usd: Coût LLM cumulé de l'exécution.
    """

    status: RunStatus
    started_at: datetime
    finished_at: datetime | None
    total_cost_usd: float


def run_state_path(feature_dir: Path) -> Path:
    """Chemin du fichier d'état dans le dossier de la fonctionnalité.

    Args:
        feature_dir: Dossier de la fonctionnalité (ex. ``<emplacement>/visuals``).

    Returns:
        Le chemin de ``run_state.json``.
    """
    return feature_dir / _RUN_STATE_FILENAME


def read_run_state(feature_dir: Path) -> FeatureRunState | None:
    """Lit l'état de la dernière exécution, ou ``None`` si absent/illisible.

    Args:
        feature_dir: Dossier de la fonctionnalité.

    Returns:
        Le ``FeatureRunState``, ou ``None`` (jamais exécuté / fichier corrompu).
    """
    path = run_state_path(feature_dir)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding=_ENCODING_UTF8))
        finished_raw = payload.get(_KEY_FINISHED_AT)
        return FeatureRunState(
            status=RunStatus(payload[_KEY_STATUS]),
            started_at=datetime.fromisoformat(payload[_KEY_STARTED_AT]),
            finished_at=(
                datetime.fromisoformat(finished_raw)
                if finished_raw is not None
                else None
            ),
            total_cost_usd=float(payload.get(_KEY_TOTAL_COST, 0.0)),
        )
    except (OSError, json.JSONDecodeError, KeyError, ValueError, TypeError):
        return None


def write_run_state(
    artifacts: FsArtifactStore, feature_dir: Path, state: FeatureRunState
) -> None:
    """Écrit l'état de la dernière exécution de manière atomique.

    Args:
        artifacts: Store d'artefacts (écriture atomique).
        feature_dir: Dossier de la fonctionnalité.
        state: État à persister.
    """
    payload = {
        _KEY_VERSION: _STATE_VERSION,
        _KEY_STATUS: state.status.value,
        _KEY_STARTED_AT: state.started_at.isoformat(),
        _KEY_FINISHED_AT: (
            state.finished_at.isoformat() if state.finished_at is not None else None
        ),
        _KEY_TOTAL_COST: state.total_cost_usd,
    }
    artifacts.write_json_atomic(run_state_path(feature_dir), payload)
