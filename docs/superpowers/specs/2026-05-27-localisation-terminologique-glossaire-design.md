# Localisation terminologique du glossaire (Génération + Pédagogie + Dialogue) — design

- **Date** : 2026-05-27
- **Statut** : **spec validée** (brainstorming terminé)
- **Origine** : bug de qualité signalé — les **termes** du glossaire (et acronymes
  non internationaux) restent figés dans la langue d'extraction pour **toutes** les
  langues. Ex. « Bilan », « Compte de résultat », « États financiers » apparaissent
  tels quels dans `glossary.en.md`/`consolidated.en.md`/`…de.md` au lieu de
  « Balance sheet »/« Bilanz ». Pré-existant (affecte déjà FR↔EN), rendu visible par
  l'ajout des 5 langues.
- **Prérequis** : pipeline de génération (phases 1-7), Pédagogie et Dialogue livrés ;
  branche `feat/langues-export-docx` (ce correctif s'y ajoute).

## 1. Cause racine

Le glossaire master (`glossary_master.json`, produit par les phases 1-2) stocke
chaque terme sous sa **forme d'extraction** (langue d'origine). En phase 6, le
glossaire de chaque langue cible est produit en envoyant **toute la table Markdown**
au LLM : il **traduit les définitions** mais **garde les termes**. Deux raisons :

1. **`Term.cross_lang`** (`Language → traduction du terme`, docstring « alimenté par
   la phase 6 ») n'est en réalité **jamais peuplé** — uniquement lu (vérifié : 0/20
   termes ont un `cross_lang` dans le `glossary_master.json` réel).
2. Le prompt `phase_6_translation.j2` injecte une liste « *équivalents recommandés :
   `source → target`* ». Comme `target = source` (faute de `cross_lang`), le LLM
   reçoit « **Bilan → Bilan** » → il **garde le terme tel quel**, dans le glossaire
   **et** dans le corps du consolidé (vérifié : « Bilan » ×10 dans `consolidated.en.md`).

## 2. Politique de traduction des termes (validée)

Pour chaque terme et **chaque langue cible**, le LLM produit la **forme métier
consacrée dans la langue cible**, **sauf** si le terme est **international / nom
propre / marque / norme** → il est **conservé tel quel**. La décision « traduire vs
garder » est prise **par terme et par langue cible** (« Free Cash Flow » se garde en
français mais se traduit en chinois). C'est le principe **Do-Not-Translate** de la
localisation professionnelle. **Acronyme conservé** (jamais ré-inventé) ;
`acronym_expansion` **invariante** (toujours dans sa langue d'origine, déjà le cas).

## 3. Principe unificateur

> Tout consommateur du glossaire utilise `cross_lang[L]` où **L = la langue du
> `consolidated.{L}.md` réellement consommé**. Pour la génération, L = chaque langue
> produite. Pour **Pédagogie et Dialogue**, L = la **langue de contenu résolue**
> (`resolve_content_language`) qu'ils chargent.

Conséquence : `consolidated.{L}.md` (termes via l'indice de traduction),
`glossary.{L}.md` (rendu localisé) et les contextes Pédagogie/Dialogue qui lisent ces
fichiers partagent **le même terme `cross_lang[L]`** → cohérence terme↔texte de bout
en bout, y compris dans le cas de repli (cible non générée → `content_lang` = source
ou 1ʳᵉ langue dispo → `cross_lang[content_lang]` correspond aux chapitres lus).

Indépendant du **type d'entrant** (vidéo/audio/document/YouTube : la phase 6 traduit
les docs structurés **par source**) et du **mode de consolidation** (le consolidé,
ordonné ou thématique, est produit en langue source par la phase 5 puis traduit par
la phase 6 avec le même indice `cross_lang`).

## 4. Mécanisme — phase 6 (approche structurée)

On remplace, pour chaque langue **cible ≠ source**, la traduction de la table
glossaire entière par un **appel LLM structuré de localisation**.

### 4.1 Flux phase 6 (réorganisé en 2 étapes)

1. **Localisation du glossaire** (par langue cible, en parallèle `map_bounded`) :
   appel LLM → JSON. On en dérive, **en mémoire**, `cross_lang_by_language[L] =
   {terme_source: terme_localisé}` et on **rend + écrit** `glossary.{L}.md` (via
   `render_glossary_markdown_table`, termes = termes localisés, **définitions
   traduites** par le même appel ; acronyme/expansion repris du master).
2. **Traduction documentaire** (consolidé + docs **par source**, en parallèle,
   inchangée) : la liste « équivalents recommandés » du prompt provient désormais de
   `cross_lang_by_language[L]` (en mémoire ; vrais équivalents `source → cible`).
3. **Persistance pour l'aval** (fin de phase, écriture **atomique**) : on charge le
   payload `glossary_master.json` (dict), on ajoute à chaque terme
   `cross_lang: {"en": "Balance sheet", "de": "Bilanz", …}` (clés = codes langue ;
   round-trip géré par `parse_glossary_master_terms`, `Language(k)`) et on réécrit via
   `ctx.artifacts.write_json_atomic`. *(Les étapes 1-2 n'en dépendent pas — elles
   utilisent le `cross_lang_by_language` en mémoire ; cette écriture sert uniquement
   Pédagogie/Dialogue.)*

**SoC assumé** : la phase 6 **enrichit** un artefact produit par la phase 2
(`glossary_master.json`). Choix délibéré : c'est la **source unique** déjà lue par les
trois features (`parse_glossary_master_terms`). L'alternative (fichier séparé
`glossary_localized.json`) est **écartée** : elle forcerait Pédagogie/Dialogue à lire
**et fusionner** deux fichiers. Aucune incohérence de checkpoint (le checkpoint pipeline
est par-phase en SQLite, sans hash d'artefact) ; une régénération depuis la phase 2
réécrit le master sans `cross_lang`, repeuplé par la phase 6 qui suit.

La langue **source** : copie directe des artefacts (glossaire master rendu avec les
termes source — correct), aucun appel LLM. Le glossaire **n'est plus une
`_TranslationTask`**.

### 4.2 Appel de localisation (entrée/sortie)

- **Entrée** : pour chaque terme, `term` + `definition` + `acronym` +
  `acronym_expansion` (contexte pour juger l'internationalité), + labels langue
  source/cible + style.
- **Sortie** (JSON) : un tableau d'objets **réémettant le terme source** pour un
  matching robuste par identité (pas par position) :
  `[{"source": "Bilan", "term": "Balance sheet", "definition": "<traduite>"}, …]`.
- **Champs persistés/utilisés** : `cross_lang[L]` ← `term` ; `glossary.{L}.md` ←
  `term` + `definition` (+ acronyme/expansion du master).

### 4.3 Robustesse / erreurs (aligné phases 1/2)

- JSON malformé → `parse_json_response` lève une `Fahmi2Error` typée → retry policy.
- **Appariement par `source`** : pour chaque terme master, on cherche l'entrée de
  même `source` ; **terme absent → repli sur le terme source** (per-terme, pas
  d'échec global). Définition absente → repli sur la définition source.
- **Glossaire vide** → pas d'appel (coût 0), glossaire vide rendu.

## 5. Propagation aux consommateurs

`cross_lang` étant **persisté** dans `glossary_master.json` (source unique lue par
les trois features via `parse_glossary_master_terms`), on ajoute un résolveur
partagé et on l'utilise au point d'injection de chaque consommateur.

**Mécanisme — pré-localisation chez le producteur** (les deux générateurs pédagogie
*et* `mock_exam` appellent `format_glossary_terms` ; le faire dépendre d'une nouvelle
langue toucherait 3 sites. Plus propre : le **producteur** fournit un glossaire déjà
localisé, les consommateurs restent inchangés) :

- **Domaine** : `glossary_term_for_language(term, language) -> str`
  = `term.cross_lang.get(language, term.term)` + `localize_glossary_terms(terms,
  language) -> tuple[Term, ...]` (= `dataclasses.replace(t, term=…)`). Source unique
  de résolution (DRY).
- **Pédagogie** : `SupportsOrchestrator` résout déjà `content_lang`
  (`resolve_content_language`) mais le **discarde** ; on le **conserve** et on passe
  `localize_glossary_terms(glossary, content_lang)` à `_run_one` (à la place du
  glossaire master). Générateurs + `format_glossary_terms` **inchangés**. → supports
  en allemand citent « Bilanz ».
- **Dialogue** : `load_corpus_chunks` (qui a déjà `language` = langue de contenu
  résolue par le contrôleur) pré-localise via `localize_glossary_terms(…, language)`
  avant `_glossary_chunks` (**inchangé**). → retrieval/citations dans la bonne langue.

### 5.1 Limite assumée (définitions en aval)

`cross_lang` ne stocke que le **terme** localisé. En aval (Pédagogie/Dialogue lisant
`glossary_master.json`), le **terme** est localisé mais la **définition** reste en
langue source. C'est **strictement meilleur qu'aujourd'hui** (terme *et* définition
en source) et cible exactement le problème signalé (termes/acronymes). Le
`glossary.{L}.md` **exporté** par la génération reste **entièrement** localisé (terme
+ définition traduite). Localiser aussi les définitions en aval = extension future
additive (stocker la définition par langue), **hors périmètre**.

## 6. Fraîcheur (cohérence avec l'existant)

Réécrire `glossary_master.json` change son `mtime` → la **fraîcheur Dialogue** (clé
incluant le mtime glossaire) ré-indexe et le **manifeste Pédagogie** périme les
supports — **comportement correct** (le glossaire a changé). L'écriture a lieu
**pendant** la génération (fin de phase 6, écriture atomique) → mtime stable ensuite,
pas de churn parasite.

## 7. Migration

Les projets **déjà générés** ont un `glossary_master.json` **sans** `cross_lang` →
**repli automatique** sur le terme source partout (comportement actuel) jusqu'à une
**régénération** (qui peuple `cross_lang`). Aucune migration forcée.

## 8. Coût

+1 **petit** appel LLM par langue cible en phase 6 (termes seulement), **en
remplacement** de l'ancienne traduction de la table glossaire → ordre de grandeur
similaire. Vérifier/ajuster `CostEstimator` (phase 6) pour rester réaliste.

## 9. Composants touchés

| Couche | Fichier | Changement |
|--------|---------|------------|
| infra/prompts | `defaults/phase_6_glossary_localization.j2` (**nouveau**) | prompt de localisation structuré (JSON, politique DNT) ; enregistré au catalogue éditable via `PromptTemplateMeta(name, display_name, description)` dans `app/prompts_service.py` |
| infra/prompts | `defaults/phase_6_translation.j2` | la liste d'équivalents porte désormais de vrais `source→cible` (via `cross_lang`, plus de « X→X ») ; clarification mineure de la consigne : **utiliser** l'équivalent cible indiqué |
| pipeline | `handlers/phase_6_translation.py` | étape de localisation + persistance `cross_lang` + flux 2 étapes ; `_glossary_terms_for_template` lit `cross_lang_by_language` |
| domain | `glossary.py` | `glossary_term_for_language()` + `localize_glossary_terms()` ; (parsing `cross_lang` déjà OK) |
| app | `supports_orchestrator.py` | conserver `content_lang` (déjà résolu) + pré-localiser le glossaire (`localize_glossary_terms`) avant `_run_one` |
| chat | `corpus.load_corpus_chunks` | pré-localiser via `localize_glossary_terms(…, language)` avant `_glossary_chunks` |
| pedagogy/chat | — | générateurs, `format_glossary_terms`, `_glossary_chunks` **inchangés** |

## 10. Tests

- **Unit localisation** (FakeLLM JSON) : terme international **gardé**, non-international
  **traduit**, acronyme/expansion **préservés**, appariement par `source`, **terme
  manquant → repli**, glossaire **vide** → pas d'appel.
- **Round-trip `cross_lang`** : écriture `{"en": …}` dans `glossary_master.json` →
  `parse_glossary_master_terms` → `Term.cross_lang[Language.EN]`.
- **`glossary_term_for_language`** : `cross_lang[L]` si présent, sinon terme source.
- **Pédagogie** : `format_glossary_terms(glossary, language=content_lang)` localise ;
  `SupportsOrchestrator` propage `content_lang`.
- **Dialogue** : `_glossary_chunks` localise par langue de corpus.
- **prompt** `.j2` rendu + présence au catalogue.
- **E2E (fakes)** FR→EN/DE : `glossary.en.md` contient « Balance sheet » ;
  `consolidated.en.md` **ne contient plus** « Bilan » ; un support DE et un chunk
  Dialogue DE utilisent le terme localisé.
- MAJ des tests phase 6 existants (glossaire n'est plus une `_TranslationTask`).
- Repasses obligatoires : `pytest`, `ruff check .`, `mypy src tests` verts.

## 11. Documentation

`CLAUDE.md` (phase 6 : localisation + `cross_lang` persisté ; mécanismes glossaire
Pédagogie/Dialogue), README si pertinent, spec (ce document).

## 12. Hors périmètre

- Localisation des **définitions** du glossaire en aval (Pédagogie/Dialogue) — repli
  langue source assumé (cf. §5.1) ; extension additive future.
- Renommage du sous-dossier legacy `per-video/` → `per-source/` (changement de
  chemins, risque, non lié).
- Normalisation du glossaire **en langue source** (les anglicismes internationaux
  extraits restent tels quels — comportement voulu).
