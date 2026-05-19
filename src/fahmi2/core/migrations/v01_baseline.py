"""Migration baseline ``v0 → v1`` (schéma initial).

Cette migration est un placeholder qui formalise la version 1 du schéma. Le
schéma SQLite v1 est créé directement par ``SqliteState._init_database`` via
``_schema.sql`` ; cette migration enregistre simplement la mécanique pour les
futures évolutions ``v1 → v2`` et au-delà.
"""

from __future__ import annotations

from fahmi2.core.migrations.runner import Migration


class _BaselineState:
    """Type-marker minimaliste pour la migration baseline (placeholder).

    Implémente le protocole ``_HasSchemaVersion``.
    """

    def __init__(self, schema_version: int) -> None:
        self.schema_version = schema_version


def _apply_baseline(state: _BaselineState) -> None:
    """Migration vide : aligne ``schema_version`` à 1.

    Args:
        state: État à migrer.
    """
    state.schema_version = 1


def baseline_migration() -> Migration[_BaselineState]:
    """Retourne l'objet ``Migration`` pour ``v0 → v1``.

    Returns:
        L'instance ``Migration``.
    """
    return Migration(from_version=0, to_version=1, apply=_apply_baseline)
