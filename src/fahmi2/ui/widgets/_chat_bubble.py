"""Bulles de chat à coins arrondis (vrais widgets natifs, `QPainter`).

``QTextBrowser`` ne supporte pas ``border-radius`` dans son mini-HTML : les
bulles précédentes étaient des encadrés rectangulaires. Ce module fournit
deux widgets Qt natifs qui contournent cette limitation :

- :class:`MessageBubble` — une bulle de message peint son arrière-plan via
  ``QPainter.drawRoundedRect`` (vrais coins arrondis), avec un en-tête de
  rôle, un corps en ``QLabel`` Rich Text (Markdown rendu), et une zone de
  citations cliquables.
- :class:`ChatThread` — un ``QScrollArea`` qui empile les bulles en
  laissant les bulles utilisateur s'aligner à droite et les bulles
  assistant à gauche. Expose ``toPlainText`` pour la compatibilité avec
  les tests qui inspectaient le contenu du ``QTextBrowser``.

L'API publique du fil (``show_conversation``, ``start_assistant_bubble``,
``append_delta``, ``finalize_message``) est conçue pour rester en miroir
de l'API historique de :class:`~fahmi2.ui.widgets.chat_view.ChatView` —
le contrôleur n'a aucune adaptation à faire.
"""

from __future__ import annotations

import html
from typing import Final

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import (
    QColor,
    QPainter,
    QPalette,
    QPen,
    QTextDocument,
)
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from fahmi2.domain.chat import ChatMessage, Citation
from fahmi2.infra.export.markdown_pdf import render_markdown_fragment
from fahmi2.ui.theme._tokens import current_palette

# ---------------------------------------------------------------- constantes

_ROLE_USER: Final[str] = "user"
_ROLE_ASSISTANT: Final[str] = "assistant"
_ROLE_DISPLAY_LABEL: Final[dict[str, str]] = {
    _ROLE_USER: "Vous",
    _ROLE_ASSISTANT: "Assistant",
}

#: Rayon des coins arrondis de la bulle (px).
_BUBBLE_RADIUS: Final[int] = 14
#: Largeur maximale d'une bulle en pourcentage de la largeur disponible.
_BUBBLE_MAX_WIDTH_PCT: Final[float] = 0.82
#: Marges internes de la bulle (px).
_BUBBLE_PADDING_LEFT: Final[int] = 14
_BUBBLE_PADDING_TOP: Final[int] = 10
_BUBBLE_PADDING_RIGHT: Final[int] = 14
_BUBBLE_PADDING_BOTTOM: Final[int] = 12
#: Espacement vertical entre les enfants de la bulle.
_BUBBLE_SPACING: Final[int] = 4

#: Marges autour de chaque bulle (dans le fil scrollable).
_THREAD_PADDING_HORIZONTAL: Final[int] = 12
_THREAD_PADDING_VERTICAL: Final[int] = 12
_THREAD_BUBBLE_SPACING: Final[int] = 10

#: Style commun (compact) du texte des liens dans une bulle.
_LINK_STYLE: Final[str] = "text-decoration: none;"

#: Style des chips de citation (pastilles cliquables sous une bulle assistant).
_CHIP_PADDING: Final[int] = 6
_CHIP_RADIUS: Final[int] = 6

#: ``objectName`` réservé aux bulles (utilisé pour cibler le QSS interne qui
#: rend les ``QLabel`` enfants transparents).
_BUBBLE_OBJECT_NAME: Final[str] = "chatMessageBubble"


def _role_display_label(role: str) -> str:
    """Retourne le libellé FR pour le rôle ``role`` (``"Vous"`` / ``"Assistant"``).

    Args:
        role: Rôle brut (``"user"`` ou ``"assistant"``).

    Returns:
        Le libellé d'affichage.
    """
    return _ROLE_DISPLAY_LABEL.get(role, role)


def _palette_colors(role: str) -> tuple[QColor, QColor, QColor, QColor]:
    """Retourne ``(bg, border, text, role_label)`` pour le rôle ``role``.

    Les couleurs sont dérivées de la palette active (clair ou sombre) :

    - bulle **utilisateur** : fond accent doux + texte accent fort
    - bulle **assistant**  : surface bordée + texte principal

    Args:
        role: Rôle (``"user"`` / ``"assistant"``).

    Returns:
        Quadruplet de ``QColor``.
    """
    palette = current_palette()
    role_label = QColor(palette.text_3)
    if role == _ROLE_USER:
        return (
            QColor(palette.accent_soft),
            QColor(palette.border_card),
            QColor(palette.accent_strong),
            role_label,
        )
    return (
        QColor(palette.surface),
        QColor(palette.border_card),
        QColor(palette.text_1),
        role_label,
    )


def _strip_html(html_text: str) -> str:
    """Convertit un fragment HTML en texte brut (via ``QTextDocument``).

    Args:
        html_text: Fragment HTML.

    Returns:
        Le texte brut équivalent (utile pour ``toPlainText`` de compatibilité).
    """
    doc = QTextDocument()
    doc.setHtml(html_text)
    return doc.toPlainText()


class MessageBubble(QFrame):
    """Bulle de message à coins arrondis (rendu via ``QPainter``).

    Le widget peint lui-même son arrière-plan en ``paintEvent`` (le QSS de
    Qt ne supporte pas ``border-radius`` sur un ``QFrame`` qu'on souhaite
    aussi traverser par d'autres rendus). Le contenu (rôle + corps + chips
    de citations) est dans des ``QLabel``.
    """

    citation_clicked = Signal(str)

    def __init__(self, role: str, parent: QWidget | None = None) -> None:
        """Construit une bulle vide pour le rôle ``role``.

        Args:
            role: ``"user"`` ou ``"assistant"``.
            parent: Parent Qt optionnel.
        """
        super().__init__(parent)
        self.setObjectName(_BUBBLE_OBJECT_NAME)
        self._role = role
        self._content_html: str = ""
        self._citations: tuple[Citation, ...] = ()
        # Le fond est peint par ``paintEvent``. On désactive tout fond de
        # widget Qt (palette / styled background) sur la bulle ET on cible les
        # ``QLabel`` enfants via un object-name dédié pour qu'ils héritent
        # d'un fond transparent (sinon le QSS global ``QWidget { background }``
        # leur applique le gris de l'application, donnant l'impression de
        # boîtes empilées à l'intérieur de la bulle).
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self.setAutoFillBackground(False)
        self.setStyleSheet(
            f"#{_BUBBLE_OBJECT_NAME} QLabel {{ background: transparent; }}"
        )
        self.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            _BUBBLE_PADDING_LEFT,
            _BUBBLE_PADDING_TOP,
            _BUBBLE_PADDING_RIGHT,
            _BUBBLE_PADDING_BOTTOM,
        )
        layout.setSpacing(_BUBBLE_SPACING)

        bg, _border, text_color, role_color = _palette_colors(role)
        del bg

        self._role_label = QLabel(_role_display_label(role), self)
        role_pal = self._role_label.palette()
        role_pal.setColor(QPalette.ColorRole.WindowText, role_color)
        self._role_label.setPalette(role_pal)
        role_font = self._role_label.font()
        role_font.setBold(True)
        role_font.setPointSize(max(8, role_font.pointSize() - 1))
        self._role_label.setFont(role_font)
        layout.addWidget(self._role_label)

        self._content = QLabel(self)
        self._content.setTextFormat(Qt.TextFormat.RichText)
        self._content.setWordWrap(True)
        self._content.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.LinksAccessibleByMouse
        )
        self._content.setOpenExternalLinks(False)
        self._content.linkActivated.connect(self._on_link_activated)
        content_pal = self._content.palette()
        content_pal.setColor(QPalette.ColorRole.WindowText, text_color)
        self._content.setPalette(content_pal)
        layout.addWidget(self._content)

        # Conteneur des chips de citations (rempli après finalisation pour les
        # bulles assistant qui en ont).
        self._citations_layout = QVBoxLayout()
        self._citations_layout.setContentsMargins(0, 6, 0, 0)
        self._citations_layout.setSpacing(3)
        layout.addLayout(self._citations_layout)

    # --------------------------------------------------------------- API

    def set_content_html(self, content_html: str) -> None:
        """Définit (ou remplace) le corps HTML rendu de la bulle.

        Args:
            content_html: Fragment HTML (Markdown rendu pour l'assistant,
                texte échappé pour l'utilisateur).
        """
        self._content_html = content_html
        self._content.setText(content_html)

    def set_citations(self, citations: tuple[Citation, ...]) -> None:
        """Ajoute les chips de citations cliquables sous le corps.

        Idempotent : un appel ultérieur remplace les chips existantes.

        Args:
            citations: Citations à afficher (vide → aucune chip rendue).
        """
        # Vider l'éventuel précédent contenu.
        while self._citations_layout.count() > 0:
            item = self._citations_layout.takeAt(0)
            if item is None:
                continue
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._citations = citations
        if not citations:
            return
        palette = current_palette()
        sources_label = QLabel("Sources", self)
        sources_pal = sources_label.palette()
        sources_pal.setColor(
            QPalette.ColorRole.WindowText, QColor(palette.text_3)
        )
        sources_label.setPalette(sources_pal)
        small_font = sources_label.font()
        small_font.setPointSize(max(8, small_font.pointSize() - 1))
        sources_label.setFont(small_font)
        self._citations_layout.addWidget(sources_label)
        for citation in citations:
            chip = self._make_chip(citation)
            self._citations_layout.addWidget(chip)

    def to_plain_text(self) -> str:
        """Retourne le contenu brut (rôle + corps + citations) pour les tests.

        Returns:
            Texte agrégé sans balises HTML.
        """
        role = _role_display_label(self._role)
        body = _strip_html(self._content_html)
        parts = [role, body]
        if self._citations:
            parts.append("Sources")
            for c in self._citations:
                parts.append(
                    f"[{c.number}] {c.chapter_title} › {c.section_title}"
                )
        return "\n".join(parts)

    @property
    def role(self) -> str:
        """Rôle de la bulle (``"user"`` / ``"assistant"``)."""
        return self._role

    # --------------------------------------------------------------- internes

    def _make_chip(self, citation: Citation) -> QLabel:
        """Construit une chip de citation (lien stylé inline).

        Args:
            citation: Citation à représenter.

        Returns:
            Le ``QLabel`` Rich Text cliquable.
        """
        palette = current_palette()
        chip = QLabel(self)
        chip.setTextFormat(Qt.TextFormat.RichText)
        chip.setOpenExternalLinks(False)
        chip.setTextInteractionFlags(
            Qt.TextInteractionFlag.LinksAccessibleByMouse
        )
        snippet_tip = html.escape(" ".join(citation.snippet.split()))
        chip.setText(
            f'<a href="{html.escape(citation.anchor)}" '
            f'title="{snippet_tip}" '
            f'style="{_LINK_STYLE}">'
            f'<span style="color: {palette.accent_strong};">'
            f"[{citation.number}] {html.escape(citation.chapter_title)} › "
            f"{html.escape(citation.section_title)}"
            f"</span></a>"
        )
        chip.linkActivated.connect(self._on_link_activated)
        return chip

    def _on_link_activated(self, link: str) -> None:
        """Slot interne : propage le clic sur citation via le signal."""
        self.citation_clicked.emit(link)

    def paintEvent(self, event: object) -> None:  # noqa: N802, ARG002
        """Peint le fond arrondi de la bulle.

        Args:
            event: Événement Qt (non utilisé).
        """
        bg, border, _text, _role_label = _palette_colors(self._role)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(border, 1))
        painter.setBrush(bg)
        # ``-1`` sur la largeur/hauteur pour que la bordure 1px ne soit pas
        # rognée sur les bords.
        rect = self.rect().adjusted(0, 0, -1, -1)
        painter.drawRoundedRect(rect, _BUBBLE_RADIUS, _BUBBLE_RADIUS)


class ChatThread(QScrollArea):
    """Fil de bulles de chat, défilable verticalement.

    Pile les bulles dans un conteneur interne ; les bulles utilisateur sont
    alignées à droite et les bulles assistant à gauche. Expose une API en
    miroir de celle de l'ancien ``QTextBrowser`` pour rester un drop-in :

    - :meth:`show_conversation` (réinitialise le fil)
    - :meth:`add_user_message`
    - :meth:`start_assistant_bubble`
    - :meth:`append_delta`
    - :meth:`finalize_message`
    - :meth:`toPlainText` (compatibilité tests)
    """

    citation_clicked = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Construit un fil vide.

        Args:
            parent: Parent Qt optionnel.
        """
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._container = QWidget(self)
        self._layout = QVBoxLayout(self._container)
        self._layout.setContentsMargins(
            _THREAD_PADDING_HORIZONTAL,
            _THREAD_PADDING_VERTICAL,
            _THREAD_PADDING_HORIZONTAL,
            _THREAD_PADDING_VERTICAL,
        )
        self._layout.setSpacing(_THREAD_BUBBLE_SPACING)
        # Stretch en bas : pousse les bulles en haut quand peu nombreuses.
        self._layout.addStretch(1)
        self.setWidget(self._container)
        self._bubbles: list[MessageBubble] = []
        self._pending_bubble: MessageBubble | None = None
        self._pending_raw_text: str = ""

    # --------------------------------------------------------------- API

    def show_conversation(self, messages: tuple[ChatMessage, ...]) -> None:
        """Affiche une conversation complète (réinitialise le fil)."""
        self._clear()
        for message in messages:
            if message.role == _ROLE_USER:
                self._append_user_bubble(message.content)
            else:
                bubble = self._append_assistant_bubble()
                bubble.set_content_html(render_markdown_fragment(message.content))
                bubble.set_citations(message.citations)

    def add_user_message(self, text: str) -> None:
        """Ajoute une bulle utilisateur avec ``text``."""
        self._append_user_bubble(text)
        self._scroll_to_bottom()

    def start_assistant_bubble(self) -> None:
        """Ajoute une bulle assistant vide pour démarrer un streaming."""
        self._pending_bubble = self._append_assistant_bubble()
        self._pending_raw_text = ""
        self._scroll_to_bottom()

    def append_delta(self, text: str) -> None:
        """Ajoute un fragment de réponse à la bulle assistant en cours."""
        if self._pending_bubble is None:
            return
        self._pending_raw_text += text
        # Pendant le streaming on ne rend pas le Markdown à chaque delta
        # (coûteux) ; on échappe et on transforme les sauts de ligne.
        escaped = html.escape(self._pending_raw_text).replace("\n", "<br>")
        self._pending_bubble.set_content_html(escaped)
        self._scroll_to_bottom()

    def finalize_message(self, message: ChatMessage) -> None:
        """Remplace la bulle en cours par le message finalisé (markdown + citations).

        Si aucune bulle en cours, ajoute une nouvelle bulle assistant.

        Args:
            message: Message assistant complet.
        """
        bubble = self._pending_bubble
        if bubble is None:
            bubble = self._append_assistant_bubble()
        bubble.set_content_html(render_markdown_fragment(message.content))
        bubble.set_citations(message.citations)
        self._pending_bubble = None
        self._pending_raw_text = ""
        self._scroll_to_bottom()

    def toPlainText(self) -> str:  # noqa: N802 — miroir de l'API QTextBrowser
        """Retourne le texte brut agrégé de toutes les bulles (compat tests)."""
        return "\n".join(bubble.to_plain_text() for bubble in self._bubbles)

    # --------------------------------------------------------------- internes

    def _clear(self) -> None:
        """Supprime toutes les bulles existantes."""
        for bubble in self._bubbles:
            parent = bubble.parentWidget()
            if parent is not None and parent is not self._container:
                # Le wrapper d'alignement est entre la bulle et le container.
                parent.deleteLater()
            else:
                bubble.deleteLater()
        self._bubbles.clear()
        self._pending_bubble = None
        self._pending_raw_text = ""

    def _append_user_bubble(self, text: str) -> MessageBubble:
        """Ajoute une bulle utilisateur (alignée à droite) avec le texte fourni."""
        bubble = MessageBubble(_ROLE_USER, self._container)
        bubble.citation_clicked.connect(self.citation_clicked.emit)
        escaped = html.escape(text).replace("\n", "<br>")
        bubble.set_content_html(escaped)
        self._add_aligned(bubble, align_right=True)
        return bubble

    def _append_assistant_bubble(self) -> MessageBubble:
        """Ajoute une bulle assistant vide (alignée à gauche)."""
        bubble = MessageBubble(_ROLE_ASSISTANT, self._container)
        bubble.citation_clicked.connect(self.citation_clicked.emit)
        self._add_aligned(bubble, align_right=False)
        return bubble

    def _add_aligned(self, bubble: MessageBubble, *, align_right: bool) -> None:
        """Englobe la bulle dans un layout horizontal avec stretch pour aligner."""
        wrap = QWidget(self._container)
        wrap.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        wrap.setAutoFillBackground(False)
        row = QHBoxLayout(wrap)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        if align_right:
            row.addStretch(1)
            row.addWidget(bubble, stretch=4)
        else:
            row.addWidget(bubble, stretch=4)
            row.addStretch(1)
        # Insertion avant le stretch final (qui pousse vers le haut quand vide).
        self._layout.insertWidget(self._layout.count() - 1, wrap)
        self._bubbles.append(bubble)

    def _scroll_to_bottom(self) -> None:
        """Défile le fil pour afficher la dernière bulle."""
        scroll_bar = self.verticalScrollBar()
        if scroll_bar is not None:
            scroll_bar.setValue(scroll_bar.maximum())
