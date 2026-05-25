# Chat « Dialogue » — Lot 6 : Jalon d'évaluation qualité + documentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans
> (exécution **inline**).

**Goal :** Verrouiller la qualité du retrieval par un **jalon d'évaluation**
(recall déterministe, non-régression) et documenter la fonctionnalité Dialogue.

**Interpréteur :** `.venv\Scripts\python.exe`. **Commits :** footer Co-Authored-By.

**Référence spec :** §14.1 (jalon d'évaluation), §1/§10/§11 (doc).

---

## Task 1 : Jalon d'évaluation du retrieval (recall déterministe)

**Files:** `tests/unit/chat/test_retrieval_recall.py`

Harnais déterministe (lexical, sans LLM) : un corpus fixture multi-chapitres + un
**jeu de Q/R de référence** ``(question, ancre attendue)`` ; mesure ``recall@k``
(le passage attendu est-il dans le top-K ?). Sert de **garde-fou de non-régression**
sur le chunking et le retrieval.

- `_recall_at_k(retriever, cases, k) -> float`.
- Assertion : `recall@3 == 1.0` sur le jeu de référence (lexical TF-IDF).

- [ ] Commit — `test(chat): jalon d évaluation du retrieval (recall lexical)`

## Task 2 : Documentation

**Files:** `README.md`, `CHANGELOG.md`, `docs/01-presentation-fonctionnelle.md`,
`docs/02-presentation-technique.md`, `CLAUDE.md`

- `README.md` : ajouter « Dialogue » aux capacités (3ᵉ onglet, chat ancré + citations
  + streaming, retrieval lexical/sémantique). Statut.
- `CHANGELOG.md` : entrée « Dialogue (chat RAG sur corpus) ».
- `docs/01-presentation-fonctionnelle.md` : §4 fonctionnalité Dialogue (usage,
  fidélité strict/augmenté, citations, conversations).
- `docs/02-presentation-technique.md` : package `chat/` + `core/retrieval/passages`
  + `infra/embeddings`/`infra/retrieval` + `ui` (ChatTab/Controller/View/ViewModel).
- `CLAUDE.md` : mentionner le 3ᵉ onglet, le package `chat/`, les ports
  `PassageRetriever`/`EmbeddingProvider`, le streaming `chat_stream`.

- [ ] Commit — `docs(chat): documentation de la fonctionnalité Dialogue`

---

## Clôture du Lot 6 — vérifications
- [ ] `pytest`, `ruff check .`, `mypy src tests` **verts**.
- [ ] **Index** : Lot 6 → ✅.
