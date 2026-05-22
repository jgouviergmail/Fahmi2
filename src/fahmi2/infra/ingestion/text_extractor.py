"""Extraction de texte brut depuis un document (pdf, docx, md, txt).

Port ``TextExtractor`` + implémentation par défaut. La structure (sauts de
ligne / paragraphes) est **préservée** : l'aval (reformulation ou pass-through)
reçoit le texte tel quel.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from fahmi2.core.errors.exceptions import IngestionError
from fahmi2.core.errors.severity import Severity

_PDF_PAGE_SEPARATOR = "\n\n"
_DOCX_PARAGRAPH_SEPARATOR = "\n"
_ENCODING_UTF8 = "utf-8"
_PLAIN_TEXT_SUFFIXES = frozenset({".md", ".txt"})
_PDF_SUFFIX = ".pdf"
_DOCX_SUFFIX = ".docx"


class TextExtractor(Protocol):
    """Extrait le texte brut d'un document."""

    def extract(self, path: Path) -> str:
        """Retourne le texte brut du document.

        Args:
            path: Chemin du document.

        Returns:
            Le texte extrait (structure préservée).

        Raises:
            IngestionError: ``INGESTION.TEXT_EXTRACTION_FAILED`` si le document
                est illisible ou de format non géré.
        """


class DefaultTextExtractor:
    """Extracteur par défaut : pypdf (pdf), python-docx (docx), lecture directe (md/txt)."""

    def extract(self, path: Path) -> str:
        """Extrait le texte selon l'extension du document.

        Args:
            path: Chemin du document.

        Returns:
            Le texte extrait.

        Raises:
            IngestionError: ``INGESTION.TEXT_EXTRACTION_FAILED`` si le format
                n'est pas géré ou si l'extraction échoue.
        """
        suffix = path.suffix.lower()
        try:
            if suffix in _PLAIN_TEXT_SUFFIXES:
                return path.read_text(encoding=_ENCODING_UTF8)
            if suffix == _PDF_SUFFIX:
                return self._extract_pdf(path)
            if suffix == _DOCX_SUFFIX:
                return self._extract_docx(path)
        except IngestionError:
            raise
        except Exception as exc:  # noqa: BLE001 — toute erreur lib → IngestionError
            raise _extraction_error(path, str(exc)) from exc
        raise _extraction_error(path, f"format non géré : {suffix}")

    @staticmethod
    def _extract_pdf(path: Path) -> str:
        """Extrait le texte d'un PDF via pypdf (pages séparées par double saut)."""
        from pypdf import PdfReader  # noqa: PLC0415 — import paresseux (dépendance lourde)

        reader = PdfReader(str(path))
        return _PDF_PAGE_SEPARATOR.join(
            (page.extract_text() or "") for page in reader.pages
        )

    @staticmethod
    def _extract_docx(path: Path) -> str:
        """Extrait le texte d'un .docx via python-docx (paragraphes joints)."""
        from docx import Document  # noqa: PLC0415 — import paresseux

        document = Document(str(path))
        return _DOCX_PARAGRAPH_SEPARATOR.join(p.text for p in document.paragraphs)


def _extraction_error(path: Path, detail: str) -> IngestionError:
    """Construit l'erreur d'extraction de texte.

    Args:
        path: Document concerné.
        detail: Détail technique.

    Returns:
        L'``IngestionError`` à lever.
    """
    return IngestionError(
        code="INGESTION.TEXT_EXTRACTION_FAILED",
        user_message=f"Impossible d'extraire le texte du document : {path.name}",
        severity=Severity.ERROR,
        technical_details={"path": str(path), "detail": detail},
    )
