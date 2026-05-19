"""Tests de probe_hardware."""

from dataclasses import FrozenInstanceError

import pytest

from fahmi2.app.hardware_probe import HardwareInfo, probe_hardware


def test_hardware_info_is_immutable() -> None:
    info = HardwareInfo(cuda_available=False, gpu_name="", cuda_version="")
    with pytest.raises(FrozenInstanceError):
        info.cuda_available = True  # type: ignore[misc]


def test_probe_returns_hardware_info() -> None:
    info = probe_hardware()
    assert isinstance(info, HardwareInfo)
    assert isinstance(info.cuda_available, bool)
    assert isinstance(info.gpu_name, str)
    assert isinstance(info.cuda_version, str)
