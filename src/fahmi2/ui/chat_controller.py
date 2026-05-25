"""``ChatController`` — orchestration de l'onglet Dialogue.

Calqué sur ``PedagogyController`` : maintient le projet affiché, charge le corpus
sur disque, construit le retriever (lexical + query expansion), persiste les
conversations et déporte le streaming dans un ``QThread`` worker qui émet des
signaux Qt (``delta`` / ``completed`` / ``failed``). Toute la logique d'état vit
dans le ``ChatViewModel`` (sans Qt).
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import cast

from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtWidgets import QDialog, QMessageBox, QWidget

from fahmi2.app.chat_conversation_store import ChatConversationStore
from fahmi2.app.project_service import ProjectService
from fahmi2.app.secrets_service import SecretsService
from fahmi2.chat.chat_service import ChatService
from fahmi2.chat.corpus import load_corpus_chunks
from fahmi2.chat.retriever_factory import build_passage_retriever
from fahmi2.core.config.paths import AppPaths
from fahmi2.core.retrieval.passages import PassageRetriever
from fahmi2.domain.chat import (
    CHAT_WORKSPACE_SUBDIR,
    ChatMessage,
    ChatSettings,
    Conversation,
    CorpusChunk,
)
from fahmi2.domain.enums import Language
from fahmi2.domain.generation import (
    GENERATION_OUTPUT_SUBDIR,
    GENERATION_WORKSPACE_SUBDIR,
)
from fahmi2.domain.ids import ConversationId, ProjectId
from fahmi2.domain.project import Project
from fahmi2.infra.embeddings.interface import EmbeddingProvider
from fahmi2.infra.embeddings.openai_adapter import OpenAIEmbeddingProvider
from fahmi2.infra.llm.deepseek_adapter import DeepSeekAdapter
from fahmi2.infra.llm.interface import LLMProvider
from fahmi2.infra.prompts.loader import PromptLoader
from fahmi2.infra.storage.fs_artifacts import FsArtifactStore
from fahmi2.pedagogy.sources import resolve_content_language, source_mtime_ns
from fahmi2.ui.dialogs.chat_settings_view import ChatSettingsView
from fahmi2.ui.viewmodels.chat_view_model import ChatViewModel
from fahmi2.ui.widgets.chat_view import ChatView

_INDEX_FILENAME_TEMPLATE = "index.{language}.npz"
_NO_PROJECT_TITLE = "Aucun projet sélectionné"
_NO_KEY_TITLE = "Clé DeepSeek manquante"
_NO_KEY_MESSAGE = (
    "Renseigne la clé DeepSeek dans « Édition → Paramètres globaux » pour dialoguer."
)
_FAILED_TITLE = "Le dialogue s'est terminé sur une erreur"

LlmProviderFactory = Callable[[str], LLMProvider]


class _ChatWorker(QObject):
    """Worker QObject : streame une réponse et émet des signaux Qt."""

    delta = Signal(str)
    completed = Signal(object)  # ChatMessage
    failed = Signal(str)

    def __init__(
        self,
        *,
        service: ChatService,
        retriever: PassageRetriever,
        question: str,
        history: tuple[ChatMessage, ...],
        settings: ChatSettings,
        language: Language,
    ) -> None:
        """Construit le worker.

        Args:
            service: Moteur de chat.
            retriever: Retriever de passages.
            question: Question de l'utilisateur.
            history: Historique (hors question courante).
            settings: Réglages du chat.
            language: Langue de réponse.
        """
        super().__init__()
        self._service = service
        self._retriever = retriever
        self._question = question
        self._history = history
        self._settings = settings
        self._language = language

    def run(self) -> None:
        """Itère le flux et émet les signaux (delta, completed, failed)."""
        try:
            for chunk in self._service.stream_answer(
                question=self._question,
                retriever=self._retriever,
                glossary_text="",
                history=self._history,
                settings=self._settings,
                language=self._language,
            ):
                if chunk.message is not None:
                    self.completed.emit(chunk.message)
                elif chunk.content_delta:
                    self.delta.emit(chunk.content_delta)
        except Exception as exc:  # noqa: BLE001 — isolation worker thread
            self.failed.emit(f"{type(exc).__name__}: {exc}")


class ChatController(QObject):
    """Orchestre l'onglet Dialogue (corpus, conversations, streaming)."""

    #: Émis quand une réponse est finalisée (utile aux tests et à l'UI).
    answer_completed = Signal()

    def __init__(
        self,
        *,
        view: ChatView,
        window: QWidget,
        project_service: ProjectService,
        secrets_service: SecretsService,
        app_paths: AppPaths,
        llm_provider_factory: LlmProviderFactory | None = None,
    ) -> None:
        """Construit le contrôleur et branche les signaux de la vue.

        Args:
            view: Vue conversationnelle.
            window: Fenêtre parente (parent des dialogues).
            project_service: Service projets.
            secrets_service: Service secrets (clé DeepSeek).
            app_paths: Chemins applicatifs (override des prompts).
            llm_provider_factory: Fabrique de ``LLMProvider`` (injectable pour les
                tests) ; défaut = ``DeepSeekAdapter``.
        """
        super().__init__(window)
        self._view = view
        self._window = window
        self._project_service = project_service
        self._secrets_service = secrets_service
        self._prompts = PromptLoader(override_dir=app_paths.prompts_override_dir)
        self._llm_factory: LlmProviderFactory = (
            llm_provider_factory or (lambda key: DeepSeekAdapter(api_key=key))
        )
        self._vm = ChatViewModel()
        self._project: Project | None = None
        self._content_language: Language | None = None
        self._chunks: tuple[CorpusChunk, ...] = ()
        self._conversation: Conversation | None = None
        self._store: ChatConversationStore | None = None
        self._thread: QThread | None = None
        self._worker: _ChatWorker | None = None

        view.question_submitted.connect(self.submit_question)
        view.new_conversation_requested.connect(self.new_conversation)
        view.conversation_selected.connect(self.select_conversation)
        view.citation_clicked.connect(self._on_citation_clicked)

    # ------------------------------------------------------------------ project
    def on_project_selected(self, project_id: ProjectId) -> None:
        """Charge le projet, le corpus et les conversations.

        Args:
            project_id: Projet sélectionné.
        """
        project = self._project_service.get_project(project_id)
        if project is None:
            return
        self._project = project
        generation_output_dir = self._generation_output_dir(project)
        source_language = (
            project.generation.source_language
            if project.generation is not None
            else Language.FR
        )
        self._content_language = resolve_content_language(
            generation_output_dir, source_language, source_language
        )
        if self._content_language is not None:
            self._chunks = load_corpus_chunks(
                generation_output_dir=generation_output_dir,
                generation_dir=self._generation_dir(project),
                language=self._content_language,
            )
        else:
            self._chunks = ()
        self._store = ChatConversationStore(
            artifacts=FsArtifactStore(), chat_dir=self._chat_dir(project)
        )
        self._conversation = self._vm.start_conversation(
            self._content_language or Language.FR
        )
        self._refresh_conversations()
        self._view.show_conversation(())
        self._view.set_total_cost(0.0)
        self._apply_state()

    @property
    def current_project_id(self) -> ProjectId | None:
        """Identifiant du projet affiché, ou ``None``."""
        return self._project.id if self._project is not None else None

    def clear_current_project(self) -> None:
        """Réinitialise le contrôleur (projet supprimé)."""
        self._project = None
        self._chunks = ()
        self._conversation = None
        self._store = None
        self._view.set_conversations([])
        self._view.show_conversation(())
        self._apply_state()

    # ------------------------------------------------------------------ actions
    def submit_question(self, text: str) -> None:
        """Lance la génération en flux d'une réponse à ``text``.

        Args:
            text: Question de l'utilisateur.
        """
        if (
            self._project is None
            or not self._chunks
            or self._conversation is None
            or self._thread is not None
        ):
            return
        if not self._secrets_service.has_deepseek_key():
            QMessageBox.critical(self._window, _NO_KEY_TITLE, _NO_KEY_MESSAGE)
            return
        api_key = self._secrets_service.get_deepseek_api_key()
        assert api_key is not None  # garanti par has_deepseek_key
        settings = self._project.chat or ChatSettings()
        llm = self._llm_factory(api_key)
        service = ChatService(llm_provider=llm, prompt_loader=self._prompts)
        retriever = self._build_retriever(self._chunks, settings, llm)

        history = self._conversation.messages
        self._conversation = self._vm.append_user(self._conversation, text)
        self._view.add_user_message(text)
        self._view.start_assistant_bubble()
        self._apply_state(answering=True)

        worker = _ChatWorker(
            service=service,
            retriever=retriever,
            question=text,
            history=history,
            settings=settings,
            language=self._conversation.language,
        )
        thread = QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.delta.connect(self._view.append_delta)
        worker.completed.connect(self._on_completed)
        worker.failed.connect(self._on_failed)
        worker.completed.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        self._worker = worker
        self._thread = thread
        thread.start()

    def new_conversation(self) -> None:
        """Démarre une nouvelle conversation vide."""
        if self._project is None:
            return
        self._conversation = self._vm.start_conversation(
            self._content_language or Language.FR
        )
        self._view.show_conversation(())
        self._view.set_total_cost(0.0)
        self._apply_state()

    def select_conversation(self, conversation_id: str) -> None:
        """Charge et affiche une conversation existante.

        Args:
            conversation_id: Identifiant de la conversation.
        """
        if self._store is None:
            return
        conversation = self._store.load(ConversationId(value=conversation_id))
        if conversation is None:
            return
        self._conversation = conversation
        self._view.show_conversation(conversation.messages)
        self._view.set_total_cost(conversation.total_cost_usd())
        self._apply_state()

    def open_chat_settings(self) -> None:
        """Ouvre le dialogue de réglages et persiste ``Project.chat``."""
        if self._project is None:
            QMessageBox.warning(
                self._window,
                _NO_PROJECT_TITLE,
                "Sélectionne un projet dans la sidebar avant de configurer.",
            )
            return
        dialog = ChatSettingsView(parent=self._window, initial=self._project.chat)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self._project_service.update_project(
            self._project.with_chat(dialog.get_chat_settings())
        )
        self.on_project_selected(self._project.id)

    # ------------------------------------------------------------------ slots
    def _on_completed(self, message: object) -> None:
        """Slot : réponse finalisée (persiste + affiche citations + coût)."""
        chat_message = cast("ChatMessage", message)
        if self._conversation is not None and self._store is not None:
            self._conversation = self._vm.append_assistant(
                self._conversation, chat_message
            )
            self._store.save(self._conversation)
            self._view.finalize_message(chat_message)
            self._view.set_total_cost(self._conversation.total_cost_usd())
            self._refresh_conversations()
        self._cleanup_thread()
        self._apply_state()
        self.answer_completed.emit()

    def _on_failed(self, error_message: str) -> None:
        """Slot : streaming terminé sur exception."""
        QMessageBox.critical(self._window, _FAILED_TITLE, error_message)
        self._cleanup_thread()
        self._apply_state(error=True)

    def _on_citation_clicked(self, anchor: str) -> None:
        """Slot : clic sur une citation → affiche le passage source."""
        for chunk in self._chunks:
            if chunk.anchor == anchor:
                QMessageBox.information(
                    self._window,
                    f"{chunk.chapter_title} › {chunk.section_title}",
                    chunk.text,
                )
                return

    # ------------------------------------------------------------------ helpers
    def _apply_state(self, *, answering: bool = False, error: bool = False) -> None:
        """Recalcule l'état UX et l'applique à la vue."""
        state = self._vm.resolve_state(
            has_project=self._project is not None,
            has_corpus=bool(self._chunks),
            is_answering=answering,
            has_error=error,
        )
        self._view.set_state(state)

    def _refresh_conversations(self) -> None:
        """Rafraîchit la liste latérale des conversations."""
        if self._store is None:
            return
        items = [
            (conversation.conversation_id.value, conversation.title)
            for conversation in self._store.list_all()
        ]
        self._view.set_conversations(items)

    def _build_retriever(
        self, chunks: tuple[CorpusChunk, ...], settings: ChatSettings, llm: LLMProvider
    ) -> PassageRetriever:
        """Construit le retriever via la fabrique (résolution AUTO + repli).

        Args:
            chunks: Passages du corpus.
            settings: Réglages du chat.
            llm: Provider LLM (query expansion).

        Returns:
            Le ``PassageRetriever`` adapté à la stratégie configurée.
        """
        assert self._project is not None and self._content_language is not None
        embedding_provider, embedding_model = self._embedding_provider()
        generation_output_dir = self._generation_output_dir(self._project)
        return build_passage_retriever(
            chunks=chunks,
            settings=settings,
            prompts=self._prompts,
            llm=llm,
            embedding_provider=embedding_provider,
            embedding_model=embedding_model,
            index_path=self._index_path(self._project, self._content_language),
            source_mtime_ns=source_mtime_ns(
                generation_output_dir, self._content_language
            ),
            language=self._content_language,
            artifacts=FsArtifactStore(),
        )

    def _embedding_provider(self) -> tuple[EmbeddingProvider | None, str]:
        """Fournit un ``EmbeddingProvider`` OpenAI si une clé est disponible.

        Returns:
            ``(provider, model)`` ; ``(None, "")`` sans clé OpenAI (repli lexical).
        """
        if not self._secrets_service.has_openai_key():
            return None, ""
        openai_key = self._secrets_service.get_openai_api_key()
        assert openai_key is not None  # garanti par has_openai_key
        provider = OpenAIEmbeddingProvider(api_key=openai_key)
        return provider, provider.model

    @staticmethod
    def _index_path(project: Project, language: Language) -> Path:
        return (
            project.workspace_folder
            / CHAT_WORKSPACE_SUBDIR
            / _INDEX_FILENAME_TEMPLATE.format(language=language.value)
        )

    def _cleanup_thread(self) -> None:
        """Réinitialise les références au worker/thread après fin."""
        self._worker = None
        self._thread = None

    @staticmethod
    def _generation_output_dir(project: Project) -> Path:
        return (
            project.workspace_folder
            / GENERATION_WORKSPACE_SUBDIR
            / GENERATION_OUTPUT_SUBDIR
        )

    @staticmethod
    def _generation_dir(project: Project) -> Path:
        return project.workspace_folder / GENERATION_WORKSPACE_SUBDIR

    @staticmethod
    def _chat_dir(project: Project) -> Path:
        return project.workspace_folder / CHAT_WORKSPACE_SUBDIR
