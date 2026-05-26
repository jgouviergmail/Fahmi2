# Lot 3 — Prompts thématiques + catalogue

> Sous-skill d'exécution : superpowers:executing-plans. Étapes en `- [ ]`.

**But du lot :** Créer les 3 templates Jinja2 du mode thématique et les enregistrer
au catalogue `PromptsService` (éditables/overridables comme les autres).

**Contrats de variables et de sortie** (consommés par le Lot 4) :

| Template | Variables d'entrée | Sortie JSON |
|---|---|---|
| `phase_5_fact_ledger` | `output_language_label`, `structured_markdown` | `{"elements": [{"n", "type", "enonce", "donnees", "extrait_verbatim"}]}` |
| `phase_5_thematic_plan` | `output_language_label`, `elements_listing` | `{"global_title", "chapters": [{"title", "order", "element_ids": [...]}]}` |
| `phase_5_thematic_chapter` | `output_language_label`, `style_label`, `style_directives`, `chapter_title`, `elements_json` | `{"body_markdown", "used_element_ids": [...]}` |

> L'`id` global (`"source#n"`) est composé **côté code** (Lot 4) à partir du `n`
> de T1 ; T1 ne connaît pas le `source_id`.

---

### Task 3.1 : Template T1 `phase_5_fact_ledger.j2`

**Files:**
- Create: `src/fahmi2/infra/prompts/defaults/phase_5_fact_ledger.j2`

- [ ] **Step 1 : Écrire le template**

```jinja
Tu es un documentaliste rigoureux. À partir du document Markdown structuré ci-dessous, dresse le RELEVÉ EXHAUSTIF des éléments de contenu à préserver, en {{ output_language_label }}.

Un « élément » est une unité de fond à ne jamais perdre : un fait, un chiffre, une donnée, un raisonnement/argument, ou une affirmation. Découpe finement : un élément = une information autonome.

Règles STRICTES :
- EXHAUSTIVITÉ : ne laisse passer aucun fait, chiffre, donnée ou raisonnement du document.
- FIDÉLITÉ : n'invente rien, n'ajoute aucune information absente du document.
- Pour chaque élément, fournis :
  - "n" : numéro d'ordre entier (1, 2, 3, …) unique dans ce document.
  - "type" : un parmi "fait", "chiffre", "donnee", "raisonnement", "affirmation".
  - "enonce" : l'information formulée clairement et fidèlement (reformulation autorisée, sens préservé).
  - "donnees" : les chiffres/valeurs/données brutes associés s'il y en a, sinon "".
  - "extrait_verbatim" : un extrait LITTÉRAL du document (copie exacte) qui porte cette information — c'est la vérité de terrain.

Réponds STRICTEMENT en JSON valide :
{
  "elements": [
    {"n": 1, "type": "fait", "enonce": "...", "donnees": "", "extrait_verbatim": "..."}
  ]
}

---
Document Markdown structuré :

{{ structured_markdown }}
```

- [ ] **Step 2 : Test de rendu (PromptLoader rend le défaut)**

Dans `tests/unit/infra/prompts/test_thematic_prompts.py` :

```python
"""Tests de rendu des prompts thématiques (défauts bundlés)."""

from fahmi2.infra.prompts.loader import PromptLoader


def test_fact_ledger_renders() -> None:
    out = PromptLoader().render(
        "phase_5_fact_ledger",
        output_language_label="français",
        structured_markdown="# Titre\nDu contenu.",
    )
    assert "RELEVÉ EXHAUSTIF" in out
    assert "Du contenu." in out
```

- [ ] **Step 3 : Lancer → succès**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/infra/prompts/test_thematic_prompts.py::test_fact_ledger_renders -v`
Expected: PASS.

---

### Task 3.2 : Template T2 `phase_5_thematic_plan.j2`

**Files:**
- Create: `src/fahmi2/infra/prompts/defaults/phase_5_thematic_plan.j2`

- [ ] **Step 1 : Écrire le template**

```jinja
Tu es un rédacteur en chef. On te donne les éléments de contenu extraits de PLUSIEURS sources (chaque élément a un identifiant "id" et un énoncé). Conçois le PLAN THÉMATIQUE d'un document consolidé unique, en {{ output_language_label }}.

Objectif : regrouper les éléments par THÈME (et non par source), dans un ordre de lecture logique. Un document de synthèse comme le ferait un journaliste à partir de plusieurs sources.

Règles STRICTES :
- COUVERTURE : chaque "id" fourni doit être rattaché à AU MOINS un chapitre. N'oublie aucun id.
- Un id peut apparaître dans plusieurs chapitres s'il est transversal.
- CONFLITS : si plusieurs éléments traitent du MÊME point (en particulier s'ils se contredisent entre sources), place-les dans le MÊME chapitre, pour qu'ils soient traités ensemble.
- Ne rédige PAS le contenu ici : seulement les titres de chapitres et la liste des ids couverts.

Réponds STRICTEMENT en JSON valide :
{
  "global_title": "...",
  "chapters": [
    {"title": "...", "order": 1, "element_ids": ["s1#3", "s2#7"]}
  ]
}

---
Éléments par source (id — énoncé) :

{{ elements_listing }}
```

- [ ] **Step 2 : Test de rendu**

```python
def test_thematic_plan_renders() -> None:
    out = PromptLoader().render(
        "phase_5_thematic_plan",
        output_language_label="français",
        elements_listing="s1#1 — un fait",
    )
    assert "PLAN THÉMATIQUE" in out
    assert "s1#1 — un fait" in out
```

- [ ] **Step 3 : Lancer → succès**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/infra/prompts/test_thematic_prompts.py::test_thematic_plan_renders -v`
Expected: PASS.

---

### Task 3.3 : Template T3 `phase_5_thematic_chapter.j2`

**Files:**
- Create: `src/fahmi2/infra/prompts/defaults/phase_5_thematic_chapter.j2`

- [ ] **Step 1 : Écrire le template**

```jinja
Tu es un rédacteur de synthèse. Rédige UN chapitre d'un document consolidé, en {{ output_language_label }}, à partir UNIQUEMENT des éléments fournis ci-dessous (chacun avec son énoncé, ses données et un extrait verbatim de sa source).

Titre du chapitre : {{ chapter_title }}

Règles STRICTES (rigueur sur le fond) :
- N'utilise QUE le contenu fourni. N'invente RIEN, n'ajoute aucun fait, chiffre ou donnée absent des éléments.
- Préserve fidèlement tous les chiffres et données. En cas de doute, fie-toi à l'extrait_verbatim (vérité de terrain).
- CONFLITS : si des éléments se contredisent selon leur source, NE TRANCHE PAS. Présente les divergences en les attribuant à chaque source (« selon la source A… ; la source B indique au contraire… »), et tu peux en tirer une brève réflexion.

Souplesse sur la forme :
- Agrège, fusionne et déduplique les éléments redondants ; rédige des transitions fluides.
- Structure le corps avec des sous-titres Markdown `##` et `###` (PAS de titre `#` : le titre du chapitre est ajouté ensuite).
{% if style_directives -%}
- Style : {{ style_label }}. Directives : {{ style_directives }}
{%- else -%}
- Style : {{ style_label }}.
{%- endif %}

Indique aussi la liste des "id" d'éléments que tu as effectivement utilisés.

Réponds STRICTEMENT en JSON valide :
{
  "body_markdown": "## Sous-titre\n...",
  "used_element_ids": ["s1#3", "s2#7"]
}

---
Éléments assignés à ce chapitre :

{{ elements_json }}
```

- [ ] **Step 2 : Test de rendu**

```python
def test_thematic_chapter_renders() -> None:
    out = PromptLoader().render(
        "phase_5_thematic_chapter",
        output_language_label="français",
        style_label="académique",
        style_directives="",
        chapter_title="Origines",
        elements_json='[{"id": "s1#1"}]',
    )
    assert "UN chapitre" in out
    assert "Origines" in out
    assert "académique" in out
```

- [ ] **Step 3 : Lancer → succès**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/infra/prompts/test_thematic_prompts.py -v`
Expected: PASS (3 tests).

---

### Task 3.4 : Enregistrer au catalogue `PromptsService`

**Files:**
- Modify: `src/fahmi2/app/prompts_service.py`
- Test: `tests/unit/app/test_prompts_service.py`

- [ ] **Step 1 : Test — les 3 templates sont au catalogue**

```python
def test_catalog_includes_thematic_prompts() -> None:
    from fahmi2.app.prompts_service import PromptsService

    names = {m.name for m in PromptsService().list_templates()}
    assert {
        "phase_5_fact_ledger",
        "phase_5_thematic_plan",
        "phase_5_thematic_chapter",
    } <= names
```

> Adapter `PromptsService().list_templates()` au nom réel de la méthode de listing
> (vérifier dans `prompts_service.py` ; sinon lire directement `_TEMPLATE_METADATA`).

- [ ] **Step 2 : Lancer → échec**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/app/test_prompts_service.py -k thematic -v`
Expected: FAIL.

- [ ] **Step 3 : Ajouter les 3 entrées**

Dans `_TEMPLATE_METADATA` de `prompts_service.py`, **juste après** l'entrée
`phase_5_consolidation` (pour respecter l'ordre logique du pipeline) :

```python
    PromptTemplateMeta(
        name="phase_5_fact_ledger",
        display_name="Phase 5c — Relevé factuel (thématique)",
        description=(
            "Mode thématique : extrait par source le relevé exhaustif des "
            "éléments à préserver (faits, chiffres, données, raisonnements) "
            "avec extraits verbatim."
        ),
    ),
    PromptTemplateMeta(
        name="phase_5_thematic_plan",
        display_name="Phase 5d — Plan thématique",
        description=(
            "Mode thématique : conçoit le plan transversal (chapitres par "
            "thème) en rattachant chaque élément à au moins un chapitre."
        ),
    ),
    PromptTemplateMeta(
        name="phase_5_thematic_chapter",
        display_name="Phase 5e — Rédaction de chapitre thématique",
        description=(
            "Mode thématique : rédige un chapitre à partir des éléments "
            "assignés (fusion, dédup, transitions, conflits par source)."
        ),
    ),
```

- [ ] **Step 4 : Lancer → succès**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/app/test_prompts_service.py -k thematic -v`
Expected: PASS.

- [ ] **Step 5 : Vérifs de lot + commit**

```powershell
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m mypy src tests
git add src/fahmi2/infra/prompts/defaults/phase_5_fact_ledger.j2
git add src/fahmi2/infra/prompts/defaults/phase_5_thematic_plan.j2
git add src/fahmi2/infra/prompts/defaults/phase_5_thematic_chapter.j2
git add src/fahmi2/app/prompts_service.py
git add tests/unit/infra/prompts/test_thematic_prompts.py tests/unit/app/test_prompts_service.py
git commit -m "feat(prompts): 3 templates du mode consolidation thematique + catalogue"
```
