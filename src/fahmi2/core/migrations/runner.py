"""Runner de migrations forward-only avec chaînage automatique.

Chaque artefact persistant (``project.json``, SQLite ``project.db``, etc.) porte
un ``schema_version: int``. Au démarrage de l'app, le ``MigrationRunner`` applique
en chaîne les migrations nécessaires pour atteindre la version cible courante du
code, en refusant les downgrades.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic, Protocol, TypeVar


class _HasSchemaVersion(Protocol):
    """Interface implicite : tout état persistant porte un ``schema_version``."""

    schema_version: int


S = TypeVar("S", bound=_HasSchemaVersion)


@dataclass(frozen=True)
class Migration(Generic[S]):
    """Migration unitaire d'un schéma vX vers vY.

    Attributes:
        from_version: Version source attendue.
        to_version: Version cible après application.
        apply: Fonction mutant l'état en place et mettant à jour
            ``state.schema_version``.
    """

    from_version: int
    to_version: int
    apply: Callable[[S], None]


class MigrationRunner(Generic[S]):
    """Applique en chaîne les migrations nécessaires pour atteindre ``target_version``.

    Migrations forward-only : refuse les downgrades (``target < current``). Refuse
    également les migrations qui ne font pas progresser ``schema_version`` (anti
    boucle infinie).
    """

    def __init__(
        self,
        *,
        migrations: list[Migration[S]],
        target_version: int,
    ) -> None:
        """Construit le runner.

        Args:
            migrations: Liste des migrations disponibles.
            target_version: Version finale visée.
        """
        self._by_from: dict[int, Migration[S]] = {
            m.from_version: m for m in migrations
        }
        self._target = target_version

    def run(self, state: S) -> None:
        """Applique en chaîne les migrations jusqu'à ``target_version``.

        Args:
            state: État mutable à migrer (mutation en place).

        Raises:
            RuntimeError: Si downgrade demandé, ou aucun chemin de migration
                disponible, ou si une migration n'avance pas le schéma.
        """
        if state.schema_version > self._target:
            raise RuntimeError(
                f"Cannot downgrade schema from v{state.schema_version} "
                f"to v{self._target}"
            )
        while state.schema_version < self._target:
            current = state.schema_version
            mig = self._by_from.get(current)
            if mig is None:
                raise RuntimeError(
                    f"No migration path from v{current} towards v{self._target}"
                )
            mig.apply(state)
            if state.schema_version <= current:
                raise RuntimeError(
                    f"Migration {mig.from_version}->{mig.to_version} did not advance "
                    f"schema_version (got v{state.schema_version})"
                )
