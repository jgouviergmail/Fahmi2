"""Renderer d'export Markdown → HTML / PDF (pur, sans I/O d'orchestration).

Le corps HTML est rendu **une fois** par :func:`render_markdown_body` (extensions
``tables`` + ``toc``), réutilisé tel quel par l'export HTML, par l'export PDF et par
l'export DOCX (``markdown_docx``). Le HTML est un document autonome (CSS intégré,
sommaire cliquable via ``toc``). Le **PDF** rend ce même corps via ``xhtml2pdf``
(moteur ReportLab) : vraie pagination, typo CSS, orientation **paysage** optionnelle
(glossaire) et largeurs de colonnes maîtrisées. L'orchestration (collecte, dispatch
par format, écriture) vit dans ``app.document_export``.

**Police PDF par langue** (toutes système Windows, rien à bundler) : latin
(fr/en/de/es/it) → ``Arial`` (résolu en Helvetica par xhtml2pdf, couvre le Latin-1) ;
**chinois** → ``Microsoft YaHei`` (``msyh.ttc``, chargé via ``subfontIndex`` et injecté
dans ``xhtml2pdf.default.DEFAULT_FONT`` ; garde ``EXPORT.NO_CJK_FONT`` si absente). Le
chinois s'écrivant **sans espaces** (ReportLab ne coupe qu'aux espaces), la prose CJK est
**pré-coupée** par ``<br/>`` (cf. ``_prewrap_cjk_runs``) et les cellules de tableau par la
règle CSS ``-pdf-word-wrap: CJK`` — sinon le texte déborderait de la marge ;
**arabe** → ``Arial`` (glyphes arabes) + ``direction:rtl`` + tag ``pdf:language`` qui
déclenche le reshaping contextuel et la bidi. Quelques tirets Unicode rares
(U+2010/2011/2012/2015) non rendus par ReportLab+Arial (carré ``□``) sont normalisés
vers ``-``/``—`` au rendu PDF (cf. ``_PDF_CHAR_REPLACEMENTS``) ; plus généralement, tout
caractère **sans glyphe** dans la police active (émojis décoratifs 📖/📝/💡/🎯…) est
**retiré** avant rendu (cf. ``_strip_unrenderable_for_pdf``) — ReportLab le dessinerait
en carré. HTML et DOCX conservent ces caractères (repli natif du navigateur/Word).
"""

from __future__ import annotations

import functools
import io
import os
import re
import unicodedata
from html import escape
from pathlib import Path

import markdown
from bs4 import BeautifulSoup
from bs4.element import NavigableString
from reportlab.lib.fonts import addMapping
from reportlab.lib.pagesizes import A4
from reportlab.lib.textsplit import wordSplit
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from xhtml2pdf import default as xhtml2pdf_default
from xhtml2pdf import pisa

from fahmi2.core.errors.exceptions import ConfigError
from fahmi2.core.errors.severity import Severity
from fahmi2.core.slugify import slugify_anchor
from fahmi2.domain.enums import ExportFormat, Language

#: Extension de fichier par format documentaire (MD/PDF/HTML ; APKG non concerné).
EXTENSION_BY_FORMAT: dict[ExportFormat, str] = {
    ExportFormat.MARKDOWN: ".md",
    ExportFormat.PDF: ".pdf",
    ExportFormat.HTML: ".html",
    ExportFormat.DOCX: ".docx",
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

#: Police CJK système Windows (TrueType Collection) — Microsoft YaHei (régulier +
#: gras). Chargée via ``subfontIndex`` (ReportLab gère ainsi les TTC) puis injectée
#: dans la table de résolution de xhtml2pdf pour rendre le chinois.
_CJK_FONT_FILE_REGULAR = "msyh.ttc"
_CJK_FONT_FILE_BOLD = "msyhbd.ttc"
_CJK_FONT_NAME = "CJKFont"
_CJK_FONT_NAME_BOLD = "CJKFont-Bold"
#: Familles ``font-family`` injectées dans ``xhtml2pdf.default.DEFAULT_FONT``.
_CJK_FAMILY = "cjk"
_ARABIC_FAMILY = "arab"
#: Tag xhtml2pdf déclenchant le reshaping + bidi de l'arabe (cf. xhtml2pdf/util.py).
_PDF_LANGUAGE_TAG_ARABIC = '<pdf:language name="arabic"/>'

#: Directions d'écriture CSS et langues écrites de droite à gauche (source unique
#: partagée par les rendus PDF et HTML).
_DIRECTION_LTR = "ltr"
_DIRECTION_RTL = "rtl"
_RTL_LANGUAGES: frozenset[Language] = frozenset({Language.AR})

#: Famille par défaut (latin) : ``AppSans`` est résolu en Helvetica par xhtml2pdf,
#: qui couvre le Latin-1 (fr/en/de/es/it). Pas de police à embarquer.
_PDF_DEFAULT_FAMILY = _PDF_FONT_FAMILY

#: Rendu PDF par langue spécifique : (famille ``font-family``, tag ``pdf:language``).
#: Les langues absentes utilisent le défaut latin (Helvetica, sans tag). La
#: direction d'écriture est dérivée séparément via :func:`_text_direction`.
_PDF_LANG_RENDERING: dict[Language, tuple[str, str]] = {
    Language.ZH: (_CJK_FAMILY, ""),
    Language.AR: (_ARABIC_FAMILY, _PDF_LANGUAGE_TAG_ARABIC),
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

#: Catégories Unicode des caractères **conservés** même absents de la police : codes
#: de contrôle (``\n``, ``\t``), formats (ZWJ/ZWNJ/RLM/LRM — indispensables à la
#: jonction et à la bidi arabes) et séparateurs d'espace. Tout autre caractère absent
#: de la police active (émojis…) est retiré au rendu PDF, car ReportLab le dessine en
#: carré ``□`` (pas de repli de police par glyphe, pas d'émojis couleur).
_PDF_KEPT_UNRENDERABLE_CATEGORIES: frozenset[str] = frozenset(
    {"Cc", "Cf", "Zs", "Zl", "Zp"}
)

#: Préfixe Markdown d'un titre H1 (pour extraire le titre du document HTML).
_MD_H1_PREFIX = "# "
#: Titre HTML par défaut si le Markdown ne commence pas par un H1.
_HTML_DEFAULT_TITLE = "Supports de révision"

#: Gabarit d'un document HTML autonome (UTF-8 + feuille de style intégrée).
_HTML_DOCUMENT_TEMPLATE = """<!DOCTYPE html>
<html lang="{lang}" dir="{direction}">
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

#: Géométrie de page A4 (pt, source ReportLab) et marge — **source unique** du calcul
#: de largeur disponible (pré-formatage CJK) ET de la marge ``@page`` du gabarit.
_A4_WIDTH_PT, _A4_HEIGHT_PT = A4
_PDF_PAGE_MARGIN_CM = 1.8
_PDF_PAGE_MARGIN_PT = _PDF_PAGE_MARGIN_CM * cm

#: Tailles de police (pt) — **source unique** : injectées dans le gabarit CSS et
#: réutilisées pour estimer la largeur d'un texte lors du pré-formatage CJK.
_PDF_FONT_SIZE_BODY_PT = 10.5
_PDF_HEADING_FONT_SIZES_PT: dict[str, float] = {
    "h1": 19.0,
    "h2": 14.0,
    "h3": 12.0,
    "h4": 11.0,
    "h5": 11.0,
    "h6": 11.0,
}

#: Gabarit d'un document PDF (xhtml2pdf) : ``@page`` (orientation, marge), police +
#: direction par langue, styles de titres/tableaux. Placeholders : ``{orientation}`` =
#: ``portrait``/``landscape`` ; ``{margin_cm}`` = marge ; ``{font_family}`` = famille
#: résolue (latin/CJK/arabe) ; ``{direction}`` = ``ltr``/``rtl`` ; ``{body_size}`` /
#: ``{h1_size}``…``{h456_size}`` = tailles de police ; ``{cjk_table_rule}`` = règle de
#: coupe CJK des cellules (langues CJK) ou chaîne vide ; ``{language_tag}`` = tag
#: ``pdf:language`` (arabe) ou chaîne vide ; ``{body}`` = corps HTML du Markdown.
_PDF_HTML_TEMPLATE = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
@page {{ size: a4 {orientation}; margin: {margin_cm}cm; }}
body {{ font-family: "{font_family}"; font-size: {body_size}pt; line-height: 1.4;
        color: #1f2328; direction: {direction}; }}
h1 {{ font-size: {h1_size}pt; color: #0a4f93; }}
h2 {{ font-size: {h2_size}pt; color: #0a4f93; }}
h3 {{ font-size: {h3_size}pt; color: #0a4f93; }}
h4, h5, h6 {{ font-size: {h456_size}pt; color: #0a4f93; }}
li {{ margin-bottom: 2pt; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ border: 0.5pt solid #d0d7de; padding: 3pt 5pt; text-align: left;
         vertical-align: top; }}
th {{ background: #f5f7fb; }}
a {{ color: #0a4f93; text-decoration: none; }}
{cjk_table_rule}
</style></head><body>
{language_tag}{body}
</body></html>
"""

#: Langues à écriture **sans espaces** : ReportLab ne coupe les lignes qu'aux espaces,
#: et le mode ``-pdf-word-wrap: CJK`` de xhtml2pdf 0.2.17 plante sur ``<p>``/``<li>``.
#: On pré-formate donc leur prose (cf. :func:`_prewrap_cjk_runs`). Extensible.
_CJK_LANGUAGES: frozenset[Language] = frozenset({Language.ZH})

#: Détection d'un texte CJK (idéogrammes unifiés + Ext. A, ponctuation, compatibilité,
#: pleine chasse) : un nœud contenant l'un de ces caractères est pré-formaté.
_CJK_CODEPOINT_RE = re.compile(
    "[　-〿㐀-䶿一-鿿豈-﫿＀-￯]"
)

#: Balises dont le **texte** est pré-formaté (un ``<br/>`` aux points de coupe CJK).
_CJK_PREWRAP_TAGS: frozenset[str] = frozenset(
    {"p", "li", "blockquote", "h1", "h2", "h3", "h4", "h5", "h6"}
)
#: Ancêtres où l'on s'**abstient** de pré-formater : cellules (coupe gérée par la règle
#: CSS ``td, th``) et contenus préformatés.
_CJK_PREWRAP_SKIP_ANCESTORS: frozenset[str] = frozenset({"td", "th", "pre", "code"})
#: Marge de sécurité (pt) retranchée de la largeur estimée (variabilité des métriques)
#: et retrait supplémentaire pour l'indentation d'une puce/élément de liste.
_CJK_PREWRAP_SAFETY_PT = 6.0
_CJK_PREWRAP_LIST_INDENT_PT = 20.0
#: Règle CSS de coupe CJK des cellules de tableau : le seul contexte où le mode CJK
#: de xhtml2pdf 0.2.17 fonctionne (n'est injectée que pour les langues CJK).
_PDF_TABLE_CJK_WORD_WRAP_RULE = "td, th { -pdf-word-wrap: CJK; }"

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


def _cjk_font_path() -> Path:
    """Chemin de la police CJK régulière système (Microsoft YaHei).

    Returns:
        ``%SystemRoot%/Fonts/msyh.ttc``.
    """
    return _fonts_dir() / _CJK_FONT_FILE_REGULAR


def cjk_font_available() -> bool:
    """Indique si la police CJK (Microsoft YaHei) est résolue.

    Returns:
        ``True`` si le rendu PDF du chinois est possible.
    """
    return _cjk_font_path().exists()


def _text_direction(language: Language) -> str:
    """Direction d'écriture CSS d'une langue.

    Args:
        language: Langue du contenu.

    Returns:
        ``"rtl"`` pour les langues de droite à gauche (arabe), ``"ltr"`` sinon.
    """
    return _DIRECTION_RTL if language in _RTL_LANGUAGES else _DIRECTION_LTR


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


@functools.cache
def _ensure_cjk_font_registered() -> None:
    """Enregistre Microsoft YaHei (TTC, régulier + gras) et l'injecte dans xhtml2pdf.

    Le TTC est chargé via ``subfontIndex`` (ReportLab le gère ainsi). La famille
    ``cjk`` est injectée dans ``xhtml2pdf.default.DEFAULT_FONT`` (point d'injection
    standard : ``pisa.CreatePDF`` n'expose pas de hook de registre). Idempotent et
    mémoïsé. Appelée **seulement** pour le chinois.

    Raises:
        ConfigError: ``EXPORT.NO_CJK_FONT`` si Microsoft YaHei est introuvable.
    """
    if not _cjk_font_path().exists():
        raise ConfigError(
            code="EXPORT.NO_CJK_FONT",
            user_message=(
                "Police chinoise (Microsoft YaHei) introuvable pour l'export PDF. "
                "Utilisez l'export Markdown, HTML ou Word."
            ),
            severity=Severity.ERROR,
        )
    fonts = _fonts_dir()
    pdfmetrics.registerFont(
        TTFont(_CJK_FONT_NAME, str(_cjk_font_path()), subfontIndex=0)
    )
    bold_path = fonts / _CJK_FONT_FILE_BOLD
    bold_name = _CJK_FONT_NAME_BOLD if bold_path.exists() else _CJK_FONT_NAME
    if bold_path.exists():
        pdfmetrics.registerFont(TTFont(bold_name, str(bold_path), subfontIndex=0))
    addMapping(_CJK_FONT_NAME, 0, 0, _CJK_FONT_NAME)
    addMapping(_CJK_FONT_NAME, 1, 0, bold_name)
    xhtml2pdf_default.DEFAULT_FONT[_CJK_FAMILY] = _CJK_FONT_NAME


@functools.cache
def _ensure_arabic_font_registered() -> None:
    """Mappe la famille ``arab`` sur Arial (déjà enregistré comme ``AppSans``).

    Arial contient les glyphes arabes (régulier + gras déjà enregistrés par
    :func:`_ensure_pdf_fonts_registered`, appelé en amont) : on **réutilise** cet
    enregistrement plutôt que de réenregistrer la police. Sans ce mapping,
    ``font-family: arab`` serait rabattu par xhtml2pdf sur Helvetica (dépourvue de
    glyphes arabes). Le reshaping contextuel + la bidi sont, eux, déclenchés par le
    tag ``pdf:language``. Mémoïsé (injection idempotente).
    """
    xhtml2pdf_default.DEFAULT_FONT[_ARABIC_FAMILY] = _PDF_FONT_REGULAR


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


def render_markdown_body(markdown_text: str) -> str:
    """Convertit un Markdown en corps HTML (tableaux GFM + sommaire ancré).

    Rendu de base **partagé** par les exports HTML, PDF et DOCX : extensions
    ``tables`` (tableaux pipe) et ``toc`` (ids de titres slugifiés via
    ``slugify_anchor``, alignés sur les ancres du sommaire). Ne produit que le
    corps (pas d'enveloppe ``<html>``).

    Args:
        markdown_text: Texte Markdown.

    Returns:
        Le corps HTML correspondant.
    """
    html_body: str = markdown.markdown(
        markdown_text,
        extensions=_MARKDOWN_EXTENSIONS,
        extension_configs={"toc": {"slugify": _toc_slugify}},
    )
    return html_body


def render_markdown_to_html(
    markdown_text: str,
    output_path: Path,
    *,
    language: Language = Language.FR,
) -> None:
    """Rend un Markdown en document HTML autonome (UTF-8, style intégré).

    Aucune police système n'est requise — le fichier est ouvrable dans n'importe
    quel navigateur (qui substitue lui-même les polices CJK/arabe). Les titres
    reçoivent un ``id`` slugifié (extension ``toc``) → le sommaire est cliquable.

    Args:
        markdown_text: Texte Markdown (commençant idéalement par un titre H1).
        output_path: Chemin du fichier ``.html`` à écrire.
        language: Langue du contenu (pose ``lang`` et ``dir`` ; arabe → RTL).
    """
    body = render_markdown_body(markdown_text)
    direction = _text_direction(language)
    document = _HTML_DOCUMENT_TEMPLATE.format(
        title=escape(_extract_title(markdown_text)),
        body=body,
        lang=language.value,
        direction=direction,
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


@functools.cache
def _renderable_codepoints(font_name: str) -> frozenset[int]:
    """Codepoints couverts par une police déjà enregistrée auprès de ReportLab.

    Interroge la table ``charToGlyph`` de la police analysée par ReportLab (aucune
    dépendance externe : ReportLab est déjà requis). Mémoïsé par police.

    Args:
        font_name: Nom d'enregistrement de la police (ex. ``AppSans``, ``CJKFont``).

    Returns:
        L'ensemble des codepoints (``ord``) ayant un glyphe dans la police.
    """
    return frozenset(int(cp) for cp in pdfmetrics.getFont(font_name).face.charToGlyph)


def _strip_unrenderable_for_pdf(text: str, font_name: str) -> str:
    """Retire les caractères sans glyphe dans la police (émojis…), source des carrés.

    ReportLab dessine un carré ``□`` pour tout caractère absent de la police et ne
    fait pas de repli par glyphe. On retire donc les caractères non couverts, en
    **conservant** les invisibles/structurels (cf. ``_PDF_KEPT_UNRENDERABLE_CATEGORIES``,
    dont ZWJ/RLM nécessaires à l'arabe). HTML et DOCX, eux, gardent ces caractères
    (repli natif du navigateur/Word).

    Args:
        text: Texte Markdown source (idéalement déjà passé par ``_normalize_for_pdf``).
        font_name: Police active du rendu (Arial pour latin/arabe, YaHei pour le CJK).

    Returns:
        Le texte privé des caractères non rendus par la police.
    """
    covered = _renderable_codepoints(font_name)
    return "".join(
        ch
        for ch in text
        if ord(ch) in covered
        or unicodedata.category(ch) in _PDF_KEPT_UNRENDERABLE_CATEGORIES
    )


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


def _contains_cjk(text: str | None) -> bool:
    """Indique si un texte contient au moins un caractère CJK.

    Args:
        text: Texte d'un nœud (``None`` pour les nœuds sans contenu textuel).

    Returns:
        ``True`` si ``text`` contient un caractère CJK (cf. ``_CJK_CODEPOINT_RE``).
    """
    return text is not None and _CJK_CODEPOINT_RE.search(text) is not None


def _nearest_prewrap_tag(node: NavigableString) -> str | None:
    """Balise de pré-formatage la plus proche d'un nœud texte CJK.

    Remonte les ancêtres : renvoie ``None`` si l'on rencontre d'abord un ancêtre où
    l'on s'abstient (cellule de tableau, ``pre``/``code``), sinon le nom de la
    première balise pré-formatable rencontrée (``p``, ``li``, titre…).

    Args:
        node: Nœud texte (BeautifulSoup) contenant du CJK.

    Returns:
        Le nom de balise pré-formatable, ou ``None`` si aucun / contexte exclu.
    """
    for parent in node.parents:
        if parent.name in _CJK_PREWRAP_SKIP_ANCESTORS:
            return None
        if parent.name in _CJK_PREWRAP_TAGS:
            return str(parent.name)
    return None


def _prewrap_cjk_runs(body_html: str, *, font_name: str, landscape: bool) -> str:
    """Insère des ``<br/>`` aux points de coupe CJK de la prose (hors tableaux).

    ReportLab ne coupe les lignes qu'aux espaces ; le chinois s'écrit sans espaces et
    déborderait. On découpe chaque **nœud texte** CJK avec ``reportlab.lib.textsplit.
    wordSplit`` (coupe caractère par caractère, sans insérer d'espace, en préservant
    les mots latins) à la largeur disponible de la page, puis on remplace le nœud par
    ses lignes séparées de ``<br/>``. Les cellules de tableau sont laissées à la règle
    CSS ``-pdf-word-wrap: CJK`` (cf. ``_PDF_TABLE_CJK_WORD_WRAP_RULE``).

    Args:
        body_html: Corps HTML rendu (après ``_layout_table_cells``).
        font_name: Police CJK enregistrée (estimation de largeur).
        landscape: Orientation de la page (largeur disponible portrait vs paysage).

    Returns:
        Le corps HTML avec les longs passages CJK pré-coupés.
    """
    soup = BeautifulSoup(body_html, "html.parser")
    page_width = _A4_HEIGHT_PT if landscape else _A4_WIDTH_PT
    available = page_width - 2 * _PDF_PAGE_MARGIN_PT
    for text_node in list(soup.find_all(string=_contains_cjk)):
        tag = _nearest_prewrap_tag(text_node)
        if tag is None:
            continue
        font_size = _PDF_HEADING_FONT_SIZES_PT.get(tag, _PDF_FONT_SIZE_BODY_PT)
        indent = _CJK_PREWRAP_LIST_INDENT_PT if tag == "li" else 0.0
        width = available - indent - _CJK_PREWRAP_SAFETY_PT
        lines = [line for _extra, line in wordSplit(str(text_node), width, font_name, font_size)]
        if len(lines) <= 1:
            continue
        for index, line in enumerate(lines):
            if index:
                text_node.insert_before(soup.new_tag("br"))
            text_node.insert_before(NavigableString(line))
        text_node.extract()
    return str(soup)


def render_markdown_to_pdf(
    markdown_text: str,
    output_path: Path,
    *,
    landscape: bool = False,
    table_column_widths: tuple[str, ...] | None = None,
    language: Language = Language.FR,
) -> None:
    """Rend un Markdown en PDF via ``xhtml2pdf`` (Markdown → HTML → PDF).

    Args:
        markdown_text: Texte Markdown.
        output_path: Chemin du PDF à écrire.
        landscape: Orientation paysage (ex: glossaire large) ; portrait sinon.
        table_column_widths: Largeurs CSS par colonne appliquées aux tableaux
            (ex: glossaire). ``None`` = largeurs automatiques.
        language: Langue du contenu. Sélectionne la police et la direction :
            latin (fr/en/de/es/it) → Helvetica/LTR ; chinois → police CJK
            (Microsoft YaHei) ; arabe → Arial + RTL + reshaping/bidi.

    Raises:
        ConfigError: ``EXPORT.NO_PDF_FONT`` si la police Arial est introuvable,
            ``EXPORT.NO_CJK_FONT`` si la police chinoise manque (langue ZH), ou
            ``EXPORT.PDF_RENDER_FAILED`` si le moteur de rendu échoue.
    """
    if not pdf_fonts_available():
        raise ConfigError(
            code="EXPORT.NO_PDF_FONT",
            user_message=(
                "Aucune police Unicode trouvée pour l'export PDF. Utilisez "
                "l'export Markdown, HTML ou Word."
            ),
            severity=Severity.ERROR,
        )
    _ensure_pdf_fonts_registered()
    font_family, language_tag = _PDF_LANG_RENDERING.get(
        language, (_PDF_DEFAULT_FAMILY, "")
    )
    direction = _text_direction(language)
    if language is Language.ZH:
        _ensure_cjk_font_registered()
    elif language is Language.AR:
        _ensure_arabic_font_registered()
    # Police effective du rendu : YaHei pour le chinois, Arial sinon (couvre latin
    # et arabe) — sert à filtrer les caractères sans glyphe (émojis → carrés ``□``).
    render_font = _CJK_FONT_NAME if language is Language.ZH else _PDF_FONT_REGULAR
    normalized = _strip_unrenderable_for_pdf(
        _normalize_for_pdf(markdown_text), render_font
    )
    body = render_markdown_body(normalized)
    body = _layout_table_cells(body, table_column_widths)
    cjk_table_rule = ""
    if language in _CJK_LANGUAGES:
        body = _prewrap_cjk_runs(body, font_name=render_font, landscape=landscape)
        cjk_table_rule = _PDF_TABLE_CJK_WORD_WRAP_RULE
    document = _PDF_HTML_TEMPLATE.format(
        orientation="landscape" if landscape else "portrait",
        margin_cm=_PDF_PAGE_MARGIN_CM,
        font_family=font_family,
        direction=direction,
        body_size=_PDF_FONT_SIZE_BODY_PT,
        h1_size=_PDF_HEADING_FONT_SIZES_PT["h1"],
        h2_size=_PDF_HEADING_FONT_SIZES_PT["h2"],
        h3_size=_PDF_HEADING_FONT_SIZES_PT["h3"],
        h456_size=_PDF_HEADING_FONT_SIZES_PT["h4"],
        cjk_table_rule=cjk_table_rule,
        language_tag=language_tag,
        body=body,
    )
    buffer = io.BytesIO()
    status = pisa.CreatePDF(document, dest=buffer, encoding="utf-8")
    if status.err:
        raise ConfigError(
            code="EXPORT.PDF_RENDER_FAILED",
            user_message=(
                "Le rendu du PDF a échoué. Utilisez l'export Markdown, HTML ou Word."
            ),
            severity=Severity.ERROR,
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(buffer.getvalue())
