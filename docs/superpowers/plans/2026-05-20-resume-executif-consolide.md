# Résumé exécutif dans le document consolidé — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ajouter une section `## Résumé` (abstract de 3-5 phrases) sous le titre du document consolidé, générée par le LLM, et corriger au passage la comptabilité de coût per-video de la phase 6.

**Architecture:** Le résumé est produit par le même appel LLM que les autres méta-éléments (champ `summary_markdown` ajouté au prompt `phase_5_consolidation.j2`), puis inséré de façon déterministe par `_assemble_consolidated` entre le `# titre` et `## Introduction générale`. La phase 6 le traduit avec le reste du document (aucune modif) ; la phase 7 est avertie de son existence pour ne pas le supprimer. Insertion conditionnelle (omise si vide) pour rétrocompatibilité.

**Tech Stack:** Python 3.12, Jinja2 (prompts), pytest, ruff, mypy. Interpréteur : `.venv\Scripts\python.exe`.

**Spec de référence :** [docs/superpowers/specs/2026-05-20-resume-executif-consolide-design.md](../specs/2026-05-20-resume-executif-consolide-design.md)

---

## Notes transverses (à lire avant de commencer)

- **Couplage prompt ↔ e2e.** Le fake LLM e2e (`tests/e2e/test_full_pipeline.py`, `_RotatingFakeLLM.chat`) route par sous-chaîne du prompt. **Ne jamais supprimer** la phrase « rédige les méta-éléments » du prompt phase 5, ni « passe de cohérence » du prompt phase 7. Les tâches 2 et 3 incluent un test qui le verrouille.
- **Accents.** Tous les libellés et docstrings en français avec accents corrects (jamais d'ASCII de substitution).
- **Commits.** Une étape de commit clôt chaque tâche. Ne committer que si l'utilisateur a autorisé l'exécution.

---

## Task 1: Insertion de la section `## Résumé` dans `_assemble_consolidated`

**Files:**
- Modify: `src/fahmi2/pipeline/handlers/phase_5_consolidation.py`
- Test: `tests/unit/pipeline/handlers/test_phase_5_consolidation.py`

- [ ] **Step 1: Écrire les tests qui échouent**

Ajouter ces fonctions à la fin de `tests/unit/pipeline/handlers/test_phase_5_consolidation.py` :

```python
def test_assemble_consolidated_includes_summary_between_title_and_intro() -> None:
    structured_by_video = {"v1": "# Chap\n## Sec\ntexte\n"}
    summaries = [{"video_id": "v1", "title": "Chap"}]
    meta = {
        "global_title": "Mon Cours",
        "summary_markdown": "Un abstract synthétique du cours.",
        "introduction_markdown": "Intro développée.",
        "conclusion_markdown": "Conclusion.",
    }
    md = _assemble_consolidated(meta, structured_by_video, summaries)
    assert "## Résumé" in md
    assert "Un abstract synthétique du cours." in md
    # Ordre : titre < résumé < introduction
    assert md.index("# Mon Cours") < md.index("## Résumé")
    assert md.index("## Résumé") < md.index("## Introduction générale")


def test_assemble_consolidated_omits_summary_when_empty() -> None:
    structured_by_video = {"v1": "# Chap\n"}
    summaries = [{"video_id": "v1", "title": "Chap"}]
    meta = {
        "global_title": "T",
        "summary_markdown": "   ",
        "introduction_markdown": "Intro.",
        "conclusion_markdown": "",
    }
    md = _assemble_consolidated(meta, structured_by_video, summaries)
    assert "## Résumé" not in md


def test_assemble_consolidated_omits_summary_when_key_missing() -> None:
    structured_by_video = {"v1": "# Chap\n"}
    summaries = [{"video_id": "v1", "title": "Chap"}]
    meta = {"global_title": "T", "introduction_markdown": "", "conclusion_markdown": ""}
    md = _assemble_consolidated(meta, structured_by_video, summaries)
    assert "## Résumé" not in md


def test_assemble_consolidated_summary_not_referenced_in_toc() -> None:
    structured_by_video = {"v1": "# Chap\n## Sec\ntexte\n"}
    summaries = [{"video_id": "v1", "title": "Chap"}]
    meta = {
        "global_title": "T",
        "summary_markdown": "Abstract.",
        "introduction_markdown": "",
        "conclusion_markdown": "",
    }
    md = _assemble_consolidated(meta, structured_by_video, summaries)
    # La portion sommaire (entre "## Sommaire" et le 1er chapitre) ne cite pas le résumé.
    toc = md.split("## Sommaire", 1)[1].split("# 1.", 1)[0]
    assert "Résumé" not in toc
```

- [ ] **Step 2: Lancer les tests pour vérifier qu'ils échouent**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/pipeline/handlers/test_phase_5_consolidation.py -k summary -v`
Expected: FAIL (les 4 tests échouent : `## Résumé` absent du document).

- [ ] **Step 3: Ajouter la constante de libellé**

Dans `src/fahmi2/pipeline/handlers/phase_5_consolidation.py`, juste après la ligne `_TEMPLATE_CONSOLIDATION = "phase_5_consolidation"` :

```python
_TEMPLATE_CONSOLIDATION = "phase_5_consolidation"

# Libellé de la section résumé exécutif (placée sous le titre, avant l'intro).
_SUMMARY_HEADING = "Résumé"
```

- [ ] **Step 4: Implémenter l'insertion conditionnelle**

Dans `_assemble_consolidated`, remplacer ce bloc :

```python
    title = str(meta.get("global_title", "Document consolidé"))
    introduction = str(meta.get("introduction_markdown", "")).strip()
    conclusion = str(meta.get("conclusion_markdown", "")).strip()
    titles_by_video = {s.get("video_id", ""): s.get("title", "") for s in summaries}

    chapters = _build_chapters(structured_by_video, titles_by_video)

    parts: list[str] = [f"# {title}", ""]
    if introduction:
        parts.extend(["## Introduction générale", "", introduction, ""])
```

par :

```python
    title = str(meta.get("global_title", "Document consolidé"))
    summary = str(meta.get("summary_markdown", "")).strip()
    introduction = str(meta.get("introduction_markdown", "")).strip()
    conclusion = str(meta.get("conclusion_markdown", "")).strip()
    titles_by_video = {s.get("video_id", ""): s.get("title", "") for s in summaries}

    chapters = _build_chapters(structured_by_video, titles_by_video)

    parts: list[str] = [f"# {title}", ""]
    if summary:
        parts.extend([f"## {_SUMMARY_HEADING}", "", summary, ""])
    if introduction:
        parts.extend(["## Introduction générale", "", introduction, ""])
```

- [ ] **Step 5: Lancer les tests pour vérifier qu'ils passent**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/pipeline/handlers/test_phase_5_consolidation.py -k summary -v`
Expected: PASS (4 tests).

- [ ] **Step 6: Enrichir le test d'intégration handler existant**

Dans `test_execute_assembles_consolidated_markdown`, modifier `meta_json` pour inclure le résumé :

```python
    meta_json = json.dumps(
        {
            "global_title": "Mon Cours",
            "summary_markdown": "Vue d'ensemble du cours en quelques phrases.",
            "introduction_markdown": "Texte d'intro.",
            "plan_markdown": "1. Un\n2. Deux",
            "conclusion_markdown": "Texte de conclusion.",
        }
    )
```

Et ajouter cette assertion juste après `assert "# Mon Cours" in content` :

```python
    # Le résumé exécutif apparaît sous le titre
    assert "## Résumé" in content
    assert "Vue d'ensemble du cours en quelques phrases." in content
```

- [ ] **Step 7: Mettre à jour les docstrings du fichier**

Dans la docstring de **module** (haut du fichier), remplacer :

```
2. **Consolidation globale** : un unique appel LLM ``phase_5_consolidation``
   reçoit tous les résumés condensés et produit les *méta-éléments* (titre,
   introduction générale, plan d'ensemble, conclusion générale).
```

par :

```
2. **Consolidation globale** : un unique appel LLM ``phase_5_consolidation``
   reçoit tous les résumés condensés et produit les *méta-éléments* (titre,
   résumé exécutif, introduction générale, plan d'ensemble, conclusion
   générale).
```

Dans la docstring de `_assemble_consolidated`, remplacer la liste numérotée de structure :

```
    1. ``# <titre global>``
    2. ``## Introduction générale`` (texte narratif du LLM, non numéroté)
    3. ``## Sommaire`` (liste hiérarchique avec ancres GitHub vers chaque
       titre numéroté : chapitres + sections ## et sous-sections ###)
    4. Chapitres : ``# 1. <titre>``, ``# 2. <titre>``…  À l'intérieur d'un
       chapitre, les ``##`` deviennent ``## N.M <titre>`` et les ``###``
       deviennent ``### N.M.P <titre>``. Les numérotations posées
       précédemment par le LLM (« 1. », « 1.1 »…) sont systématiquement
       décapées avant d'écrire la nouvelle.
    5. ``## Conclusion générale`` (non numéroté)
```

par :

```
    1. ``# <titre global>``
    2. ``## Résumé`` (abstract synthétique du LLM, non numéroté ; omis si
       ``summary_markdown`` est vide ou absent)
    3. ``## Introduction générale`` (texte narratif du LLM, non numéroté)
    4. ``## Sommaire`` (liste hiérarchique avec ancres GitHub vers chaque
       titre numéroté : chapitres + sections ## et sous-sections ###)
    5. Chapitres : ``# 1. <titre>``, ``# 2. <titre>``…  À l'intérieur d'un
       chapitre, les ``##`` deviennent ``## N.M <titre>`` et les ``###``
       deviennent ``### N.M.P <titre>``. Les numérotations posées
       précédemment par le LLM (« 1. », « 1.1 »…) sont systématiquement
       décapées avant d'écrire la nouvelle.
    6. ``## Conclusion générale`` (non numéroté)
```

Et dans la section `Args:` de la même docstring, remplacer :

```
        meta: Méta-éléments produits par la consolidation (title, intro,
            plan, conclusion). ``plan_markdown`` est ignoré : le sommaire
            est déterministe.
```

par :

```
        meta: Méta-éléments produits par la consolidation (title, summary,
            intro, plan, conclusion). ``plan_markdown`` est ignoré : le
            sommaire est déterministe.
```

- [ ] **Step 8: Relancer tous les tests de la phase 5**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/pipeline/handlers/test_phase_5_consolidation.py -v`
Expected: PASS (tous, y compris les tests préexistants).

- [ ] **Step 9: Commit**

```bash
git add src/fahmi2/pipeline/handlers/phase_5_consolidation.py tests/unit/pipeline/handlers/test_phase_5_consolidation.py
git commit -m "feat(consolidation): inserer une section Resume sous le titre du document consolide"
```

---

## Task 2: Demander le résumé exécutif dans le prompt phase 5

**Files:**
- Modify: `src/fahmi2/infra/prompts/defaults/phase_5_consolidation.j2`
- Test: `tests/unit/infra/prompts/test_prompt_loader.py`

- [ ] **Step 1: Écrire le test qui échoue**

Ajouter à `tests/unit/infra/prompts/test_prompt_loader.py` :

```python
def test_render_phase_5_consolidation_requests_summary() -> None:
    loader = PromptLoader()
    rendered = loader.render(
        "phase_5_consolidation",
        output_language_label="français",
        style_label="standard",
        style_directives="",
        summaries_json="[]",
    )
    # Le champ de sortie JSON est demandé
    assert "summary_markdown" in rendered
    # La consigne de résumé exécutif est présente
    assert "Résumé exécutif" in rendered
    # La phrase de routage du fake e2e est préservée
    assert "rédige les méta-éléments" in rendered
```

- [ ] **Step 2: Lancer le test pour vérifier qu'il échoue**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/infra/prompts/test_prompt_loader.py::test_render_phase_5_consolidation_requests_summary -v`
Expected: FAIL (`summary_markdown` absent du prompt).

- [ ] **Step 3: Modifier le prompt**

Remplacer l'intégralité de `src/fahmi2/infra/prompts/defaults/phase_5_consolidation.j2` par :

```jinja
Tu es un rédacteur en chef qui prépare la préface, le plan d'ensemble et la conclusion d'un document consolidé.

À partir des résumés condensés de chaque vidéo ci-dessous (titre + plan + idées-clés), rédige les méta-éléments suivants en {{ output_language_label }} pour le document consolidé :

1. **Titre global** : titre du document consolidé (une ligne, percutant et fidèle au sujet).
2. **Résumé exécutif** : un abstract synthétique de l'ensemble du document, en un seul paragraphe de 3 à 5 phrases. Il offre au lecteur une vue « en 30 secondes » : de quoi traite le document, ses principaux apports et son public. NE REPRENDS PAS le contenu de l'introduction générale — le résumé est plus court et plus dense ; l'introduction développe le contexte, les objectifs et le fil conducteur.
3. **Introduction générale** : 2 à 4 paragraphes qui présentent l'ensemble du document, son contexte, ses objectifs et son fil conducteur.
4. **Plan d'ensemble** : liste ordonnée des chapitres (un par vidéo) avec en bullet, le titre court et 1-2 phrases présentant ce que le chapitre apporte.
5. **Conclusion générale** : 2 à 3 paragraphes qui synthétisent les apports du document et ouvrent vers des approfondissements.

NE RÉÉCRIS PAS les contenus détaillés des vidéos : ils seront recopiés tels quels comme chapitres entre l'introduction et la conclusion.

Style : {{ style_label }}.
{% if style_directives -%}
Directives stylistiques : {{ style_directives }}
{%- endif %}

Réponds STRICTEMENT en JSON valide :
{
  "global_title": "...",
  "summary_markdown": "...",
  "introduction_markdown": "...",
  "plan_markdown": "...",
  "conclusion_markdown": "..."
}

---
Résumés condensés par vidéo :

{{ summaries_json }}
```

- [ ] **Step 4: Lancer le test ciblé + le smoke test de chargement**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/infra/prompts/test_prompt_loader.py -v`
Expected: PASS (le nouveau test + `test_all_phase_templates_are_loadable` confirmant que le template reste un Jinja2 valide).

- [ ] **Step 5: Commit**

```bash
git add src/fahmi2/infra/prompts/defaults/phase_5_consolidation.j2 tests/unit/infra/prompts/test_prompt_loader.py
git commit -m "feat(prompts): demander un resume executif (summary_markdown) en phase 5"
```

---

## Task 3: Avertir la phase 7 (cohérence) de l'existence du résumé

**Files:**
- Modify: `src/fahmi2/infra/prompts/defaults/phase_7_coherence.j2`
- Test: `tests/unit/infra/prompts/test_prompt_loader.py`

- [ ] **Step 1: Écrire le test qui échoue**

Ajouter à `tests/unit/infra/prompts/test_prompt_loader.py` :

```python
def test_render_phase_7_coherence_mentions_summary() -> None:
    loader = PromptLoader()
    rendered = loader.render(
        "phase_7_coherence",
        output_language_label="français",
        style_label="standard",
        style_directives="",
        glossary_terms=[],
        consolidated_markdown="# t",
    )
    # Le résumé exécutif fait partie des méta-éléments à relire
    assert "résumé exécutif" in rendered.lower()
    # La phrase de routage du fake e2e est préservée
    assert "passe de cohérence" in rendered.lower()
```

- [ ] **Step 2: Lancer le test pour vérifier qu'il échoue**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/infra/prompts/test_prompt_loader.py::test_render_phase_7_coherence_mentions_summary -v`
Expected: FAIL (« résumé exécutif » absent de la liste).

- [ ] **Step 3: Modifier le prompt**

Dans `src/fahmi2/infra/prompts/defaults/phase_7_coherence.j2`, remplacer la ligne :

```
À partir du document Markdown consolidé ci-dessous en {{ output_language_label }}, réalise une passe de cohérence ciblée SUR LES MÉTA-ÉLÉMENTS UNIQUEMENT (titre global, introduction générale, plan d'ensemble, conclusion générale, transitions entre chapitres) :
```

par :

```
À partir du document Markdown consolidé ci-dessous en {{ output_language_label }}, réalise une passe de cohérence ciblée SUR LES MÉTA-ÉLÉMENTS UNIQUEMENT (titre global, résumé exécutif, introduction générale, plan d'ensemble, conclusion générale, transitions entre chapitres) :
```

- [ ] **Step 4: Lancer les tests des prompts**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/infra/prompts/test_prompt_loader.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/fahmi2/infra/prompts/defaults/phase_7_coherence.j2 tests/unit/infra/prompts/test_prompt_loader.py
git commit -m "feat(prompts): inclure le resume executif dans la passe de coherence (phase 7)"
```

---

## Task 4: Corriger la comptabilité de coût per-video de la phase 6

**Files:**
- Modify: `src/fahmi2/pipeline/handlers/phase_6_translation.py` (`_produce_for_language`)
- Test: `tests/unit/pipeline/handlers/test_phase_6_translation.py`

- [ ] **Step 1: Écrire le test qui échoue**

Ajouter à `tests/unit/pipeline/handlers/test_phase_6_translation.py` :

```python
def test_execute_accumulates_per_video_translation_cost(
    tmp_path: Path, make_settings: Any
) -> None:
    video = VideoExecution(video_id=VideoId.new(), source_path=tmp_path / "v.mp4")
    ctx, _ = build_phase_context(
        tmp_path,
        make_settings,
        llm_response=_llm("Translated."),  # cost_usd=0.01 par appel
        videos=(video,),
        settings_overrides={
            "source_language": Language.FR,
            "output_languages": (Language.FR, Language.EN),
        },
    )
    _seed_workspace(ctx.workspace, videos=(video,))
    handler = Phase6TranslationHandler()
    result = handler.execute(ctx, video=None)
    # FR = source -> copies gratuites. EN -> 3 appels : 1 per-video + consolidated
    # + glossaire, chacun 0.01 = 0.03. Avant correctif : 0.02 (per-video ignoré).
    assert result.cost_usd == pytest.approx(0.03)
```

- [ ] **Step 2: Lancer le test pour vérifier qu'il échoue**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/pipeline/handlers/test_phase_6_translation.py::test_execute_accumulates_per_video_translation_cost -v`
Expected: FAIL (`0.02 != 0.03` — le coût per-video n'est pas compté).

- [ ] **Step 3: Implémenter le correctif**

Dans `_produce_for_language`, ajouter l'initialisation juste après la première ligne :

```python
        is_source = target is ctx.settings.source_language
        per_video_cost = 0.0
```

Dans la boucle per-video, ajouter l'accumulation après l'écriture du fichier traduit :

```python
            translated, cost = self._translate(ctx, structured_md, target, glossary_master_payload)
            ctx.artifacts.write_text_atomic(target_path, translated)
            per_video_cost += cost
```

Enfin, remplacer le bloc de fin (commentaire obsolète + variable morte) :

```python
        # Cumul (les coûts par-vidéo sont déjà comptés dans les _translate ci-dessus)
        per_video_cost = 0.0
        if not is_source:
            # Re-calculer le coût des appels de traduction des per-video :
            # déjà imputé dans _translate ; on a juste à le retracer ici.
            # Pour simplicité, on s'appuie sur le total accumulé via FakeLLM.
            # Cette branche est laissée à 0 car les coûts ont déjà été émis.
            pass

        return consolidated_cost + glossary_cost + per_video_cost
```

par :

```python
        return consolidated_cost + glossary_cost + per_video_cost
```

- [ ] **Step 4: Lancer les tests de la phase 6**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/pipeline/handlers/test_phase_6_translation.py -v`
Expected: PASS (nouveau test + les 4 préexistants).

- [ ] **Step 5: Commit**

```bash
git add src/fahmi2/pipeline/handlers/phase_6_translation.py tests/unit/pipeline/handlers/test_phase_6_translation.py
git commit -m "fix(translation): comptabiliser le cout des traductions per-video (phase 6)"
```

---

## Task 5: Couverture e2e du résumé

**Files:**
- Modify: `tests/e2e/test_full_pipeline.py`

- [ ] **Step 1: Enrichir le scénario consolidation du fake LLM**

Dans `_llm_response_for_phase`, remplacer le bloc `consolidation` :

```python
    elif "consolidation" in phase_name and "video_summary" not in phase_name:
        content = json.dumps(
            {
                "global_title": "Cours d'économie",
                "introduction_markdown": "Introduction.",
                "plan_markdown": "1. Chapitre 1\n2. Chapitre 2",
                "conclusion_markdown": "Conclusion.",
            }
        )
```

par :

```python
    elif "consolidation" in phase_name and "video_summary" not in phase_name:
        content = json.dumps(
            {
                "global_title": "Cours d'économie",
                "summary_markdown": "Vue d'ensemble synthétique du cours.",
                "introduction_markdown": "Introduction.",
                "plan_markdown": "1. Chapitre 1\n2. Chapitre 2",
                "conclusion_markdown": "Conclusion.",
            }
        )
```

- [ ] **Step 2: Ajouter l'assertion de présence du résumé dans le master**

Dans `test_full_pipeline_produces_expected_outputs`, juste après la ligne
`assert (workspace / "consolidated_master.md").exists()`, ajouter :

```python
    # Le document consolidé master s'ouvre sur la section Résumé (sous le titre).
    master_md = (workspace / "consolidated_master.md").read_text(encoding="utf-8")
    assert "## Résumé" in master_md
    assert "Vue d'ensemble synthétique du cours." in master_md
```

> Rappel : on n'asserte **pas** `## Résumé` dans `output_dir/consolidated.{lang}.md`. Le fake LLM de la phase 7 réécrit ces fichiers par du contenu fictif (branche `else`), comme il le fait déjà pour l'intro/conclusion. C'est une limite assumée de l'e2e (cf. spec §6).

- [ ] **Step 3: Lancer l'e2e**

Run: `.venv\Scripts\python.exe -m pytest tests/e2e/test_full_pipeline.py -v`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add tests/e2e/test_full_pipeline.py
git commit -m "test(e2e): verifier la presence du resume dans le document consolide master"
```

---

## Task 6: Documentation utilisateur et fonctionnelle

**Files:**
- Modify: `docs/01-presentation-fonctionnelle.md`
- Modify: `docs/05-exploitation.md`

- [ ] **Step 1: Tableau des phases (présentation fonctionnelle)**

Dans `docs/01-presentation-fonctionnelle.md`, remplacer la ligne du tableau :

```
| 5. Consolidation | Production des méta-éléments (titre global, introduction générale, plan, conclusion générale) pour un document consolidé |
```

par :

```
| 5. Consolidation | Production des méta-éléments (titre global, résumé exécutif, introduction générale, plan, conclusion générale) pour un document consolidé |
```

- [ ] **Step 2: Description du fichier de sortie (présentation fonctionnelle)**

Dans `docs/01-presentation-fonctionnelle.md`, sous `- \`consolidated.{lang}.md\` — document consolidé navigable :`, remplacer :

```
  - Titre global + introduction générale.
```

par :

```
  - Titre global, **résumé exécutif** (abstract synthétique), puis introduction générale.
```

- [ ] **Step 3: Format des fichiers (exploitation)**

Dans `docs/05-exploitation.md`, sous `- **Document consolidé** :`, remplacer :

```
  - Titre global + introduction générale.
```

par :

```
  - Titre global, **résumé exécutif** (abstract synthétique), puis introduction générale.
```

- [ ] **Step 4: Vérifier qu'aucune autre description de structure n'est à jour**

Run: `.venv\Scripts\python.exe -m pytest -q` n'est pas concerné ici ; vérifier visuellement que `docs/02-presentation-technique.md` (ligne ~295) ne décrit que l'arborescence de fichiers (pas la structure interne) — aucune modif requise. `CLAUDE.md` ne détaille pas la structure interne du consolidé — aucune modif requise.

- [ ] **Step 5: Commit**

```bash
git add docs/01-presentation-fonctionnelle.md docs/05-exploitation.md
git commit -m "docs: documenter le resume executif dans le document consolide"
```

---

## Task 7: Repasse qualité finale (obligatoire, zéro défaut)

**Files:** aucun (vérification globale ; corriger si nécessaire).

- [ ] **Step 1: Suite de tests complète**

Run: `.venv\Scripts\python.exe -m pytest`
Expected: PASS (aucun échec, aucun test cassé par les changements).

- [ ] **Step 2: Lint**

Run: `.venv\Scripts\python.exe -m ruff check .`
Expected: « All checks passed! »

- [ ] **Step 3: Typage**

Run: `.venv\Scripts\python.exe -m mypy src tests`
Expected: « Success: no issues found ».

- [ ] **Step 4: Corriger et reboucler si besoin**

Si l'une des trois commandes signale un défaut, le corriger puis **relancer les trois** jusqu'à ce qu'elles soient toutes vertes. Ne pas considérer la tâche terminée tant que `pytest`, `ruff` et `mypy` ne sont pas tous propres.

- [ ] **Step 5: Commit final (si des corrections ont été apportées en Step 4)**

```bash
git add -A
git commit -m "chore: repasse qualite (tests, ruff, mypy) pour le resume executif"
```
