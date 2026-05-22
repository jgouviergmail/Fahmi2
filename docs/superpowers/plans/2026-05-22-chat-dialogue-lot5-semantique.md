# Chat « Dialogue » — Lot 5 : Retrieval sémantique (embeddings) + résolution AUTO

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans
> (exécution **inline**).

**Goal :** Activer le retrieval sémantique : port `EmbeddingProvider` (+ OpenAI +
fake), `SemanticPassageRetriever` avec index `.npz` persisté + **empreinte de
validité** (modèle + mtime + langue), `retriever_factory` résolvant `AUTO`
(sémantique si clé OpenAI, sinon lexical) avec **repli** propre, branché dans le
`ChatController`.

**Architecture :** Index numpy local (cosine brute-force, corpus petit). Écriture
atomique via `FsArtifactStore`. Embeddings OpenAI (`text-embedding-3-small`).
Zéro nouvelle dépendance (numpy via scikit-learn, SDK openai déjà présents).

**Tech Stack :** numpy, openai, Lots 1-4.

**Interpréteur :** `.venv\Scripts\python.exe`. **Commits :** footer Co-Authored-By.

**Référence spec :** §4.3/§4.4 (embeddings + sémantique), §4.5 (résolution AUTO),
§6.0 (DeepSeek sans embeddings → OpenAI), §10.2 (cycle de vie de l'index).

**Périmètre Lot 5 :** cœur sémantique fonctionnel + résolution AUTO + repli +
empreinte de validité (péremption sur mtime/modèle/langue) + **purge** (suppression
de l'index). L'indexation se fait **à la volée** à la construction du retriever
(persistée, réutilisée si fraîche) ; coût d'embedding **journalisé**. Les contrôles
UI explicites (bouton « Réindexer », confirmation modale, états `INDEXING`) sont une
amélioration **différée** — le coût d'indexation d'un cours est négligeable et
l'index est mis en cache. *(Aligner la spec §10.2.)*

---

## Task 1 : Port `EmbeddingProvider` (+ fake + OpenAI)

**Files:** `src/fahmi2/infra/embeddings/__init__.py`,
`interface.py`, `_fakes.py`, `openai_adapter.py`,
`tests/unit/infra/embeddings/test_fake_embeddings.py`

- `EmbeddingProvider(Protocol)` : `embed_documents(texts) -> list[list[float]]`,
  `embed_query(text) -> list[float]`.
- `FakeEmbeddingProvider` : vecteurs déterministes (hash → floats bornés), **sans
  réseau** — pour tests.
- `OpenAIEmbeddingProvider` : SDK `openai` (`OpenAI(api_key=...)`), modèle
  `text-embedding-3-small`, `client.embeddings.create(model, input=texts)`.

- [ ] Test fake : `embed_documents` renvoie N vecteurs de même dimension ;
  déterministe ; `embed_query` cohérent.
- [ ] Commit — `feat(chat): port EmbeddingProvider (+ fake + OpenAI)`

## Task 2 : `SemanticPassageRetriever` + index `.npz` + empreinte

**Files:** `src/fahmi2/infra/retrieval/__init__.py`, `semantic.py`,
`tests/unit/infra/retrieval/test_semantic_retriever.py`

- `build_index_fingerprint(*, model, source_mtime_ns, language) -> str` (JSON trié).
- `SemanticPassageRetriever(PassageRetriever)` :
  - `__init__(*, chunks, embedding_provider, index_path, fingerprint, artifacts)` :
    charge l'index `.npz` si présent **et** empreinte identique **et** nb de chunks
    cohérent ; sinon (ré)embed les chunks et **persiste** (écriture atomique).
  - `retrieve(query, top_k)` : `embed_query` + cosine numpy → top-K `RetrievedPassage`.
  - **Échec d'indexation** : aucune écriture partielle (embed puis save en une fois).
- `purge_index(index_path)` : supprime l'index (idempotent).

- [ ] Tests (`FakeEmbeddingProvider`) : retrieval ordonne par similarité ;
  **réutilisation** si empreinte identique (pas de ré-embed — provider compté) ;
  **péremption** si empreinte change (mtime/modèle) → ré-embed ; purge supprime.
- [ ] Commit — `feat(chat): SemanticPassageRetriever + index .npz + empreinte`

## Task 3 : `retriever_factory` (résolution AUTO + repli) + branchement

**Files:** `src/fahmi2/chat/retriever_factory.py`, `src/fahmi2/ui/chat_controller.py`,
`tests/unit/chat/test_retriever_factory.py`

- `build_passage_retriever(*, chunks, settings, prompts, llm, embedding_provider,
  index_path, source_mtime_ns, language, artifacts) -> PassageRetriever` :
  1. résout la stratégie : `AUTO` → sémantique si `embedding_provider` non `None`,
     sinon lexical ; `SEMANTIC` sans provider → **repli lexical** ; `LEXICAL` → lexical.
  2. construit le retriever de base (sémantique ou `TfidfPassageRetriever`).
  3. enveloppe d'un `QueryExpander` si `settings.query_expansion_enabled` **et** base
     lexicale (le sémantique n'en a pas besoin).
- `ChatController` : construit un `OpenAIEmbeddingProvider` si `has_openai_key()`,
  calcule `source_mtime_ns` (`pedagogy.sources.source_mtime_ns`) + `index_path`
  (`chat/index.{lang}.npz`), et délègue à `build_passage_retriever` (remplace
  `_build_retriever`).

- [ ] Tests : `AUTO` + provider → sémantique ; `AUTO` sans provider → lexical ;
  `SEMANTIC` sans provider → lexical (repli) ; lexical + expansion → `QueryExpander`.
- [ ] Commit — `feat(chat): retriever_factory (résolution AUTO + repli) + ChatController`

---

## Clôture du Lot 5 — vérifications + revue
- [ ] `pytest`, `ruff check .`, `mypy src tests` **verts**.
- [ ] **Revue approfondie** (9 points) : pas de magic value (epsilon, modèle) ;
  index atomique ; repli sans clé propre ; numpy typé `Any` documenté.
- [ ] Aligner **spec §10.2** (indexation à la volée v1, contrôles explicites différés).
- [ ] **Index** : Lot 5 → ✅, puis plan du **Lot 6**.
