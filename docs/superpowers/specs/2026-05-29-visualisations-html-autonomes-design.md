# Fonctionnalité « Visualisations » — cartes de connaissances & schémas HTML autonomes — design

- **Date** : 2026-05-29
- **Statut** : **spec rédigée — en attente de revue utilisateur** (brainstorming terminé,
  langage visuel validé en maquette haute-fidélité)
- **Origine** : demande utilisateur — produire, à partir des livrables de la
  Génération, (A) une **carte de connaissances interactive** (termes, concepts,
  idées, enchaînements, exemples) et (B) un **tableau de schémas/diagrammes**, sous
  forme de **pages HTML pleinement autonomes**.
- **Prérequis** : une génération aboutie (consolidé + glossaire sur disque). Réutilise
  les acquis : glossaire **réconcilié** (phase 2), `EmbeddingProvider` (Dialogue),
  parser de sections (relocalisé en `core/corpus`, §11), `slugify_anchor` (core).

---

## 1. Intention & périmètre

On ajoute une **4ᵉ fonctionnalité** (onglet « Visualisations »), sœur de
Génération / Pédagogie / Dialogue, qui **relit le disque** et produit **2 livrables
HTML autonomes par langue** :

- **Document A — Carte de connaissances** : un **graphe interactif** de tout le
  corpus (concepts, termes du glossaire, idées, exemples) relié par des **relations
  typées** (enchaînements). Vue **réseau** par défaut ; **clic sur un nœud →
  réorganisation en arbre** centré sur ce nœud, et retour. Communautés thématiques
  **repliables**. Recherche, filtres par type, panneau latéral (définition + extrait
  source embarqué + relations).
- **Document B — Schémas & diagrammes** : une **galerie de diagrammes** générés
  depuis le contenu (processus/flowchart, chronologie, comparaison, hiérarchie/
  organigramme, cycle, arbre de décision), chacun avec titre, légende, renvoi de
  chapitre et extrait source.

**Décisions de cadrage validées (brainstorming) :**

1. **Déclenchement** : à la demande, **modèle Pédagogie** (orchestrateur léger, lit
   le disque, manifeste de fraîcheur, `run_state.json`, onglet dédié). Découplé de la
   Génération.
2. **Multilingue (option « structure une fois + libellés localisés »)** : la
   structure coûteuse (graphe, modèles de diagrammes) est extraite **une seule fois**
   (langue source) ; elle est **invariante par langue** ; seuls les **libellés** sont
   traduits par langue (réutilise `cross_lang` du glossaire + une passe de traduction
   de libellés). Philosophie identique à la localisation du glossaire (phase 6).
3. **Langues** : **scripts latins uniquement** — `fr`, `en`, `de`, `es`, `it`. Le
   **chinois et l'arabe sont volontairement écartés de cette fonctionnalité**
   (décision produit : ne pas brider le rendu par les contraintes RTL/CJK). Si un
   projet a produit `zh`/`ar`, la feature **ignore** ces langues et produit pour les
   langues latines présentes. Cela ne retire pas `zh`/`ar` du reste de l'application.
4. **Autonomie** : chaque livrable est **un fichier `.html` unique**, tout embarqué
   (CSS + JS vendorisé + données JSON + extraits sources), **ouvrable par double-clic,
   sans réseau**. Aucune référence externe (garde-fou de test).
5. **Navigation source** : les **extraits sources** sont **embarqués** dans le HTML
   (affichés au clic dans le panneau latéral), tirés du `consolidated.{lang}.md` de la
   bonne langue — aucune dépendance à un fichier externe.
6. **Moteur de rendu unique, zéro DSL** (cf. §6) : **le LLM n'émet jamais de langage
   de rendu**, seulement du **JSON typé** ; tout le rendu est déterministe (Python →
   données + **Cytoscape.js** pour les graphes, **HTML/CSS** pour les diagrammes
   linéaires). Mermaid est **écarté** (réintroduit une étape de parsing DSL non
   validable à l'exécution dans l'app portable + bugs CJK/RTL).
7. **Densité** : curseur **peu / moyen / beaucoup** réutilisant l'enum
   **`SupportDensity`** de la Pédagogie (DRY).

**Exigence transverse — excellence de rendu** : la stylisation doit être **soignée et
travaillée** (exigence forte de l'utilisateur). La maquette haute-fidélité validée
(cf. §6.4) est la **référence**. L'implémentation du rendu sera guidée par le skill
`frontend-design`.

---

## 2. Principe directeur : « squelette déterministe + couche sémantique LLM »

L'erreur serait soit d'être **simpliste** (graphe de co-occurrence plat), soit de
**sur-ingénierer** (réconciliation globale coûteuse). On vise l'élégance via une
**division du travail** inspirée de **GraphRAG** (Microsoft) mais adaptée aux acquis
de Fahmi2 :

- **Le squelette est déterministe et gratuit** : les **termes** viennent du glossaire
  **déjà réconcilié** (phase 2) ; les **chapitres / ancres** viennent du sommaire du
  consolidé. On n'**extrait pas** ce qu'on possède déjà.
- **Le LLM ne fait que la couche sémantique** que lui seul peut produire : concepts,
  idées, **relations typées** (enchaînements), exemples, et le **choix/contenu** des
  diagrammes.
- **La cohérence inter-chapitres émerge** de la **résolution d'entités** (une entité
  vue dans deux chapitres devient **un seul nœud** qui les relie) + une **détection de
  communautés** déterministe (Louvain) qui regroupe ce qui va ensemble **par-delà**
  l'ordre des chapitres — et fournit **du même coup** la hiérarchie repliable qui rend
  le graphe lisible à grande échelle.

Un seul mécanisme (communautés) résout donc **la cohérence transversale** *et* **la
lisibilité à l'échelle**.

**Alignement sur le pipeline GraphRAG canonique** (standard du marché) : extraction par
**unité de texte** + **gleaning** (passe de rappel) → **consolidation des descriptions**
(résolution d'entités) → **communautés** Louvain hiérarchiques → **community reports**
(résumés bottom-up) → **map-reduce** pour le raisonnement transversal. Fahmi2 y greffe
ses acquis (glossaire réconcilié comme colonne vertébrale, `EmbeddingProvider`,
`slugify_anchor`). Les *community reports* sont **à double usage** : étiquette lisible des
communautés (UI) **et** unité de raisonnement des enchaînements inter-communautés.

---

## 3. Modèle de données (domain)

### 3.1 Enums (`domain/enums.py`)

- `class NodeType(StrEnum)` : `CONCEPT = "concept"`, `GLOSSARY_TERM = "glossary_term"`,
  `EXAMPLE = "example"`, `IDEA = "idea"`.
- `class EdgeType(StrEnum)` : `LEADS_TO` (cause→effet/mène à), `PREREQUISITE`
  (prérequis), `ILLUSTRATES` (illustre), `CONTRASTS_WITH` (s'oppose à),
  `PART_OF` (composé de/partie de), `RELATED` (lié à).
- `class DiagramType(StrEnum)` : `FLOWCHART`, `TIMELINE`, `COMPARISON`, `HIERARCHY`,
  `CYCLE`, `DECISION_TREE`.
- Réutilise **`SupportDensity`** (existant) pour la densité.

Chaque enum porte des **libellés FR gelés** dédiés (pour les prompts LLM), à l'image
de `pedagogy/labels.py` ; les variantes UI traduites passent par `ui/` (cf. §9).

### 3.2 Entités immuables (`domain/visuals.py`, `@dataclass(frozen=True)`)

- `SourceExcerpt` : `text: str`, `section_path: tuple[int, ...]` (chemin structurel
  **invariant par langue**, ex. `(2,1,1)`), `chapter_title: str`, `anchor: str` (ancre
  GFM **de la langue rendue**) — calqué sur le « grand livre des faits » T1 de la
  consolidation thématique.
- `GraphNode` : `id: str` (**stable et unique** :
  `f"{node_type}:{slugify_anchor(label)}"` + compteur de désambiguïsation en cas de
  collision — cf. §13), `label: str`,
  `node_type: NodeType`, `definition: str | None`, `excerpts: tuple[SourceExcerpt, ...]`,
  `chapter_anchor: str | None`, `community_path: tuple[int, ...]` (chemin dans la
  hiérarchie de communautés, rempli par Louvain).
- `GraphEdge` : `source_id: str`, `target_id: str`, `edge_type: EdgeType`,
  `label: str | None`.
- `KnowledgeGraph` : `nodes: tuple[GraphNode, ...]`, `edges: tuple[GraphEdge, ...]`,
  `communities: tuple[Community, ...]`, `language: Language`.
- `Community` : `id: int`, `label: str`, `report: str` (synthèse courte + idée-clé —
  **double usage** UI/raisonnement), `level: int`, `member_ids: tuple[str, ...]`,
  `parent_id: int | None`.
- Diagrammes (modèles **typés**, jamais de DSL) :
  - `DiagramNode` (`id`, `label`, `role: str | None`), `DiagramLink` (`from_id`,
    `to_id`, `label: str | None`).
  - `TimelineEvent` (`date_label: str`, `title: str`, `detail: str | None`),
    `ComparisonTable` (`columns: tuple[str, ...]`, `rows: tuple[tuple[str, ...], ...]`).
  - `Diagram` : `id: str`, `title: str`, `diagram_type: DiagramType`, **+ une charge
    utile typée selon le type** : types « graphe » (`FLOWCHART`/`HIERARCHY`/
    `DECISION_TREE`/`CYCLE`) → `nodes: tuple[DiagramNode, ...]` +
    `links: tuple[DiagramLink, ...]` ; `TIMELINE` → `events: tuple[TimelineEvent, ...]` ;
    `COMPARISON` → `comparison: ComparisonTable`. Plus `caption: str`,
    `chapter_anchor: str`, `excerpts: tuple[SourceExcerpt, ...]`. Les champs non
    pertinents pour le type sont vides ; cohérence **validée en `__post_init__`**.
  - `DiagramBoard` : `diagrams: tuple[Diagram, ...]`, `language: Language`.

Les entités sont **pures** (aucun import Qt/HTTP/SQL), validées dans `__post_init__`.

---

## 4. Pipeline de construction (orchestrateur `visuals/`)

Paquet `visuals/` (modelé sur `pedagogy/`, sans STT/SQLite). Le pipeline **calque les
phases canoniques de GraphRAG** (cf. §2). Toutes les sorties LLM sont du **JSON typé**
(parsé via le `_base` Pédagogie + retry `core/retry/classification.default_classify`) :

1. **Chargement (`visuals/sources.py`)** : lit `output/consolidated.{lang}.md` (toutes
   les langues **latines** présentes) + `glossary_master.json`. Parse le consolidé en
   **arbre de sections** via le parser relocalisé (`core/corpus`, §11), qui expose pour
   chaque section son **`section_path`** (chemin structurel, ex. `(2,1,1)`) — **invariant
   par langue** —, son titre et son ancre GFM.
2. **Unités de texte** : l'unité d'extraction = **sous-section `###`** (à défaut le
   chapitre `##`), **bornée en taille** (chunk si trop longue) — granularité alignée sur
   le « text unit » GraphRAG (≈ 1200 tokens), meilleure pour le rappel qu'un chapitre
   entier.
3. **Squelette déterministe (zéro LLM)** : nœuds `GLOSSARY_TERM` depuis le glossaire
   (définition connue) ; rattachement terme↔section par balayage d'occurrences (label +
   `aliases`, normalisés `slugify_anchor`).
4. **Extraction sémantique par unité** (`extractors/graph_extractor.py`, LLM, parallèle)
   : concepts / idées / exemples + relations typées + **span de citation** (texte +
   `section_path`). **Borné par `density`**. Prompt `visuals_graph_extraction.j2`.
   - **Gleaning** (standard du marché, **1 passe** bornée) : re-prompt « as-tu manqué des
     entités/relations ? » pour améliorer le **rappel** sans exploser le coût.
5. **Consolidation des descriptions / résolution d'entités**
   (`extractors/entity_resolver.py`) :
   - **Termes** → entrées de glossaire (déjà réconciliées) — coût nul.
   - **Entités libres** (concepts/idées/exemples) → fusion par **embeddings**
     (`EmbeddingProvider`) sur `label + courte description`, au-dessus d'un **seuil
     cosinus** (constante nommée, §13). **Fallback AUTO** sans clé OpenAI : label/alias
     normalisés (`slugify_anchor`) — pattern `retriever_factory` du Dialogue. Pour chaque
     cluster fusionné, une mini-passe LLM (`visuals_entity_canonicalize.j2`) **fusionne
     les descriptions variantes en une seule** + nom canonique (étape « entity
     description summarization » de GraphRAG).
     > **Écart livré (V1)** : la canonicalisation est **déterministe** (libellé le plus
     > fréquent, 1ʳᵉ définition non vide, extraits unionnés) — la mini-passe LLM
     > `visuals_entity_canonicalize.j2` n'est **pas** implémentée (template absent, pas
     > d'appel LLM). Choix assumé : coût/latence évités pour un gain marginal ;
     > réintroductible plus tard sans changement de schéma.
6. **Liens inter-chapitres émergents** : les entités partagées (après résolution)
   **relient naturellement** les sections (un nœud unique référencé par plusieurs).
7. **Communautés** (`visuals/community.py`, **déterministe, pur Python, zéro LLM**) :
   `networkx.louvain_partitions` → **dendrogramme** (hiérarchie multi-niveaux). Seed fixe
   (constante) pour la **reproductibilité**. Remplit `community_path` et construit les
   `Community`.
   > **Écart livré (V1)** : partition **plate** (un seul niveau) via
   > `networkx.louvain_communities` — toutes les `Community` ont `level=0` /
   > `parent_id=None` et un `community_path` à un seul entier. La hiérarchie
   > multi-niveaux est **volontairement non livrée** (rendu plus simple) ; les champs
   > `level`/`parent_id` restent en place pour une introduction ultérieure.
8. **Community reports — double usage** (`extractors/community_reporter.py`, LLM,
   **bottom-up**) : par communauté → un **rapport court** (label lisible + 1–2 phrases de
   synthèse + idée-clé). Sert **à la fois** l'étiquetage UI **et** d'unité de raisonnement
   transversal. Prompt `visuals_community_report.j2`.
9. **Enchaînements transversaux (idea-chains)** : une passe **reduce**
   (`visuals_idea_chains.j2`) **sur les community reports** (et non sur des labels nus)
   ajoute les relations typées **inter-communautés** de haut niveau (ex. « fraude Enron →
   défiance → besoin d'IFRS → comparabilité ») — c'est le *global map-reduce* GraphRAG,
   donc sémantiquement riche **et** borné en contexte. (Remplace l'ancienne « passe ponts »
   jugée trop simpliste.)
10. **Diagrammes** (`extractors/diagram_author.py`, LLM, parallèle) : par unité/thème,
    sélectionne les types pertinents **parmi `diagram_types`** et émet le **modèle JSON
    typé** (`Diagram`) + span de citation (`section_path`). **Borné par `density`**.
    Prompt `visuals_diagram_authoring.j2`.
11. **Localisation par langue latine** (`extractors/label_translator.py`) : traduit les
    *textes* (labels de nœuds, définitions, libellés de relations, reports de communautés,
    titres/légendes/labels de diagrammes). `GLOSSARY_TERM` → `cross_lang[L]` (zéro appel).
    Prompt `visuals_label_translation.j2`.
12. **Résolution des extraits par langue** (§5) : pour chaque span, le **`section_path`**
    (invariant) est résolu vers la section correspondante de `consolidated.{lang}.md`, et
    l'extrait embarqué = le **passage de cette sous-section dans la langue cible** (tronqué
    proprement) + ancre/`§x.y` **de cette langue**. **Aucun alignement phrase-à-phrase
    fragile, aucune ancre ni quote partagée entre langues.**
13. **Rendu** (`infra/export/`, §6) → `knowledge_map.{lang}.html` +
    `diagrams.{lang}.html`, écrits atomiquement (`infra/storage/fs_artifacts`) dans
    `visuals/output/`.
14. **Persistance d'état** : manifeste de fraîcheur + `run_state.json` ; événements →
    UI (cf. §7, §9).

---

## 5. Multilingue — détail

- **Coût** ≈ 1 langue (extraction + diagrammes + communautés) + **petites traductions
  de libellés** × (N−1) langues latines. Le clustering Louvain ne coûte **aucun token**.
- La **structure** (ids de nœuds, arêtes, communautés, formes/liens de diagrammes) est
  produite une fois et **partagée** ; seuls les textes varient → cohérence structurelle
  garantie entre langues.
- **Extraits** : keyés par `section_path` (**invariant par langue**) → résolus vers le
  passage de `consolidated.{lang}.md` de chaque langue (cf. §4.12). L'ancre/`§x.y`
  affichée est celle **de la langue rendue**. Jamais d'ancre ni de citation partagée
  entre langues (les titres traduits produisent des ancres différentes).
- Si `EmbeddingProvider` absent (pas de clé OpenAI) → résolution dégradée par label
  (fallback AUTO), le reste inchangé.

---

## 6. Rendu HTML autonome — moteur unique, zéro DSL

### 6.1 Principe
Le LLM **n'émet jamais** de DSL de rendu. Python transforme les entités `domain` en
(a) **données JSON inline** + (b) **markup déterministe**. Aucune étape de parsing de
langage de diagramme → **aucune classe d'erreur de syntaxe**, et **tout le chemin de
données est testable** en pytest.

### 6.2 Document A — `infra/export/knowledge_map_html.py`
- **Cytoscape.js** + extensions **`fcose`** (réseau), **`dagre`** (arbre),
  **`expand-collapse`** + **nœuds composés** (communautés repliables) — **vendorisés
  et inlinés** (cf. §6.5).
- **Données** : `KnowledgeGraph` sérialisé en JSON inline (`<script type="application/
  json">`), incluant définitions, extraits et `community_path`.
- **Deux modes explicites — modèle d'exploration standard du marché** (focus /
  ego-network façon Neo4j Bloom / Linkurious, combiné au regroupement par communautés) :
  - **Mode réseau (défaut)** : layout `fcose` ; communautés = **nœuds composés** repliés
    au niveau haut (≈ une douzaine). **Déplier** une communauté (`expand-collapse`)
    révèle ses nœuds. Recherche (focus + surbrillance), filtres `NodeType`/`EdgeType`,
    zoom/déplacement.
  - **Mode arbre (focus)** : **clic sur un nœud individuel** → ce nœud devient **racine**,
    layout `dagre` sur son **ego-network** (voisinage ; arbre couvrant BFS, arêtes
    hors-arbre en secondaire), tiré **par-delà les communautés** — qui **dégradent alors
    en simple code-couleur** (et non plus en conteneurs). Bouton/clic « retour » → mode
    réseau, **état des communautés restauré**.
  - Les deux modes **ne se concurrencent plus** : le rôle « conteneur » des communautés
    est propre au mode réseau ; en mode focus, elles ne sont qu'un attribut visuel.
- **Panneau latéral** au clic : badge de type, label, définition, **extrait source** cité
  (renvoi `§x.y` de la langue rendue), **relations** (chips typés cliquables), bouton
  **« recentrer (mode focus) »**.

### 6.3 Document B — `infra/export/diagram_board_html.py`
- Diagrammes **« graphe »** (`FLOWCHART`, `HIERARCHY`, `DECISION_TREE`, `CYCLE`) →
  petites instances **Cytoscape** (layout `dagre` ; `concentric` pour `CYCLE`) — **même
  moteur que le Doc A**, donc un seul socle vendorisé.
- Diagrammes **« linéaires/tabulaires »** (`TIMELINE`, `COMPARISON`) → **HTML/CSS
  déterministe** (aucune lib).
- Galerie de **cartes** (titre + schéma + légende + renvoi chapitre) ; **sommaire**
  filtrable par `DiagramType` ; clic sur un élément → panneau d'extrait.
- **Perf** : les instances Cytoscape des cartes sont **initialisées paresseusement**
  (IntersectionObserver) → une galerie de dizaines de diagrammes reste fluide.

### 6.4 Système de design (référence : maquette HF validée)
- Réplique la **palette de tokens** (`ui/theme/_tokens.py`) : mode **clair** + mode
  **sombre miroir** (CSS variables + `prefers-color-scheme` + bascule manuelle).
- **Code couleur des nœuds (corrigé pour distinction nette)** :
  - Concept = `#0a4f93` (bleu profond)
  - Terme glossaire = `#1a7f37` (vert)
  - Exemple / cas = `#b45309` (ambre)
  - **Idée / enchaînement = `#c2185b` (framboise/magenta)** — *remplace l'ancien violet,
    trop proche du bleu.*
- Chrome : barre d'outils (recherche, sélecteur Réseau/Arbre, zoom), sous-barre
  (pastilles-filtres + compteur communautés), canvas à fond pointillé léger, halos de
  communautés teintés étiquetés, ombres douces, panneau latéral. Typographie système
  (`"Segoe UI", system-ui`). Micro-interactions (transitions de layout, glissement du
  panneau), états de focus accessibles (clavier sur recherche/filtres).
- **Exigence** : rendu **abouti**, calibré à l'implémentation (skill `frontend-design`).

### 6.5 Vendoring & autonomie
- Assets JS vendorisés sous `infra/export/_assets/visuals/` : `cytoscape.min.js`,
  `cytoscape-fcose`, `cytoscape-dagre` (+ `dagre`), `cytoscape-expand-collapse`
  (+ dépendances `layout-base`/`cose-base` requises). **Tous MIT.** Versions épinglées,
  provenance documentée (`packaging/README.md`).
- **Ordre d'inline** (l'enregistrement des extensions en dépend) :
  `layout-base`/`cose-base`/`dagre` → `cytoscape` → extensions (`fcose` / `dagre` /
  `expand-collapse`). Un test vérifie la présence et l'ordre.
- Le renderer **lit ces assets et les inline** dans `<script>` → **fichier unique**,
  hors-ligne. Résolution du chemin des assets à l'exécution via `core/config/paths`
  (même mécanisme que ffmpeg bundlé).
- **Garde-fou de test** : le HTML produit ne contient **aucune** référence
  `src="http`/`href="http"` externe ; le JSON embarqué est valide ; CSS clair **et**
  sombre présents.

---

## 7. Orchestration, fraîcheur, coût, parallélisme

- **`VisualsOrchestrator`** (modelé sur `SupportsOrchestrator`) : parallélise les unités
  via **`core/concurrency/map_bounded`** (borné par `VisualsSettings.llm_workers`),
  honore le **`PauseToken`**, verrou sur le manifeste, **compteur de coût partagé**.
  Unités parallélisables : extraction par unité (sous-section), diagrammes par unité,
  community reports, traduction par langue.
- **Fraîcheur** (`visuals/manifest.py`) : `manifest.json` = hash des réglages +
  **mtime par langue** de `consolidated.{lang}.md` **et** `glossary_master.json`. Une
  source régénérée **périme** les visuels (bannière d'état UI). **Alignement
  Génération/Pédagogie** : ensemble complet relancé → **régénère** (écrase) ; ensemble
  incomplet (interruption/plafond) → **reprise grossière** (frais sautés, manquants
  produits).
- **`run_state.json`** : `RunStatus` + horodatages + coût (état lisible hors session,
  cohérent avec sidebar/tuiles).
- **Plafond de coût** best-effort en parallèle (léger dépassement toléré par les requêtes
  en vol), via `VisualsCostEstimator` (cf. §10).
- **Réutilisation** : `map_bounded`, `PauseToken`, `default_classify`, `PromptLoader`,
  `LLMProvider`, `EmbeddingProvider`, `slugify_anchor`, parser de sections (`core/corpus`).

---

## 8. Réglages (`VisualsSettings`) & persistance projet

`domain/visuals.py` — `@dataclass(frozen=True)` :

- `produce_knowledge_map: bool = True`
- `produce_diagrams: bool = True`
- `density: SupportDensity = SupportDensity.STANDARD`
- `diagram_types: frozenset[DiagramType] = frozenset(DiagramType)` (les 6 activés par défaut)
- `llm_workers: int = 16` (borne UI 1–64, comme la Pédagogie)
- `cost_ceiling_usd: float | None = None`

Langues : **non listées en réglage** — suit les langues **latines** réellement
produites par la Génération (présence de `consolidated.{lang}.md`). `zh`/`ar` ignorées.

**Blob v2** (`domain/project.py` / `infra/storage/sqlite_state.py`) : ajout d'une clé
`visuals` dans `{version, workspace_folder, generation, pedagogy, chat, visuals}`,
migration **lenient** (absente → `None` = « à configurer »), aucune rupture des blobs
existants. Sous-dossier workspace : `visuals/` (+ `visuals/output/`).

---

## 9. UI (PySide6)

Miroir de Pédagogie/Dialogue, **logique testable sans Qt** :

- `ui/features/visuals_tab.py` (`FeatureTab`) **enregistré** dans `FeatureRegistry`
  (aucune modification de `MainWindow`/`Project`).
- `ui/visuals_controller.py` (découplé, reçoit header/état/progression/logs ;
  distingue projet affiché vs projet du worker actif, comme la Génération).
- `ui/viewmodels/visuals_state.py` + viewmodel de progression (sans Qt).
- `ui/dialogs/visuals_settings_view.py` (réutilise le `SettingsView` master-détail).
- Vue de progression réutilisant le pattern `PedagogyProgressView`.
- `ui/qt_event_bus` : `VisualsQtEventBus` (EventBus → signaux Qt).
- **Action « ouvrir le livrable »** : bouton ouvrant le HTML produit dans le navigateur
  par défaut / révélant le dossier (réutilise le helper d'ouverture existant si
  présent).
- **PromptsEditor** : ajout au catalogue éditable des templates
  `visuals_graph_extraction`, `visuals_community_report`, `visuals_idea_chains`,
  `visuals_diagram_authoring`, `visuals_label_translation`.
  > **Écart livré (V1)** : **5** templates (pas 6) — `visuals_entity_canonicalize`
  > n'existe pas (canonicalisation déterministe, cf. §5).
- **i18n** : chaînes via `self.tr()` / `QCoreApplication.translate("<Contexte>", ...)`,
  nouveau(x) contexte(s) Linguist, extraction/compilation `scripts/i18n_*`, +
  **tests garde-fou** paramétrés (≥ 1 chaîne par nouveau contexte).
- **Libellés de domaine FR gelés** (`NodeType`/`EdgeType`/`DiagramType`) → variantes UI
  traduites exposées comme fonctions (pattern `ui/pedagogy_labels`).

---

## 10. Coût (`app/VisualsCostEstimator`)

Réutilise `app/_cost_common`. Comptabilise : extraction sémantique par unité
(**+ gleaning**), **canonicalisation des descriptions**, **community reports**, passe
**idea-chains** (reduce), **traduction de libellés × langues**, génération des
diagrammes, **embeddings** (via `infra/embeddings/_pricing`). Le clustering Louvain = 0.
Exposé dans l'estimation UI (opt-in) et appliqué comme plafond best-effort à
l'exécution.

---

## 11. Réutilisations transverses & points d'attention

- **Parser de sections — RELOCALISÉ (décidé)** : `pedagogy/chapters` est déplacé vers un
  **module neutre partagé `core/corpus`** (pur, sans Qt/HTTP/SQL), enrichi pour exposer le
  **`section_path`** (chemin structurel invariant par langue) en plus du titre et de
  l'ancre. La Pédagogie est **refactorée** pour importer depuis ce module (Boy Scout,
  **zéro duplication**) ; Visualisations le consomme aussi. Le découpage par section du
  Dialogue (`chat/corpus`) pourra l'adopter ultérieurement (hors périmètre, non bloquant).
- **`EmbeddingProvider`** : déjà utilisé par le Dialogue ; réutilisé tel quel, avec
  résolution **AUTO** (présence de clé OpenAI ou non).
- **`slugify_anchor`** : source unique des ids de nœuds et ancres → cohérence avec les
  ancres du consolidé exporté (renvois `§x.y`).

---

## 12. Tests & vérifications

`pytest` + `ruff check .` + `mypy --strict src tests` doivent être **verts** (barre
projet). Grâce au découpage **LLM → JSON typé → rendu déterministe**, **tout le chemin
de données est testable** :

- **domain** : validation des entités/enums.
- **extractors** : `FakeLLMProvider` → assertions sur nœuds/arêtes/diagrammes.
- **résolution** : `FakeEmbeddingProvider` → clustering attendu ; chemin **fallback
  AUTO** sans embeddings.
- **communautés** : **déterminisme Louvain** (seed fixe) + mapping hiérarchie →
  nœuds composés.
- **renderers** : HTML contient les données attendues + tokens de couleur ;
  **garde-fou « zéro URL externe »** ; JSON embarqué valide ; CSS clair **et** sombre.
- **orchestrateur** : fraîcheur / reprise / plafond de coût (patterns Pédagogie).
- **viewmodels** sans Qt ; smoke `pytest-qt` des widgets.
- **i18n** : garde-fou chaînes paramétrées.
- **Smoke navigateur — DÉCIDÉ : optionnel/dev** : un test **Playwright** (ouverture des
  HTML produits → *nœuds rendus / clic→arbre / zéro erreur console*) reste **hors suite
  standard** (inutile aux utilisateurs finaux ; le chemin de données est déjà couvert en
  pytest). Conservé comme **outillage dev** facultatif.

---

## 13. Constantes & limites assumées

- **Centralisation des constantes** (directive #1) : seuil cosinus de fusion, **seed
  Louvain**, **nombre de passes de gleaning** (= 1), plafonds de nœuds/diagrammes par
  niveau de `density`, taille max d'une unité de texte (chunk), longueur max d'un extrait,
  **règle d'id de nœud** (`type:slug` + compteur), dimensions de canvas, noms de fichiers
  (`knowledge_map.{lang}.html`, `diagrams.{lang}.html`), sous-dossier `visuals/` — **tous
  nommés**, aucun littéral épars.
- **Cas dégénérés** (garantis valides) : cours minuscule / glossaire vide / unité sans
  entité extractible → HTML **valide même clairsemé** (graphe/galerie possiblement vide,
  message d'état) ; `produce_knowledge_map`/`produce_diagrams` à `False` → un seul livrable
  produit.
- **Limites assumées** :
  - `zh`/`ar` **hors périmètre** de la fonctionnalité (décision produit §1.3).
  - Le seuil de fusion d'entités est une **constante ajustable** (risque
    over/under-merge maîtrisé par la colonne vertébrale glossaire).
  - La qualité des **relations sémantiques** dépend du prompt (itérable via
    PromptsEditor).

---

## 14. Dépendances nouvelles

- **`networkx`** (BSD, **pur Python**, bundlable PyInstaller) — communautés Louvain
  hiérarchiques.
- **Assets JS vendorisés** (MIT, checkés au repo, **non** dépendances pip) : `cytoscape`
  + `cytoscape-fcose` + `cytoscape-dagre` (+ la lib de layout `dagre`) +
  `cytoscape-expand-collapse` (+ `layout-base`/`cose-base`).
- Embeddings : **déjà** présent (OpenAI), aucune nouvelle dépendance.

**Packaging (`packaging/fahmi2.spec`, gitignored — à patcher)** : `collect`/
`hiddenimports` pour `networkx` ; `datas` pour `infra/export/_assets/visuals/*.js`.
Documenter dans `packaging/README.md`.

---

## 15. Documentation à mettre à jour

`README.md`, `docs/`, `CLAUDE.md` (nouvelle **4ᵉ fonctionnalité** + paragraphe
transverse), `packaging/README.md` (networkx + assets vendorisés), et cette spec.

---

## 16. Décisions — toutes verrouillées

- Smoke test **Playwright** : **optionnel/dev** (décidé).
- Parser de sections : **relocalisé dans `core/corpus`** (décidé, §11).
- Modèle d'interaction Doc A : **deux modes focus/réseau réconciliés** (§6.2).
- Extraits multilingues : **par `section_path`** (§4.12, §5).
- Enchaînements transversaux : **map-reduce sur les community reports** (§4.8–4.9).
- Aucune décision ouverte restante.
