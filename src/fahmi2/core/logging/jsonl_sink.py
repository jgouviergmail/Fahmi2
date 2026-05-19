"""Sink d'écriture des LogEvent en JSON lignes (.jsonl)."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from types import TracebackType
from typing import IO

from fahmi2.core.errors.severity import Severity
from fahmi2.core.logging.event import LogEvent
from fahmi2.core.logging.sink import LogSink

_FILE_MODE = "a"
_FILE_ENCODING = "utf-8"
_LINE_BUFFERING = 1


class JsonlFileSink(LogSink):
    """Écrit chaque ``LogEvent`` sous forme d'une ligne JSON dans un fichier .jsonl.

    Thread-safe : un verrou interne sérialise les écritures concurrentes.
    Le fichier est ouvert en mode append + utf-8 + line-buffering pour limiter
    la perte de données en cas de crash. Le parent du chemin est créé si
    nécessaire.
    """

    def __init__(self, path: Path, *, min_severity: Severity = Severity.INFO) -> None:
        """Ouvre le fichier de logs.

        Args:
            path: Chemin du fichier .jsonl à écrire.
            min_severity: Sévérité plancher acceptée par le sink.
        """
        super().__init__(min_severity=min_severity)
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._fp: IO[str] | None = self._path.open(
            _FILE_MODE, encoding=_FILE_ENCODING, buffering=_LINE_BUFFERING
        )

    def _write(self, event: LogEvent) -> None:
        line = json.dumps(event.to_dict(), ensure_ascii=False, separators=(",", ":"))
        with self._lock:
            if self._fp is None:
                raise RuntimeError("JsonlFileSink is closed")
            self._fp.write(line + "\n")

    def close(self) -> None:
        """Ferme proprement le descripteur de fichier (idempotent)."""
        with self._lock:
            if self._fp is not None:
                self._fp.flush()
                self._fp.close()
                self._fp = None

    def __enter__(self) -> JsonlFileSink:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()
