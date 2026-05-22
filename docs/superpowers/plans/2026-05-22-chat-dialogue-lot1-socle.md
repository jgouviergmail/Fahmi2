# Chat « Dialogue » — Lot 1 : Socle domaine + corpus + retrieval lexical

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans
> (exécution **inline**, préférence projet). Steps en cases à cocher (`- [ ]`).

**Goal :** Poser le socle non-UI/non-LLM du chat : entités du domaine, identifiant
de conversation, enums, port `PassageRetriever` + implémentation TF-IDF, et le
chargement + découpage (chunking) du corpus.

**Architecture :** `domain/` pur (frozen dataclasses, aucun import infra/Qt) ;
`core/retrieval/passages.py` réutilise la stack scikit-learn du glossaire ;
nouveau package moteur `chat/` (calqué sur `pedagogy/`) pour `corpus.py`.

**Tech Stack :** Python 3.12, scikit-learn (déjà présent), `pedagogy.chapters`,
`core.slugify`.

**Interpréteur :** `.venv\Scripts\python.exe`.
**Commits :** chaque message se termine par
`Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>`.
**Imports de test :** les blocs d'import montrés par tâche se **fusionnent** en tête
du fichier de test concerné (pas de doublon) — `ruff` doit rester propre à chaque commit.

**Référence spec :** §3 (modèle de données), §4.1-4.2 (retrieval lexical),
§5 + §5.1 (corpus & chunking) de
[2026-05-22-chat-dialogue-corpus-design.md](../specs/2026-05-22-chat-dialogue-corpus-design.md).

---

## Fichiers du lot

- Modifier : `src/fahmi2/domain/enums.py` (2 enums)
- Modifier : `src/fahmi2/domain/ids.py` (`ConversationId`)
- Créer : `src/fahmi2/domain/chat.py` (entités + `ChatSettings`)
- Créer : `src/fahmi2/core/retrieval/passages.py` (port + TF-IDF)
- Créer : `src/fahmi2/chat/__init__.py`
- Créer : `src/fahmi2/chat/corpus.py` (chargement + chunking)
- Tests : `tests/unit/domain/test_chat.py`,
  `tests/unit/core/test_passage_retrieval.py`,
  `tests/unit/chat/test_corpus.py`

---

## Task 1 : Enums `ChatGroundingMode` & `RetrievalStrategy`

**Files:**
- Modify: `src/fahmi2/domain/enums.py`
- Test: `tests/unit/domain/test_chat.py`

- [ ] **Step 1 : Écrire le test qui échoue**

```python
"""Tests des entités et enums du chat de dialogue."""

from __future__ import annotations

from fahmi2.domain.enums import ChatGroundingMode, RetrievalStrategy


def test_grounding_mode_values() -> None:
    assert ChatGroundingMode.STRICT.value == "strict"
    assert ChatGroundingMode.AUGMENTED.value == "augmented"


def test_retrieval_strategy_values() -> None:
    assert RetrievalStrategy.AUTO.value == "auto"
    assert RetrievalStrategy.LEXICAL.value == "lexical"
    assert RetrievalStrategy.SEMANTIC.value == "semantic"
```

- [ ] **Step 2 : Lancer le test (échec attendu)**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/domain/test_chat.py -v`
Expected: FAIL — `ImportError: cannot import name 'ChatGroundingMode'`.

- [ ] **Step 3 : Implémenter les enums**

Ajouter à la fin de `src/fahmi2/domain/enums.py` :

```python
class ChatGroundingMode(StrEnum):
    """Posture de fidélité des réponses du chat de dialogue."""

    STRICT = "strict"        # uniquement le corpus, citations, refus hors-corpus
    AUGMENTED = "augmented"  # corpus prioritaire + complément balisé


class RetrievalStrategy(StrEnum):
    """Stratégie de récupération des passages du corpus."""

    AUTO = "auto"            # défaut : sémantique si clé OpenAI dispo, sinon lexical
    LEXICAL = "lexical"      # TF-IDF (+ query expansion), 100% offline
    SEMANTIC = "semantic"    # embeddings OpenAI
```

- [ ] **Step 4 : Lancer le test (succès attendu)**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/domain/test_chat.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5 : Commit**

```bash
git add src/fahmi2/domain/enums.py tests/unit/domain/test_chat.py
git commit -m "feat(chat): enums ChatGroundingMode et RetrievalStrategy"
```

---

## Task 2 : Identifiant `ConversationId`

**Files:**
- Modify: `src/fahmi2/domain/ids.py`
- Test: `tests/unit/domain/test_chat.py`

- [ ] **Step 1 : Ajouter le test qui échoue**

Ajouter à `tests/unit/domain/test_chat.py` :

```python
from fahmi2.domain.ids import ConversationId


def test_conversation_id_is_distinct_ulid() -> None:
    cid = ConversationId.new()
    assert isinstance(cid.value, str)
    assert len(cid.value) == 26
    assert ConversationId(value=cid.value) == cid
```

- [ ] **Step 2 : Lancer le test (échec attendu)**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/domain/test_chat.py::test_conversation_id_is_distinct_ulid -v`
Expected: FAIL — `ImportError: cannot import name 'ConversationId'`.

- [ ] **Step 3 : Implémenter**

Ajouter à la fin de `src/fahmi2/domain/ids.py` :

```python
@dataclass(frozen=True)
class ConversationId(_UlidIdBase):
    """Identifiant stable d'une conversation du chat de dialogue."""
```

- [ ] **Step 4 : Lancer le test (succès attendu)**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/domain/test_chat.py::test_conversation_id_is_distinct_ulid -v`
Expected: PASS.

- [ ] **Step 5 : Commit**

```bash
git add src/fahmi2/domain/ids.py tests/unit/domain/test_chat.py
git commit -m "feat(chat): ConversationId (ULID typé)"
```

---

## Task 3 : Entités de données (`CorpusChunk`, `RetrievedPassage`, `Citation`, `ChatMessage`)

**Files:**
- Create: `src/fahmi2/domain/chat.py`
- Test: `tests/unit/domain/test_chat.py`

- [ ] **Step 1 : Ajouter le test qui échoue**

Ajouter à `tests/unit/domain/test_chat.py` :

```python
from fahmi2.domain.chat import Citation, ChatMessage, CorpusChunk, RetrievedPassage


def test_corpus_chunk_and_passage() -> None:
    chunk = CorpusChunk(
        chunk_id="1-bases::0",
        chapter_title="Bases",
        section_title="Bases",
        anchor="1-bases",
        text="contenu",
        origin="consolidated",
    )
    passage = RetrievedPassage(chunk=chunk, score=0.8)
    assert passage.chunk.anchor == "1-bases"
    assert passage.score == 0.8


def test_chat_message_defaults() -> None:
    msg = ChatMessage(role="user", content="bonjour")
    assert msg.role == "user"
    assert msg.citations == ()
    assert msg.cost_usd == 0.0


def test_citation_fields() -> None:
    cit = Citation(
        chapter_title="Bases", section_title="1.1", anchor="11", snippet="…"
    )
    assert cit.anchor == "11"
```

- [ ] **Step 2 : Lancer le test (échec attendu)**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/domain/test_chat.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'fahmi2.domain.chat'`.

- [ ] **Step 3 : Créer `src/fahmi2/domain/chat.py`**

```python
"""Entités immuables du chat de dialogue ancré sur le corpus.

``domain/`` ne dépend ni d'``infra`` ni de Qt : le rôle d'un message est un type
**du domaine** (``ChatRole``), distinct du ``Role`` d'``infra/llm`` ; la conversion
``ChatMessage`` → ``infra/llm.Message`` se fait dans ``chat/prompt_builder.py``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

ChatRole = Literal["user", "assistant"]


@dataclass(frozen=True)
class CorpusChunk:
    """Passage indexable du corpus (section du consolidé ou entrée de glossaire).

    Attributes:
        chunk_id: Identifiant stable du chunk (ancre + ordinal, ou ``glossary::…``).
        chapter_title: Titre du chapitre d'origine.
        section_title: Titre de la section (ou du chapitre à défaut).
        anchor: Ancre GFM (``slugify_anchor``) → citation cliquable.
        text: Contenu textuel du passage.
        origin: ``"consolidated"`` ou ``"glossary"``.
    """

    chunk_id: str
    chapter_title: str
    section_title: str
    anchor: str
    text: str
    origin: str


@dataclass(frozen=True)
class RetrievedPassage:
    """Passage récupéré + score de pertinence."""

    chunk: CorpusChunk
    score: float


@dataclass(frozen=True)
class Citation:
    """Référence vers un passage cité dans une réponse."""

    chapter_title: str
    section_title: str
    anchor: str
    snippet: str


@dataclass(frozen=True)
class ChatMessage:
    """Un tour de conversation (question ou réponse)."""

    role: ChatRole
    content: str
    citations: tuple[Citation, ...] = ()
    cost_usd: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    created_at: datetime | None = None
```

- [ ] **Step 4 : Lancer le test (succès attendu)**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/domain/test_chat.py -v`
Expected: PASS.

- [ ] **Step 5 : Commit**

```bash
git add src/fahmi2/domain/chat.py tests/unit/domain/test_chat.py
git commit -m "feat(chat): entités CorpusChunk, RetrievedPassage, Citation, ChatMessage"
```

---

## Task 4 : `Conversation` + `ChatSettings`

**Files:**
- Modify: `src/fahmi2/domain/chat.py`
- Test: `tests/unit/domain/test_chat.py`

- [ ] **Step 1 : Ajouter le test qui échoue**

Ajouter à `tests/unit/domain/test_chat.py` :

```python
from fahmi2.domain.chat import ChatSettings, Conversation
from fahmi2.domain.enums import ChatGroundingMode, LLMModel, RetrievalStrategy, Language
from fahmi2.domain.ids import ConversationId


def test_conversation_with_message_and_total_cost() -> None:
    conv = Conversation(
        conversation_id=ConversationId.new(), title="Q1", language=Language.FR
    )
    conv2 = conv.with_message(ChatMessage(role="user", content="q"))
    conv3 = conv2.with_message(
        ChatMessage(role="assistant", content="r", cost_usd=0.02)
    )
    assert conv.messages == ()  # immuable : l'original est inchangé
    assert len(conv3.messages) == 2
    assert conv3.total_cost_usd() == 0.02


def test_chat_settings_defaults() -> None:
    s = ChatSettings()
    assert s.grounding_mode is ChatGroundingMode.STRICT
    assert s.retrieval_strategy is RetrievalStrategy.AUTO
    assert s.query_expansion_enabled is True
    assert s.model is LLMModel.DEEPSEEK_V4_FLASH
    assert s.thinking_enabled is False
    assert s.top_k == 6


def test_chat_settings_with_helpers() -> None:
    s = ChatSettings().with_grounding_mode(ChatGroundingMode.AUGMENTED)
    assert s.grounding_mode is ChatGroundingMode.AUGMENTED
    s2 = s.with_retrieval_strategy(RetrievalStrategy.LEXICAL)
    assert s2.retrieval_strategy is RetrievalStrategy.LEXICAL
    assert s.retrieval_strategy is RetrievalStrategy.AUTO  # original inchangé
```

- [ ] **Step 2 : Lancer le test (échec attendu)**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/domain/test_chat.py -v`
Expected: FAIL — `ImportError: cannot import name 'Conversation'`.

- [ ] **Step 3 : Implémenter dans `src/fahmi2/domain/chat.py`**

Compléter les imports en tête (fusionner avec l'existant) :

```python
from dataclasses import dataclass, replace

from fahmi2.domain.enums import (
    ChatGroundingMode,
    Language,
    LLMModel,
    ReasoningEffort,
    RetrievalStrategy,
)
from fahmi2.domain.ids import ConversationId
```

Ajouter les constantes près du haut du module (sous `ChatRole`) :

```python
_DEFAULT_CHAT_TEMPERATURE = 0.3
_DEFAULT_TOP_K = 6
```

Ajouter les classes à la fin du fichier :

```python
@dataclass(frozen=True)
class Conversation:
    """Conversation persistée, propre à un projet."""

    conversation_id: ConversationId
    title: str
    language: Language
    messages: tuple[ChatMessage, ...] = ()
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def with_message(self, message: ChatMessage) -> "Conversation":
        """Retourne une copie avec ``message`` ajouté en fin.

        Args:
            message: Tour à ajouter.

        Returns:
            Nouvelle instance immuable.
        """
        return replace(self, messages=(*self.messages, message))

    def total_cost_usd(self) -> float:
        """Somme des coûts des messages de la conversation.

        Returns:
            Coût cumulé en USD.
        """
        return sum(m.cost_usd for m in self.messages)


@dataclass(frozen=True)
class ChatSettings:
    """Réglages de l'onglet Dialogue (blob ``settings_json`` v2, clé ``chat``)."""

    grounding_mode: ChatGroundingMode = ChatGroundingMode.STRICT
    retrieval_strategy: RetrievalStrategy = RetrievalStrategy.AUTO
    query_expansion_enabled: bool = True
    model: LLMModel = LLMModel.DEEPSEEK_V4_FLASH
    thinking_enabled: bool = False
    reasoning_effort: ReasoningEffort | None = None
    temperature: float = _DEFAULT_CHAT_TEMPERATURE
    top_k: int = _DEFAULT_TOP_K

    def with_grounding_mode(self, mode: ChatGroundingMode) -> "ChatSettings":
        """Copie avec un nouveau mode de fidélité."""
        return replace(self, grounding_mode=mode)

    def with_retrieval_strategy(self, strategy: RetrievalStrategy) -> "ChatSettings":
        """Copie avec une nouvelle stratégie de retrieval."""
        return replace(self, retrieval_strategy=strategy)
```

- [ ] **Step 4 : Lancer le test (succès attendu)**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/domain/test_chat.py -v`
Expected: PASS.

- [ ] **Step 5 : Commit**

```bash
git add src/fahmi2/domain/chat.py tests/unit/domain/test_chat.py
git commit -m "feat(chat): Conversation (with_message/total_cost) + ChatSettings"
```

---

## Task 5 : Port `PassageRetriever` + `TfidfPassageRetriever`

**Files:**
- Create: `src/fahmi2/core/retrieval/passages.py`
- Test: `tests/unit/core/test_passage_retrieval.py`

- [ ] **Step 1 : Écrire le test qui échoue**

```python
"""Tests du retrieval de passages (TF-IDF lexical)."""

from __future__ import annotations

from fahmi2.core.retrieval.passages import TfidfPassageRetriever
from fahmi2.domain.chat import CorpusChunk


def _chunk(cid: str, text: str) -> CorpusChunk:
    return CorpusChunk(
        chunk_id=cid,
        chapter_title="C",
        section_title="S",
        anchor="a",
        text=text,
        origin="consolidated",
    )


def test_retrieves_most_relevant_first() -> None:
    chunks = (
        _chunk("1", "Le produit intérieur brut mesure la richesse produite."),
        _chunk("2", "La photosynthèse transforme la lumière en énergie."),
    )
    results = TfidfPassageRetriever(chunks).retrieve(
        query="la richesse produite et le produit intérieur", top_k=2
    )
    assert results[0].chunk.chunk_id == "1"
    assert len(results) == 2


def test_empty_corpus_returns_empty() -> None:
    assert TfidfPassageRetriever(()).retrieve(query="x", top_k=3) == []


def test_respects_top_k() -> None:
    chunks = tuple(_chunk(str(i), f"texte {i} économie marché") for i in range(5))
    results = TfidfPassageRetriever(chunks).retrieve(query="économie", top_k=2)
    assert len(results) == 2
```

- [ ] **Step 2 : Lancer le test (échec attendu)**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/core/test_passage_retrieval.py -v`
Expected: FAIL — `ModuleNotFoundError: ...core.retrieval.passages`.

- [ ] **Step 3 : Créer `src/fahmi2/core/retrieval/passages.py`**

```python
"""Port ``PassageRetriever`` + implémentation TF-IDF (passages du corpus).

Distinct de :py:class:`GlossaryRetriever` (qui sélectionne des *termes*) : ici on
récupère des *passages* (``CorpusChunk``) pertinents pour une question en langage
naturel. Réutilise la stack ``scikit-learn`` déjà présente (cf. ``tfidf.py``).
"""

from __future__ import annotations

from typing import Any, Protocol

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from fahmi2.domain.chat import CorpusChunk, RetrievedPassage


class PassageRetriever(Protocol):
    """Récupère les passages du corpus les plus pertinents pour une question."""

    def retrieve(self, *, query: str, top_k: int) -> list[RetrievedPassage]:
        """Retourne au plus ``top_k`` passages, triés par pertinence décroissante.

        Args:
            query: Question en langage naturel.
            top_k: Nombre maximal de passages.

        Returns:
            Liste de ``RetrievedPassage`` (taille <= ``top_k``).
        """


class TfidfPassageRetriever:
    """Retriever top-K par similarité TF-IDF (cosine) sur les chunks du corpus.

    La matrice TF-IDF est construite à l'instanciation (corpus d'un cours = petit).
    """

    def __init__(self, chunks: tuple[CorpusChunk, ...]) -> None:
        """Construit l'index TF-IDF des chunks.

        Args:
            chunks: Passages du corpus à indexer.
        """
        self._chunks = chunks
        self._vectorizer = TfidfVectorizer(
            lowercase=True,
            token_pattern=r"(?u)\b\w+\b",  # noqa: S106 — tokenizer regex, pas un secret
        )
        self._matrix: Any = (
            self._vectorizer.fit_transform([c.text for c in chunks])
            if chunks
            else None
        )

    def retrieve(self, *, query: str, top_k: int) -> list[RetrievedPassage]:
        """Retourne au plus ``top_k`` passages triés par pertinence décroissante.

        Args:
            query: Question en langage naturel.
            top_k: Nombre maximal de passages.

        Returns:
            Liste de ``RetrievedPassage``.
        """
        if not self._chunks or top_k <= 0 or not query.strip():
            return []
        query_vec = self._vectorizer.transform([query])
        similarities = cosine_similarity(query_vec, self._matrix)[0]
        ranked = sorted(
            enumerate(similarities),
            key=lambda pair: (-pair[1], pair[0]),
        )
        return [
            RetrievedPassage(chunk=self._chunks[i], score=float(score))
            for i, score in ranked[:top_k]
        ]
```

- [ ] **Step 4 : Lancer le test (succès attendu)**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/core/test_passage_retrieval.py -v`
Expected: PASS.

- [ ] **Step 5 : Commit**

```bash
git add src/fahmi2/core/retrieval/passages.py tests/unit/core/test_passage_retrieval.py
git commit -m "feat(chat): port PassageRetriever + TfidfPassageRetriever"
```

---

## Task 6 : Découpage du corpus (`chunk_consolidated`)

**Files:**
- Create: `src/fahmi2/chat/__init__.py`
- Create: `src/fahmi2/chat/corpus.py`
- Test: `tests/unit/chat/test_corpus.py`

- [ ] **Step 1 : Écrire le test qui échoue**

Créer `tests/unit/chat/test_corpus.py` :

```python
"""Tests du chargement et du découpage (chunking) du corpus."""

from __future__ import annotations

from fahmi2.chat.corpus import chunk_consolidated

_DOC = """# Mon cours

## Résumé

abstract

# 1. Bases

Paragraphe introductif du chapitre.

## 1.1 Définitions

Une définition importante ici.

# 2. Avancé

Contenu avancé.
"""


def test_chunk_consolidated_chapters_and_sections() -> None:
    chunks = chunk_consolidated(_DOC)
    assert {c.chapter_title for c in chunks} == {"Bases", "Avancé"}
    sections = {c.section_title for c in chunks}
    assert "1.1 Définitions" in sections
    assert any(c.anchor == "11-définitions" for c in chunks)
    assert all(c.origin == "consolidated" for c in chunks)


def test_chunk_ids_are_unique() -> None:
    chunks = chunk_consolidated(_DOC)
    ids = [c.chunk_id for c in chunks]
    assert len(ids) == len(set(ids))


def test_large_section_splits_into_multiple_chunks() -> None:
    big = "paragraphe répété. " * 400  # ~ 1900 tokens estimés
    doc = f"# T\n\n# 1. Gros\n\n{big}\n\n{big}\n"
    chunks = [c for c in chunk_consolidated(doc) if c.chapter_title == "Gros"]
    assert len(chunks) >= 2
```

- [ ] **Step 2 : Lancer le test (échec attendu)**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/chat/test_corpus.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'fahmi2.chat'`.

- [ ] **Step 3 : Créer le package et le chunker**

Créer `src/fahmi2/chat/__init__.py` :

```python
"""Moteur du chat de dialogue ancré sur le corpus."""
```

Créer `src/fahmi2/chat/corpus.py` :

```python
"""Chargement et découpage (chunking) du corpus interrogeable du chat.

Le corpus = document consolidé (chunké par section, cf. spec §5.1) + entrées de
glossaire (un chunk par terme). Réutilise ``pedagogy.chapters`` et
``pedagogy.sources``. Toutes les valeurs de découpage sont des constantes.
"""

from __future__ import annotations

import re

from fahmi2.core.slugify import slugify_anchor
from fahmi2.domain.chat import CorpusChunk
from fahmi2.pedagogy.chapters import Chapter, parse_chapters

_CHARS_PER_TOKEN = 4
_CHUNK_TARGET_TOKENS = 700
_CHUNK_MIN_TOKENS = 120
_CHUNK_OVERLAP_BLOCKS = 1
_ORIGIN_CONSOLIDATED = "consolidated"
_FENCE = "```"
_RE_SUBHEADING = re.compile(r"^#{2,}\s+(.+?)\s*$")


def _estimate_tokens(text: str) -> int:
    """Estimation grossière du nombre de tokens d'un texte."""
    return max(1, len(text) // _CHARS_PER_TOKEN)


def _match_subheading(line: str) -> str | None:
    """Titre d'une sous-section (``##``+), ou ``None``."""
    match = _RE_SUBHEADING.match(line)
    return match.group(1).strip() if match is not None else None


def _split_blocks(body: str) -> list[tuple[str, str]]:
    """Découpe le corps d'un chapitre en ``(section_title, bloc)``.

    Les titres ``##``/``###`` fixent la section courante (non émis). Les blocs sont
    séparés par lignes vides ; un bloc de code ``` reste entier (intégrité).

    Args:
        body: Corps Markdown du chapitre.

    Returns:
        Liste ordonnée de ``(section_title, texte_du_bloc)``.
    """
    blocks: list[tuple[str, str]] = []
    current_section = ""
    buffer: list[str] = []
    in_fence = False

    def flush() -> None:
        nonlocal buffer
        text = "\n".join(buffer).strip()
        if text:
            blocks.append((current_section, text))
        buffer = []

    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith(_FENCE):
            in_fence = not in_fence
            buffer.append(line)
            continue
        if not in_fence:
            heading = _match_subheading(line)
            if heading is not None:
                flush()
                current_section = heading
                continue
            if stripped == "":
                flush()
                continue
        buffer.append(line)
    flush()
    return blocks


def _pack_blocks(blocks: list[str]) -> list[str]:
    """Regroupe des blocs en textes ``<= cible`` (+ chevauchement, + fusion finale).

    Args:
        blocks: Blocs d'une même section, dans l'ordre.

    Returns:
        Textes de chunks (chevauchement d'un bloc entre voisins).
    """
    packed: list[str] = []
    acc: list[str] = []
    acc_tokens = 0
    for block in blocks:
        block_tokens = _estimate_tokens(block)
        if acc and acc_tokens + block_tokens > _CHUNK_TARGET_TOKENS:
            packed.append("\n\n".join(acc))
            acc = acc[-_CHUNK_OVERLAP_BLOCKS:] if _CHUNK_OVERLAP_BLOCKS else []
            acc_tokens = sum(_estimate_tokens(b) for b in acc)
        acc.append(block)
        acc_tokens += block_tokens
    if acc:
        packed.append("\n\n".join(acc))
    if len(packed) >= 2 and _estimate_tokens(packed[-1]) < _CHUNK_MIN_TOKENS:
        tail = packed.pop()
        packed[-1] = f"{packed[-1]}\n\n{tail}"
    return packed


def _chunk_chapter(chapter: Chapter) -> list[CorpusChunk]:
    """Découpe un chapitre en ``CorpusChunk`` (par section, taille bornée).

    Args:
        chapter: Chapitre parsé du consolidé.

    Returns:
        Chunks du chapitre.
    """
    sections: list[tuple[str, list[str]]] = []
    for section, block in _split_blocks(chapter.body_markdown):
        if sections and sections[-1][0] == section:
            sections[-1][1].append(block)
        else:
            sections.append((section, [block]))

    chunks: list[CorpusChunk] = []
    ordinal = 0
    for section, blocks in sections:
        section_title = section or chapter.title
        anchor = slugify_anchor(section) if section else chapter.anchor
        for text in _pack_blocks(blocks):
            chunks.append(
                CorpusChunk(
                    chunk_id=f"{chapter.anchor}::{ordinal}",
                    chapter_title=chapter.title,
                    section_title=section_title,
                    anchor=anchor,
                    text=text,
                    origin=_ORIGIN_CONSOLIDATED,
                )
            )
            ordinal += 1
    return chunks


def chunk_consolidated(consolidated_markdown: str) -> tuple[CorpusChunk, ...]:
    """Découpe un document consolidé entier en chunks.

    Args:
        consolidated_markdown: Contenu d'un ``consolidated.{lang}.md``.

    Returns:
        Chunks de tous les chapitres (vide si aucun chapitre).
    """
    chunks: list[CorpusChunk] = []
    for chapter in parse_chapters(consolidated_markdown):
        chunks.extend(_chunk_chapter(chapter))
    return tuple(chunks)
```

- [ ] **Step 4 : Lancer le test (succès attendu)**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/chat/test_corpus.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5 : Commit**

```bash
git add src/fahmi2/chat/__init__.py src/fahmi2/chat/corpus.py tests/unit/chat/test_corpus.py
git commit -m "feat(chat): package chat + chunking du consolidé (chunk_consolidated)"
```

---

## Task 7 : `load_corpus_chunks` (consolidé + glossaire)

**Files:**
- Modify: `src/fahmi2/chat/corpus.py`
- Test: `tests/unit/chat/test_corpus.py`

- [ ] **Step 1 : Ajouter le test qui échoue**

Ajouter à `tests/unit/chat/test_corpus.py` :

```python
import json
from pathlib import Path

from fahmi2.chat.corpus import load_corpus_chunks
from fahmi2.domain.enums import Language
from fahmi2.pedagogy.sources import consolidated_doc_path


def test_load_corpus_chunks_consolidated_and_glossary(tmp_path: Path) -> None:
    out_dir = tmp_path / "output"
    out_dir.mkdir()
    consolidated_doc_path(out_dir, Language.FR).write_text(_DOC, encoding="utf-8")
    (tmp_path / "glossary_master.json").write_text(
        json.dumps(
            {
                "terms": [
                    {
                        "term": "Produit intérieur brut",
                        "definition": "Mesure de la richesse produite.",
                        "acronym": "PIB",
                        "acronym_expansion": "Produit Intérieur Brut",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    chunks = load_corpus_chunks(
        generation_output_dir=out_dir,
        generation_dir=tmp_path,
        language=Language.FR,
    )
    glossary = [c for c in chunks if c.origin == "glossary"]
    assert len(glossary) == 1
    assert "PIB" in glossary[0].text
    assert glossary[0].chunk_id == "glossary::produit-intérieur-brut"
    assert any(c.chapter_title == "Bases" for c in chunks)


def test_load_corpus_chunks_empty_when_no_consolidated(tmp_path: Path) -> None:
    chunks = load_corpus_chunks(
        generation_output_dir=tmp_path / "missing",
        generation_dir=tmp_path,
        language=Language.FR,
    )
    assert chunks == ()
```

- [ ] **Step 2 : Lancer le test (échec attendu)**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/chat/test_corpus.py -v`
Expected: FAIL — `ImportError: cannot import name 'load_corpus_chunks'`.

- [ ] **Step 3 : Implémenter dans `src/fahmi2/chat/corpus.py`**

Ajouter les imports en tête (à fusionner avec les imports existants) :

```python
from pathlib import Path

from fahmi2.domain.glossary import Term
from fahmi2.pedagogy.sources import load_chapters, load_glossary_master_terms
```

Ajouter la constante près des autres :

```python
_ORIGIN_GLOSSARY = "glossary"
```

Ajouter les fonctions à la fin du fichier :

```python
def _glossary_chunks(terms: tuple[Term, ...]) -> list[CorpusChunk]:
    """Convertit les termes du glossaire en chunks (un par terme).

    Args:
        terms: Termes du glossaire master.

    Returns:
        Chunks de glossaire.
    """
    chunks: list[CorpusChunk] = []
    for term in terms:
        header_parts = [term.term]
        if term.acronym:
            header_parts.append(f"({term.acronym})")
        if term.acronym_expansion:
            header_parts.append(f"— {term.acronym_expansion}")
        header = " ".join(header_parts)
        slug = slugify_anchor(term.term)
        chunks.append(
            CorpusChunk(
                chunk_id=f"glossary::{slug}",
                chapter_title="Glossaire",
                section_title=term.term,
                anchor=f"glossary-{slug}",
                text=f"{header}\n\n{term.definition}".strip(),
                origin=_ORIGIN_GLOSSARY,
            )
        )
    return chunks


def load_corpus_chunks(
    *,
    generation_output_dir: Path,
    generation_dir: Path,
    language: Language,
) -> tuple[CorpusChunk, ...]:
    """Charge et découpe le corpus interrogeable (consolidé + glossaire).

    Args:
        generation_output_dir: Dossier des livrables (``consolidated.{lang}.md``).
        generation_dir: Dossier de travail génération (``glossary_master.json``).
        language: Langue du corpus.

    Returns:
        Tuple de chunks (consolidé puis glossaire ; vide si aucune source).
    """
    chunks: list[CorpusChunk] = []
    for chapter in load_chapters(generation_output_dir, language):
        chunks.extend(_chunk_chapter(chapter))
    chunks.extend(_glossary_chunks(load_glossary_master_terms(generation_dir)))
    return tuple(chunks)
```

Ajouter l'import `Language` en tête :

```python
from fahmi2.domain.enums import Language
```

- [ ] **Step 4 : Lancer le test (succès attendu)**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/chat/test_corpus.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5 : Commit**

```bash
git add src/fahmi2/chat/corpus.py tests/unit/chat/test_corpus.py
git commit -m "feat(chat): load_corpus_chunks (consolidé + glossaire)"
```

---

## Clôture du Lot 1 — vérifications obligatoires

- [ ] **Suite complète + qualité** (doivent être verts)

```
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m mypy src tests
```

- [ ] **Corriger** tout défaut jusqu'à zéro (repasser autant que nécessaire).
- [ ] **Mettre à jour l'index** ([00-index](2026-05-22-chat-dialogue-00-index.md)) :
  Lot 1 → ✅, puis rédiger le plan du **Lot 2**.

> **Note mypy `--strict`** : si le narrowing pose problème sur `self._matrix`
> (sparse scikit-learn, typé `Any`), c'est volontaire — ne pas remplacer par un
> faux `assert` mutant (cf. convention `CLAUDE.md`).
