# Chat « Dialogue » — Lot 2 : Moteur (non-streaming) + prompts + fidélité + persistance

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans
> (exécution **inline**). Steps en cases à cocher (`- [ ]`).

**Goal :** Produire une réponse **ancrée et citée** à partir d'une question et du
corpus (retrieval lexical du Lot 1), sans UI ni streaming : moteur `ChatService`,
prompts de fidélité (strict/augmenté), query expansion, persistance des
conversations et des `ChatSettings`.

**Architecture :** Moteur `chat/` (calqué sur `pedagogy/`) ; réutilise
`invoke_llm_chat` + `PromptLoader` ; persistance fichiers via `FsArtifactStore` ;
`ChatSettings` ajouté au blob v2 (clé `chat`, lecture lenient).

**Tech Stack :** Python 3.12, Jinja2, scikit-learn (Lot 1), DeepSeek (LLM).

**Interpréteur :** `.venv\Scripts\python.exe`.
**Commits :** chaque message se termine par
`Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>`.
**Imports de test :** fusionner en tête de fichier (pas de doublon).

**Référence spec :** §5, §6.0 (raisonnement), §7 (prompts), §8 (persistance),
§4.5 (query expansion), §10.3 (garde-fou historique).

**Limite assumée du Lot 2 :** appel LLM **sans retry** (le retry + events arrivent
au **Lot 3** avec le streaming, cf. spec §6) ; pas de streaming.

---

## Fichiers du lot

- Créer : `src/fahmi2/core/text_metrics.py` (estimation de tokens centralisée)
- Modifier : `src/fahmi2/chat/corpus.py` (utiliser `text_metrics`)
- Modifier : `src/fahmi2/domain/chat.py` (`ChatSettings.to_phase_config`)
- Créer : `src/fahmi2/infra/prompts/defaults/chat_strict.j2`,
  `chat_augmented.j2`, `chat_query_expansion.j2`
- Modifier : `src/fahmi2/app/prompts_service.py` (catalogue + 3 entrées)
- Créer : `src/fahmi2/chat/prompt_builder.py`, `src/fahmi2/chat/citations.py`,
  `src/fahmi2/chat/chat_service.py`, `src/fahmi2/chat/query_expander.py`
- Créer : `src/fahmi2/app/chat_conversation_store.py`
- Modifier : `src/fahmi2/domain/project.py` (`chat` + `with_chat`),
  `src/fahmi2/app/project_service.py` (param `chat`),
  `src/fahmi2/infra/storage/sqlite_state.py` (sérialisation `chat`)
- Tests : `tests/unit/core/test_text_metrics.py`,
  `tests/unit/chat/test_prompt_builder.py`, `tests/unit/chat/test_citations.py`,
  `tests/unit/chat/test_chat_service.py`, `tests/unit/chat/test_query_expander.py`,
  `tests/unit/app/test_chat_conversation_store.py`,
  `tests/unit/infra/storage/test_project_blob_chat.py` (+ ajouts à `test_chat.py`)

---

## Task 1 : Estimation de tokens centralisée (`core/text_metrics.py`)

DRY : `corpus.py` a son propre `_CHARS_PER_TOKEN` ; on centralise pour le réutiliser
dans le moteur (garde-fou historique).

- [ ] **Step 1 : Test** — `tests/unit/core/test_text_metrics.py`

```python
"""Tests de l'estimation de tokens."""

from __future__ import annotations

from fahmi2.core.text_metrics import CHARS_PER_TOKEN, estimate_tokens


def test_estimate_tokens_proportional() -> None:
    assert estimate_tokens("a" * (CHARS_PER_TOKEN * 10)) == 10


def test_estimate_tokens_minimum_one() -> None:
    assert estimate_tokens("") == 1
    assert estimate_tokens("x") == 1
```

- [ ] **Step 2 : Échec** — `.venv\Scripts\python.exe -m pytest tests/unit/core/test_text_metrics.py -q` → FAIL (module absent).

- [ ] **Step 3 : Implémenter** — `src/fahmi2/core/text_metrics.py`

```python
"""Estimation grossière du nombre de tokens (heuristique caractères).

Source unique partagée (chunking du corpus, garde-fou d'historique du chat, …).
Approximation volontairement simple : ~4 caractères par token.
"""

from __future__ import annotations

CHARS_PER_TOKEN = 4


def estimate_tokens(text: str) -> int:
    """Estime le nombre de tokens d'un texte.

    Args:
        text: Texte à mesurer.

    Returns:
        Nombre de tokens estimé (au moins 1).
    """
    return max(1, len(text) // CHARS_PER_TOKEN)
```

- [ ] **Step 4 : Refactor `corpus.py`** — remplacer la constante/fonction locales :
  - Supprimer `_CHARS_PER_TOKEN` et le corps de `_estimate_tokens`.
  - Importer : `from fahmi2.core.text_metrics import estimate_tokens`.
  - Remplacer les appels `_estimate_tokens(...)` par `estimate_tokens(...)`.

- [ ] **Step 5 : Vérifier** — `.venv\Scripts\python.exe -m pytest tests/unit/core/test_text_metrics.py tests/unit/chat/test_corpus.py -q` → PASS.

- [ ] **Step 6 : Commit**

```bash
git add src/fahmi2/core/text_metrics.py src/fahmi2/chat/corpus.py tests/unit/core/test_text_metrics.py
git commit -m "feat(chat): estimation de tokens centralisée (core/text_metrics)"
```

---

## Task 2 : `ChatSettings.to_phase_config()`

- [ ] **Step 1 : Test** — ajouter à `tests/unit/domain/test_chat.py`

```python
from fahmi2.domain.enums import ReasoningEffort
from fahmi2.domain.phase import PhaseConfig


def test_chat_settings_to_phase_config() -> None:
    settings = ChatSettings(
        thinking_enabled=True, reasoning_effort=ReasoningEffort.HIGH, temperature=0.5
    )
    config = settings.to_phase_config()
    assert isinstance(config, PhaseConfig)
    assert config.thinking_enabled is True
    assert config.reasoning_effort is ReasoningEffort.HIGH
    assert config.temperature == 0.5
```

- [ ] **Step 2 : Échec** → `pytest tests/unit/domain/test_chat.py -q`.

- [ ] **Step 3 : Implémenter** dans `src/fahmi2/domain/chat.py` :
  - Importer `from fahmi2.domain.phase import PhaseConfig`.
  - Ajouter la méthode à `ChatSettings` :

```python
    def to_phase_config(self) -> PhaseConfig:
        """Construit la PhaseConfig LLM correspondante (pour invoke_llm_chat).

        Returns:
            La ``PhaseConfig`` (thinking / reasoning_effort / température).
        """
        return PhaseConfig(
            thinking_enabled=self.thinking_enabled,
            reasoning_effort=self.reasoning_effort,
            temperature=self.temperature,
        )
```

- [ ] **Step 4 : Vérifier** → PASS.
- [ ] **Step 5 : Commit** — `git commit -m "feat(chat): ChatSettings.to_phase_config"`

---

## Task 3 : Prompts de fidélité + query expansion + catalogue

- [ ] **Step 1 : Créer les 3 templates** dans `src/fahmi2/infra/prompts/defaults/`

`chat_strict.j2` :
```jinja
Tu es un assistant de révision. Tu réponds STRICTEMENT à partir des extraits de cours fournis ci-dessous.

Règles :
- Utilise uniquement les informations présentes dans les extraits.
- Cite chaque affirmation avec le format [§N] (N = numéro de l'extrait).
- Si l'information n'est pas dans les extraits, réponds exactement :
  « Ce point n'est pas couvert par le cours. »
- Rédige ta réponse en {{ output_language_label }}.
{% if glossary_terms %}
Glossaire de référence (orthographe et sens) :
{{ glossary_terms }}
{% endif %}
Extraits du cours :
{{ passages }}
```

`chat_augmented.j2` :
```jinja
Tu es un assistant de révision. Tu t'appuies EN PRIORITÉ sur les extraits de cours fournis ci-dessous.

Règles :
- Privilégie les informations des extraits et cite-les avec le format [§N].
- Tu peux compléter avec tes connaissances générales UNIQUEMENT dans une section
  finale intitulée « Au-delà du cours », clairement séparée du reste.
- Rédige ta réponse en {{ output_language_label }}.
{% if glossary_terms %}
Glossaire de référence (orthographe et sens) :
{{ glossary_terms }}
{% endif %}
Extraits du cours :
{{ passages }}
```

`chat_query_expansion.j2` :
```jinja
Reformule la question suivante en une liste de mots-clés et de synonymes
(séparés par des espaces, sans phrase) pour améliorer une recherche lexicale
dans un cours. Réponds uniquement par les mots-clés.

Question : {{ question }}
```

- [ ] **Step 2 : Catalogue** — ajouter 3 `PromptTemplateMeta` à la fin de
  `_TEMPLATE_METADATA` dans `app/prompts_service.py` :

```python
    PromptTemplateMeta(
        name="chat_strict",
        display_name="Dialogue — Réponse ancrée (strict)",
        description=(
            "Chat : répond uniquement à partir du corpus, avec citations [§N]."
        ),
    ),
    PromptTemplateMeta(
        name="chat_augmented",
        display_name="Dialogue — Réponse augmentée",
        description=(
            "Chat : corpus prioritaire + complément balisé « Au-delà du cours »."
        ),
    ),
    PromptTemplateMeta(
        name="chat_query_expansion",
        display_name="Dialogue — Expansion de requête",
        description=(
            "Chat : reformule une question en mots-clés pour le retrieval lexical."
        ),
    ),
```

- [ ] **Step 3 : Test** — `tests/unit/app/test_prompts_service.py` (ajouter, ou créer si absent)

```python
def test_chat_templates_present_and_loadable(tmp_path: Path) -> None:
    service = PromptsService(override_dir=tmp_path)
    names = {meta.name for meta in service.list_templates()}
    assert {"chat_strict", "chat_augmented", "chat_query_expansion"} <= names
    # les défauts bundlés sont chargeables
    assert "Extraits du cours" in service.load_default("chat_strict")
    assert "Au-delà du cours" in service.load_default("chat_augmented")
```

(En tête : `from pathlib import Path` ; `from fahmi2.app.prompts_service import PromptsService`.)

- [ ] **Step 4 : Vérifier** → PASS.
- [ ] **Step 5 : Commit** — `git commit -m "feat(chat): prompts strict/augmenté/expansion + catalogue"`

---

## Task 4 : `chat/prompt_builder.py` (passages, garde-fou historique, messages)

- [ ] **Step 1 : Test** — `tests/unit/chat/test_prompt_builder.py`

```python
"""Tests de l'assemblage des messages du chat."""

from __future__ import annotations

from fahmi2.chat.prompt_builder import (
    build_chat_messages,
    format_passages,
    truncate_history,
)
from fahmi2.domain.chat import ChatMessage, ChatSettings, CorpusChunk, RetrievedPassage
from fahmi2.domain.enums import ChatGroundingMode, Language
from fahmi2.infra.prompts.loader import PromptLoader


def _passage(idx: int, text: str) -> RetrievedPassage:
    chunk = CorpusChunk(
        chunk_id=f"c::{idx}",
        chapter_title=f"Chap {idx}",
        section_title=f"Sec {idx}",
        anchor=f"a{idx}",
        text=text,
        origin="consolidated",
    )
    return RetrievedPassage(chunk=chunk, score=1.0)


def test_format_passages_numbered() -> None:
    text = format_passages((_passage(1, "alpha"), _passage(2, "beta")))
    assert "§1" in text and "§2" in text
    assert "alpha" in text and "beta" in text


def test_truncate_history_keeps_recent() -> None:
    history = tuple(
        ChatMessage(role="user", content="x" * 400) for _ in range(10)
    )
    kept = truncate_history(history, max_tokens=50)
    assert len(kept) < len(history)
    assert kept[-1] is history[-1]  # les plus récents sont conservés


def test_build_chat_messages_strict_has_system_and_question() -> None:
    loader = PromptLoader()
    messages = build_chat_messages(
        question="Qu'est-ce que le PIB ?",
        passages=(_passage(1, "Le PIB mesure la richesse."),),
        glossary_text="",
        history=(),
        settings=ChatSettings(grounding_mode=ChatGroundingMode.STRICT),
        language=Language.FR,
        prompt_loader=loader,
    )
    assert messages[0].role == "system"
    assert "Extraits du cours" in messages[0].content
    assert messages[-1].role == "user"
    assert messages[-1].content == "Qu'est-ce que le PIB ?"
```

- [ ] **Step 2 : Échec** → pytest.

- [ ] **Step 3 : Implémenter** — `src/fahmi2/chat/prompt_builder.py`

```python
"""Assemblage des messages LLM du chat (système + historique + question).

Le prompt système (strict ou augmenté) embarque les passages numérotés du corpus
et le glossaire pertinent. Un garde-fou élague l'historique le plus ancien si le
budget de contexte est dépassé (fenêtre glissante, cf. spec §10.3).
"""

from __future__ import annotations

from fahmi2.core.text_metrics import estimate_tokens
from fahmi2.domain.chat import ChatMessage, ChatSettings, RetrievedPassage
from fahmi2.domain.enums import ChatGroundingMode, Language
from fahmi2.infra.llm.interface import Message
from fahmi2.infra.prompts.loader import PromptLoader
from fahmi2.pedagogy.labels import language_label

_PROMPT_STRICT = "chat_strict"
_PROMPT_AUGMENTED = "chat_augmented"
_MAX_HISTORY_TOKENS = 100_000  # garde-fou : fenêtre glissante au-delà
_PASSAGE_HEADER = "§{n} — {chapter} › {section}"

_PROMPT_BY_MODE = {
    ChatGroundingMode.STRICT: _PROMPT_STRICT,
    ChatGroundingMode.AUGMENTED: _PROMPT_AUGMENTED,
}


def format_passages(passages: tuple[RetrievedPassage, ...]) -> str:
    """Formate les passages récupérés en bloc numéroté (§1, §2, …).

    Args:
        passages: Passages récupérés, dans l'ordre de pertinence.

    Returns:
        Bloc texte numéroté pour injection dans le prompt système.
    """
    blocks: list[str] = []
    for index, passage in enumerate(passages, start=1):
        chunk = passage.chunk
        header = _PASSAGE_HEADER.format(
            n=index, chapter=chunk.chapter_title, section=chunk.section_title
        )
        blocks.append(f"{header}\n{chunk.text}")
    return "\n\n".join(blocks)


def truncate_history(
    history: tuple[ChatMessage, ...], *, max_tokens: int = _MAX_HISTORY_TOKENS
) -> tuple[ChatMessage, ...]:
    """Conserve les tours les plus récents tenant dans ``max_tokens`` (estimé).

    Args:
        history: Historique complet (du plus ancien au plus récent).
        max_tokens: Budget de tokens estimé pour l'historique injecté.

    Returns:
        Sous-suite **suffixe** (tours récents) tenant dans le budget.
    """
    kept: list[ChatMessage] = []
    total = 0
    for message in reversed(history):
        total += estimate_tokens(message.content)
        if total > max_tokens and kept:
            break
        kept.append(message)
    kept.reverse()
    return tuple(kept)


def build_chat_messages(
    *,
    question: str,
    passages: tuple[RetrievedPassage, ...],
    glossary_text: str,
    history: tuple[ChatMessage, ...],
    settings: ChatSettings,
    language: Language,
    prompt_loader: PromptLoader,
) -> list[Message]:
    """Assemble la liste de messages LLM (système + historique + question).

    Args:
        question: Question de l'utilisateur.
        passages: Passages récupérés à citer.
        glossary_text: Glossaire pertinent déjà formaté (vide si aucun).
        history: Historique de la conversation (hors question courante).
        settings: Réglages du chat (mode de fidélité).
        language: Langue de réponse.
        prompt_loader: Loader de templates (override > défaut).

    Returns:
        Liste ordonnée de ``Message`` prête pour ``LLMProvider``.
    """
    system_prompt = prompt_loader.render(
        _PROMPT_BY_MODE[settings.grounding_mode],
        output_language_label=language_label(language),
        glossary_terms=glossary_text,
        passages=format_passages(passages),
    )
    messages: list[Message] = [Message(role="system", content=system_prompt)]
    for message in truncate_history(history):
        messages.append(Message(role=message.role, content=message.content))
    messages.append(Message(role="user", content=question))
    return messages
```

- [ ] **Step 4 : Vérifier** → PASS.
- [ ] **Step 5 : Commit** — `git commit -m "feat(chat): prompt_builder (passages numérotés, garde-fou historique)"`

---

## Task 5 : `chat/citations.py` (parsing [§N])

- [ ] **Step 1 : Test** — `tests/unit/chat/test_citations.py`

```python
"""Tests du parsing des citations [§N]."""

from __future__ import annotations

from fahmi2.chat.citations import parse_citations
from fahmi2.domain.chat import CorpusChunk, RetrievedPassage


def _passage(idx: int) -> RetrievedPassage:
    chunk = CorpusChunk(
        chunk_id=f"c::{idx}",
        chapter_title=f"Chap {idx}",
        section_title=f"Sec {idx}",
        anchor=f"a{idx}",
        text=f"Texte du passage {idx} avec du contenu.",
        origin="consolidated",
    )
    return RetrievedPassage(chunk=chunk, score=1.0)


def test_parse_citations_maps_indices() -> None:
    passages = (_passage(1), _passage(2))
    citations = parse_citations("Le PIB [§1] et l'inflation [§2].", passages)
    assert {c.anchor for c in citations} == {"a1", "a2"}


def test_parse_citations_dedup_and_ignores_out_of_range() -> None:
    passages = (_passage(1),)
    citations = parse_citations("Voir [§1] et encore [§1] et [§9].", passages)
    assert len(citations) == 1
    assert citations[0].anchor == "a1"


def test_parse_citations_none() -> None:
    assert parse_citations("Aucune citation ici.", (_passage(1),)) == ()
```

- [ ] **Step 2 : Échec** → pytest.

- [ ] **Step 3 : Implémenter** — `src/fahmi2/chat/citations.py`

```python
"""Parsing des marqueurs de citation [§N] d'une réponse en ``Citation``.

Le prompt impose des marqueurs ``[§N]`` référant les passages numérotés fournis.
Le parsing est **tolérant** : un index hors bornes est ignoré, les doublons sont
dédupliqués (par ancre), une réponse sans marqueur donne un tuple vide.
"""

from __future__ import annotations

import re

from fahmi2.domain.chat import Citation, RetrievedPassage

_RE_CITATION = re.compile(r"\[§(\d+)\]")
_SNIPPET_MAX_CHARS = 160


def parse_citations(
    answer: str, passages: tuple[RetrievedPassage, ...]
) -> tuple[Citation, ...]:
    """Extrait les citations d'une réponse et les mappe aux passages.

    Args:
        answer: Texte de la réponse du LLM.
        passages: Passages numérotés fournis au prompt (1-based dans la réponse).

    Returns:
        Citations uniques (dédupliquées par ancre), dans l'ordre d'apparition.
    """
    citations: list[Citation] = []
    seen: set[str] = set()
    for match in _RE_CITATION.finditer(answer):
        index = int(match.group(1))
        if not 1 <= index <= len(passages):
            continue
        chunk = passages[index - 1].chunk
        if chunk.anchor in seen:
            continue
        seen.add(chunk.anchor)
        citations.append(
            Citation(
                chapter_title=chunk.chapter_title,
                section_title=chunk.section_title,
                anchor=chunk.anchor,
                snippet=chunk.text[:_SNIPPET_MAX_CHARS],
            )
        )
    return tuple(citations)
```

- [ ] **Step 4 : Vérifier** → PASS.
- [ ] **Step 5 : Commit** — `git commit -m "feat(chat): parsing des citations [§N]"`

---

## Task 6 : `chat/chat_service.py` (réponse non-streaming)

- [ ] **Step 1 : Test** — `tests/unit/chat/test_chat_service.py`

```python
"""Tests du moteur de chat (réponse non-streaming)."""

from __future__ import annotations

from fahmi2.chat.chat_service import ChatService
from fahmi2.core.retrieval.passages import TfidfPassageRetriever
from fahmi2.domain.chat import ChatSettings, CorpusChunk
from fahmi2.domain.enums import Language
from fahmi2.infra.llm._fakes import FakeLLMProvider
from fahmi2.infra.llm.interface import LLMResponse
from fahmi2.infra.prompts.loader import PromptLoader


def _chunk(cid: str, text: str) -> CorpusChunk:
    return CorpusChunk(
        chunk_id=cid,
        chapter_title="Économie",
        section_title="PIB",
        anchor="pib",
        text=text,
        origin="consolidated",
    )


def _service(answer: str) -> ChatService:
    response = LLMResponse(
        content=answer,
        thinking_content=None,
        prompt_tokens=120,
        completion_tokens=30,
        cached_prompt_tokens=0,
        cost_usd=0.01,
    )
    return ChatService(
        llm_provider=FakeLLMProvider(default_response=response),
        prompt_loader=PromptLoader(),
    )


def test_answer_returns_message_with_citation() -> None:
    retriever = TfidfPassageRetriever(
        (_chunk("1", "Le produit intérieur brut mesure la richesse."),)
    )
    service = _service("Le PIB mesure la richesse produite [§1].")
    message = service.answer(
        question="Qu'est-ce que le PIB ?",
        retriever=retriever,
        glossary_text="",
        history=(),
        settings=ChatSettings(),
        language=Language.FR,
    )
    assert message.role == "assistant"
    assert "[§1]" in message.content
    assert message.cost_usd == 0.01
    assert len(message.citations) == 1
    assert message.citations[0].anchor == "pib"


def test_answer_no_passages_when_empty_corpus() -> None:
    service = _service("Ce point n'est pas couvert par le cours.")
    message = service.answer(
        question="Question hors sujet ?",
        retriever=TfidfPassageRetriever(()),
        glossary_text="",
        history=(),
        settings=ChatSettings(),
        language=Language.FR,
    )
    assert message.citations == ()
```

- [ ] **Step 2 : Échec** → pytest.

- [ ] **Step 3 : Implémenter** — `src/fahmi2/chat/chat_service.py`

```python
"""Moteur de chat (réponse non-streaming) : retrieve → prompt → LLM → citations.

Orchestrateur léger : récupère les passages, assemble les messages (fidélité),
appelle le LLM, parse les citations et construit un ``ChatMessage``. Le retry et
le streaming sont ajoutés au Lot 3.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fahmi2.chat.citations import parse_citations
from fahmi2.chat.prompt_builder import build_chat_messages
from fahmi2.core.retrieval.passages import PassageRetriever
from fahmi2.domain.chat import ChatMessage, ChatSettings
from fahmi2.domain.enums import Language
from fahmi2.infra.llm.interface import LLMProvider
from fahmi2.infra.prompts.loader import PromptLoader


class ChatService:
    """Produit une réponse ancrée à partir d'une question et du corpus."""

    def __init__(
        self, *, llm_provider: LLMProvider, prompt_loader: PromptLoader
    ) -> None:
        """Construit le service.

        Args:
            llm_provider: Provider LLM (DeepSeek en production).
            prompt_loader: Loader de prompts (override > défaut).
        """
        self._llm = llm_provider
        self._prompts = prompt_loader

    def answer(
        self,
        *,
        question: str,
        retriever: PassageRetriever,
        glossary_text: str,
        history: tuple[ChatMessage, ...],
        settings: ChatSettings,
        language: Language,
    ) -> ChatMessage:
        """Génère la réponse assistant à une question.

        Args:
            question: Question de l'utilisateur.
            retriever: Retriever de passages (lexical au Lot 2).
            glossary_text: Glossaire pertinent formaté (vide si aucun).
            history: Historique de la conversation (hors question courante).
            settings: Réglages du chat.
            language: Langue de réponse.

        Returns:
            Le ``ChatMessage`` assistant (contenu + citations + coût).
        """
        passages = tuple(
            retriever.retrieve(query=question, top_k=settings.top_k)
        )
        messages = build_chat_messages(
            question=question,
            passages=passages,
            glossary_text=glossary_text,
            history=history,
            settings=settings,
            language=language,
            prompt_loader=self._prompts,
        )
        # Chat multi-tours : on passe la liste complète de Message (système +
        # historique + question) directement au provider (invoke_llm_chat ne gère
        # que système + user, sans historique).
        response = self._llm.chat(
            messages=messages,
            model=str(settings.model),
            thinking=settings.thinking_enabled,
            reasoning_effort=(
                str(settings.reasoning_effort)
                if settings.reasoning_effort is not None
                else None
            ),
            temperature=settings.temperature,
        )
        citations = parse_citations(response.content, passages)
        return ChatMessage(
            role="assistant",
            content=response.content,
            citations=citations,
            cost_usd=response.cost_usd,
            prompt_tokens=response.prompt_tokens,
            completion_tokens=response.completion_tokens,
            created_at=datetime.now(tz=UTC),
        )
```

- [ ] **Step 4 : Vérifier** → PASS.
- [ ] **Step 5 : Commit** — `git commit -m "feat(chat): ChatService (réponse ancrée non-streaming)"`

---

## Task 7 : `chat/query_expander.py` (décorateur)

- [ ] **Step 1 : Test** — `tests/unit/chat/test_query_expander.py`

```python
"""Tests du décorateur de query expansion."""

from __future__ import annotations

from fahmi2.chat.query_expander import QueryExpander
from fahmi2.core.retrieval.passages import TfidfPassageRetriever
from fahmi2.domain.chat import ChatSettings, CorpusChunk
from fahmi2.domain.enums import Language
from fahmi2.infra.llm._fakes import FakeLLMProvider
from fahmi2.infra.llm.interface import LLMResponse
from fahmi2.infra.prompts.loader import PromptLoader


def _chunk(cid: str, text: str) -> CorpusChunk:
    return CorpusChunk(
        chunk_id=cid, chapter_title="C", section_title="S",
        anchor=cid, text=text, origin="consolidated",
    )


def _expander(inner: TfidfPassageRetriever, *, expansion: str) -> QueryExpander:
    llm = FakeLLMProvider(
        default_response=LLMResponse(
            content=expansion, thinking_content=None, prompt_tokens=10,
            completion_tokens=5, cached_prompt_tokens=0, cost_usd=0.0,
        )
    )
    return QueryExpander(
        inner=inner, llm_provider=llm, prompt_loader=PromptLoader(),
        settings=ChatSettings(), language=Language.FR,
    )


def test_strong_match_skips_expansion() -> None:
    inner = TfidfPassageRetriever((_chunk("1", "le pib mesure la richesse"),))
    expander = _expander(inner, expansion="ignored")
    results = expander.retrieve(query="pib richesse", top_k=3)
    assert results[0].chunk.chunk_id == "1"


def test_weak_match_triggers_expansion_and_merges() -> None:
    inner = TfidfPassageRetriever(
        (_chunk("1", "produit intérieur brut richesse nationale"),)
    )
    # Question sans vocabulaire commun → score initial faible → expansion.
    expander = _expander(inner, expansion="produit intérieur brut richesse")
    results = expander.retrieve(query="économie agrégée ?", top_k=3)
    assert any(r.chunk.chunk_id == "1" for r in results)
```

- [ ] **Step 2 : Échec** → pytest.

- [ ] **Step 3 : Implémenter** — `src/fahmi2/chat/query_expander.py`

```python
"""Décorateur de query expansion : améliore un retrieval lexical faible.

Si le meilleur score du retrieval direct est sous un seuil, demande au LLM une
reformulation (mots-clés/synonymes) et relance le retrieval, en fusionnant les
résultats (dédup par chunk_id). Évite tout appel LLM systématique.
"""

from __future__ import annotations

from fahmi2.core.retrieval.passages import PassageRetriever
from fahmi2.domain.chat import ChatSettings, RetrievedPassage
from fahmi2.domain.enums import Language
from fahmi2.infra.llm.interface import LLMProvider, Message
from fahmi2.infra.prompts.loader import PromptLoader

_PROMPT_QUERY_EXPANSION = "chat_query_expansion"
_WEAK_SCORE_THRESHOLD = 0.15


class QueryExpander:
    """Enveloppe un ``PassageRetriever`` d'une expansion LLM à la demande."""

    def __init__(
        self,
        *,
        inner: PassageRetriever,
        llm_provider: LLMProvider,
        prompt_loader: PromptLoader,
        settings: ChatSettings,
        language: Language,
        weak_score_threshold: float = _WEAK_SCORE_THRESHOLD,
    ) -> None:
        """Construit le décorateur.

        Args:
            inner: Retriever sous-jacent (lexical).
            llm_provider: Provider LLM pour la reformulation.
            prompt_loader: Loader de prompts.
            settings: Réglages du chat (modèle, température).
            language: Langue (non utilisée par le prompt d'expansion, réservée).
            weak_score_threshold: Seuil sous lequel on déclenche l'expansion.
        """
        self._inner = inner
        self._llm = llm_provider
        self._prompts = prompt_loader
        self._settings = settings
        self._language = language
        self._threshold = weak_score_threshold

    def retrieve(self, *, query: str, top_k: int) -> list[RetrievedPassage]:
        """Récupère les passages, avec expansion si le retrieval direct est faible.

        Args:
            query: Question.
            top_k: Nombre maximal de passages.

        Returns:
            Passages (fusion directe + expansion si déclenchée).
        """
        direct = self._inner.retrieve(query=query, top_k=top_k)
        if not self._settings.query_expansion_enabled:
            return direct
        if direct and direct[0].score >= self._threshold:
            return direct
        expanded_query = self._expand(query)
        if not expanded_query:
            return direct
        more = self._inner.retrieve(
            query=f"{query} {expanded_query}", top_k=top_k
        )
        return self._merge(direct, more, top_k=top_k)

    def _expand(self, query: str) -> str:
        """Demande au LLM une reformulation en mots-clés.

        Args:
            query: Question d'origine.

        Returns:
            Mots-clés (chaîne), ou vide en cas d'absence.
        """
        prompt = self._prompts.render(_PROMPT_QUERY_EXPANSION, question=query)
        response = self._llm.chat(
            messages=[Message(role="user", content=prompt)],
            model=str(self._settings.model),
            thinking=False,
            temperature=self._settings.temperature,
        )
        return response.content.strip()

    @staticmethod
    def _merge(
        direct: list[RetrievedPassage],
        more: list[RetrievedPassage],
        *,
        top_k: int,
    ) -> list[RetrievedPassage]:
        """Fusionne deux listes de passages (dédup par chunk_id, tri par score).

        Args:
            direct: Résultats du retrieval direct.
            more: Résultats du retrieval enrichi.
            top_k: Borne supérieure.

        Returns:
            Les ``top_k`` meilleurs passages dédupliqués.
        """
        best: dict[str, RetrievedPassage] = {}
        for passage in (*direct, *more):
            current = best.get(passage.chunk.chunk_id)
            if current is None or passage.score > current.score:
                best[passage.chunk.chunk_id] = passage
        ranked = sorted(best.values(), key=lambda p: -p.score)
        return ranked[:top_k]
```

- [ ] **Step 4 : Vérifier** → PASS.
- [ ] **Step 5 : Commit** — `git commit -m "feat(chat): QueryExpander (expansion lexicale à la demande)"`

---

## Task 8 : `app/chat_conversation_store.py` (persistance JSON)

- [ ] **Step 1 : Test** — `tests/unit/app/test_chat_conversation_store.py`

```python
"""Tests de la persistance des conversations du chat."""

from __future__ import annotations

from pathlib import Path

from fahmi2.app.chat_conversation_store import ChatConversationStore
from fahmi2.domain.chat import ChatMessage, Conversation
from fahmi2.domain.enums import Language
from fahmi2.domain.ids import ConversationId
from fahmi2.infra.storage.fs_artifacts import FsArtifactStore


def _store(tmp_path: Path) -> ChatConversationStore:
    return ChatConversationStore(artifacts=FsArtifactStore(), chat_dir=tmp_path)


def _conversation() -> Conversation:
    return Conversation(
        conversation_id=ConversationId.new(),
        title="Le PIB",
        language=Language.FR,
        messages=(
            ChatMessage(role="user", content="Qu'est-ce que le PIB ?"),
            ChatMessage(role="assistant", content="Le PIB [§1].", cost_usd=0.02),
        ),
    )


def test_save_then_load_roundtrip(tmp_path: Path) -> None:
    store = _store(tmp_path)
    conv = _conversation()
    store.save(conv)
    loaded = store.load(conv.conversation_id)
    assert loaded is not None
    assert loaded.title == "Le PIB"
    assert len(loaded.messages) == 2
    assert loaded.messages[1].cost_usd == 0.02


def test_list_and_delete(tmp_path: Path) -> None:
    store = _store(tmp_path)
    conv = _conversation()
    store.save(conv)
    assert [c.conversation_id for c in store.list_all()] == [conv.conversation_id]
    store.delete(conv.conversation_id)
    assert store.list_all() == ()
    assert store.load(conv.conversation_id) is None
```

- [ ] **Step 2 : Échec** → pytest.

- [ ] **Step 3 : Implémenter** — `src/fahmi2/app/chat_conversation_store.py`

```python
"""Persistance des conversations du chat (JSON sous ``<workspace>/chat/``).

Sérialisation domaine ↔ JSON, écriture atomique via ``FsArtifactStore``. Une
conversation = un fichier ``conversations/{conversation_id}.json``.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from fahmi2.domain.chat import ChatMessage, Citation, Conversation
from fahmi2.domain.enums import Language
from fahmi2.domain.ids import ConversationId
from fahmi2.infra.storage.fs_artifacts import FsArtifactStore

_CONVERSATIONS_SUBDIR = "conversations"
_FILE_SUFFIX = ".json"
_ENCODING_UTF8 = "utf-8"


def _serialize_citation(citation: Citation) -> dict[str, str]:
    return {
        "chapter_title": citation.chapter_title,
        "section_title": citation.section_title,
        "anchor": citation.anchor,
        "snippet": citation.snippet,
    }


def _serialize_message(message: ChatMessage) -> dict[str, object]:
    return {
        "role": message.role,
        "content": message.content,
        "citations": [_serialize_citation(c) for c in message.citations],
        "cost_usd": message.cost_usd,
        "prompt_tokens": message.prompt_tokens,
        "completion_tokens": message.completion_tokens,
        "created_at": (
            message.created_at.isoformat() if message.created_at else None
        ),
    }


def _deserialize_message(payload: dict[str, object]) -> ChatMessage:
    raw_created = payload.get("created_at")
    citations = tuple(
        Citation(
            chapter_title=str(c["chapter_title"]),
            section_title=str(c["section_title"]),
            anchor=str(c["anchor"]),
            snippet=str(c["snippet"]),
        )
        for c in payload.get("citations", [])  # type: ignore[union-attr]
    )
    return ChatMessage(
        role="assistant" if payload["role"] == "assistant" else "user",
        content=str(payload["content"]),
        citations=citations,
        cost_usd=float(payload.get("cost_usd", 0.0)),  # type: ignore[arg-type]
        prompt_tokens=int(payload.get("prompt_tokens", 0)),  # type: ignore[arg-type]
        completion_tokens=int(payload.get("completion_tokens", 0)),  # type: ignore[arg-type]
        created_at=(
            datetime.fromisoformat(str(raw_created)) if raw_created else None
        ),
    )


class ChatConversationStore:
    """CRUD fichiers des conversations d'un projet."""

    def __init__(self, *, artifacts: FsArtifactStore, chat_dir: Path) -> None:
        """Construit le store.

        Args:
            artifacts: Store d'écriture atomique.
            chat_dir: Dossier ``<workspace>/chat`` de la fonctionnalité.
        """
        self._artifacts = artifacts
        self._dir = chat_dir / _CONVERSATIONS_SUBDIR

    def save(self, conversation: Conversation) -> None:
        """Persiste une conversation (écrase si elle existe).

        Args:
            conversation: Conversation à enregistrer.
        """
        payload = {
            "conversation_id": conversation.conversation_id.value,
            "title": conversation.title,
            "language": str(conversation.language),
            "messages": [_serialize_message(m) for m in conversation.messages],
            "created_at": (
                conversation.created_at.isoformat()
                if conversation.created_at
                else None
            ),
            "updated_at": (
                conversation.updated_at.isoformat()
                if conversation.updated_at
                else None
            ),
        }
        self._artifacts.write_json_atomic(self._path(conversation.conversation_id), payload)

    def load(self, conversation_id: ConversationId) -> Conversation | None:
        """Charge une conversation, ou ``None`` si absente.

        Args:
            conversation_id: Identifiant.

        Returns:
            La ``Conversation``, ou ``None``.
        """
        path = self._path(conversation_id)
        if not path.exists():
            return None
        payload = json.loads(path.read_text(encoding=_ENCODING_UTF8))
        return self._from_payload(payload)

    def list_all(self) -> tuple[Conversation, ...]:
        """Liste toutes les conversations du projet (triées par titre).

        Returns:
            Tuple de conversations (vide si aucune).
        """
        if not self._dir.exists():
            return ()
        conversations = [
            self._from_payload(
                json.loads(path.read_text(encoding=_ENCODING_UTF8))
            )
            for path in sorted(self._dir.glob(f"*{_FILE_SUFFIX}"))
        ]
        return tuple(conversations)

    def delete(self, conversation_id: ConversationId) -> None:
        """Supprime une conversation (idempotent).

        Args:
            conversation_id: Identifiant.
        """
        path = self._path(conversation_id)
        if path.exists():
            path.unlink()

    def _path(self, conversation_id: ConversationId) -> Path:
        return self._dir / f"{conversation_id.value}{_FILE_SUFFIX}"

    @staticmethod
    def _from_payload(payload: dict[str, object]) -> Conversation:
        raw_created = payload.get("created_at")
        raw_updated = payload.get("updated_at")
        return Conversation(
            conversation_id=ConversationId(value=str(payload["conversation_id"])),
            title=str(payload["title"]),
            language=Language(str(payload["language"])),
            messages=tuple(
                _deserialize_message(m)
                for m in payload.get("messages", [])  # type: ignore[union-attr]
            ),
            created_at=(
                datetime.fromisoformat(str(raw_created)) if raw_created else None
            ),
            updated_at=(
                datetime.fromisoformat(str(raw_updated)) if raw_updated else None
            ),
        )
```

- [ ] **Step 4 : Vérifier** → PASS.
- [ ] **Step 5 : Commit** — `git commit -m "feat(chat): persistance des conversations (JSON)"`

---

## Task 9 : `ChatSettings` dans le blob v2

- [ ] **Step 1 : Test** — `tests/unit/infra/storage/test_project_blob_chat.py`

```python
"""Tests de la persistance des ChatSettings dans le blob projet v2."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from fahmi2.domain.chat import ChatSettings
from fahmi2.domain.enums import ChatGroundingMode, RetrievalStrategy
from fahmi2.domain.ids import ProjectId
from fahmi2.domain.project import Project
from fahmi2.infra.storage.sqlite_state import SqliteState


def _project(chat: ChatSettings | None) -> Project:
    return Project(
        id=ProjectId.new(),
        name="P",
        workspace_folder=Path("./ws"),
        created_at=datetime.now(tz=UTC),
        chat=chat,
    )


def test_chat_settings_roundtrip(tmp_path: Path) -> None:
    state = SqliteState(tmp_path / "state.db")
    project = _project(
        ChatSettings(
            grounding_mode=ChatGroundingMode.AUGMENTED,
            retrieval_strategy=RetrievalStrategy.LEXICAL,
        )
    )
    state.upsert_project(project)
    loaded = state.get_project(project.id)
    assert loaded is not None
    assert loaded.chat is not None
    assert loaded.chat.grounding_mode is ChatGroundingMode.AUGMENTED
    assert loaded.chat.retrieval_strategy is RetrievalStrategy.LEXICAL


def test_chat_absent_defaults_to_none(tmp_path: Path) -> None:
    state = SqliteState(tmp_path / "state.db")
    project = _project(None)
    state.upsert_project(project)
    loaded = state.get_project(project.id)
    assert loaded is not None
    assert loaded.chat is None
```

> Vérifier l'API exacte de `SqliteState.__init__` (chemin de base) au moment du
> test ; adapter si le constructeur diffère.

- [ ] **Step 2 : Échec** → pytest.

- [ ] **Step 3 : Implémenter** (4 sous-modifs)

(a) `domain/project.py` : ajouter le champ + helper :

```python
    chat: ChatSettings | None = None
```
```python
    def with_chat(self, chat: ChatSettings | None) -> Project:
        """Retourne une copie avec de nouveaux réglages Dialogue (chat).

        Args:
            chat: Réglages chat, ou ``None``.

        Returns:
            Nouvelle instance immuable (autres réglages préservés).
        """
        return replace(self, chat=chat)
```
Import : `from fahmi2.domain.chat import ChatSettings`.

(b) `infra/storage/sqlite_state.py` :
- Constante : `_BLOB_KEY_CHAT = "chat"`.
- `_serialize_chat_settings(chat) -> dict` et `_deserialize_chat_settings(payload) -> ChatSettings` (calqués sur pedagogy ; champs : grounding_mode, retrieval_strategy, query_expansion_enabled, model, thinking_enabled, reasoning_effort, temperature, top_k).
- `_serialize_project_blob` : ajouter la clé chat.
- `_deserialize_project_blob` : retourner un 4-uple `(workspace, generation, pedagogy, chat)` (lecture lenient : clé absente → `None`).
- Adapter les **appelants** internes (`get_project`, `list_projects`) qui construisent `Project(...)` → passer `chat=...`.

```python
def _serialize_chat_settings(chat: ChatSettings) -> dict[str, Any]:
    return {
        "grounding_mode": str(chat.grounding_mode),
        "retrieval_strategy": str(chat.retrieval_strategy),
        "query_expansion_enabled": chat.query_expansion_enabled,
        "model": str(chat.model),
        "thinking_enabled": chat.thinking_enabled,
        "reasoning_effort": (
            str(chat.reasoning_effort) if chat.reasoning_effort is not None else None
        ),
        "temperature": chat.temperature,
        "top_k": chat.top_k,
    }


def _deserialize_chat_settings(payload: dict[str, Any]) -> ChatSettings:
    return ChatSettings(
        grounding_mode=ChatGroundingMode(payload["grounding_mode"]),
        retrieval_strategy=RetrievalStrategy(payload["retrieval_strategy"]),
        query_expansion_enabled=bool(payload.get("query_expansion_enabled", True)),
        model=LLMModel(payload["model"]),
        thinking_enabled=bool(payload.get("thinking_enabled", False)),
        reasoning_effort=(
            ReasoningEffort(payload["reasoning_effort"])
            if payload.get("reasoning_effort")
            else None
        ),
        temperature=float(payload["temperature"]),
        top_k=int(payload["top_k"]),
    )
```

(c) `app/project_service.py` : ajouter le paramètre `chat: ChatSettings | None = None`
à `create_project` et le passer au `Project(...)`.

(d) Imports manquants dans `sqlite_state.py` : `ChatSettings`, `ChatGroundingMode`,
`RetrievalStrategy` (LLMModel/ReasoningEffort déjà importés).

- [ ] **Step 4 : Vérifier** — `pytest tests/unit/infra/storage/ -q` puis suite ciblée.
- [ ] **Step 5 : Commit** — `git commit -m "feat(chat): ChatSettings persistés dans le blob projet v2"`

---

## Clôture du Lot 2 — vérifications + revue

- [ ] `.venv\Scripts\python.exe -m pytest`
- [ ] `.venv\Scripts\python.exe -m ruff check .`
- [ ] `.venv\Scripts\python.exe -m mypy src tests`
- [ ] **Revue de code approfondie** (9 points + standards). Points d'attention :
  absence de magic values ; cohérence des noms de prompts (constantes) ;
  cohérence domaine sans dépendance infra (sauf moteur `chat/`).
- [ ] **Mettre à jour l'index** : Lot 2 → ✅, puis rédiger le plan du **Lot 3**.
