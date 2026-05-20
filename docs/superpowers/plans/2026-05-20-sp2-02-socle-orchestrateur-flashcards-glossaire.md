# SP2 · Plan 02 — Socle orchestrateur + tranche verticale flashcards glossaire

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (inline, sans subagents).
> **Design** : [`../specs/2026-05-20-sp2-sp3-supports-revision-design.md`](../specs/2026-05-20-sp2-sp3-supports-revision-design.md) (§§5, 6, 10).
> **Avancement** : [`./2026-05-20-sp2-sp3-00-avancement.md`](./2026-05-20-sp2-sp3-00-avancement.md).
> Steps use checkbox (`- [ ]`) syntax.

**Goal:** Poser le socle de génération des supports pédagogiques (générateur +
registre + contexte DI + orchestrateur dédié léger + parseur de chapitres +
lecture glossaire DB + manifeste de fraîcheur + events) et livrer **de bout en
bout** la première tranche verticale : **flashcards glossaire (sans LLM)** →
artefacts JSON + Markdown sous `pedagogy/`.

**Architecture:** Un nouveau package `pedagogy/` calqué sur `pipeline/`
(générateurs ≈ handlers, registre, contexte DI, events) ; un `SupportsOrchestrator`
dans `app/` calqué sur `RunOrchestrator` ; **aucune dépendance** `pipeline → pedagogy`.
On **généralise** les helpers LLM/JSON de `pipeline/handlers/_base.py` vers
`infra/llm/invocation.py` (refactor DRY, handlers existants délégant). On rend
`EventBus` **générique** (`EventBus[E]`) pour porter aussi bien `PipelineEvent` que
`PedagogyEvent`, sans coupler les deux familles. Persistance = **fichiers** sous
`pedagogy/` + manifeste `pedagogy/manifest.json` (hash réglages + mtime source par
langue) pour la reprise coarse et l'indicateur de péremption.

**Tech Stack:** Python 3.12, dataclasses frozen, `pytest`, `ruff`, `mypy --strict`,
SQLite (lecture glossaire), Jinja2 (réservé SP2/03).

**Rappels directives :** pas de magic value (constantes centralisées), docstrings
Google (`Args`/`Returns`/`Raises` + docstring de module), réutiliser les patterns
existants (`PhaseHandler`/`PhaseRegistry`/`PhaseContext`/`FsArtifactStore`/`with_retry`),
DRY/YAGNI/KISS/SRP/SoC, entités domaine `frozen` + helpers privés `_method` +
modules internes `_module.py`. **Tout en français** (orthographe avec accents).

**Note prompts (directive utilisateur) :** SP2/02 n'introduit **aucun** prompt LLM
(le seul générateur, flashcards glossaire, est **sans LLM**). Les prompts pédagogie
arrivent au **SP2/03** : chaque `pedagogy_<support>.j2` devra être **éditable via
« Édition → Modifier les prompts »**, c.-à-d. ajouté à la constante
`_TEMPLATE_METADATA` de `app/prompts_service.py` (le catalogue est explicite, pas
auto-découvert). À acter dans le plan SP2/03.

---

## File structure (vue d'ensemble)

**Créés :**

- `src/fahmi2/domain/supports.py` — entités `Flashcard`, `SupportArtifact`, alias `SupportItem`.
- `src/fahmi2/infra/llm/invocation.py` — `invoke_llm_chat`, `parse_llm_json` (généralisés).
- `src/fahmi2/pedagogy/__init__.py`
- `src/fahmi2/pedagogy/chapters.py` — `Chapter` + `parse_chapters`.
- `src/fahmi2/pedagogy/events.py` — events pédagogie + union `PedagogyEvent`.
- `src/fahmi2/pedagogy/support_generator.py` — `SupportGenerator` (ABC) + `SupportContext` (DI frozen).
- `src/fahmi2/pedagogy/support_registry.py` — `SupportGeneratorRegistry` + ordre canonique.
- `src/fahmi2/pedagogy/manifest.py` — `PedagogyManifest`, hash réglages, lecture/écriture.
- `src/fahmi2/pedagogy/artifact_writer.py` — sérialisation artefacts + chemins.
- `src/fahmi2/pedagogy/generators/__init__.py`
- `src/fahmi2/pedagogy/generators/flashcards_glossary.py` — `FlashcardsGlossaryGenerator`.
- `src/fahmi2/app/supports_orchestrator.py` — `SupportsOrchestrator`.
- Tests : `tests/unit/domain/test_supports.py`, `tests/unit/infra/llm/test_invocation.py`,
  `tests/unit/pedagogy/test_chapters.py`, `tests/unit/pedagogy/test_support_registry.py`,
  `tests/unit/pedagogy/test_manifest.py`, `tests/unit/pedagogy/test_flashcards_glossary.py`,
  `tests/unit/app/test_supports_orchestrator.py`.

**Modifiés :**

- `src/fahmi2/app/run_orchestrator.py` — **régression** : préserver `pedagogy` en fin de run.
- `src/fahmi2/domain/generation.py` — constantes `GENERATION_OUTPUT_SUBDIR` + `consolidated_doc_filename`.
- `src/fahmi2/ui/generation_controller.py` — utiliser la constante (2 sites).
- `src/fahmi2/pipeline/handlers/phase_6_translation.py`, `phase_7_coherence.py` — utiliser le helper de nom (3 sites).
- `src/fahmi2/pipeline/handlers/_base.py` — déléguer aux helpers généralisés.
- `src/fahmi2/pipeline/event_bus.py` — `EventBus` générique.
- `src/fahmi2/pipeline/phase_handler.py` — `event_bus: EventBus[PipelineEvent]`.
- `src/fahmi2/ui/qt_event_bus.py` — base `EventBus[PipelineEvent]`.
- `src/fahmi2/app/project_service.py` — `get_last_completed_run`.
- Tests : `tests/unit/pipeline/test_event_bus.py` (paramétrer `EventBus[PipelineEvent]()`),
  `tests/unit/app/test_run_orchestrator.py` (test de régression pedagogy).

---

## Task 0 : Régression — préserver `pedagogy` en fin de run

> SP2/01 a ajouté `Project.pedagogy` mais `RunOrchestrator.execute` reconstruit le
> `Project` **sans** ce champ → un run de génération **efface** les réglages
> pédagogie. À corriger avant de bâtir la pédagogie dessus.

**Files:** Modify `src/fahmi2/app/run_orchestrator.py:162-174` ;
Test `tests/unit/app/test_run_orchestrator.py`

- [ ] **Step 1 : Test (échoue)** — ajouter à la fin de `test_run_orchestrator.py`.
  L'import `make_pedagogy_settings` est une fixture globale (pas d'import nécessaire).

```python
def test_execute_preserves_pedagogy_settings(
    tmp_path: Path,
    make_generation_settings: Any,
    make_pedagogy_settings: Any,
) -> None:
    orchestrator, _, project_service = _build_orchestrator(tmp_path)
    input_folder = _seed_input_folder(tmp_path)
    settings = make_generation_settings(input_folder=input_folder)
    project = project_service.create_project(
        name="Test", workspace_folder=tmp_path / "ws", generation=settings
    )
    # On configure la pédagogie après création (parité avec l'usage réel).
    project_service.update_project(
        Project(
            id=project.id,
            name=project.name,
            workspace_folder=project.workspace_folder,
            created_at=project.created_at,
            generation=project.generation,
            pedagogy=make_pedagogy_settings(),
        )
    )
    run = orchestrator.create_run(project)
    orchestrator.execute(run=run, ctx=_build_ctx(tmp_path, run))

    reloaded = project_service.get_project(project.id)
    assert reloaded is not None
    assert reloaded.pedagogy is not None
```

Ajouter `from fahmi2.domain.project import Project` aux imports du test si absent.

- [ ] **Step 2 : Lancer** → FAIL (`reloaded.pedagogy is None`).

Run: `.venv\Scripts\python.exe -m pytest tests/unit/app/test_run_orchestrator.py::test_execute_preserves_pedagogy_settings -v`

- [ ] **Step 3 : Corriger la reconstruction du `Project`** dans `RunOrchestrator.execute`.
  Ajouter la ligne `pedagogy=project.pedagogy,` au `Project(...)` :

```python
            self._project_service.update_project(
                Project(
                    id=project.id,
                    name=project.name,
                    workspace_folder=project.workspace_folder,
                    created_at=project.created_at,
                    last_run_at=finished_run.finished_at,
                    runs=(*project.runs, finished_run.id),
                    generation=project.generation,
                    pedagogy=project.pedagogy,
                )
            )
```

- [ ] **Step 4 : Lancer** → PASS (+ non-régression du fichier complet).

Run: `.venv\Scripts\python.exe -m pytest tests/unit/app/test_run_orchestrator.py -q`

---

## Task 1 : Centraliser les constantes de chemins génération

> `pedagogy/` doit lire `<emplacement>/generation/output/consolidated.{lang}.md`.
> Le sous-dossier `output` et le motif de nom sont aujourd'hui des magic strings
> dupliquées (controller + handlers 6/7). On les centralise (directive 1, DRY).

**Files:** Modify `src/fahmi2/domain/generation.py`,
`src/fahmi2/ui/generation_controller.py`,
`src/fahmi2/pipeline/handlers/phase_6_translation.py`,
`src/fahmi2/pipeline/handlers/phase_7_coherence.py` ;
Test `tests/unit/domain/test_generation.py` (créer si absent)

- [ ] **Step 1 : Test (échoue)** — créer `tests/unit/domain/test_generation_paths.py` :

```python
"""Tests des constantes/helpers de chemins de la fonctionnalité Génération."""

from __future__ import annotations

from fahmi2.domain.enums import Language
from fahmi2.domain.generation import (
    GENERATION_OUTPUT_SUBDIR,
    consolidated_doc_filename,
)


def test_output_subdir_constant() -> None:
    assert GENERATION_OUTPUT_SUBDIR == "output"


def test_consolidated_doc_filename() -> None:
    assert consolidated_doc_filename(Language.FR) == "consolidated.fr.md"
    assert consolidated_doc_filename(Language.EN) == "consolidated.en.md"
```

- [ ] **Step 2 : Lancer** → FAIL (`ImportError`).

- [ ] **Step 3 : Ajouter à `domain/generation.py`** (sous `GENERATION_WORKSPACE_SUBDIR`) :

```python
#: Sous-dossier des livrables finaux de la génération (sous le dossier feature).
GENERATION_OUTPUT_SUBDIR = "output"


def consolidated_doc_filename(language: Language) -> str:
    """Nom de fichier du document consolidé pour une langue.

    Args:
        language: Langue cible.

    Returns:
        Le nom de fichier (ex: ``"consolidated.fr.md"``).
    """
    return f"consolidated.{language}.md"
```

- [ ] **Step 4 : Lancer** → PASS.

- [ ] **Step 5 : Réutiliser la constante dans `generation_controller.py`** (2 sites :
  ~ligne 501 et ~ligne 705). Importer la constante puis remplacer le littéral
  `"output"` :

Import (regrouper avec l'import existant `GENERATION_WORKSPACE_SUBDIR`) :

```python
from fahmi2.domain.generation import (
    GENERATION_OUTPUT_SUBDIR,
    GENERATION_WORKSPACE_SUBDIR,
)
```

Remplacer `output_dir=gen_workspace / "output",` par
`output_dir=gen_workspace / GENERATION_OUTPUT_SUBDIR,` et, dans
`_current_output_dir`, `/ "output"` par `/ GENERATION_OUTPUT_SUBDIR`.

- [ ] **Step 6 : Réutiliser le helper de nom dans les handlers 6 et 7.**
  Dans `phase_6_translation.py`, importer `consolidated_doc_filename` et remplacer
  `ctx.output_dir / f"consolidated.{target.value}.md"` par
  `ctx.output_dir / consolidated_doc_filename(target)`. Idem `phase_7_coherence.py`
  (`path = ctx.output_dir / consolidated_doc_filename(target)`).

  > `target` est une `Language` ; `consolidated_doc_filename` accepte une `Language`.

- [ ] **Step 7 : Vérifier la non-régression** (les tests phase 6/7 + e2e couvrent ces chemins).

Run: `.venv\Scripts\python.exe -m pytest tests/unit/pipeline/handlers/test_phase_6_translation.py tests/unit/pipeline/handlers/test_phase_7_coherence.py tests/e2e -q`
Expected: PASS.

---

## Task 2 : Généraliser les helpers LLM / JSON

> Le design §5.3 prévoit `invoke_llm_chat(...)` + `parse_json(...)` réutilisables par
> les générateurs LLM (SP2/03) et l'orchestrateur. On les extrait de
> `pipeline/handlers/_base.py` vers `infra/llm/invocation.py` et on fait **déléguer**
> les helpers existants (DRY, pas de code mort, comportement inchangé).

**Files:** Create `src/fahmi2/infra/llm/invocation.py` ;
Modify `src/fahmi2/pipeline/handlers/_base.py` ;
Test `tests/unit/infra/llm/test_invocation.py`

- [ ] **Step 1 : Test (échoue)** — `tests/unit/infra/llm/test_invocation.py` :

```python
"""Tests des helpers LLM généralisés (invocation + parsing JSON)."""

from __future__ import annotations

import pytest

from fahmi2.core.errors.exceptions import LLMError
from fahmi2.domain.phase import PhaseConfig
from fahmi2.infra.llm._fakes import FakeLLMProvider
from fahmi2.infra.llm.invocation import invoke_llm_chat, parse_llm_json


def test_parse_llm_json_strips_code_fence() -> None:
    assert parse_llm_json('```json\n{"a": 1}\n```', context_label="x") == {"a": 1}


def test_parse_llm_json_raises_typed_error() -> None:
    with pytest.raises(LLMError) as exc_info:
        parse_llm_json("pas du json", context_label="flashcards")
    assert exc_info.value.code == "LLM.INVALID_JSON"
    assert exc_info.value.technical_details["context_label"] == "flashcards"


def test_invoke_llm_chat_builds_messages_and_calls_provider() -> None:
    provider = FakeLLMProvider()
    response = invoke_llm_chat(
        provider,
        model="deepseek-v4-flash",
        config=PhaseConfig(),
        system_prompt="sys",
        user_prompt="user",
    )
    assert isinstance(response.content, str)
```

> Si `FakeLLMProvider.chat` exige un `content` programmé, adapter le test à son API
> (cf. usages existants dans `tests/unit/pipeline/handlers/`). Le but du test est de
> vérifier que `invoke_llm_chat` construit bien les messages et délègue à `chat`.

- [ ] **Step 2 : Lancer** → FAIL (`ImportError`).

- [ ] **Step 3 : Créer `infra/llm/invocation.py`** :

```python
"""Helpers LLM généralisés : invocation chat + parsing JSON robuste.

Mutualise l'appel ``LLMProvider.chat`` à partir d'une ``PhaseConfig`` et le
parsing tolérant des réponses JSON (délimiteurs ```` ```json ```` éventuels),
avec mapping vers une erreur typée. Réutilisé par les handlers de phase
(``pipeline/handlers/_base.py``) et par les générateurs de supports pédagogiques.
"""

from __future__ import annotations

import json
from typing import Any

from fahmi2.core.errors.exceptions import LLMError
from fahmi2.core.errors.severity import Severity
from fahmi2.domain.phase import PhaseConfig
from fahmi2.infra.llm.interface import LLMProvider, LLMResponse, Message

_RAW_CONTENT_MAX_CHARS = 500


def invoke_llm_chat(
    llm_provider: LLMProvider,
    *,
    model: str,
    config: PhaseConfig,
    system_prompt: str | None,
    user_prompt: str,
    max_tokens: int | None = None,
) -> LLMResponse:
    """Appelle ``llm_provider.chat`` avec une ``PhaseConfig``.

    Args:
        llm_provider: Provider LLM à invoquer.
        model: Identifiant du modèle (ex: ``"deepseek-v4-flash"``).
        config: Config LLM (thinking / reasoning_effort / température).
        system_prompt: Prompt système optionnel.
        user_prompt: Prompt utilisateur (corps de la requête).
        max_tokens: Borne supérieure de tokens en sortie (``None`` = défaut modèle).

    Returns:
        La ``LLMResponse``.
    """
    messages: list[Message] = []
    if system_prompt:
        messages.append(Message(role="system", content=system_prompt))
    messages.append(Message(role="user", content=user_prompt))
    reasoning_effort_str = (
        str(config.reasoning_effort) if config.reasoning_effort else None
    )
    return llm_provider.chat(
        messages=messages,
        model=model,
        thinking=config.thinking_enabled,
        reasoning_effort=reasoning_effort_str,
        temperature=config.temperature,
        max_tokens=max_tokens,
    )


def parse_llm_json(content: str, *, context_label: str) -> Any:  # noqa: ANN401
    """Parse une réponse LLM JSON, en isolant d'éventuels délimiteurs.

    Args:
        content: Contenu textuel de la réponse LLM.
        context_label: Libellé de contexte pour les messages d'erreur
            (ex: ``"reformulation"``, ``"flashcards_glossary"``).

    Returns:
        L'objet Python décodé.

    Raises:
        LLMError: ``LLM.INVALID_JSON`` si le contenu n'est pas du JSON valide.
    """
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise LLMError(
            code="LLM.INVALID_JSON",
            user_message=(
                f"La réponse du LLM pour {context_label} n'est pas du JSON valide."
            ),
            severity=Severity.ERROR,
            technical_details={
                "context_label": context_label,
                "raw_content": content[:_RAW_CONTENT_MAX_CHARS],
            },
        ) from exc
```

- [ ] **Step 4 : Faire déléguer `_base.py`.** Remplacer le corps de `invoke_llm` et
  `parse_json_response` (garder leurs signatures publiques inchangées), ajouter
  l'import `from fahmi2.infra.llm.invocation import invoke_llm_chat, parse_llm_json`,
  et supprimer les imports devenus inutiles (`json`, `LLMError`, `Severity`,
  `Message`, `LLMResponse` si plus référencés ailleurs dans `_base.py` — vérifier) :

```python
def invoke_llm(
    ctx: PhaseContext,
    *,
    phase_id: PhaseId,
    system_prompt: str | None,
    user_prompt: str,
    max_tokens: int | None = None,
) -> LLMResponse:
    """Appelle le ``LLMProvider`` avec la ``PhaseConfig`` propre à ``phase_id``.

    (cf. ``infra.llm.invocation.invoke_llm_chat`` pour le détail.)
    """
    return invoke_llm_chat(
        ctx.llm_provider,
        model=str(ctx.settings.llm_model),
        config=ctx.settings.phases_config[phase_id],
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        max_tokens=max_tokens,
    )


def parse_json_response(content: str, *, phase_id: PhaseId) -> Any:  # noqa: ANN401
    """Parse une réponse LLM JSON (délègue à ``parse_llm_json``)."""
    return parse_llm_json(content, context_label=phase_id.value)
```

  > `LLMResponse` reste importé (annotation de retour de `invoke_llm`). `Message` et
  > `Any` : garder `Any` (annotation `parse_json_response`). Retirer `Message`, `json`,
  > `LLMError`, `Severity` s'ils ne servent plus. Lancer `ruff` confirmera les imports morts.
  > Le message d'erreur reste identique (`context_label=phase_id.value`) ; le test
  > `test_phase_1_term_extraction.py` (qui n'asserte que `.code`) reste vert.

- [ ] **Step 5 : Lancer** → PASS.

Run: `.venv\Scripts\python.exe -m pytest tests/unit/infra/llm/test_invocation.py tests/unit/pipeline/handlers -q`
Expected: PASS (helpers généralisés + handlers délégant, comportement inchangé).

---

## Task 3 : `EventBus` générique

> Pour porter `PedagogyEvent` sur le même mécanisme de bus que `PipelineEvent` sans
> coupler les deux familles (et sans que `pipeline` importe `pedagogy`), on rend
> `EventBus` générique : `EventBus[PipelineEvent]` (génération) et
> `EventBus[PedagogyEvent]` (pédagogie). Comportement runtime inchangé.

**Files:** Modify `src/fahmi2/pipeline/event_bus.py`,
`src/fahmi2/pipeline/phase_handler.py`, `src/fahmi2/ui/qt_event_bus.py` ;
Test `tests/unit/pipeline/test_event_bus.py`

- [ ] **Step 1 : Rendre `EventBus` générique** dans `pipeline/event_bus.py`. Le bus ne
  doit **plus** importer `PipelineEvent` (découplage) :

```python
"""Bus d'événements générique (in-memory, thread-safe).

Paramétré par le type d'événement (``EventBus[PipelineEvent]`` pour la
génération, ``EventBus[PedagogyEvent]`` pour la pédagogie). L'adapter Qt
(``ui/qt_event_bus.py``) en hérite pour bridger worker → UI thread.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Generic, TypeVar

E = TypeVar("E")


class EventBus(Generic[E]):
    """Bus d'événements in-memory thread-safe, paramétré par le type d'event."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._handlers: list[Callable[[E], None]] = []

    def subscribe(self, handler: Callable[[E], None]) -> Callable[[], None]:
        """Abonne un handler aux événements futurs.

        Args:
            handler: Fonction appelée à chaque publication.

        Returns:
            Fonction de désabonnement (idempotente).
        """
        with self._lock:
            self._handlers.append(handler)

        def _unsubscribe() -> None:
            with self._lock:
                if handler in self._handlers:
                    self._handlers.remove(handler)

        return _unsubscribe

    def publish(self, event: E) -> None:
        """Distribue ``event`` à tous les handlers abonnés.

        Args:
            event: Événement à publier.

        Note:
            Les exceptions levées par un handler ne sont pas propagées : on
            isole chaque handler pour ne pas casser la chaîne.
        """
        with self._lock:
            handlers = tuple(self._handlers)
        for h in handlers:
            try:
                h(event)
            except Exception:  # noqa: BLE001, S110 — isolation des handlers
                pass
```

- [ ] **Step 2 : Paramétrer `PhaseContext.event_bus`** dans `pipeline/phase_handler.py` :
  ajouter l'import `from fahmi2.pipeline.events import PipelineEvent` et changer le champ
  `event_bus: EventBus` → `event_bus: EventBus[PipelineEvent]`. Mettre à jour la docstring
  du champ si besoin.

- [ ] **Step 3 : Paramétrer `QtEventBus`** dans `ui/qt_event_bus.py` : la classe devient
  `class QtEventBus(QObject, EventBus[PipelineEvent]):`. (`publish` est déjà typé
  `PipelineEvent`.) L'import `PipelineEvent` existe déjà.

- [ ] **Step 4 : Paramétrer les `EventBus()` sans contexte de typage** dans
  `tests/unit/pipeline/test_event_bus.py` (5 occurrences) : remplacer `EventBus()` par
  `EventBus[PipelineEvent]()`. Ajouter l'import
  `from fahmi2.pipeline.events import PipelineEvent` en tête du fichier.

  > Les sites `event_bus=EventBus()` passés à `PhaseContext(...)` (tests handlers, engine,
  > run_orchestrator, e2e) sont **inférés** via le type attendu `EventBus[PipelineEvent]`
  > → aucune modification nécessaire.

- [ ] **Step 5 : Lancer** → PASS + mypy local.

Run: `.venv\Scripts\python.exe -m pytest tests/unit/pipeline/test_event_bus.py -q && .venv\Scripts\python.exe -m mypy src/fahmi2/pipeline/event_bus.py src/fahmi2/pipeline/phase_handler.py src/fahmi2/ui/qt_event_bus.py`
Expected: PASS / Success.

---

## Task 4 : Domaine — entités de support (`Flashcard`, `SupportArtifact`)

> §3.4 : entités introduites **par tranche** (YAGNI). SP2/02 a besoin de `Flashcard`
> et de l'enveloppe `SupportArtifact`. Les autres entités (`QcmItem`, `ClozeItem`…)
> seront ajoutées au SP2/03.

**Files:** Create `src/fahmi2/domain/supports.py` ; Test `tests/unit/domain/test_supports.py`

- [ ] **Step 1 : Test (échoue)** — `tests/unit/domain/test_supports.py` :

```python
"""Tests des entités de support de révision."""

from __future__ import annotations

from fahmi2.domain.enums import Language, SupportType
from fahmi2.domain.supports import Flashcard, SupportArtifact


def test_flashcard_is_frozen() -> None:
    card = Flashcard(front="PIB", back="Produit intérieur brut", source_ref="PIB")
    assert card.tags == ()


def test_support_artifact_holds_items() -> None:
    card = Flashcard(front="X", back="def", source_ref="X", tags=("t",))
    artifact = SupportArtifact(
        support_type=SupportType.FLASHCARDS_GLOSSARY,
        language=Language.FR,
        items=(card,),
        rendered_markdown="# Flashcards",
        cost_usd=0.0,
    )
    assert artifact.items[0].front == "X"
    assert artifact.cost_usd == 0.0
```

- [ ] **Step 2 : Lancer** → FAIL.

- [ ] **Step 3 : Créer `domain/supports.py`** :

```python
"""Entités structurées des supports de révision (immuables).

Représentations consommées par les exports SP3 (Anki, Markdown/PDF) et écrites
sur disque (JSON + Markdown rendu). Les entités spécifiques aux supports
évaluatifs (``QcmItem``, ``ClozeItem``…) sont ajoutées par leurs tranches
respectives (SP2/03). Le ``source_ref`` trace l'origine (terme de glossaire ou
ancre/chapitre du document consolidé).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fahmi2.domain.enums import Language, SupportType


@dataclass(frozen=True)
class Flashcard:
    """Carte recto/verso.

    Attributes:
        front: Recto (terme / acronyme / question).
        back: Verso (définition / réponse).
        source_ref: Référence d'origine (terme de glossaire ou ancre de chapitre).
        tags: Étiquettes (type de support, langue…), pour l'export Anki.
    """

    front: str
    back: str
    source_ref: str
    tags: tuple[str, ...] = ()


#: Union des entités structurées portées par un ``SupportArtifact``. S'étend au SP2/03.
SupportItem = Flashcard


@dataclass(frozen=True)
class SupportArtifact:
    """Enveloppe unifiée d'un support généré (écrite en JSON + Markdown).

    Attributes:
        support_type: Type de support.
        language: Langue du support.
        items: Entités structurées (cartes, questions…).
        rendered_markdown: Rendu Markdown lisible du support.
        cost_usd: Coût LLM de génération (0.0 pour les supports sans LLM).
    """

    support_type: SupportType
    language: Language
    items: tuple[SupportItem, ...]
    rendered_markdown: str
    cost_usd: float = 0.0

    def __post_init__(self) -> None:
        if self.cost_usd < 0:
            raise ValueError(f"cost_usd must be >= 0, got {self.cost_usd}")
```

> `field` est importé pour cohérence future (entités à valeurs par défaut mutables au
> SP2/03). Si `ruff` signale un import inutilisé à ce stade, le retirer et le
> réintroduire au SP2/03. Préférer **ne pas** l'importer maintenant (YAGNI) :
> supprimer la ligne `field` de l'import si non utilisée.

- [ ] **Step 4 : Lancer** → PASS.

---

## Task 5 : Parseur de chapitres du document consolidé

> §4 : découpe `consolidated.{lang}.md` en chapitres (titres `# N. …`). Utilitaire
> pur (pas d'I/O). Consommé par l'orchestrateur (chargement des entrants) et par les
> générateurs LLM (SP2/03). Le générateur flashcards glossaire ne l'utilise pas mais
> le parseur fait partie du socle et est testé isolément.

**Files:** Create `src/fahmi2/pedagogy/__init__.py`, `src/fahmi2/pedagogy/chapters.py` ;
Test `tests/unit/pedagogy/test_chapters.py`

- [ ] **Step 1 : Créer le package** `src/fahmi2/pedagogy/__init__.py` :

```python
"""Moteur de génération des supports pédagogiques (calqué sur ``pipeline``)."""
```

- [ ] **Step 2 : Test (échoue)** — `tests/unit/pedagogy/test_chapters.py` :

```python
"""Tests du parseur de chapitres du document consolidé."""

from __future__ import annotations

from fahmi2.pedagogy.chapters import Chapter, parse_chapters

_DOC = """# Mon cours

## Résumé

Abstract...

## Introduction générale

Intro...

## Sommaire

- [1. Bases](#1-bases)

# 1. Bases

Contenu du chapitre 1.

## 1.1 Définitions

Texte.

# 2. Avancé

Contenu du chapitre 2.

## Conclusion générale

Fin.
"""


def test_parse_chapters_extracts_numbered_h1_only() -> None:
    chapters = parse_chapters(_DOC)
    assert [c.index for c in chapters] == [1, 2]
    assert [c.title for c in chapters] == ["Bases", "Avancé"]


def test_parse_chapters_body_and_anchor() -> None:
    chapters = parse_chapters(_DOC)
    assert "Contenu du chapitre 1." in chapters[0].body_markdown
    assert "## 1.1 Définitions" in chapters[0].body_markdown
    assert chapters[0].anchor == "1-bases"


def test_parse_chapters_empty_when_no_chapter() -> None:
    assert parse_chapters("# Titre\n\n## Résumé\n\ntexte\n") == ()
```

- [ ] **Step 3 : Lancer** → FAIL.

- [ ] **Step 4 : Créer `pedagogy/chapters.py`** :

```python
"""Parseur de chapitres du document consolidé (``consolidated.{lang}.md``).

Le document consolidé (cf. ``pipeline/handlers/phase_5_consolidation``) place le
titre global en ``# <titre>``, les sections méta (Résumé, Introduction, Sommaire,
Conclusion) en ``##``, et chaque **chapitre** en ``# N. <titre>``. Ce parseur
isole donc uniquement les ``#`` à préfixe numérique comme frontières de chapitre.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# H1 de chapitre : "# 1. Titre", "# 12. Autre". Le préfixe numérique distingue les
# chapitres du titre global (sans numéro) et des sections méta (qui sont en ##).
_RE_CHAPTER_H1 = re.compile(r"^#\s+(\d+)\.\s+(.+?)\s*$")
_RE_ANCHOR_STRIP = re.compile(r"[^\w\s-]", flags=re.UNICODE)
_RE_ANCHOR_SPACES = re.compile(r"\s+")


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
                anchor=_slugify(f"{index}. {title}"),
                body_markdown=body,
            )
        )
    return tuple(chapters)


def _slugify(text: str) -> str:
    """Construit une ancre GFM (minuscules, tirets) à partir d'un titre.

    Args:
        text: Texte du titre (ex: ``"1. Bases"``).

    Returns:
        Slug GFM (ex: ``"1-bases"``).
    """
    lowered = text.strip().lower()
    cleaned = _RE_ANCHOR_STRIP.sub("", lowered)
    return _RE_ANCHOR_SPACES.sub("-", cleaned).strip("-")
```

- [ ] **Step 5 : Lancer** → PASS.

Run: `.venv\Scripts\python.exe -m pytest tests/unit/pedagogy/test_chapters.py -v`

---

## Task 6 : Events pédagogie

> §5.4. Quatre events immuables, union `PedagogyEvent`. Réutilise les statuts
> **domaine** existants : `PhaseStatus` (par support : SUCCEEDED/SKIPPED/FAILED) et
> `RunStatus` (global : COMPLETED/FAILED/CANCELLED). Aucun import `pipeline`.

**Files:** Create `src/fahmi2/pedagogy/events.py` (pas de test dédié : couvert par
l'orchestrateur Task 13)

- [ ] **Step 1 : Créer `pedagogy/events.py`** :

```python
"""Événements émis par le ``SupportsOrchestrator`` lors d'une génération.

Immuables, bridgés à l'UI via ``EventBus[PedagogyEvent]`` (et un ``QtEventBus``
côté UI, SP2/04). Réutilisent les statuts domaine ``PhaseStatus`` (unité de
travail) et ``RunStatus`` (génération globale) — pas de nouvel enum.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from fahmi2.core.errors.error_info import ErrorInfo
from fahmi2.domain.enums import Language, PhaseStatus, RunStatus, SupportType


@dataclass(frozen=True)
class SupportGenerationStarted:
    """Démarrage d'une génération de supports.

    Attributes:
        timestamp: Horodatage.
    """

    timestamp: datetime


@dataclass(frozen=True)
class SupportStarted:
    """Démarrage de la génération d'un support pour une langue.

    Attributes:
        timestamp: Horodatage.
        support_type: Type de support.
        language: Langue.
    """

    timestamp: datetime
    support_type: SupportType
    language: Language


@dataclass(frozen=True)
class SupportFinished:
    """Fin de la génération d'un support pour une langue.

    Attributes:
        timestamp: Horodatage.
        support_type: Type de support.
        language: Langue.
        status: ``SUCCEEDED``, ``SKIPPED`` (artefact frais) ou ``FAILED``.
        cost_usd: Coût LLM de ce support (0.0 si sans LLM ou skippé).
        error: ``ErrorInfo`` si échec, sinon ``None``.
    """

    timestamp: datetime
    support_type: SupportType
    language: Language
    status: PhaseStatus
    cost_usd: float
    error: ErrorInfo | None


@dataclass(frozen=True)
class SupportGenerationFinished:
    """Fin d'une génération de supports.

    Attributes:
        timestamp: Horodatage.
        status: ``COMPLETED``, ``FAILED`` (≥1 support échoué) ou ``CANCELLED``.
        total_cost_usd: Coût LLM cumulé.
    """

    timestamp: datetime
    status: RunStatus
    total_cost_usd: float


PedagogyEvent = (
    SupportGenerationStarted
    | SupportStarted
    | SupportFinished
    | SupportGenerationFinished
)
```

- [ ] **Step 2 : Vérifier l'import** (sanity) :

Run: `.venv\Scripts\python.exe -c "from fahmi2.pedagogy.events import PedagogyEvent; print('ok')"`
Expected: `ok`.

---

## Task 7 : `SupportGenerator` (ABC) + `SupportContext` (DI)

> §5.1 / §5.2. Calqué sur `PhaseHandler` / `PhaseContext`. Le contexte porte les
> dépendances **stables** ; les données par appel (langue, chapitres, glossaire)
> passent en arguments de `generate`.

**Files:** Create `src/fahmi2/pedagogy/support_generator.py` (couvert par les Tasks 11 & 13)

- [ ] **Step 1 : Créer `pedagogy/support_generator.py`** :

```python
"""Interface ``SupportGenerator`` et ``SupportContext`` (injection de dépendances).

Chaque type de support de révision est produit par une sous-classe de
``SupportGenerator``. Le ``SupportContext`` regroupe les dépendances stables
injectées par l'orchestrateur (réglages, dossiers, provider LLM, prompts,
artifacts, bus d'événements, jeton de pause) — **pas** de STT/ffmpeg.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from fahmi2.domain.enums import Language, SupportType
from fahmi2.domain.glossary import Term
from fahmi2.domain.pedagogy import PedagogySettings
from fahmi2.domain.supports import SupportArtifact
from fahmi2.infra.llm.interface import LLMProvider
from fahmi2.infra.prompts.loader import PromptLoader
from fahmi2.infra.storage.fs_artifacts import FsArtifactStore
from fahmi2.pedagogy.chapters import Chapter
from fahmi2.pedagogy.events import PedagogyEvent
from fahmi2.pipeline.event_bus import EventBus
from fahmi2.pipeline.pause_token import PauseToken


@dataclass(frozen=True)
class SupportContext:
    """Dépendances injectées à un ``SupportGenerator``.

    Attributes:
        pedagogy: Réglages pédagogie du projet.
        generation_output_dir: Dossier des livrables de génération (source).
        pedagogy_dir: Dossier de sortie des supports (``<emplacement>/pedagogy``).
        llm_provider: Provider LLM (utilisé par les générateurs LLM, SP2/03).
        prompts: Loader de prompts (défauts bundlés + override ``%APPDATA%``).
        artifacts: Écriture atomique d'artefacts.
        event_bus: Bus d'événements pédagogie.
        pause_token: Jeton coopératif pause/annulation.
    """

    pedagogy: PedagogySettings
    generation_output_dir: Path
    pedagogy_dir: Path
    llm_provider: LLMProvider
    prompts: PromptLoader
    artifacts: FsArtifactStore
    event_bus: EventBus[PedagogyEvent]
    pause_token: PauseToken


class SupportGenerator(ABC):
    """Base abstraite d'un générateur de support de révision."""

    @property
    @abstractmethod
    def support_type(self) -> SupportType:
        """Type de support produit."""

    @property
    @abstractmethod
    def uses_llm(self) -> bool:
        """Indique si le générateur appelle le LLM (``True``) ou non (``False``)."""

    @abstractmethod
    def generate(
        self,
        ctx: SupportContext,
        *,
        language: Language,
        chapters: tuple[Chapter, ...],
        glossary: tuple[Term, ...],
    ) -> SupportArtifact:
        """Génère le support pour une langue donnée.

        Args:
            ctx: Contexte d'exécution (dépendances stables).
            language: Langue cible.
            chapters: Chapitres du document consolidé (vide si non disponible).
            glossary: Termes du glossaire pour cette langue.

        Returns:
            Le ``SupportArtifact`` produit (items structurés + Markdown rendu + coût).

        Raises:
            Fahmi2Error: Toute erreur métier doit être typée (capturée par
                l'orchestrateur et convertie en ``ErrorInfo``).
        """
```

- [ ] **Step 2 : Vérifier l'import** :

Run: `.venv\Scripts\python.exe -c "from fahmi2.pedagogy.support_generator import SupportGenerator, SupportContext; print('ok')"`
Expected: `ok`.

---

## Task 8 : `SupportGeneratorRegistry`

> §5.1. Calqué sur `PhaseRegistry` (ordre canonique des 9 supports).

**Files:** Create `src/fahmi2/pedagogy/support_registry.py` ;
Test `tests/unit/pedagogy/test_support_registry.py`

- [ ] **Step 1 : Test (échoue)** — `tests/unit/pedagogy/test_support_registry.py` :

```python
"""Tests du registre de générateurs de supports."""

from __future__ import annotations

import pytest

from fahmi2.domain.enums import Language, SupportType
from fahmi2.domain.glossary import Term
from fahmi2.domain.supports import Flashcard, SupportArtifact
from fahmi2.pedagogy.chapters import Chapter
from fahmi2.pedagogy.support_generator import SupportContext, SupportGenerator
from fahmi2.pedagogy.support_registry import SupportGeneratorRegistry


class _FakeGen(SupportGenerator):
    @property
    def support_type(self) -> SupportType:
        return SupportType.FLASHCARDS_GLOSSARY

    @property
    def uses_llm(self) -> bool:
        return False

    def generate(
        self,
        ctx: SupportContext,
        *,
        language: Language,
        chapters: tuple[Chapter, ...],
        glossary: tuple[Term, ...],
    ) -> SupportArtifact:
        del ctx, chapters, glossary
        return SupportArtifact(
            support_type=self.support_type,
            language=language,
            items=(Flashcard(front="a", back="b", source_ref="a"),),
            rendered_markdown="x",
        )


def test_register_and_get() -> None:
    registry = SupportGeneratorRegistry([_FakeGen()])
    assert registry.has(SupportType.FLASHCARDS_GLOSSARY)
    assert registry.get(SupportType.FLASHCARDS_GLOSSARY).uses_llm is False


def test_duplicate_registration_raises() -> None:
    with pytest.raises(ValueError, match="already registered"):
        SupportGeneratorRegistry([_FakeGen(), _FakeGen()])


def test_canonical_order_has_nine_supports() -> None:
    assert len(SupportGeneratorRegistry.canonical_order()) == 9
    assert SupportGeneratorRegistry.canonical_order()[0] == (
        SupportType.FLASHCARDS_GLOSSARY
    )


def test_ordered_generators_follows_canonical_order() -> None:
    registry = SupportGeneratorRegistry([_FakeGen()])
    ordered = registry.ordered_generators()
    assert [g.support_type for g in ordered] == [SupportType.FLASHCARDS_GLOSSARY]
```

- [ ] **Step 2 : Lancer** → FAIL.

- [ ] **Step 3 : Créer `pedagogy/support_registry.py`** :

```python
"""Registre des générateurs de supports indexés par ``SupportType``.

Calqué sur ``pipeline/phase_registry.py`` : enregistre/retrouve un générateur par
type, et expose l'ordre canonique des supports (flashcards glossaire d'abord :
tranche verticale sans LLM, puis les supports LLM).
"""

from __future__ import annotations

from collections.abc import Iterable

from fahmi2.domain.enums import SupportType
from fahmi2.pedagogy.support_generator import SupportGenerator

_SUPPORT_ORDER: tuple[SupportType, ...] = (
    SupportType.FLASHCARDS_GLOSSARY,
    SupportType.FLASHCARDS_CONCEPTS,
    SupportType.QCM,
    SupportType.TRUE_FALSE,
    SupportType.CLOZE,
    SupportType.OPEN_QUESTIONS,
    SupportType.REVISION_SHEET,
    SupportType.KEY_POINTS,
    SupportType.MOCK_EXAM,
)


class SupportGeneratorRegistry:
    """Enregistre et retrouve les générateurs de supports."""

    def __init__(self, generators: Iterable[SupportGenerator] = ()) -> None:
        """Construit le registre.

        Args:
            generators: Générateurs à enregistrer initialement.

        Raises:
            ValueError: Si deux générateurs déclarent le même ``support_type``.
        """
        self._by_type: dict[SupportType, SupportGenerator] = {}
        for generator in generators:
            self.register(generator)

    def register(self, generator: SupportGenerator) -> None:
        """Enregistre un générateur.

        Args:
            generator: Générateur à enregistrer.

        Raises:
            ValueError: Si ``support_type`` est déjà enregistré.
        """
        if generator.support_type in self._by_type:
            raise ValueError(
                f"Generator already registered for support {generator.support_type}"
            )
        self._by_type[generator.support_type] = generator

    def get(self, support_type: SupportType) -> SupportGenerator:
        """Retourne le générateur d'un type, ou lève ``KeyError``.

        Args:
            support_type: Type de support.

        Returns:
            Le générateur enregistré.

        Raises:
            KeyError: Si aucun générateur n'est enregistré pour ce type.
        """
        try:
            return self._by_type[support_type]
        except KeyError as exc:
            raise KeyError(
                f"No generator registered for support {support_type}"
            ) from exc

    def has(self, support_type: SupportType) -> bool:
        """Indique si un générateur est enregistré pour ce type.

        Args:
            support_type: Type de support.

        Returns:
            ``True`` si présent.
        """
        return support_type in self._by_type

    def ordered_generators(self) -> list[SupportGenerator]:
        """Retourne les générateurs enregistrés dans l'ordre canonique.

        Returns:
            Liste ordonnée des générateurs présents (les types absents sont omis).
        """
        return [
            self._by_type[st] for st in _SUPPORT_ORDER if st in self._by_type
        ]

    @staticmethod
    def canonical_order() -> tuple[SupportType, ...]:
        """Retourne l'ordre canonique des supports.

        Returns:
            Tuple immuable des ``SupportType``.
        """
        return _SUPPORT_ORDER
```

- [ ] **Step 4 : Lancer** → PASS.

---

## Task 9 : Manifeste de fraîcheur

> §2.2 / §5.3. `pedagogy/manifest.json` enregistre, par (support, langue), le **hash
> des réglages** (champs affectant le contenu) + le **mtime du doc consolidé source**.
> Sert (a) à la **reprise coarse** (skip si frais) et (b) à l'indicateur de péremption UI.

**Files:** Create `src/fahmi2/pedagogy/manifest.py` ; Test `tests/unit/pedagogy/test_manifest.py`

- [ ] **Step 1 : Test (échoue)** — `tests/unit/pedagogy/test_manifest.py` :

```python
"""Tests du manifeste de fraîcheur des supports."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fahmi2.domain.enums import Language, SupportType
from fahmi2.infra.storage.fs_artifacts import FsArtifactStore
from fahmi2.pedagogy.manifest import (
    PedagogyManifest,
    compute_settings_hash,
    read_manifest,
    write_manifest,
)


def test_settings_hash_is_stable_and_sensitive(make_pedagogy_settings: Any) -> None:
    base = make_pedagogy_settings()
    assert compute_settings_hash(base) == compute_settings_hash(make_pedagogy_settings())
    changed = make_pedagogy_settings(pedagogy_directives="autre")
    assert compute_settings_hash(base) != compute_settings_hash(changed)


def test_settings_hash_ignores_export_formats(make_pedagogy_settings: Any) -> None:
    from fahmi2.domain.enums import ExportFormat

    a = make_pedagogy_settings(export_formats=frozenset({ExportFormat.APKG}))
    b = make_pedagogy_settings(export_formats=frozenset({ExportFormat.MARKDOWN}))
    assert compute_settings_hash(a) == compute_settings_hash(b)


def test_is_fresh_logic() -> None:
    manifest = PedagogyManifest()
    st, lang = SupportType.FLASHCARDS_GLOSSARY, Language.FR
    assert not manifest.is_fresh(st, lang, settings_hash="h", source_mtime_ns=10)
    manifest.record(st, lang, settings_hash="h", source_mtime_ns=10)
    assert manifest.is_fresh(st, lang, settings_hash="h", source_mtime_ns=10)
    assert not manifest.is_fresh(st, lang, settings_hash="h2", source_mtime_ns=10)
    assert not manifest.is_fresh(st, lang, settings_hash="h", source_mtime_ns=99)


def test_round_trip(tmp_path: Path) -> None:
    artifacts = FsArtifactStore()
    manifest = PedagogyManifest()
    manifest.record(
        SupportType.FLASHCARDS_GLOSSARY,
        Language.FR,
        settings_hash="h",
        source_mtime_ns=10,
    )
    write_manifest(artifacts, tmp_path, manifest)
    loaded = read_manifest(tmp_path)
    assert loaded.is_fresh(
        SupportType.FLASHCARDS_GLOSSARY, Language.FR, settings_hash="h", source_mtime_ns=10
    )


def test_read_missing_returns_empty(tmp_path: Path) -> None:
    loaded = read_manifest(tmp_path)
    assert not loaded.is_fresh(
        SupportType.FLASHCARDS_GLOSSARY, Language.FR, settings_hash="h", source_mtime_ns=1
    )
```

- [ ] **Step 2 : Lancer** → FAIL.

- [ ] **Step 3 : Créer `pedagogy/manifest.py`** :

```python
"""Manifeste de fraîcheur des supports pédagogiques (``pedagogy/manifest.json``).

Enregistre, par (support, langue), le **hash des réglages** (champs affectant le
contenu : supports, corrigés, public, Bloom, directives, densité, modèle, config
LLM) et le **mtime du document consolidé source**. Permet la reprise coarse de
l'orchestrateur (skip si frais) et l'indicateur de péremption de l'UI (R19).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fahmi2.domain.enums import Language, SupportType
from fahmi2.domain.pedagogy import PedagogySettings
from fahmi2.infra.storage.fs_artifacts import FsArtifactStore

_MANIFEST_FILENAME = "manifest.json"
_MANIFEST_VERSION = 1
_ENCODING_UTF8 = "utf-8"


def manifest_path(pedagogy_dir: Path) -> Path:
    """Chemin du manifeste dans le dossier pédagogie.

    Args:
        pedagogy_dir: Dossier ``<emplacement>/pedagogy``.

    Returns:
        Le chemin de ``manifest.json``.
    """
    return pedagogy_dir / _MANIFEST_FILENAME


def compute_settings_hash(pedagogy: PedagogySettings) -> str:
    """Hash SHA-256 stable des réglages affectant le **contenu** des supports.

    N'inclut pas ``languages`` (géré par langue), ``cost_ceiling_usd``,
    ``export_formats`` ni ``max_retries`` (sans effet sur le contenu généré).

    Args:
        pedagogy: Réglages pédagogie.

    Returns:
        Le digest hexadécimal.
    """
    cfg = pedagogy.llm_config
    payload: dict[str, Any] = {
        "selected_supports": sorted(s.value for s in pedagogy.selected_supports),
        "separate_correction": sorted(s.value for s in pedagogy.separate_correction),
        "target_audience": pedagogy.target_audience.value,
        "bloom_objective": pedagogy.bloom_objective.value,
        "pedagogy_directives": pedagogy.pedagogy_directives,
        "density": pedagogy.density.value,
        "llm_model": pedagogy.llm_model.value,
        "llm_config": {
            "thinking_enabled": cfg.thinking_enabled,
            "reasoning_effort": (
                cfg.reasoning_effort.value if cfg.reasoning_effort else None
            ),
            "temperature": cfg.temperature,
        },
    }
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode(_ENCODING_UTF8)).hexdigest()


@dataclass(frozen=True)
class _Entry:
    """Entrée de manifeste pour un (support, langue)."""

    settings_hash: str
    source_mtime_ns: int | None


class PedagogyManifest:
    """État de fraîcheur des supports générés (par support × langue)."""

    def __init__(self) -> None:
        self._entries: dict[tuple[SupportType, Language], _Entry] = {}

    def is_fresh(
        self,
        support_type: SupportType,
        language: Language,
        *,
        settings_hash: str,
        source_mtime_ns: int | None,
    ) -> bool:
        """Indique si le support enregistré est à jour.

        Args:
            support_type: Type de support.
            language: Langue.
            settings_hash: Hash courant des réglages.
            source_mtime_ns: mtime courant du doc source (``None`` si absent).

        Returns:
            ``True`` si une entrée existe avec mêmes hash et mtime.
        """
        entry = self._entries.get((support_type, language))
        if entry is None:
            return False
        return (
            entry.settings_hash == settings_hash
            and entry.source_mtime_ns == source_mtime_ns
        )

    def record(
        self,
        support_type: SupportType,
        language: Language,
        *,
        settings_hash: str,
        source_mtime_ns: int | None,
    ) -> None:
        """Enregistre/Met à jour l'entrée d'un support.

        Args:
            support_type: Type de support.
            language: Langue.
            settings_hash: Hash des réglages au moment de la génération.
            source_mtime_ns: mtime du doc source au moment de la génération.
        """
        self._entries[(support_type, language)] = _Entry(
            settings_hash=settings_hash, source_mtime_ns=source_mtime_ns
        )

    def to_dict(self) -> dict[str, Any]:
        """Sérialise le manifeste en dict JSON-compatible.

        Returns:
            ``{"version", "entries": [...]}``.
        """
        return {
            "version": _MANIFEST_VERSION,
            "entries": [
                {
                    "support": st.value,
                    "language": lang.value,
                    "settings_hash": entry.settings_hash,
                    "source_mtime_ns": entry.source_mtime_ns,
                }
                for (st, lang), entry in self._entries.items()
            ],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> PedagogyManifest:
        """Reconstruit un manifeste depuis un dict (tolérant aux entrées invalides).

        Args:
            payload: Dict issu de ``to_dict``.

        Returns:
            Le manifeste reconstruit (entrées illisibles ignorées).
        """
        manifest = cls()
        for raw in payload.get("entries", []):
            try:
                st = SupportType(raw["support"])
                lang = Language(raw["language"])
            except (KeyError, ValueError):
                continue
            manifest.record(
                st,
                lang,
                settings_hash=str(raw.get("settings_hash", "")),
                source_mtime_ns=raw.get("source_mtime_ns"),
            )
        return manifest


def read_manifest(pedagogy_dir: Path) -> PedagogyManifest:
    """Lit le manifeste, ou renvoie un manifeste vide si absent/corrompu.

    Args:
        pedagogy_dir: Dossier ``<emplacement>/pedagogy``.

    Returns:
        Le ``PedagogyManifest`` (vide si fichier manquant ou JSON invalide).
    """
    path = manifest_path(pedagogy_dir)
    if not path.exists():
        return PedagogyManifest()
    try:
        payload = json.loads(path.read_text(encoding=_ENCODING_UTF8))
    except (OSError, json.JSONDecodeError):
        return PedagogyManifest()
    if not isinstance(payload, dict):
        return PedagogyManifest()
    return PedagogyManifest.from_dict(payload)


def write_manifest(
    artifacts: FsArtifactStore, pedagogy_dir: Path, manifest: PedagogyManifest
) -> None:
    """Écrit le manifeste de manière atomique.

    Args:
        artifacts: Store d'artefacts (écriture atomique).
        pedagogy_dir: Dossier ``<emplacement>/pedagogy``.
        manifest: Manifeste à persister.
    """
    artifacts.write_json_atomic(manifest_path(pedagogy_dir), manifest.to_dict())
```

- [ ] **Step 4 : Lancer** → PASS.

Run: `.venv\Scripts\python.exe -m pytest tests/unit/pedagogy/test_manifest.py -v`

---

## Task 10 : Sérialisation d'artefacts + chemins

> §5.3 : « écrit `pedagogy/<support>/<lang>/…` (JSON + `.md`) ». Helper de chemins +
> sérialisation des items (`dataclasses.asdict`, suffisant pour `Flashcard` ; étendu
> au SP2/03 si des entités imbriquées l'exigent).

**Files:** Create `src/fahmi2/pedagogy/artifact_writer.py` (couvert par Tasks 11 & 13)

- [ ] **Step 1 : Créer `pedagogy/artifact_writer.py`** :

```python
"""Chemins et sérialisation des artefacts de supports pédagogiques.

Layout sur disque : ``<pedagogy_dir>/<support>/<lang>/<support>.{json,md}``.
Le JSON porte la représentation structurée (items) ; le ``.md`` le rendu lisible.
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from fahmi2.domain.enums import Language, SupportType
from fahmi2.domain.supports import SupportArtifact, SupportItem

_JSON_EXT = ".json"
_MD_EXT = ".md"


def support_dir(pedagogy_dir: Path, support_type: SupportType, language: Language) -> Path:
    """Dossier d'un support pour une langue.

    Args:
        pedagogy_dir: Dossier ``<emplacement>/pedagogy``.
        support_type: Type de support.
        language: Langue.

    Returns:
        ``<pedagogy_dir>/<support>/<lang>``.
    """
    return pedagogy_dir / support_type.value / language.value


def artifact_json_path(
    pedagogy_dir: Path, support_type: SupportType, language: Language
) -> Path:
    """Chemin du fichier JSON d'un support.

    Args:
        pedagogy_dir: Dossier pédagogie.
        support_type: Type de support.
        language: Langue.

    Returns:
        Le chemin ``…/<support>.json``.
    """
    return support_dir(pedagogy_dir, support_type, language) / f"{support_type.value}{_JSON_EXT}"


def artifact_markdown_path(
    pedagogy_dir: Path, support_type: SupportType, language: Language
) -> Path:
    """Chemin du fichier Markdown d'un support.

    Args:
        pedagogy_dir: Dossier pédagogie.
        support_type: Type de support.
        language: Langue.

    Returns:
        Le chemin ``…/<support>.md``.
    """
    return support_dir(pedagogy_dir, support_type, language) / f"{support_type.value}{_MD_EXT}"


def serialize_artifact(artifact: SupportArtifact) -> dict[str, Any]:
    """Sérialise un ``SupportArtifact`` en dict JSON-compatible.

    Args:
        artifact: Artefact à sérialiser.

    Returns:
        Dict ``{support_type, language, cost_usd, items: [...]}``.
    """
    return {
        "support_type": artifact.support_type.value,
        "language": artifact.language.value,
        "cost_usd": artifact.cost_usd,
        "items": [_serialize_item(item) for item in artifact.items],
    }


def _serialize_item(item: SupportItem) -> dict[str, Any]:
    """Sérialise un item de support (dataclass plat).

    Args:
        item: Item à sérialiser.

    Returns:
        Dict des champs (tuples → listes via ``json``).
    """
    return asdict(item)
```

- [ ] **Step 2 : Vérifier l'import** :

Run: `.venv\Scripts\python.exe -c "from fahmi2.pedagogy.artifact_writer import serialize_artifact, artifact_json_path; print('ok')"`
Expected: `ok`.

---

## Task 11 : Générateur flashcards glossaire (sans LLM)

> §6 : recto = terme (+ acronyme), verso = définition, depuis le glossaire.

**Files:** Create `src/fahmi2/pedagogy/generators/__init__.py`,
`src/fahmi2/pedagogy/generators/flashcards_glossary.py` ;
Test `tests/unit/pedagogy/test_flashcards_glossary.py`

- [ ] **Step 1 : Créer le sous-package** `src/fahmi2/pedagogy/generators/__init__.py` :

```python
"""Générateurs de supports de révision (un module par support)."""
```

- [ ] **Step 2 : Test (échoue)** — `tests/unit/pedagogy/test_flashcards_glossary.py` :

```python
"""Tests du générateur de flashcards glossaire (sans LLM)."""

from __future__ import annotations

from pathlib import Path

from fahmi2.domain.enums import Language, SupportType
from fahmi2.domain.glossary import Term
from fahmi2.infra.llm._fakes import FakeLLMProvider
from fahmi2.infra.prompts.loader import PromptLoader
from fahmi2.infra.storage.fs_artifacts import FsArtifactStore
from fahmi2.pedagogy.events import PedagogyEvent
from fahmi2.pedagogy.generators.flashcards_glossary import FlashcardsGlossaryGenerator
from fahmi2.pedagogy.support_generator import SupportContext
from fahmi2.pipeline.event_bus import EventBus
from fahmi2.pipeline.pause_token import PauseToken


def _ctx(tmp_path: Path, make_pedagogy_settings) -> SupportContext:  # type: ignore[no-untyped-def]
    return SupportContext(
        pedagogy=make_pedagogy_settings(),
        generation_output_dir=tmp_path / "generation" / "output",
        pedagogy_dir=tmp_path / "pedagogy",
        llm_provider=FakeLLMProvider(),
        prompts=PromptLoader(),
        artifacts=FsArtifactStore(),
        event_bus=EventBus[PedagogyEvent](),
        pause_token=PauseToken(),
    )


def test_generates_one_card_per_term(tmp_path: Path, make_pedagogy_settings) -> None:  # type: ignore[no-untyped-def]
    gen = FlashcardsGlossaryGenerator()
    glossary = (
        Term(term="Produit intérieur brut", definition="Somme des valeurs ajoutées", acronym="PIB"),
        Term(term="Inflation", definition="Hausse générale des prix"),
    )
    artifact = gen.generate(
        _ctx(tmp_path, make_pedagogy_settings),
        language=Language.FR,
        chapters=(),
        glossary=glossary,
    )
    assert gen.support_type is SupportType.FLASHCARDS_GLOSSARY
    assert gen.uses_llm is False
    assert len(artifact.items) == 2
    assert artifact.items[0].front == "Produit intérieur brut (PIB)"
    assert artifact.items[0].back == "Somme des valeurs ajoutées"
    assert artifact.items[1].front == "Inflation"
    assert artifact.cost_usd == 0.0
    assert "Produit intérieur brut" in artifact.rendered_markdown


def test_empty_glossary_yields_empty_deck(tmp_path: Path, make_pedagogy_settings) -> None:  # type: ignore[no-untyped-def]
    artifact = FlashcardsGlossaryGenerator().generate(
        _ctx(tmp_path, make_pedagogy_settings),
        language=Language.FR,
        chapters=(),
        glossary=(),
    )
    assert artifact.items == ()
```

- [ ] **Step 3 : Lancer** → FAIL.

- [ ] **Step 4 : Créer `pedagogy/generators/flashcards_glossary.py`** :

```python
"""Générateur de flashcards à partir du glossaire (sans LLM).

Recto = terme (+ acronyme entre parenthèses s'il existe), verso = définition.
Première tranche verticale (design §6) : produit un ``SupportArtifact`` JSON + MD
sans aucun appel LLM (coût 0).
"""

from __future__ import annotations

from fahmi2.domain.enums import Language, SupportType
from fahmi2.domain.glossary import Term
from fahmi2.domain.supports import Flashcard, SupportArtifact
from fahmi2.pedagogy.chapters import Chapter
from fahmi2.pedagogy.support_generator import SupportContext, SupportGenerator

_GLOSSARY_SOURCE_REF = "glossaire"
_CARD_SEPARATOR = "\n---\n\n"


class FlashcardsGlossaryGenerator(SupportGenerator):
    """Produit une carte recto/verso par terme du glossaire."""

    @property
    def support_type(self) -> SupportType:
        """Type de support produit."""
        return SupportType.FLASHCARDS_GLOSSARY

    @property
    def uses_llm(self) -> bool:
        """Générateur déterministe, sans LLM."""
        return False

    def generate(
        self,
        ctx: SupportContext,
        *,
        language: Language,
        chapters: tuple[Chapter, ...],
        glossary: tuple[Term, ...],
    ) -> SupportArtifact:
        """Génère le jeu de flashcards depuis le glossaire.

        Args:
            ctx: Contexte (inutilisé ici : pas de LLM, pas de prompt).
            language: Langue cible.
            chapters: Chapitres (inutilisés pour ce support).
            glossary: Termes du glossaire pour cette langue.

        Returns:
            Le ``SupportArtifact`` (cartes + Markdown rendu, coût 0).
        """
        del ctx, chapters
        cards = tuple(self._term_to_card(term, language) for term in glossary)
        return SupportArtifact(
            support_type=self.support_type,
            language=language,
            items=cards,
            rendered_markdown=self._render_markdown(cards, language),
            cost_usd=0.0,
        )

    def _term_to_card(self, term: Term, language: Language) -> Flashcard:
        """Construit la flashcard d'un terme.

        Args:
            term: Terme du glossaire.
            language: Langue (pour les tags).

        Returns:
            La ``Flashcard`` recto/verso.
        """
        front = f"{term.term} ({term.acronym})" if term.acronym else term.term
        return Flashcard(
            front=front,
            back=term.definition,
            source_ref=term.term or _GLOSSARY_SOURCE_REF,
            tags=(self.support_type.value, language.value),
        )

    def _render_markdown(
        self, cards: tuple[Flashcard, ...], language: Language
    ) -> str:
        """Rend le jeu de cartes en Markdown lisible.

        Args:
            cards: Cartes générées.
            language: Langue (titre).

        Returns:
            Le Markdown du paquet.
        """
        header = f"# Flashcards — Glossaire ({language.value})\n"
        if not cards:
            return f"{header}\n_Aucun terme de glossaire disponible._\n"
        blocks = [f"### {card.front}\n\n{card.back}\n" for card in cards]
        return header + "\n" + _CARD_SEPARATOR.join(blocks)
```

- [ ] **Step 5 : Lancer** → PASS.

Run: `.venv\Scripts\python.exe -m pytest tests/unit/pedagogy/test_flashcards_glossary.py -v`

---

## Task 12 : `ProjectService.get_last_completed_run`

> §4 : le glossaire vient du **dernier run COMPLETED**. `get_last_run` renvoie le plus
> récent quel que soit le statut → nouvelle méthode dédiée (réutilisée par l'orchestrateur
> SP2/02 et l'estimation/UI SP2/04).

**Files:** Modify `src/fahmi2/app/project_service.py` ; Test `tests/unit/app/test_project_service.py`

- [ ] **Step 1 : Test (échoue)** — ajouter à `test_project_service.py` :

```python
def test_get_last_completed_run(tmp_path: Path, make_generation_settings: Any) -> None:
    from datetime import UTC, datetime

    from fahmi2.domain.enums import RunStatus
    from fahmi2.domain.ids import RunId
    from fahmi2.domain.run import Run

    state = SqliteState(tmp_path / "t.db")
    service = ProjectService(state)
    project = service.create_project(
        name="X", workspace_folder=tmp_path / "ws", generation=make_generation_settings()
    )
    settings = make_generation_settings()
    failed = Run(
        id=RunId.new(), project_id=project.id, started_at=datetime.now(tz=UTC),
        status=RunStatus.FAILED, settings_snapshot=settings,
    )
    completed = Run(
        id=RunId.new(), project_id=project.id, started_at=datetime.now(tz=UTC),
        status=RunStatus.COMPLETED, settings_snapshot=settings,
    )
    state.upsert_run(failed)
    state.upsert_run(completed)
    last = service.get_last_completed_run(project.id)
    assert last is not None
    assert last.id == completed.id


def test_get_last_completed_run_none_when_no_completed(
    tmp_path: Path, make_generation_settings: Any
) -> None:
    state = SqliteState(tmp_path / "t.db")
    service = ProjectService(state)
    project = service.create_project(
        name="X", workspace_folder=tmp_path / "ws", generation=make_generation_settings()
    )
    assert service.get_last_completed_run(project.id) is None
```

> Vérifier/compléter les imports en tête du fichier (`SqliteState`, `ProjectService`,
> `Path`, `Any`) — déjà présents dans ce fichier de test.

- [ ] **Step 2 : Lancer** → FAIL.

- [ ] **Step 3 : Ajouter la méthode** dans `ProjectService` (après `get_last_run`) :

```python
    def get_last_completed_run(self, project_id: ProjectId) -> Run | None:
        """Retourne le dernier run ``COMPLETED`` du projet (ou ``None``).

        Args:
            project_id: Identifiant.

        Returns:
            Le run ``COMPLETED`` le plus récent, ou ``None`` si aucun.
        """
        completed = [
            run
            for run in self.list_runs(project_id)
            if run.status is RunStatus.COMPLETED
        ]
        return completed[-1] if completed else None
```

  Ajouter l'import `RunStatus` si absent : `from fahmi2.domain.enums import RunStatus`
  (vérifier l'en-tête de `project_service.py`).

- [ ] **Step 4 : Lancer** → PASS.

Run: `.venv\Scripts\python.exe -m pytest tests/unit/app/test_project_service.py -q`

---

## Task 13 : `SupportsOrchestrator`

> §5.3. Charge inputs par langue (chapitres + glossaire), itère
> `selected_supports × languages` dans l'ordre canonique, invoque le générateur,
> écrit JSON + MD, émet les events, agrège le coût, applique la **reprise coarse**
> (manifeste) et gère **pause/annulation**. Pas de `with_retry` ici : le retry LLM
> vivra **dans** les générateurs LLM (SP2/03). Pas d'enforcement du plafond de coût
> ici (SP2/04 : seul le générateur flashcards, coût 0, existe).

**Files:** Create `src/fahmi2/app/supports_orchestrator.py` ;
Test `tests/unit/app/test_supports_orchestrator.py`

- [ ] **Step 1 : Test (échoue)** — `tests/unit/app/test_supports_orchestrator.py` :

```python
"""Tests du SupportsOrchestrator (tranche flashcards glossaire)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fahmi2.app.project_service import ProjectService
from fahmi2.app.supports_orchestrator import SupportsOrchestrator
from fahmi2.core.errors.exceptions import LLMError
from fahmi2.core.errors.severity import Severity
from fahmi2.domain.enums import Language, PhaseStatus, RunStatus, SupportType
from fahmi2.domain.generation import (
    GENERATION_OUTPUT_SUBDIR,
    GENERATION_WORKSPACE_SUBDIR,
)
from fahmi2.domain.glossary import Term
from fahmi2.domain.ids import RunId
from fahmi2.domain.run import Run
from fahmi2.domain.supports import Flashcard, SupportArtifact
from fahmi2.infra.llm._fakes import FakeLLMProvider
from fahmi2.infra.prompts.loader import PromptLoader
from fahmi2.infra.storage.fs_artifacts import FsArtifactStore
from fahmi2.infra.storage.sqlite_state import SqliteState
from fahmi2.pedagogy.artifact_writer import artifact_json_path, artifact_markdown_path
from fahmi2.pedagogy.chapters import Chapter
from fahmi2.pedagogy.events import (
    PedagogyEvent,
    SupportFinished,
    SupportGenerationFinished,
)
from fahmi2.pedagogy.generators.flashcards_glossary import FlashcardsGlossaryGenerator
from fahmi2.pedagogy.support_generator import SupportContext, SupportGenerator
from fahmi2.pedagogy.support_registry import SupportGeneratorRegistry
from fahmi2.pipeline.event_bus import EventBus
from fahmi2.pipeline.pause_token import PauseToken


def _seed_completed_run_with_glossary(
    state: SqliteState, project_id: Any, settings: Any
) -> None:
    run = Run(
        id=RunId.new(),
        project_id=project_id,
        started_at=datetime.now(tz=UTC),
        status=RunStatus.COMPLETED,
        settings_snapshot=settings,
    )
    state.upsert_run(run)
    state.upsert_glossary_term(
        run.id, Language.FR, Term(term="PIB", definition="Produit intérieur brut")
    )


def _build(
    tmp_path: Path,
    registry: SupportGeneratorRegistry,
) -> tuple[SupportsOrchestrator, SqliteState, ProjectService]:
    state = SqliteState(tmp_path / "t.db")
    project_service = ProjectService(state)
    orchestrator = SupportsOrchestrator(
        state=state,
        project_service=project_service,
        registry=registry,
        artifacts=FsArtifactStore(),
        llm_provider=FakeLLMProvider(),
        prompts=PromptLoader(),
    )
    return orchestrator, state, project_service


def _collect(bus: EventBus[PedagogyEvent]) -> list[PedagogyEvent]:
    events: list[PedagogyEvent] = []
    bus.subscribe(events.append)
    return events


def test_generates_flashcards_artifacts(
    tmp_path: Path, make_generation_settings: Any, make_pedagogy_settings: Any
) -> None:
    registry = SupportGeneratorRegistry([FlashcardsGlossaryGenerator()])
    orchestrator, state, project_service = _build(tmp_path, registry)
    ws = tmp_path / "ws"
    project = project_service.create_project(
        name="P",
        workspace_folder=ws,
        generation=make_generation_settings(),
        pedagogy=make_pedagogy_settings(),
    )
    _seed_completed_run_with_glossary(state, project.id, make_generation_settings())

    bus: EventBus[PedagogyEvent] = EventBus()
    events = _collect(bus)
    status = orchestrator.generate(project, pause_token=PauseToken(), event_bus=bus)

    assert status is RunStatus.COMPLETED
    pedagogy_dir = ws / "pedagogy"
    json_path = artifact_json_path(
        pedagogy_dir, SupportType.FLASHCARDS_GLOSSARY, Language.FR
    )
    md_path = artifact_markdown_path(
        pedagogy_dir, SupportType.FLASHCARDS_GLOSSARY, Language.FR
    )
    assert json_path.exists()
    assert md_path.exists()
    assert (pedagogy_dir / "manifest.json").exists()
    finished = [e for e in events if isinstance(e, SupportFinished)]
    assert finished and finished[0].status is PhaseStatus.SUCCEEDED
    assert isinstance(events[-1], SupportGenerationFinished)


def test_coarse_resume_skips_fresh(
    tmp_path: Path, make_generation_settings: Any, make_pedagogy_settings: Any
) -> None:
    registry = SupportGeneratorRegistry([FlashcardsGlossaryGenerator()])
    orchestrator, state, project_service = _build(tmp_path, registry)
    project = project_service.create_project(
        name="P",
        workspace_folder=tmp_path / "ws",
        generation=make_generation_settings(),
        pedagogy=make_pedagogy_settings(),
    )
    _seed_completed_run_with_glossary(state, project.id, make_generation_settings())

    orchestrator.generate(project, pause_token=PauseToken(), event_bus=EventBus())
    bus: EventBus[PedagogyEvent] = EventBus()
    events = _collect(bus)
    orchestrator.generate(project, pause_token=PauseToken(), event_bus=bus)

    finished = [e for e in events if isinstance(e, SupportFinished)]
    assert finished and finished[0].status is PhaseStatus.SKIPPED


class _FailingGen(SupportGenerator):
    @property
    def support_type(self) -> SupportType:
        return SupportType.FLASHCARDS_GLOSSARY

    @property
    def uses_llm(self) -> bool:
        return False

    def generate(
        self,
        ctx: SupportContext,
        *,
        language: Language,
        chapters: tuple[Chapter, ...],
        glossary: tuple[Term, ...],
    ) -> SupportArtifact:
        del ctx, language, chapters, glossary
        raise LLMError(
            code="LLM.BOOM", user_message="boom", severity=Severity.ERROR
        )


def test_generator_failure_yields_failed_status(
    tmp_path: Path, make_generation_settings: Any, make_pedagogy_settings: Any
) -> None:
    registry = SupportGeneratorRegistry([_FailingGen()])
    orchestrator, state, project_service = _build(tmp_path, registry)
    project = project_service.create_project(
        name="P",
        workspace_folder=tmp_path / "ws",
        generation=make_generation_settings(),
        pedagogy=make_pedagogy_settings(),
    )
    _seed_completed_run_with_glossary(state, project.id, make_generation_settings())

    bus: EventBus[PedagogyEvent] = EventBus()
    events = _collect(bus)
    status = orchestrator.generate(project, pause_token=PauseToken(), event_bus=bus)

    assert status is RunStatus.FAILED
    failed = [e for e in events if isinstance(e, SupportFinished)]
    assert failed and failed[0].status is PhaseStatus.FAILED
    assert failed[0].error is not None and failed[0].error.code == "LLM.BOOM"
```

- [ ] **Step 2 : Lancer** → FAIL.

- [ ] **Step 3 : Créer `app/supports_orchestrator.py`** :

```python
"""``SupportsOrchestrator`` — service applicatif pilotant la génération des supports.

Orchestrateur dédié **léger** (design §2.1) : ne réutilise pas le ``PipelineEngine``.
Pour chaque langue, charge les entrants (chapitres du doc consolidé + glossaire du
dernier run COMPLETED), itère les supports sélectionnés dans l'ordre canonique du
registre, invoque le générateur, écrit les artefacts (JSON + Markdown), met à jour
le manifeste de fraîcheur (reprise coarse) et émet les événements pédagogie. Gère
pause/annulation aux frontières sûres (entre supports).
"""

from __future__ import annotations

from datetime import UTC, datetime

from fahmi2.app.project_service import ProjectService
from fahmi2.core.errors.error_info import ErrorInfo
from fahmi2.core.errors.exceptions import ConfigError, Fahmi2Error, PausedError
from fahmi2.core.errors.severity import Severity
from fahmi2.domain.enums import Language, PhaseStatus, RunStatus, SupportType
from fahmi2.domain.generation import (
    GENERATION_OUTPUT_SUBDIR,
    GENERATION_WORKSPACE_SUBDIR,
    consolidated_doc_filename,
)
from fahmi2.domain.glossary import Term
from fahmi2.domain.pedagogy import PEDAGOGY_WORKSPACE_SUBDIR, PedagogySettings
from fahmi2.domain.project import Project
from fahmi2.domain.supports import SupportArtifact
from fahmi2.infra.llm.interface import LLMProvider
from fahmi2.infra.prompts.loader import PromptLoader
from fahmi2.infra.storage.fs_artifacts import FsArtifactStore
from fahmi2.infra.storage.sqlite_state import SqliteState
from fahmi2.pedagogy.artifact_writer import (
    artifact_json_path,
    artifact_markdown_path,
    serialize_artifact,
)
from fahmi2.pedagogy.chapters import Chapter, parse_chapters
from fahmi2.pedagogy.events import (
    PedagogyEvent,
    SupportFinished,
    SupportGenerationFinished,
    SupportGenerationStarted,
    SupportStarted,
)
from fahmi2.pedagogy.manifest import (
    PedagogyManifest,
    compute_settings_hash,
    read_manifest,
    write_manifest,
)
from fahmi2.pedagogy.support_generator import SupportContext
from fahmi2.pedagogy.support_registry import SupportGeneratorRegistry
from fahmi2.pipeline.event_bus import EventBus
from fahmi2.pipeline.pause_token import PauseToken


class SupportsOrchestrator:
    """Pilote la génération des supports pédagogiques d'un projet."""

    def __init__(
        self,
        *,
        state: SqliteState,
        project_service: ProjectService,
        registry: SupportGeneratorRegistry,
        artifacts: FsArtifactStore,
        llm_provider: LLMProvider,
        prompts: PromptLoader,
    ) -> None:
        """Construit l'orchestrateur.

        Args:
            state: Stockage SQLite (lecture glossaire).
            project_service: Service projet (dernier run COMPLETED).
            registry: Registre des générateurs.
            artifacts: Écriture atomique d'artefacts.
            llm_provider: Provider LLM (générateurs LLM, SP2/03).
            prompts: Loader de prompts.
        """
        self._state = state
        self._project_service = project_service
        self._registry = registry
        self._artifacts = artifacts
        self._llm_provider = llm_provider
        self._prompts = prompts

    def generate(
        self,
        project: Project,
        *,
        pause_token: PauseToken,
        event_bus: EventBus[PedagogyEvent],
    ) -> RunStatus:
        """Génère les supports sélectionnés pour toutes les langues.

        Args:
            project: Projet (doit avoir ``pedagogy`` configuré).
            pause_token: Jeton coopératif pause/annulation.
            event_bus: Bus d'événements pédagogie.

        Returns:
            ``COMPLETED`` (succès), ``FAILED`` (≥1 support échoué) ou
            ``CANCELLED`` (annulé par l'utilisateur).

        Raises:
            ConfigError: Si la pédagogie n'est pas configurée sur le projet.
        """
        pedagogy = project.pedagogy
        if pedagogy is None:
            raise ConfigError(
                code="PEDAGOGY.NOT_CONFIGURED",
                user_message="La fonctionnalité Supports pédagogiques n'est pas configurée.",
                severity=Severity.ERROR,
                technical_details={"project_id": project.id.value},
            )

        ctx = self._build_context(project, pedagogy, pause_token, event_bus)
        settings_hash = compute_settings_hash(pedagogy)
        manifest = read_manifest(ctx.pedagogy_dir)
        event_bus.publish(SupportGenerationStarted(timestamp=_now()))

        any_failure = False
        total_cost = 0.0
        try:
            for language in pedagogy.languages:
                source_mtime = self._source_mtime_ns(ctx.generation_output_dir, language)
                chapters = self._load_chapters(ctx.generation_output_dir, language)
                glossary = self._load_glossary(project, language)
                for support_type in self._registry.canonical_order():
                    if support_type not in pedagogy.selected_supports:
                        continue
                    if not self._registry.has(support_type):
                        continue
                    pause_token.wait_if_paused()
                    pause_token.raise_if_cancelled()
                    cost, failed = self._run_one(
                        ctx,
                        manifest=manifest,
                        support_type=support_type,
                        language=language,
                        chapters=chapters,
                        glossary=glossary,
                        settings_hash=settings_hash,
                        source_mtime_ns=source_mtime,
                    )
                    total_cost += cost
                    any_failure = any_failure or failed
        except PausedError:
            event_bus.publish(
                SupportGenerationFinished(
                    timestamp=_now(),
                    status=RunStatus.CANCELLED,
                    total_cost_usd=total_cost,
                )
            )
            return RunStatus.CANCELLED

        final = RunStatus.FAILED if any_failure else RunStatus.COMPLETED
        event_bus.publish(
            SupportGenerationFinished(
                timestamp=_now(), status=final, total_cost_usd=total_cost
            )
        )
        return final

    def _run_one(
        self,
        ctx: SupportContext,
        *,
        manifest: PedagogyManifest,
        support_type: SupportType,
        language: Language,
        chapters: tuple[Chapter, ...],
        glossary: tuple[Term, ...],
        settings_hash: str,
        source_mtime_ns: int | None,
    ) -> tuple[float, bool]:
        """Génère (ou skippe) un support pour une langue.

        Args:
            ctx: Contexte d'exécution.
            manifest: Manifeste de fraîcheur (mis à jour + persisté en cas de succès).
            support_type: Type de support.
            language: Langue.
            chapters: Chapitres du doc consolidé.
            glossary: Glossaire de la langue.
            settings_hash: Hash courant des réglages.
            source_mtime_ns: mtime courant du doc source.

        Returns:
            ``(cost_usd, failed)`` : coût LLM et drapeau d'échec.
        """
        ctx.event_bus.publish(
            SupportStarted(
                timestamp=_now(), support_type=support_type, language=language
            )
        )
        json_path = artifact_json_path(ctx.pedagogy_dir, support_type, language)
        is_fresh = manifest.is_fresh(
            support_type,
            language,
            settings_hash=settings_hash,
            source_mtime_ns=source_mtime_ns,
        )
        if is_fresh and json_path.exists():
            ctx.event_bus.publish(
                SupportFinished(
                    timestamp=_now(),
                    support_type=support_type,
                    language=language,
                    status=PhaseStatus.SKIPPED,
                    cost_usd=0.0,
                    error=None,
                )
            )
            return 0.0, False

        try:
            artifact = self._registry.get(support_type).generate(
                ctx, language=language, chapters=chapters, glossary=glossary
            )
            self._write_artifact(ctx, artifact)
            manifest.record(
                support_type,
                language,
                settings_hash=settings_hash,
                source_mtime_ns=source_mtime_ns,
            )
            write_manifest(ctx.artifacts, ctx.pedagogy_dir, manifest)
            ctx.event_bus.publish(
                SupportFinished(
                    timestamp=_now(),
                    support_type=support_type,
                    language=language,
                    status=PhaseStatus.SUCCEEDED,
                    cost_usd=artifact.cost_usd,
                    error=None,
                )
            )
            return artifact.cost_usd, False
        except Fahmi2Error as exc:
            ctx.event_bus.publish(
                SupportFinished(
                    timestamp=_now(),
                    support_type=support_type,
                    language=language,
                    status=PhaseStatus.FAILED,
                    cost_usd=0.0,
                    error=ErrorInfo.from_exception(exc),
                )
            )
            return 0.0, True

    def _write_artifact(self, ctx: SupportContext, artifact: SupportArtifact) -> None:
        """Écrit l'artefact (JSON + Markdown) sous ``pedagogy/``.

        Args:
            ctx: Contexte (dossier pédagogie + store).
            artifact: Artefact à persister.
        """
        json_path = artifact_json_path(
            ctx.pedagogy_dir, artifact.support_type, artifact.language
        )
        md_path = artifact_markdown_path(
            ctx.pedagogy_dir, artifact.support_type, artifact.language
        )
        ctx.artifacts.write_json_atomic(json_path, serialize_artifact(artifact))
        ctx.artifacts.write_text_atomic(md_path, artifact.rendered_markdown)

    def _build_context(
        self,
        project: Project,
        pedagogy: PedagogySettings,
        pause_token: PauseToken,
        event_bus: EventBus[PedagogyEvent],
    ) -> SupportContext:
        """Construit le ``SupportContext`` (dépendances stables).

        Args:
            project: Projet.
            pedagogy: Réglages pédagogie (non None).
            pause_token: Jeton de pause.
            event_bus: Bus d'événements.

        Returns:
            Le contexte d'exécution.
        """
        generation_output_dir = (
            project.workspace_folder
            / GENERATION_WORKSPACE_SUBDIR
            / GENERATION_OUTPUT_SUBDIR
        )
        return SupportContext(
            pedagogy=pedagogy,
            generation_output_dir=generation_output_dir,
            pedagogy_dir=project.workspace_folder / PEDAGOGY_WORKSPACE_SUBDIR,
            llm_provider=self._llm_provider,
            prompts=self._prompts,
            artifacts=self._artifacts,
            event_bus=event_bus,
            pause_token=pause_token,
        )

    def _load_chapters(
        self, generation_output_dir: Path, language: Language
    ) -> tuple[Chapter, ...]:
        """Charge et parse les chapitres du doc consolidé (vide si absent).

        Args:
            generation_output_dir: Dossier des livrables génération.
            language: Langue.

        Returns:
            Les chapitres (vide si le fichier n'existe pas).
        """
        doc = generation_output_dir / consolidated_doc_filename(language)
        if not doc.exists():
            return ()
        return parse_chapters(doc.read_text(encoding="utf-8"))

    def _load_glossary(self, project: Project, language: Language) -> tuple[Term, ...]:
        """Charge le glossaire de la langue depuis le dernier run COMPLETED.

        Args:
            project: Projet.
            language: Langue.

        Returns:
            Les termes (vide si aucun run COMPLETED).
        """
        run = self._project_service.get_last_completed_run(project.id)
        if run is None:
            return ()
        return tuple(self._state.list_glossary_terms(run.id, language))

    @staticmethod
    def _source_mtime_ns(
        generation_output_dir: Path, language: Language
    ) -> int | None:
        """mtime (ns) du doc consolidé source, ou ``None`` s'il est absent.

        Args:
            generation_output_dir: Dossier des livrables génération.
            language: Langue.

        Returns:
            Le ``st_mtime_ns`` du fichier, ou ``None``.
        """
        doc = generation_output_dir / consolidated_doc_filename(language)
        if not doc.exists():
            return None
        return doc.stat().st_mtime_ns


def _now() -> datetime:
    """Horodatage UTC courant.

    Returns:
        ``datetime`` UTC aware.
    """
    return datetime.now(tz=UTC)
```

  > **Import manquant** : ajouter `from pathlib import Path` en tête (utilisé par les
  > annotations `_load_chapters`/`_source_mtime_ns`). Vérifier que `ConfigError`,
  > `Fahmi2Error`, `PausedError` existent bien dans `core.errors.exceptions` (oui :
  > hiérarchie `Fahmi2Error`).

- [ ] **Step 4 : Lancer** → PASS.

Run: `.venv\Scripts\python.exe -m pytest tests/unit/app/test_supports_orchestrator.py -v`

---

## Task 14 : Vérifications systématiques + commit + avancement

- [ ] **Step 1 : Suite complète** :

Run: `.venv\Scripts\python.exe -m pytest -q`
Expected: tout vert (508 + nouveaux tests).

- [ ] **Step 2 : Lint** :

Run: `.venv\Scripts\python.exe -m ruff check .`
Expected: `All checks passed!` (corriger imports morts / ordre d'imports / lignes longues
si signalés — notamment les imports de `_base.py` après délégation).

- [ ] **Step 3 : Types** :

Run: `.venv\Scripts\python.exe -m mypy src tests`
Expected: `Success: no issues found`.
> Points d'attention : `EventBus` doit toujours être paramétré (`EventBus[...]`) en
> annotation ; `parse_llm_json`/`parse_json_response` annotés `Any` (avec `# noqa: ANN401`).

- [ ] **Step 4 : Mettre à jour le doc d'avancement.** Dans
  `docs/superpowers/plans/2026-05-20-sp2-sp3-00-avancement.md` : déplacer **SP2/02** de
  « Reste à faire » vers « Fait ✅ » (mentionner : socle orchestrateur, registre,
  contexte DI, parseur de chapitres, lecture glossaire DB, manifeste, events,
  générateur flashcards glossaire, helpers LLM généralisés, `EventBus` générique,
  régression pedagogy corrigée). Mettre à jour le compteur de tests.

- [ ] **Step 5 : Mettre à jour la doc transverse** si nécessaire : ajouter l'arborescence
  `pedagogy/<support>/<lang>/<support>.{json,md}` + `pedagogy/manifest.json` à
  `docs/02-presentation-technique.md` (§4.2), et une ligne `CHANGELOG.md`
  (« SP2/02 — socle générateur de supports + flashcards glossaire »).

- [ ] **Step 6 : Commit (lot complet, après tout vert)** :

```bash
git add -A
git commit -m "feat(pedagogy): socle orchestrateur + flashcards glossaire (SP2/02)"
```

  > Message multi-lignes possible (corps : helpers LLM généralisés, EventBus générique,
  > parseur chapitres, manifeste, régression pedagogy). Terminer par le `Co-Authored-By`
  > usuel.

---

## Self-review (à exécuter avant de coder, et après)

**Couverture du design :**

- §5.1 `SupportGenerator` + registre → Tasks 7, 8.
- §5.2 `SupportContext` (DI, frozen, sans STT/ffmpeg) → Task 7.
- §5.3 orchestrateur : inputs (chapitres + glossaire), boucle, écriture JSON+MD, events,
  agrégation coût, reprise coarse, helpers LLM généralisés → Tasks 2, 5, 9, 10, 12, 13.
- §5.4 events pédagogie → Task 6.
- §6 générateur flashcards glossaire (sans LLM) → Task 11.
- §2.2 manifeste de fraîcheur → Task 9 (+ intégration Task 13).
- §4 lecture glossaire DB (dernier run COMPLETED), doc consolidé sur disque → Tasks 12, 13.

**Hors périmètre SP2/02 (assumé, tracé) :** générateurs LLM + prompts `pedagogy_*.j2`
(SP2/03, dont l'**ajout à `_TEMPLATE_METADATA`** pour l'édition des prompts) ; onglet
UI + estimation coût + plafond + fraîcheur affichée + bridge `QtEventBus[PedagogyEvent]`
(SP2/04) ; `with_retry` autour des appels LLM (dans les générateurs LLM, SP2/03) ;
exports `.apkg`/MD/PDF (SP3).

**Cohérence des types/signatures :** `SupportGenerator.generate(ctx, *, language,
chapters, glossary) -> SupportArtifact` (identique Tasks 7/8/11/13) ; `SupportArtifact`
porte `cost_usd` (Task 4, lu Task 13) ; `EventBus[PedagogyEvent]` (Tasks 3/6/7/13) ;
`SupportFinished.status: PhaseStatus`, `SupportGenerationFinished.status: RunStatus`
(Tasks 6/13) ; `compute_settings_hash`/`PedagogyManifest.is_fresh/record`/`read_manifest`/
`write_manifest` (Tasks 9/13) ; `artifact_json_path`/`artifact_markdown_path`/
`serialize_artifact` (Tasks 10/13) ; `consolidated_doc_filename`/`GENERATION_OUTPUT_SUBDIR`
(Tasks 1/13).
