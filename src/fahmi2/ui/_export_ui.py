"""Helper UI partagé pour l'export documentaire (génération & pédagogie).

Deux fonctions réutilisables par les contrôleurs :

- ``choose_export_format`` : propose les formats configurés (ou message si aucun).
- ``run_document_export`` : sélectionne un dossier, exécute l'export, gère les
  erreurs, journalise et notifie.

Le routage spécifique (ex. APKG côté pédagogie) reste dans chaque contrôleur.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QInputDialog, QMessageBox, QWidget

from fahmi2.app.document_export import DocumentExportResult
from fahmi2.core.errors.exceptions import Fahmi2Error
from fahmi2.core.errors.severity import Severity
from fahmi2.core.logging.event import LogEvent
from fahmi2.domain.enums import ExportFormat
from fahmi2.ui.widgets.logs_dock import LogsDock

_NO_FORMAT_TITLE = "Aucun format d'export"
_NO_FORMAT_BODY = (
    "Aucun format d'export n'est sélectionné dans les réglages "
    "(⚙ Réglages → Export)."
)
_PICK_TITLE = "Exporter"
_PICK_LABEL = "Format :"
_EMPTY_TITLE = "Rien à exporter"
_EMPTY_BODY = (
    "Aucun document à exporter. Lancez d'abord la génération pour ce projet."
)
_DONE_TITLE = "Export terminé"
_FAIL_TITLE = "Export impossible"
_UNEXPECTED_TITLE = "Erreur inattendue"
_LOG_CODE = "DOCUMENTS_EXPORTED"


def choose_export_format(
    *,
    window: QWidget,
    configured_formats: frozenset[ExportFormat],
    label_by_format: dict[ExportFormat, str],
) -> ExportFormat | None:
    """Demande à l'utilisateur de choisir un format parmi ceux configurés.

    Args:
        window: Fenêtre parente des dialogues.
        configured_formats: Formats cochés dans les réglages.
        label_by_format: Libellés humains par format.

    Returns:
        Le format choisi, ou ``None`` (aucun configuré / annulation).
    """
    formats = [fmt for fmt in ExportFormat if fmt in configured_formats]
    if not formats:
        QMessageBox.information(window, _NO_FORMAT_TITLE, _NO_FORMAT_BODY)
        return None
    by_label = {label_by_format[fmt]: fmt for fmt in formats}
    choice, ok = QInputDialog.getItem(
        window, _PICK_TITLE, _PICK_LABEL, list(by_label), 0, editable=False
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
    """Sélectionne un dossier, exécute l'export, gère erreurs + log + message.

    Args:
        window: Fenêtre parente des dialogues.
        logs_dock: Dock de logs (journalise le succès).
        label: Libellé humain du format (messages).
        exporter: ``(output_dir) -> DocumentExportResult``.
    """
    directory = QFileDialog.getExistingDirectory(window, f"Dossier d'export {label}")
    if not directory:
        return
    try:
        result = exporter(Path(directory))
    except Fahmi2Error as exc:
        QMessageBox.critical(window, _FAIL_TITLE, f"{exc.code}\n\n{exc.user_message}")
        return
    except Exception as exc:  # noqa: BLE001 — affichage UX puis stop
        QMessageBox.critical(
            window, _UNEXPECTED_TITLE, f"{type(exc).__name__} : {exc}"
        )
        return
    if result.document_count == 0:
        QMessageBox.information(window, _EMPTY_TITLE, _EMPTY_BODY)
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
        _DONE_TITLE,
        f"{result.document_count} document(s) {label} exporté(s) dans :\n{directory}",
    )
