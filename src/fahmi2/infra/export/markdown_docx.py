"""Renderer d'export Markdown → DOCX (Word), via HTML intermédiaire.

Réutilise le rendu Markdown → HTML partagé (``markdown_pdf.render_markdown_body`` :
mêmes extensions ``tables``/``toc`` que les exports HTML et PDF), puis convertit
le corps HTML en document Word avec ``htmldocx`` (qui s'appuie sur ``python-docx``).
Pur *renderer* : l'orchestration (collecte, dispatch par format) vit dans
``app.document_export``.

Word applique nativement, **au niveau des runs**, la bidirectionnalité (arabe), la
substitution de police et la coupe de ligne (chinois) : aucune police ni pré-formatage
à déclarer côté DOCX. **Limite connue (arabe)** : contrairement au PDF (``direction:rtl``)
et au HTML (``dir="rtl"``), on ne pose pas de direction RTL explicite ni de ``bidiVisual``
sur les tableaux — le texte arabe s'affiche correctement (bidi des runs) mais l'ordre des
colonnes et l'alignement des paragraphes restent LTR. L'orientation **paysage** (option
``landscape``, ex: glossaire) est posée sur les sections du document, comme le PDF.

``htmldocx`` ne traduit pas les bordures CSS ni ``width: 100%`` : ses tableaux sortent
**sans contour** et en largeur **automatique** (ajustée au contenu). On les reformate
donc après conversion (style ``Table Grid`` pour les bordures + largeur 100 %), pour
s'aligner sur le rendu HTML/PDF.
"""

from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.document import Document as DocumentType
from docx.enum.section import WD_ORIENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.table import Table
from htmldocx import HtmlToDocx

from fahmi2.infra.export.markdown_pdf import render_markdown_body

#: Style Word intégré (présent dans le gabarit ``python-docx`` par défaut) qui pose une
#: bordure simple sur **toutes** les cellules.
_DOCX_TABLE_GRID_STYLE = "Table Grid"
#: Largeur de tableau « pleine page » en cinquantièmes de pour-cent (5000 = 100 %).
_DOCX_TABLE_FULL_WIDTH_PCT = "5000"


def _set_table_full_width(table: Table) -> None:
    """Force un tableau Word à occuper 100 % de la largeur utile (``tblW`` en %).

    ``htmldocx`` laisse ``tblW`` en ``auto`` (largeur ajustée au contenu) ; on le passe
    en pourcentage pour remplir la colonne de texte, comme ``width: 100%`` en HTML/PDF.

    Args:
        table: Tableau Word à élargir (modifié en place).
    """
    tbl_pr = table._tbl.tblPr
    tbl_w = tbl_pr.find(qn("w:tblW"))
    if tbl_w is None:
        tbl_w = OxmlElement("w:tblW")
        tbl_pr.append(tbl_w)
    tbl_w.set(qn("w:type"), "pct")
    tbl_w.set(qn("w:w"), _DOCX_TABLE_FULL_WIDTH_PCT)


def _format_docx_tables(document: DocumentType) -> None:
    """Reformate tous les tableaux : bordures (``Table Grid``) + pleine largeur.

    ``htmldocx`` produit des tableaux sans contour et en largeur automatique ; on les
    aligne sur le rendu HTML/PDF (bordures + 100 % de large).

    Args:
        document: Document Word à modifier en place.
    """
    for table in document.tables:
        table.style = _DOCX_TABLE_GRID_STYLE
        _set_table_full_width(table)


def _set_landscape(document: DocumentType) -> None:
    """Bascule toutes les sections d'un document Word en orientation paysage.

    Permute largeur et hauteur de page (Word ne le fait pas automatiquement en
    changeant ``orientation``) sur chaque section.

    Args:
        document: Document Word à modifier en place.
    """
    for section in document.sections:
        new_width, new_height = section.page_height, section.page_width
        section.orientation = WD_ORIENT.LANDSCAPE
        section.page_width = new_width
        section.page_height = new_height


def render_markdown_to_docx(
    markdown_text: str, output_path: Path, *, landscape: bool = False
) -> None:
    """Rend un Markdown en document Word ``.docx``.

    Args:
        markdown_text: Texte Markdown.
        output_path: Chemin du fichier ``.docx`` à écrire.
        landscape: Orientation paysage (ex: glossaire large), comme le PDF ;
            portrait sinon.
    """
    body = render_markdown_body(markdown_text)
    document = Document()
    HtmlToDocx().add_html_to_document(body, document)
    _format_docx_tables(document)
    if landscape:
        _set_landscape(document)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    document.save(str(output_path))
