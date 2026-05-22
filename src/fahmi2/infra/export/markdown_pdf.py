"""Renderer d'export Markdown / PDF / HTML (pur, sans I/O d'orchestration).

Rend un Markdown **déjà produit** en PDF (via ``markdown`` → HTML →
``fpdf2.write_html``) ou en document HTML autonome (UTF-8, feuille de style
intégrée), et expose la table d'extensions par format. L'orchestration (collecte
des documents, dispatch par format, écriture) vit dans ``app.document_export``.
La police PDF est une police Unicode système Windows (``Arial``) : les polices
cœur de fpdf2 sont latin-1 et lèvent sur les caractères typographiques français
(« — », « … »).

Limite connue : ``fpdf2.write_html`` rend les blocs de code (``<pre>``/``<code>``)
avec sa police monospace cœur (latin-1). Les rendus de supports pédagogiques n'en
produisent pas ; un éventuel bloc de code (issu d'un chapitre) contenant des
caractères non latin-1 pourrait faire échouer le rendu PDF (l'export Markdown
reste alors disponible).
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from html import escape
from pathlib import Path

import markdown
from fpdf import FPDF
from fpdf.fonts import TextStyle

from fahmi2.core.errors.exceptions import ConfigError
from fahmi2.core.errors.severity import Severity
from fahmi2.domain.enums import ExportFormat

#: Extension de fichier par format documentaire (MD/PDF/HTML ; APKG non concerné).
EXTENSION_BY_FORMAT: dict[ExportFormat, str] = {
    ExportFormat.MARKDOWN: ".md",
    ExportFormat.PDF: ".pdf",
    ExportFormat.HTML: ".html",
}

#: Couleur des titres PDF — noir (au lieu du rouge ``#960000`` par défaut de fpdf2).
_PDF_HEADING_COLOR = "#000000"
#: Couleur des puces PDF — gris foncé (au lieu du rouge par défaut de fpdf2).
_PDF_LI_PREFIX_COLOR = "#1f2328"
#: Tailles de titre par niveau (pt) — reprend les tailles par défaut de fpdf2.
_PDF_HEADING_SIZES_PT: dict[str, float] = {
    "h1": 24.0,
    "h2": 18.0,
    "h3": 14.0,
    "h4": 12.0,
    "h5": 10.0,
    "h6": 8.0,
}
#: Marges verticales (mm) des titres PDF.
_PDF_HEADING_TOP_MARGIN = 5.0
_PDF_HEADING_BOTTOM_MARGIN = 0.4

_PDF_FONT_FAMILY = "AppSans"
_PDF_FONT_SIZE = 11

#: Extensions Python-Markdown activées au rendu : ``tables`` rend les tableaux
#: pipe GFM (sinon ils restent du texte littéral, en HTML comme en PDF).
_MARKDOWN_EXTENSIONS: list[str] = ["tables"]

#: Liens d'ancre **internes** (``<a href="#...">``) : ``fpdf2.write_html`` exige une
#: destination enregistrée via ``set_link`` (sinon ``FPDFException``). Au rendu PDF
#: on neutralise ces liens en conservant leur texte (un sommaire en texte simple
#: reste lisible ; le PDF ne porte pas de table d'ancres). Les liens externes
#: (``http(s)://``) ne sont pas concernés.
_INTERNAL_ANCHOR_RE = re.compile(r'<a href="#[^"]*">(.*?)</a>', re.DOTALL)

#: Styles PDF des listes : ``fpdf2`` rend les puces/numéros sans ``font_size_pt``
#: explicite à une taille erronée (numéros géants). On force la taille du corps et
#: une marge d'item pour un rendu aéré et homogène.
_PDF_LIST_INDENT = 5.0
_PDF_LIST_ITEM_TOP_MARGIN = 1.0
_PDF_LIST_ITEM_BOTTOM_MARGIN = 1.0
_PDF_LIST_BLOCK_TOP_MARGIN = 2.0

#: Préfixe Markdown d'un titre H1 (pour extraire le titre du document HTML).
_MD_H1_PREFIX = "# "
#: Titre HTML par défaut si le Markdown ne commence pas par un H1.
_HTML_DEFAULT_TITLE = "Supports de révision"
#: Gabarit d'un document HTML autonome (UTF-8 + feuille de style intégrée).
_HTML_DOCUMENT_TEMPLATE = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
body {{ font-family: "Segoe UI", system-ui, sans-serif; max-width: 820px;
        margin: 2rem auto; padding: 0 1rem; line-height: 1.6; color: #1f2328; }}
h1, h2, h3 {{ color: #0a4f93; }}
code, pre {{ background: #f5f7fb; border-radius: 4px; padding: 0.1em 0.3em; }}
hr {{ border: none; border-top: 1px solid #e5e7eb; margin: 2rem 0; }}
table {{ border-collapse: collapse; width: 100%; margin: 1rem 0; }}
th, td {{ border: 1px solid #d0d7de; padding: 0.4em 0.6em; text-align: left;
         vertical-align: top; }}
th {{ background: #f5f7fb; }}
</style>
</head>
<body>
{body}
</body>
</html>
"""
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


def _extract_title(markdown_text: str) -> str:
    """Extrait le titre H1 d'un Markdown (pour le ``<title>`` HTML).

    Args:
        markdown_text: Texte Markdown.

    Returns:
        Le texte du premier titre H1, ou un titre par défaut.
    """
    for line in markdown_text.splitlines():
        if line.startswith(_MD_H1_PREFIX):
            return line[len(_MD_H1_PREFIX) :].strip()
    return _HTML_DEFAULT_TITLE


def render_markdown_to_html(markdown_text: str, output_path: Path) -> None:
    """Rend un Markdown en document HTML autonome (UTF-8, style intégré).

    Contrairement au PDF, aucune police système n'est requise — le fichier est
    ouvrable dans n'importe quel navigateur.

    Args:
        markdown_text: Texte Markdown (commençant idéalement par un titre H1).
        output_path: Chemin du fichier ``.html`` à écrire.
    """
    body = markdown.markdown(markdown_text, extensions=_MARKDOWN_EXTENSIONS)
    document = _HTML_DOCUMENT_TEMPLATE.format(
        title=escape(_extract_title(markdown_text)), body=body
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(document, encoding="utf-8")


def _pdf_tag_styles() -> dict[str, TextStyle]:
    """Styles PDF des titres **et des listes** passés à ``write_html``.

    - Titres : **noir gras** (au lieu du rouge fpdf2 par défaut), tailles standard.
    - Listes (``li``/``ol``/``ul``) : ``font_size_pt`` du corps **explicite** —
      fpdf2 rend sinon les numéros/puces à une taille erronée (numéros géants) — et
      des marges d'item pour un rendu aéré.

    ``TextStyle`` n'exposant pas ses champs en lecture, les styles sont reconstruits
    plutôt que dérivés des défauts.

    Returns:
        Mapping ``tag → TextStyle`` à passer à ``write_html``.
    """
    styles: dict[str, TextStyle] = {
        tag: TextStyle(
            font_style="B",
            font_size_pt=size,
            color=_PDF_HEADING_COLOR,
            t_margin=_PDF_HEADING_TOP_MARGIN,
            b_margin=_PDF_HEADING_BOTTOM_MARGIN,
        )
        for tag, size in _PDF_HEADING_SIZES_PT.items()
    }
    styles["li"] = TextStyle(
        font_size_pt=_PDF_FONT_SIZE,
        l_margin=_PDF_LIST_INDENT,
        t_margin=_PDF_LIST_ITEM_TOP_MARGIN,
        b_margin=_PDF_LIST_ITEM_BOTTOM_MARGIN,
    )
    styles["ol"] = TextStyle(
        font_size_pt=_PDF_FONT_SIZE, t_margin=_PDF_LIST_BLOCK_TOP_MARGIN
    )
    styles["ul"] = TextStyle(
        font_size_pt=_PDF_FONT_SIZE, t_margin=_PDF_LIST_BLOCK_TOP_MARGIN
    )
    return styles


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
    html = markdown.markdown(markdown_text, extensions=_MARKDOWN_EXTENSIONS)
    html = _INTERNAL_ANCHOR_RE.sub(r"\1", html)
    pdf.write_html(
        html,
        tag_styles=_pdf_tag_styles(),
        li_prefix_color=_PDF_LI_PREFIX_COLOR,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(output_path))
