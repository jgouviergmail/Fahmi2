# Chat « Dialogue » — Lot 3 : Streaming

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans
> (exécution **inline**). Steps en cases à cocher.

**Goal :** Réponses en flux (token par token). Extension **additive** du port
`LLMProvider` (`chat_stream`), implémentation `DeepSeekAdapter` + `FakeLLMProvider`,
et `ChatService.stream_answer`. Aucun impact sur `chat()` (pipeline/pédagogie).

**Architecture :** `chat_stream` yield des `LLMStreamChunk` (deltas + chunk final
porteur de l'`usage`/coût). `ChatService.stream_answer` yield des `ChatAnswerChunk`
(deltas, puis un dernier portant le `ChatMessage` complet avec citations + coût).

**Tech Stack :** Python 3.12, SDK OpenAI (stream SSE DeepSeek), DeepSeek V4
(`stream_options.include_usage` vérifié supporté, cf. spec §6.0).

**Interpréteur :** `.venv\Scripts\python.exe`. **Commits :** footer Co-Authored-By.

**Référence spec :** §6 (streaming), §6.0 (capacités vérifiées).

---

## Task 1 : `LLMStreamChunk` + port `chat_stream` + `FakeLLMProvider.chat_stream`

**Files:** `src/fahmi2/infra/llm/interface.py`, `src/fahmi2/infra/llm/_fakes.py`,
`tests/unit/infra/llm/test_fake_stream.py`

- [ ] **Step 1 : Test** — `tests/unit/infra/llm/test_fake_stream.py`

```python
"""Tests du streaming factice (FakeLLMProvider.chat_stream)."""

from __future__ import annotations

from fahmi2.infra.llm._fakes import FakeLLMProvider
from fahmi2.infra.llm.interface import LLMResponse, Message


def _response(content: str) -> LLMResponse:
    return LLMResponse(
        content=content,
        thinking_content=None,
        prompt_tokens=10,
        completion_tokens=5,
        cached_prompt_tokens=0,
        cost_usd=0.01,
    )


def test_chat_stream_yields_deltas_then_final() -> None:
    provider = FakeLLMProvider(default_response=_response("Le PIB mesure tout"))
    chunks = list(
        provider.chat_stream(
            messages=[Message(role="user", content="q")],
            model="deepseek-v4-flash",
            thinking=False,
            temperature=0.3,
        )
    )
    deltas = "".join(c.content_delta for c in chunks if not c.is_final)
    assert deltas == "Le PIB mesure tout"
    final = chunks[-1]
    assert final.is_final is True
    assert final.response is not None
    assert final.response.cost_usd == 0.01
```

- [ ] **Step 2 : Échec** → pytest.

- [ ] **Step 3 : Implémenter**

(a) `interface.py` — ajouter en tête `from collections.abc import Iterator` et,
après `LLMResponse` :

```python
@dataclass(frozen=True)
class LLMStreamChunk:
    """Fragment de réponse en streaming.

    Attributes:
        content_delta: Incrément de texte de réponse (vide sur le chunk final).
        thinking_delta: Incrément de raisonnement (``None`` si absent).
        is_final: ``True`` pour le dernier chunk (porteur de l'usage/coût).
        response: ``LLMResponse`` complète (usage + coût), seulement si ``is_final``.
    """

    content_delta: str
    thinking_delta: str | None = None
    is_final: bool = False
    response: LLMResponse | None = None
```

Et dans le `Protocol LLMProvider`, ajouter la méthode (après `chat`) :

```python
    def chat_stream(
        self,
        *,
        messages: list[Message],
        model: str,
        thinking: bool,
        reasoning_effort: str | None = None,
        temperature: float,
        max_tokens: int | None = None,
    ) -> Iterator[LLMStreamChunk]:
        """Émet un appel chat en streaming (deltas + chunk final porteur de coût).

        Args:
            messages: Liste ordonnée des messages.
            model: Identifiant du modèle.
            thinking: Active le mode raisonnement.
            reasoning_effort: Niveau d'effort (si ``thinking``).
            temperature: Température LLM.
            max_tokens: Borne supérieure de tokens en sortie.

        Returns:
            Itérateur de ``LLMStreamChunk`` ; le dernier a ``is_final=True`` et
            porte la ``LLMResponse`` complète.

        Raises:
            LLMError: En cas d'échec d'appel.
        """
        ...
```

(b) `_fakes.py` — ajouter `chat_stream` à `FakeLLMProvider` (réutilise la logique
de scénario/échec de `chat`, découpe le contenu en deltas par mot) :

```python
    def chat_stream(
        self,
        *,
        messages: list[Message],
        model: str,
        thinking: bool,
        reasoning_effort: str | None = None,
        temperature: float,
        max_tokens: int | None = None,
    ) -> Iterator[LLMStreamChunk]:
        """Émet la réponse scénarisée en deltas (un par mot) + chunk final."""
        del max_tokens, reasoning_effort
        key = make_request_key(
            messages=messages, model=model, thinking=thinking, temperature=temperature
        )
        if key in self._failures:
            raise self._failures[key]
        response = self._scenarios.get(key, self._default)
        for index, word in enumerate(response.content.split(" ")):
            delta = word if index == 0 else f" {word}"
            yield LLMStreamChunk(content_delta=delta)
        yield LLMStreamChunk(content_delta="", is_final=True, response=response)
```

Imports `_fakes.py` : ajouter `from collections.abc import Iterator` et
`LLMStreamChunk` à l'import depuis `interface`.

- [ ] **Step 4 : Vérifier** → PASS.
- [ ] **Step 5 : Commit** — `feat(chat): port chat_stream + LLMStreamChunk + fake streaming`

---

## Task 2 : `DeepSeekAdapter.chat_stream`

**Files:** `src/fahmi2/infra/llm/deepseek_adapter.py`,
`tests/unit/infra/llm/test_deepseek_adapter.py` (ajout)

- [ ] **Step 1 : Test** — ajouter à `test_deepseek_adapter.py`

```python
def _stream_chunk(payload: dict[str, Any]) -> Any:
    chunk = MagicMock()
    chunk.model_dump.return_value = payload
    return chunk


def test_chat_stream_accumulates_and_final_usage() -> None:
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = iter(
        [
            _stream_chunk({"choices": [{"delta": {"content": "Le "}}], "usage": None}),
            _stream_chunk({"choices": [{"delta": {"content": "PIB"}}], "usage": None}),
            _stream_chunk(
                {
                    "choices": [],
                    "usage": {
                        "prompt_tokens": 100,
                        "completion_tokens": 20,
                        "prompt_cache_hit_tokens": 0,
                    },
                }
            ),
        ]
    )
    adapter = DeepSeekAdapter(api_key="dummy", client=mock_client)
    chunks = list(
        adapter.chat_stream(
            messages=[Message(role="user", content="u")],
            model="deepseek-v4-flash",
            thinking=False,
            temperature=0.3,
        )
    )
    assert "".join(c.content_delta for c in chunks if not c.is_final) == "Le PIB"
    final = chunks[-1]
    assert final.is_final and final.response is not None
    assert final.response.completion_tokens == 20
    assert final.response.cost_usd > 0
    call = mock_client.chat.completions.create.call_args
    assert call.kwargs["stream"] is True
    assert call.kwargs["stream_options"] == {"include_usage": True}
```

- [ ] **Step 2 : Échec** → pytest.

- [ ] **Step 3 : Implémenter** dans `deepseek_adapter.py`

Imports : `from collections.abc import Iterator`, `from fahmi2.core.text_metrics
import estimate_tokens`, et `LLMStreamChunk` depuis `interface`.

Méthode `chat_stream` sur `DeepSeekAdapter` :

```python
    def chat_stream(
        self,
        *,
        messages: list[Message],
        model: str,
        thinking: bool,
        reasoning_effort: str | None = None,
        temperature: float,
        max_tokens: int | None = None,
    ) -> Iterator[LLMStreamChunk]:
        """Émet un appel chat en streaming SSE (deltas + chunk final).

        Args:
            messages: Conversation.
            model: Modèle DeepSeek.
            thinking: Active le mode raisonnement.
            reasoning_effort: Niveau d'effort (si ``thinking``).
            temperature: Température.
            max_tokens: Limite de tokens en sortie.

        Yields:
            ``LLMStreamChunk`` (deltas, puis un dernier ``is_final`` porteur du coût).

        Raises:
            LLMError: En cas d'échec d'appel.
        """
        kwargs = self._build_kwargs(
            messages=messages,
            model=model,
            thinking=thinking,
            reasoning_effort=reasoning_effort,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        kwargs["stream"] = True
        kwargs["stream_options"] = {"include_usage": True}
        prompt_text = " ".join(m.content for m in messages)
        content_parts: list[str] = []
        reasoning_parts: list[str] = []
        usage: dict[str, Any] | None = None
        try:
            stream = self._client.chat.completions.create(**kwargs)
            for raw_chunk in stream:
                chunk = raw_chunk.model_dump()
                choices = chunk.get("choices") or []
                if choices:
                    delta = choices[0].get("delta") or {}
                    content_delta = str(delta.get("content") or "")
                    reasoning_raw = delta.get(_REASONING_FIELD)
                    reasoning_delta = (
                        str(reasoning_raw) if reasoning_raw else None
                    )
                    if content_delta or reasoning_delta:
                        content_parts.append(content_delta)
                        if reasoning_delta:
                            reasoning_parts.append(reasoning_delta)
                        yield LLMStreamChunk(
                            content_delta=content_delta, thinking_delta=reasoning_delta
                        )
                if chunk.get("usage"):
                    usage = chunk["usage"]
        except BaseException as exc:  # noqa: BLE001 — mappé vers une LLMError typée
            raise _map_exception_to_llm_error(exc) from exc
        yield LLMStreamChunk(
            content_delta="",
            is_final=True,
            response=_build_stream_response(
                content="".join(content_parts),
                thinking_content="".join(reasoning_parts) or None,
                usage=usage,
                model=model,
                prompt_text=prompt_text,
            ),
        )
```

Extraire la construction des kwargs (réutilisée par `chat` et `chat_stream`) dans
`_build_kwargs` (refactor de `chat`, DRY) :

```python
    def _build_kwargs(
        self,
        *,
        messages: list[Message],
        model: str,
        thinking: bool,
        reasoning_effort: str | None,
        temperature: float,
        max_tokens: int | None,
    ) -> dict[str, Any]:
        """Construit les kwargs communs d'appel (chat et chat_stream)."""
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
        }
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        extra_body: dict[str, Any] = {
            "thinking": {"type": "enabled" if thinking else "disabled"}
        }
        if thinking and reasoning_effort is not None:
            extra_body["reasoning_effort"] = reasoning_effort
        kwargs["extra_body"] = extra_body
        return kwargs
```
(et remplacer le corps de `chat` qui construit kwargs par un appel à `_build_kwargs`.)

Fonction module `_build_stream_response` (à côté de `_parse_chat_response`) :

```python
def _build_stream_response(
    *,
    content: str,
    thinking_content: str | None,
    usage: dict[str, Any] | None,
    model: str,
    prompt_text: str,
) -> LLMResponse:
    """Construit la ``LLMResponse`` finale d'un flux (usage exact ou estimé).

    Args:
        content: Contenu accumulé.
        thinking_content: Raisonnement accumulé (ou ``None``).
        usage: Bloc ``usage`` du dernier chunk (``None`` si non fourni → repli).
        model: Modèle (pour le coût).
        prompt_text: Concaténation des messages (repli d'estimation des tokens).

    Returns:
        ``LLMResponse`` (coût exact si ``usage`` présent, sinon estimé).
    """
    if usage:
        prompt_tokens = int(usage.get("prompt_tokens", 0))
        completion_tokens = int(usage.get("completion_tokens", 0))
        cached = int(usage.get(_CACHED_TOKENS_FIELD, 0) or 0)
    else:
        prompt_tokens = estimate_tokens(prompt_text)
        completion_tokens = estimate_tokens(content)
        cached = 0
    cost = get_pricing(model).cost_for(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        cached_prompt_tokens=cached,
    )
    return LLMResponse(
        content=content,
        thinking_content=thinking_content,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        cached_prompt_tokens=cached,
        cost_usd=cost,
    )
```

- [ ] **Step 4 : Vérifier** → PASS (+ relancer tous les tests deepseek).
- [ ] **Step 5 : Commit** — `feat(chat): DeepSeekAdapter.chat_stream (usage exact + repli)`

---

## Task 3 : `ChatService.stream_answer` + `ChatAnswerChunk`

**Files:** `src/fahmi2/chat/chat_service.py`, `tests/unit/chat/test_chat_service.py`

- [ ] **Step 1 : Test** — ajouter à `test_chat_service.py`

```python
def test_stream_answer_yields_deltas_then_final_message() -> None:
    retriever = TfidfPassageRetriever(
        (_chunk("1", "Le produit intérieur brut mesure la richesse."),)
    )
    service = _service("Le PIB mesure la richesse [§1].")
    chunks = list(
        service.stream_answer(
            question="Qu'est-ce que le PIB ?",
            retriever=retriever,
            glossary_text="",
            history=(),
            settings=ChatSettings(),
            language=Language.FR,
        )
    )
    streamed = "".join(c.content_delta for c in chunks if c.message is None)
    assert streamed == "Le PIB mesure la richesse [§1]."
    final = chunks[-1]
    assert final.message is not None
    assert final.message.role == "assistant"
    assert final.message.citations[0].anchor == "pib"
    assert final.message.cost_usd == 0.01
```

- [ ] **Step 2 : Échec** → pytest.

- [ ] **Step 3 : Implémenter** — refactor `chat_service.py` (DRY entre `answer` et
  `stream_answer`) :

Imports : ajouter `from collections.abc import Iterator`, `from dataclasses import
dataclass`, `from fahmi2.chat.prompt_builder import build_chat_messages` (déjà),
`from fahmi2.domain.chat import ChatMessage, ChatSettings, RetrievedPassage`,
`from fahmi2.infra.llm.interface import LLMProvider, LLMResponse, Message`.

```python
@dataclass(frozen=True)
class ChatAnswerChunk:
    """Fragment de réponse du chat (delta, ou message final si ``message``)."""

    content_delta: str
    message: ChatMessage | None = None
```

Méthodes privées partagées + `stream_answer` :

```python
    def _prepare(
        self, *, question, retriever, glossary_text, history, settings, language
    ) -> tuple[list[Message], tuple[RetrievedPassage, ...]]:
        """Récupère les passages et assemble les messages (commun answer/stream)."""
        passages = tuple(retriever.retrieve(query=question, top_k=settings.top_k))
        messages = build_chat_messages(
            question=question, passages=passages, glossary_text=glossary_text,
            history=history, settings=settings, language=language,
            prompt_loader=self._prompts,
        )
        return messages, passages

    def _build_message(
        self, response: LLMResponse, passages: tuple[RetrievedPassage, ...]
    ) -> ChatMessage:
        """Construit le ChatMessage assistant final (citations + coût)."""
        return ChatMessage(
            role="assistant",
            content=response.content,
            citations=parse_citations(response.content, passages),
            cost_usd=response.cost_usd,
            prompt_tokens=response.prompt_tokens,
            completion_tokens=response.completion_tokens,
            created_at=datetime.now(tz=UTC),
        )

    def stream_answer(
        self, *, question, retriever, glossary_text, history, settings, language
    ) -> Iterator[ChatAnswerChunk]:
        """Génère la réponse en flux (deltas puis chunk final porteur du message)."""
        messages, passages = self._prepare(
            question=question, retriever=retriever, glossary_text=glossary_text,
            history=history, settings=settings, language=language,
        )
        content_parts: list[str] = []
        final_response: LLMResponse | None = None
        for chunk in self._llm.chat_stream(
            messages=messages, model=str(settings.model),
            thinking=settings.thinking_enabled,
            reasoning_effort=(
                str(settings.reasoning_effort)
                if settings.reasoning_effort is not None else None
            ),
            temperature=settings.temperature,
        ):
            if chunk.is_final and chunk.response is not None:
                final_response = chunk.response
            elif chunk.content_delta:
                content_parts.append(chunk.content_delta)
                yield ChatAnswerChunk(content_delta=chunk.content_delta)
        response = final_response or LLMResponse(
            content="".join(content_parts), thinking_content=None,
            prompt_tokens=0, completion_tokens=0, cached_prompt_tokens=0, cost_usd=0.0,
        )
        yield ChatAnswerChunk(content_delta="", message=self._build_message(response, passages))
```

Et `answer` réécrit pour réutiliser `_prepare`/`_build_message` :

```python
    def answer(self, *, question, retriever, glossary_text, history, settings, language) -> ChatMessage:
        messages, passages = self._prepare(
            question=question, retriever=retriever, glossary_text=glossary_text,
            history=history, settings=settings, language=language,
        )
        response = self._llm.chat(
            messages=messages, model=str(settings.model),
            thinking=settings.thinking_enabled,
            reasoning_effort=(
                str(settings.reasoning_effort)
                if settings.reasoning_effort is not None else None
            ),
            temperature=settings.temperature,
        )
        return self._build_message(response, passages)
```

(Signatures complètes des paramètres conservées comme au Lot 2 ; conserver les
annotations de type sur `_prepare`/`stream_answer`.)

- [ ] **Step 4 : Vérifier** → PASS (tous les tests chat).
- [ ] **Step 5 : Commit** — `feat(chat): ChatService.stream_answer (flux + message final)`

---

## Clôture du Lot 3 — vérifications + revue

- [ ] `pytest`, `ruff check .`, `mypy src tests` **verts**.
- [ ] **Revue approfondie** (9 points) : DRY (`_build_kwargs`, `_prepare`/
  `_build_message`) ; pas de magic value ; `chat()` inchangé fonctionnellement
  (non-régression pipeline/pédagogie) ; le Protocol étendu n'a cassé aucun
  implémenteur.
- [ ] **Index** : Lot 3 → ✅, puis plan du **Lot 4**.
