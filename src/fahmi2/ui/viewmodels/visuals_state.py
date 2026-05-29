"""ViewModel ``VisualsStateViewModel`` — état/fraîcheur de la fonctionnalité Visualisations.

Calcule l'état affiché dans le bandeau de l'onglet Visualisations à partir du projet,
du dernier run COMPLETED, des documents consolidés latins sur disque et du manifeste de
fraîcheur. Pure logique, testable sans Qt.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from PySide6.QtCore import QCoreApplication

from fahmi2.app.project_service import ProjectService
from fahmi2.domain.enums import Language
from fahmi2.domain.generation import (
    GENERATION_OUTPUT_SUBDIR,
    GENERATION_WORKSPACE_SUBDIR,
)
from fahmi2.domain.project import Project
from fahmi2.domain.visuals import (
    VISUALS_OUTPUT_SUBDIR,
    VISUALS_WORKSPACE_SUBDIR,
    VisualsSettings,
)
from fahmi2.visuals.manifest import compute_settings_hash, read_manifest
from fahmi2.visuals.sources import (
    available_visuals_languages,
    glossary_master_mtime_ns,
    outputs_present,
    source_mtime_ns,
    structure_language,
)


class VisualsState(StrEnum):
    """État global de la fonctionnalité Visualisations pour un projet."""

    NOT_CONFIGURED = "not_configured"
    GENERATION_REQUIRED = "generation_required"
    READY = "ready"
    UP_TO_DATE = "up_to_date"
    STALE = "stale"


@dataclass(frozen=True)
class VisualsStateInfo:
    """Résultat du calcul d'état.

    Attributes:
        state: État global.
        message: Texte traduit du bandeau.
        can_generate: ``True`` si la génération est possible (source latine présente).
    """

    state: VisualsState
    message: str
    can_generate: bool


def _state_message(state: VisualsState) -> str:
    """Libellé court traduit pour le bandeau de l'onglet Visualisations.

    Args:
        state: État global.

    Returns:
        Le message traduit.
    """
    if state is VisualsState.NOT_CONFIGURED:
        return QCoreApplication.translate("VisualsState", "⚙ À configurer")
    if state is VisualsState.GENERATION_REQUIRED:
        return QCoreApplication.translate("VisualsState", "⚠ Génération requise")
    if state is VisualsState.READY:
        return QCoreApplication.translate("VisualsState", "● Prêt à générer")
    if state is VisualsState.UP_TO_DATE:
        return QCoreApplication.translate("VisualsState", "✓ Visualisations à jour")
    return QCoreApplication.translate("VisualsState", "⟳ Visualisations à régénérer")


class VisualsStateViewModel:
    """Calcule l'état de fraîcheur des visualisations pour un projet."""

    def __init__(self, *, project_service: ProjectService) -> None:
        """Construit le viewmodel.

        Args:
            project_service: Service projet (dernier run COMPLETED).
        """
        self._project_service = project_service

    def compute(self, project: Project) -> VisualsStateInfo:
        """Calcule l'état des visualisations pour ``project``.

        Args:
            project: Projet courant.

        Returns:
            ``VisualsStateInfo`` (état + message + ``can_generate``).
        """
        visuals = project.visuals
        if visuals is None:
            return self._info(VisualsState.NOT_CONFIGURED, can_generate=False)
        if self._project_service.get_last_completed_run(project.id) is None:
            return self._info(VisualsState.GENERATION_REQUIRED, can_generate=False)
        output_dir = (
            project.workspace_folder
            / GENERATION_WORKSPACE_SUBDIR
            / GENERATION_OUTPUT_SUBDIR
        )
        available = available_visuals_languages(output_dir)
        if not available:
            return self._info(VisualsState.GENERATION_REQUIRED, can_generate=False)
        return self._info(
            self._freshness_state(project, visuals, output_dir, available),
            can_generate=True,
        )

    def _freshness_state(
        self,
        project: Project,
        visuals: VisualsSettings,
        output_dir: Path,
        available: list[Language],
    ) -> VisualsState:
        """Détermine ``READY`` / ``UP_TO_DATE`` / ``STALE`` (source latine disponible).

        Args:
            project: Projet courant.
            visuals: Réglages Visualisations.
            output_dir: Dossier des livrables de génération.
            available: Langues latines disponibles.

        Returns:
            L'état de fraîcheur.
        """
        visuals_dir = project.workspace_folder / VISUALS_WORKSPACE_SUBDIR
        out_dir = visuals_dir / VISUALS_OUTPUT_SUBDIR
        manifest = read_manifest(visuals_dir)
        settings_hash = compute_settings_hash(visuals)
        source = (
            project.generation.source_language
            if project.generation is not None
            else None
        )
        struct_lang = structure_language(source, available)
        structure_mtime = (
            source_mtime_ns(output_dir, struct_lang) if struct_lang is not None else None
        )
        glossary_mtime = glossary_master_mtime_ns(
            project.workspace_folder / GENERATION_WORKSPACE_SUBDIR
        )

        any_generated = False
        all_fresh = True
        for language in available:
            present = outputs_present(out_dir, language, visuals)
            fresh = manifest.is_fresh(
                language,
                settings_hash=settings_hash,
                structure_mtime_ns=structure_mtime,
                glossary_mtime_ns=glossary_mtime,
                content_mtime_ns=source_mtime_ns(output_dir, language),
            )
            if present:
                any_generated = True
            if not (present and fresh):
                all_fresh = False

        if not any_generated:
            return VisualsState.READY
        if all_fresh:
            return VisualsState.UP_TO_DATE
        return VisualsState.STALE

    @staticmethod
    def _info(state: VisualsState, *, can_generate: bool) -> VisualsStateInfo:
        """Construit un ``VisualsStateInfo`` avec le message associé.

        Args:
            state: État.
            can_generate: Possibilité de générer.

        Returns:
            ``VisualsStateInfo``.
        """
        return VisualsStateInfo(
            state=state, message=_state_message(state), can_generate=can_generate
        )
