"""ViewModel ``PedagogyStateViewModel`` — état/fraîcheur de la fonctionnalité.

Calcule l'état affiché dans le bandeau de l'onglet pédagogique (R19) à partir du
projet, du dernier run COMPLETED, des documents consolidés sur disque et du
manifeste de fraîcheur. Pure logique, testable sans Qt.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from fahmi2.app.project_service import ProjectService
from fahmi2.domain.generation import (
    GENERATION_OUTPUT_SUBDIR,
    GENERATION_WORKSPACE_SUBDIR,
)
from fahmi2.domain.pedagogy import PEDAGOGY_WORKSPACE_SUBDIR, PedagogySettings
from fahmi2.domain.project import Project
from fahmi2.pedagogy.artifact_writer import artifact_json_path
from fahmi2.pedagogy.manifest import compute_settings_hash, read_manifest
from fahmi2.pedagogy.sources import consolidated_doc_path, source_mtime_ns

_MSG_NOT_CONFIGURED = (
    "Supports pédagogiques non configurés — cliquez sur « ⚙ Réglages »."
)
_MSG_GENERATION_REQUIRED = (
    "Génération requise : lancez d'abord la Génération pour produire le document "
    "consolidé et le glossaire des langues sélectionnées."
)
_MSG_READY = "Prêt à générer les supports."
_MSG_UP_TO_DATE = "Supports à jour."
_MSG_STALE = "Supports périmés (réglages ou source modifiés) — régénérez."


class PedagogyState(StrEnum):
    """État global de la fonctionnalité pédagogie pour un projet."""

    NOT_CONFIGURED = "not_configured"
    GENERATION_REQUIRED = "generation_required"
    READY = "ready"
    UP_TO_DATE = "up_to_date"
    STALE = "stale"


@dataclass(frozen=True)
class PedagogyStateInfo:
    """Résultat du calcul d'état.

    Attributes:
        state: État global.
        message: Texte FR du bandeau.
        can_generate: ``True`` si la génération est possible (source disponible).
    """

    state: PedagogyState
    message: str
    can_generate: bool


_MESSAGES: dict[PedagogyState, str] = {
    PedagogyState.NOT_CONFIGURED: _MSG_NOT_CONFIGURED,
    PedagogyState.GENERATION_REQUIRED: _MSG_GENERATION_REQUIRED,
    PedagogyState.READY: _MSG_READY,
    PedagogyState.UP_TO_DATE: _MSG_UP_TO_DATE,
    PedagogyState.STALE: _MSG_STALE,
}


class PedagogyStateViewModel:
    """Calcule l'état de fraîcheur des supports pour un projet."""

    def __init__(self, *, project_service: ProjectService) -> None:
        """Construit le viewmodel.

        Args:
            project_service: Service projet (dernier run COMPLETED).
        """
        self._project_service = project_service

    def compute(self, project: Project) -> PedagogyStateInfo:
        """Calcule l'état de la pédagogie pour ``project``.

        Args:
            project: Projet courant.

        Returns:
            ``PedagogyStateInfo`` (état + message + ``can_generate``).
        """
        pedagogy = project.pedagogy
        if pedagogy is None:
            return self._info(PedagogyState.NOT_CONFIGURED, can_generate=False)

        if self._project_service.get_last_completed_run(project.id) is None:
            return self._info(PedagogyState.GENERATION_REQUIRED, can_generate=False)

        generation_output_dir = (
            project.workspace_folder
            / GENERATION_WORKSPACE_SUBDIR
            / GENERATION_OUTPUT_SUBDIR
        )
        if any(
            not consolidated_doc_path(generation_output_dir, language).exists()
            for language in pedagogy.languages
        ):
            return self._info(PedagogyState.GENERATION_REQUIRED, can_generate=False)

        return self._info(
            self._freshness_state(project, pedagogy, generation_output_dir),
            can_generate=True,
        )

    def _freshness_state(
        self,
        project: Project,
        pedagogy: PedagogySettings,
        generation_output_dir: Path,
    ) -> PedagogyState:
        """Détermine ``READY`` / ``UP_TO_DATE`` / ``STALE`` (source disponible).

        Args:
            project: Projet courant.
            pedagogy: Réglages pédagogie.
            generation_output_dir: Dossier des livrables de génération.

        Returns:
            L'état de fraîcheur.
        """
        pedagogy_dir = project.workspace_folder / PEDAGOGY_WORKSPACE_SUBDIR
        manifest = read_manifest(pedagogy_dir)
        settings_hash = compute_settings_hash(pedagogy)

        any_generated = False
        any_stale = False
        for language in pedagogy.languages:
            source_mtime = source_mtime_ns(generation_output_dir, language)
            for support in pedagogy.selected_supports:
                if not artifact_json_path(pedagogy_dir, support, language).exists():
                    continue
                any_generated = True
                if not manifest.is_fresh(
                    support,
                    language,
                    settings_hash=settings_hash,
                    source_mtime_ns=source_mtime,
                ):
                    any_stale = True

        if not any_generated:
            return PedagogyState.READY
        if any_stale:
            return PedagogyState.STALE
        return PedagogyState.UP_TO_DATE

    @staticmethod
    def _info(state: PedagogyState, *, can_generate: bool) -> PedagogyStateInfo:
        """Construit un ``PedagogyStateInfo`` avec le message associé.

        Args:
            state: État.
            can_generate: Possibilité de générer.

        Returns:
            ``PedagogyStateInfo``.
        """
        return PedagogyStateInfo(
            state=state, message=_MESSAGES[state], can_generate=can_generate
        )
