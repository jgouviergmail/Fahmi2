"""Service de détection de l'environnement matériel (CUDA/GPU).

Utilisé par l'UI pour bloquer la sélection de ``faster_whisper_local`` quand
aucun GPU NVIDIA n'est détecté (cf. spec §7.7).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HardwareInfo:
    """Informations matérielles détectées au démarrage de l'application.

    Attributes:
        cuda_available: ``True`` si au moins un device CUDA est disponible.
        gpu_name: Nom du premier GPU détecté (chaîne vide si aucun).
        cuda_version: Version CUDA du runtime (chaîne vide si introuvable).
    """

    cuda_available: bool
    gpu_name: str
    cuda_version: str


def probe_hardware() -> HardwareInfo:
    """Sonde l'environnement matériel.

    L'implémentation s'appuie sur ``torch`` quand disponible, puis sur
    ``ctranslate2`` en fallback. En cas d'absence de runtime CUDA, retourne
    une ``HardwareInfo`` avec ``cuda_available=False``.

    Returns:
        Un snapshot immuable des informations matérielles détectées.
    """
    try:
        import torch  # noqa: PLC0415

        if torch.cuda.is_available():
            gpu_name = torch.cuda.get_device_name(0) if torch.cuda.device_count() else ""
            cuda_version = str(getattr(torch.version, "cuda", "") or "")
            return HardwareInfo(
                cuda_available=True,
                gpu_name=str(gpu_name),
                cuda_version=cuda_version,
            )
    except ImportError:
        pass
    return _probe_via_ctranslate2()


def _probe_via_ctranslate2() -> HardwareInfo:
    """Fallback de détection via ``ctranslate2``.

    Returns:
        ``HardwareInfo`` avec champs renseignés au mieux.
    """
    try:
        import ctranslate2  # noqa: PLC0415

        n = ctranslate2.get_cuda_device_count()
        return HardwareInfo(
            cuda_available=n > 0,
            gpu_name="" if n == 0 else f"CUDA device {0}",
            cuda_version="",
        )
    except (ImportError, AttributeError):
        return HardwareInfo(cuda_available=False, gpu_name="", cuda_version="")
