"""Widget conversationnel de l'onglet Dialogue.

Fil de messages (``QTextBrowser`` HTML), zone de saisie, liste latérale des
conversations et libellé de coût cumulé. Le rendu du message assistant est
incrémental (deltas du streaming) puis finalisé avec ses citations cliquables.
Le widget est passif : il **émet** des signaux et **expose** des méthodes pilotées
par le ``ChatController`` (toute la logique d'état vit dans le ViewModel/contrôleur).
"""

from __future__ import annotations

import html

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from fahmi2.domain.chat import ChatMessage
from fahmi2.domain.enums import ChatTabState

_NEW_CONVERSATION_LABEL = "＋ Nouvelle conversation"
_SEND_LABEL = "Envoyer"
_INPUT_PLACEHOLDER = "Pose une question sur le cours…"
_NO_CORPUS_BANNER = "Lance d'abord une génération pour dialoguer avec ce cours."
_COST_PREFIX = "Coût cumulé : "
_ROLE_LABEL = {"user": "Vous", "assistant": "Assistant"}
_CONVERSATION_ID_ROLE = int(Qt.ItemDataRole.UserRole)


class ChatView(QWidget):
    """Vue conversationnelle (passive) de l'onglet Dialogue."""

    question_submitted = Signal(str)
    new_conversation_requested = Signal()
    conversation_selected = Signal(str)
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
        new_button = QPushButton(_NEW_CONVERSATION_LABEL, self)
        new_button.clicked.connect(self.new_conversation_requested)
        left = QVBoxLayout()
        left.addWidget(new_button)
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
        self._cost_label = QLabel(f"{_COST_PREFIX}$0.0000", self)
        self._input = QLineEdit(self)
        self._input.setPlaceholderText(_INPUT_PLACEHOLDER)
        self._input.returnPressed.connect(self._on_send)
        self._send_button = QPushButton(_SEND_LABEL, self)
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
            _bubble_html(_ROLE_LABEL["user"], html.escape(text))
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
        can_send = state is ChatTabState.READY
        self._input.setEnabled(can_send)
        self._send_button.setEnabled(can_send)

    def set_total_cost(self, usd: float) -> None:
        """Met à jour le libellé de coût cumulé.

        Args:
            usd: Coût cumulé en USD.
        """
        self._cost_label.setText(f"{_COST_PREFIX}${usd:.4f}")

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

    def _render(self) -> None:
        blocks = list(self._finalized_html)
        if self._pending_html is not None:
            blocks.append(
                _bubble_html(_ROLE_LABEL["assistant"], self._pending_html or "…")
            )
        self._thread.setHtml("".join(blocks))
        self._thread.moveCursor(QTextCursor.MoveOperation.End)


def _bubble_html(role_label: str, body_html: str) -> str:
    """Rend une bulle (rôle + corps HTML déjà échappé)."""
    return f"<p><b>{html.escape(role_label)} :</b><br>{body_html}</p>"


def _message_html(message: ChatMessage) -> str:
    """Rend un message complet (corps + citations cliquables si assistant)."""
    role_label = _ROLE_LABEL.get(message.role, message.role)
    body = html.escape(message.content).replace("\n", "<br>")
    if not message.citations:
        return _bubble_html(role_label, body)
    links = " ".join(
        f'<a href="{html.escape(c.anchor)}">[§ {html.escape(c.chapter_title)} › '
        f"{html.escape(c.section_title)}]</a>"
        for c in message.citations
    )
    return _bubble_html(role_label, f"{body}<br><small>Sources : {links}</small>")
