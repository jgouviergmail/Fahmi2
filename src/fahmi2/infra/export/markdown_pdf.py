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
from bs4.element import NavigableString, PageElement
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

#: Détection des barrières de bloc de code (``` ou ~~~) : on n'y normalise pas les
#: tableaux (un tableau d'exemple dans du code ne doit pas être transformé).
_CODE_FENCE_RE = re.compile(r"^\s*(?:```|~~~)")
#: Caractères autorisés dans une **ligne de séparation** de tableau GFM
#: (``|---|:--:|``) : barres, tirets, deux-points, espaces.
_TABLE_DELIMITER_CHARS = frozenset("|:- ")
#: Nombre minimal de ``<ol>`` pour qu'une liste ait pu être scindée par un tableau
#: (en deçà, pas de recollage de numérotation à tenter).
_MIN_ORDERED_LISTS_FOR_SPLIT = 2

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
#: Famille ReportLab dédiée à l'arabe : Arial **Italic** et **Bold-Italic** n'ont
#: **aucun glyphe arabe** (l'arabe n'a pas de formes italiques) → un terme arabe en
#: emphase tomberait en carrés ``□``. On mappe donc italique/gras-italique sur les
#: variantes **droites** (régulier/gras), qui couvrent l'arabe.
_PDF_ARABIC_FONT_FAMILY = "AppArabic"
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
#: ``wordSplit`` peut **dépasser** sa largeur cible d'un caractère (il inclut le glyphe
#: qui fait franchir la limite). On réserve donc en plus la largeur d'un idéogramme
#: pleine chasse pour que ce dépassement reste **dans** la marge (sinon le dernier
#: caractère sort à droite). Mesuré sur la police active à la taille du bloc.
_CJK_WIDEST_CHAR = "中"
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
    """Mappe la famille ``arab`` sur une famille Arial **toujours arabe** (droite).

    Arial contient les glyphes arabes en **régulier** et **gras**, mais **pas** en
    italique ni gras-italique (cf. ``ariali.ttf``/``arialbi.ttf`` : 0 glyphe arabe).
    Comme l'arabe n'a pas de formes italiques, on enregistre une famille dédiée
    ``AppArabic`` dont les 4 variantes pointent vers les fontes **droites** Arial
    (régulier/gras, déjà enregistrées par :func:`_ensure_pdf_fonts_registered`) : un
    terme arabe en emphase reste ainsi lisible au lieu de tomber en carrés ``□``. Le
    reshaping contextuel + la bidi sont, eux, déclenchés par le tag ``pdf:language``.
    Mémoïsé (injection idempotente).
    """
    addMapping(_PDF_ARABIC_FONT_FAMILY, 0, 0, _PDF_FONT_REGULAR)
    addMapping(_PDF_ARABIC_FONT_FAMILY, 1, 0, _PDF_FONT_BOLD)
    addMapping(_PDF_ARABIC_FONT_FAMILY, 0, 1, _PDF_FONT_REGULAR)  # italique → droit
    addMapping(_PDF_ARABIC_FONT_FAMILY, 1, 1, _PDF_FONT_BOLD)  # gras-italique → gras
    xhtml2pdf_default.DEFAULT_FONT[_ARABIC_FAMILY] = _PDF_ARABIC_FONT_FAMILY


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


def _is_pipe_row(line: str) -> bool:
    """Indique si une ligne ressemble à une ligne de tableau pipe (contient ``|``).

    Args:
        line: Ligne de Markdown.

    Returns:
        ``True`` si la ligne (sans espaces de bord) contient une barre verticale.
    """
    return "|" in line.strip()


def _is_table_delimiter(line: str) -> bool:
    """Indique si une ligne est la **séparation** d'un tableau GFM (``|---|:-:|``).

    Args:
        line: Ligne de Markdown.

    Returns:
        ``True`` si la ligne ne contient que des barres/tirets/deux-points/espaces
        et comporte au moins un tiret et une barre.
    """
    stripped = line.strip()
    return (
        "|" in stripped
        and "-" in stripped
        and set(stripped) <= _TABLE_DELIMITER_CHARS
    )


def _normalize_table_blocks(markdown_text: str) -> str:
    """Isole les tableaux pipe pour que python-markdown les reconnaisse.

    L'extension ``tables`` n'active un tableau que s'il forme un **bloc** précédé
    d'une ligne vide et **non indenté**. Les sorties LLM collent souvent le tableau
    à la phrase qui l'introduit ou l'indentent dans une liste numérotée (le tableau
    s'affiche alors en barres littérales). On garantit donc une ligne vide avant et
    après chaque bloc de tableau et on le **désindente**. Les blocs de code (``` /
    ~~~) sont préservés. *Limitation connue* : python-markdown ne sait pas imbriquer
    un tableau dans un élément de liste — le tableau en ressort (la liste qui suit
    peut donc se renuméroter).

    Args:
        markdown_text: Texte Markdown source.

    Returns:
        Le Markdown avec les tableaux pipe correctement isolés.
    """
    lines = markdown_text.splitlines()
    out: list[str] = []
    in_fence = False
    index = 0
    total = len(lines)
    while index < total:
        if _CODE_FENCE_RE.match(lines[index]):
            in_fence = not in_fence
            out.append(lines[index])
            index += 1
            continue
        is_table_start = (
            not in_fence
            and _is_pipe_row(lines[index])
            and index + 1 < total
            and _is_table_delimiter(lines[index + 1])
        )
        if is_table_start:
            if out and out[-1].strip():
                out.append("")
            while index < total and _is_pipe_row(lines[index]):
                out.append(lines[index].strip())
                index += 1
            if index < total and lines[index].strip():
                out.append("")
            continue
        out.append(lines[index])
        index += 1
    return "\n".join(out)


def _renumber_lists_split_by_tables(body_html: str) -> str:
    """Recolle la numérotation d'une liste ordonnée scindée par un tableau.

    Quand un tableau est sorti d'un élément de liste (cf. ``_normalize_table_blocks``,
    limitation python-markdown), la liste qui suit redémarre à 1. On rétablit la
    continuité en posant l'attribut ``start`` sur tout ``<ol>`` séparé du précédent
    ``<ol>`` **uniquement** par des ``<table>`` (motif spécifique de l'extraction ;
    deux listes séparées par un titre/paragraphe restent indépendantes). ``<ol
    start>`` est honoré par les navigateurs et par xhtml2pdf (PDF).

    Args:
        body_html: Corps HTML rendu par python-markdown.

    Returns:
        Le corps HTML avec la numérotation des listes scindées rétablie.
    """
    if body_html.count("<ol") < _MIN_ORDERED_LISTS_FOR_SPLIT or "<table" not in body_html:
        return body_html
    soup = BeautifulSoup(body_html, "html.parser")
    for ordered_list in soup.find_all("ol"):
        sibling = ordered_list.find_previous_sibling()
        saw_table = False
        while sibling is not None and sibling.name == "table":
            saw_table = True
            sibling = sibling.find_previous_sibling()
        if not saw_table or sibling is None or sibling.name != "ol":
            continue
        start_value = sibling.get("start")
        previous_start = int(start_value) if isinstance(start_value, str) else 1
        previous_count = len(sibling.find_all("li", recursive=False))
        ordered_list["start"] = str(previous_start + previous_count)
    return str(soup)


def render_markdown_body(markdown_text: str) -> str:
    """Convertit un Markdown en corps HTML (tableaux GFM + sommaire ancré).

    Rendu de base **partagé** par les exports HTML, PDF et DOCX : normalisation des
    blocs de tableau (cf. ``_normalize_table_blocks``) puis extensions ``tables``
    (tableaux pipe) et ``toc`` (ids de titres slugifiés via ``slugify_anchor``,
    alignés sur les ancres du sommaire) ; enfin, recollage de la numérotation des
    listes scindées par un tableau (cf. ``_renumber_lists_split_by_tables``). Ne
    produit que le corps (pas d'enveloppe ``<html>``).

    Args:
        markdown_text: Texte Markdown.

    Returns:
        Le corps HTML correspondant.
    """
    html_body: str = markdown.markdown(
        _normalize_table_blocks(markdown_text),
        extensions=_MARKDOWN_EXTENSIONS,
        extension_configs={"toc": {"slugify": _toc_slugify}},
    )
    return _renumber_lists_split_by_tables(html_body)


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


def _cjk_line_break_offsets(
    flat_text: str, width: float, font_name: str, font_size: float
) -> list[int]:
    """Décale les points de coupe (offsets) d'un texte CJK à une largeur donnée.

    Utilise ``wordSplit`` (coupe caractère par caractère pour le CJK, préserve les
    mots latins) puis convertit les lignes en **offsets cumulés** dans ``flat_text``.

    Args:
        flat_text: Texte aplati du bloc (CJK + éventuel latin inline).
        width: Largeur cible (réserve d'un idéogramme déjà retranchée par l'appelant).
        font_name: Police CJK enregistrée.
        font_size: Taille de police du bloc.

    Returns:
        Les offsets (positions de caractère dans ``flat_text``) où insérer un ``<br/>``.
    """
    lines = [line for _extra, line in wordSplit(flat_text, width, font_name, font_size)]
    offsets: list[int] = []
    position = 0
    for line in lines[:-1]:
        position += len(line)
        offsets.append(position)
    return offsets


def _insert_cjk_breaks(
    text_nodes: list[NavigableString], offsets: list[int], soup: BeautifulSoup
) -> None:
    """Insère des ``<br/>`` aux offsets donnés à travers les nœuds texte d'un bloc.

    Les offsets sont relatifs au texte **aplati** du bloc (concaténation des nœuds).
    Un offset tombant **au début** d'un nœud (frontière avec un élément inline, ex.
    après un terme en gras) insère un ``<br/>`` avant ce nœud ; un offset **interne**
    scinde le nœud autour d'un ``<br/>``. Préserve donc la mise en forme inline.

    Args:
        text_nodes: Nœuds texte du bloc, dans l'ordre du document.
        offsets: Positions de coupe dans le texte aplati (triées, ``0 < offset < len``).
        soup: Soupe BeautifulSoup (fabrique des balises ``<br/>``).
    """
    starts: list[tuple[NavigableString, int]] = []
    position = 0
    for node in text_nodes:
        starts.append((node, position))
        position += len(str(node))
    node_at_start = {start: node for node, start in starts}
    within: dict[int, tuple[NavigableString, list[int]]] = {}
    for offset in sorted(offsets):
        boundary_node = node_at_start.get(offset)
        if boundary_node is not None and offset > 0:
            boundary_node.insert_before(soup.new_tag("br"))
            continue
        for node, start in starts:
            if start < offset < start + len(str(node)):
                within.setdefault(id(node), (node, []))[1].append(offset - start)
                break
    for node, local_offsets in within.values():
        text = str(node)
        pieces: list[PageElement] = []
        previous = 0
        for local in sorted(local_offsets):
            pieces.append(NavigableString(text[previous:local]))
            pieces.append(soup.new_tag("br"))
            previous = local
        pieces.append(NavigableString(text[previous:]))
        for piece in pieces:
            node.insert_before(piece)
        node.extract()


def _prewrap_cjk_runs(body_html: str, *, font_name: str, landscape: bool) -> str:
    """Insère des ``<br/>`` aux points de coupe CJK de la prose (hors tableaux).

    ReportLab ne coupe les lignes qu'aux espaces ; le chinois s'écrit sans espaces et
    déborderait. On opère **par bloc** (paragraphe, élément de liste, titre…) : on
    **aplatit** tout le texte du bloc — y compris les fragments en **gras/italique** —
    puis on calcule les coupures sur ce flux complet et on insère les ``<br/>`` aux bons
    offsets (cf. ``_insert_cjk_breaks``). Indispensable : couper **nœud par nœud** place
    la 1ʳᵉ ligne du texte qui suit un terme en gras *après* ce terme → débordement à
    droite. La largeur cible réserve **un idéogramme** car ``wordSplit`` dépasse sa cible
    du dernier caractère ajouté (cf. ``_CJK_WIDEST_CHAR``). Les cellules de tableau sont
    laissées à la règle CSS ``-pdf-word-wrap: CJK`` (cf. ``_PDF_TABLE_CJK_WORD_WRAP_RULE``).

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
    skip_ancestors = list(_CJK_PREWRAP_SKIP_ANCESTORS)
    prewrap_tags = list(_CJK_PREWRAP_TAGS)
    for block in soup.find_all(prewrap_tags):
        if block.find_parent(skip_ancestors) is not None:
            continue
        # Texte **directement** porté par ce bloc (hors blocs imbriqués, qui seront
        # traités à leur tour) et hors contenu préformaté.
        text_nodes = [
            node
            for node in block.descendants
            if isinstance(node, NavigableString)
            and node.find_parent(prewrap_tags) is block
            and node.find_parent(skip_ancestors) is None
        ]
        flat_text = "".join(str(node) for node in text_nodes)
        if not _contains_cjk(flat_text):
            continue
        font_size = _PDF_HEADING_FONT_SIZES_PT.get(block.name, _PDF_FONT_SIZE_BODY_PT)
        indent = (
            _CJK_PREWRAP_LIST_INDENT_PT
            if block.name == "li" or block.find_parent("li") is not None
            else 0.0
        )
        char_width = pdfmetrics.stringWidth(_CJK_WIDEST_CHAR, font_name, font_size)
        width = available - indent - char_width - _CJK_PREWRAP_SAFETY_PT
        offsets = _cjk_line_break_offsets(flat_text, width, font_name, font_size)
        if offsets:
            _insert_cjk_breaks(text_nodes, offsets, soup)
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
    is_cjk = language in _CJK_LANGUAGES
    if is_cjk:
        _ensure_cjk_font_registered()
    elif language is Language.AR:
        _ensure_arabic_font_registered()
    # Police effective du rendu : YaHei pour le chinois, Arial sinon (couvre latin
    # et arabe) — sert à filtrer les caractères sans glyphe (émojis → carrés ``□``).
    render_font = _CJK_FONT_NAME if is_cjk else _PDF_FONT_REGULAR
    normalized = _strip_unrenderable_for_pdf(
        _normalize_for_pdf(markdown_text), render_font
    )
    body = render_markdown_body(normalized)
    body = _layout_table_cells(body, table_column_widths)
    cjk_table_rule = ""
    if is_cjk:
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
