# Citations lisibles et cliquables dans le Dialogue — Plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rendre les citations du Dialogue parlantes : marqueurs `[N]` cliquables dans le corps de la réponse + liste « Sources » numérotée à l'identique.

**Architecture:** Le LLM continue d'écrire `[§N]` (N = index de passage). À l'assemblage du message, `resolve_citations` réécrit chaque `[§N]` valide en lien Markdown `[[K]](ancre)` (K = numéro d'affichage séquentiel dédupliqué par ancre) et retire les marqueurs invalides ; le rendu Markdown existant produit alors des liens cliquables sans toucher l'UI du clic. La liste « Sources » affiche `[K]` au lieu de `§`.

**Tech Stack:** Python 3.12, dataclasses frozen, python-markdown (`render_markdown_fragment`), PySide6/QTextBrowser, pytest + pytest-qt, ruff, mypy.

**Spec de référence :** `docs/superpowers/specs/2026-05-27-citations-dialogue-lisibles-design.md`

---

## Structure des fichiers

| Fichier | Rôle | Action |
|---------|------|--------|
| `src/fahmi2/domain/chat.py` | Entité `Citation` | Ajouter le champ `number: int` |
| `src/fahmi2/chat/citations.py` | Détection/réécriture des marqueurs | Remplacer `parse_citations` par `resolve_citations` |
| `src/fahmi2/chat/chat_service.py` | Assemblage du `ChatMessage` | `_build_message` utilise `resolve_citations` |
| `src/fahmi2/app/chat_conversation_store.py` | Persistance JSON | Sérialiser/désérialiser `number` (+ fallback legacy) |
| `src/fahmi2/ui/widgets/chat_view.py` | Rendu du fil | `_citations_html` préfixe `[K]` |

Tests touchés : `tests/unit/chat/test_citations.py` (réécrit), `tests/unit/chat/test_chat_service.py` (1 assertion), `tests/unit/domain/test_chat.py` (1 construction), `tests/unit/app/test_chat_conversation_store.py` (1 construction + test legacy), `tests/unit/ui/widgets/test_chat_view_smoke.py` (2 constructions + 2 tests).

**Note d'ordonnancement :** `number` est un champ **requis** (pas de défaut, cohérent avec les entités domaine immuables). L'ajouter casse simultanément tous les sites de construction de `Citation`. La Task 1 forme donc un lot cohérent « couche données » qui se termine **vert** (un seul commit). La Task 2 traite l'UI, la Task 3 la vérification finale.

---

## Task 1 : Couche données — `Citation.number` + `resolve_citations` + service + store

**Files:**
- Modify: `src/fahmi2/domain/chat.py` (dataclass `Citation`, ~67-81)
- Modify: `src/fahmi2/chat/citations.py` (remplacement complet)
- Modify: `src/fahmi2/chat/chat_service.py` (import ~15, `_build_message` ~195-220)
- Modify: `src/fahmi2/app/chat_conversation_store.py` (`_serialize_citation` ~36-43, `_deserialize_message` ~59-81)
- Test: `tests/unit/chat/test_citations.py` (réécrit), `tests/unit/chat/test_chat_service.py` (l.70), `tests/unit/domain/test_chat.py` (l.62-65), `tests/unit/app/test_chat_conversation_store.py` (l.29-34 + nouveau test)

- [ ] **Step 1 : Écrire les tests de `resolve_citations` (remplace tout le fichier)**

Remplacer intégralement `tests/unit/chat/test_citations.py` par :

```python
"""Tests de la résolution des citations [§N] → liens numérotés [[K]](ancre)."""

from __future__ import annotations

from fahmi2.chat.citations import resolve_citations
from fahmi2.domain.chat import CorpusChunk, RetrievedPassage


def _passage(idx: int) -> RetrievedPassage:
    chunk = CorpusChunk(
        chunk_id=f"c::{idx}",
        chapter_title=f"Chap {idx}",
        section_title=f"Sec {idx}",
        anchor=f"a{idx}",
        text=f"Texte du passage {idx} avec du contenu.",
        origin="consolidated",
    )
    return RetrievedPassage(chunk=chunk, score=1.0)


def test_resolve_renumbers_sequentially_by_appearance() -> None:
    passages = (_passage(1), _passage(2), _passage(3))
    # Le LLM cite les passages 3 puis 1 → numérotés 1 puis 2 (ordre d'apparition).
    content, citations = resolve_citations("D'abord [§3] puis [§1].", passages)
    assert content == "D'abord [[1]](a3) puis [[2]](a1)."
    assert [c.number for c in citations] == [1, 2]
    assert [c.anchor for c in citations] == ["a3", "a1"]


def test_resolve_dedup_same_anchor_keeps_number() -> None:
    passages = (_passage(1),)
    content, citations = resolve_citations("Voir [§1] et encore [§1].", passages)
    assert content == "Voir [[1]](a1) et encore [[1]](a1)."
    assert len(citations) == 1
    assert citations[0].number == 1


def test_resolve_drops_out_of_range_without_double_space() -> None:
    passages = (_passage(1),)
    content, citations = resolve_citations("Le PIB [§9] augmente.", passages)
    assert content == "Le PIB augmente."  # marqueur + espace adjacente retirés
    assert citations == ()


def test_resolve_marker_at_start_has_no_leading_space() -> None:
    passages = (_passage(1),)
    content, _ = resolve_citations("[§1] ouvre la phrase.", passages)
    assert content == "[[1]](a1) ouvre la phrase."


def test_resolve_no_marker_returns_text_unchanged() -> None:
    content, citations = resolve_citations("Aucune citation ici.", (_passage(1),))
    assert content == "Aucune citation ici."
    assert citations == ()
```

- [ ] **Step 2 : Lancer le test pour vérifier l'échec**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/chat/test_citations.py -v`
Expected: FAIL avec `ImportError: cannot import name 'resolve_citations'`.

- [ ] **Step 3 : Ajouter le champ `number` à `Citation`**

Dans `src/fahmi2/domain/chat.py`, remplacer la dataclass `Citation` (~67-81) par :

```python
@dataclass(frozen=True)
class Citation:
    """Référence vers un passage cité dans une réponse.

    Attributes:
        number: Numéro d'affichage 1-based, séquentiel par ordre d'apparition
            (dédupliqué par ancre) ; relie le marqueur ``[N]`` du corps à la
            ligne « Sources ».
        chapter_title: Titre du chapitre cité.
        section_title: Titre de la section citée.
        anchor: Ancre GFM du passage (lien cliquable).
        snippet: Court extrait du passage cité.
    """

    number: int
    chapter_title: str
    section_title: str
    anchor: str
    snippet: str
```

- [ ] **Step 4 : Remplacer `parse_citations` par `resolve_citations`**

Remplacer intégralement `src/fahmi2/chat/citations.py` par :

```python
"""Résolution des marqueurs de citation [§N] d'une réponse.

Le prompt impose des marqueurs ``[§N]`` (N = index 1-based du passage fourni). On
réécrit chaque marqueur **valide** en lien Markdown ``[[K]](ancre)`` (K = numéro
d'affichage séquentiel, dédupliqué par ancre) et on **retire** les marqueurs hors
bornes. La liaison est matérialisée à la réécriture : le rendu Markdown produit
ensuite des liens cliquables sans risque de confondre un ``[3]`` littéral du cours.
"""

from __future__ import annotations

import re

from fahmi2.domain.chat import Citation, RetrievedPassage

#: Marqueur de citation, avec une espace optionnelle capturée en amont (pour ne
#: pas laisser de double espace quand un marqueur invalide est retiré).
_RE_CITATION = re.compile(r" ?\[§(\d+)\]")
_SNIPPET_MAX_CHARS = 160


def resolve_citations(
    answer: str, passages: tuple[RetrievedPassage, ...]
) -> tuple[str, tuple[Citation, ...]]:
    """Réécrit les marqueurs ``[§N]`` en liens numérotés et extrait les citations.

    Args:
        answer: Texte de la réponse du LLM (marqueurs ``[§N]``, 1-based).
        passages: Passages numérotés fournis au prompt.

    Returns:
        ``(contenu_réécrit, citations)`` : le contenu où chaque ``[§N]`` valide est
        remplacé par ``[[K]](ancre)`` (les invalides retirés), et les citations
        uniques (dédupliquées par ancre) numérotées dans l'ordre d'apparition.
    """
    citations: list[Citation] = []
    number_by_anchor: dict[str, int] = {}

    def _replace(match: re.Match[str]) -> str:
        leading_space = " " if match.group(0).startswith(" ") else ""
        index = int(match.group(1))
        if not 1 <= index <= len(passages):
            return ""  # marqueur hors bornes : retiré avec l'espace adjacente
        chunk = passages[index - 1].chunk
        number = number_by_anchor.get(chunk.anchor)
        if number is None:
            number = len(number_by_anchor) + 1
            number_by_anchor[chunk.anchor] = number
            citations.append(
                Citation(
                    number=number,
                    chapter_title=chunk.chapter_title,
                    section_title=chunk.section_title,
                    anchor=chunk.anchor,
                    snippet=chunk.text[:_SNIPPET_MAX_CHARS],
                )
            )
        return f"{leading_space}[[{number}]]({chunk.anchor})"

    rewritten = _RE_CITATION.sub(_replace, answer)
    return rewritten, tuple(citations)
```

- [ ] **Step 5 : Lancer les tests citations**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/chat/test_citations.py -v`
Expected: PASS (5 tests).

- [ ] **Step 6 : Brancher `chat_service._build_message` sur `resolve_citations`**

Dans `src/fahmi2/chat/chat_service.py` :

1. Remplacer l'import (~15) :
```python
from fahmi2.chat.citations import resolve_citations
```

2. Remplacer le corps de `_build_message` (le `return ChatMessage(...)`, ~212-220) par :
```python
        content, citations = resolve_citations(response.content, passages)
        return ChatMessage(
            role="assistant",
            content=content,
            citations=citations,
            cost_usd=response.cost_usd + retrieval_cost_usd,
            prompt_tokens=response.prompt_tokens,
            completion_tokens=response.completion_tokens,
            created_at=datetime.now(tz=UTC),
        )
```

- [ ] **Step 7 : Adapter l'assertion de contenu dans `test_chat_service.py`**

Dans `tests/unit/chat/test_chat_service.py`, ligne 70, remplacer :
```python
    assert "[§1]" in message.content
```
par :
```python
    assert "[[1]](pib)" in message.content  # marqueur réécrit en lien numéroté
```

(Le test `test_stream_answer_yields_deltas_then_final_message` reste inchangé : `streamed` accumule les deltas **bruts**, non réécrits — la réécriture n'intervient qu'à la finalisation.)

- [ ] **Step 8 : Lancer les tests du service**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/chat/test_chat_service.py -v`
Expected: PASS (tous).

- [ ] **Step 9 : Persister `number` dans le store**

Dans `src/fahmi2/app/chat_conversation_store.py` :

1. `_serialize_citation` (~36-43) — ajouter `number` :
```python
def _serialize_citation(citation: Citation) -> dict[str, Any]:
    """Sérialise une ``Citation`` en dict JSON-compatible."""
    return {
        "number": citation.number,
        "chapter_title": citation.chapter_title,
        "section_title": citation.section_title,
        "anchor": citation.anchor,
        "snippet": citation.snippet,
    }
```

2. `_deserialize_message` (~64-72) — lire `number` avec fallback par position :
```python
    citations = tuple(
        Citation(
            number=int(c.get("number", index + 1)),
            chapter_title=str(c["chapter_title"]),
            section_title=str(c["section_title"]),
            anchor=str(c["anchor"]),
            snippet=str(c["snippet"]),
        )
        for index, c in enumerate(payload.get("citations", []))
    )
```

- [ ] **Step 10 : Adapter le test du store + ajouter le test de migration legacy**

Dans `tests/unit/app/test_chat_conversation_store.py` :

1. Ajouter l'import `json` en tête (après `from __future__ import annotations`) :
```python
import json
```

2. Dans `_conversation()`, compléter la `Citation` (l.29-34) avec `number=1` :
```python
                    Citation(
                        number=1,
                        chapter_title="Éco",
                        section_title="PIB",
                        anchor="pib",
                        snippet="Le produit intérieur brut…",
                    ),
```

3. Ajouter ce test (migration des conversations sans `number`) :
```python
def test_load_legacy_citation_without_number_falls_back_to_position(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path)
    conv = _conversation()
    store.save(conv)
    # Simule un fichier antérieur : retire la clé "number" des citations.
    path = tmp_path / "conversations" / f"{conv.conversation_id.value}.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    for message in payload["messages"]:
        for citation in message["citations"]:
            citation.pop("number", None)
    path.write_text(json.dumps(payload), encoding="utf-8")
    loaded = store.load(conv.conversation_id)
    assert loaded is not None
    assert loaded.messages[1].citations[0].number == 1  # 1er = position 1
```

- [ ] **Step 11 : Adapter la construction de `Citation` dans `test_chat.py`**

Dans `tests/unit/domain/test_chat.py`, `test_citation_fields` (l.62-65), ajouter `number` :
```python
def test_citation_fields() -> None:
    cit = Citation(
        number=1, chapter_title="Bases", section_title="1.1", anchor="11", snippet="…"
    )
    assert cit.anchor == "11"
    assert cit.number == 1
```

- [ ] **Step 12 : Lancer les tests domaine + store**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/domain/test_chat.py tests/unit/app/test_chat_conversation_store.py -v`
Expected: PASS (tous, dont le nouveau test legacy).

- [ ] **Step 13 : Qualité sur le périmètre**

Run: `.venv\Scripts\python.exe -m ruff check src/fahmi2/domain/chat.py src/fahmi2/chat/citations.py src/fahmi2/chat/chat_service.py src/fahmi2/app/chat_conversation_store.py`
Run: `.venv\Scripts\python.exe -m mypy src tests`
Expected: aucun défaut.

- [ ] **Step 14 : Commit**

```bash
git add src/fahmi2/domain/chat.py src/fahmi2/chat/citations.py src/fahmi2/chat/chat_service.py src/fahmi2/app/chat_conversation_store.py tests/unit/chat/test_citations.py tests/unit/chat/test_chat_service.py tests/unit/domain/test_chat.py tests/unit/app/test_chat_conversation_store.py
git commit -F - <<'EOF'
feat(dialogue): citations numérotées et liens cliquables (couche données)

resolve_citations réécrit les marqueurs [§N] en liens Markdown [[K]](ancre)
(K séquentiel dédupliqué par ancre, invalides retirés) et porte le numéro sur
Citation. chat_service assemble le message réécrit ; le store persiste number
avec migration par position pour les conversations antérieures.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
```

---

## Task 2 : UI — liste « Sources » numérotée + liens inline cliquables

**Files:**
- Modify: `src/fahmi2/ui/widgets/chat_view.py` (`_citations_html`, ~303-320)
- Test: `tests/unit/ui/widgets/test_chat_view_smoke.py` (2 constructions `Citation` + 2 tests)

- [ ] **Step 1 : Adapter les constructions de `Citation` + ajouter les tests**

Dans `tests/unit/ui/widgets/test_chat_view_smoke.py` :

1. `test_streaming_then_finalize` (l.24-29) — ajouter `number=1` :
```python
                Citation(
                    number=1,
                    chapter_title="Éco",
                    section_title="PIB",
                    anchor="pib",
                    snippet="…",
                ),
```

2. `test_citation_link_carries_snippet_tooltip` (l.42-47) — ajouter `number=1` :
```python
        Citation(
            number=1,
            chapter_title="Éco",
            section_title="PIB",
            anchor="pib",
            snippet="Le produit intérieur brut\nmesure la richesse produite.",
        ),
```

3. Ajouter ces deux tests (numérotation de la liste + lien inline rendu) — `_message_html` est déjà importable depuis le module :
```python
def test_citations_list_is_numbered_not_paragraph_sign() -> None:
    citations = (
        Citation(
            number=1,
            chapter_title="Éco",
            section_title="PIB",
            anchor="pib",
            snippet="…",
        ),
    )
    html_out = _citations_html(citations)
    assert "[1] Éco › PIB" in html_out
    assert "§" not in html_out  # plus de pied-de-mouche


def test_assistant_inline_marker_is_clickable_link() -> None:
    from fahmi2.ui.widgets.chat_view import _message_html

    message = ChatMessage(
        role="assistant",
        content="Le PIB [[1]](pib) mesure la richesse.",
        citations=(
            Citation(
                number=1,
                chapter_title="Éco",
                section_title="PIB",
                anchor="pib",
                snippet="…",
            ),
        ),
    )
    html_out = _message_html(message)
    assert '<a href="pib">[1]</a>' in html_out
```

- [ ] **Step 2 : Lancer les tests pour vérifier l'échec**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/ui/widgets/test_chat_view_smoke.py::test_citations_list_is_numbered_not_paragraph_sign -v`
Expected: FAIL (la liste contient encore `§`, pas `[1]`).

- [ ] **Step 3 : Numéroter la liste dans `_citations_html`**

Dans `src/fahmi2/ui/widgets/chat_view.py`, `_citations_html` (~314-319), remplacer la f-string de l'item par :
```python
    items = "".join(
        f'<li><a href="{html.escape(c.anchor)}" '
        f'title="{_tooltip(c.snippet)}">[{c.number}] {html.escape(c.chapter_title)} › '
        f"{html.escape(c.section_title)}</a></li>"
        for c in citations
    )
```

(`_message_html` reste **inchangé** : le contenu réécrit `[[1]](pib)` est rendu en `<a href="pib">[1]</a>` par `render_markdown_fragment`.)

- [ ] **Step 4 : Lancer les tests du widget**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/ui/widgets/test_chat_view_smoke.py -v`
Expected: PASS (tous).

- [ ] **Step 5 : Qualité sur le périmètre**

Run: `.venv\Scripts\python.exe -m ruff check src/fahmi2/ui/widgets/chat_view.py tests/unit/ui/widgets/test_chat_view_smoke.py`
Run: `.venv\Scripts\python.exe -m mypy src tests`
Expected: aucun défaut.

- [ ] **Step 6 : Commit**

```bash
git add src/fahmi2/ui/widgets/chat_view.py tests/unit/ui/widgets/test_chat_view_smoke.py
git commit -F - <<'EOF'
feat(dialogue): liste « Sources » numérotée [K] et marqueurs cliquables

_citations_html préfixe chaque source par [K] (au lieu de §). Les marqueurs
inline [[K]](ancre) du contenu réécrit sont rendus en liens cliquables par
le moteur Markdown existant (clic inchangé : anchorClicked → citation_clicked).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
```

---

## Task 3 : Vérification finale complète + documentation

**Files:**
- Vérification: suite complète
- Modify (si nécessaire): docs/`README.md` mentionnant le format d'affichage des citations

- [ ] **Step 1 : Suite complète**

Run: `.venv\Scripts\python.exe -m pytest`
Expected: PASS intégral.

- [ ] **Step 2 : Lint complet**

Run: `.venv\Scripts\python.exe -m ruff check .`
Expected: `All checks passed!`

- [ ] **Step 3 : Typage complet**

Run: `.venv\Scripts\python.exe -m mypy src tests`
Expected: `Success: no issues found`.

Si l'un des trois échoue, corriger et **repasser les trois** jusqu'à zéro défaut (exigence projet).

- [ ] **Step 4 : Vérifier la documentation**

Run: `.venv\Scripts\python.exe -m pytest -q` (confirmation finale) puis inspecter :
- `CLAUDE.md` : la mention « `citations` (parsing `[§N]`) » reste **exacte** (le LLM écrit toujours `[§N]`) → ne pas modifier.
- `README.md` et `docs/` : chercher toute description du **format d'affichage** des citations (ex. mention d'un `§` visible). S'il en existe une, la mettre à jour pour décrire les repères numérotés `[N]` cliquables. Sinon, aucune modification.

Run: `git -C . grep -n "§" -- README.md docs/`
Si une occurrence décrit l'affichage utilisateur des citations, la corriger ; les occurrences dans les specs historiques (`docs/superpowers/specs/`) ne sont pas réécrites.

- [ ] **Step 5 : Commit (uniquement si la doc a changé)**

```bash
git add README.md docs/
git commit -F - <<'EOF'
docs(dialogue): décrit les citations numérotées [N] cliquables

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
```

(Si aucune doc n'a changé, ne rien committer.)

---

## Self-Review

**1. Couverture du spec :**
- Repère `[N]` cliquable dans le corps → Task 1 (réécriture `[[K]](ancre)`) + Task 2 (rendu lien vérifié par `test_assistant_inline_marker_is_clickable_link`). ✓
- Liste « Sources » numérotée → Task 2 (`_citations_html` + `test_citations_list_is_numbered_not_paragraph_sign`). ✓
- Numérotation séquentielle dédupliquée par ancre → Task 1 (`test_resolve_renumbers_sequentially_by_appearance`, `test_resolve_dedup_same_anchor_keeps_number`). ✓
- Marqueurs invalides retirés (sans double espace) → Task 1 (`test_resolve_drops_out_of_range_without_double_space`). ✓
- `number` sur `Citation` + persistance + migration legacy → Task 1 (domaine, store, `test_load_legacy_citation_without_number_falls_back_to_position`). ✓
- Clic inline = clic liste (réutilise `citation_clicked`) → aucun changement de câblage (confirmé dans le spec) ; `_message_html` inchangé. ✓
- Prompt inchangé → aucune tâche ne le touche. ✓
- Dégradation gracieuse (conversations anciennes) → fallback par position (Task 1, step 9-10). ✓

**2. Scan des placeholders :** aucun TBD/TODO ; chaque step de code montre le code complet, chaque step de commande montre la commande exacte et l'attendu.

**3. Cohérence des types/noms :** `resolve_citations(answer, passages) -> tuple[str, tuple[Citation, ...]]` est défini en Task 1 step 4 et appelé identiquement en step 6. Le champ `Citation.number: int` (step 3) est fourni partout : `resolve_citations` (step 4), store désérialisation (step 9), et tous les tests adaptés (steps 1, 7, 10, 11 ; Task 2 step 1). La forme du lien `[[K]](ancre)` est cohérente entre la réécriture (step 4), l'assertion service (step 7) et le test de rendu UI (Task 2 step 1).
