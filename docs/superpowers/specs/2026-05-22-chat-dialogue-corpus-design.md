# Dialogue — chat de révision ancré sur le corpus — design détaillé

- **Date** : 2026-05-22
- **Statut** : design (à valider)
- **Périmètre** : cette spec couvre une **nouvelle fonctionnalité (3ᵉ onglet)** :
  un **chat conversationnel** ancré sur le corpus déjà produit par la Génération
  (document **consolidé** + **glossaire**). C'est la **première tranche verticale**
  d'un axe plus large « rendre le corpus interactif et raisonnant » (gisements B
  *restitutions* + C *agentique* du brainstorming) : elle pose le socle réutilisable
  (« corpus interrogeable ») dont hériteront le **tuteur adaptatif** et l'**assistant
  auteur** (hors périmètre, cf. §17). **Ampleur réelle** : un **incrément autonome
  d'ampleur mini-projet** (~10-14 j, ~30 fichiers), pas une simple « tranche
  légère » — découpé en lots verts (cf. §16).
- **Contexte** : l'app est aujourd'hui **génératrice par lot** (lancer → attendre →
  récupérer des fichiers). Le chat introduit un **paradigme conversationnel**
  (session, état, réponse incrémentale) qui réutilise l'infra existante (`QThread`
  worker + `QtEventBus`, port `LLMProvider`, lecture du corpus sur disque,
  abstraction `FeatureTab`, réglages master-detail, override des prompts).
- **Pivot** : la qualité du chat = la qualité du **retrieval** (retrouver les bons
  passages) × la **fidélité** du prompt. Le retrieval est posé comme un **port
  extensible** (lexical par défaut, sémantique optionnel), à l'image des ports
  STT/LLM.

## 1. Objectif & portée

Offrir un onglet **Dialogue** où l'utilisateur pose des questions en langage
naturel et reçoit des réponses **ancrées dans le cours**, **citées**, en **flux
incrémental** (streaming).

**Cas d'usage** : l'étudiant interroge son cours pour réviser ; l'enseignant
retrouve/vérifie un point. Mono-projet (le projet sélectionné dans la sidebar).

### Inclus (v1)
- Onglet **Dialogue** (3ᵉ `FeatureTab`), corpus = **consolidé + glossaire**.
- Retrieval **port extensible**, **défaut adaptatif `AUTO`** (sémantique si clé
  OpenAI présente, sinon lexical TF-IDF offline réutilisant `scikit-learn`), le
  lexical **boosté par une query expansion LLM** déclenchée à la demande.
- Fidélité **configurable** : `STRICT` (citations + refus poli hors-corpus, défaut) /
  `AUGMENTED` (complément de connaissances balisé).
- **Streaming** token-par-token (réponse incrémentale).
- **Conversations multiples** persistées sur disque par projet ; citations
  cliquables ; **coût par message + cumulé** affiché.
- Réglages master-detail ; prompts éditables (`chat_strict.j2` / `chat_augmented.j2`).
- `pytest` + `ruff check .` + `mypy src tests` (`--strict`) **verts**.

### Hors périmètre (YAGNI / extensions futures)
- **Tuteur adaptatif** (l'IA mène la session, modèle de progression) — réutilisera ce socle.
- **Assistant auteur** (outils d'édition, enrichissement web sourcé) — réutilisera ce socle.
- **Indexation des transcriptions per-source** (le corpus v1 est le consolidé + glossaire).
- **Multi-projets / corpus transverse**, partage/export de conversations.
- **Re-ranking** des passages, RAG « agentique » multi-étapes (query rewriting itératif).
- **Embeddings locaux** (modèle à bundler) : écartés au profit d'OpenAI (clé déjà gérée),
  zéro dépendance lourde.

## 2. Décisions verrouillées

1. **Nouvelle fonctionnalité = nouvel onglet** : `FeatureId.CHAT` + `ChatTab`
   enregistré dans le `FeatureRegistry`, **sans toucher** `MainWindow` ni `Project`
   (contrat du chapeau multi-fonctionnalités). Workspace : dossier `chat/`.
2. **Corpus v1** = document **consolidé** (chunké par section) + **glossaire**.
   Langue de contenu résolue via `pedagogy/sources.resolve_content_language`.
3. **Retrieval = port `PassageRetriever`** (nouveau, dans `core/retrieval`, à côté
   de `GlossaryRetriever` — port **distinct**, SRP). Deux implémentations :
   `TfidfPassageRetriever` (offline, sklearn déjà dépendance) et
   `SemanticPassageRetriever` (embeddings OpenAI + index numpy local persisté).
   **Défaut = `AUTO`** : sémantique si une clé OpenAI est présente, sinon lexical.
   Le lexical est **boosté par une *query expansion* LLM** (reformulation de la
   question en mots-clés/synonymes), déclenchée **uniquement si le retrieval initial
   est faible** (meilleur score sous un seuil) → pas d'appel LLM systématique. Objectif
   produit : éviter la **mauvaise première impression** d'un retrieval qui rate les
   paraphrases.
4. **Fidélité configurable** : enum `ChatGroundingMode {STRICT, AUGMENTED}`,
   **`STRICT` par défaut**. Deux prompts dédiés, éditables via `PromptsService`.
5. **Streaming v1** : extension **additive** du port `LLMProvider`
   (`chat_stream`), implémentée dans `DeepSeekAdapter` + `FakeLLMProvider`. Le
   pipeline et la pédagogie (batch) continuent d'utiliser `chat()` → **aucune
   régression**.
6. **Coût en streaming** : **vérifié sur la doc officielle** — DeepSeek V4 supporte
   `stream_options={"include_usage": true}` (chunk d'`usage` final avant `[DONE]`,
   cf. §6.0) → le **coût exact** est conservé en streaming, comme en non-streaming.
   Le repli par estimation de tokens (`CHARS_PER_TOKEN`) devient un simple **filet
   défensif** (futur provider OpenAI-compatible dépourvu d'`usage`), pas le cas nominal.
7. **Conversations** : multiples par projet, **persistées en JSON** sous
   `chat/conversations/{conversation_id}.json`. `ChatSettings` vit dans le blob
   `projects.settings_json` v2 (clé `chat`, lecture **lenient** : absente → défaut,
   pas de bump de version).
8. **Pas de plafond de coût bloquant** (le chat est interactif, piloté message par
   message) ; on **affiche** le coût par message + cumulé.
9. **Zéro nouvelle dépendance** : lexical = `scikit-learn` (déjà là) + `numpy`
   (transitif) ; embeddings = SDK `openai` (déjà présent pour Whisper cloud). Rien
   à bundler de plus dans le `.spec`.

## 3. Modèle de données (`domain`)

### 3.1 Enums (`domain/enums.py`)
```python
class ChatGroundingMode(StrEnum):
    """Posture de fidélité des réponses du chat."""
    STRICT = "strict"        # uniquement le corpus, citations, refus hors-corpus
    AUGMENTED = "augmented"  # corpus prioritaire + complément balisé

class RetrievalStrategy(StrEnum):
    """Stratégie de récupération des passages."""
    AUTO = "auto"            # DÉFAUT : sémantique si clé OpenAI dispo, sinon lexical
    LEXICAL = "lexical"      # TF-IDF (+ query expansion), 100% offline
    SEMANTIC = "semantic"    # embeddings OpenAI
```

### 3.2 `domain/ids.py`
`ConversationId` (ULID typé, comme `RunId`/`ProjectId`).

### 3.3 `domain/chat.py` (nouveau)
> **Rappel d'isolement** : `domain/` ne dépend **ni** d'`infra` **ni** de Qt. Le
> rôle d'un message est donc un type **du domaine** (`ChatRole = Literal["user",
> "assistant"]`), **pas** le `Role` d'`infra/llm` ; la conversion `ChatMessage` →
> `infra/llm.Message` se fait dans `chat/prompt_builder.py` (couche moteur).
```python
ChatRole = Literal["user", "assistant"]  # type du domaine, indépendant d'infra

@dataclass(frozen=True)
class CorpusChunk:
    """Un passage indexable du corpus (section du consolidé ou entrée de glossaire)."""
    chunk_id: str            # stable : ancre slugify de la section, ou "glossary:<terme>"
    chapter_title: str
    section_title: str
    anchor: str              # ancre GFM (slugify_anchor) → citation cliquable
    text: str
    origin: str              # "consolidated" | "glossary"

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
    """Un tour de conversation."""
    role: ChatRole           # "user" | "assistant" (type du domaine, cf. ci-dessus)
    content: str
    citations: tuple[Citation, ...] = ()
    cost_usd: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    created_at: datetime | None = None

@dataclass(frozen=True)
class Conversation:
    """Une conversation persistée, propre à un projet."""
    conversation_id: ConversationId
    title: str               # dérivé de la 1ʳᵉ question (tronquée)
    language: Language       # langue de réponse (défaut = langue de contenu)
    messages: tuple[ChatMessage, ...] = ()
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def with_message(self, message: ChatMessage) -> "Conversation": ...
    def total_cost_usd(self) -> float: ...

@dataclass(frozen=True)
class ChatSettings:
    """Réglages de l'onglet Dialogue (blob v2, clé `chat`)."""
    grounding_mode: ChatGroundingMode = ChatGroundingMode.STRICT
    retrieval_strategy: RetrievalStrategy = RetrievalStrategy.AUTO
    query_expansion_enabled: bool = True      # reformulation LLM si retrieval faible
    model: LLMModel = LLMModel.DEEPSEEK_V4_FLASH
    thinking_enabled: bool = False
    reasoning_effort: ReasoningEffort | None = None
    temperature: float = _DEFAULT_CHAT_TEMPERATURE
    top_k: int = _DEFAULT_TOP_K               # passages injectés (constante centralisée)
    def with_grounding_mode(...) / with_retrieval_strategy(...): ...
```
Constantes (`_DEFAULT_TOP_K`, `_DEFAULT_CHAT_TEMPERATURE`, bornes top-K) **centralisées**.

## 4. Couche retrieval (`core/retrieval` + `infra`)

### 4.1 Port `PassageRetriever` (`core/retrieval/passages.py`, nouveau)
```python
class PassageRetriever(Protocol):
    """Récupère les passages du corpus les plus pertinents pour une question.

    L'implémentation encapsule son corpus/index (construit à l'instanciation pour
    le lexical, chargé/persisté pour le sémantique).
    """
    def retrieve(self, *, query: str, top_k: int) -> list[RetrievedPassage]: ...
```
> Port **distinct** de `GlossaryRetriever` (qui sélectionne des *termes*, pas des
> *passages*) : responsabilités séparées, signatures différentes.

### 4.2 `TfidfPassageRetriever` (`core/retrieval/passages.py`)
Réutilise `TfidfVectorizer` + `cosine_similarity` (pattern de `TfidfGlossaryRetriever`).
Construit la matrice TF-IDF des chunks à l'instanciation (corpus d'un cours = petit,
< quelques milliers de chunks → coût négligeable). `retrieve` vectorise la requête,
classe par cosine décroissant, renvoie les `top_k` meilleurs.
> Choix : **TF-IDF sklearn** (zéro nouvelle dépendance, cohérent avec l'existant)
> plutôt que `rank_bm25`. Évolution possible vers BM25 si la qualité l'exige.

### 4.3 Port `EmbeddingProvider` (`infra/embeddings/interface.py`, nouveau)
```python
class EmbeddingProvider(Protocol):
    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...
    def embed_query(self, text: str) -> list[float]: ...
```
- `OpenAIEmbeddingProvider` (`infra/embeddings/openai_adapter.py`) : SDK `openai`
  (déjà présent), modèle `text-embedding-3-small` (constante), clé via
  `SecretsService`. Coût d'embedding négligeable (cours entier ≈ quelques centimes).
  > **Pourquoi OpenAI et non DeepSeek** : DeepSeek **n'expose pas** d'API
  > d'embeddings (vérifié, cf. §6.0). OpenAI est le choix naturel (clé déjà gérée
  > pour Whisper cloud). Le port `EmbeddingProvider` laisse la porte ouverte à un
  > autre fournisseur si besoin.
- `FakeEmbeddingProvider` (`infra/embeddings/_fakes.py`) : vecteurs déterministes
  (hash → float) pour tests **sans réseau**.

### 4.4 `SemanticPassageRetriever` (`infra/retrieval/semantic.py`, nouveau)
- À la construction : charge l'index persisté (`chat/index.{lang}.npz` : matrice
  d'embeddings + métadonnées chunks) **s'il est frais** (empreinte de validité
  inchangée : `mtime` du consolidé + modèle d'embedding + langue, cf. §10.2) ; sinon
  (ré)embed les chunks via `EmbeddingProvider` et persiste.
- `retrieve` : `embed_query` + cosine **brute-force numpy** (corpus petit → pas de
  base vectorielle exotique, pas de `faiss`).
- **Repli** : si `RetrievalStrategy.SEMANTIC` est demandé mais la clé OpenAI est
  absente → repli automatique sur `TfidfPassageRetriever` + avertissement
  (`CHAT.SEMANTIC_FALLBACK`, WARN), jamais d'échec dur.

### 4.5 Résolution `AUTO` + `QueryExpander` (`chat/retriever_factory.py`, `chat/query_expander.py`)
- **Résolution `AUTO`** (`retriever_factory`) : `AUTO` → `SemanticPassageRetriever`
  si une **clé OpenAI** est configurée **et** qu'un index frais existe (ou peut être
  construit) ; sinon `TfidfPassageRetriever`. `LEXICAL`/`SEMANTIC` forcent le choix.
- **Query expansion** (`QueryExpander`, **décorateur** d'un `PassageRetriever`) :
  lance d'abord le retrieval direct ; si le **meilleur score** est sous un seuil
  (constante), demande au LLM une **reformulation** (mots-clés/synonymes, prompt
  `chat_query_expansion.j2`) puis **relance** le retrieval sur la requête enrichie,
  en **fusionnant** les résultats (dédup par `chunk_id`). Déclenchement **à la
  demande** → pas d'appel LLM systématique. Surtout utile au **lexical** ;
  `query_expansion_enabled=False` le désactive. Coût de l'appel **journalisé**.

## 5. Moteur chat (`chat/`, package nouveau — calqué sur `pedagogy/`)

| Fichier | Rôle |
|---|---|
| `chat/corpus.py` | `load_corpus_chunks(generation_output_dir, glossary_dir, language) -> tuple[CorpusChunk, ...]` : lit le consolidé (réutilise `pedagogy/sources.consolidated_doc_path` + `parse_chapters`), **chunke par section** (titre → `slugify_anchor`, taille bornée par une constante), + entrées de glossaire (`load_glossary_master_terms`). |
| `chat/retriever_factory.py` | `build_passage_retriever(chunks, settings, embedding_provider \| None, llm \| None) -> PassageRetriever` : résout `AUTO`, choisit lexical/sémantique (+ repli §4.4), enveloppe d'un `QueryExpander` si activé (§4.5). |
| `chat/query_expander.py` | décorateur de query expansion LLM (§4.5) |
| `chat/prompt_builder.py` | Assemble les messages : *system* (rendu de `chat_strict.j2`/`chat_augmented.j2` selon `grounding_mode`, avec passages numérotés + glossaire pertinent) + historique de la conversation + question. |
| `chat/citations.py` | `parse_citations(answer, passages) -> tuple[Citation, ...]` : le prompt impose des marqueurs `[§<n>]` référant les passages numérotés ; mappe `n → RetrievedPassage` → `Citation` (anchor cliquable). |
| `chat/chat_service.py` | `ChatService.stream_answer(conversation, question, settings, deps) -> Iterator[ChatStreamEvent]` : retrieve → build prompt → `LLMProvider.chat_stream` → accumulation → `parse_citations` → `ChatMessage` final. Retry (cf. §6) à l'établissement du flux. |
| `chat/events.py` | Événements `EventBus` : `ChatDeltaReceived(content_delta, thinking_delta)`, `ChatAnswerCompleted(message)`, `ChatFailed(error)` (calqué sur `pedagogy/events`). |
| `chat/deps.py` | `ChatDeps` (DI) : `llm_provider`, `embedding_provider \| None`, chemins workspace, `PromptLoader`. |

### 5.1 Stratégie de chunking (`chat/corpus.py`)
Le chunking conditionne la qualité du retrieval — il est donc spécifié :
- **Unité** : une section du consolidé (frontière = titre, via `parse_chapters` +
  `slugify_anchor`). Une entrée de glossaire = un chunk dédié (`origin="glossary"`).
- **Taille cible** : ~`_CHUNK_TARGET_TOKENS` (constante, estimée via
  `CHARS_PER_TOKEN`). Une section plus longue est **redécoupée** aux frontières de
  paragraphe ; une section très courte est **fusionnée** avec la suivante du même
  chapitre (évite les chunks d'une ligne).
- **Chevauchement** : `_CHUNK_OVERLAP` (~10-15 %) entre sous-chunks d'une même
  section (ne pas couper une idée à cheval).
- **Intégrité** : ne **jamais couper** au milieu d'un tableau, d'un bloc de code ou
  d'une admonition (📝/💡/📖/🎯) — ces blocs restent entiers.
- **Métadonnées** par `CorpusChunk` : chapitre, section, ancre, origine → citations
  précises et cliquables.
Toutes les valeurs sont des **constantes centralisées**.

## 6. Streaming (`infra/llm`)

### 6.0 Capacités API DeepSeek vérifiées (doc officielle, mai 2026)
Vérification factuelle préalable (sources : `api-docs.deepseek.com`) — toutes
**alignées** avec l'existant du projet :
- **Modèles réels** : `deepseek-v4-flash` et `deepseek-v4-pro` existent bien
  (preview V4 du 24 avril 2026) → les identifiants de `LLMModel` sont **corrects**.
  Contexte **1M tokens**, sortie max **384K**. `deepseek-chat`/`deepseek-reasoner`
  legacy routent vers v4-flash et **disparaissent le 24/07/2026** (à surveiller hors
  périmètre).
- **Streaming + usage** : `stream=True` (SSE) et `stream_options.include_usage`
  **supportés** → coût exact (cf. §2.6, §6.2).
- **Raisonnement** : `thinking={"type":"enabled"|"disabled"}` (thinking activé par
  défaut côté API) et `reasoning_effort ∈ {"high","max"}` → **identiques** à
  `PhaseConfig`/`ReasoningEffort` ; réponse exposant `reasoning_content` →
  `LLMResponse.thinking_content`. `ChatSettings.thinking_enabled=False` par défaut
  (réponses chat rapides ; activable).
- **Embeddings** : **DeepSeek n'expose AUCUN endpoint `/embeddings`** (seul
  `/chat/completions` est documenté ; demandes GitHub #802/#1124 non satisfaites) →
  le lot 5 passe par **OpenAI** (cf. §4.3), décision factuellement fondée.

### 6.1 Extension du port (`infra/llm/interface.py`)
```python
@dataclass(frozen=True)
class LLMStreamChunk:
    content_delta: str
    thinking_delta: str | None = None
    is_final: bool = False
    response: LLMResponse | None = None   # rempli sur le chunk final (usage + coût)

class LLMProvider(Protocol):
    def chat(...) -> LLMResponse: ...      # inchangé (pipeline/pédagogie)
    def chat_stream(self, *, messages, model, thinking, reasoning_effort=None,
                    temperature, max_tokens=None) -> Iterator[LLMStreamChunk]: ...
    def estimate_cost(...) -> float: ...   # inchangé
```

### 6.2 `DeepSeekAdapter.chat_stream`
`stream=True` + `stream_options={"include_usage": True}`. Accumule séparément
`content` et `reasoning_content` (deltas). Émet un `LLMStreamChunk` par delta non
vide ; sur le chunk d'usage final, construit `LLMResponse` via `_pricing` →
`LLMStreamChunk(is_final=True, response=…)`.
- **Repli usage absent** (provider ne renvoie pas `usage` en stream) : estimer
  `prompt_tokens` (somme des messages) et `completion_tokens`
  (`len(content)/CHARS_PER_TOKEN`) → coût **approché**, marqué comme estimation
  (champ/journal). DeepSeek **renvoie** l'`usage` (cf. §6.0) : ce repli ne sert
  qu'à un éventuel autre provider OpenAI-compatible dépourvu d'`usage`.
- **Retry** : **non implémenté en v1** (ni `chat` ni `chat_stream`). Une erreur
  transitoire (rate limit, réseau) est remontée à l'UI, qui permet de **relancer**
  la question. L'enveloppe `with_retry` à l'établissement du flux est une
  amélioration future (cf. §17).

### 6.3 `FakeLLMProvider.chat_stream`
Découpe une réponse fixe en quelques deltas + chunk final avec `usage` simulé →
tests **déterministes sans réseau**.

## 7. Fidélité & citations (prompts)

- `infra/prompts/defaults/chat_strict.j2` : instruit de répondre **uniquement** à
  partir des passages fournis (numérotés), de **citer** via `[§<n>]`, et de
  répondre « Ce point n'est pas couvert par le cours. » si l'information est
  absente. Glossaire pertinent injecté pour la terminologie.
- `infra/prompts/defaults/chat_augmented.j2` : autorise un complément de
  connaissances générales **balisé** (section « Au-delà du cours »), les citations
  du corpus restant prioritaires.
- Tous deux **éditables** via `PromptsService` + `PromptsEditorDialog` (catalogue
  étendu de **3 entrées** : `chat_strict`, `chat_augmented`, `chat_query_expansion`
  — cf. §4.5), override `%APPDATA%/Fahmi2/prompts/`.

## 8. Persistance & fraîcheur

- **Conversations** : `app/chat_conversation_store.py` (sérialisation domaine ↔
  JSON) — `save`, `load`, `list_for_project`, `delete`. Fichiers sous
  `<workspace>/chat/conversations/{conversation_id}.json` (writes atomiques via
  `fs_artifacts`). Lisibles hors session.
- **`ChatSettings`** : dans le blob `projects.settings_json` v2, clé `chat` ;
  lecture **lenient** (absente → `ChatSettings()` par défaut) — même mécanisme que
  l'ajout de champs à `GenerationSettings`/`PedagogySettings`. Pas de migration de
  schéma SQLite (aucune table touchée).
- **Index sémantique** : `chat/index.{lang}.npz`, invalidé par une **empreinte de
  validité** (mtime du consolidé + modèle d'embedding + langue) ; cycle de vie
  complet (construction, péremption, réinitialisation, réalimentation) en §10.2. Le
  lexical ne persiste rien (reconstruction triviale à l'ouverture).

## 9. Coût

- Par message : `cost_usd` (+ tokens) issu de `LLMStreamChunk` final ; cumulé via
  `Conversation.total_cost_usd()`. Affichés dans l'UI.
- Embeddings : coût d'indexation comptabilisé une fois (lot 5), négligeable.
- Pas de `CostEstimator` pré-run dédié en v1 (le chat est interactif) ; pas de
  plafond bloquant.

## 10. Comportements fonctionnels & cycles de vie (vue produit)

Cette section spécifie *comment la fonctionnalité vit dans le temps* (états,
référentiels, conversations) — au-delà des composants techniques.

### 10.1 États de l'onglet Dialogue (machine UX — portée par le viewmodel)
| État | Ce que voit l'utilisateur | Sortie |
|---|---|---|
| `NO_PROJECT` | Invite à sélectionner / créer un projet | sélection projet |
| `NO_CORPUS` | Bandeau « Lance d'abord une génération » ; saisie désactivée (`CHAT.NO_CORPUS`) | génération produite |
| `INDEX_MISSING` | (sémantique choisi, pas d'index) bandeau + bouton « Construire l'index ». Le **lexical n'a jamais cet état** | indexation lancée |
| `INDEXING` | « Indexation… (n/N passages) », **annulable** | fin / échec |
| `READY` | Prêt à dialoguer | — |
| `STALE` | Corpus régénéré → bandeau « cours mis à jour » (cf. 10.4) ; dialogue possible | réindexation |
| `ANSWERING` | Réponse en streaming, bouton **Arrêter** | fin / arrêt |
| `ERROR` | Message + action de reprise (réseau/clé/retrieval) | nouvelle tentative |

### 10.2 Cycle de vie du référentiel d'embeddings (mode sémantique)
Politique retenue : **hybride** — lexical automatique (gratuit), **sémantique
explicite** (l'utilisateur choisit `SEMANTIC`/`AUTO` dans les réglages).

> **Réalisation v1** : le sémantique est *opt-in par réglage* (`RetrievalStrategy`),
> et l'index est construit **à la volée** au premier message en mode sémantique
> (persisté, réutilisé tant que frais). Le coût d'embedding d'un cours étant
> négligeable, les **contrôles UI explicites** (bouton « Réindexer », confirmation
> modale du coût, état `INDEXING`) et la **journalisation du coût d'indexation** sont
> **différés** (amélioration). La **purge** est disponible (`purge_index`).

- **Construction** : à la volée au premier message en mode sémantique (ou via une
  future commande « Réindexer »). Un **index par langue** (`chat/index.{lang}.npz`).
- **Empreinte de validité** stockée avec l'index : `model` d'embedding + hash des
  réglages d'indexation + `mtime` du consolidé source.
- **Péremption** (état `STALE`) si l'une change : (a) `mtime` du consolidé
  (régénération), (b) **modèle d'embedding** différent, (c) **langue** différente
  (index distinct). Le lexical reste utilisable **immédiatement** en repli.
- **Réalimentation (rebuild)** : reconstruction **tout-ou-rien** (corpus d'un cours
  = petit), **remplacement atomique** du `.npz` (temp + rename via `fs_artifacts`).
- **Réinitialisation / purge** : bouton « Réinitialiser l'index » (réglages) →
  supprime le(s) `.npz` → repasse `INDEX_MISSING`. La **suppression du projet**
  purge `chat/`. Nettoyage documenté.
- **Coût & transparence** : **estimation + confirmation** avant toute (ré)indexation
  sémantique (option « ne plus demander ») ; coût d'indexation **journalisé**.
- **Échec en cours** (réseau/clé) : index partiel **rejeté** (jamais de `.npz`
  corrompu) → reste `INDEX_MISSING`/`STALE` + message ; **repli lexical** disponible
  entre-temps.
- **Sans clé OpenAI** : bascule sémantique **refusée proprement** → repli lexical +
  `CHAT.SEMANTIC_FALLBACK` (WARN) ; bouton d'indexation désactivé + infobulle.

### 10.3 Cycle de vie des conversations
- **Création** : « Nouvelle conversation » ; **titre auto** (1ʳᵉ question tronquée),
  **renommable**.
- **Persistance** : chaque message persiste la conversation
  (`chat/conversations/{id}.json`) → reprise après fermeture de l'app.
- **Suppression** : par conversation ; « Tout supprimer » (projet). La suppression
  du projet purge `chat/` (cf. `on_project_deleted`).
- **Historique long** : politique = **tout conserver** (contexte 1M tokens) ;
  **garde-fou** : au-delà d'un seuil (constante, ~80 % d'un budget de contexte), une
  **fenêtre glissante** élague les tours les plus anciens (**avertissement**
  affiché). Pas de résumé LLM en v1 (YAGNI).
- **Contrôles de tour** : **Arrêter** (interrompt le streaming ; partiel conservé,
  marqué « interrompu »), **Régénérer** la dernière réponse (même question),
  **Copier**. Pas d'édition de question en v1.

### 10.4 Fraîcheur corpus ↔ génération
- Une **nouvelle génération** (consolidé réécrit) **périme l'index** (10.2) et passe
  l'onglet en `STALE`.
- Politique = **conversations figées** : l'historique reste **lisible tel quel**
  (citations historiques conservées) ; **bandeau « cours mis à jour — réindexer pour
  les nouvelles réponses »** ; le **prochain message** s'appuie sur le corpus à jour
  (lexical immédiat ; sémantique après réindexation).
- **Multilingue** : sélecteur de langue si plusieurs `consolidated.{lang}.md` ;
  **un index et un fil par langue de corpus** (changer de langue = nouvelle
  conversation).

### 10.5 Fidélité côté UX
- **Hors-corpus en mode `STRICT`** : « Ce point n'est pas couvert par le cours. » +
  suggestion *« Passez en mode augmenté pour une réponse au-delà du cours »*
  (**sans** bascule automatique).
- **Citations cliquables** : ouvre le **passage source** (aperçu chapitre/section
  dans un panneau, ancré via `slugify_anchor`).
- **Affichage pendant le streaming** : les marqueurs `[§n]` du flux ne sont **pas
  montrés bruts** ; le texte s'affiche proprement au fil de l'eau et les citations
  sont **résolues en fin de réponse** en **puces cliquables** (renvois discrets en
  exposant si pertinent) → pas de *flicker* de marqueurs.
- **Citations périmées** : ancre absente du corpus courant (régénéré) → citation
  **non cliquable** + infobulle « passage modifié depuis cette réponse ». Jamais
  d'erreur.
- **Raisonnement** : si `thinking_enabled`, la trace (`reasoning_content`) est
  affichée dans un **bloc repliable** distinct de la réponse.

### 10.6 Coût & garde-fous
- **Affichage** : coût **par message**, **cumulé par conversation**
  (`total_cost_usd`), coût d'**indexation** séparé.
- **Garde-fous** (pas de plafond bloquant) : **confirmation** avant une
  (ré)indexation sémantique payante (10.2) ; **avertissement** au déclenchement de
  l'élagage d'historique (10.3).

### 10.7 Confidentialité & données (ADN local-first)
- **Lexical** : aucun envoi pour le retrieval (100 % local) ; seule la **réponse**
  appelle DeepSeek (comme tout le LLM du produit).
- **Sémantique** : **corpus** + **questions** envoyés à **OpenAI** pour embedding →
  **avertissement de transparence** à l'activation (cohérent avec Whisper cloud qui
  envoie déjà l'audio).
- Aucune télémétrie ; conversations et index restent **sous le workspace du projet**.

## 11. UI (`ui/`)

| Élément | Rôle |
|---|---|
| `FeatureId.CHAT` (`features/feature.py`) | + valeur d'enum |
| `features/chat_tab.py` (`ChatTab`) | onglet « Dialogue » ; `on_project_selected` charge conversations + corpus |
| `ui/chat_controller.py` | worker `QThread` consommant `ChatService.stream_answer` ; pont via `QtEventBus` (signal par delta + signal final) ; distinction projet affiché / projet actif (cf. `GenerationController`) |
| `ui/viewmodels/chat_view_model.py` | état conversation + formatage + **machine d'état `ChatTabState`** (§10.1), **sans Qt**, testable |
| `ui/widgets/chat_view.py` | fil de bulles (append incrémental des deltas), saisie, citations cliquables/**périmées** (§10.5), coût message + cumulé, liste des conversations, **contrôles** Arrêter/Régénérer (§10.3), **bandeaux d'état** (§10.1/10.4) |
| `ui/dialogs/chat_settings_view.py` | `SettingsView` master-detail (fidélité, modèle, stratégie retrieval, top-K, thinking, température) + **gestion de l'index** : Construire/Réindexer/Réinitialiser, statut de fraîcheur, confirmation de coût (§10.2) |
| `ui/qt_event_bus.py` | `ChatQtEventBus` (EventBus → Signal Qt) si besoin d'un bus dédié |
| `ui/app_main.py` | DI complet : enregistrement du `ChatTab` dans le `FeatureRegistry` |

Bandeau si **aucun consolidé** (`CHAT.NO_CORPUS`) : « Lance d'abord une génération
pour dialoguer avec ce cours. » Sélecteur de langue de corpus si plusieurs
`consolidated.{lang}.md` existent (défaut = `resolve_content_language`).

## 12. Erreurs (`core/errors`)

| Code | Sévérité | Sens |
|---|---|---|
| `CHAT.NO_CORPUS` | ERROR | Aucun `consolidated.{lang}.md` pour ce projet |
| `CHAT.SEMANTIC_FALLBACK` | WARN | Stratégie sémantique demandée sans clé OpenAI → repli lexical |
| `CHAT.EMBEDDING_FAILED` | ERROR | Échec d'appel embeddings (réseau/clé) |
| `CHAT.RETRIEVAL_FAILED` | ERROR | Échec de construction d'index / récupération |

Hiérarchie `ChatError(Fahmi2Error)` + messages FR (`core/errors/messages.py`). Les
échecs LLM de `chat_stream` remontent en `LLMError` existant. Toute erreur est une
`Fahmi2Error` → exposée dans les logs.

## 13. Dépendances & packaging
- **Aucune nouvelle dépendance** : `scikit-learn`/`numpy` (déjà là) pour le lexical
  et le cosine ; SDK `openai` (déjà là) pour les embeddings.
- `.spec` : **rien à ajouter** (pas de modèle local, pas de binaire). Le seul
  artefact runtime nouveau est l'index `.npz` (écrit sous le workspace projet).

## 14. Tests

- **domain** : `Conversation.with_message`/`total_cost_usd` ; sérialisation
  conversation ↔ JSON (round-trip).
- **corpus** : `load_corpus_chunks` sur un consolidé fixture → chunks par section,
  ancres `slugify_anchor` correctes, entrées de glossaire incluses.
- **lexical** : `TfidfPassageRetriever` retrouve le passage attendu sur corpus
  fixture (question paraphrasée vs mot-clé).
- **sémantique** : `SemanticPassageRetriever` avec `FakeEmbeddingProvider` →
  ordre attendu ; **index persisté** + **invalidation par mtime** ; **repli**
  sans clé → `SEMANTIC_FALLBACK` + résultats lexicaux.
- **chat_service** : `FakeLLMProvider.chat_stream` → `ChatMessage` final avec
  **citations parsées** ; mode `STRICT` → le fake renvoyant « non couvert » produit
  une réponse sans citation ; historique transmis.
- **streaming adapter** : `DeepSeekAdapter.chat_stream` (SSE mocké) → accumulation
  content/reasoning, usage final → coût ; **repli estimation** si usage absent.
- **viewmodel** : `ChatViewModel` sans Qt (append deltas, finalisation, coût cumulé).
- **smoke pytest-qt** : `ChatView` (append incrémental, clic citation).
- **store** : `chat_conversation_store` save/load/list/delete.
- **blob v2** : lecture **lenient** (clé `chat` absente → `ChatSettings()` défaut).
- **cycle de vie index** (§10.2) : empreinte de validité → péremption sur
  changement de **mtime** / **modèle d'embedding** / **langue** ; **rejet d'index
  partiel** sur échec (aucun `.npz` corrompu écrit) ; **purge** → `INDEX_MISSING`.
- **garde-fou historique** (§10.3) : au-delà du seuil, fenêtre glissante élague les
  tours anciens + avertissement ; sinon tout conservé.
- **machine d'état** (`ChatTabState`, §10.1) : transitions `NO_CORPUS → READY →
  STALE`, `INDEX_MISSING → INDEXING → READY`, arrêt → message partiel « interrompu ».
- **citations périmées** (§10.5) : ancre absente du corpus courant → citation non
  cliquable, sans erreur.
- **résolution `AUTO`** (§4.5) : clé OpenAI présente → sémantique ; absente → lexical.
- **query expansion** (§4.5) : score faible → reformulation LLM (fake) → fusion
  dédupliquée ; score fort → **pas** d'appel LLM.
- **chunking** (§5.1) : tableaux/admonitions non coupés ; redécoupage/fusion aux
  bornes ; chevauchement appliqué.
- `pytest`, `ruff check .`, `mypy src tests` **verts**.

### 14.1 Jalon d'évaluation de la qualité (non bloquant)
Harnais d'évaluation distinct de la suite unitaire (le LLM réel n'est pas
déterministe) : un **jeu de Q/R de référence** sur un cours fixture mesure le
**rappel du retrieval** (le passage attendu est-il dans le top-K ?) et permet une
**revue qualitative** des réponses (strict/augmenté). Lançable à la demande ; sert
de **garde-fou avant d'élargir** et de **base de non-régression** lors des
changements de chunking, de seuils ou de prompts.

## 15. Découpage des responsabilités (fichiers)

| Fichier | Rôle | Action |
|---|---|---|
| `domain/enums.py` | `ChatGroundingMode`, `RetrievalStrategy` | Modifier |
| `domain/ids.py` | `ConversationId` | Modifier |
| `domain/chat.py` | entités chat + `ChatSettings` | Créer |
| `core/retrieval/passages.py` | port `PassageRetriever` + `TfidfPassageRetriever` | Créer |
| `infra/embeddings/interface.py` | port `EmbeddingProvider` | Créer |
| `infra/embeddings/openai_adapter.py` | `OpenAIEmbeddingProvider` | Créer |
| `infra/embeddings/_fakes.py` | `FakeEmbeddingProvider` | Créer |
| `infra/retrieval/semantic.py` | `SemanticPassageRetriever` + index `.npz` | Créer |
| `chat/corpus.py` | chargement + chunking du corpus | Créer |
| `chat/retriever_factory.py` | choix lexical/sémantique + repli | Créer |
| `chat/prompt_builder.py` | assemblage des messages | Créer |
| `chat/citations.py` | parsing des citations | Créer |
| `chat/chat_service.py` | orchestration streaming | Créer |
| `chat/events.py`, `chat/deps.py` | events + DI | Créer |
| `infra/llm/interface.py` | `chat_stream` + `LLMStreamChunk` | Modifier |
| `infra/llm/deepseek_adapter.py` | implémentation streaming + usage/repli | Modifier |
| `infra/llm/_fakes.py` | `FakeLLMProvider.chat_stream` | Modifier |
| `infra/prompts/defaults/chat_strict.j2`, `chat_augmented.j2`, `chat_query_expansion.j2` | prompts (fidélité + query expansion §4.5) | Créer |
| `app/prompts_service.py` | catalogue + 2 entrées chat | Modifier |
| `app/chat_conversation_store.py` | persistance conversations | Créer |
| `domain/project.py` / settings blob | clé `chat` (lenient) | Modifier |
| `ui/features/feature.py` | `FeatureId.CHAT` | Modifier |
| `ui/features/chat_tab.py` | `ChatTab` | Créer |
| `ui/chat_controller.py` | worker + pont events | Créer |
| `ui/viewmodels/chat_view_model.py` | viewmodel sans Qt | Créer |
| `ui/widgets/chat_view.py` | vue conversationnelle | Créer |
| `ui/dialogs/chat_settings_view.py` | réglages master-detail | Créer |
| `ui/qt_event_bus.py` | `ChatQtEventBus` | Modifier |
| `ui/app_main.py` | DI + enregistrement onglet | Modifier |
| `core/errors/*` | `ChatError` + codes + messages FR | Modifier |
| `tests/**` | fakes + tests §14 | Créer/Modifier |
| `docs/`, `CLAUDE.md`, `README.md`, `CHANGELOG` | doc transverse | Modifier |

## 16. Lots d'implémentation (incrément autonome — ampleur mini-projet)

1. **Socle domaine + corpus + retrieval lexical** : enums, `domain/chat`,
   `ConversationId`, `chat/corpus.py` (**chunking §5.1**), port `PassageRetriever` +
   `TfidfPassageRetriever`. Testable, sans UI ni LLM.
2. **Moteur chat (non-streaming d'abord) + prompts + fidélité + persistance** :
   `prompt_builder` (+ **garde-fou historique** §10.3), `citations`, `ChatService`
   branché sur `chat()` existant, `chat_strict.j2`/`chat_augmented.j2`,
   `ChatSettings` + blob v2, `chat_conversation_store` (cycle de vie conversations
   §10.3), **`query_expander` + `chat_query_expansion.j2`** (§4.5, chemin lexical).
   Testable sans UI ni streaming.
3. **Streaming** : `chat_stream` (port + `DeepSeekAdapter` + `FakeLLMProvider` +
   usage/repli), bascule de `ChatService` sur le flux + `events`.
4. **UI** : `FeatureId.CHAT`, `ChatTab`, `ChatController` (worker `QThread`),
   `ChatViewModel` (**machine d'état** `ChatTabState` §10.1), `ChatView` (deltas +
   citations cliquables/**périmées** §10.5 + coût + **contrôles** Arrêter/Régénérer
   §10.3 + **bandeaux d'état** §10.1/10.4), `ChatSettingsView`, DI `app_main`. →
   **chat lexical + streaming fonctionnel de bout en bout**.
5. **Sémantique optionnel + cycle de vie de l'index** : port `EmbeddingProvider` +
   `OpenAIEmbeddingProvider` + fake, `SemanticPassageRetriever` + index `.npz` +
   **empreinte de validité** ; **(ré)indexation explicite + confirmation de coût**,
   **réinitialisation/purge**, **rejet d'index partiel**, **résolution `AUTO`**
   (§4.5), bascule de stratégie + **repli sans clé** (§10.2).
6. **Évaluation, docs & finitions** : **jalon d'évaluation qualité** (§14.1), puis
   `docs/` (présentations, guide), `README`, `CHANGELOG`, catalogue `PromptsService`,
   `CLAUDE.md`.

> Les **6 lots sont les étapes successives d'une seule réalisation** : le retrieval
> sémantique (lot 5) et les finitions/docs (lot 6) **font partie du livrable**, ils
> ne sont pas optionnels ni « hors MVP ». Le retrieval sémantique reste *optionnel à
> l'exécution* (choix de réglage `RetrievalStrategy`), mais sa **réalisation** est
> due. Chaque lot se termine **vert** (`pytest`/`ruff`/`mypy --strict`) et laisse le
> tronc fonctionnel : après le lot 4, le chat tourne déjà (lexical + streaming),
> offrant un **point de démonstration intermédiaire** — le périmètre ne s'y arrête pas.

## 17. Limites connues (assumées)
- **Qualité du retrieval lexical** : rate les paraphrases sans vocabulaire commun ;
  mitigé par l'injection du glossaire et par la bascule sémantique optionnelle.
- **Fiabilité des citations** : dépend du respect du format `[§<n>]` par le LLM ;
  parsing **tolérant** (citation non reconnue ignorée, réponse conservée).
- **Coût en streaming** : DeepSeek V4 renvoie l'`usage` exact (`include_usage`,
  vérifié §6.0) → coût exact. L'estimation (§6.2) n'intervient que pour un futur
  provider OpenAI-compatible sans `usage`.
- **Retry** : pas de retry automatique en v1 (chat ni streaming) ; une erreur
  transitoire est remontée à l'UI qui permet de relancer la question. L'enveloppe
  `with_retry` (établissement du flux) reste une amélioration future.
- **Mono-langue par conversation** : le corpus est indexé pour une langue de
  contenu ; changer de langue = nouvelle conversation / ré-index.
- **Corpus v1 = consolidé + glossaire** : le détail des transcriptions per-source
  n'est pas interrogeable (extension future).
- **Hallucination en mode `AUGMENTED`** : assumée et balisée ; `STRICT` reste le
  défaut.
