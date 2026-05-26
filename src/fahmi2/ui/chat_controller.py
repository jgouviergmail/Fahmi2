"""``ChatController`` — orchestration de l'onglet Dialogue.

Calqué sur ``PedagogyController`` : maintient le projet affiché, charge le corpus
sur disque, construit le retriever (lexical + query expansion), persiste les
conversations et déporte le streaming dans un ``QThread`` worker qui émet des
signaux Qt (``delta`` / ``completed`` / ``failed``). Toute la logique d'état vit
dans le ``ChatViewModel`` (sans Qt).
"""

from __future__ import annotations

from collections.abc import Callable
from functools import partial
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
from fahmi2.pedagogy.labels import format_glossary_terms
from fahmi2.pedagogy.sources import (
    glossary_master_mtime_ns,
    load_glossary_master_terms,
    resolve_content_language,
    source_mtime_ns,
)
from fahmi2.ui.dialogs.chat_settings_view import ChatSettingsView
from fahmi2.ui.viewmodels.chat_view_model import ChatViewModel
from fahmi2.ui.widgets.chat_view import ChatView, show_passage_dialog

_INDEX_FILENAME_TEMPLATE = "index.{language}.npz"
_NO_PROJECT_TITLE = "Aucun projet sélectionné"
_NO_KEY_TITLE = "Clé DeepSeek manquante"
_NO_KEY_MESSAGE = (
    "Renseigne la clé DeepSeek dans « Édition → Paramètres globaux » pour dialoguer."
)
_FAILED_TITLE = "Le dialogue s'est terminé sur une erreur"
_DELETE_CONFIRM_TITLE = "Supprimer la conversation"
_DELETE_CONFIRM_MESSAGE = (
    "Supprimer définitivement cette conversation ? Cette action est irréversible."
)

LlmProviderFactory = Callable[[str], LLMProvider]

#: Empreinte de fraîcheur du corpus : (langue de contenu, mtime consolidé, mtime glossaire).
_CorpusKey = tuple[str | None, int | None, int | None]


class _ChatWorker(QObject):
    """Worker QObject : streame une réponse et émet des signaux Qt."""

    delta = Signal(str)
    completed = Signal(object)  # ChatMessage
    failed = Signal(str)

    def __init__(
        self,
        *,
        service: ChatService,
        retriever_provider: Callable[[], PassageRetriever],
        question: str,
        glossary_text: str,
        history: tuple[ChatMessage, ...],
        settings: ChatSettings,
        language: Language,
    ) -> None:
        """Construit le worker.

        Args:
            service: Moteur de chat.
            retriever_provider: Fabrique du retriever, **appelée dans le thread
                worker** (l'indexation sémantique peut faire des appels réseau).
            question: Question de l'utilisateur.
            glossary_text: Glossaire pertinent formaté (vide si aucun).
            history: Historique (hors question courante).
            settings: Réglages du chat.
            language: Langue de réponse.
        """
        super().__init__()
        self._service = service
        self._retriever_provider = retriever_provider
        self._question = question
        self._glossary_text = glossary_text
        self._history = history
        self._settings = settings
        self._language = language

    def run(self) -> None:
        """Itère le flux et émet les signaux (delta, completed, failed)."""
        try:
            retriever = self._retriever_provider()
            for chunk in self._service.stream_answer(
                question=self._question,
                retriever=retriever,
                glossary_text=self._glossary_text,
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
        self._glossary_text: str = ""
        # Clé de fraîcheur du corpus chargé (langue de contenu, mtime du consolidé,
        # mtime du glossaire) : permet de re-dériver le corpus quand le document est
        # régénéré, sans recharger tout le projet (cf. refresh_corpus_if_stale).
        self._corpus_key: _CorpusKey = (None, None, None)
        self._conversation: Conversation | None = None
        self._store: ChatConversationStore | None = None
        self._thread: QThread | None = None
        self._worker: _ChatWorker | None = None
        # Contexte figé de la réponse en cours : permet de persister la réponse sur
        # le BON projet/conversation même si l'utilisateur change de projet pendant
        # le streaming (cf. _on_completed). Aligné sur le découplage
        # affiché ↔ worker du GenerationController.
        self._answering_conversation: Conversation | None = None
        self._answering_store: ChatConversationStore | None = None
        self._answering_project_id: ProjectId | None = None

        view.question_submitted.connect(self.submit_question)
        view.new_conversation_requested.connect(self.new_conversation)
        view.conversation_selected.connect(self.select_conversation)
        view.conversation_delete_requested.connect(self.delete_conversation)
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
        self._load_corpus(project)
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

    def refresh_corpus_if_stale(self) -> None:
        """Recharge le corpus si le consolidé/glossaire a changé sur disque.

        Le corpus est chargé une fois à la sélection du projet ; une régénération
        (consolidé ou glossaire) le rendrait périmé. On compare l'empreinte de
        fraîcheur courante à celle chargée et on re-dérive le corpus au besoin —
        **sans** réinitialiser la conversation affichée. Appelé avant chaque
        réponse (``submit_question``) et au signal de fin de génération.

        Ignoré pendant le streaming d'une réponse (``self._thread``) : la
        prochaine soumission rafraîchira de toute façon.
        """
        if self._project is None or self._thread is not None:
            return
        if self._compute_corpus_key(self._project) != self._corpus_key:
            self._load_corpus(self._project)
            self._apply_state()

    def _load_corpus(self, project: Project) -> None:
        """(Re)dérive le corpus (chunks + glossaire + langue) et l'empreinte.

        Args:
            project: Projet dont on charge le corpus.
        """
        generation_output_dir = self._generation_output_dir(project)
        generation_dir = self._generation_dir(project)
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
                generation_dir=generation_dir,
                language=self._content_language,
            )
            self._glossary_text = format_glossary_terms(
                load_glossary_master_terms(generation_dir)
            )
        else:
            self._chunks = ()
            self._glossary_text = ""
        self._corpus_key = self._compute_corpus_key(project)

    def _compute_corpus_key(self, project: Project) -> _CorpusKey:
        """Empreinte de fraîcheur courante du corpus (lue sur disque).

        Args:
            project: Projet concerné.

        Returns:
            ``(langue de contenu, mtime du consolidé, mtime du glossaire)``.
        """
        generation_output_dir = self._generation_output_dir(project)
        source_language = (
            project.generation.source_language
            if project.generation is not None
            else Language.FR
        )
        content_language = resolve_content_language(
            generation_output_dir, source_language, source_language
        )
        consolidated_mtime = (
            source_mtime_ns(generation_output_dir, content_language)
            if content_language is not None
            else None
        )
        glossary_mtime = glossary_master_mtime_ns(self._generation_dir(project))
        language_key = str(content_language) if content_language is not None else None
        return (language_key, consolidated_mtime, glossary_mtime)

    @property
    def current_project_id(self) -> ProjectId | None:
        """Identifiant du projet affiché, ou ``None``."""
        return self._project.id if self._project is not None else None

    def clear_current_project(self) -> None:
        """Réinitialise le contrôleur (projet supprimé)."""
        self._project = None
        self._chunks = ()
        self._glossary_text = ""
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
        # Hors streaming : s'assurer que le corpus reflète le document courant
        # (une régénération a pu le périmer depuis le chargement du projet).
        if self._thread is None:
            self.refresh_corpus_if_stale()
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
        # Construction différée au thread worker : l'indexation sémantique peut
        # appeler le réseau (embeddings) — ne pas geler l'UI ni laisser fuir l'erreur.
        retriever_provider = partial(self._build_retriever, self._chunks, settings, llm)

        history = self._conversation.messages
        self._conversation = self._vm.append_user(self._conversation, text)
        # Fige le contexte de réponse (projet/conversation/store) au moment de la
        # soumission : la finalisation persistera sur ce contexte, pas sur le projet
        # éventuellement re-sélectionné entre-temps.
        self._answering_conversation = self._conversation
        self._answering_store = self._store
        self._answering_project_id = self._project.id
        self._view.add_user_message(text)
        self._view.start_assistant_bubble()
        self._apply_state(answering=True)

        worker = _ChatWorker(
            service=service,
            retriever_provider=retriever_provider,
            question=text,
            glossary_text=self._glossary_text,
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

    def delete_conversation(self, conversation_id: str) -> None:
        """Supprime une conversation après confirmation (ignorée si une réponse coule).

        Si la conversation supprimée est celle affichée, repart sur une nouvelle
        conversation vide ; la liste latérale est toujours rafraîchie.

        Args:
            conversation_id: Identifiant de la conversation à supprimer.
        """
        if self._store is None or self._thread is not None:
            return
        confirm = QMessageBox.question(
            self._window, _DELETE_CONFIRM_TITLE, _DELETE_CONFIRM_MESSAGE
        )
        if confirm is not QMessageBox.StandardButton.Yes:
            return
        self._store.delete(ConversationId(value=conversation_id))
        is_current = (
            self._conversation is not None
            and self._conversation.conversation_id.value == conversation_id
        )
        if is_current:
            self.new_conversation()
        self._refresh_conversations()

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
        """Slot : réponse finalisée (persiste sur le projet répondu + affiche)."""
        chat_message = cast("ChatMessage", message)
        conversation = self._answering_conversation
        store = self._answering_store
        if conversation is not None and store is not None:
            conversation = self._vm.append_assistant(conversation, chat_message)
            store.save(conversation)  # persiste TOUJOURS sur le projet répondu
            # N'actualise l'affichage que si le projet répondu est encore affiché
            # (l'utilisateur peut avoir changé de projet pendant le streaming).
            if (
                self._project is not None
                and self._project.id == self._answering_project_id
            ):
                self._conversation = conversation
                self._view.finalize_message(chat_message)
                self._view.set_total_cost(conversation.total_cost_usd())
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
        """Slot : clic sur une citation → aperçu du passage (Markdown rendu)."""
        for chunk in self._chunks:
            if chunk.anchor == anchor:
                show_passage_dialog(
                    self._window,
                    title=f"{chunk.chapter_title} › {chunk.section_title}",
                    markdown_text=chunk.text,
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
        embedding_provider, embedding_model = self._embedding_provider(settings)
        generation_output_dir = self._generation_output_dir(self._project)
        return build_passage_retriever(
            chunks=chunks,
            settings=settings,
            prompts=self._prompts,
            llm=llm,
            embedding_provider=embedding_provider,
            embedding_model=embedding_model,
            index_path=self._index_path(self._project, self._content_language),
            glossary_mtime_ns=glossary_master_mtime_ns(
                self._generation_dir(self._project)
            ),
            source_mtime_ns=source_mtime_ns(
                generation_output_dir, self._content_language
            ),
            language=self._content_language,
            artifacts=FsArtifactStore(),
        )

    def _embedding_provider(
        self, settings: ChatSettings
    ) -> tuple[EmbeddingProvider | None, str]:
        """Fournit un ``EmbeddingProvider`` OpenAI si une clé est disponible.

        Args:
            settings: Réglages du chat (modèle d'embedding choisi).

        Returns:
            ``(provider, model)`` ; ``(None, "")`` sans clé OpenAI (repli lexical).
        """
        if not self._secrets_service.has_openai_key():
            return None, ""
        openai_key = self._secrets_service.get_openai_api_key()
        assert openai_key is not None  # garanti par has_openai_key
        provider = OpenAIEmbeddingProvider(
            api_key=openai_key, model=str(settings.embedding_model)
        )
        return provider, provider.model

    @staticmethod
    def _index_path(project: Project, language: Language) -> Path:
        return (
            project.workspace_folder
            / CHAT_WORKSPACE_SUBDIR
            / _INDEX_FILENAME_TEMPLATE.format(language=language.value)
        )

    def _cleanup_thread(self) -> None:
        """Réinitialise les références au worker/thread + le contexte de réponse."""
        self._worker = None
        self._thread = None
        self._answering_conversation = None
        self._answering_store = None
        self._answering_project_id = None

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
