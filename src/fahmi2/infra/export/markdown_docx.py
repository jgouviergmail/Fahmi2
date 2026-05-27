"""Renderer d'export Markdown → DOCX (Word), via HTML intermédiaire.

Réutilise le rendu Markdown → HTML partagé (``markdown_pdf.render_markdown_body`` :
mêmes extensions ``tables``/``toc`` que les exports HTML et PDF), puis convertit
le corps HTML en document Word avec ``htmldocx`` (qui s'appuie sur ``python-docx``).
Pur *renderer* : l'orchestration (collecte, dispatch par format) vit dans
``app.document_export``.

Word applique nativement la bidirectionnalité (arabe), la substitution de police et
la coupe de ligne (chinois) à l'affichage : aucune police ni pré-formatage à déclarer
côté DOCX. L'orientation **paysage** (option ``landscape``, ex: glossaire) est posée
sur les sections du document, comme le PDF.
"""

from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.document import Document as DocumentType
from docx.enum.section import WD_ORIENT
from htmldocx import HtmlToDocx

from fahmi2.infra.export.markdown_pdf import render_markdown_body


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
    if landscape:
        _set_landscape(document)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    document.save(str(output_path))
