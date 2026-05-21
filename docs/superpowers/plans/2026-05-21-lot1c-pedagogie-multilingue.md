# Lot 1c — Pédagogie : retrait `flashcards_glossary` + langues découplées (#4)

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (inline, sans subagents).
> **Spec** : [`../specs/2026-05-21-corrections-lot1-design.md`](../specs/2026-05-21-corrections-lot1-design.md) §4.
> Steps en checkbox. Tout en français (accents). Travail directement sur `main`.

**Goal:** Retirer le support `flashcards_glossary` (valeur quasi nulle) et découpler
le choix de langue de la pédagogie de ce que la génération a produit (#4) : les 8
supports LLM sont générés dans n'importe quelle langue cible.

**Architecture:** `SupportType` perd `FLASHCARDS_GLOSSARY` (8 types). Le générateur,
sa registration, ses libellés et son désérialiseur disparaissent ; la
désérialisation des réglages persistés devient **tolérante** aux types inconnus.
L'orchestrateur **résout une langue de contenu** (doc consolidé existant) distincte
de la **langue cible** passée aux générateurs. La dépendance morte `project_service`
de l'orchestrateur (issue du Lot 1b) est retirée.

**Tech Stack:** Python 3.12, PySide6, pytest.

**Ordre des tâches** (chaque tâche verte + commit) :
1. retrait du support `flashcards_glossary` (production + tests) ;
2. #4 langues découplées (+ retrait `project_service` mort) ;
3. CHANGELOG + docs.

---

## Task 1 : retrait du support `flashcards_glossary`

**Files (production):**
- `src/fahmi2/domain/enums.py`
- `src/fahmi2/domain/pedagogy.py`
- `src/fahmi2/pedagogy/support_registry.py`
- `src/fahmi2/pedagogy/default_registry.py`
- `src/fahmi2/pedagogy/artifact_reader.py`
- `src/fahmi2/ui/pedagogy_labels.py`
- `src/fahmi2/infra/anki/genanki_exporter.py`
- `src/fahmi2/infra/storage/sqlite_state.py` (désérialisation tolérante)
- Delete : `src/fahmi2/pedagogy/generators/flashcards_glossary.py`

**Files (tests):** swap `FLASHCARDS_GLOSSARY → FLASHCARDS_CONCEPTS` (fixture
générique) + suppressions ciblées (voir steps).

- [ ] **Step 1 : enum** — `domain/enums.py`, retirer la ligne
  `FLASHCARDS_GLOSSARY = "flashcards_glossary"` de `SupportType` (8 membres restants).

- [ ] **Step 2 : domaine pedagogy** — `domain/pedagogy.py`, remplacer :

```python
#: Supports produits sans appel LLM (depuis le glossaire).
NO_LLM_SUPPORTS: frozenset[SupportType] = frozenset({SupportType.FLASHCARDS_GLOSSARY})
```

par :

```python
#: Supports produits sans appel LLM. Vide depuis le retrait de
#: ``flashcards_glossary`` ; conservé pour rester générique (le cost estimator
#: filtre dessus).
NO_LLM_SUPPORTS: frozenset[SupportType] = frozenset()
```

- [ ] **Step 3 : ordre canonique** — `pedagogy/support_registry.py`, retirer
  `SupportType.FLASHCARDS_GLOSSARY,` de `_SUPPORT_ORDER` ; ajuster le docstring
  (« flashcards concepts d'abord, puis les supports LLM » → simplement les 8 supports).

- [ ] **Step 4 : factory** — `pedagogy/default_registry.py`, retirer l'import
  `from fahmi2.pedagogy.generators.flashcards_glossary import FlashcardsGlossaryGenerator`
  et la ligne `FlashcardsGlossaryGenerator(),` ; mettre à jour docstring
  (« 8 générateurs » au lieu de 9).

- [ ] **Step 5 : reader** — `pedagogy/artifact_reader.py`, retirer la ligne
  `SupportType.FLASHCARDS_GLOSSARY: _flashcard,` de `_ITEM_DESERIALIZERS`
  (l'entrée `FLASHCARDS_CONCEPTS: _flashcard` reste).

- [ ] **Step 6 : libellés UI** — `ui/pedagogy_labels.py`, retirer la ligne
  `SupportType.FLASHCARDS_GLOSSARY: "Flashcards — Glossaire",` de `SUPPORT_LABELS`.

- [ ] **Step 7 : libellés Anki** — `infra/anki/genanki_exporter.py`, retirer la
  ligne `SupportType.FLASHCARDS_GLOSSARY: "Flashcards Glossaire",` de `_SUPPORT_LABELS`.

- [ ] **Step 8 : désérialisation tolérante** — `infra/storage/sqlite_state.py`,
  dans `_deserialize_pedagogy_settings`, remplacer la construction directe des
  ensembles par un filtrage des types inconnus. Ajouter en tête du module
  (près des helpers) :

```python
def _known_support_types(values: list[str]) -> frozenset[SupportType]:
    """Convertit des valeurs de support en ``SupportType``, ignorant les inconnus.

    Tolère les réglages persistés référant un support retiré (ex. l'ancien
    ``flashcards_glossary``) : la valeur inconnue est ignorée plutôt que de lever.

    Args:
        values: Valeurs brutes (chaînes) issues du blob persisté.

    Returns:
        Les ``SupportType`` reconnus.
    """
    known = {s.value for s in SupportType}
    return frozenset(SupportType(v) for v in values if v in known)
```

Puis dans `_deserialize_pedagogy_settings`, remplacer :

```python
        selected_supports=frozenset(
            SupportType(s) for s in payload["selected_supports"]
        ),
        separate_correction=frozenset(
            SupportType(s) for s in payload["separate_correction"]
        ),
```

par :

```python
        selected_supports=_known_support_types(payload["selected_supports"]),
        separate_correction=_known_support_types(payload["separate_correction"]),
```

(Si après filtrage `selected_supports` est vide, `PedagogySettings.__post_init__`
lève — capturé par la lecture *lenient* du blob projet, qui retombe alors sur
`pedagogy=None`. Comportement acceptable : un projet n'ayant sélectionné que
l'ancien support perd sa config pédagogie.)

- [ ] **Step 9 : supprimer le générateur + son test**

```powershell
git rm src/fahmi2/pedagogy/generators/flashcards_glossary.py tests/unit/pedagogy/test_flashcards_glossary.py
```

- [ ] **Step 10 : adapter les tests (fixture générique → `FLASHCARDS_CONCEPTS`)**

Dans les fichiers suivants, remplacer les usages de `SupportType.FLASHCARDS_GLOSSARY`
(simple support de test) par `SupportType.FLASHCARDS_CONCEPTS` (qui produit aussi des
`Flashcard`, même désérialiseur, même chemins) :
`tests/unit/pedagogy/test_artifact_writer.py` (y compris les chemins littéraux
`flashcards_glossary` → `flashcards_concepts` et `payload["support_type"] ==
"flashcards_concepts"`), `tests/unit/pedagogy/test_artifact_reader.py`,
`tests/unit/pedagogy/test_manifest.py`, `tests/unit/domain/test_supports.py`,
`tests/unit/infra/anki/test_genanki_exporter.py`,
`tests/unit/app/test_pedagogy_export.py`,
`tests/unit/app/test_pedagogy_export_documents.py`,
`tests/unit/app/test_pedagogy_cost_estimator.py`,
`tests/unit/ui/viewmodels/test_pedagogy_state.py`, `tests/conftest.py`
(défaut `make_pedagogy_settings`).

- [ ] **Step 11 : tests d'enum / registre / domaine pedagogy**

- `tests/unit/domain/test_enums_pedagogy.py` : remplacer l'assertion
  `assert SupportType.FLASHCARDS_GLOSSARY in SupportType` par une assertion sur un
  type restant, ex. `assert SupportType.FLASHCARDS_CONCEPTS in SupportType` et
  `assert len(list(SupportType)) == 8`.
- `tests/unit/domain/test_pedagogy.py` : l'assertion
  `assert SupportType.FLASHCARDS_GLOSSARY in NO_LLM_SUPPORTS` devient
  `assert NO_LLM_SUPPORTS == frozenset()` ; les `selected_supports=frozenset({FLASHCARDS_GLOSSARY})`
  → `frozenset({SupportType.FLASHCARDS_CONCEPTS})`.
- `tests/unit/pedagogy/test_default_registry.py` : l'assertion
  `registry.get(FLASHCARDS_GLOSSARY).uses_llm is False` → vérifier plutôt qu'il y a
  **8** générateurs (`len(registry.canonical_order())` filtré sur `has`), ou que
  `FLASHCARDS_CONCEPTS` est enregistré. Adapter sans référencer l'ancien type.
- `tests/unit/pedagogy/test_support_registry.py` : le `_StubGen` de test retourne
  `FLASHCARDS_GLOSSARY` → le faire retourner `FLASHCARDS_CONCEPTS` ; adapter les
  assertions correspondantes.

- [ ] **Step 12 : orchestrateur & controller (générateur no-LLM de test)**

`test_supports_orchestrator.py` et `test_pedagogy_controller.py` utilisent
`FlashcardsGlossaryGenerator()` comme générateur **déterministe sans LLM**.
Le remplacer par un stub local. Dans `test_supports_orchestrator.py`, ajouter (près
des autres générateurs de test `_FailingGen`/`_CostlyGen`) :

```python
class _StubGen(SupportGenerator):
    def __init__(self, support_type: SupportType) -> None:
        self._support_type = support_type

    @property
    def support_type(self) -> SupportType:
        return self._support_type

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
            support_type=self._support_type,
            language=language,
            items=(),
            rendered_markdown="# Stub\n",
            cost_usd=0.0,
        )
```

Remplacer `SupportGeneratorRegistry([FlashcardsGlossaryGenerator()])` par
`SupportGeneratorRegistry([_StubGen(SupportType.FLASHCARDS_CONCEPTS)])` et les
`SupportType.FLASHCARDS_GLOSSARY` résiduels par `FLASHCARDS_CONCEPTS` (assertions de
chemins, `_CostlyGen(...)`, `_FailingGen.support_type`, separate_correction set,
`succeeded[0].support_type`). Retirer l'import
`from fahmi2.pedagogy.generators.flashcards_glossary import FlashcardsGlossaryGenerator`.

Dans `test_pedagogy_controller.py` : importer/définir un stub équivalent (ou
réutiliser un générateur réel via `FakeLLMProvider`) ; remplacer les deux
`SupportGeneratorRegistry([FlashcardsGlossaryGenerator()])` (lignes ~100 et ~391) et
les `FLASHCARDS_GLOSSARY` résiduels par `FLASHCARDS_CONCEPTS`. Retirer l'import du
générateur supprimé.

- [ ] **Step 13 : `ruff --fix` (imports morts) + suite complète**

```powershell
.venv\Scripts\python.exe -m ruff check --fix .
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m mypy src tests
```
Attendu : tout vert ; **aucune** référence résiduelle à `FLASHCARDS_GLOSSARY` /
`FlashcardsGlossaryGenerator` (vérifier par `grep`).

- [ ] **Step 14 : commit**

```powershell
git add -A
git commit -m @'
refactor(pedagogy): retirer le support flashcards_glossary

Le glossaire reste un document de reference (pas un support) ; flashcards_glossary
(deterministe, valeur quasi nulle) est retire : enum SupportType (8 types),
generateur, registration, libelles, deserialiseur. Deserialisation des reglages
persistes rendue tolerante aux types inconnus (ancien flashcards_glossary ignore).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
'@
```

---

## Task 2 : #4 — langues découplées (+ retrait `project_service` mort)

**Files:**
- `src/fahmi2/ui/pedagogy_controller.py`
- `src/fahmi2/ui/dialogs/pedagogy_settings_view.py`
- `src/fahmi2/app/supports_orchestrator.py`
- Tests : `tests/unit/ui/test_pedagogy_controller.py`, `tests/unit/app/test_supports_orchestrator.py`

- [ ] **Step 1 : test #4 (controller propose toutes les langues)**

Dans `tests/unit/ui/test_pedagogy_controller.py`, ajouter un test :

```python
def test_available_languages_offers_all(
    qtbot: QtBot, tmp_path: Path, make_generation_settings: Any, make_pedagogy_settings: Any
) -> None:
    controller, project_service, _ = _make_controller(qtbot, tmp_path)
    project = project_service.create_project(
        name="P",
        workspace_folder=tmp_path / "ws",
        generation=make_generation_settings(),
        pedagogy=make_pedagogy_settings(),
    )
    langs = controller._available_languages(project)  # noqa: SLF001
    assert set(langs) == set(Language)
```

(adapter `_make_controller` au helper existant du fichier.)

- [ ] **Step 2 : controller — proposer toutes les langues**

Dans `ui/pedagogy_controller.py`, remplacer le corps de `_available_languages` :

```python
        generation_output_dir = self._generation_output_dir(project)
        present = tuple(
            language
            for language in Language
            if consolidated_doc_path(generation_output_dir, language).exists()
        )
        return present or tuple(Language)
```

par :

```python
        del project
        return tuple(Language)
```

et adapter le docstring (« toutes les langues supportées ; la langue de contenu
source est résolue par l'orchestrateur »).

- [ ] **Step 3 : libellé page Langues**

Dans `ui/dialogs/pedagogy_settings_view.py`, page **Langues**, remplacer le texte du
libellé explicatif existant par : « *Les supports sont rédigés dans la langue
choisie, même si le document source est dans une autre langue.* » (constante de
module `_LANGUAGES_HINT`).

- [ ] **Step 4 : test orchestrateur — langue cible sans doc → repli de contenu**

Dans `tests/unit/app/test_supports_orchestrator.py`, ajouter :

```python
def test_target_language_without_doc_uses_fallback_content(
    tmp_path: Path, make_generation_settings: Any, make_pedagogy_settings: Any
) -> None:
    registry = SupportGeneratorRegistry([_StubGen(SupportType.FLASHCARDS_CONCEPTS)])
    orchestrator, state, project_service = _build(tmp_path, registry)
    ws = tmp_path / "ws"
    project = project_service.create_project(
        name="P",
        workspace_folder=ws,
        generation=make_generation_settings(source_language=Language.FR),
        pedagogy=make_pedagogy_settings(
            selected_supports=frozenset({SupportType.FLASHCARDS_CONCEPTS}),
            languages=(Language.EN,),
        ),
    )
    _seed_completed_run(state, project, make_generation_settings())
    # Seul le doc FR (source) existe ; la cible EN doit l'utiliser comme contenu.
    FsArtifactStore().write_text_atomic(
        ws / GENERATION_WORKSPACE_SUBDIR / GENERATION_OUTPUT_SUBDIR
        / consolidated_doc_filename(Language.FR),
        "# Cours\n\n# 1. Bases\n\nContenu.\n",
    )
    status = orchestrator.generate(
        project, pause_token=PauseToken(), event_bus=EventBus()
    )
    assert status is RunStatus.COMPLETED
    # Artefact écrit sous la langue cible EN.
    assert artifact_json_path(
        ws / "pedagogy", SupportType.FLASHCARDS_CONCEPTS, Language.EN
    ).exists()
```

(`_seed_completed_run` existe déjà ; sinon, ajouter le helper qui upsert un run
COMPLETED.)

- [ ] **Step 5 : orchestrateur — découplage contenu/cible + retrait `project_service`**

Dans `app/supports_orchestrator.py` :

Ajouter `consolidated_doc_path` à l'import de `pedagogy.sources`.

Retirer du constructeur le paramètre `project_service: ProjectService` (et
`self._project_service = project_service` + la ligne Args du docstring) ; retirer
l'import `from fahmi2.app.project_service import ProjectService` s'il devient inutile.

Ajouter un helper :

```python
    def _resolve_content_language(
        self, output_dir: Path, target: Language, project: Project
    ) -> Language | None:
        """Choisit la langue du document de contenu pour une langue cible.

        Préfère le doc de la langue cible (meilleure fidélité), puis la langue
        source de la génération, puis la première langue produite disponible.

        Args:
            output_dir: Dossier des livrables de génération.
            target: Langue cible du support.
            project: Projet (pour la langue source de génération).

        Returns:
            La langue de contenu, ou ``None`` si aucun doc consolidé n'existe.
        """
        if consolidated_doc_path(output_dir, target).exists():
            return target
        source = project.generation.source_language if project.generation else None
        if source is not None and consolidated_doc_path(output_dir, source).exists():
            return source
        for language in Language:
            if consolidated_doc_path(output_dir, language).exists():
                return language
        return None
```

Dans `generate`, remplacer la résolution par langue :

```python
            for language in pedagogy.languages:
                source_mtime = source_mtime_ns(ctx.generation_output_dir, language)
                chapters = load_chapters(ctx.generation_output_dir, language)
                for support_type in self._registry.canonical_order():
```

par (la cible reste `language`, le contenu vient de `content_lang`) :

```python
            for language in pedagogy.languages:
                content_lang = self._resolve_content_language(
                    ctx.generation_output_dir, language, project
                )
                source_mtime = (
                    source_mtime_ns(ctx.generation_output_dir, content_lang)
                    if content_lang is not None
                    else None
                )
                chapters = (
                    load_chapters(ctx.generation_output_dir, content_lang)
                    if content_lang is not None
                    else ()
                )
                for support_type in self._registry.canonical_order():
```

(`_run_one` reçoit toujours `language=language` : la cible. `Path` est déjà importé.)

- [ ] **Step 6 : retirer `project_service` des instanciations**

`src/fahmi2/ui/pedagogy_controller.py` (~ligne 331) : retirer
`project_service=self._project_service,` de l'appel `SupportsOrchestrator(...)`
(garder `self._project_service` utilisé ailleurs par le controller).
`tests/unit/app/test_supports_orchestrator.py` `_build` et
`tests/unit/ui/test_pedagogy_controller.py` (~ligne 389) : retirer
`project_service=...` des appels `SupportsOrchestrator(...)` (garder la création de
`ProjectService` pour les projets dans `_build`).

- [ ] **Step 7 : `ruff --fix` + suite + mypy**

```powershell
.venv\Scripts\python.exe -m ruff check --fix .
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m mypy src tests
```
Attendu : tout vert.

- [ ] **Step 8 : commit**

```powershell
git add -A
git commit -m @'
feat(pedagogy): langues decouplees (#4) + retrait dependance morte

La pedagogie propose toutes les langues ; l'orchestrateur resout une langue de
contenu (doc consolide existant : cible, sinon source, sinon premiere produite)
distincte de la langue cible passee aux generateurs (qui produisent dans cette
langue). Retrait de project_service devenu mort dans SupportsOrchestrator.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
'@
```

---

## Task 3 : docs + CHANGELOG

- [ ] `CHANGELOG.md` (Non publié) : « Supprimé » (support flashcards_glossary) +
  « Modifié » (langues pédagogie découplées).
- [ ] `CLAUDE.md` et `docs/02-presentation-technique.md` : mentionner **8** types de
  supports (au lieu de 9), retrait de `flashcards_glossary`, langues pédagogie
  proposées indépendamment de la génération. `README.md` si nécessaire.
- [ ] Commit `docs(pedagogy): Lot 1c (retrait flashcards_glossary + langues)`.

## Clôture du Lot 1

- [ ] Lot 1 (1a + 1b + 1c) terminé. Les sous-chantiers #6 (workspaces versionnés) et
  #3 (dashboards) restent à concevoir séparément.

## Self-review

Couvre §4 du spec : retrait du support (Task 1, tous les points d'usage + tolérance
persistance), #4 langues découplées (Task 2, controller + orchestrateur + UI),
retrait `project_service` mort (différé du Lot 1b). Pas de placeholder : code exact
pour la production ; stratégie de swap mécanique précise pour les fixtures de tests +
code du stub no-LLM. Types cohérents (`_StubGen`, `_resolve_content_language`,
`_known_support_types`). Le glossaire reste lu (Lot 1b) pour l'injection LLM.
