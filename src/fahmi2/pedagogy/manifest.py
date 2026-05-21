"""Manifeste de fraîcheur des supports pédagogiques (``pedagogy/manifest.json``).

Enregistre, par (support, langue), le **hash des réglages** (champs affectant le
contenu : supports, corrigés, public, Bloom, directives, densité, modèle, config
LLM) et le **mtime du document consolidé source**. Permet la reprise coarse de
l'orchestrateur (skip si frais) et l'indicateur de péremption de l'UI (R19).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fahmi2.domain.enums import Language, SupportType
from fahmi2.domain.pedagogy import PedagogySettings
from fahmi2.infra.storage.fs_artifacts import FsArtifactStore

_MANIFEST_FILENAME = "manifest.json"
_MANIFEST_VERSION = 1
_ENCODING_UTF8 = "utf-8"


def manifest_path(pedagogy_dir: Path) -> Path:
    """Chemin du manifeste dans le dossier pédagogie.

    Args:
        pedagogy_dir: Dossier ``<emplacement>/pedagogy``.

    Returns:
        Le chemin de ``manifest.json``.
    """
    return pedagogy_dir / _MANIFEST_FILENAME


def compute_settings_hash(pedagogy: PedagogySettings) -> str:
    """Hash SHA-256 stable des réglages affectant le **contenu** des supports.

    N'inclut pas ``languages`` (géré par langue), ``cost_ceiling_usd``,
    ``export_formats`` ni ``max_retries`` (sans effet sur le contenu généré).

    Args:
        pedagogy: Réglages pédagogie.

    Returns:
        Le digest hexadécimal.
    """
    cfg = pedagogy.llm_config
    payload: dict[str, Any] = {
        "selected_supports": sorted(s.value for s in pedagogy.selected_supports),
        "separate_correction": sorted(s.value for s in pedagogy.separate_correction),
        "target_audience": pedagogy.target_audience.value,
        "bloom_objective": pedagogy.bloom_objective.value,
        "pedagogy_directives": pedagogy.pedagogy_directives,
        "density": pedagogy.density.value,
        "llm_model": pedagogy.llm_model.value,
        "llm_config": {
            "thinking_enabled": cfg.thinking_enabled,
            "reasoning_effort": (
                cfg.reasoning_effort.value if cfg.reasoning_effort else None
            ),
            "temperature": cfg.temperature,
        },
    }
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode(_ENCODING_UTF8)).hexdigest()


@dataclass(frozen=True)
class _Entry:
    """Entrée de manifeste pour un (support, langue)."""

    settings_hash: str
    source_mtime_ns: int | None


class PedagogyManifest:
    """État de fraîcheur des supports générés (par support × langue)."""

    def __init__(self) -> None:
        self._entries: dict[tuple[SupportType, Language], _Entry] = {}

    def is_fresh(
        self,
        support_type: SupportType,
        language: Language,
        *,
        settings_hash: str,
        source_mtime_ns: int | None,
    ) -> bool:
        """Indique si le support enregistré est à jour.

        Args:
            support_type: Type de support.
            language: Langue.
            settings_hash: Hash courant des réglages.
            source_mtime_ns: mtime courant du doc source (``None`` si absent).

        Returns:
            ``True`` si une entrée existe avec mêmes hash et mtime.
        """
        entry = self._entries.get((support_type, language))
        if entry is None:
            return False
        return (
            entry.settings_hash == settings_hash
            and entry.source_mtime_ns == source_mtime_ns
        )

    def record(
        self,
        support_type: SupportType,
        language: Language,
        *,
        settings_hash: str,
        source_mtime_ns: int | None,
    ) -> None:
        """Enregistre/Met à jour l'entrée d'un support.

        Args:
            support_type: Type de support.
            language: Langue.
            settings_hash: Hash des réglages au moment de la génération.
            source_mtime_ns: mtime du doc source au moment de la génération.
        """
        self._entries[(support_type, language)] = _Entry(
            settings_hash=settings_hash, source_mtime_ns=source_mtime_ns
        )

    def to_dict(self) -> dict[str, Any]:
        """Sérialise le manifeste en dict JSON-compatible.

        Returns:
            ``{"version", "entries": [...]}``.
        """
        return {
            "version": _MANIFEST_VERSION,
            "entries": [
                {
                    "support": st.value,
                    "language": lang.value,
                    "settings_hash": entry.settings_hash,
                    "source_mtime_ns": entry.source_mtime_ns,
                }
                for (st, lang), entry in self._entries.items()
            ],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> PedagogyManifest:
        """Reconstruit un manifeste depuis un dict (tolérant aux entrées invalides).

        Args:
            payload: Dict issu de ``to_dict``.

        Returns:
            Le manifeste reconstruit (entrées illisibles ignorées).
        """
        manifest = cls()
        for raw in payload.get("entries", []):
            try:
                st = SupportType(raw["support"])
                lang = Language(raw["language"])
            except (KeyError, ValueError):
                continue
            manifest.record(
                st,
                lang,
                settings_hash=str(raw.get("settings_hash", "")),
                source_mtime_ns=raw.get("source_mtime_ns"),
            )
        return manifest


def read_manifest(pedagogy_dir: Path) -> PedagogyManifest:
    """Lit le manifeste, ou renvoie un manifeste vide si absent/corrompu.

    Args:
        pedagogy_dir: Dossier ``<emplacement>/pedagogy``.

    Returns:
        Le ``PedagogyManifest`` (vide si fichier manquant ou JSON invalide).
    """
    path = manifest_path(pedagogy_dir)
    if not path.exists():
        return PedagogyManifest()
    try:
        payload = json.loads(path.read_text(encoding=_ENCODING_UTF8))
    except (OSError, json.JSONDecodeError):
        return PedagogyManifest()
    if not isinstance(payload, dict):
        return PedagogyManifest()
    return PedagogyManifest.from_dict(payload)


def write_manifest(
    artifacts: FsArtifactStore, pedagogy_dir: Path, manifest: PedagogyManifest
) -> None:
    """Écrit le manifeste de manière atomique.

    Args:
        artifacts: Store d'artefacts (écriture atomique).
        pedagogy_dir: Dossier ``<emplacement>/pedagogy``.
        manifest: Manifeste à persister.
    """
    artifacts.write_json_atomic(manifest_path(pedagogy_dir), manifest.to_dict())
