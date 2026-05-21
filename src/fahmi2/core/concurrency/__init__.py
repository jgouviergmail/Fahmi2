"""Primitifs de concurrence transverses (sans Qt, HTTP ni SQL)."""

from __future__ import annotations

from fahmi2.core.concurrency._executor import map_bounded

__all__ = ["map_bounded"]
