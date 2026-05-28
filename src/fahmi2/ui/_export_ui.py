"""Helper UI partagé pour l'export documentaire (génération & pédagogie).

Deux fonctions réutilisables par les contrôleurs :

- ``choose_export_format`` : propose les formats configurés (ou message si aucun).
- ``run_document_export`` : sélectionne un dossier, exécute l'export, gère les
  erreurs, journalise et notifie.

Le routage spécifique (ex. APKG côté pédagogie) reste dans chaque contrôleur.

i18n : ``pyside6-lupdate`` n'extrait pas les chaînes passées à un wrapper de
fonction → on appelle directement
``QCoreApplication.translate("ExportUI", "literal source")`` partout.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QFileDialog, QInputDialog, QMessageBox, QWidget

from fahmi2.app.document_export import DocumentExportResult
from fahmi2.core.errors.exceptions import Fahmi2Error
from fahmi2.core.errors.severity import Severity
from fahmi2.core.logging.event import LogEvent
from fahmi2.domain.enums import ExportFormat
from fahmi2.ui.widgets.logs_dock import LogsDock

_LOG_CODE = "DOCUMENTS_EXPORTED"


def choose_export_format(
    *,
    window: QWidget,
    configured_formats: frozenset[ExportFormat],
    label_by_format: dict[ExportFormat, str],
) -> ExportFormat | None:
    """Demande à l'utilisateur de choisir un format parmi ceux configurés."""
    formats = [fmt for fmt in ExportFormat if fmt in configured_formats]
    if not formats:
        QMessageBox.information(
            window,
            QCoreApplication.translate("ExportUI", "Aucun format d'export"),
            QCoreApplication.translate(
                "ExportUI",
                "Aucun format d'export n'est sélectionné dans les réglages "
                "(⚙ Réglages → Export).",
            ),
        )
        return None
    by_label = {label_by_format[fmt]: fmt for fmt in formats}
    choice, ok = QInputDialog.getItem(
        window,
        QCoreApplication.translate("ExportUI", "Exporter"),
        QCoreApplication.translate("ExportUI", "Format :"),
        list(by_label),
        0,
        editable=False,
    )
    if not ok:
        return None
    return by_label[choice]


def run_document_export(
    *,
    window: QWidget,
    logs_dock: LogsDock,
    label: str,
    exporter: Callable[[Path], DocumentExportResult],
) -> None:
    """Sélectionne un dossier, exécute l'export, gère erreurs + log + message."""
    directory = QFileDialog.getExistingDirectory(
        window,
        QCoreApplication.translate("ExportUI", "Dossier d'export {label}").format(
            label=label
        ),
    )
    if not directory:
        return
    try:
        result = exporter(Path(directory))
    except Fahmi2Error as exc:
        QMessageBox.critical(
            window,
            QCoreApplication.translate("ExportUI", "Export impossible"),
            f"{exc.code}\n\n{exc.user_message}",
        )
        return
    except Exception as exc:  # noqa: BLE001 — affichage UX puis stop
        QMessageBox.critical(
            window,
            QCoreApplication.translate("ExportUI", "Erreur inattendue"),
            f"{type(exc).__name__} : {exc}",
        )
        return
    if result.document_count == 0:
        QMessageBox.information(
            window,
            QCoreApplication.translate("ExportUI", "Rien à exporter"),
            QCoreApplication.translate(
                "ExportUI",
                "Aucun document à exporter. Lancez d'abord la génération pour "
                "ce projet.",
            ),
        )
        return
    logs_dock.append_event(
        LogEvent(
            timestamp=datetime.now(tz=UTC),
            severity=Severity.INFO,
            code=_LOG_CODE,
            message=(
                f"{result.document_count} document(s) {label} exporté(s) vers "
                f"{directory}"
            ),
        )
    )
    QMessageBox.information(
        window,
        QCoreApplication.translate("ExportUI", "Export terminé"),
        QCoreApplication.translate(
            "ExportUI",
            "{count} document(s) {label} exporté(s) dans :\n{directory}",
        ).format(count=result.document_count, label=label, directory=directory),
    )
