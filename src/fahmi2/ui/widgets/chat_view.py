"""Widget conversationnel de l'onglet Dialogue.

Fil de messages (``QTextBrowser`` HTML), zone de saisie, liste latérale des
conversations et libellé de coût cumulé. Le rendu du message assistant est
incrémental (deltas du streaming) puis finalisé avec ses citations cliquables.
Le widget est passif : il **émet** des signaux et **expose** des méthodes pilotées
par le ``ChatController`` (toute la logique d'état vit dans le ViewModel/contrôleur).
"""

from __future__ import annotations

import html

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from fahmi2.domain.chat import ChatMessage, Citation
from fahmi2.domain.enums import ChatTabState
from fahmi2.infra.export.markdown_pdf import render_markdown_fragment
from fahmi2.ui._buttons import BUTTON_ROLE_PRIMARY, make_role_button

_NEW_CONVERSATION_LABEL = "＋ Nouvelle conversation"
_LANGUAGE_COMBO_TOOLTIP = (
    "Langue du corpus pour une nouvelle conversation : lecture, citations et réponse."
)
#: Le sélecteur de langue n'a de sens qu'à partir de 2 langues produites (un choix).
_MIN_LANGUAGES_FOR_SELECTOR = 2
_DELETE_CONVERSATION_LABEL = "Supprimer la conversation"
_SEND_LABEL = "Envoyer"
_INPUT_PLACEHOLDER = "Pose une question sur le cours…"
_NO_CORPUS_BANNER = "Lance d'abord une génération pour dialoguer avec ce cours."
_COST_PREFIX = "Coût cumulé"
_ROLE_LABEL = {"user": "Vous", "assistant": "Assistant"}
_ROLE_USER = "user"
_ROLE_ASSISTANT = "assistant"
_CONVERSATION_ID_ROLE = int(Qt.ItemDataRole.UserRole)

#: Largeur (%) des bulles utilisateur (alignées à droite).
_USER_BUBBLE_WIDTH_PCT = "72%"
#: Largeur (%) des bulles assistant (alignées à gauche).
_ASSISTANT_BUBBLE_WIDTH_PCT = "85%"
#: Fond et bordure des bulles (HTML inline ; QTextBrowser ne supporte pas
#: ``border-radius`` — on se contente d'un encadré coloré, plus un alignement
#: gauche/droite par ``<table align>``). Couleurs alignées sur les tokens
#: clairs (le thème sombre garde les mêmes contrastes : fond accent doux
#: pour utilisateur, surface bordée pour assistant).
_USER_BUBBLE_BG = "#e3f0fb"
_USER_BUBBLE_BORDER = "#cfe6fa"
_USER_BUBBLE_TEXT = "#0a4f93"
_ASSISTANT_BUBBLE_BG = "#ffffff"
_ASSISTANT_BUBBLE_BORDER = "#e5e7eb"
_ASSISTANT_BUBBLE_TEXT = "#1f2328"
#: Chips de source (pastilles inline cliquables sous une bulle assistant).
_CHIP_BG = "#f0f4f9"
_CHIP_BORDER = "#d6dae0"
_CHIP_TEXT = "#0a4f93"
#: Couleur de la ligne « Sources » (libellé discret au-dessus des chips).
_SOURCES_LABEL_COLOR = "#8b95a1"

#: Style du fil : liens lisibles, code et tableaux discrets.
_THREAD_STYLESHEET = (
    "a { color: #0a4f93; text-decoration: none; }"
    " code { background-color: #eef0f4; }"
    " th, td { border: 1px solid #d6dae0; padding: 2px 6px; }"
)
_PASSAGE_DIALOG_WIDTH = 560
_PASSAGE_DIALOG_HEIGHT = 420


class ChatView(QWidget):
    """Vue conversationnelle (passive) de l'onglet Dialogue."""

    question_submitted = Signal(str)
    new_conversation_requested = Signal(str)  # code langue ("" = langue par défaut)
    conversation_selected = Signal(str)
    conversation_delete_requested = Signal(str)
    citation_clicked = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Construit la vue.

        Args:
            parent: Parent Qt optionnel.
        """
        super().__init__(parent)
        self._finalized_html: list[str] = []
        self._pending_html: str | None = None

        root = QHBoxLayout(self)

        self._conversations = QListWidget(self)
        self._conversations.setMaximumWidth(240)
        self._conversations.itemClicked.connect(self._on_conversation_clicked)
        self._conversations.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
        self._conversations.customContextMenuRequested.connect(
            self._on_conversation_menu
        )
        self._language_combo = QComboBox(self)
        self._language_combo.setToolTip(_LANGUAGE_COMBO_TOOLTIP)
        self._language_combo.setVisible(False)  # masqué tant qu'il n'y a pas >1 langue
        self._new_button = QPushButton(_NEW_CONVERSATION_LABEL, self)
        self._new_button.clicked.connect(self._on_new_conversation)
        left = QVBoxLayout()
        left.addWidget(self._language_combo)
        left.addWidget(self._new_button)
        left.addWidget(self._conversations, stretch=1)
        root.addLayout(left)

        self._banner = QLabel(_NO_CORPUS_BANNER, self)
        self._banner.setWordWrap(True)
        self._banner.setVisible(False)
        self._thread = QTextBrowser(self)
        self._thread.setOpenLinks(False)
        self._thread.anchorClicked.connect(
            lambda url: self.citation_clicked.emit(url.toString())
        )
        self._thread.document().setDefaultStyleSheet(_THREAD_STYLESHEET)
        self._cost_label = QLabel(f"{_COST_PREFIX} · $0.0000", self)
        self._input = QLineEdit(self)
        self._input.setPlaceholderText(_INPUT_PLACEHOLDER)
        self._input.returnPressed.connect(self._on_send)
        self._send_button = make_role_button(
            self, _SEND_LABEL, role=BUTTON_ROLE_PRIMARY
        )
        self._send_button.clicked.connect(self._on_send)
        input_row = QHBoxLayout()
        input_row.addWidget(self._input, stretch=1)
        input_row.addWidget(self._send_button)
        right = QVBoxLayout()
        right.addWidget(self._banner)
        right.addWidget(self._thread, stretch=1)
        right.addWidget(self._cost_label)
        right.addLayout(input_row)
        root.addLayout(right, stretch=1)

    # ------------------------------------------------------------- pilotage
    def set_conversations(self, items: list[tuple[str, str]]) -> None:
        """Remplit la liste des conversations.

        Args:
            items: Liste de ``(conversation_id, titre)``.
        """
        self._conversations.clear()
        for conversation_id, title in items:
            entry = QListWidgetItem(title)
            entry.setData(_CONVERSATION_ID_ROLE, conversation_id)
            self._conversations.addItem(entry)

    def set_languages(self, items: list[tuple[str, str]], current: str) -> None:
        """Peuple le sélecteur de langue du corpus (utilisé par une nouvelle conversation).

        Masqué s'il y a 0 ou 1 langue produite (aucun choix à offrir → comportement
        mono-langue inchangé).

        Args:
            items: Liste de ``(code_langue, libellé)`` des langues produites.
            current: Code de la langue à présélectionner.
        """
        self._language_combo.blockSignals(True)
        self._language_combo.clear()
        for code, label in items:
            self._language_combo.addItem(label, code)
        index = self._language_combo.findData(current)
        if index >= 0:
            self._language_combo.setCurrentIndex(index)
        self._language_combo.blockSignals(False)
        self._language_combo.setVisible(len(items) >= _MIN_LANGUAGES_FOR_SELECTOR)

    def _current_language_code(self) -> str:
        """Code de la langue actuellement sélectionnée (``""`` si aucune)."""
        data = self._language_combo.currentData()
        return str(data) if data is not None else ""

    def _on_new_conversation(self) -> None:
        """Émet la demande de nouvelle conversation avec la langue sélectionnée."""
        self.new_conversation_requested.emit(self._current_language_code())

    def show_conversation(self, messages: tuple[ChatMessage, ...]) -> None:
        """Affiche une conversation complète (réinitialise le fil).

        Args:
            messages: Messages à afficher.
        """
        self._finalized_html = [_message_html(m) for m in messages]
        self._pending_html = None
        self._render()

    def add_user_message(self, text: str) -> None:
        """Ajoute une bulle utilisateur.

        Args:
            text: Texte de la question.
        """
        self._finalized_html.append(
            _message_html(ChatMessage(role="user", content=text))
        )
        self._render()

    def start_assistant_bubble(self) -> None:
        """Initialise une bulle assistant vide (début du streaming)."""
        self._pending_html = ""
        self._render()

    def append_delta(self, text: str) -> None:
        """Ajoute un fragment de réponse à la bulle assistant en cours.

        Args:
            text: Incrément de texte.
        """
        self._pending_html = (self._pending_html or "") + html.escape(text)
        self._render()

    def finalize_message(self, message: ChatMessage) -> None:
        """Remplace la bulle en cours par le message finalisé (citations + sources).

        Args:
            message: Message assistant complet.
        """
        self._pending_html = None
        self._finalized_html.append(_message_html(message))
        self._render()

    def set_state(self, state: ChatTabState) -> None:
        """Active/désactive la saisie et le bandeau selon l'état.

        Args:
            state: État UX courant.
        """
        self._banner.setVisible(state is ChatTabState.NO_CORPUS)
        # READY ou ERROR : saisie active (après une erreur, l'utilisateur relance).
        can_send = state in (ChatTabState.READY, ChatTabState.ERROR)
        self._input.setEnabled(can_send)
        self._send_button.setEnabled(can_send)
        # Pendant le streaming, gèle les contrôles de conversation : changer/créer une
        # conversation rechargerait le corpus (ignoré par le contrôleur) — on le rend
        # visible plutôt que silencieux.
        idle = state is not ChatTabState.ANSWERING
        self._new_button.setEnabled(idle)
        self._language_combo.setEnabled(idle)
        self._conversations.setEnabled(idle)

    def set_total_cost(self, usd: float) -> None:
        """Met à jour le libellé de coût cumulé.

        Args:
            usd: Coût cumulé en USD.
        """
        self._cost_label.setText(f"{_COST_PREFIX} · ${usd:.4f}")

    # ------------------------------------------------------------- internes
    def _on_send(self) -> None:
        text = self._input.text().strip()
        if not text:
            return
        self._input.clear()
        self.question_submitted.emit(text)

    def _on_conversation_clicked(self, item: QListWidgetItem) -> None:
        conversation_id = item.data(_CONVERSATION_ID_ROLE)
        if isinstance(conversation_id, str):
            self.conversation_selected.emit(conversation_id)

    def _on_conversation_menu(self, pos: QPoint) -> None:
        """Menu contextuel (clic droit) d'une conversation : suppression."""
        item = self._conversations.itemAt(pos)
        if item is None:
            return
        conversation_id = item.data(_CONVERSATION_ID_ROLE)
        if not isinstance(conversation_id, str):
            return
        menu = QMenu(self._conversations)
        delete_action = menu.addAction(_DELETE_CONVERSATION_LABEL)
        chosen = menu.exec(self._conversations.mapToGlobal(pos))
        if chosen is delete_action:
            self.conversation_delete_requested.emit(conversation_id)

    def _render(self) -> None:
        blocks = list(self._finalized_html)
        if self._pending_html is not None:
            blocks.append(
                _bubble_html(_ROLE_LABEL["assistant"], self._pending_html or "…")
            )
        self._thread.setHtml("".join(blocks))
        self._thread.moveCursor(QTextCursor.MoveOperation.End)


def _bubble_html(role_label: str, body_html: str) -> str:
    """Rend une bulle de chat assistant (alignée à gauche, encadrée discrète).

    Utilisé pour la bulle de streaming en cours (le rôle est forcément
    « Assistant » à ce stade — l'utilisateur a déjà finalisé son message).

    Args:
        role_label: Étiquette à afficher en tête.
        body_html: Corps HTML déjà échappé (deltas du streaming).

    Returns:
        Le fragment HTML de la bulle.
    """
    return _wrap_assistant_bubble(role_label, body_html, citations_html="")


def _wrap_user_bubble(role_label: str, body_html: str) -> str:
    """Rend la bulle utilisateur (alignée à droite, fond accent doux).

    Args:
        role_label: « Vous ».
        body_html: Corps HTML (déjà échappé).

    Returns:
        Le fragment HTML.
    """
    return (
        f'<table align="right" width="{_USER_BUBBLE_WIDTH_PCT}" '
        f'cellpadding="10" cellspacing="0" '
        f'bgcolor="{_USER_BUBBLE_BG}" '
        f'style="margin: 6px 0; border: 1px solid {_USER_BUBBLE_BORDER};">'
        f"<tr><td>"
        f'<div style="color: {_USER_BUBBLE_TEXT}; font-weight: 600; '
        f'font-size: 11px; margin-bottom: 4px;">'
        f"{html.escape(role_label)}</div>"
        f'<div style="color: {_USER_BUBBLE_TEXT};">{body_html}</div>'
        f"</td></tr></table>"
    )


def _wrap_assistant_bubble(
    role_label: str, body_html: str, *, citations_html: str
) -> str:
    """Rend la bulle assistant (alignée à gauche, surface bordée) + citations.

    Args:
        role_label: « Assistant ».
        body_html: Corps HTML (Markdown rendu).
        citations_html: Fragment HTML des citations (ou ``""``).

    Returns:
        Le fragment HTML.
    """
    return (
        f'<table align="left" width="{_ASSISTANT_BUBBLE_WIDTH_PCT}" '
        f'cellpadding="12" cellspacing="0" '
        f'bgcolor="{_ASSISTANT_BUBBLE_BG}" '
        f'style="margin: 6px 0; border: 1px solid {_ASSISTANT_BUBBLE_BORDER};">'
        f"<tr><td>"
        f'<div style="color: {_SOURCES_LABEL_COLOR}; font-weight: 600; '
        f'font-size: 11px; margin-bottom: 4px;">'
        f"{html.escape(role_label)}</div>"
        f'<div style="color: {_ASSISTANT_BUBBLE_TEXT};">{body_html}</div>'
        f"{citations_html}"
        f"</td></tr></table>"
    )


def _message_html(message: ChatMessage) -> str:
    """Rend un message complet en HTML (Markdown rendu pour l'assistant).

    Args:
        message: Message à rendre.

    Returns:
        Le fragment HTML du message (bulle + citations si assistant).
    """
    role_label = _ROLE_LABEL.get(message.role, message.role)
    if message.role == _ROLE_ASSISTANT:
        body = render_markdown_fragment(message.content)
        citations = _citations_html(message.citations)
        return _wrap_assistant_bubble(role_label, body, citations_html=citations)
    body = html.escape(message.content).replace("\n", "<br>")
    return _wrap_user_bubble(role_label, body)


def _citations_html(citations: tuple[Citation, ...]) -> str:
    """Rend la ligne « Sources » en chips cliquables, ou ``""`` si aucune.

    Args:
        citations: Citations du message assistant.

    Returns:
        Le fragment HTML des sources sous forme de chips inline (vide si
        aucune citation).
    """
    if not citations:
        return ""
    # ``QTextDocument`` n'applique pas ``background-color`` / ``border`` aux
    # ``<a>`` ; on enveloppe le texte dans un ``<span>`` qui, lui, prend bien
    # les propriétés inline. Chaque source est placée sur sa propre ligne
    # (``<div>`` par citation) pour faciliter la lecture quand il y en a
    # plusieurs.
    line_template = (
        '<div style="margin: 2px 0;">'
        '<a href="{href}" title="{tip}" style="text-decoration: none;">'
        '<span style="background-color: {bg}; color: {color}; '
        'padding: 2px 8px;">[{num}] {chapter} › {section}</span>'
        "</a>"
        "</div>"
    )
    chips = "".join(
        line_template.format(
            href=html.escape(c.anchor),
            tip=_tooltip(c.snippet),
            bg=_CHIP_BG,
            color=_CHIP_TEXT,
            num=c.number,
            chapter=html.escape(c.chapter_title),
            section=html.escape(c.section_title),
        )
        for c in citations
    )
    return (
        f'<div style="margin-top: 8px; color: {_SOURCES_LABEL_COLOR}; '
        f'font-size: 11px;">Sources</div>'
        f'<div style="margin-top: 4px;">{chips}</div>'
    )


def _tooltip(snippet: str) -> str:
    """Aperçu (échappé, sur une ligne) du passage cité, pour l'attribut ``title``.

    Args:
        snippet: Extrait du passage (déjà tronqué côté domaine).

    Returns:
        Le texte d'infobulle, échappé HTML et aplati sur une seule ligne.
    """
    return html.escape(" ".join(snippet.split()))


def show_passage_dialog(parent: QWidget, *, title: str, markdown_text: str) -> None:
    """Affiche un passage source (Markdown rendu) dans un dialogue scrollable.

    Args:
        parent: Fenêtre parente.
        title: Titre du dialogue (chapitre › section).
        markdown_text: Contenu Markdown du passage cité.
    """
    dialog = QDialog(parent)
    dialog.setWindowTitle(title)
    dialog.resize(_PASSAGE_DIALOG_WIDTH, _PASSAGE_DIALOG_HEIGHT)
    layout = QVBoxLayout(dialog)
    browser = QTextBrowser(dialog)
    browser.document().setDefaultStyleSheet(_THREAD_STYLESHEET)
    browser.setHtml(render_markdown_fragment(markdown_text))
    layout.addWidget(browser)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, parent=dialog)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)
    dialog.exec()
