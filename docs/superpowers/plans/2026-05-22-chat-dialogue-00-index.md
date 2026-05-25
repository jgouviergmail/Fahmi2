# Chat « Dialogue » — Index des plans d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans
> (exécution **inline**, préférence projet — pas de subagents). Chaque lot a son
> propre fichier de plan et se termine **vert** (`pytest`, `ruff`, `mypy --strict`).

**Goal :** Ajouter un 3ᵉ onglet « Dialogue » : un chat conversationnel ancré sur le
corpus produit par la Génération (document consolidé + glossaire), avec citations,
streaming et fidélité configurable.

**Spec de référence :**
[2026-05-22-chat-dialogue-corpus-design.md](../specs/2026-05-22-chat-dialogue-corpus-design.md)

**Architecture :** Couches dirigées vers le bas (UI → app → chat/infra →
domain/core). Retrieval en **port extensible** (`PassageRetriever`) ; moteur léger
`chat/` calqué sur `pedagogy/` ; streaming additif sur le port `LLMProvider` ;
persistance fichiers sous `<workspace>/chat/`. Zéro nouvelle dépendance.

**Tech Stack :** Python 3.12, PySide6, scikit-learn (TF-IDF, déjà présent), SDK
`openai` (embeddings, déjà présent), DeepSeek V4 (LLM), Jinja2 (prompts).

---

## Lots (séquentiels)

| Lot | Plan | Contenu | Dépend de | Livrable testable |
|---|---|---|---|---|
| 1 ✅ | [lot1-socle](2026-05-22-chat-dialogue-lot1-socle.md) | Domaine chat, `ConversationId`, enums, port `PassageRetriever` + TF-IDF, corpus + **chunking** | — | Domaine + retrieval lexical + chunking, **sans UI ni LLM** |
| 2 ✅ | [lot2-moteur](2026-05-22-chat-dialogue-lot2-moteur.md) | `prompt_builder`, `citations`, `ChatService` (non-streaming), prompts `chat_strict`/`chat_augmented`/`query_expansion`, `ChatSettings` + blob v2, store conversations, garde-fou historique | 1 | Réponse ancrée + citations, **sans UI ni streaming** |
| 3 ✅ | [lot3-streaming](2026-05-22-chat-dialogue-lot3-streaming.md) | `chat_stream` (port + `DeepSeekAdapter` + fake + usage/repli), `ChatService.stream_answer` | 2 | Réponses en flux |
| 4 ✅ | [lot4-ui](2026-05-22-chat-dialogue-lot4-ui.md) | `FeatureId.CHAT`, `ChatTab`, `ChatController`, `ChatViewModel` (machine d'état), `ChatView`, `ChatSettingsView`, DI | 3 | **Chat lexical + streaming de bout en bout** (point de démonstration) |
| 5 ✅ | [lot5-semantique](2026-05-22-chat-dialogue-lot5-semantique.md) | `EmbeddingProvider` + OpenAI + fake, `SemanticPassageRetriever` + index `.npz` + empreinte de validité, résolution `AUTO`, purge, repli | 4 | Retrieval sémantique + cycle de vie de l'index |
| 6 | `lot6-eval-docs` *(à venir)* | Jalon d'évaluation qualité, `docs/`, `README`, `CHANGELOG`, catalogue `PromptsService`, `CLAUDE.md` | 5 | Feature documentée + harnais d'éval |

> Les fichiers de plan des lots 2 à 6 sont rédigés **au fil de l'eau** (un à la fois),
> après revue du lot précédent. Cet index est mis à jour à chaque ajout.

## Conventions transverses (tous les lots)
- **TDD** : test qui échoue → implémentation minimale → test qui passe → commit.
- **Français** partout (code, docstrings, messages, commits), accents corrects.
- **Constantes centralisées**, entités `@dataclass(frozen=True)` + `with_*`,
  helpers privés `_method`, modules internes `_module.py`.
- **Fin de chaque lot** : `pytest`, `ruff check .`, `mypy src tests` **verts**.
- Branche : `feat/chat-dialogue-corpus`.
