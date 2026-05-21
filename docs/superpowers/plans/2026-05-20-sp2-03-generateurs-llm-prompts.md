# SP2 · Plan 03 — Générateurs LLM + prompts pédagogie

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (inline, sans subagents).
> **Design** : [`../specs/2026-05-20-sp2-sp3-supports-revision-design.md`](../specs/2026-05-20-sp2-sp3-supports-revision-design.md) (§§3.4, 6, 7).
> **Avancement** : [`./2026-05-20-sp2-sp3-00-avancement.md`](./2026-05-20-sp2-sp3-00-avancement.md).
> Steps use checkbox (`- [ ]`) syntax.

**Goal:** Sur le socle SP2/02, livrer les **8 générateurs de supports LLM** (flashcards
concepts, QCM, vrai/faux, cloze, questions ouvertes, fiche de révision, points clés,
examen blanc), chacun avec son **prompt `pedagogy_*.j2` éditable**, son **parsing JSON
typé** vers les entités de support, son **rendu Markdown** (avec **corrigé séparé** pour
les évaluatifs), et le **retry LLM** (mêmes codes retryables que le pipeline).

**Architecture:** Classes de base dans `pedagogy/generators/_base.py` (template-method
per-chapitre + invocation LLM avec retry + helpers de parsing JSON typé), mixin
évaluatif pour les corrigés séparés. Réutilise `invoke_llm_chat`/`parse_llm_json`
(SP2/02), `with_retry`/`RetryPolicy`, `PromptLoader` (override `%APPDATA%`). La
classification de retry `default_classify` est **remontée** de `pipeline/engine.py` vers
`core/retry/classification.py` (logique pure `core`, découple `pedagogy` du moteur). Les
8 prompts sont **enregistrés** dans `PromptsService._TEMPLATE_METADATA` pour être
éditables via « Édition → Modifier les prompts ». Une **factory** assemble le registre
des 9 générateurs.

**Tech Stack:** Python 3.12, dataclasses frozen, Jinja2, `pytest`/`ruff`/`mypy --strict`.

**Rappels directives :** pas de magic value (constantes), docstrings Google + module,
réutiliser les patterns existants (`_base.py` handlers, `PhaseRegistry`, `with_retry`,
`default_classify`, `PromptLoader`), DRY/YAGNI/KISS/SRP/SoC, composition > héritage,
entités `frozen`. **Tout en français** (accents corrects).

**Décisions verrouillées pour ce lot :**
- **Dé-biaisage QCM = déterministe** (rotation de la position de la bonne réponse sur
  l'ensemble des items) — pas de 2ᵉ appel LLM (YAGNI ; la qualité fine des distracteurs
  relève de l'itération produit via l'éditeur de prompts, design §12).
- **Corrigé séparé** (`separate_correction`) → l'artefact porte `rendered_markdown`
  (sujet) **et** `correction_markdown` (corrigé) ; l'orchestrateur écrit alors un 2ᵉ
  fichier `<support>.corrige.md`. Sinon `correction_markdown=None` (rendu combiné).
- **Examen blanc** = générateur **doc-entier** (consomme tous les chapitres concaténés),
  les 7 autres sont **par chapitre**.

---

## File structure (vue d'ensemble)

**Créés :**

- `src/fahmi2/core/retry/classification.py` — `default_classify` + codes retryables (déplacés).
- `src/fahmi2/pedagogy/labels.py` — libellés FR (langue, public, Bloom, densité) + format glossaire.
- `src/fahmi2/pedagogy/generators/_base.py` — `invoke_support_llm`, `_PerChapterLlmGenerator`,
  `_EvaluativePerChapterLlmGenerator`, helpers de parsing JSON typé.
- `src/fahmi2/pedagogy/generators/flashcards_concepts.py`
- `src/fahmi2/pedagogy/generators/qcm.py`
- `src/fahmi2/pedagogy/generators/true_false.py`
- `src/fahmi2/pedagogy/generators/cloze.py`
- `src/fahmi2/pedagogy/generators/open_questions.py`
- `src/fahmi2/pedagogy/generators/revision_sheet.py`
- `src/fahmi2/pedagogy/generators/key_points.py`
- `src/fahmi2/pedagogy/generators/mock_exam.py`
- `src/fahmi2/pedagogy/default_registry.py` — `build_default_support_registry()`.
- `src/fahmi2/infra/prompts/defaults/pedagogy_{flashcards_concepts,qcm,true_false,cloze,open_questions,revision_sheet,key_points,mock_exam}.j2` (8 prompts).
- Tests : `tests/unit/core/test_retry_classification.py`,
  `tests/unit/pedagogy/test_labels.py`, `tests/unit/pedagogy/test_generators_base.py`,
  `tests/unit/pedagogy/test_llm_generators.py` (paramétré sur les générateurs),
  `tests/unit/pedagogy/test_default_registry.py`,
  `tests/unit/infra/prompts/test_pedagogy_prompts.py`.

**Modifiés :**

- `src/fahmi2/domain/supports.py` — nouvelles entités + `SupportItem` union + `correction_markdown`.
- `src/fahmi2/pedagogy/events.py` — `SupportRetryAttempt` + union.
- `src/fahmi2/pedagogy/support_generator.py` — `SupportContext.retry_policy`.
- `src/fahmi2/pedagogy/artifact_writer.py` — `artifact_correction_markdown_path`.
- `src/fahmi2/app/supports_orchestrator.py` — `retry_policy` (constructeur + contexte),
  écriture du corrigé.
- `src/fahmi2/app/prompts_service.py` — 8 `PromptTemplateMeta` pédagogie.
- `src/fahmi2/pipeline/engine.py` — import `default_classify` depuis `core/retry`.
- Tests : `tests/unit/pipeline/test_engine.py` (import), `tests/unit/app/test_prompts_service.py`
  (sous-ensemble + pédagogie), `tests/unit/app/test_supports_orchestrator.py` (`retry_policy`).
- Docs : `docs/02-presentation-technique.md`, `docs/04-parametrage.md` (catalogue prompts),
  `CHANGELOG.md`, doc d'avancement.

---

## Task 1 : Refactor — `default_classify` → `core/retry/classification.py`

> Logique pure `core` (classification d'erreurs retryables), aujourd'hui dans
> `pipeline/engine.py`. La remonter découple `pedagogy` du moteur (DRY + Boy Scout).

**Files:** Create `src/fahmi2/core/retry/classification.py` ;
Modify `src/fahmi2/pipeline/engine.py` ;
Create `tests/unit/core/test_retry_classification.py` ;
Modify `tests/unit/pipeline/test_engine.py`

- [ ] **Step 1 : Créer `core/retry/classification.py`** (copier la fonction + constantes
  depuis `engine.py`, docstring de module) :

```python
"""Classification des exceptions pour la politique de retry.

Décide, pour une exception donnée, s'il faut retenter (``RETRY``), abandonner
(``NO_RETRY``) ou propager un dépassement de budget (``RAISE_BUDGET``). Logique
partagée par le moteur de génération (``pipeline/engine``) et l'orchestrateur de
supports pédagogiques (``pedagogy``).
"""

from __future__ import annotations

from fahmi2.core.errors.exceptions import (
    BudgetExceededError,
    Fahmi2Error,
    LLMError,
    PausedError,
    PermanentError,
    STTError,
    StorageError,
    TransientError,
)
from fahmi2.core.retry.policy import RetryDecision

_RETRYABLE_LLM_CODES: frozenset[str] = frozenset({"LLM.RATE_LIMIT", "LLM.SERVER_ERROR"})
_RETRYABLE_STT_CODES: frozenset[str] = frozenset({"STT.RATE_LIMIT", "STT.API_ERROR"})


def default_classify(exc: BaseException) -> RetryDecision:  # noqa: PLR0911
    """Classifie une exception pour décider du comportement de retry.

    Args:
        exc: Exception levée par un handler ou un générateur.

    Returns:
        ``RetryDecision`` selon les conventions documentées en spec §8.2.
    """
    if isinstance(exc, BudgetExceededError):
        return RetryDecision.RAISE_BUDGET
    if isinstance(exc, PausedError):
        return RetryDecision.NO_RETRY
    if isinstance(exc, TransientError):
        return RetryDecision.RETRY
    if isinstance(exc, PermanentError):
        return RetryDecision.NO_RETRY
    if isinstance(exc, LLMError) and exc.code in _RETRYABLE_LLM_CODES:
        return RetryDecision.RETRY
    if isinstance(exc, STTError) and exc.code in _RETRYABLE_STT_CODES:
        return RetryDecision.RETRY
    if isinstance(exc, StorageError):
        return RetryDecision.NO_RETRY
    if isinstance(exc, Fahmi2Error):
        return RetryDecision.NO_RETRY
    return RetryDecision.RETRY
```

  > Vérifier les noms exacts des exceptions importées dans `core/errors/exceptions.py`
  > (mêmes que ceux référencés aujourd'hui dans `engine.py`).

- [ ] **Step 2 : `engine.py`** — supprimer la définition locale + les 2 constantes,
  importer depuis `core/retry/classification` :

```python
from fahmi2.core.retry.classification import default_classify
```
  (retirer les imports d'exceptions devenus inutiles si `ruff` les signale ; `engine.py`
  garde ceux qu'il utilise encore directement, p.ex. `Fahmi2Error`, `PausedError`,
  `BudgetExceededError` pour le `try/except` de `execute`).

- [ ] **Step 3 : Déplacer le test** `test_default_classify` de `test_engine.py` vers
  `tests/unit/core/test_retry_classification.py` (copier la paramétrisation + imports),
  et dans `test_engine.py` retirer la fonction de test + ajuster l'import
  (`from fahmi2.pipeline.engine import PipelineEngine` ; retirer `default_classify`).

- [ ] **Step 4 : Lancer** :

Run: `.venv\Scripts\python.exe -m pytest tests/unit/core/test_retry_classification.py tests/unit/pipeline/test_engine.py -q`
Expected: PASS.

---

## Task 2 : Domaine — entités de support évaluatives + contenu

**Files:** Modify `src/fahmi2/domain/supports.py` ; Test `tests/unit/domain/test_supports.py`

- [ ] **Step 1 : Tests (échouent)** — ajouter à `test_supports.py` :

```python
import pytest

from fahmi2.domain.supports import (
    ClozeItem,
    KeyPoints,
    MockExam,
    MockExamSection,
    OpenQuestion,
    QcmItem,
    RevisionSheet,
    TrueFalseItem,
)


def test_qcm_item_validates_correct_index() -> None:
    QcmItem(question="q", choices=("a", "b"), correct_index=1, justification="j", source_ref="r")
    with pytest.raises(ValueError, match="correct_index"):
        QcmItem(question="q", choices=("a", "b"), correct_index=2, justification="j", source_ref="r")


def test_qcm_item_requires_two_choices() -> None:
    with pytest.raises(ValueError, match="choices"):
        QcmItem(question="q", choices=("a",), correct_index=0, justification="j", source_ref="r")


def test_other_entities_construct() -> None:
    assert TrueFalseItem(statement="s", is_true=True, justification="j", source_ref="r").is_true
    assert ClozeItem(text="a ___", answers=("x",), source_ref="r").answers == ("x",)
    assert OpenQuestion(question="q", expected_points=("p",), source_ref="r").question == "q"
    assert RevisionSheet(chapter_title="c", summary_markdown="m", source_ref="r").source_ref == "r"
    assert KeyPoints(chapter_title="c", points=("p1", "p2"), source_ref="r").points[0] == "p1"
    exam = MockExam(
        title="t",
        sections=(MockExamSection(title="s1", statement_markdown="..."),),
        grading_markdown="bareme",
    )
    assert exam.sections[0].title == "s1"
```

- [ ] **Step 2 : Lancer** → FAIL.

- [ ] **Step 3 : Ajouter les entités à `domain/supports.py`** (après `Flashcard`,
  avant `SupportItem`) :

```python
@dataclass(frozen=True)
class QcmItem:
    """Question à choix multiple.

    Attributes:
        question: Énoncé de la question.
        choices: Propositions (au moins 2).
        correct_index: Index (0-based) de la bonne proposition dans ``choices``.
        justification: Explication de la bonne réponse.
        source_ref: Référence d'origine (ancre de chapitre).
    """

    question: str
    choices: tuple[str, ...]
    correct_index: int
    justification: str
    source_ref: str

    def __post_init__(self) -> None:
        if len(self.choices) < _MIN_QCM_CHOICES:
            raise ValueError(
                f"choices must contain at least {_MIN_QCM_CHOICES} options"
            )
        if not 0 <= self.correct_index < len(self.choices):
            raise ValueError(
                f"correct_index must be in [0, {len(self.choices)}), "
                f"got {self.correct_index}"
            )


@dataclass(frozen=True)
class TrueFalseItem:
    """Affirmation vrai/faux justifiée.

    Attributes:
        statement: Affirmation à évaluer.
        is_true: ``True`` si l'affirmation est vraie.
        justification: Explication.
        source_ref: Référence d'origine.
    """

    statement: str
    is_true: bool
    justification: str
    source_ref: str


@dataclass(frozen=True)
class ClozeItem:
    """Texte à trous.

    Attributes:
        text: Texte avec marqueurs de trous (``___``).
        answers: Réponses attendues, dans l'ordre des trous (non vide).
        source_ref: Référence d'origine.
    """

    text: str
    answers: tuple[str, ...]
    source_ref: str

    def __post_init__(self) -> None:
        if not self.answers:
            raise ValueError("answers must contain at least one answer")


@dataclass(frozen=True)
class OpenQuestion:
    """Question ouverte avec éléments de réponse attendus.

    Attributes:
        question: Énoncé.
        expected_points: Points clés attendus dans la réponse.
        source_ref: Référence d'origine.
    """

    question: str
    expected_points: tuple[str, ...]
    source_ref: str


@dataclass(frozen=True)
class RevisionSheet:
    """Fiche de révision d'un chapitre.

    Attributes:
        chapter_title: Titre du chapitre.
        summary_markdown: Synthèse Markdown du chapitre.
        source_ref: Référence d'origine.
    """

    chapter_title: str
    summary_markdown: str
    source_ref: str


@dataclass(frozen=True)
class KeyPoints:
    """Points clés d'un chapitre.

    Attributes:
        chapter_title: Titre du chapitre.
        points: Puces (idées clés).
        source_ref: Référence d'origine.
    """

    chapter_title: str
    points: tuple[str, ...]
    source_ref: str


@dataclass(frozen=True)
class MockExamSection:
    """Section d'un examen blanc.

    Attributes:
        title: Titre de la section.
        statement_markdown: Énoncé Markdown de la section.
    """

    title: str
    statement_markdown: str


@dataclass(frozen=True)
class MockExam:
    """Examen blanc composite.

    Attributes:
        title: Titre de l'examen.
        sections: Sections (énoncés).
        grading_markdown: Barème / corrigé Markdown.
    """

    title: str
    sections: tuple[MockExamSection, ...]
    grading_markdown: str
```

  Ajouter la constante en tête : `_MIN_QCM_CHOICES = 2`.

  Étendre l'alias :

```python
SupportItem = (
    Flashcard
    | QcmItem
    | TrueFalseItem
    | ClozeItem
    | OpenQuestion
    | RevisionSheet
    | KeyPoints
    | MockExam
)
```

  Ajouter `correction_markdown` à `SupportArtifact` (après `rendered_markdown`) :

```python
    rendered_markdown: str
    correction_markdown: str | None = None
    cost_usd: float = 0.0
```
  (docstring : « ``correction_markdown`` : corrigé séparé Markdown, ou ``None`` si le
  support n'est pas évaluatif ou si le corrigé est intégré au rendu. »)

- [ ] **Step 4 : Lancer** → PASS.

Run: `.venv\Scripts\python.exe -m pytest tests/unit/domain/test_supports.py -q`

---

## Task 3 : Events retry + contexte `retry_policy` + écriture du corrigé

**Files:** Modify `src/fahmi2/pedagogy/events.py`, `src/fahmi2/pedagogy/support_generator.py`,
`src/fahmi2/pedagogy/artifact_writer.py`, `src/fahmi2/app/supports_orchestrator.py`,
`tests/unit/app/test_supports_orchestrator.py`

- [ ] **Step 1 : `events.py`** — ajouter `SupportRetryAttempt` (avant l'union) et
  l'inclure dans `PedagogyEvent` :

```python
@dataclass(frozen=True)
class SupportRetryAttempt:
    """Tentative de retry d'un appel LLM pour un support.

    Attributes:
        timestamp: Horodatage.
        support_type: Type de support.
        language: Langue.
        attempt: Numéro de tentative (1-indexed).
        delay_seconds: Délai avant la prochaine tentative.
        error: ``ErrorInfo`` de l'échec déclencheur.
    """

    timestamp: datetime
    support_type: SupportType
    language: Language
    attempt: int
    delay_seconds: float
    error: ErrorInfo


PedagogyEvent = (
    SupportGenerationStarted
    | SupportStarted
    | SupportRetryAttempt
    | SupportFinished
    | SupportGenerationFinished
)
```

- [ ] **Step 2 : `support_generator.py`** — ajouter `retry_policy: RetryPolicy` à
  `SupportContext` (après `pause_token`), importer
  `from fahmi2.core.retry.policy import RetryPolicy`. Compléter la docstring du champ.

- [ ] **Step 3 : `artifact_writer.py`** — ajouter le chemin du corrigé + une constante :

```python
_CORRECTION_SUFFIX = ".corrige"


def artifact_correction_markdown_path(
    pedagogy_dir: Path, support_type: SupportType, language: Language
) -> Path:
    """Chemin du fichier Markdown de corrigé d'un support.

    Args:
        pedagogy_dir: Dossier pédagogie.
        support_type: Type de support.
        language: Langue.

    Returns:
        Le chemin ``…/<support>.corrige.md``.
    """
    return (
        support_dir(pedagogy_dir, support_type, language)
        / f"{support_type.value}{_CORRECTION_SUFFIX}{_MD_EXT}"
    )
```

- [ ] **Step 4 : `supports_orchestrator.py`** — (a) ajouter `retry_policy: RetryPolicy`
  au constructeur (stocké `self._retry_policy`), import
  `from fahmi2.core.retry.policy import RetryPolicy` ; (b) le passer dans `SupportContext`
  (`retry_policy=self._retry_policy`) dans `_build_context` ; (c) dans `_write_artifact`,
  écrire le corrigé si présent :

```python
        ctx.artifacts.write_json_atomic(json_path, serialize_artifact(artifact))
        ctx.artifacts.write_text_atomic(md_path, artifact.rendered_markdown)
        if artifact.correction_markdown is not None:
            correction_path = artifact_correction_markdown_path(
                ctx.pedagogy_dir, artifact.support_type, artifact.language
            )
            ctx.artifacts.write_text_atomic(
                correction_path, artifact.correction_markdown
            )
```
  (importer `artifact_correction_markdown_path`).

- [ ] **Step 5 : `test_supports_orchestrator.py`** — le `_build` doit fournir un
  `retry_policy`. Ajouter l'import `from fahmi2.core.retry.policy import RetryPolicy` et
  passer `retry_policy=RetryPolicy(max_attempts=2, jitter=False, initial_delay_seconds=0.001)`
  au constructeur dans `_build`.

- [ ] **Step 6 : Lancer** (régression SP2/02) :

Run: `.venv\Scripts\python.exe -m pytest tests/unit/app/test_supports_orchestrator.py tests/unit/pedagogy -q`
Expected: PASS.

---

## Task 4 : Libellés pédagogie + format glossaire

**Files:** Create `src/fahmi2/pedagogy/labels.py` ; Test `tests/unit/pedagogy/test_labels.py`

- [ ] **Step 1 : Test (échoue)** :

```python
"""Tests des libellés pédagogie."""

from __future__ import annotations

from fahmi2.domain.enums import (
    BloomObjective,
    Language,
    SupportDensity,
    TargetAudience,
)
from fahmi2.domain.glossary import Term
from fahmi2.pedagogy.labels import (
    audience_label,
    bloom_label,
    density_label,
    format_glossary_terms,
    language_label,
)


def test_labels_are_french() -> None:
    assert language_label(Language.FR) == "français"
    assert audience_label(TargetAudience.LICENCE)
    assert bloom_label(BloomObjective.AUTO)
    assert density_label(SupportDensity.STANDARD)


def test_format_glossary_terms() -> None:
    text = format_glossary_terms(
        (Term(term="PIB", definition="Produit intérieur brut", acronym="PIB"),)
    )
    assert "PIB" in text
    assert "Produit intérieur brut" in text


def test_format_glossary_terms_empty() -> None:
    assert format_glossary_terms(()) == ""
```

- [ ] **Step 2 : Lancer** → FAIL.

- [ ] **Step 3 : Créer `pedagogy/labels.py`** :

```python
"""Libellés humains (FR) des réglages pédagogie + formatage du glossaire pour prompts.

Tables de correspondance dédiées à la pédagogie (le pipeline a les siennes dans
``pipeline/handlers/_base``) : public cible, objectif Bloom, densité, langue.
"""

from __future__ import annotations

from fahmi2.domain.enums import (
    BloomObjective,
    Language,
    SupportDensity,
    TargetAudience,
)
from fahmi2.domain.glossary import Term

_LANGUAGE_LABELS_FR: dict[Language, str] = {
    Language.FR: "français",
    Language.EN: "anglais",
}

_AUDIENCE_LABELS_FR: dict[TargetAudience, str] = {
    TargetAudience.DISCOVERY: "grand public (découverte)",
    TargetAudience.HIGH_SCHOOL: "lycée",
    TargetAudience.LICENCE: "licence (premier cycle universitaire)",
    TargetAudience.MASTER_EXPERT: "master / expert",
}

_BLOOM_LABELS_FR: dict[BloomObjective, str] = {
    BloomObjective.AUTO: "automatique (adapté au public cible)",
    BloomObjective.RESTITUTE: "restituer (mémorisation, définitions)",
    BloomObjective.UNDERSTAND_APPLY: "comprendre et appliquer",
    BloomObjective.ANALYZE_BEYOND: "analyser et au-delà (synthèse, évaluation)",
}

_DENSITY_LABELS_FR: dict[SupportDensity, str] = {
    SupportDensity.LIGHT: "légère",
    SupportDensity.STANDARD: "standard",
    SupportDensity.DENSE: "dense",
}


def language_label(language: Language) -> str:
    """Libellé FR d'une langue (ex: ``"français"``)."""
    return _LANGUAGE_LABELS_FR[language]


def audience_label(audience: TargetAudience) -> str:
    """Libellé FR d'un public cible."""
    return _AUDIENCE_LABELS_FR[audience]


def bloom_label(bloom: BloomObjective) -> str:
    """Libellé FR d'un objectif Bloom."""
    return _BLOOM_LABELS_FR[bloom]


def density_label(density: SupportDensity) -> str:
    """Libellé FR d'une densité."""
    return _DENSITY_LABELS_FR[density]


def format_glossary_terms(glossary: tuple[Term, ...]) -> str:
    """Formate le glossaire en bloc texte injectable dans un prompt.

    Args:
        glossary: Termes du glossaire.

    Returns:
        Une ligne ``- terme (acronyme) : définition`` par terme ; ``""`` si vide.
    """
    lines: list[str] = []
    for term in glossary:
        head = f"{term.term} ({term.acronym})" if term.acronym else term.term
        lines.append(f"- {head} : {term.definition}")
    return "\n".join(lines)
```

- [ ] **Step 4 : Lancer** → PASS.

---

## Task 5 : Socle des générateurs LLM

**Files:** Create `src/fahmi2/pedagogy/generators/_base.py` ;
Test `tests/unit/pedagogy/test_generators_base.py`

Ce module fournit :
1. `invoke_support_llm(ctx, *, support_type, language, system_prompt, user_prompt)` :
   appel LLM **avec retry** (`with_retry` + `default_classify`), émettant
   `SupportRetryAttempt` sur chaque tentative classée RETRY (parité moteur).
2. Helpers de parsing JSON typé (`require_mapping`, `require_list`, `require_str`,
   `require_int`, `require_bool`, `require_str_list`) levant `LLMError(LLM.INVALID_SCHEMA)`.
3. `_PerChapterLlmGenerator` (ABC) : boucle par chapitre (prompt → LLM → parse → items),
   contexte de prompt **commun** construit ici (seul `_template_name` varie), rendu via
   `_render_content` ; `_finalize_render` par défaut sans corrigé.
4. `_EvaluativePerChapterLlmGenerator` (ABC) : override `_finalize_render` pour produire
   sujet + corrigé selon `separate_correction`.

- [ ] **Step 1 : Test (échoue)** — `tests/unit/pedagogy/test_generators_base.py` :

```python
"""Tests du socle des générateurs LLM (retry/events + parsing typé)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from fahmi2.core.errors.exceptions import LLMError
from fahmi2.core.errors.severity import Severity
from fahmi2.core.retry.policy import RetryPolicy
from fahmi2.domain.enums import Language, SupportType
from fahmi2.infra.llm._fakes import FakeLLMProvider
from fahmi2.infra.llm.interface import LLMResponse, Message
from fahmi2.infra.prompts.loader import PromptLoader
from fahmi2.infra.storage.fs_artifacts import FsArtifactStore
from fahmi2.pedagogy.events import PedagogyEvent, SupportRetryAttempt
from fahmi2.pedagogy.generators._base import (
    invoke_support_llm,
    require_list,
    require_str,
)
from fahmi2.pedagogy.support_generator import SupportContext
from fahmi2.pipeline.event_bus import EventBus
from fahmi2.pipeline.pause_token import PauseToken


class _FailingThenOk:
    """Provider factice : échoue n fois (LLM.RATE_LIMIT) puis répond."""

    def __init__(self, *, fail_times: int) -> None:
        self._fail_times = fail_times
        self.calls = 0

    def chat(self, **_kwargs: Any) -> LLMResponse:
        self.calls += 1
        if self.calls <= self._fail_times:
            raise LLMError(
                code="LLM.RATE_LIMIT", user_message="rate", severity=Severity.ERROR
            )
        return LLMResponse(
            content="{}", thinking_content=None, prompt_tokens=1,
            completion_tokens=1, cached_prompt_tokens=0, cost_usd=0.0,
        )

    def estimate_cost(self, **_kwargs: Any) -> float:
        return 0.0


def _ctx(provider: Any, make_pedagogy_settings: Any) -> SupportContext:
    return SupportContext(
        pedagogy=make_pedagogy_settings(),
        generation_output_dir=Path("."),
        pedagogy_dir=Path("."),
        llm_provider=provider,
        prompts=PromptLoader(),
        artifacts=FsArtifactStore(),
        event_bus=EventBus[PedagogyEvent](),
        pause_token=PauseToken(),
        retry_policy=RetryPolicy(max_attempts=3, jitter=False, initial_delay_seconds=0.001),
    )


def test_invoke_retries_then_succeeds_and_emits_event(
    make_pedagogy_settings: Any,
) -> None:
    provider = _FailingThenOk(fail_times=1)
    ctx = _ctx(provider, make_pedagogy_settings)
    events: list[PedagogyEvent] = []
    ctx.event_bus.subscribe(events.append)

    response = invoke_support_llm(
        ctx, support_type=SupportType.QCM, language=Language.FR,
        system_prompt=None, user_prompt="x",
    )
    assert response.content == "{}"
    assert provider.calls == 2
    assert any(isinstance(e, SupportRetryAttempt) for e in events)


def test_invoke_gives_up_after_max_attempts(make_pedagogy_settings: Any) -> None:
    provider = _FailingThenOk(fail_times=10)
    ctx = _ctx(provider, make_pedagogy_settings)
    with pytest.raises(LLMError):
        invoke_support_llm(
            ctx, support_type=SupportType.QCM, language=Language.FR,
            system_prompt=None, user_prompt="x",
        )


def test_require_helpers() -> None:
    assert require_str({"a": "x"}, "a", context_label="t") == "x"
    assert require_list({"a": [1, 2]}, "a", context_label="t") == [1, 2]
    with pytest.raises(LLMError, match="INVALID_SCHEMA|inattendue"):
        require_str({"a": 1}, "a", context_label="t")
    with pytest.raises(LLMError):
        require_list({}, "missing", context_label="t")
```

- [ ] **Step 2 : Lancer** → FAIL.

- [ ] **Step 3 : Créer `pedagogy/generators/_base.py`** :

```python
"""Socle des générateurs de supports LLM.

Mutualise : l'appel LLM avec retry (parité moteur via ``default_classify`` +
émission de ``SupportRetryAttempt``), des helpers de parsing JSON typé, et un
template-method par chapitre (boucle → prompt → LLM → parse → items → rendu).
Le contexte de prompt commun (public/Bloom/densité/directives/langue/glossaire +
chapitre) est construit ici : un générateur concret ne déclare que son
``_template_name``, son parsing et son rendu.
"""

from __future__ import annotations

from abc import abstractmethod
from datetime import UTC, datetime
from typing import Any

from fahmi2.core.errors.error_info import ErrorInfo
from fahmi2.core.errors.exceptions import Fahmi2Error, LLMError
from fahmi2.core.errors.severity import Severity
from fahmi2.core.retry.classification import default_classify
from fahmi2.core.retry.policy import RetryDecision
from fahmi2.core.retry.runner import with_retry
from fahmi2.domain.enums import Language, SupportType
from fahmi2.domain.glossary import Term
from fahmi2.domain.supports import SupportArtifact, SupportItem
from fahmi2.infra.llm.interface import LLMResponse
from fahmi2.infra.llm.invocation import invoke_llm_chat
from fahmi2.pedagogy.chapters import Chapter
from fahmi2.pedagogy.events import SupportRetryAttempt
from fahmi2.pedagogy.labels import (
    audience_label,
    bloom_label,
    density_label,
    format_glossary_terms,
    language_label,
)
from fahmi2.pedagogy.support_generator import SupportContext, SupportGenerator

_INVALID_SCHEMA_CODE = "LLM.INVALID_SCHEMA"


def _now() -> datetime:
    """Horodatage UTC courant."""
    return datetime.now(tz=UTC)


def _schema_error(context_label: str, detail: str) -> LLMError:
    """Construit une ``LLMError`` de schéma invalide (non retryable)."""
    return LLMError(
        code=_INVALID_SCHEMA_CODE,
        user_message=f"Réponse du LLM inattendue pour {context_label} : {detail}",
        severity=Severity.ERROR,
        technical_details={"context_label": context_label, "detail": detail},
    )


def require_mapping(value: Any, *, context_label: str) -> dict[str, Any]:  # noqa: ANN401
    """Exige un objet JSON (dict)."""
    if not isinstance(value, dict):
        raise _schema_error(context_label, "objet JSON attendu")
    return value


def require_list(
    mapping: dict[str, Any], key: str, *, context_label: str
) -> list[Any]:
    """Exige une liste à ``key``."""
    value = mapping.get(key)
    if not isinstance(value, list):
        raise _schema_error(context_label, f"liste attendue pour « {key} »")
    return value


def require_str(mapping: dict[str, Any], key: str, *, context_label: str) -> str:
    """Exige une chaîne non vide à ``key``."""
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        raise _schema_error(context_label, f"chaîne attendue pour « {key} »")
    return value


def require_int(mapping: dict[str, Any], key: str, *, context_label: str) -> int:
    """Exige un entier à ``key`` (rejette ``bool``)."""
    value = mapping.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise _schema_error(context_label, f"entier attendu pour « {key} »")
    return value


def require_bool(mapping: dict[str, Any], key: str, *, context_label: str) -> bool:
    """Exige un booléen à ``key``."""
    value = mapping.get(key)
    if not isinstance(value, bool):
        raise _schema_error(context_label, f"booléen attendu pour « {key} »")
    return value


def require_str_list(
    mapping: dict[str, Any], key: str, *, context_label: str
) -> tuple[str, ...]:
    """Exige une liste de chaînes non vide à ``key``."""
    raw = require_list(mapping, key, context_label=context_label)
    out = [str(x) for x in raw if str(x).strip()]
    if not out:
        raise _schema_error(context_label, f"liste de chaînes attendue pour « {key} »")
    return tuple(out)


def invoke_support_llm(
    ctx: SupportContext,
    *,
    support_type: SupportType,
    language: Language,
    system_prompt: str | None,
    user_prompt: str,
) -> LLMResponse:
    """Appelle le LLM avec retry et émission de ``SupportRetryAttempt``.

    Args:
        ctx: Contexte d'exécution.
        support_type: Support en cours (pour les events).
        language: Langue (pour les events).
        system_prompt: Prompt système optionnel.
        user_prompt: Prompt utilisateur.

    Returns:
        La ``LLMResponse``.

    Raises:
        Fahmi2Error: La dernière erreur si toutes les tentatives échouent.
    """
    attempts = {"n": 0}

    def _once() -> LLMResponse:
        attempts["n"] += 1
        try:
            return invoke_llm_chat(
                ctx.llm_provider,
                model=str(ctx.pedagogy.llm_model),
                config=ctx.pedagogy.llm_config,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )
        except Fahmi2Error as exc:
            if default_classify(exc) is RetryDecision.RETRY:
                ctx.event_bus.publish(
                    SupportRetryAttempt(
                        timestamp=_now(),
                        support_type=support_type,
                        language=language,
                        attempt=attempts["n"],
                        delay_seconds=ctx.retry_policy.compute_delay(
                            attempt=attempts["n"]
                        ),
                        error=ErrorInfo.from_exception(exc),
                    )
                )
            raise

    return with_retry(_once, policy=ctx.retry_policy, classify=default_classify)


class _PerChapterLlmGenerator(SupportGenerator):
    """Base des générateurs LLM produisant des items **par chapitre**."""

    @property
    def uses_llm(self) -> bool:
        """Générateur LLM."""
        return True

    @property
    @abstractmethod
    def _template_name(self) -> str:
        """Nom du template Jinja2 (sans extension)."""

    @abstractmethod
    def _parse_items(
        self, payload: Any, *, chapter: Chapter  # noqa: ANN401
    ) -> tuple[SupportItem, ...]:
        """Convertit la réponse JSON d'un chapitre en items typés."""

    @abstractmethod
    def _render_content(
        self, items: tuple[SupportItem, ...], *, language: Language
    ) -> str:
        """Rend le support en Markdown (vue combinée, avec réponses si évaluatif)."""

    def generate(
        self,
        ctx: SupportContext,
        *,
        language: Language,
        chapters: tuple[Chapter, ...],
        glossary: tuple[Term, ...],
    ) -> SupportArtifact:
        """Génère le support par chapitre (cf. ``SupportGenerator.generate``)."""
        from fahmi2.pedagogy.generators._base import parse_support_json  # local

        items: list[SupportItem] = []
        total_cost = 0.0
        for chapter in chapters:
            ctx.pause_token.wait_if_paused()
            ctx.pause_token.raise_if_cancelled()
            user_prompt = ctx.prompts.render(
                self._template_name,
                **self._chapter_context(ctx, chapter=chapter, language=language,
                                        glossary=glossary),
            )
            response = invoke_support_llm(
                ctx, support_type=self.support_type, language=language,
                system_prompt=None, user_prompt=user_prompt,
            )
            total_cost += response.cost_usd
            payload = parse_support_json(
                response.content,
                context_label=f"{self.support_type.value}:{chapter.index}",
            )
            items.extend(self._parse_items(payload, chapter=chapter))
        items_t = tuple(items)
        subject, correction = self._finalize_render(ctx, items_t, language=language)
        return SupportArtifact(
            support_type=self.support_type,
            language=language,
            items=items_t,
            rendered_markdown=subject,
            correction_markdown=correction,
            cost_usd=total_cost,
        )

    def _chapter_context(
        self,
        ctx: SupportContext,
        *,
        chapter: Chapter,
        language: Language,
        glossary: tuple[Term, ...],
    ) -> dict[str, Any]:
        """Contexte Jinja2 commun à tous les prompts par chapitre."""
        ped = ctx.pedagogy
        return {
            "output_language_label": language_label(language),
            "audience_label": audience_label(ped.target_audience),
            "bloom_label": bloom_label(ped.bloom_objective),
            "density_label": density_label(ped.density),
            "pedagogy_directives": ped.pedagogy_directives,
            "glossary_terms": format_glossary_terms(glossary),
            "chapter_title": chapter.title,
            "chapter_markdown": chapter.body_markdown,
        }

    def _finalize_render(
        self,
        ctx: SupportContext,
        items: tuple[SupportItem, ...],
        *,
        language: Language,
    ) -> tuple[str, str | None]:
        """Rendu final : (sujet, corrigé). Par défaut : combiné, sans corrigé."""
        del ctx
        return self._render_content(items, language=language), None


class _EvaluativePerChapterLlmGenerator(_PerChapterLlmGenerator):
    """Base des générateurs **évaluatifs** par chapitre (corrigé séparable)."""

    @abstractmethod
    def _render_subject(
        self, items: tuple[SupportItem, ...], *, language: Language
    ) -> str:
        """Rend le **sujet** seul (sans réponses)."""

    @abstractmethod
    def _render_correction(
        self, items: tuple[SupportItem, ...], *, language: Language
    ) -> str:
        """Rend le **corrigé** (réponses + justifications)."""

    def _finalize_render(
        self,
        ctx: SupportContext,
        items: tuple[SupportItem, ...],
        *,
        language: Language,
    ) -> tuple[str, str | None]:
        """Sujet+corrigé séparés si demandé, sinon rendu combiné."""
        if self.support_type in ctx.pedagogy.separate_correction:
            return (
                self._render_subject(items, language=language),
                self._render_correction(items, language=language),
            )
        return self._render_content(items, language=language), None
```

  > `parse_support_json` = alias importable de `parse_llm_json` pour cohérence de
  > nommage local. Au lieu d'un import local, ajouter en tête :
  > `from fahmi2.infra.llm.invocation import parse_json as parse_support_json`
  > **n'existe pas** ; utiliser directement `parse_llm_json`. Corriger le code de
  > `generate` pour : `from fahmi2.infra.llm.invocation import parse_llm_json` en tête
  > et `payload = parse_llm_json(response.content, context_label=...)`. **Retirer**
  > l'import local et l'usage de `parse_support_json`.

- [ ] **Step 4 : Lancer** → PASS.

Run: `.venv\Scripts\python.exe -m pytest tests/unit/pedagogy/test_generators_base.py -q`

---

## Tasks 6–13 : Les 8 générateurs (un par support)

> **Patron commun (TDD pour chacun) :** Step 1 écrire le test (FakeLLMProvider avec
> `default_response=LLMResponse(content=<JSON crafté>)`, appeler `generate` avec un
> `chapters=(Chapter(...),)` ou whole-doc, asserter items typés + rendu + corrigé) →
> Step 2 FAIL → Step 3 créer le module générateur + son prompt `.j2` → Step 4 PASS.
> Le **contexte de prompt** est fourni par le socle ; chaque générateur déclare
> `support_type`, `_template_name`, `_parse_items`, `_render_content` (+ pour les
> évaluatifs `_render_subject`/`_render_correction`).

Les **schémas JSON** attendus (contrat prompt ↔ parsing) :

| Support | Base | Schéma JSON | Entité |
|---|---|---|---|
| `key_points` | `_PerChapterLlmGenerator` | `{"points": ["…"]}` | `KeyPoints` (1/chapitre) |
| `flashcards_concepts` | `_PerChapterLlmGenerator` | `{"cards": [{"front","back"}]}` | `Flashcard` |
| `revision_sheet` | `_PerChapterLlmGenerator` | `{"summary_markdown": "…"}` | `RevisionSheet` (1/chapitre) |
| `qcm` | `_EvaluativePerChapterLlmGenerator` | `{"questions":[{"question","choices":[…],"correct_index","justification"}]}` | `QcmItem` |
| `true_false` | `_EvaluativePerChapterLlmGenerator` | `{"items":[{"statement","is_true","justification"}]}` | `TrueFalseItem` |
| `cloze` | `_EvaluativePerChapterLlmGenerator` | `{"items":[{"text","answers":[…]}]}` | `ClozeItem` |
| `open_questions` | `_EvaluativePerChapterLlmGenerator` | `{"questions":[{"question","expected_points":[…]}]}` | `OpenQuestion` |
| `mock_exam` | doc-entier (cf. Task 13) | `{"title","sections":[{"title","statement_markdown"}],"grading_markdown"}` | `MockExam` |

`source_ref` des items par chapitre = `chapter.anchor`. `tags` des flashcards concepts
= `(support_type.value, language.value, chapter.anchor)`.

### Task 6 : `key_points` (non évaluatif — valide le socle par chapitre)

**Files:** Create `src/fahmi2/pedagogy/generators/key_points.py`,
`src/fahmi2/infra/prompts/defaults/pedagogy_key_points.j2`

- [ ] Générateur :

```python
"""Générateur « Points clés » : 3–5 idées clés par chapitre (LLM)."""

from __future__ import annotations

from typing import Any

from fahmi2.domain.enums import Language, SupportType
from fahmi2.domain.supports import KeyPoints, SupportItem
from fahmi2.pedagogy.chapters import Chapter
from fahmi2.pedagogy.generators._base import (
    _PerChapterLlmGenerator,
    require_mapping,
    require_str_list,
)

_TEMPLATE_NAME = "pedagogy_key_points"
_HEADING = "Points clés"


class KeyPointsGenerator(_PerChapterLlmGenerator):
    """Produit un bloc de points clés par chapitre."""

    @property
    def support_type(self) -> SupportType:
        """Type de support."""
        return SupportType.KEY_POINTS

    @property
    def _template_name(self) -> str:
        """Template de prompt."""
        return _TEMPLATE_NAME

    def _parse_items(
        self, payload: Any, *, chapter: Chapter  # noqa: ANN401
    ) -> tuple[SupportItem, ...]:
        """Parse ``{"points": [...]}`` en un ``KeyPoints``."""
        label = f"{self.support_type.value}:{chapter.index}"
        mapping = require_mapping(payload, context_label=label)
        points = require_str_list(mapping, "points", context_label=label)
        return (
            KeyPoints(
                chapter_title=chapter.title, points=points, source_ref=chapter.anchor
            ),
        )

    def _render_content(
        self, items: tuple[SupportItem, ...], *, language: Language
    ) -> str:
        """Rend les points clés groupés par chapitre."""
        parts = [f"# {_HEADING} ({language.value})", ""]
        for item in items:
            assert isinstance(item, KeyPoints)
            parts.append(f"## {item.chapter_title}")
            parts.append("")
            parts.extend(f"- {p}" for p in item.points)
            parts.append("")
        return "\n".join(parts).rstrip() + "\n"
```

- [ ] Prompt `pedagogy_key_points.j2` :

```jinja
Tu es un pédagogue. À partir du chapitre ci-dessous, dégage les **points clés** à retenir.

Public cible : {{ audience_label }}.
Objectif cognitif : {{ bloom_label }}.
Densité attendue : {{ density_label }}.
{% if pedagogy_directives -%}
Directives supplémentaires : {{ pedagogy_directives }}
{%- endif %}

Rédige en {{ output_language_label }}, 3 à 5 puces concises et autoportantes, fidèles
au contenu (pas d'invention).
{% if glossary_terms %}
Glossaire de référence (réutilise la terminologie exacte) :
{{ glossary_terms }}
{% endif %}
Réponds STRICTEMENT en JSON valide, sans préambule :
{"points": ["...", "..."]}

---
Chapitre : {{ chapter_title }}

{{ chapter_markdown }}
```

> Les **tests** des Tasks 6–13 sont regroupés dans
> `tests/unit/pedagogy/test_llm_generators.py` (un test par générateur, avec un JSON
> craft é via `FakeLLMProvider(default_response=…)`). Exemple pour `key_points` :

```python
def test_key_points_generator(tmp_path: Path, make_pedagogy_settings: Any) -> None:
    provider = FakeLLMProvider(
        default_response=LLMResponse(
            content='{"points": ["Idée 1", "Idée 2"]}',
            thinking_content=None, prompt_tokens=1, completion_tokens=1,
            cached_prompt_tokens=0, cost_usd=0.0,
        )
    )
    artifact = KeyPointsGenerator().generate(
        _ctx(provider, make_pedagogy_settings),
        language=Language.FR,
        chapters=(Chapter(index=1, title="Bases", anchor="1-bases", body_markdown="…"),),
        glossary=(),
    )
    assert isinstance(artifact.items[0], KeyPoints)
    assert artifact.items[0].points == ("Idée 1", "Idée 2")
    assert "Idée 1" in artifact.rendered_markdown
    assert artifact.correction_markdown is None
```

(`_ctx` est un helper local du fichier de tests, identique à celui de
`test_generators_base.py` mais réutilisable ; le factoriser en tête du fichier.)

### Task 7 : `flashcards_concepts` (non évaluatif)

- [ ] `_parse_items` : `cards = require_list({"cards"})` ; pour chaque carte
  `require_mapping` + `require_str("front")` + `require_str("back")` →
  `Flashcard(front, back, source_ref=chapter.anchor, tags=(support, lang, chapter.anchor))`.
- [ ] `_render_content` : titre + blocs `### {front}` / `{back}` séparés par `---`
  (réutiliser le style de `flashcards_glossary`).
- [ ] Prompt `pedagogy_flashcards_concepts.j2` : produire `{"cards":[{"front","back"}]}`,
  Q/R sur les idées clés du chapitre (mêmes variables communes).
- [ ] Test : JSON `{"cards":[{"front":"Q","back":"R"}]}` → 1 `Flashcard`, rendu contient `Q`.

### Task 8 : `qcm` (évaluatif + dé-biaisage déterministe)

**Files:** Create `src/fahmi2/pedagogy/generators/qcm.py`, `…/defaults/pedagogy_qcm.j2`

- [ ] `_parse_items` : `questions = require_list("questions")` ; par question
  `require_str("question")`, `choices = require_str_list("choices")`,
  `correct_index = require_int("correct_index")`, `justification = require_str("justification")`
  → `QcmItem(...)` (le `__post_init__` valide l'index). Puis **dé-biaisage** :
  `return _balance(items)`.
- [ ] `_balance(items)` : pour l'item *i*, repositionne la bonne réponse à
  `i % len(choices)` (rotation déterministe) et met à jour `correct_index`.

```python
def _balance(items: tuple[QcmItem, ...]) -> tuple[QcmItem, ...]:
    """Équilibre la position de la bonne réponse sur l'ensemble des items."""
    balanced: list[QcmItem] = []
    for i, item in enumerate(items):
        target = i % len(item.choices)
        choices = list(item.choices)
        correct = choices.pop(item.correct_index)
        choices.insert(target, correct)
        balanced.append(
            QcmItem(
                question=item.question,
                choices=tuple(choices),
                correct_index=target,
                justification=item.justification,
                source_ref=item.source_ref,
            )
        )
    return tuple(balanced)
```

- [ ] `_render_content` (combiné) : `### Question` + choix `A. … B. …` (lettres via
  constante `_CHOICE_LETTERS = "ABCDEFGHIJ"`) + `**Réponse : {lettre}** — {justification}`.
- [ ] `_render_subject` : question + choix **sans** réponse.
- [ ] `_render_correction` : `### Question` + `Réponse : {lettre}` + justification.
- [ ] Prompt `pedagogy_qcm.j2` : produire
  `{"questions":[{"question","choices":["…"],"correct_index":N,"justification":"…"}]}`,
  4 propositions plausibles dont 1 correcte, `correct_index` 0-based.
- [ ] Tests : (a) parsing + `correct_index` valide ; (b) **dé-biaisage** : avec 3 questions
  toutes `correct_index=0` en entrée, vérifier que les positions résultantes sont
  `0,1,2` ; (c) `separate_correction={QCM}` → `correction_markdown is not None` et le
  sujet ne contient pas « Réponse » ; (d) sans separate → `correction_markdown is None`.

### Task 9 : `true_false` (évaluatif)

- [ ] `_parse_items` : `items = require_list("items")` ; `statement=require_str`,
  `is_true=require_bool`, `justification=require_str` → `TrueFalseItem`.
- [ ] `_render_content` : `- {statement}` + `**Réponse : Vrai/Faux** — {justification}`.
  `_render_subject` : `- {statement}  (Vrai / Faux ?)`. `_render_correction` : statement +
  Vrai/Faux + justification. Constantes `_TRUE_LABEL="Vrai"`, `_FALSE_LABEL="Faux"`.
- [ ] Prompt `pedagogy_true_false.j2` → `{"items":[{"statement","is_true","justification"}]}`.
- [ ] Test JSON crafté.

### Task 10 : `cloze` (évaluatif)

- [ ] `_parse_items` : `items=require_list("items")` ; `text=require_str("text")`,
  `answers=require_str_list("answers")` → `ClozeItem`.
- [ ] `_render_content` : texte + `Réponses : a, b`. `_render_subject` : texte seul.
  `_render_correction` : texte + réponses.
- [ ] Prompt `pedagogy_cloze.j2` → phrases à trous (marqueur `___`) +
  `{"items":[{"text","answers":["…"]}]}`.
- [ ] Test JSON crafté.

### Task 11 : `open_questions` (évaluatif)

- [ ] `_parse_items` : `questions=require_list("questions")` ; `question=require_str`,
  `expected_points=require_str_list("expected_points")` → `OpenQuestion`.
- [ ] `_render_content` : `### {question}` + `Éléments attendus :` + puces.
  `_render_subject` : `### {question}` seul. `_render_correction` : question + puces.
- [ ] Prompt `pedagogy_open_questions.j2` → `{"questions":[{"question","expected_points":["…"]}]}`.
- [ ] Test JSON crafté.

### Task 12 : `revision_sheet` (non évaluatif)

- [ ] `_parse_items` : `summary = require_str("summary_markdown")` →
  `(RevisionSheet(chapter_title=chapter.title, summary_markdown=summary, source_ref=chapter.anchor),)`.
- [ ] `_render_content` : `# Fiche de révision ({lang})` + par chapitre
  `## {chapter_title}` + `{summary_markdown}`.
- [ ] Prompt `pedagogy_revision_sheet.j2` → synthèse Markdown du chapitre,
  `{"summary_markdown":"..."}`.
- [ ] Test JSON crafté.

### Task 13 : `mock_exam` (évaluatif, **doc-entier**)

**Files:** Create `src/fahmi2/pedagogy/generators/mock_exam.py`, `…/defaults/pedagogy_mock_exam.j2`

> N'hérite **pas** de `_PerChapterLlmGenerator` (pas de boucle par chapitre) : implémente
> `generate` directement, en concaténant les chapitres en `consolidated_markdown` et via
> `invoke_support_llm`. Reste **évaluatif** (sujet + corrigé séparable).

- [ ] Générateur :

```python
"""Générateur « Examen blanc » : sujet composite + barème (LLM, doc entier)."""

from __future__ import annotations

from typing import Any

from fahmi2.domain.enums import Language, SupportType
from fahmi2.domain.glossary import Term
from fahmi2.domain.supports import MockExam, MockExamSection, SupportArtifact, SupportItem
from fahmi2.infra.llm.invocation import parse_llm_json
from fahmi2.pedagogy.chapters import Chapter
from fahmi2.pedagogy.generators._base import (
    invoke_support_llm,
    require_list,
    require_mapping,
    require_str,
)
from fahmi2.pedagogy.labels import (
    audience_label,
    bloom_label,
    density_label,
    format_glossary_terms,
    language_label,
)
from fahmi2.pedagogy.support_generator import SupportContext, SupportGenerator

_TEMPLATE_NAME = "pedagogy_mock_exam"
_CHAPTER_JOIN = "\n\n"


class MockExamGenerator(SupportGenerator):
    """Produit un examen blanc composite (sujet + barème) sur tout le document."""

    @property
    def support_type(self) -> SupportType:
        return SupportType.MOCK_EXAM

    @property
    def uses_llm(self) -> bool:
        return True

    def generate(
        self,
        ctx: SupportContext,
        *,
        language: Language,
        chapters: tuple[Chapter, ...],
        glossary: tuple[Term, ...],
    ) -> SupportArtifact:
        consolidated = _CHAPTER_JOIN.join(
            f"# {c.index}. {c.title}\n\n{c.body_markdown}" for c in chapters
        )
        ped = ctx.pedagogy
        prompt = ctx.prompts.render(
            _TEMPLATE_NAME,
            output_language_label=language_label(language),
            audience_label=audience_label(ped.target_audience),
            bloom_label=bloom_label(ped.bloom_objective),
            density_label=density_label(ped.density),
            pedagogy_directives=ped.pedagogy_directives,
            glossary_terms=format_glossary_terms(glossary),
            consolidated_markdown=consolidated,
        )
        response = invoke_support_llm(
            ctx, support_type=self.support_type, language=language,
            system_prompt=None, user_prompt=prompt,
        )
        exam = _parse_exam(response.content, context_label=self.support_type.value)
        separate = self.support_type in ped.separate_correction
        subject = _render_subject(exam, language=language)
        correction = exam.grading_markdown if separate else None
        rendered = subject if separate else _render_combined(exam, language=language)
        return SupportArtifact(
            support_type=self.support_type,
            language=language,
            items=(exam,),
            rendered_markdown=rendered,
            correction_markdown=correction,
            cost_usd=response.cost_usd,
        )
```

  + fonctions module `_parse_exam`, `_render_subject`, `_render_combined` :
  - `_parse_exam` : `require_mapping`, `title=require_str`, `sections=require_list` →
    chaque section `require_str("title")` + `require_str("statement_markdown")`,
    `grading_markdown=require_str` → `MockExam`.
  - `_render_subject` : `# {title}` + par section `## {title}` + statement.
  - `_render_combined` : sujet + `## Barème` + grading_markdown.

- [ ] Prompt `pedagogy_mock_exam.j2` → `consolidated_markdown` en entrée,
  `{"title","sections":[{"title","statement_markdown"}],"grading_markdown"}`.
- [ ] Test : JSON crafté → `MockExam` avec 1 section ; `separate_correction={MOCK_EXAM}`
  → `correction_markdown == grading_markdown` et sujet sans barème.

---

## Task 14 : Enregistrer les 8 prompts dans l'éditeur de prompts

> Directive utilisateur : les prompts pédagogie doivent être **éditables** via
> « Édition → Modifier les prompts ». Le catalogue est la constante `_TEMPLATE_METADATA`.

**Files:** Modify `src/fahmi2/app/prompts_service.py` ;
Modify `tests/unit/app/test_prompts_service.py` ;
Create `tests/unit/infra/prompts/test_pedagogy_prompts.py`

- [ ] **Step 1 : Ajouter 8 `PromptTemplateMeta`** à la fin du tuple `_TEMPLATE_METADATA`
  (ordre : flashcards concepts, qcm, vrai/faux, cloze, questions ouvertes, fiche,
  points clés, examen blanc), `display_name` préfixé « Pédagogie — … », descriptions FR.

- [ ] **Step 2 : Assouplir `test_list_templates_covers_all_llm_phases`** : remplacer
  `assert names == expected` par `assert expected <= names`, et ajouter :

```python
def test_list_templates_includes_pedagogy_supports(tmp_path: Path) -> None:
    service = PromptsService(override_dir=tmp_path)
    names = {meta.name for meta in service.list_templates()}
    expected = {
        "pedagogy_flashcards_concepts",
        "pedagogy_qcm",
        "pedagogy_true_false",
        "pedagogy_cloze",
        "pedagogy_open_questions",
        "pedagogy_revision_sheet",
        "pedagogy_key_points",
        "pedagogy_mock_exam",
    }
    assert expected <= names
```

- [ ] **Step 3 : Smoke render des 8 prompts** — `test_pedagogy_prompts.py` : pour chaque
  nom de template pédagogie, `PromptLoader().render(name, **sample_context)` ne lève pas
  et produit une chaîne non vide. Le `sample_context` couvre toutes les variables
  (communes + `chapter_title`/`chapter_markdown` + `consolidated_markdown`). Un template
  qui n'utilise pas une variable l'ignore : fournir un sur-ensemble est sûr.

- [ ] **Step 4 : Lancer** :

Run: `.venv\Scripts\python.exe -m pytest tests/unit/app/test_prompts_service.py tests/unit/infra/prompts/test_pedagogy_prompts.py -q`

---

## Task 15 : Factory du registre des générateurs

**Files:** Create `src/fahmi2/pedagogy/default_registry.py` ;
Test `tests/unit/pedagogy/test_default_registry.py`

- [ ] **Step 1 : Test** : `build_default_support_registry()` retourne un
  `SupportGeneratorRegistry` avec un générateur pour **chacun** des 9 `SupportType`
  (`registry.has(st)` pour tout `st in SupportType`), et `ordered_generators()` a 9
  éléments dans l'ordre canonique.

- [ ] **Step 2 : Créer `default_registry.py`** :

```python
"""Factory du registre des générateurs de supports (les 9 supports)."""

from __future__ import annotations

from fahmi2.pedagogy.generators.cloze import ClozeGenerator
from fahmi2.pedagogy.generators.flashcards_concepts import FlashcardsConceptsGenerator
from fahmi2.pedagogy.generators.flashcards_glossary import FlashcardsGlossaryGenerator
from fahmi2.pedagogy.generators.key_points import KeyPointsGenerator
from fahmi2.pedagogy.generators.mock_exam import MockExamGenerator
from fahmi2.pedagogy.generators.open_questions import OpenQuestionsGenerator
from fahmi2.pedagogy.generators.qcm import QcmGenerator
from fahmi2.pedagogy.generators.revision_sheet import RevisionSheetGenerator
from fahmi2.pedagogy.generators.true_false import TrueFalseGenerator
from fahmi2.pedagogy.support_registry import SupportGeneratorRegistry


def build_default_support_registry() -> SupportGeneratorRegistry:
    """Construit le registre avec les 9 générateurs de supports.

    Returns:
        Un ``SupportGeneratorRegistry`` peuplé (flashcards glossaire + 8 LLM).
    """
    return SupportGeneratorRegistry(
        [
            FlashcardsGlossaryGenerator(),
            FlashcardsConceptsGenerator(),
            QcmGenerator(),
            TrueFalseGenerator(),
            ClozeGenerator(),
            OpenQuestionsGenerator(),
            RevisionSheetGenerator(),
            KeyPointsGenerator(),
            MockExamGenerator(),
        ]
    )
```

- [ ] **Step 3 : Lancer** → PASS.

---

## Task 16 : Vérifications systématiques + docs + commit

- [ ] **Step 1** : `.venv\Scripts\python.exe -m pytest -q` → tout vert.
- [ ] **Step 2** : `.venv\Scripts\python.exe -m ruff check .` → clean (attention :
  imports `_base` privés importés par les générateurs — préfixe `_` autorisé dans le
  même package ; `assert isinstance(...)` dans les rendus → OK pour le narrowing mypy ;
  vérifier `ANN401`/`PLR` sur les helpers `require_*`).
- [ ] **Step 3** : `.venv\Scripts\python.exe -m mypy src tests` → Success.
- [ ] **Step 4 : Docs** : `docs/04-parametrage.md` (catalogue des prompts éditables :
  ajouter les 8 `pedagogy_*`), `docs/02-presentation-technique.md` (corrigé séparé
  `<support>.corrige.md` + note retry pédagogie), doc d'avancement (SP2/03 → Fait),
  `CHANGELOG.md`. Note packaging : les 8 `.j2` sont bundlés comme les défauts existants
  (vérifier `packaging/fahmi2.spec` au build, non versionné).
- [ ] **Step 5 : Commit** :

```bash
git add -A
git commit -m "feat(pedagogy): 8 generateurs LLM + prompts editables (SP2/03)"
```

---

## Self-review (avant de coder, et après)

**Couverture du design :**
- §3.4 entités (`QcmItem`, `TrueFalseItem`, `ClozeItem`, `OpenQuestion`, `RevisionSheet`,
  `KeyPoints`, `MockExam`) → Task 2.
- §6 8 générateurs LLM + corrigés séparés + dé-biaisage QCM → Tasks 5–13.
- §7 prompts `pedagogy_*.j2` (variables communes) → Tasks 6–13 + smoke Task 14.
- Éditabilité prompts (directive utilisateur) → Task 14.
- retry « mêmes codes retryables » → Tasks 1, 5.

**Hors périmètre (tracé) :** onglet UI + estimation coût + plafond + fraîcheur affichée +
câblage `app_main` du registre/orchestrateur (SP2/04) ; passe LLM de dé-biaisage des
distracteurs QCM (itération produit via l'éditeur, design §12) ; exports (SP3).

**Cohérence types/signatures :** `SupportGenerator.generate(ctx, *, language, chapters,
glossary) -> SupportArtifact` (inchangé) ; `SupportArtifact.correction_markdown`
(Task 2/3, lu Task 3 orchestrateur) ; `invoke_support_llm(ctx, *, support_type, language,
system_prompt, user_prompt)` (Tasks 5/13) ; `require_*` (Task 5, util. Tasks 6–13) ;
`SupportContext.retry_policy` (Tasks 3/5) ; `SupportRetryAttempt` (Tasks 3/5) ; classes de
générateurs nommées `<Support>Generator` (Tasks 6–13, réf. Task 15).
