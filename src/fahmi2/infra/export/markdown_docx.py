"""Renderer d'export Markdown → DOCX (Word), via HTML intermédiaire.

Réutilise le rendu Markdown → HTML partagé (``markdown_pdf.render_markdown_body`` :
mêmes extensions ``tables``/``toc`` que les exports HTML et PDF), puis convertit
le corps HTML en document Word avec ``htmldocx`` (qui s'appuie sur ``python-docx``).
Pur *renderer* : l'orchestration (collecte, dispatch par format) vit dans
``app.document_export``.

Word applique nativement la bidirectionnalité (arabe) et la substitution de
police (chinois) à l'affichage : aucune police à déclarer côté DOCX.
"""

from __future__ import annotations

from pathlib import Path

from docx import Document
from htmldocx import HtmlToDocx

from fahmi2.infra.export.markdown_pdf import render_markdown_body


def render_markdown_to_docx(markdown_text: str, output_path: Path) -> None:
    """Rend un Markdown en document Word ``.docx``.

    Args:
        markdown_text: Texte Markdown.
        output_path: Chemin du fichier ``.docx`` à écrire.
    """
    body = render_markdown_body(markdown_text)
    document = Document()
    HtmlToDocx().add_html_to_document(body, document)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    document.save(str(output_path))
