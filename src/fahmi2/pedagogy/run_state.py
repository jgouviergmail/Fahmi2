"""État de la dernière exécution pédagogie — ré-export du module partagé.

Le contenu vit désormais dans ``infra/storage/feature_run_state`` (source unique,
partagée avec les Visualisations). Ce module conserve les noms historiques
(``PedagogyRunState`` …) pour ses consommateurs (orchestrateur, contrôleur UI, tests).
"""

from __future__ import annotations

from fahmi2.infra.storage.feature_run_state import (
    FeatureRunState as PedagogyRunState,
)
from fahmi2.infra.storage.feature_run_state import (
    read_run_state,
    run_state_path,
    write_run_state,
)

__all__ = ["PedagogyRunState", "read_run_state", "run_state_path", "write_run_state"]
