"""Manifeste de fraîcheur des Visualisations (``visuals/manifest.json``).

Enregistre, **par langue**, le hash des réglages affectant le contenu et les mtimes
des sources dont dépendent les livrables : le document consolidé **de la langue de
structure** (d'où le graphe/diagrammes sont extraits), le **glossaire master**, et le
document consolidé **de la langue cible** (d'où sont re-dérivés les extraits). Permet la
reprise *coarse* de l'orchestrateur et l'indicateur de péremption de l'UI. Persiste aussi
les **coûts LLM de production par livrable** (localisation par langue + extraction de
structure globale) pour **reconstruire la ventilation des coûts hors session** (vue
persistée de la matrice de progression), à l'image des coûts par artefact de la Pédagogie.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from fahmi2.domain.enums import Language
from fahmi2.domain.visuals import VisualsSettings
from fahmi2.infra.storage.fs_artifacts import FsArtifactStore

_MANIFEST_FILENAME = "manifest.json"
_MANIFEST_VERSION = 2
_ENCODING_UTF8 = "utf-8"

_KEY_SETTINGS = "settings_hash"
_KEY_STRUCTURE = "structure_mtime_ns"
_KEY_GLOSSARY = "glossary_mtime_ns"
_KEY_CONTENT = "content_mtime_ns"
_KEY_MAP_COST = "map_cost_usd"
_KEY_DIAGRAMS_COST = "diagrams_cost_usd"
_KEY_STRUCTURE_COSTS = "structure_costs"

#: Longueur attendue de la paire de coûts de structure ``[carte, diagrammes]``.
_STRUCTURE_COSTS_LEN = 2


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


class VisualsManifest:
    """Manifeste de fraîcheur des livrables Visualisations (mutable, par langue).

    Encapsule un dict privé ``langue -> {settings_hash, structure_mtime_ns,
    glossary_mtime_ns, content_mtime_ns}`` ; on ne le manipule qu'via ``record`` /
    ``is_fresh`` et la (dé)sérialisation ``to_dict`` / ``from_dict`` (même pattern que
    ``PedagogyManifest``).
    """

    def __init__(self) -> None:
        self._entries: dict[str, dict[str, Any]] = {}
        #: Coûts LLM (USD) de l'extraction de structure ``(carte, diagrammes)``, globaux ;
        #: ``None`` tant que jamais enregistrés (manifeste v1) — distinct d'un coût nul.
        self._structure_costs: tuple[float, float] | None = None

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
        entry = self._entries.get(language.value)
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
        map_cost_usd: float | None = None,
        diagrams_cost_usd: float | None = None,
    ) -> None:
        """Enregistre l'état de fraîcheur **et les coûts** d'une langue après production.

        Args:
            language: Langue cible.
            settings_hash: Hash des réglages.
            structure_mtime_ns: mtime du doc de structure.
            glossary_mtime_ns: mtime du glossaire master.
            content_mtime_ns: mtime du doc de la langue cible.
            map_cost_usd: Coût LLM de la localisation de la carte (``None`` = non
                enregistré, p. ex. à la relecture d'un manifeste v1).
            diagrams_cost_usd: Coût LLM de la localisation des diagrammes.
        """
        entry: dict[str, Any] = {
            _KEY_SETTINGS: settings_hash,
            _KEY_STRUCTURE: structure_mtime_ns,
            _KEY_GLOSSARY: glossary_mtime_ns,
            _KEY_CONTENT: content_mtime_ns,
        }
        if map_cost_usd is not None:
            entry[_KEY_MAP_COST] = map_cost_usd
            entry[_KEY_DIAGRAMS_COST] = diagrams_cost_usd or 0.0
        self._entries[language.value] = entry

    def record_structure_cost(
        self, map_cost_usd: float, diagrams_cost_usd: float
    ) -> None:
        """Enregistre le coût LLM **global** de l'extraction de structure par livrable.

        Args:
            map_cost_usd: Coût imputé à la carte (graphe + résolution + rapports +
                idea-chains).
            diagrams_cost_usd: Coût imputé aux diagrammes.
        """
        self._structure_costs = (map_cost_usd, diagrams_cost_usd)

    def structure_costs(self) -> tuple[float, float] | None:
        """Coûts de structure persistés.

        Returns:
            ``(coût carte, coût diagrammes)``, ou ``None`` si jamais enregistrés
            (ex. manifeste v1) — à distinguer d'un coût nul.
        """
        return self._structure_costs

    def language_costs(self) -> dict[Language, tuple[float, float]]:
        """Coûts de localisation persistés, par langue **dont le coût est connu**.

        Les langues sans coût enregistré (ex. manifeste v1) sont **omises** (≠ coût
        nul), à l'image de ``read_generated_costs`` côté Pédagogie.

        Returns:
            Un mapping ``langue -> (coût carte, coût diagrammes)``.
        """
        costs: dict[Language, tuple[float, float]] = {}
        for lang_str, entry in self._entries.items():
            if _KEY_MAP_COST not in entry:
                continue
            try:
                language = Language(lang_str)
            except ValueError:
                continue
            costs[language] = (
                float(entry[_KEY_MAP_COST]),
                float(entry.get(_KEY_DIAGRAMS_COST, 0.0)),
            )
        return costs

    def to_dict(self) -> dict[str, Any]:
        """Sérialise le manifeste en dict JSON-compatible.

        Returns:
            ``{"version", "entries": {langue: {…}}, "structure_costs": [carte, diag]}``.
        """
        return {
            "version": _MANIFEST_VERSION,
            "entries": dict(self._entries),
            _KEY_STRUCTURE_COSTS: (
                list(self._structure_costs)
                if self._structure_costs is not None
                else None
            ),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> VisualsManifest:
        """Reconstruit un manifeste depuis un dict (tolérant aux entrées invalides).

        Args:
            payload: Dict issu de ``to_dict``.

        Returns:
            Le manifeste reconstruit (entrées illisibles ignorées).
        """
        manifest = cls()
        raw_struct = payload.get(_KEY_STRUCTURE_COSTS)
        if isinstance(raw_struct, list) and len(raw_struct) == _STRUCTURE_COSTS_LEN:
            try:
                manifest.record_structure_cost(
                    float(raw_struct[0]), float(raw_struct[1])
                )
            except (TypeError, ValueError):
                pass
        entries = payload.get("entries", {})
        if not isinstance(entries, dict):
            return manifest
        for lang_str, entry in entries.items():
            try:
                language = Language(lang_str)
            except ValueError:
                continue
            if not isinstance(entry, dict):
                continue
            # Cast défensif des coûts (symétrique du garde-fou de ``structure_costs``) :
            # une valeur non castable laisse les coûts à ``None`` (inconnu) plutôt que de
            # faire échouer toute la lecture du manifeste.
            map_cost: float | None = None
            diagrams_cost: float | None = None
            if _KEY_MAP_COST in entry:
                try:
                    map_cost = float(entry[_KEY_MAP_COST])
                    diagrams_cost = float(entry.get(_KEY_DIAGRAMS_COST, 0.0))
                except (TypeError, ValueError):
                    map_cost = None
                    diagrams_cost = None
            manifest.record(
                language,
                settings_hash=str(entry.get(_KEY_SETTINGS, "")),
                structure_mtime_ns=entry.get(_KEY_STRUCTURE),
                glossary_mtime_ns=entry.get(_KEY_GLOSSARY),
                content_mtime_ns=entry.get(_KEY_CONTENT),
                map_cost_usd=map_cost,
                diagrams_cost_usd=diagrams_cost,
            )
        return manifest


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
    except (OSError, json.JSONDecodeError, ValueError, TypeError):
        return VisualsManifest()
    if not isinstance(payload, dict):
        # JSON valide mais non-objet (ex. liste) : manifeste vide plutôt qu'un crash
        # ``AttributeError`` dans ``from_dict`` (alignement sur ``PedagogyManifest``).
        return VisualsManifest()
    return VisualsManifest.from_dict(payload)


def write_manifest(
    artifacts: FsArtifactStore, visuals_dir: Path, manifest: VisualsManifest
) -> None:
    """Écrit le manifeste de manière atomique.

    Args:
        artifacts: Store d'artefacts (écriture atomique).
        visuals_dir: Dossier ``<emplacement>/visuals``.
        manifest: Manifeste à persister.
    """
    artifacts.write_json_atomic(manifest_path(visuals_dir), manifest.to_dict())
