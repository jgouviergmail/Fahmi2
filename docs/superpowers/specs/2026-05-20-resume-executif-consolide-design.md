# Résumé exécutif dans le document consolidé — Design Document

**Date** : 2026-05-20
**Auteur** : co-conception utilisateur + assistant
**Statut** : Spec validée par l'utilisateur, prête pour la phase de planification d'implémentation
**Périmètre** : Phase 5 (consolidation), Phase 7 (cohérence), + correctif indépendant Phase 6 (comptabilité de coût)

---

## 1. Objectif

Le document consolidé final (`workspace/consolidated_master.md`, puis
`output_dir/consolidated.{lang}.md` après traduction) doit désormais s'ouvrir
sur un **résumé exécutif** : un abstract synthétique de l'ensemble du document,
placé juste sous le titre global, avant l'introduction générale.

Le lecteur obtient ainsi une vue « en 30 secondes » de l'intégralité du contenu
dès l'ouverture du document, sans avoir à lire l'introduction développée ni à
parcourir le sommaire.

## 2. Décisions de conception (validées avec l'utilisateur)

### 2.1 Placement — section `## Résumé` sous le titre

Le résumé est une section de méta-élément `## Résumé`, insérée **après** le
`# {titre global}` et **avant** `## Introduction générale`.

Structure finale du document consolidé :

```
# {titre global}

## Résumé              ← NOUVEAU
<abstract 3-5 phrases>

## Introduction générale   (inchangée)
...

## Sommaire
...

# 1. {chapitre}
...

## Conclusion générale     (inchangée)
...
```

**Justification du placement.** La demande initiale était « avant le titre »,
mais aucun contenu lisible ne peut précéder le `#` H1 sans casser la détection
du titre par les outils en aval (extracteurs de titre, TOC automatiques,
conversions HTML/PDF, aperçu GitHub, qui prennent tous la première ligne `#`
comme titre du document). L'idiome universel (article scientifique, README,
encyclopédie) est : titre en première ligne, puis abstract immédiatement
dessous. L'effet « résumé en tête » est obtenu sans aucune régression de rendu.

**Cohérence avec l'existant.** `## Résumé` est traité exactement comme les
autres méta-sections non numérotées (`## Introduction générale`, `## Sommaire`,
`## Conclusion générale`) :

- non numéroté (ce n'est pas un chapitre) ;
- **absent du sommaire** (comme l'introduction et la conclusion) — le sommaire
  ne liste que les chapitres numérotés et leurs sous-titres. Aucune
  modification de `_build_toc_lines` n'est nécessaire.

### 2.2 Génération — champ `summary_markdown` dans le prompt existant

Le résumé est produit par le **même appel LLM** que les autres méta-éléments,
via le prompt `phase_5_consolidation.j2`. Ce prompt reçoit déjà tous les
résumés condensés par vidéo (`summaries_json`) : c'est exactement le contexte
nécessaire pour rédiger un abstract d'ensemble. On ajoute donc un champ
`summary_markdown` au JSON de sortie attendu.

**Alternatives écartées :**

- *Appel LLM dédié* : coût supplémentaire (un appel batch de plus) sans gain de
  qualité, le contexte étant déjà disponible dans l'appel existant.
- *Concaténation déterministe des `key_ideas`* : gratuit mais qualité médiocre,
  pas d'abstract cohérent et fluide.

**Distinction résumé / introduction.** Les deux étant produits par le même
appel à partir des mêmes données, le prompt doit expliciter leur différence
pour éviter la redite :

- **Résumé** : abstract ultra-condensé (3 à 5 phrases, un seul paragraphe), le
  « en 30 secondes ».
- **Introduction générale** : contexte, objectifs et fil conducteur développés
  (2 à 4 paragraphes — inchangée).

## 3. Changements détaillés

### 3.1 `infra/prompts/defaults/phase_5_consolidation.j2`

- Ajouter un item de consigne « Résumé exécutif » décrivant l'abstract attendu
  (3-5 phrases, un paragraphe, vue d'ensemble), avec consigne explicite de ne
  **pas** dupliquer l'introduction générale.
- Ajouter `"summary_markdown": "..."` au schéma JSON de sortie demandé.
- **Couplage avec l'e2e — ne pas casser le routage.** Le test e2e
  (`tests/e2e/test_full_pipeline.py`, `_RotatingFakeLLM.chat`) route les
  réponses du fake LLM par détection de **sous-chaînes** du prompt : la
  consolidation est reconnue via « rédige les méta-éléments », et le résumé
  condensé par vidéo via « résumé condensé » + « carte mentale ». Toute
  reformulation du prompt **doit préserver ces phrases** (ou mettre à jour le
  routage). Idem « passe de cohérence » pour le prompt de la phase 7 — phrase
  située en tête, non modifiée par ce travail.

### 3.2 `pipeline/handlers/phase_5_consolidation.py`

- `_assemble_consolidated` : extraire `summary_markdown` de `meta` (comme
  `introduction` / `conclusion`), et insérer la section `## Résumé` entre le
  `# {title}` et l'introduction, **uniquement si le résumé n'est pas vide**.
- Centraliser le libellé de section dans une constante de module (ex.
  `_SUMMARY_HEADING = "Résumé"`), pas de magic string.
- Mettre à jour la docstring de module et la docstring de `_assemble_consolidated`
  (la liste numérotée décrivant la structure du document).

### 3.3 `infra/prompts/defaults/phase_7_coherence.j2`

La phase 7 relit le consolidé en n'autorisant la réécriture que des
méta-éléments **explicitement énumérés** dans le prompt (« titre global,
introduction générale, plan d'ensemble, conclusion générale, transitions »).
Le résumé n'y figurant pas, le LLM pourrait le considérer hors-périmètre et le
supprimer. **Ajouter « résumé exécutif » à la liste** des méta-éléments à
relire/polir, pour qu'il soit traité comme les autres (cohérence
terminologique, correction des maladresses) sans risque de suppression.

### 3.4 Phase 6 (traduction) — aucune modification liée au résumé

La phase 6 traduit l'intégralité du markdown consolidé : la section `## Résumé`
(libellé inclus) est donc traduite dans chaque langue de sortie comme le reste
du document — exactement comme `## Introduction générale` / `## Sommaire` /
`## Conclusion générale`, qui sont des libellés FR en dur traduits par le LLM.

## 4. Correctif inclus (indépendant) — comptabilité de coût Phase 6

Décision utilisateur : corriger dans le même travail.

Dans `pipeline/handlers/phase_6_translation.py`, `_produce_for_language`
récupère le coût de chaque traduction per-video (`translated, cost =
self._translate(...)`) mais **ne l'accumule jamais** : `per_video_cost` reste
figé à `0.0`, accompagné d'un commentaire qui reconnaît lui-même
l'approximation. Les coûts de traduction des documents per-video sont donc
absents du coût total remonté par la phase.

**Correctif** : accumuler le coût de chaque appel `_translate` per-video et
l'inclure dans la valeur retournée ; supprimer le bloc de commentaire obsolète
et la variable morte. Cela ne change pas le comportement fonctionnel, seulement
l'exactitude du coût remonté.

**Impact sur les tests existants.** Le coût total remonté par la phase 6
**augmente** (les traductions per-video étaient à 0). Vérification faite :
**aucun test existant n'asserte ce coût** — ni l'e2e
(`test_full_pipeline_produces_expected_outputs` ne contrôle pas le coût), ni les
tests unitaires actuels de la phase 6
(`test_execute_translates_for_target_language` ne vérifie que l'existence des
fichiers). Le correctif est donc couvert par un **nouveau** test dédié, sans
réajustement d'assertion préexistante.

## 5. Robustesse & rétrocompatibilité

- **Résumé absent ou vide** (ancien prompt surchargé en `%APPDATA%/Fahmi2/
  prompts/`, ou réponse LLM partielle) : aucune section `## Résumé` n'est
  émise — pas de section vide. Le document reste valide, identique à
  l'actuel. Même logique que le traitement existant de `introduction` /
  `conclusion`.
- **Override utilisateur du prompt** : un override `%APPDATA%` d'un ancien
  `phase_5_consolidation.j2` (sans `summary_markdown`) continue de fonctionner,
  le résumé est simplement omis (voir ci-dessus).

## 6. Tests

- `_assemble_consolidated` :
  - le `## Résumé` apparaît entre le `# titre` et `## Introduction générale`
    quand `summary_markdown` est fourni ;
  - aucune section `## Résumé` quand le champ est absent ou vide ;
  - le `## Résumé` n'apparaît pas dans le sommaire.
- Handler Phase 5 avec `FakeLLMProvider` renvoyant un `summary_markdown` :
  vérifier la présence du résumé dans l'artefact `consolidated_master.md`.
- Mise à jour des fixtures / réponses figées du `FakeLLMProvider` pour la phase 5
  si elles imposent le JSON de sortie exact (ajout du champ).
- Phase 6 : test vérifiant que le coût total inclut désormais les traductions
  per-video (réponses `FakeLLMProvider` à coût non nul, langue cible ≠ source).
- **E2e** (`tests/e2e/test_full_pipeline.py`) :
  - enrichir le scénario `consolidation` de `_llm_response_for_phase` avec un
    `summary_markdown` non vide ;
  - asserter la présence de `## Résumé` dans `consolidated_master.md`.
  - **Limite assumée** : on n'asserte pas le résumé dans les
    `output_dir/consolidated.{lang}.md`. Le fake LLM de la phase 7 (cohérence)
    réécrit l'intégralité de ces fichiers par du contenu fictif (branche
    `else` de `_llm_response_for_phase`) — comme il le fait déjà pour l'intro,
    la conclusion et les chapitres. L'e2e teste donc le câblage des phases, pas
    la fidélité du contenu post-LLM. La préservation du résumé par la
    traduction est garantie structurellement : la phase 6 passe l'intégralité
    du markdown consolidé au prompt de traduction (cf. §3.4).

## 7. Documentation à mettre à jour

- Docstrings du module et de `_assemble_consolidated` (phase 5).
- Toute description de la structure du document consolidé dans `docs/`
  (notamment `docs/02-presentation-technique.md` et
  `docs/01-presentation-fonctionnelle.md` si la structure y est détaillée).
- `CLAUDE.md` si la description du pipeline mentionne la structure du consolidé.

## 8. Hors périmètre

- Front matter YAML / métadonnées de document.
- Modification du sommaire pour y inclure les méta-sections.
- Toute refonte de la phase 6 au-delà du correctif de coût ci-dessus.
