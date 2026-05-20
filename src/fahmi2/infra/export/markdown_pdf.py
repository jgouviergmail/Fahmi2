"""Adapter d'export Markdown / PDF des supports pédagogiques.

L'export réutilise le Markdown **déjà rendu** par les générateurs : ce module
assemble les documents agrégés et rend le PDF via ``markdown`` → HTML →
``fpdf2.write_html``. La police PDF est une police Unicode système Windows
(``Arial``) : les polices cœur de fpdf2 sont latin-1 et lèvent sur les
caractères typographiques français (« — », « … »).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import markdown
from fpdf import FPDF

from fahmi2.core.errors.exceptions import ConfigError
from fahmi2.core.errors.severity import Severity

_SECTION_SEPARATOR = "\n\n---\n\n"
_EMPTY_BODY = "_Aucun support à exporter._"
_PDF_FONT_FAMILY = "AppSans"
_PDF_FONT_SIZE = 11
_WINDOWS_FONT_FILES: dict[str, str] = {
    "": "arial.ttf",
    "B": "arialbd.ttf",
    "I": "ariali.ttf",
    "BI": "arialbi.ttf",
}


def _fonts_dir() -> Path:
    """Dossier des polices système Windows.

    Returns:
        ``%SystemRoot%\\Fonts`` (``C:\\Windows\\Fonts`` par défaut).
    """
    return Path(os.environ.get("SystemRoot", r"C:\Windows")) / "Fonts"


def pdf_fonts_available() -> bool:
    """Indique si la police Unicode (Arial régulier) est résolue.

    Returns:
        ``True`` si le rendu PDF est possible.
    """
    return (_fonts_dir() / _WINDOWS_FONT_FILES[""]).exists()


def assemble_markdown(title: str, bodies: tuple[str, ...]) -> str:
    """Assemble un document Markdown agrégé (titre + corps).

    Args:
        title: Titre du document.
        bodies: Corps Markdown déjà rendus (chacun porte son propre titre).

    Returns:
        Le Markdown agrégé.
    """
    if not bodies:
        return f"# {title}\n\n{_EMPTY_BODY}\n"
    return f"# {title}\n\n" + _SECTION_SEPARATOR.join(bodies) + "\n"


@dataclass(frozen=True)
class _PdfFonts:
    """Chemins des 4 variantes de police pour le rendu PDF."""

    regular: Path
    bold: Path
    italic: Path
    bold_italic: Path


def _resolve_pdf_fonts() -> _PdfFonts | None:
    """Résout les 4 variantes Arial, ou ``None`` si la régulière est absente.

    Returns:
        Les chemins de police, ou ``None``.
    """
    fonts = _fonts_dir()
    regular = fonts / _WINDOWS_FONT_FILES[""]
    if not regular.exists():
        return None
    return _PdfFonts(
        regular=regular,
        bold=fonts / _WINDOWS_FONT_FILES["B"],
        italic=fonts / _WINDOWS_FONT_FILES["I"],
        bold_italic=fonts / _WINDOWS_FONT_FILES["BI"],
    )


def render_markdown_to_pdf(markdown_text: str, output_path: Path) -> None:
    """Rend un Markdown en PDF (``markdown`` → HTML → ``fpdf2``).

    Args:
        markdown_text: Texte Markdown.
        output_path: Chemin du PDF à écrire.

    Raises:
        ConfigError: ``EXPORT.NO_PDF_FONT`` si aucune police Unicode n'est résolue.
    """
    fonts = _resolve_pdf_fonts()
    if fonts is None:
        raise ConfigError(
            code="EXPORT.NO_PDF_FONT",
            user_message=(
                "Aucune police Unicode trouvée pour l'export PDF. Utilisez "
                "l'export Markdown."
            ),
            severity=Severity.ERROR,
        )
    pdf = FPDF()
    pdf.add_font(_PDF_FONT_FAMILY, "", str(fonts.regular))
    pdf.add_font(_PDF_FONT_FAMILY, "B", str(fonts.bold))
    pdf.add_font(_PDF_FONT_FAMILY, "I", str(fonts.italic))
    pdf.add_font(_PDF_FONT_FAMILY, "BI", str(fonts.bold_italic))
    pdf.add_page()
    pdf.set_font(_PDF_FONT_FAMILY, size=_PDF_FONT_SIZE)
    pdf.write_html(markdown.markdown(markdown_text))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(output_path))
