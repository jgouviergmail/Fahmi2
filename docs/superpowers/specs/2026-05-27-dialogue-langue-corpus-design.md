# Dialogue : langue de corpus sélectionnable — conception

**Date** : 2026-05-27
**Statut** : conçu (validé en dialogue), à implémenter sur `feat/dialogue-langue-corpus`.

## Problème

Le Dialogue (chat ancré sur le corpus) lit et cite aujourd'hui **toujours** le document
dans la **langue d'origine** de la génération. L'utilisateur veut **choisir** une autre
langue disponible (un `consolidated.{langue}.md` produit) afin d'échanger **et** d'obtenir
les **références** dans la langue désirée.

## Constat de faisabilité (déjà en place)

- Le corpus est **déjà paramétré par langue** : `chat.corpus.load_corpus_chunks(..., language=)`
  charge `consolidated.{lang}.md` et localise le glossaire.
- L'index sémantique est **déjà par langue** (`chat/index.{lang}.npz`) ; l'empreinte de
  fraîcheur inclut la langue → indexation **paresseuse, une fois par langue utilisée**
  (jamais les 7 d'avance ; lexical = aucun embedding).
- `Conversation.language` **existe déjà** et est persistée (aujourd'hui = langue de réponse).

Ce qui manque : (1) que `Conversation.language` pilote **aussi** le corpus, (2) un
**sélecteur** à la création d'une conversation, (3) un helper « langues disponibles »,
(4) la **localisation complète du glossaire** (terme **et** définition) en aval.

## Décisions de conception

1. **Portée = par conversation.** Une conversation = une langue, **fixée à sa création**
   (pas de bascule en cours de fil → pas d'historique multilingue incohérent). Pour
   « changer de langue », on crée une nouvelle conversation. S'appuie sur le champ
   `Conversation.language` existant.
2. **Une seule langue pilote tout** : lecture du corpus, **références citées** et **langue
   de réponse**. (`Conversation.language` devient le pivot unique.)
3. **Glossaire entièrement localisé** : la définition traduite est **déjà calculée** par la
   phase 6 (le `glossary.{lang}.md` exporté le prouve) mais **jetée** à la persistance. On la
   **conserve** dans `cross_lang`. **Aucun appel LLM supplémentaire.** L'`acronym_expansion`
   (colonne *Signification*) reste **invariante** par langue (convention métier voulue).
4. **Indexation inchangée** (paresseuse par langue) ; la clé de fraîcheur et le chemin
   d'index portant déjà la langue, le multi-langue fonctionne sans changement du moteur de
   retrieval.

## Changements par zone

### `domain/glossary.py` — `cross_lang` porte terme **+** définition

- Nouveau `@dataclass(frozen=True) LocalizedTerm: term: str; definition: str`.
- `Term.cross_lang: dict[Language, LocalizedTerm]` (au lieu de `dict[Language, str]`).
- `localize_glossary_terms(terms, language)` → remplace **terme et définition**
  (`replace(t, term=loc.term, definition=loc.definition)`), repli sur la source ;
  `acronym`/`acronym_expansion` inchangés. (Le helper mono-champ
  `glossary_term_for_language`, devenu redondant avec ce flux, est **retiré** — sa
  logique de repli vit désormais ici, source unique.)
- `parse_glossary_master_terms` — parsing **lenient** d'une valeur `cross_lang` :
  - objet `{"term": …, "definition": …}` → `LocalizedTerm`;
  - chaîne (**legacy**, terme seul) → `LocalizedTerm(term=str, definition=<définition source>)`
    (dégradation propre : les anciens glossaires gardent la définition source).

### `pipeline/handlers/phase_6_translation.py` — persister la définition

- `_persist_cross_lang` reçoit désormais les **termes localisés** par langue (qui portent
  déjà `term` **et** `definition` via `_LocalizedTerm`) et écrit
  `cross_lang[lang] = {"term": …, "definition": …}`.
- L'indice de traduction du consolidé (`cross_lang_by_language: dict[Language, dict[str,str]]`
  source→terme) **reste tel quel** (seul le terme sert d'indice ; inchangé).

### `pedagogy/sources.py` — langues disponibles

- Nouveau `available_content_languages(generation_output_dir) -> list[Language]` : les langues
  (ordre de l'enum) dont le `consolidated_doc_path` existe. Réutilise la même logique que
  `resolve_content_language`.

### `ui/chat_controller.py` — corpus piloté par la conversation

- La langue de contenu effective = **langue de la conversation active** (si son doc existe ;
  sinon repli `resolve_content_language`). `_resolve_content_language(project, target)` prend
  la langue cible.
- Sélectionner/charger une conversation (re)dérive le corpus pour **sa** langue (la clé de
  fraîcheur intègre déjà la langue → rechargement automatique ; l'index `.npz` est déjà par
  langue).
- `new_conversation(language)` accepte la langue choisie (défaut : langue source si produite,
  sinon 1ʳᵉ disponible).
- La réponse est déjà générée dans `conversation.language` (inchangé).

### `ui/widgets/chat_view.py` (+ viewmodel si besoin) — sélecteur

- À la **création** d'une conversation : un combo « Langue » peuplé par
  `available_content_languages` (libellés via `domain/languages.language_display_label`).
  **Masqué/neutralisé s'il n'y a qu'une langue produite** (comportement actuel inchangé).
- Le signal `new_conversation_requested` porte la langue choisie.
- La langue de la conversation est affichée (en-tête/liste) pour lever l'ambiguïté.

### Tests

- `domain` : `cross_lang` terme+définition (sérialisation lenient legacy/objet), `localize_glossary_terms` localise la définition.
- `phase_6` : `_persist_cross_lang` écrit `{term, definition}` ; round-trip parse.
- `pedagogy/sources` : `available_content_languages`.
- `ui` viewmodel/contrôleur : nouvelle conversation dans une langue ≠ source → corpus + index de cette langue ; repli si langue absente.
- `chat/corpus` : chunks de glossaire avec **définition localisée**.

### Documentation

- `CLAUDE.md` (section `chat/` + localisation glossaire : lever la « limite assumée »),
  `docs/02` (Dialogue : langue de corpus par conversation), `docs/04` (réglage/sélecteur),
  `docs/01`/`README` (capacité), `CHANGELOG` (section `[Unreleased]`).

## Critères d'acceptation

- Créer une conversation en langue X (produite) → le Dialogue lit `consolidated.X.md`, **cite
  en X**, **répond en X** ; les **chunks de glossaire** (terme **et** définition) sont en X.
- Une seule langue produite → aucune régression visible (pas de sélecteur).
- Index sémantique construit **à la demande** par langue (pas d'embedding des 7).
- Anciens `glossary_master.json` (cross_lang terme-seul) lus sans erreur (définition source).
- `pytest`, `ruff`, `mypy --strict` verts.
