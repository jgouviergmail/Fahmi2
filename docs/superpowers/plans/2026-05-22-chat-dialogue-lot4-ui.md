# Chat « Dialogue » — Lot 4 : UI (onglet conversationnel + streaming)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans
> (exécution **inline**).

**Goal :** Onglet **Dialogue** de bout en bout (lexical + streaming) : `ChatTab`,
`ChatController` (worker `QThread` qui streame), `ChatViewModel` (machine d'état,
**sans Qt**, testable), `ChatView` (fil de bulles + saisie + citations + coût),
`ChatSettingsView`, DI dans `app_main`/`MainWindow`.

**Architecture :** Calqué sur `PedagogyTab`/`PedagogyController`. Le worker itère
`ChatService.stream_answer` et émet des **signaux Qt** (`delta`, `completed`,
`failed`) — pas d'EventBus dédié (plus simple que la pédagogie). Le `ChatController`
distingue projet affiché / projet actif (comme `PedagogyController`), persiste les
conversations (`ChatConversationStore`), construit le retriever (lexical +
`QueryExpander`) à partir du corpus sur disque (`load_corpus_chunks`).

**Tech Stack :** PySide6, pytest-qt (smoke), Lots 1-3.

**Interpréteur :** `.venv\Scripts\python.exe`. **Commits :** footer Co-Authored-By.

**Référence spec :** §10 (états, fidélité UX, coût), §11 (UI). Le retrieval reste
**lexical** (sémantique = Lot 5) ; états sémantiques (`INDEX_MISSING`/`INDEXING`/
`STALE`) **différés au Lot 5** (YAGNI).

---

## Task 1 : `FeatureId.CHAT` + `ChatTabState` + `ChatViewModel` (sans Qt)

**Files:** `src/fahmi2/ui/features/feature.py`, `src/fahmi2/domain/enums.py`,
`src/fahmi2/ui/viewmodels/chat_view_model.py`,
`tests/unit/ui/viewmodels/test_chat_view_model.py`

### Décisions
- `FeatureId.CHAT = "chat"`.
- `ChatTabState(StrEnum)` (domaine UI, dans `enums.py`) — états atteignables au
  Lot 4 : `NO_PROJECT`, `NO_CORPUS`, `READY`, `ANSWERING`, `ERROR`.
- `ChatViewModel` (sans Qt) :
  - `resolve_state(*, has_project, has_corpus, is_answering, has_error) -> ChatTabState`
  - `start_conversation(language) -> Conversation` (titre provisoire vide)
  - `derive_title(question) -> str` (tronqué à `_TITLE_MAX_CHARS`)
  - `append_user(conversation, question) -> Conversation` (titre auto si 1ʳᵉ)
  - `append_assistant(conversation, message) -> Conversation`

- [ ] **Step 1 : Test** — `tests/unit/ui/viewmodels/test_chat_view_model.py`

```python
"""Tests du ChatViewModel (logique sans Qt)."""

from __future__ import annotations

from fahmi2.domain.chat import ChatMessage
from fahmi2.domain.enums import ChatTabState, Language
from fahmi2.ui.viewmodels.chat_view_model import ChatViewModel


def test_resolve_state_transitions() -> None:
    vm = ChatViewModel()
    assert vm.resolve_state(has_project=False, has_corpus=False, is_answering=False, has_error=False) is ChatTabState.NO_PROJECT
    assert vm.resolve_state(has_project=True, has_corpus=False, is_answering=False, has_error=False) is ChatTabState.NO_CORPUS
    assert vm.resolve_state(has_project=True, has_corpus=True, is_answering=False, has_error=False) is ChatTabState.READY
    assert vm.resolve_state(has_project=True, has_corpus=True, is_answering=True, has_error=False) is ChatTabState.ANSWERING
    assert vm.resolve_state(has_project=True, has_corpus=True, is_answering=False, has_error=True) is ChatTabState.ERROR


def test_first_user_message_sets_title() -> None:
    vm = ChatViewModel()
    conv = vm.start_conversation(Language.FR)
    conv = vm.append_user(conv, "Qu'est-ce que le PIB exactement ?")
    assert conv.title.startswith("Qu'est-ce que le PIB")
    assert conv.messages[-1].role == "user"


def test_append_assistant_keeps_title() -> None:
    vm = ChatViewModel()
    conv = vm.start_conversation(Language.FR)
    conv = vm.append_user(conv, "Question ?")
    conv = vm.append_assistant(conv, ChatMessage(role="assistant", content="Réponse."))
    assert conv.title == "Question ?"
    assert len(conv.messages) == 2
```

- [ ] **Step 2-4 :** échec → implémenter → succès.

`enums.py` :
```python
class ChatTabState(StrEnum):
    """États de l'onglet Dialogue (machine UX, cf. spec §10.1)."""
    NO_PROJECT = "no_project"
    NO_CORPUS = "no_corpus"
    READY = "ready"
    ANSWERING = "answering"
    ERROR = "error"
```

`feature.py` : `CHAT = "chat"` dans `FeatureId`.

`chat_view_model.py` :
```python
"""ViewModel du chat de dialogue (logique d'état, sans Qt — testable)."""

from __future__ import annotations

from fahmi2.domain.chat import ChatMessage, Conversation
from fahmi2.domain.enums import ChatTabState, Language
from fahmi2.domain.ids import ConversationId

_TITLE_MAX_CHARS = 60
_UNTITLED = "Nouvelle conversation"


class ChatViewModel:
    """Logique d'état de l'onglet Dialogue (indépendante de Qt)."""

    def resolve_state(
        self, *, has_project: bool, has_corpus: bool, is_answering: bool, has_error: bool
    ) -> ChatTabState:
        """Détermine l'état courant de l'onglet."""
        if not has_project:
            return ChatTabState.NO_PROJECT
        if not has_corpus:
            return ChatTabState.NO_CORPUS
        if has_error:
            return ChatTabState.ERROR
        if is_answering:
            return ChatTabState.ANSWERING
        return ChatTabState.READY

    def start_conversation(self, language: Language) -> Conversation:
        """Crée une conversation vide."""
        return Conversation(
            conversation_id=ConversationId.new(), title=_UNTITLED, language=language
        )

    def derive_title(self, question: str) -> str:
        """Titre dérivé d'une question (tronqué)."""
        cleaned = question.strip().replace("\n", " ")
        if len(cleaned) <= _TITLE_MAX_CHARS:
            return cleaned or _UNTITLED
        return f"{cleaned[:_TITLE_MAX_CHARS].rstrip()}…"

    def append_user(self, conversation: Conversation, question: str) -> Conversation:
        """Ajoute la question ; fixe le titre si c'est le premier message."""
        updated = conversation.with_message(
            ChatMessage(role="user", content=question)
        )
        if not conversation.messages:
            from dataclasses import replace  # noqa: PLC0415

            return replace(updated, title=self.derive_title(question))
        return updated

    def append_assistant(
        self, conversation: Conversation, message: ChatMessage
    ) -> Conversation:
        """Ajoute la réponse assistant."""
        return conversation.with_message(message)
```
> Remarque : préférer importer `replace` en tête de module plutôt qu'en local
> (corriger à l'implémentation : `from dataclasses import replace`).

- [ ] **Step 5 : Commit** — `feat(chat): FeatureId.CHAT + ChatTabState + ChatViewModel`

---

## Task 2 : `ChatView` (widget conversationnel)

**Files:** `src/fahmi2/ui/widgets/chat_view.py`,
`tests/unit/ui/widgets/test_chat_view_smoke.py`

`ChatView(QWidget)` — composants :
- liste latérale des conversations (`QListWidget`) + bouton « Nouvelle conversation » ;
- fil de messages (`QTextBrowser` ou `QScrollArea` de bulles) ;
- zone de saisie (`QLineEdit`/`QPlainTextEdit`) + bouton « Envoyer » ;
- libellé de coût cumulé.

Signaux exposés : `question_submitted = Signal(str)`, `new_conversation_requested
= Signal()`, `conversation_selected = Signal(str)`.

Méthodes pilotées par le contrôleur :
- `start_assistant_bubble()` ; `append_delta(text: str)` ; `finalize_message(message:
  ChatMessage)` (rend citations cliquables + coût) ; `add_user_message(text)` ;
  `set_conversations(items)` ; `set_state(state: ChatTabState)` (active/désactive
  la saisie, affiche bandeau `NO_CORPUS`) ; `set_total_cost(usd: float)`.

Citations cliquables : rendre `[§N]` en liens ; au clic, signal `citation_clicked
= Signal(str)` (anchor) — le contrôleur affiche l'extrait (`QMessageBox` ou panneau).

- [ ] **Tests smoke** (pytest-qt) : instanciation, `append_delta` accumule,
  `question_submitted` émis à l'envoi, `set_state(NO_CORPUS)` désactive la saisie.
- [ ] **Commit** — `feat(chat): ChatView (fil de bulles + saisie + citations + coût)`

---

## Task 3 : `ChatSettingsView` (réglages master-detail)

**Files:** `src/fahmi2/ui/dialogs/chat_settings_view.py`,
`tests/unit/ui/dialogs/test_chat_settings_view_smoke.py`

`QDialog` réutilisant le composant `SettingsView` master-detail (comme
`PedagogySettingsView`). Catégories : **Fidélité** (mode strict/augmenté),
**Retrieval** (stratégie AUTO/lexical/sémantique + query expansion on/off + top-K),
**Modèle & coût** (modèle, thinking, reasoning_effort, température).
`get_chat_settings() -> ChatSettings | None`. `initial: ChatSettings | None`.

- [ ] **Tests smoke** : ouverture, valeurs par défaut, `get_chat_settings` round-trip.
- [ ] **Commit** — `feat(chat): ChatSettingsView (réglages master-detail)`

---

## Task 4 : `ChatController` + worker streaming

**Files:** `src/fahmi2/ui/chat_controller.py`,
`tests/unit/ui/test_chat_controller_smoke.py`

`_ChatWorker(QObject)` : signaux `delta = Signal(str)`, `completed = Signal(object)`
(`ChatMessage`), `failed = Signal(str)`. `run()` itère
`chat_service.stream_answer(...)` : `delta.emit(chunk.content_delta)` puis sur le
chunk final `completed.emit(chunk.message)` ; `except Exception → failed.emit(...)`.

`ChatController(QObject)` (calqué sur `PedagogyController`) :
- `on_project_selected(project_id)` : charge le projet, résout la **langue de
  contenu** (`resolve_content_language`), charge le corpus (`load_corpus_chunks`),
  construit le retriever (`TfidfPassageRetriever` + `QueryExpander` si
  `query_expansion_enabled`), charge les conversations (`ChatConversationStore`),
  applique l'état via `ChatViewModel.resolve_state`.
- `submit_question(text)` : refuse si pas de corpus / déjà en cours ; `append_user`
  (VM) ; démarre `_ChatWorker` dans un `QThread` ; `view.start_assistant_bubble()`.
- slots worker : `delta → view.append_delta` ; `completed → append_assistant (VM) +
  view.finalize_message + persiste la conversation + recalcule l'état + coût` ;
  `failed → LogsDock + QMessageBox + état READY`.
- `new_conversation()` / `select_conversation(id)`.
- Réglages : `open_chat_settings()` → `ChatSettingsView` → `project.with_chat(...)`.
- Construit le `ChatService` avec `DeepSeekAdapter(api_key)` + `PromptLoader`.

> Sans clé DeepSeek → message clair (comme la pédagogie). Glossaire : passer un
> `glossary_text` vide au Lot 4 (formatage du glossaire = amélioration ; le corpus
> contient déjà les chunks de glossaire). *(Décision : suffisant pour la v1.)*

- [ ] **Tests smoke** : sélection projet sans corpus → état `NO_CORPUS` ; avec
  corpus fixture + `FakeLLMProvider` injecté → `submit_question` produit une bulle
  finalisée (utiliser un service injectable pour ne pas dépendre de DeepSeek).
- [ ] **Commit** — `feat(chat): ChatController (worker streaming + persistance)`

> **Injection testable** : le `ChatController.__init__` accepte un
> `chat_service_factory` (défaut = fabrique DeepSeek) pour permettre l'injection
> d'un `FakeLLMProvider` en test. *(À cadrer à l'implémentation.)*

## Task 5 : `ChatTab` + intégration `MainWindow`/`app_main`

**Files:** `src/fahmi2/ui/features/chat_tab.py`, `src/fahmi2/ui/app_main.py`,
`tests/unit/ui/features/test_tabs_smoke.py` (ajout)

`ChatTab(FeatureTab)` calqué sur `PedagogyTab` : construit `ChatView` + son
`ChatController`, expose `feature_id = FeatureId.CHAT`, `title = "Dialogue"`,
`widget`, `controller`, délègue `on_project_selected`/`on_project_deleted`.

`app_main` : instancier `ChatTab`, l'ajouter au `FeatureRegistry`
(`[generation_tab, pedagogy_tab, chat_tab]`), garder une référence
(`window._chat_tab`), connecter `run_state_changed` si exposé (sinon non).

- [ ] **Tests smoke** : `test_main_window_shows_three_feature_tabs`.
- [ ] **Commit** — `feat(chat): ChatTab + intégration MainWindow/app_main`

---

## Clôture du Lot 4 — vérifications + revue
- [ ] `pytest`, `ruff check .`, `mypy src tests` **verts**.
- [ ] **Revue approfondie** (9 points) : logique testable concentrée dans le
  ViewModel (sans Qt) ; pas de magic value ; cohérence avec `PedagogyController` ;
  threads nettoyés (`deleteLater`) ; saisie désactivée hors `READY`.
- [ ] **Index** : Lot 4 → ✅, puis plan du **Lot 5**.
