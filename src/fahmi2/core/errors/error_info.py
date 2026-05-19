"""Représentation sérialisable d'une erreur, utilisée par les logs et l'UI."""

from __future__ import annotations

import traceback as tb_module
from dataclasses import dataclass, field
from typing import Any

from fahmi2.core.errors.exceptions import Fahmi2Error
from fahmi2.core.errors.severity import Severity

_UNEXPECTED_CODE_PREFIX = "UNEXPECTED."


@dataclass(frozen=True)
class ErrorInfo:
    """Snapshot immuable et sérialisable d'une erreur survenue dans l'app.

    Attributes:
        code: Identifiant stable de l'erreur.
        user_message: Message localisé destiné à l'UI.
        severity: Niveau de gravité.
        technical_details: Métadonnées additionnelles (logs uniquement).
        traceback: Représentation textuelle de la stack trace, ou ``None``.
    """

    code: str
    user_message: str
    severity: Severity
    technical_details: dict[str, Any] = field(default_factory=dict)
    traceback: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Sérialise au format dict JSON-friendly.

        Returns:
            Dictionnaire des attributs encodable JSON.
        """
        return {
            "code": self.code,
            "user_message": self.user_message,
            "severity": str(self.severity),
            "technical_details": dict(self.technical_details),
            "traceback": self.traceback,
        }

    @classmethod
    def from_exception(cls, exc: BaseException) -> ErrorInfo:
        """Construit un ErrorInfo à partir d'une exception.

        Pour les ``Fahmi2Error``, on récupère directement les attributs.
        Pour les autres, on dérive un code générique et on capture le traceback.

        Args:
            exc: Exception capturée.

        Returns:
            Un ``ErrorInfo`` reflétant l'exception.
        """
        tb = "".join(tb_module.format_exception(type(exc), exc, exc.__traceback__))

        if isinstance(exc, Fahmi2Error):
            return cls(
                code=exc.code,
                user_message=exc.user_message,
                severity=exc.severity,
                technical_details=dict(exc.technical_details),
                traceback=tb,
            )

        return cls(
            code=f"{_UNEXPECTED_CODE_PREFIX}{type(exc).__name__.upper()}",
            user_message=str(exc) or type(exc).__name__,
            severity=Severity.ERROR,
            technical_details={"exception_type": type(exc).__name__},
            traceback=tb,
        )
