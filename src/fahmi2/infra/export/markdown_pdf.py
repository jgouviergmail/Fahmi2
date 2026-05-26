"""Renderer d'export Markdown → HTML / PDF (pur, sans I/O d'orchestration).

Le HTML est un document autonome (CSS intégré, tableaux stylés, sommaire cliquable
via l'extension ``toc``). Le **PDF** rend ce même HTML via ``xhtml2pdf`` (moteur
ReportLab) : vraie pagination (listes/tableaux qui franchissent les pages), typo
CSS, orientation **paysage** optionnelle (glossaire) et largeurs de colonnes de
tableau maîtrisées. L'orchestration (collecte, dispatch par format, écriture) vit
dans ``app.document_export``.

La police PDF est une police Unicode système Windows (``Arial``), enregistrée
auprès de ReportLab. Quelques tirets Unicode rares (U+2010/2011/2012/2015) ne sont
pas rendus par ReportLab+Arial (carré ``□``) : ils sont normalisés vers
``-``/``—`` au rendu PDF (cf. ``_PDF_CHAR_REPLACEMENTS``).
"""

from __future__ import annotations

import functools
import io
import os
import re
from html import escape
from pathlib import Path

import markdown
from reportlab.lib.fonts import addMapping
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from xhtml2pdf import pisa

from fahmi2.core.errors.exceptions import ConfigError
from fahmi2.core.errors.severity import Severity
from fahmi2.core.slugify import slugify_anchor
from fahmi2.domain.enums import ExportFormat

#: Extension de fichier par format documentaire (MD/PDF/HTML ; APKG non concerné).
EXTENSION_BY_FORMAT: dict[ExportFormat, str] = {
    ExportFormat.MARKDOWN: ".md",
    ExportFormat.PDF: ".pdf",
    ExportFormat.HTML: ".html",
}

#: Extensions Python-Markdown : ``tables`` rend les tableaux pipe GFM (sinon texte
#: littéral) ; ``toc`` ajoute aux titres un ``id`` slugifié via ``slugify_anchor``
#: (cf. ``_toc_slugify``) identique aux ancres du sommaire → sommaire cliquable
#: (HTML et PDF). Mêmes extensions pour les deux formats.
_MARKDOWN_EXTENSIONS: list[str] = ["tables", "toc"]

#: Extensions pour un **fragment** HTML inline (réponse de chat, aperçu de passage) :
#: tableaux GFM, sans sommaire (``toc``) ni enveloppe de document.
_FRAGMENT_EXTENSIONS: list[str] = ["tables"]


def render_markdown_fragment(markdown_text: str) -> str:
    """Rend un fragment Markdown en HTML inline (sans document/CSS autour).

    Destiné à l'affichage dans un widget (``QTextBrowser``) : réponses du chat,
    aperçu d'un passage cité. Contrairement à :func:`render_markdown_to_html`, ne
    produit ni enveloppe ``<html>`` ni sommaire — uniquement le corps converti.

    Args:
        markdown_text: Texte Markdown.

    Returns:
        Le fragment HTML correspondant.
    """
    html_body: str = markdown.markdown(markdown_text, extensions=_FRAGMENT_EXTENSIONS)
    return html_body

#: Famille de police enregistrée auprès de ReportLab (+ noms des 4 variantes).
_PDF_FONT_FAMILY = "AppSans"
_PDF_FONT_REGULAR = "AppSans"
_PDF_FONT_BOLD = "AppSans-Bold"
_PDF_FONT_ITALIC = "AppSans-Italic"
_PDF_FONT_BOLD_ITALIC = "AppSans-BoldItalic"
_WINDOWS_FONT_FILES: dict[str, str] = {
    "": "arial.ttf",
    "B": "arialbd.ttf",
    "I": "ariali.ttf",
    "BI": "arialbi.ttf",
}

#: Caractères non rendus par ReportLab+Arial (affichés ``□``) → équivalents sûrs.
#: Em-dash (—) et en-dash (–) sont conservés (ils, eux, sont rendus correctement).
_PDF_CHAR_REPLACEMENTS = str.maketrans(
    {
        "‐": "-",  # HYPHEN
        "‑": "-",  # NON-BREAKING HYPHEN (fréquent dans les sorties LLM)
        "‒": "-",  # FIGURE DASH
        "―": "—",  # HORIZONTAL BAR → EM DASH
        "­": "",  # SOFT HYPHEN (invisible → retiré)
    }
)

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

#: Gabarit d'un document PDF (xhtml2pdf) : ``@page`` (orientation), police Arial
#: enregistrée, styles de titres/tableaux. ``{orientation}`` = ``portrait``/
#: ``landscape`` ; ``{body}`` = corps HTML rendu depuis le Markdown.
_PDF_HTML_TEMPLATE = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
@page {{ size: a4 {orientation}; margin: 1.8cm; }}
body {{ font-family: "AppSans"; font-size: 10.5pt; line-height: 1.4; color: #1f2328; }}
h1 {{ font-size: 19pt; color: #0a4f93; }}
h2 {{ font-size: 14pt; color: #0a4f93; }}
h3 {{ font-size: 12pt; color: #0a4f93; }}
h4, h5, h6 {{ font-size: 11pt; color: #0a4f93; }}
li {{ margin-bottom: 2pt; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ border: 0.5pt solid #d0d7de; padding: 3pt 5pt; text-align: left;
         vertical-align: top; }}
th {{ background: #f5f7fb; }}
a {{ color: #0a4f93; text-decoration: none; }}
</style></head><body>
{body}
</body></html>
"""

#: Découpe d'une ligne de tableau et de ses cellules (tables Markdown simples,
#: sans imbrication) pour l'aménagement PDF (remplissage des vides + largeurs).
_TABLE_ROW_RE = re.compile(r"<tr>.*?</tr>", re.DOTALL)
_TABLE_CELL_RE = re.compile(r"<(td|th)((?:\s[^>]*)?)>(.*?)</(?:td|th)>", re.DOTALL)


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


@functools.cache
def _ensure_pdf_fonts_registered() -> None:
    """Enregistre Arial (4 variantes) auprès de ReportLab, une seule fois.

    Mémoïsé (``functools.cache``) : exécuté au premier rendu PDF. ``registerFont``
    est idempotent, donc une rare double-exécution concurrente est sans effet.
    """
    fonts = _fonts_dir()
    pdfmetrics.registerFont(
        TTFont(_PDF_FONT_REGULAR, str(fonts / _WINDOWS_FONT_FILES[""]))
    )
    pdfmetrics.registerFont(
        TTFont(_PDF_FONT_BOLD, str(fonts / _WINDOWS_FONT_FILES["B"]))
    )
    pdfmetrics.registerFont(
        TTFont(_PDF_FONT_ITALIC, str(fonts / _WINDOWS_FONT_FILES["I"]))
    )
    pdfmetrics.registerFont(
        TTFont(_PDF_FONT_BOLD_ITALIC, str(fonts / _WINDOWS_FONT_FILES["BI"]))
    )
    addMapping(_PDF_FONT_FAMILY, 0, 0, _PDF_FONT_REGULAR)
    addMapping(_PDF_FONT_FAMILY, 1, 0, _PDF_FONT_BOLD)
    addMapping(_PDF_FONT_FAMILY, 0, 1, _PDF_FONT_ITALIC)
    addMapping(_PDF_FONT_FAMILY, 1, 1, _PDF_FONT_BOLD_ITALIC)


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


def _toc_slugify(value: str, separator: str) -> str:
    """Slugify de l'extension ``toc`` : aligne les ids de titres sur les ancres.

    L'extension ``toc`` appelle ``slugify(value, separator)`` ; on délègue à
    ``slugify_anchor`` (séparateur ignoré, toujours ``-``) pour que les ids de
    titres correspondent exactement aux ancres du sommaire du consolidé.

    Args:
        value: Texte du titre.
        separator: Séparateur proposé par l'extension (ignoré).

    Returns:
        Le slug d'ancre.
    """
    del separator
    return slugify_anchor(value)


def render_markdown_to_html(markdown_text: str, output_path: Path) -> None:
    """Rend un Markdown en document HTML autonome (UTF-8, style intégré).

    Aucune police système n'est requise — le fichier est ouvrable dans n'importe
    quel navigateur. Les titres reçoivent un ``id`` slugifié (extension ``toc``) →
    le sommaire du consolidé est cliquable.

    Args:
        markdown_text: Texte Markdown (commençant idéalement par un titre H1).
        output_path: Chemin du fichier ``.html`` à écrire.
    """
    body = markdown.markdown(
        markdown_text,
        extensions=_MARKDOWN_EXTENSIONS,
        extension_configs={"toc": {"slugify": _toc_slugify}},
    )
    document = _HTML_DOCUMENT_TEMPLATE.format(
        title=escape(_extract_title(markdown_text)), body=body
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(document, encoding="utf-8")


def _normalize_for_pdf(text: str) -> str:
    """Remplace les caractères non rendus par ReportLab+Arial par des équivalents.

    Args:
        text: Texte Markdown source.

    Returns:
        Le texte avec tirets Unicode problématiques normalisés.
    """
    return text.translate(_PDF_CHAR_REPLACEMENTS)


def _layout_table_cells(body: str, column_widths: tuple[str, ...] | None) -> str:
    """Aménage les cellules de tableau pour un rendu PDF correct (xhtml2pdf).

    - Remplit les cellules **vides** d'un espace insécable : sinon xhtml2pdf
      effondre la colonne et le contenu des autres lignes déborde.
    - Si ``column_widths`` est fourni, applique une largeur à **chaque** cellule
      selon sa position de colonne (xhtml2pdf n'honore ni ``<colgroup>`` ni la
      largeur sur le seul en-tête).

    Args:
        body: Corps HTML rendu depuis le Markdown.
        column_widths: Largeurs CSS par colonne (ex: ``("20%", "12%", …)``), ou
            ``None`` (cellules vides comblées, sans largeur imposée).

    Returns:
        Le corps HTML avec les tableaux aménagés.
    """

    def _fix_row(row_match: re.Match[str]) -> str:
        column_index = [0]

        def _fix_cell(cell_match: re.Match[str]) -> str:
            tag, attrs, content = cell_match.group(1, 2, 3)
            if not content.strip():
                content = "&nbsp;"
            width_attr = ""
            if column_widths is not None and column_index[0] < len(column_widths):
                width_attr = f' width="{column_widths[column_index[0]]}"'
            column_index[0] += 1
            return f"<{tag}{attrs}{width_attr}>{content}</{tag}>"

        return _TABLE_CELL_RE.sub(_fix_cell, row_match.group(0))

    return _TABLE_ROW_RE.sub(_fix_row, body)


def render_markdown_to_pdf(
    markdown_text: str,
    output_path: Path,
    *,
    landscape: bool = False,
    table_column_widths: tuple[str, ...] | None = None,
) -> None:
    """Rend un Markdown en PDF via ``xhtml2pdf`` (Markdown → HTML → PDF).

    Args:
        markdown_text: Texte Markdown.
        output_path: Chemin du PDF à écrire.
        landscape: Orientation paysage (ex: glossaire large) ; portrait sinon.
        table_column_widths: Largeurs CSS par colonne appliquées aux tableaux
            (ex: glossaire). ``None`` = largeurs automatiques.

    Raises:
        ConfigError: ``EXPORT.NO_PDF_FONT`` si la police Arial est introuvable, ou
            ``EXPORT.PDF_RENDER_FAILED`` si le moteur de rendu échoue.
    """
    if not pdf_fonts_available():
        raise ConfigError(
            code="EXPORT.NO_PDF_FONT",
            user_message=(
                "Aucune police Unicode trouvée pour l'export PDF. Utilisez "
                "l'export Markdown ou HTML."
            ),
            severity=Severity.ERROR,
        )
    _ensure_pdf_fonts_registered()
    body = markdown.markdown(
        _normalize_for_pdf(markdown_text),
        extensions=_MARKDOWN_EXTENSIONS,
        extension_configs={"toc": {"slugify": _toc_slugify}},
    )
    body = _layout_table_cells(body, table_column_widths)
    document = _PDF_HTML_TEMPLATE.format(
        orientation="landscape" if landscape else "portrait", body=body
    )
    buffer = io.BytesIO()
    status = pisa.CreatePDF(document, dest=buffer, encoding="utf-8")
    if status.err:
        raise ConfigError(
            code="EXPORT.PDF_RENDER_FAILED",
            user_message="Le rendu du PDF a échoué. Utilisez l'export Markdown ou HTML.",
            severity=Severity.ERROR,
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(buffer.getvalue())
