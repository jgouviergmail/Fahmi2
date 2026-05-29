"""Manifeste de fraîcheur des Visualisations (``visuals/manifest.json``).

Enregistre, **par langue**, le hash des réglages affectant le contenu et les mtimes
des sources dont dépendent les livrables : le document consolidé **de la langue de
structure** (d'où le graphe/diagrammes sont extraits), le **glossaire master**, et le
document consolidé **de la langue cible** (d'où sont re-dérivés les extraits). Permet la
reprise *coarse* de l'orchestrateur et l'indicateur de péremption de l'UI.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fahmi2.domain.enums import Language
from fahmi2.domain.visuals import VisualsSettings
from fahmi2.infra.storage.fs_artifacts import FsArtifactStore

_MANIFEST_FILENAME = "manifest.json"
_MANIFEST_VERSION = 1
_ENCODING_UTF8 = "utf-8"

_KEY_SETTINGS = "settings_hash"
_KEY_STRUCTURE = "structure_mtime_ns"
_KEY_GLOSSARY = "glossary_mtime_ns"
_KEY_CONTENT = "content_mtime_ns"


def manifest_path(visuals_dir: Path) -> Path:
    """Chemin du manifeste dans le dossier de la fonctionnalité.

    Args:
        visuals_dir: Dossier ``<emplacement>/visuals``.

    Returns:
        Le chemin de ``manifest.json``.
    """
    return visuals_dir / _MANIFEST_FILENAME


def compute_settings_hash(settings: VisualsSettings) -> str:
    """Hash SHA-256 stable des réglages affectant le **contenu** des livrables.

    N'inclut pas ``llm_workers`` ni ``cost_ceiling_usd`` (sans effet sur le contenu).

    Args:
        settings: Réglages Visualisations.

    Returns:
        Le digest hexadécimal.
    """
    cfg = settings.llm_config
    payload: dict[str, Any] = {
        "produce_knowledge_map": settings.produce_knowledge_map,
        "produce_diagrams": settings.produce_diagrams,
        "density": settings.density.value,
        "diagram_types": sorted(t.value for t in settings.diagram_types),
        "llm_model": settings.llm_model.value,
        "llm_config": {
            "thinking_enabled": cfg.thinking_enabled,
            "reasoning_effort": (
                cfg.reasoning_effort.value if cfg.reasoning_effort else None
            ),
            "temperature": cfg.temperature,
        },
    }
    serialized = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(serialized.encode(_ENCODING_UTF8)).hexdigest()


@dataclass
class VisualsManifest:
    """Manifeste de fraîcheur des livrables Visualisations (mutable, par langue).

    Attributes:
        entries: ``langue -> {settings_hash, structure_mtime_ns, glossary_mtime_ns,
            content_mtime_ns}``.
    """

    entries: dict[str, dict[str, Any]] = field(default_factory=dict)

    def is_fresh(
        self,
        language: Language,
        *,
        settings_hash: str,
        structure_mtime_ns: int | None,
        glossary_mtime_ns: int | None,
        content_mtime_ns: int | None,
    ) -> bool:
        """Indique si les livrables d'une langue sont à jour.

        Args:
            language: Langue cible.
            settings_hash: Hash courant des réglages.
            structure_mtime_ns: mtime courant du doc de structure.
            glossary_mtime_ns: mtime courant du glossaire master.
            content_mtime_ns: mtime courant du doc de la langue cible.

        Returns:
            ``True`` si tous les éléments enregistrés correspondent aux valeurs
            courantes ; ``False`` si absent ou périmé.
        """
        entry = self.entries.get(language.value)
        if entry is None:
            return False
        return (
            entry.get(_KEY_SETTINGS) == settings_hash
            and entry.get(_KEY_STRUCTURE) == structure_mtime_ns
            and entry.get(_KEY_GLOSSARY) == glossary_mtime_ns
            and entry.get(_KEY_CONTENT) == content_mtime_ns
        )

    def record(
        self,
        language: Language,
        *,
        settings_hash: str,
        structure_mtime_ns: int | None,
        glossary_mtime_ns: int | None,
        content_mtime_ns: int | None,
    ) -> None:
        """Enregistre l'état de fraîcheur d'une langue après production.

        Args:
            language: Langue cible.
            settings_hash: Hash des réglages.
            structure_mtime_ns: mtime du doc de structure.
            glossary_mtime_ns: mtime du glossaire master.
            content_mtime_ns: mtime du doc de la langue cible.
        """
        self.entries[language.value] = {
            _KEY_SETTINGS: settings_hash,
            _KEY_STRUCTURE: structure_mtime_ns,
            _KEY_GLOSSARY: glossary_mtime_ns,
            _KEY_CONTENT: content_mtime_ns,
        }


def read_manifest(visuals_dir: Path) -> VisualsManifest:
    """Lit le manifeste, ou un manifeste vide si absent/illisible.

    Args:
        visuals_dir: Dossier ``<emplacement>/visuals``.

    Returns:
        Le ``VisualsManifest`` (vide si jamais produit / fichier corrompu).
    """
    path = manifest_path(visuals_dir)
    if not path.exists():
        return VisualsManifest()
    try:
        payload = json.loads(path.read_text(encoding=_ENCODING_UTF8))
        entries = payload.get("entries", {})
        if not isinstance(entries, dict):
            return VisualsManifest()
        return VisualsManifest(entries=entries)
    except (OSError, json.JSONDecodeError, ValueError, TypeError):
        return VisualsManifest()


def write_manifest(
    artifacts: FsArtifactStore, visuals_dir: Path, manifest: VisualsManifest
) -> None:
    """Écrit le manifeste de manière atomique.

    Args:
        artifacts: Store d'artefacts (écriture atomique).
        visuals_dir: Dossier ``<emplacement>/visuals``.
        manifest: Manifeste à persister.
    """
    payload = {"version": _MANIFEST_VERSION, "entries": manifest.entries}
    artifacts.write_json_atomic(manifest_path(visuals_dir), payload)
