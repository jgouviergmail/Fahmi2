# Citations lisibles et cliquables dans le Dialogue — Design

**Date** : 2026-05-27
**Statut** : validé (prêt pour plan d'implémentation)

## Contexte et problème

Dans l'onglet **Dialogue** (désormais multilingue : la langue du corpus est
sélectionnable par conversation), le LLM cite ses sources avec des marqueurs
`[§N]` au fil de la réponse (le prompt impose ce format, cf.
`infra/prompts/defaults/chat_augmented.j2` et `chat_strict.j2`). Aujourd'hui :

- le corps de la réponse affiche le marqueur **brut** `[§3]`, cryptique pour
  l'apprenant ;
- la section « Sources » en bas du message liste les citations sous la forme
  `§ <Chapitre> › <Section>` (liens cliquables), **mais sans numéro** ;
- conséquence : **rien ne relie** le `[§3]` du texte à une entrée précise de la
  liste. Le marqueur est doublement inutile (jargon + non rattachable).

`N` est l'**index du passage récupéré** (1-based parmi les `top_k` passages
fournis au prompt), avec des trous (tous les passages ne sont pas cités) et des
doublons.

## Objectif

Rendre les citations parlantes pour l'utilisateur final :

1. un repère **compact et cliquable** dans le corps de la réponse ;
2. une liste « Sources » **numérotée à l'identique**, de sorte que `[3]` dans le
   texte renvoie sans ambiguïté à la 3ᵉ source.

## Décisions validées

| Sujet | Décision |
|-------|----------|
| Style du repère | **Crochets classiques `[3]`** (style bibliographie). |
| Numérotation | **Séquentielle, par ordre d'apparition, dédupliquée par ancre** (un passage cité 2× garde son numéro). |
| Action du clic | **Ouvre le passage source** (fenêtre `show_passage_dialog` existante), identique au clic sur l'entrée de liste. |
| Marqueurs invalides (hors-bornes) | **Retirés** du texte affiché. |
| Prompt LLM | **Inchangé** : le LLM continue d'écrire `[§N]` (le `§` fiabilise la détection vs un `[3]` littéral du cours). |
| Liaison repère → source | **Matérialisée dans le contenu au moment de la réécriture** (forme liée persistée), pas re-devinée au rendu. |

### Pourquoi lier au moment de la réécriture (et pas au rendu)

On ne peut pas avoir à la fois un contenu persisté « pur » (`[1]` nu) **et** zéro
collision au rendu : un `[1]` nu a perdu l'information « ceci est un marqueur »,
et serait indistinct d'un `[1]` littéral présent dans le cours. La seule façon
d'éliminer la collision est de matérialiser la liaison là où le `[§N]` est encore
identifié sans ambiguïté (la regex `_RE_CITATION`). Le contenu persiste donc la
forme liée. C'est sans conséquence : il n'existe **aucun export de conversation**,
le contenu n'est lu que par le re-rendu et le store ; et un lien est la
représentation Markdown naturelle d'une citation.

## Contexte multilingue (vérifié — sans impact sur la conception)

L'évolution du Dialogue vers le multilingue (langue de corpus par conversation)
est **orthogonale** à cette feature. Trois points confirmés :

1. **Marqueur non localisé** : les prompts `chat_strict`/`chat_augmented`
   localisent la *réponse* (`output_language_label`) mais imposent le format
   `[§N]` **quelle que soit la langue**. La regex `\[§(\d+)\]` reste universelle.
2. **Ancres = langue de la conversation** : `ChatController` recharge
   `self._chunks` selon `conversation.language` à l'affichage
   (`_load_corpus(project, conversation.language)`). Les ancres des citations
   stockées (dans cette langue) correspondent donc au corpus rechargé → le clic
   inline est cohérent **par construction**, sans logique nouvelle
   (`_on_citation_clicked` résout `chunk.anchor == anchor` dans `self._chunks`).
3. **RTL/CJK** : afficher un `[K]` ASCII dans un texte arabe/chinois relève du
   rendu bidi déjà existant (identique au `[§K]` brut actuel) → pas une
   régression introduite ici.

## Comportement cible

Réponse de l'assistant rendue :

```
La photosynthèse convertit la lumière en énergie chimique [1]
et libère du dioxygène [2].

Sources :
  [1] Chapitre 2 › La phase claire
  [2] Chapitre 2 › Le cycle de Calvin
```

- `[1]`/`[2]` dans le texte : liens cliquables (couleur lien) → ouvrent le
  passage source.
- Liste « Sources » : numérotée `[K]`, liens + infobulle d'aperçu conservés.
- Numéros séquentiels, sans trous, cohérents entre texte et liste.

## Conception détaillée

### `domain/chat.py`

`Citation` (frozen dataclass) gagne un champ **`number: int`** (numéro
d'affichage 1-based). Pas de valeur par défaut : tout site de construction le
fournit explicitement (cohérent avec les entités domaine immuables).

### `chat/citations.py`

`parse_citations` est **remplacée** par :

```python
def resolve_citations(
    answer: str, passages: tuple[RetrievedPassage, ...]
) -> tuple[str, tuple[Citation, ...]]:
    """Réécrit les marqueurs [§N] en liens [[K]](anchor) et renvoie les citations."""
```

Algorithme, en **une seule passe** sur `_RE_CITATION` (`\[§(\d+)\]`, inchangé) :

1. pour chaque `[§N]` : si `1 <= N <= len(passages)`, résoudre le chunk ;
2. attribuer un **numéro séquentiel `K` par ancre** (déduplication : une ancre
   déjà vue réutilise son `K`) ;
3. accumuler les `Citation(number=K, chapter_title, section_title, anchor,
   snippet)` dans l'ordre de première apparition ;
4. **réécrire** le texte : `[§N]` valide → `[[K]](anchor)` (lien Markdown, ancre
   **sans `#`**) ; `[§N]` invalide → supprimé, en absorbant une espace adjacente
   superflue pour ne pas laisser de double espace.

Retour : `(contenu_réécrit, citations)`.

### `chat/chat_service.py`

`_build_message` appelle `resolve_citations(response.content, passages)`, place le
**contenu réécrit** dans `ChatMessage.content` et les citations numérotées dans
`ChatMessage.citations` (l'appel actuel à `parse_citations` ligne ~215 est
remplacé). Le streaming est inchangé : la réécriture a lieu à la finalisation
(comme l'actuel parsing de citations) ; pendant le flux, les deltas bruts
s'affichent transitoirement puis sont remplacés par le message finalisé.

### `ui/widgets/chat_view.py`

- `_message_html` (assistant) : **aucune transformation inline supplémentaire**.
  `render_markdown_fragment(message.content)` produit nativement les
  `<a href="anchor">[K]</a>` (validé empiriquement, cf. plus bas). Le clic est
  déjà câblé : `anchorClicked` → `citation_clicked(anchor)`.
- `_citations_html` : préfixer chaque entrée par **`[K]`** (au lieu de `§ `), en
  conservant le lien `href=anchor` et l'infobulle `title` d'aperçu. La
  numérotation vient de `citation.number`.

### `app/chat_conversation_store.py`

- `_serialize_citation` : ajouter `"number": citation.number`.
- `_deserialize_message` : lire `number` avec **fallback par position** :
  `c.get("number", index + 1)` via `enumerate`. Les conversations antérieures
  (sans `number`) obtiennent ainsi une numérotation cohérente de liste ; leur
  contenu déjà stocké conserve ses `[§N]` bruts (non liés) → **dégradation
  gracieuse**, aucune casse.

### Prompts

Inchangés. La réécriture est entièrement côté application.

## Validations empiriques (preuves)

Exécuté avec `python-markdown` du venv (extension `tables`, exactement la config
de `render_markdown_fragment` — `_FRAGMENT_EXTENSIONS = ["tables"]`, inchangée) :

```
markdown('le PIB [[1]](resume-eco) augmente [[2]](inflation).')
 → '<p>le PIB <a href="resume-eco">[1]</a> augmente <a href="inflation">[2]</a>.</p>'

markdown('a [[1]](x) b [[2]](y) c [[1]](x)')
 → '<p>a <a href="x">[1]</a> b <a href="y">[2]</a> c <a href="x">[1]</a></p>'
```

→ Les crochets imbriqués `[[K]](anchor)` sont rendus correctement, doublons
compris. **Le fallback HTML inline n'est pas nécessaire.**

**Ancres non-ASCII (multilingue) — équivalence prouvée.** `slugify_anchor`
conserve les caractères de mot Unicode (`[^\w\-]+` avec `re.UNICODE`) : les
ancres réelles sont non-ASCII même en français accentué (`réflexion-générale`),
et a fortiori en arabe/chinois. Vérifié pour FR accentué et arabe (`الفصل-2`) :

- Markdown **ne percent-encode pas** l'ancre : le href généré (`<a
  href="réflexion-générale">`, `<a href="الفصل-2">`) est **rigoureusement
  identique** à celui que pose déjà `_citations_html` via `html.escape(anchor)`
  (mécanisme de référence qui fonctionne en production) ;
- `QUrl(anchor).toString()` rend l'ancre **à l'identique** → au clic,
  `url.toString() == chunk.anchor` matche en FR accentué comme en arabe.

Comme `slugify_anchor` ne produit que `[\w-]` (mot Unicode + tirets), une ancre
ne contient jamais de `(`, `)`, espace ou `]` susceptible de casser la syntaxe
`[[K]](anchor)`. Le chemin inline introduit est donc **strictement équivalent**
au chemin liste existant, y compris en multilingue.

Chemin du clic confirmé (`ui/chat_controller.py::_on_citation_clicked`,
lignes 554-563) : la résolution `chunk.anchor == anchor` contre le corpus chargé
puis `show_passage_dialog` est **partagée** par l'inline et la liste — aucun
câblage nouveau. (Si l'ancre n'existe plus après régénération du corpus, le clic
est sans effet : comportement actuel inchangé, pas une régression.)

Périmètre d'impact reconfirmé après l'évolution multilingue du code :
`parse_citations` n'a qu'**un appelant de prod** (`chat_service.py`) + 3 tests ;
**aucun export de conversation** ne lit `message.content` ; le store des citations
et le format d'affichage sont **inchangés**.

## Hors périmètre (YAGNI)

- Pas de surlignage / défilement vers la liste (le clic ouvre directement le
  passage, plus utile).
- Pas de changement de prompt.
- Pas de réécriture rétroactive des conversations déjà stockées.

## Plan de tests

- `tests/unit/chat/test_citations.py` (adapté à `resolve_citations`) :
  - numérotation séquentielle 1..K ;
  - déduplication par ancre (même `K`, contenu réécrit cohérent) ;
  - marqueurs hors-bornes supprimés (sans double espace résiduel) ;
  - texte réécrit `[§N]` → `[[K]](anchor)` exact ;
  - réponse sans marqueur → `(texte inchangé, ())`.
- `app/chat_conversation_store` : round-trip avec `number` ; migration d'un
  payload legacy sans `number` (fallback par position).
- Widget `pytest-qt` (smoke) : un message assistant rend des `<a>` inline et une
  liste « Sources » numérotée.
- `pytest`, `ruff check .`, `mypy src tests` verts.

## Risques et dégradation gracieuse

| Risque | Traitement |
|--------|------------|
| `[3]` littéral du cours pris pour un marqueur | Éliminé : liaison faite uniquement sur les `[§N]` détectés à la réécriture ; le contenu rendu ne contient que des liens déjà matérialisés. |
| Conversations anciennes | Liste re-numérotée par position ; corps conservé tel quel (`[§N]` non liés). Pas de casse. |
| Ancre périmée après régénération | Clic sans effet (comportement actuel), pas de régression. |
| Crochets imbriqués non rendus | Écarté empiriquement (cf. preuves). |
| Multilingue (marqueur, ancres, RTL/CJK) | Sans impact : marqueur non localisé, ancres alignées sur `conversation.language`, affichage bidi déjà existant. |
| Encodage des ancres non-ASCII via Markdown | Écarté empiriquement (FR accentué + arabe) : href Markdown identique au chemin liste existant, round-trip `QUrl` fidèle, ancres `[\w-]` sans caractère cassant. |
