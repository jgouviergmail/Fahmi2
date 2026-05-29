# Fonctionnalité « Visualisations » — Plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: `superpowers:executing-plans` (exécution
> **inline**, sans subagents — règle absolue du projet, cf. mémoire
> `feedback-execution-inline-no-subagents`). Les étapes utilisent la syntaxe checkbox
> (`- [ ]`) pour le suivi.

**Goal:** Ajouter une 4ᵉ fonctionnalité « Visualisations » produisant, depuis les
livrables de la Génération, deux pages HTML pleinement autonomes par langue latine :
(A) une carte de connaissances interactive et (B) une galerie de schémas/diagrammes.

**Architecture:** Fonctionnalité sœur de Pédagogie (orchestrateur léger lisant le disque,
manifeste de fraîcheur, `run_state.json`, onglet dédié). Pipeline « GraphRAG-lite »
(squelette déterministe glossaire+sections → extraction sémantique LLM + gleaning →
résolution d'entités par embeddings → communautés Louvain pur-Python → community reports
→ idea-chains map-reduce → diagrammes). Multilingue par traduction de libellés (structure
extraite une fois). Rendu déterministe **zéro-DSL** : un seul moteur **Cytoscape.js**
vendorisé inline (graphes) + HTML/CSS (diagrammes linéaires). Couches respectées
(UI → app → visuals/infra → domain/core).

**Tech Stack:** Python 3.12, PySide6, DeepSeek (LLM), OpenAI (embeddings),
`networkx` (Louvain, **nouvelle dép. pure Python**), Cytoscape.js + `fcose` + `dagre` +
`expand-collapse` (**assets MIT vendorisés**), Jinja2 (prompts), SQLite (blob projet),
pytest/ruff/mypy.

**Spec de référence :** `docs/superpowers/specs/2026-05-29-visualisations-html-autonomes-design.md`

---

## Méthode de travail (consigne utilisateur — `docs/JGO/doc.txt`)

Boucle **phase par phase**, **inline**, sans subagents :

1. (Plan de la phase déjà écrit / à détailler juste-à-temps.)
2. **Implémenter** la phase en TDD, commits fréquents.
3. **Fin de phase = vérification approfondie obligatoire** : suite de tests **complète**
   + `ruff check .` + `mypy --strict src tests` (anti-régression), **plus** revue de code
   sur la checklist ci-dessous, **jusqu'à pleine conviction** (repasses tant que défaut).
4. **Détailler le plan de la phase suivante** (repasses jusqu'à pleine conviction), puis
   implémenter. Idem jusqu'à la dernière phase.
5. **Fin du chantier** : revue de code **exhaustive de toute la branche**, rigoureuse,
   jusqu'à pleine conviction.

**Checklist de revue (chaque fin de phase) :** complétude vs spec ; constantes centralisées
(zéro magic string/number/défaut épars) ; conformité aux patterns existants (réutilisation
classes/méthodes/helpers/constantes/mixins/bases) ; Google Python Style (docstrings
Args/Returns/Raises, docstring module sur chaque fichier) ; cohérence de nommage + passage
correct des arguments ; patterns du framework ; DRY/YAGNI/KISS/SRP/SoC/Boy Scout/Composition
over Inheritance ; code générique et extensible ; mise à jour de **toute** la doc (`docs/`,
`README.md`, `CLAUDE.md`, `packaging/README.md`).

> **Détail just-à-temps :** seule la **Phase 0** est entièrement détaillée (bite-sized/TDD)
> ci-dessous. Les **Phases 1→8** sont décrites au niveau feuille de route (objectif,
> fichiers, tâches clés) ; chacune sera détaillée bite-sized **juste avant** son
> implémentation, après la revue de la phase précédente.

---

## Feuille de route (phases 0→8)

Ordre = dépendances ascendantes ; chaque phase produit un logiciel testable.

| Phase | Titre | Produit testable |
|-------|-------|------------------|
| **0** | Fondations : `core/corpus` + domain (enums, entités, `VisualsSettings`) | parser de sections + entités validées ; suite existante verte |
| **1** | Chargement + squelette déterministe + extraction sémantique (+ gleaning) | `KnowledgeGraph` partiel (langue source) depuis disque |
| **2** | Résolution d'entités + communautés Louvain + community reports + idea-chains | `KnowledgeGraph` complet, cohérent, communautés étiquetées |
| **3** | Diagrammes (extraction → modèles `Diagram` typés) | `DiagramBoard` (langue source) |
| **4** | Multilingue : traduction de libellés + résolution d'extraits par `section_path` | graphe + board localisés (5 langues latines) |
| **5** | Rendu HTML autonome (Cytoscape vendorisé + HTML/CSS) + design system | `knowledge_map.{lang}.html` + `diagrams.{lang}.html` autonomes |
| **6** | Orchestrateur + manifeste + `run_state` + `VisualsCostEstimator` + blob v2 | pipeline complet déclenchable, fraîcheur/reprise/coût |
| **7** | UI (onglet, contrôleur, viewmodels, réglages, progression, event bus, ouverture) | onglet « Visualisations » fonctionnel |
| **8** | i18n + packaging (`.spec`, networkx, assets) + documentation | build portable + traductions + docs à jour |

### Fichiers par phase (décomposition)

- **Phase 0** — `core/corpus/__init__.py`, `core/corpus/structure.py` (déplace `Chapter`/
  `parse_chapters` + ajoute `Section`/`parse_sections`) ; suppression
  `pedagogy/chapters.py` + maj des 15 imports ; `domain/enums.py` (+3 enums) ;
  `domain/visuals.py` (entités + `VisualsSettings`). Tests : `tests/unit/core/corpus/
  test_structure.py`, `tests/unit/domain/test_visuals.py`.
- **Phase 1** — `visuals/__init__.py`, `visuals/_constants.py`, `visuals/sources.py`
  (charge consolidé+glossaire, construit les unités de texte + squelette `GLOSSARY_TERM`),
  `visuals/extractors/__init__.py`, `visuals/extractors/_base.py` (JSON typé + retry, calqué
  `pedagogy/generators/_base.py`), `visuals/extractors/graph_extractor.py` (+ gleaning),
  `infra/prompts/defaults/visuals_graph_extraction.j2`. Tests associés.
- **Phase 2** — `visuals/extractors/entity_resolver.py`, `visuals/community.py`
  (`networkx`), `visuals/extractors/community_reporter.py`,
  `visuals/extractors/idea_chains.py`, prompts `visuals_entity_canonicalize.j2`,
  `visuals_community_report.j2`, `visuals_idea_chains.j2`. Tests.
- **Phase 3** — `visuals/extractors/diagram_author.py`,
  `infra/prompts/defaults/visuals_diagram_authoring.j2`. Tests.
- **Phase 4** — `visuals/extractors/label_translator.py`, `visuals/excerpts.py`
  (résolution par `section_path` → passage langue cible), prompt
  `visuals_label_translation.j2`. Tests.
- **Phase 5** — `infra/export/_assets/visuals/*.js` (vendorisés), `infra/export/
  _visuals_assets.py` (résolution + inline), `infra/export/knowledge_map_html.py`,
  `infra/export/diagram_board_html.py`, gabarits CSS/JS. Tests (garde-fous autonomie).
- **Phase 6** — `visuals/events.py`, `visuals/manifest.py`, `visuals/run_state.py`,
  `visuals/orchestrator.py`, `app/visuals_cost_estimator.py` ; maj `domain/project.py`
  + `infra/storage/sqlite_state.py` (blob v2 clé `visuals`). Tests.
- **Phase 7** — `ui/features/visuals_tab.py` (+ enregistrement `FeatureRegistry`),
  `ui/visuals_controller.py`, `ui/viewmodels/visuals_state.py`,
  `ui/dialogs/visuals_settings_view.py`, `ui/qt_event_bus.py` (+`VisualsQtEventBus`),
  `ui/visuals_labels.py`, maj `PromptsService`/PromptsEditor (catalogue),
  `ui/app_main.py` (DI). Tests viewmodels + smoke widgets.
- **Phase 8** — `scripts/i18n_*` (extraction/compilation), `tests/unit/i18n/` (garde-fous),
  `packaging/fahmi2.spec` (networkx + datas assets), `README.md`, `docs/`, `CLAUDE.md`,
  `packaging/README.md`.

### Couverture de la spec (validation de complétude)

| Spec | Phase(s) |
|------|----------|
| §1 périmètre, 2 livrables, latin, autonomie, densité | 1–8 (transverse) |
| §2 principe + alignement GraphRAG | 1, 2 |
| §3.1 enums / §3.2 entités | 0 |
| §4 pipeline (chargement→rendu→persistance) | 1, 2, 3, 4, 5, 6 |
| §5 multilingue (libellés + extraits par `section_path`) | 4 |
| §6 rendu autonome zéro-DSL + design system + vendoring | 5 |
| §7 orchestration/fraîcheur/coût/parallélisme | 6 |
| §8 `VisualsSettings` + blob v2 | 0 (settings), 6 (persistance) |
| §9 UI | 7 |
| §10 coût | 6 |
| §11 `core/corpus` relocalisé | 0 |
| §12 tests (chemin de données + garde-fous) | toutes |
| §13 constantes + cas dégénérés | 1 (`_constants`), transverse |
| §14 dépendances (networkx + assets) | 5 (assets), 8 (packaging) |
| §15 documentation | 8 |

---

## PHASE 0 — Fondations (`core/corpus` + domain)

**Objectif :** poser les briques pures réutilisées partout, **sans aucune régression**.
Aucune dépendance LLM/Qt. À la fin, `parse_sections` expose le `section_path` et les
entités/enums du domaine sont validées.

**Files:**
- Create: `src/fahmi2/core/corpus/__init__.py`
- Create: `src/fahmi2/core/corpus/structure.py`
- Delete: `src/fahmi2/pedagogy/chapters.py`
- Modify (imports `fahmi2.pedagogy.chapters` → `fahmi2.core.corpus`) :
  `src/fahmi2/chat/corpus.py`, `src/fahmi2/app/pedagogy_cost_estimator.py`,
  `src/fahmi2/app/supports_orchestrator.py`, `src/fahmi2/pedagogy/support_generator.py`,
  `src/fahmi2/pedagogy/sources.py`, `src/fahmi2/pedagogy/generators/_base.py`,
  `src/fahmi2/pedagogy/generators/cloze.py`, `…/flashcards_concepts.py`,
  `…/key_points.py`, `…/qcm.py`, `…/open_questions.py`, `…/mock_exam.py`,
  `…/revision_sheet.py`, `…/true_false.py`
- Modify: `src/fahmi2/domain/enums.py` (ajout `NodeType`, `EdgeType`, `DiagramType`)
- Create: `src/fahmi2/domain/visuals.py`
- Move: `tests/unit/pedagogy/test_chapters.py` → `tests/unit/core/corpus/test_structure.py`
- Create: `tests/unit/core/corpus/__init__.py` (si nécessaire au discovery)
- Create: `tests/unit/domain/test_visuals.py`

---

### Task 0.1 : Relocaliser le parser dans `core/corpus` (refactor, zéro changement de comportement)

- [ ] **Step 1 — Créer `src/fahmi2/core/corpus/structure.py`** (copie verbatim de
  `Chapter`/`parse_chapters`, docstring module adaptée) :

```python
"""Parseur de structure du document consolidé (``consolidated.{lang}.md``).

Module **neutre partagé** (pur Python, sans Qt/HTTP/SQL), consommé par la Pédagogie,
le Dialogue et les Visualisations. Le document consolidé (cf.
``pipeline/handlers/phase_5_consolidation``) place le titre global en ``# <titre>``,
les sections méta (Résumé, Introduction, Sommaire, Conclusion) en ``##``, les
**chapitres** en ``# N. <titre>``, et les **sous-sections** en ``## N.M`` / ``### N.M.K``.

Expose :

- ``Chapter`` / ``parse_chapters`` : découpage **chapitre** (comportement historique,
  inchangé — utilisé par la Pédagogie/Dialogue).
- ``Section`` / ``parse_sections`` : découpage **fin** de toutes les rubriques
  numérotées, avec ``section_path`` **invariant par langue** (dérivé du préfixe
  numérique du titre, ex. ``(2, 1, 1)``) — utilisé par les Visualisations.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from fahmi2.core.slugify import slugify_anchor

# H1 de chapitre : "# 1. Titre", "# 12. Autre". Le préfixe numérique distingue les
# chapitres du titre global (sans numéro) et des sections méta (qui sont en ##).
_RE_CHAPTER_H1 = re.compile(r"^#\s+(\d+)\.\s+(.+?)\s*$")

# Toute rubrique numérotée (H1..H6) : "# 2. T", "## 2.1 T", "### 2.1.1 T".
# Le point final après le dernier nombre est optionnel (présent sur les chapitres).
_RE_NUMBERED_HEADING = re.compile(r"^(#{1,6})\s+(\d+(?:\.\d+)*)\.?\s+(.+?)\s*$")


@dataclass(frozen=True)
class Chapter:
    """Chapitre extrait du document consolidé.

    Attributes:
        index: Numéro du chapitre (1, 2, …).
        title: Titre sans le préfixe ``"N. "``.
        anchor: Ancre GFM (slug) vers le titre numéroté (ex: ``"1-bases"``).
        body_markdown: Corps Markdown du chapitre (jusqu'au chapitre suivant).
    """

    index: int
    title: str
    anchor: str
    body_markdown: str


@dataclass(frozen=True)
class Section:
    """Rubrique numérotée du document consolidé (chapitre ou sous-section).

    Attributes:
        section_path: Chemin structurel issu du préfixe numérique du titre
            (ex: ``(2, 1, 1)`` pour « 2.1.1 »). **Invariant par langue** (les
            numéros ne sont pas traduits).
        level: Profondeur du titre (1 = ``#``, 2 = ``##``, 3 = ``###`` …).
        title: Titre sans le préfixe numérique.
        anchor: Ancre GFM (slug) du titre complet (numéro inclus), telle que
            produite par le rendu Markdown.
        body_markdown: Corps Markdown **direct** (jusqu'au prochain titre numéroté
            de **n'importe quel** niveau), hors sous-rubriques.
    """

    section_path: tuple[int, ...]
    level: int
    title: str
    anchor: str
    body_markdown: str


def parse_chapters(consolidated_markdown: str) -> tuple[Chapter, ...]:
    """Découpe le document consolidé en chapitres (``# N. …``).

    Args:
        consolidated_markdown: Contenu du fichier ``consolidated.{lang}.md``.

    Returns:
        Tuple ordonné des chapitres. Vide si aucun chapitre numéroté.
    """
    lines = consolidated_markdown.splitlines()
    starts: list[tuple[int, int, str]] = []  # (line_idx, index, title)
    for line_idx, line in enumerate(lines):
        match = _RE_CHAPTER_H1.match(line)
        if match is not None:
            starts.append((line_idx, int(match.group(1)), match.group(2).strip()))

    chapters: list[Chapter] = []
    for pos, (line_idx, index, title) in enumerate(starts):
        end = starts[pos + 1][0] if pos + 1 < len(starts) else len(lines)
        body = "\n".join(lines[line_idx + 1 : end]).strip()
        chapters.append(
            Chapter(
                index=index,
                title=title,
                anchor=slugify_anchor(f"{index}. {title}"),
                body_markdown=body,
            )
        )
    return tuple(chapters)


def parse_sections(consolidated_markdown: str) -> tuple[Section, ...]:
    """Découpe le document en toutes les rubriques numérotées (chapitres + sous-sections).

    Args:
        consolidated_markdown: Contenu du fichier ``consolidated.{lang}.md``.

    Returns:
        Tuple ordonné des ``Section``. Vide si aucune rubrique numérotée. Le corps de
        chaque rubrique s'arrête au prochain titre numéroté (tout niveau), de sorte
        qu'une sous-section feuille porte son contenu propre.
    """
    lines = consolidated_markdown.splitlines()
    heads: list[tuple[int, int, tuple[int, ...], str, str]] = []
    for line_idx, line in enumerate(lines):
        match = _RE_NUMBERED_HEADING.match(line)
        if match is None:
            continue
        hashes, number, title = match.group(1), match.group(2), match.group(3).strip()
        path = tuple(int(part) for part in number.split("."))
        anchor = slugify_anchor(line.lstrip("#").strip())
        heads.append((line_idx, len(hashes), path, title, anchor))

    sections: list[Section] = []
    for pos, (line_idx, level, path, title, anchor) in enumerate(heads):
        end = heads[pos + 1][0] if pos + 1 < len(heads) else len(lines)
        body = "\n".join(lines[line_idx + 1 : end]).strip()
        sections.append(
            Section(
                section_path=path,
                level=level,
                title=title,
                anchor=anchor,
                body_markdown=body,
            )
        )
    return tuple(sections)
```

- [ ] **Step 2 — Créer `src/fahmi2/core/corpus/__init__.py`** (ré-export) :

```python
"""Parsing transverse de la structure du document consolidé (module neutre partagé)."""

from fahmi2.core.corpus.structure import (
    Chapter,
    Section,
    parse_chapters,
    parse_sections,
)

__all__ = ["Chapter", "Section", "parse_chapters", "parse_sections"]
```

- [ ] **Step 3 — Mettre à jour les 15 imports** : remplacer dans chaque fichier listé
  `from fahmi2.pedagogy.chapters import …` par `from fahmi2.core.corpus import …`
  (les symboles importés — `Chapter`, `parse_chapters` — sont identiques). Utiliser
  un remplacement exact par fichier (ne pas toucher au reste). Exemple
  (`src/fahmi2/pedagogy/sources.py`) :

```python
from fahmi2.core.corpus import Chapter, parse_chapters
```

- [ ] **Step 4 — Supprimer l'ancien module** :

```bash
git rm src/fahmi2/pedagogy/chapters.py
```

- [ ] **Step 5 — Déplacer le test existant** :

```bash
git mv tests/unit/pedagogy/test_chapters.py tests/unit/core/corpus/test_structure.py
```
Créer `tests/unit/core/corpus/__init__.py` (vide) si le package de test l'exige.
Dans `tests/unit/core/corpus/test_structure.py`, remplacer l'import
`from fahmi2.pedagogy.chapters import …` par `from fahmi2.core.corpus import …`.

- [ ] **Step 6 — Vérifier l'absence de régression (suite complète)** :

Run: `.venv\Scripts\python.exe -m pytest -q`
Expected: PASS (aucun test échoué ; les tests de Pédagogie/Dialogue passent via le
nouveau chemin).
Run: `.venv\Scripts\python.exe -m ruff check .`
Expected: PASS (aucune erreur ; aucun import inutilisé résiduel).
Run: `.venv\Scripts\python.exe -m mypy src tests`
Expected: PASS.

- [ ] **Step 7 — Commit** :

```bash
git add -A
git commit -m "refactor(core): relocalise le parser de sections dans core/corpus (réutilisé pédagogie/dialogue/visualisations)"
```

---

### Task 0.2 : Ajouter `parse_sections` + `Section` (TDD du `section_path`)

> `Section`/`parse_sections` ont été ajoutés en Task 0.1 (même fichier). Ici on
> **verrouille leur comportement** par des tests dédiés.

- [ ] **Step 1 — Écrire le test (échec attendu)** dans
  `tests/unit/core/corpus/test_structure.py` :

```python
from fahmi2.core.corpus import Section, parse_sections

_SAMPLE = """# Titre global

## Résumé

Texte méta.

# 1. Premier chapitre

Intro chapitre 1.

## 1.1 Sous-section A

Corps A.

# 2. Deuxième chapitre

## 2.1 Sous-section B

### 2.1.1 Feuille profonde

Corps profond.
"""


def test_parse_sections_extrait_le_chemin_structurel():
    sections = parse_sections(_SAMPLE)
    paths = [s.section_path for s in sections]
    assert paths == [(1,), (1, 1), (2,), (2, 1), (2, 1, 1)]


def test_parse_sections_ignore_titre_global_et_sections_meta():
    titres = [s.title for s in parse_sections(_SAMPLE)]
    assert "Résumé" not in titres
    assert titres[0] == "Premier chapitre"


def test_parse_sections_niveau_et_corps_direct():
    feuille = parse_sections(_SAMPLE)[-1]
    assert feuille.level == 3
    assert feuille.section_path == (2, 1, 1)
    assert feuille.body_markdown == "Corps profond."


def test_parse_sections_ancre_inclut_le_numero():
    sous = parse_sections(_SAMPLE)[1]  # 1.1 Sous-section A
    assert sous.anchor == "11-sous-section-a"


def test_parse_sections_document_sans_rubrique_numerotee():
    assert parse_sections("# Titre\n\n## Résumé\n\ntexte") == ()
```

- [ ] **Step 2 — Lancer (échoue si Task 0.1 incomplète, sinon passe)** :

Run: `.venv\Scripts\python.exe -m pytest tests/unit/core/corpus/test_structure.py -v`
Expected: PASS (l'implémentation existe depuis Task 0.1). Si un test échoue, corriger
`parse_sections` jusqu'au vert. *(Vérifier en particulier que `slugify_anchor("1.1
Sous-section A") == "11-sous-section-a"` ; sinon ajuster l'assertion à la valeur réelle
de `slugify_anchor` — c'est la source unique d'ancre.)*

- [ ] **Step 3 — Commit** :

```bash
git add tests/unit/core/corpus/test_structure.py
git commit -m "test(core): verrouille parse_sections (section_path invariant par langue)"
```

---

### Task 0.3 : Enums `NodeType` / `EdgeType` / `DiagramType`

**Files:** Modify `src/fahmi2/domain/enums.py` ; Test `tests/unit/domain/test_visuals.py`.

- [ ] **Step 1 — Écrire le test (échec attendu)** dans `tests/unit/domain/test_visuals.py` :

```python
from fahmi2.domain.enums import DiagramType, EdgeType, NodeType


def test_node_types():
    assert {n.value for n in NodeType} == {
        "concept", "glossary_term", "example", "idea"
    }


def test_edge_types():
    assert {e.value for e in EdgeType} == {
        "leads_to", "prerequisite", "illustrates", "contrasts_with",
        "part_of", "related",
    }


def test_diagram_types():
    assert {d.value for d in DiagramType} == {
        "flowchart", "timeline", "comparison", "hierarchy", "cycle",
        "decision_tree",
    }
```

- [ ] **Step 2 — Lancer (échec)** :

Run: `.venv\Scripts\python.exe -m pytest tests/unit/domain/test_visuals.py -v`
Expected: FAIL (`ImportError: cannot import name 'NodeType'`).

- [ ] **Step 3 — Implémenter** : ajouter à la fin de `src/fahmi2/domain/enums.py`
  (les imports `StrEnum` y sont déjà) :

```python
class NodeType(StrEnum):
    """Type d'un nœud de la carte de connaissances (Visualisations)."""

    CONCEPT = "concept"
    GLOSSARY_TERM = "glossary_term"
    EXAMPLE = "example"
    IDEA = "idea"


class EdgeType(StrEnum):
    """Type d'une relation (enchaînement) entre nœuds de la carte de connaissances."""

    LEADS_TO = "leads_to"
    PREREQUISITE = "prerequisite"
    ILLUSTRATES = "illustrates"
    CONTRASTS_WITH = "contrasts_with"
    PART_OF = "part_of"
    RELATED = "related"


class DiagramType(StrEnum):
    """Type de diagramme généré dans la galerie de schémas (Visualisations)."""

    FLOWCHART = "flowchart"
    TIMELINE = "timeline"
    COMPARISON = "comparison"
    HIERARCHY = "hierarchy"
    CYCLE = "cycle"
    DECISION_TREE = "decision_tree"
```

- [ ] **Step 4 — Lancer (passe)** :

Run: `.venv\Scripts\python.exe -m pytest tests/unit/domain/test_visuals.py -v`
Expected: PASS.

- [ ] **Step 5 — Commit** :

```bash
git add src/fahmi2/domain/enums.py tests/unit/domain/test_visuals.py
git commit -m "feat(domain): enums NodeType/EdgeType/DiagramType (Visualisations)"
```

---

### Task 0.4 : Entités immuables (`domain/visuals.py`)

**Files:** Create `src/fahmi2/domain/visuals.py` ; Test (compléter)
`tests/unit/domain/test_visuals.py`.

- [ ] **Step 1 — Écrire le test (échec attendu)** : ajouter à `test_visuals.py` :

```python
import pytest

from fahmi2.domain.enums import DiagramType, EdgeType, Language, NodeType
from fahmi2.domain.visuals import (
    ComparisonTable,
    Diagram,
    DiagramBoard,
    DiagramLink,
    DiagramNode,
    GraphEdge,
    GraphNode,
    KnowledgeGraph,
    SourceExcerpt,
    TimelineEvent,
)


def test_graph_node_minimal():
    node = GraphNode(
        id="concept:bilan",
        label="Bilan",
        node_type=NodeType.CONCEPT,
        definition=None,
        excerpts=(),
        chapter_anchor=None,
        community_path=(),
    )
    assert node.id == "concept:bilan"


def test_knowledge_graph_rejette_arete_vers_noeud_inconnu():
    node = GraphNode(
        id="concept:a", label="A", node_type=NodeType.CONCEPT, definition=None,
        excerpts=(), chapter_anchor=None, community_path=(),
    )
    edge = GraphEdge(source_id="concept:a", target_id="concept:inconnu",
                     edge_type=EdgeType.RELATED, label=None)
    with pytest.raises(ValueError):
        KnowledgeGraph(nodes=(node,), edges=(edge,), communities=(),
                       language=Language.FR)


def test_diagram_flowchart_exige_nodes_et_links():
    with pytest.raises(ValueError):
        Diagram(
            id="d1", title="T", diagram_type=DiagramType.FLOWCHART,
            nodes=(), links=(), events=(), comparison=None,
            caption="c", chapter_anchor="2-x", excerpts=(),
        )


def test_diagram_timeline_exige_events():
    diagram = Diagram(
        id="d2", title="Chute d'Enron", diagram_type=DiagramType.TIMELINE,
        nodes=(), links=(),
        events=(TimelineEvent(date_label="2001", title="Faillite", detail=None),),
        comparison=None, caption="c", chapter_anchor="2-x", excerpts=(),
    )
    assert diagram.events[0].date_label == "2001"
```

- [ ] **Step 2 — Lancer (échec)** :

Run: `.venv\Scripts\python.exe -m pytest tests/unit/domain/test_visuals.py -v`
Expected: FAIL (`ModuleNotFoundError: fahmi2.domain.visuals`).

- [ ] **Step 3 — Implémenter `src/fahmi2/domain/visuals.py`** :

```python
"""Entités immuables de la fonctionnalité Visualisations.

Carte de connaissances (graphe typé + communautés) et galerie de diagrammes (modèles
**typés**, jamais de DSL de rendu). Toutes les entités sont des ``@dataclass(frozen=True)``
pures (aucun import Qt/HTTP/SQL), validées dans ``__post_init__``.
"""

from __future__ import annotations

from dataclasses import dataclass

from fahmi2.domain.enums import (
    DiagramType,
    EdgeType,
    Language,
    NodeType,
    SupportDensity,
)

#: Types de diagramme dont la charge utile est un graphe (nodes + links).
_GRAPH_DIAGRAM_TYPES: frozenset[DiagramType] = frozenset(
    {
        DiagramType.FLOWCHART,
        DiagramType.HIERARCHY,
        DiagramType.DECISION_TREE,
        DiagramType.CYCLE,
    }
)


@dataclass(frozen=True)
class SourceExcerpt:
    """Extrait source verbatim rattaché à un nœud/diagramme.

    Attributes:
        text: Passage de la sous-section, dans la langue rendue.
        section_path: Chemin structurel **invariant par langue** (ex. ``(2, 1, 1)``).
        chapter_title: Titre de la rubrique (langue rendue).
        anchor: Ancre GFM de la rubrique **dans la langue rendue**.
    """

    text: str
    section_path: tuple[int, ...]
    chapter_title: str
    anchor: str


@dataclass(frozen=True)
class GraphNode:
    """Nœud de la carte de connaissances.

    Attributes:
        id: Identifiant stable et unique (``f"{node_type}:{slug}"`` + désambiguïsation).
        label: Libellé affiché (langue rendue).
        node_type: Type du nœud.
        definition: Définition (termes/concepts) ou ``None``.
        excerpts: Extraits sources rattachés.
        chapter_anchor: Ancre du chapitre d'origine (langue rendue) ou ``None``.
        community_path: Chemin dans la hiérarchie de communautés (rempli par Louvain).
    """

    id: str
    label: str
    node_type: NodeType
    definition: str | None
    excerpts: tuple[SourceExcerpt, ...]
    chapter_anchor: str | None
    community_path: tuple[int, ...]


@dataclass(frozen=True)
class GraphEdge:
    """Relation typée entre deux nœuds.

    Attributes:
        source_id: Id du nœud source.
        target_id: Id du nœud cible.
        edge_type: Type de relation (enchaînement).
        label: Libellé optionnel (langue rendue).
    """

    source_id: str
    target_id: str
    edge_type: EdgeType
    label: str | None


@dataclass(frozen=True)
class Community:
    """Communauté thématique (cluster Louvain) avec son rapport.

    Attributes:
        id: Identifiant entier de la communauté.
        label: Étiquette lisible (langue rendue).
        report: Synthèse courte + idée-clé (double usage UI/raisonnement).
        level: Niveau dans la hiérarchie (0 = plus fin).
        member_ids: Ids des nœuds membres directs.
        parent_id: Id de la communauté parente ou ``None`` (racine).
    """

    id: int
    label: str
    report: str
    level: int
    member_ids: tuple[str, ...]
    parent_id: int | None


@dataclass(frozen=True)
class KnowledgeGraph:
    """Graphe de connaissances complet pour une langue.

    Attributes:
        nodes: Nœuds.
        edges: Relations (référencent des ids de ``nodes``).
        communities: Communautés thématiques.
        language: Langue des libellés/extraits.

    Raises:
        ValueError: Si une arête référence un id de nœud inconnu, ou si des ids de
            nœuds sont dupliqués.
    """

    nodes: tuple[GraphNode, ...]
    edges: tuple[GraphEdge, ...]
    communities: tuple[Community, ...]
    language: Language

    def __post_init__(self) -> None:
        ids = [n.id for n in self.nodes]
        if len(ids) != len(set(ids)):
            raise ValueError("KnowledgeGraph: ids de nœuds dupliqués")
        known = set(ids)
        for edge in self.edges:
            if edge.source_id not in known or edge.target_id not in known:
                raise ValueError(
                    f"KnowledgeGraph: arête vers un nœud inconnu "
                    f"({edge.source_id} -> {edge.target_id})"
                )


@dataclass(frozen=True)
class DiagramNode:
    """Nœud d'un diagramme « graphe ».

    Attributes:
        id: Identifiant local au diagramme.
        label: Libellé (langue rendue).
        role: Rôle optionnel (ex. décision/début/fin) ou ``None``.
    """

    id: str
    label: str
    role: str | None


@dataclass(frozen=True)
class DiagramLink:
    """Lien orienté d'un diagramme « graphe ».

    Attributes:
        from_id: Id du nœud source (dans le diagramme).
        to_id: Id du nœud cible (dans le diagramme).
        label: Libellé d'arête optionnel (ex. « oui »/« non ») ou ``None``.
    """

    from_id: str
    to_id: str
    label: str | None


@dataclass(frozen=True)
class TimelineEvent:
    """Évènement d'une chronologie.

    Attributes:
        date_label: Repère temporel affiché (ex. « 2001 »).
        title: Intitulé de l'évènement.
        detail: Détail optionnel ou ``None``.
    """

    date_label: str
    title: str
    detail: str | None


@dataclass(frozen=True)
class ComparisonTable:
    """Tableau de comparaison.

    Attributes:
        columns: En-têtes de colonnes.
        rows: Lignes (chaque ligne a ``len(columns)`` cellules).

    Raises:
        ValueError: Si une ligne n'a pas le bon nombre de cellules.
    """

    columns: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]

    def __post_init__(self) -> None:
        width = len(self.columns)
        for row in self.rows:
            if len(row) != width:
                raise ValueError(
                    f"ComparisonTable: ligne de largeur {len(row)} != {width}"
                )


@dataclass(frozen=True)
class Diagram:
    """Diagramme typé (charge utile selon ``diagram_type``).

    Types « graphe » (``FLOWCHART``/``HIERARCHY``/``DECISION_TREE``/``CYCLE``) →
    ``nodes`` + ``links`` non vides. ``TIMELINE`` → ``events`` non vide. ``COMPARISON``
    → ``comparison`` non ``None``. Les champs non pertinents restent vides/``None``.

    Attributes:
        id: Identifiant stable du diagramme.
        title: Titre (langue rendue).
        diagram_type: Type du diagramme.
        nodes: Nœuds (types « graphe »).
        links: Liens (types « graphe »).
        events: Évènements (``TIMELINE``).
        comparison: Tableau (``COMPARISON``) ou ``None``.
        caption: Légende (langue rendue).
        chapter_anchor: Ancre du chapitre d'origine (langue rendue).
        excerpts: Extraits sources rattachés.

    Raises:
        ValueError: Si la charge utile ne correspond pas au ``diagram_type``.
    """

    id: str
    title: str
    diagram_type: DiagramType
    nodes: tuple[DiagramNode, ...]
    links: tuple[DiagramLink, ...]
    events: tuple[TimelineEvent, ...]
    comparison: ComparisonTable | None
    caption: str
    chapter_anchor: str
    excerpts: tuple[SourceExcerpt, ...]

    def __post_init__(self) -> None:
        if self.diagram_type in _GRAPH_DIAGRAM_TYPES:
            if not self.nodes:
                raise ValueError(
                    f"Diagram {self.diagram_type}: nodes requis"
                )
        elif self.diagram_type is DiagramType.TIMELINE:
            if not self.events:
                raise ValueError("Diagram TIMELINE: events requis")
        elif self.diagram_type is DiagramType.COMPARISON:
            if self.comparison is None:
                raise ValueError("Diagram COMPARISON: comparison requis")


@dataclass(frozen=True)
class DiagramBoard:
    """Galerie de diagrammes pour une langue.

    Attributes:
        diagrams: Diagrammes.
        language: Langue des libellés.
    """

    diagrams: tuple[Diagram, ...]
    language: Language
```

- [ ] **Step 4 — Lancer (passe)** :

Run: `.venv\Scripts\python.exe -m pytest tests/unit/domain/test_visuals.py -v`
Expected: PASS.

- [ ] **Step 5 — Commit** :

```bash
git add src/fahmi2/domain/visuals.py tests/unit/domain/test_visuals.py
git commit -m "feat(domain): entités Visualisations (graphe + communautés + diagrammes typés)"
```

---

### Task 0.5 : `VisualsSettings`

**Files:** Modify `src/fahmi2/domain/visuals.py` ; Test (compléter) `test_visuals.py`.

- [ ] **Step 1 — Écrire le test (échec attendu)** : ajouter à `test_visuals.py` :

```python
from fahmi2.domain.visuals import VisualsSettings


def test_visuals_settings_defaults():
    s = VisualsSettings()
    assert s.produce_knowledge_map is True
    assert s.produce_diagrams is True
    assert s.density is SupportDensity.STANDARD
    assert s.diagram_types == frozenset(DiagramType)
    assert s.llm_workers == 16
    assert s.cost_ceiling_usd is None


def test_visuals_settings_rejette_workers_invalides():
    with pytest.raises(ValueError):
        VisualsSettings(llm_workers=0)


def test_visuals_settings_rejette_cout_negatif():
    with pytest.raises(ValueError):
        VisualsSettings(cost_ceiling_usd=-1.0)
```
(ajouter `from fahmi2.domain.enums import SupportDensity` à l'en-tête du test si absent.)

- [ ] **Step 2 — Lancer (échec)** :

Run: `.venv\Scripts\python.exe -m pytest tests/unit/domain/test_visuals.py -k settings -v`
Expected: FAIL (`ImportError: VisualsSettings`).

- [ ] **Step 3 — Implémenter** : ajouter dans `src/fahmi2/domain/visuals.py` (après les
  imports ; constantes de défaut **nommées**) :

```python
#: Nombre de workers LLM par défaut (aligné sur la Pédagogie).
_DEFAULT_VISUALS_LLM_WORKERS = 16


@dataclass(frozen=True)
class VisualsSettings:
    """Paramètres de la fonctionnalité Visualisations.

    Attributes:
        produce_knowledge_map: Produire la carte de connaissances (Doc A).
        produce_diagrams: Produire la galerie de diagrammes (Doc B).
        density: Densité (volume) des nœuds/diagrammes ; réutilise ``SupportDensity``.
        diagram_types: Types de diagrammes autorisés (sous-ensemble de ``DiagramType``).
        llm_workers: Workers LLM concurrents (>= 1).
        cost_ceiling_usd: Plafond de coût (``None`` = pas de plafond).

    Raises:
        ValueError: Si ``llm_workers < 1`` ou ``cost_ceiling_usd < 0``.
    """

    produce_knowledge_map: bool = True
    produce_diagrams: bool = True
    density: SupportDensity = SupportDensity.STANDARD
    diagram_types: frozenset[DiagramType] = frozenset(DiagramType)
    llm_workers: int = _DEFAULT_VISUALS_LLM_WORKERS
    cost_ceiling_usd: float | None = None

    def __post_init__(self) -> None:
        if self.llm_workers < 1:
            raise ValueError("llm_workers must be >= 1")
        if self.cost_ceiling_usd is not None and self.cost_ceiling_usd < 0:
            raise ValueError(
                f"cost_ceiling_usd must be >= 0 or None, got {self.cost_ceiling_usd}"
            )
```

- [ ] **Step 4 — Lancer (passe)** :

Run: `.venv\Scripts\python.exe -m pytest tests/unit/domain/test_visuals.py -v`
Expected: PASS.

- [ ] **Step 5 — Commit** :

```bash
git add src/fahmi2/domain/visuals.py tests/unit/domain/test_visuals.py
git commit -m "feat(domain): VisualsSettings (réglages de la fonctionnalité Visualisations)"
```

---

### Task 0.6 : Revue de fin de Phase 0 (obligatoire — jusqu'à pleine conviction)

- [ ] **Step 1 — Suite complète + qualité (anti-régression)** :

Run: `.venv\Scripts\python.exe -m pytest -q`
Expected: PASS (tous).
Run: `.venv\Scripts\python.exe -m ruff check .`
Expected: PASS.
Run: `.venv\Scripts\python.exe -m mypy src tests`
Expected: PASS.

- [ ] **Step 2 — Revue de code (checklist § Méthode de travail)** : vérifier docstrings
  module + Args/Returns/Raises ; constantes nommées (aucun magic value) ; cohérence de
  nommage ; réutilisation de `slugify_anchor` ; immutabilité/validation des entités ;
  aucun import résiduel vers `pedagogy.chapters` (`grep -r "pedagogy.chapters" src tests`
  doit être **vide**). Corriger jusqu'à zéro défaut.

- [ ] **Step 3 — Commit éventuel des corrections de revue**, puis **détailler la Phase 1**
  (repasses jusqu'à pleine conviction) avant de l'implémenter.

---

## Phases 1→8 — à détailler juste-à-temps

Chaque phase sera développée en tâches bite-sized/TDD (même format que la Phase 0)
**après** la revue validée de la phase précédente, conformément à la méthode de travail.
Les objectifs, fichiers et tâches clés figurent dans la feuille de route ci-dessus et la
spec §4→§15. Points de vigilance déjà identifiés à reporter dans le détail :

- **Phase 1** : sélection des unités de texte (sous-section feuille avec corps substantiel,
  fallback chapitre) ; squelette `GLOSSARY_TERM` sans LLM ; gleaning **1 passe** ;
  constantes dans `visuals/_constants.py` (plafonds par `density`, taille d'unité).
  **Décision DRY (constatée à la revue Phase 0)** : les helpers de parsing JSON typé
  génériques (`schema_error`, `require_mapping`/`require_list`/`require_str`/`require_int`/
  `require_bool`/`require_str_list`) sont actuellement dans `pedagogy/generators/_base.py`
  mais ne sont **pas** spécifiques à la Pédagogie → les **relocaliser** dans un module
  neutre `infra/llm/json_schema.py` (réutilisé par Pédagogie ET Visualisations, zéro
  duplication, pas de couplage inter-features). `invoke_support_llm` reste pédagogique
  (events `SupportRetryAttempt`) ; l'équivalent Visualisations vivra dans
  `visuals/extractors/_base.py` et réutilisera `invoke_llm_chat`/`parse_llm_json`/
  `with_retry`/`default_classify` directement. Tâche 1 de la Phase 1 = cette relocalisation
  (refactor à comportement constant, suite verte).
- **Phase 2** : `networkx.louvain_partitions` avec **seed constant** ; fallback AUTO sans
  embeddings ; fusion des descriptions ; reports = unités de raisonnement des idea-chains.
- **Phase 4** : extraits résolus par `section_path` (jamais par ancre traduite).
- **Phase 5** : garde-fous **« zéro URL externe »** + JSON embarqué valide + CSS clair &
  sombre ; ordre d'inline des assets ; init paresseuse Doc B ; design system = maquette HF
  validée (couleur idée = `#c2185b`) ; skill `frontend-design`.
- **Phase 6** : blob v2 **lenient** (clé `visuals`) ; fraîcheur (hash réglages + mtimes) ;
  reprise grossière ; plafond best-effort.
- **Phase 7** : enregistrement `FeatureRegistry` sans toucher `MainWindow`/`Project` ;
  contextes i18n via `QCoreApplication.translate("<Contexte>", "littéral")`.
- **Phase 8** : `.spec` (gitignored) — `networkx` + `datas` assets ; garde-fous i18n ;
  mise à jour `README`/`docs/`/`CLAUDE.md`/`packaging/README.md`.
