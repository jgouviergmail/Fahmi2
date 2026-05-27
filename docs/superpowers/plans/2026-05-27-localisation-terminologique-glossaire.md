# Localisation terminologique du glossaire — plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (exécution inline imposée sur ce projet — pas de subagents ; repasses `pytest`/`ruff`/`mypy` obligatoires en fin de phase). Steps use checkbox (`- [ ]`) syntax.

**Goal:** Localiser les **termes** du glossaire dans chaque langue (traduits sauf international ; acronyme conservé) et propager cette terminologie à la Génération, aux Supports pédagogiques et au Dialogue, via un `cross_lang` peuplé en phase 6 et persisté dans `glossary_master.json`.

**Architecture:** En phase 6, pour chaque langue cible ≠ source, un appel LLM **structuré** (JSON) localise les termes + traduit leurs définitions. On en dérive `cross_lang_by_language` (en mémoire) qui (a) rend `glossary.{L}.md` de façon déterministe, (b) alimente l'indice « équivalents » de la traduction du consolidé/docs par source, et (c) est **persisté** dans `glossary_master.json`. Pédagogie et Dialogue **pré-localisent** le glossaire master (`localize_glossary_terms`) à la langue de contenu qu'ils chargent.

**Tech Stack:** Python 3.12, DeepSeek (LLM), Jinja2 (prompts), pytest/ruff/mypy.

**Spec :** `docs/superpowers/specs/2026-05-27-localisation-terminologique-glossaire-design.md`

---

## Structure des fichiers

| Fichier | Responsabilité | Action |
|---------|----------------|--------|
| `src/fahmi2/domain/glossary.py` | `glossary_term_for_language` + `localize_glossary_terms` | Modifier |
| `src/fahmi2/infra/prompts/defaults/phase_6_glossary_localization.j2` | Prompt de localisation structuré (JSON, DNT) | **Créer** |
| `src/fahmi2/infra/prompts/defaults/phase_6_translation.j2` | Clarifier : utiliser l'équivalent cible | Modifier |
| `src/fahmi2/app/prompts_service.py` | Entrée catalogue du nouveau prompt | Modifier |
| `src/fahmi2/pipeline/handlers/phase_6_translation.py` | Localisation + persistance `cross_lang` + flux 2 étapes | Modifier |
| `src/fahmi2/app/supports_orchestrator.py` | Pré-localiser le glossaire à `content_lang` | Modifier |
| `src/fahmi2/chat/corpus.py` | Pré-localiser le glossaire à la langue de corpus | Modifier |
| `CLAUDE.md` | Doc transverse (phase 6, glossaire, pédagogie, dialogue) | Modifier |

---

## Task 1 : Helpers domaine de localisation des termes

**Files:**
- Modify: `src/fahmi2/domain/glossary.py`
- Test: `tests/unit/domain/test_glossary.py`

- [ ] **Step 1: Écrire les tests qui échouent**

Ajouter dans `tests/unit/domain/test_glossary.py` :

```python
def test_glossary_term_for_language_uses_cross_lang_then_falls_back() -> None:
    from fahmi2.domain.glossary import glossary_term_for_language

    t = Term(term="Bilan", definition="...", cross_lang={Language.EN: "Balance sheet"})
    assert glossary_term_for_language(t, Language.EN) == "Balance sheet"
    # Pas d'entrée DE → repli sur le terme source.
    assert glossary_term_for_language(t, Language.DE) == "Bilan"


def test_localize_glossary_terms_replaces_surface_keeps_rest() -> None:
    from fahmi2.domain.glossary import localize_glossary_terms

    terms = (
        Term(term="Bilan", definition="def", acronym="B",
             cross_lang={Language.EN: "Balance sheet"}),
        Term(term="IFRS", definition="norme"),  # pas de cross_lang → inchangé
    )
    out = localize_glossary_terms(terms, Language.EN)
    assert out[0].term == "Balance sheet"
    assert out[0].definition == "def"      # définition inchangée (source)
    assert out[0].acronym == "B"           # acronyme conservé
    assert out[1].term == "IFRS"           # repli (pas d'équivalent)
```

- [ ] **Step 2: Lancer pour vérifier l'échec**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/domain/test_glossary.py -k "for_language or localize" -v`
Expected: FAIL (`ImportError` : noms absents)

- [ ] **Step 3: Implémenter**

Dans `src/fahmi2/domain/glossary.py`, ajouter l'import `replace` en tête (avec les
autres imports `dataclasses`) :

```python
from dataclasses import dataclass, field, replace
```

Puis ajouter après `glossary_title` (les deux fonctions de localisation) :

```python
def glossary_term_for_language(term: Term, language: Language) -> str:
    """Forme localisée d'un terme pour une langue (repli sur le terme source).

    Args:
        term: Terme du glossaire master.
        language: Langue cible.

    Returns:
        ``term.cross_lang[language]`` s'il existe, sinon ``term.term``.
    """
    return term.cross_lang.get(language, term.term)


def localize_glossary_terms(
    terms: Iterable[Term], language: Language
) -> tuple[Term, ...]:
    """Vue du glossaire pour une langue : remplace la forme du terme par sa
    localisation (``cross_lang[language]``), définition/acronyme/expansion inchangés.

    Args:
        terms: Termes du glossaire master.
        language: Langue de la vue voulue.

    Returns:
        Un tuple de ``Term`` dont seul ``term`` est localisé (repli sur la source).
    """
    return tuple(
        replace(t, term=glossary_term_for_language(t, language)) for t in terms
    )
```

- [ ] **Step 4: Lancer les tests**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/domain/test_glossary.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/fahmi2/domain/glossary.py tests/unit/domain/test_glossary.py
git commit -m "feat(domain): helpers de localisation des termes du glossaire (cross_lang)"
```

---

## Task 2 : Prompt de localisation structuré + catalogue

**Files:**
- Create: `src/fahmi2/infra/prompts/defaults/phase_6_glossary_localization.j2`
- Modify: `src/fahmi2/app/prompts_service.py`
- Test: `tests/unit/infra/prompts/test_prompts.py` (ou test catalogue existant)

- [ ] **Step 1: Créer le prompt**

Créer `src/fahmi2/infra/prompts/defaults/phase_6_glossary_localization.j2` :

```jinja
Tu es un expert en localisation terminologique. Pour chaque terme d'un glossaire
rédigé en {{ source_language_label }}, produis sa forme en {{ target_language_label }}.

Règles :
- **Traduis** le terme vers l'équivalent métier **consacré** en {{ target_language_label }}.
- **Garde le terme INCHANGÉ** s'il est international, un nom propre, une marque, le
  nom d'une norme, ou un terme habituellement employé tel quel par les professionnels
  en {{ target_language_label }} (ex. selon l'usage : IFRS, WACC, ROI, Big Four,
  Free Cash Flow). La décision se prend **terme par terme**.
- **Traduis la définition** en {{ target_language_label }}, registre {{ style_label }}.
- Ne touche PAS aux acronymes (non demandés ici).
{% if style_directives %}- Directives : {{ style_directives }}{% endif %}

Réponds avec **UNIQUEMENT** un tableau JSON, un objet par terme dans l'ordre fourni,
en **réémettant le terme source** (pour l'appariement) :

[{"source": "<terme source exact>", "term": "<terme en {{ target_language_label }} ou inchangé>", "definition": "<définition en {{ target_language_label }}>"}]

Termes à localiser :
{% for t in terms %}
- source: {{ t.term }}{% if t.acronym %} (acronyme : {{ t.acronym }}){% endif %}
  définition: {{ t.definition }}
{% endfor %}
```

- [ ] **Step 2: Écrire le test de présence catalogue (échoue)**

Le catalogue est le tuple module-level `_TEMPLATE_METADATA` (exposé par
`PromptLoader.list_templates()`). Créer/compléter `tests/unit/app/test_prompts_service.py` :

```python
def test_glossary_localization_prompt_in_catalog() -> None:
    from fahmi2.app.prompts_service import _TEMPLATE_METADATA

    assert "phase_6_glossary_localization" in {m.name for m in _TEMPLATE_METADATA}
```

> Le **rendu** du template est exercé en bout de chaîne par le test de `_localize_glossary`
> (Task 3, via `ctx.prompts.render`), inutile de le tester deux fois.

- [ ] **Step 3: Lancer pour vérifier l'échec**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/app/test_prompts_service.py -k "glossary_localization" -v`
Expected: FAIL (nom absent du catalogue)

- [ ] **Step 4: Enregistrer au catalogue**

Dans `src/fahmi2/app/prompts_service.py`, ajouter dans la liste des
`PromptTemplateMeta` (juste après l'entrée `name="phase_6_translation"`) :

```python
    PromptTemplateMeta(
        name="phase_6_glossary_localization",
        display_name="Phase 6 — Localisation du glossaire",
        description=(
            "Localise chaque terme du glossaire dans la langue cible (traduit "
            "l'équivalent métier consacré, garde les termes internationaux) et "
            "traduit les définitions. Sortie JSON."
        ),
    ),
```

- [ ] **Step 5: Lancer le test**

Run: `.venv\Scripts\python.exe -m pytest tests/ -k "glossary_localization_prompt" -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/fahmi2/infra/prompts/defaults/phase_6_glossary_localization.j2 src/fahmi2/app/prompts_service.py tests/
git commit -m "feat(prompts): prompt de localisation du glossaire (phase 6) + catalogue"
```

---

## Task 3 : Méthode `_localize_glossary` (appel LLM + parse + appariement)

**Files:**
- Modify: `src/fahmi2/pipeline/handlers/phase_6_translation.py`
- Test: `tests/unit/pipeline/handlers/test_phase_6_translation.py`

- [ ] **Step 1: Écrire le test qui échoue**

Ajouter dans `tests/unit/pipeline/handlers/test_phase_6_translation.py` :

```python
import json as _json

from fahmi2.infra.llm._fakes import FakeLLMProvider
from fahmi2.infra.llm.interface import LLMResponse


def _localization_response(entries: list[dict[str, str]]) -> LLMResponse:
    return LLMResponse(
        content=_json.dumps(entries, ensure_ascii=False),
        thinking_content=None, prompt_tokens=100, completion_tokens=100,
        cached_prompt_tokens=0, cost_usd=0.01,
    )


def test_localize_glossary_matches_by_source_and_falls_back(
    tmp_path: Path, make_generation_settings: Any
) -> None:
    payload = {"terms": [
        {"term": "Bilan", "definition": "doc comptable", "acronym": None},
        {"term": "IFRS", "definition": "norme", "acronym": "IFRS"},
    ]}
    # build_phase_context construit le FakeLLMProvider en interne avec ce llm_response.
    ctx, _run = build_phase_context(
        tmp_path,
        make_generation_settings,
        llm_response=_localization_response([
            {"source": "Bilan", "term": "Balance sheet", "definition": "accounting doc"},
            # "IFRS" manquant volontairement → repli attendu
        ]),
    )
    localized, cost = Phase6TranslationHandler()._localize_glossary(
        ctx, target=Language.EN, payload=payload
    )
    assert localized[0].term == "Balance sheet"
    assert localized[0].definition == "accounting doc"
    assert localized[1].term == "IFRS"          # repli (manquant dans la réponse)
    assert localized[1].definition == "norme"   # repli définition source
    assert cost == pytest.approx(0.01)
```

> `build_phase_context(tmp_path, make_generation_settings, *, llm_response=, sources=(),
> settings_overrides=)` renvoie `(ctx, run)` ; le helper et la fixture
> `make_generation_settings` (conftest) sont déjà disponibles.

- [ ] **Step 2: Lancer pour vérifier l'échec**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/pipeline/handlers/test_phase_6_translation.py -k "localize_glossary" -v`
Expected: FAIL (`_localize_glossary` n'existe pas)

- [ ] **Step 3: Implémenter `_localize_glossary` + un type de retour**

Dans `src/fahmi2/pipeline/handlers/phase_6_translation.py`, ajouter le template name
et le type d'entrée localisée près des constantes de module :

```python
_GLOSSARY_LOCALIZATION_TEMPLATE = "phase_6_glossary_localization"
```

Ajouter le dataclass de résultat (après `_TranslationTask`) :

```python
@dataclass(frozen=True)
class _LocalizedTerm:
    """Terme localisé : forme source (appariement), forme cible, définition cible."""

    source: str
    term: str
    definition: str
```

Ajouter l'import du parseur JSON (déjà disponible via `_base`) en complétant l'import :

```python
from fahmi2.pipeline.handlers._base import (
    build_succeeded_phase,
    invoke_llm,
    language_label,
    parse_json_response,
    style_label,
    utc_now,
)
```

Ajouter la méthode dans `Phase6TranslationHandler` :

```python
    def _localize_glossary(
        self,
        ctx: PhaseContext,
        *,
        target: Language,
        payload: dict[str, Any],
    ) -> tuple[list[_LocalizedTerm], float]:
        """Localise les termes du glossaire master vers ``target`` via le LLM.

        Args:
            ctx: Contexte d'exécution.
            target: Langue cible (≠ langue source).
            payload: Payload JSON du glossaire master.

        Returns:
            ``(localized, cost)`` : un ``_LocalizedTerm`` par terme master (ordre
            préservé ; repli sur la forme/définition source si l'entrée LLM manque),
            et le coût LLM.

        Raises:
            LLMError / ValidationError: via ``parse_json_response`` si JSON invalide.
        """
        master_terms = payload.get("terms", [])
        if not master_terms:
            return [], 0.0
        prompt = ctx.prompts.render(
            _GLOSSARY_LOCALIZATION_TEMPLATE,
            source_language_label=language_label(ctx.settings.source_language),
            target_language_label=language_label(target),
            style_label=style_label(ctx.settings.style_preset),
            style_directives=ctx.settings.style_directives,
            terms=[
                {
                    "term": str(t.get("term", "")),
                    "acronym": t.get("acronym"),
                    "definition": str(t.get("definition", "")),
                }
                for t in master_terms
            ],
        )
        response = invoke_llm(
            ctx, phase_id=self.phase_id, system_prompt=None, user_prompt=prompt
        )
        entries = parse_json_response(response.content, phase_id=self.phase_id)
        if not isinstance(entries, list):
            entries = []  # forme JSON inattendue → repli per-terme (termes source)
        by_source: dict[str, dict[str, Any]] = {
            str(e.get("source", "")): e for e in entries if isinstance(e, dict)
        }
        localized: list[_LocalizedTerm] = []
        for t in master_terms:
            source = str(t.get("term", ""))
            entry = by_source.get(source, {})
            localized.append(
                _LocalizedTerm(
                    source=source,
                    term=str(entry.get("term") or source),
                    definition=str(entry.get("definition") or t.get("definition", "")),
                )
            )
        return localized, response.cost_usd
```

- [ ] **Step 4: Lancer le test**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/pipeline/handlers/test_phase_6_translation.py -k "localize_glossary" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/fahmi2/pipeline/handlers/phase_6_translation.py tests/unit/pipeline/handlers/test_phase_6_translation.py
git commit -m "feat(pipeline): _localize_glossary (appel LLM structure + appariement par source)"
```

---

## Task 4 : Flux phase 6 — localisation, rendu déterministe, persistance `cross_lang`

**Files:**
- Modify: `src/fahmi2/pipeline/handlers/phase_6_translation.py`
- Test: `tests/unit/pipeline/handlers/test_phase_6_translation.py`

- [ ] **Step 1: Écrire le test de flux qui échoue**

Ajouter (le helper `_seed_workspace` existe déjà dans ce fichier) :

```python
def test_execute_localizes_glossary_and_persists_cross_lang(
    tmp_path: Path, make_generation_settings: Any
) -> None:
    video = SourceExecution(
        source_id=SourceId(value="s1"),
        source=InputSource(kind=SourceKind.VIDEO, location=str(tmp_path / "v.mp4")),
        status=PhaseStatus.PENDING,
    )
    ctx, _run = build_phase_context(
        tmp_path,
        make_generation_settings,
        llm_response=_localization_response([
            {"source": "Bilan", "term": "Balance sheet", "definition": "accounting doc"},
        ]),
        sources=(video,),
        settings_overrides={
            "output_languages": (Language.FR, Language.EN),
            "source_language": Language.FR,
        },
    )
    _seed_workspace(ctx.workspace, sources=(video,), glossary_terms=[
        {"term": "Bilan", "definition": "doc comptable"},
    ])
    Phase6TranslationHandler().execute(ctx, source=None)

    glossary_en = (ctx.output_dir / "glossary.en.md").read_text(encoding="utf-8")
    assert "Balance sheet" in glossary_en and "Bilan" not in glossary_en
    glossary_fr = (ctx.output_dir / "glossary.fr.md").read_text(encoding="utf-8")
    assert "Bilan" in glossary_fr  # source : terme conservé
    master = _json.loads(
        (ctx.workspace / "glossary_master.json").read_text(encoding="utf-8")
    )
    assert master["terms"][0]["cross_lang"]["en"] == "Balance sheet"
```

> `SourceExecution`/`InputSource`/`SourceId`/`SourceKind`/`PhaseStatus` sont déjà
> importés dans ce fichier de test ; vérifier les champs exacts de `SourceExecution`
> (le fichier en construit déjà). `_seed_workspace(workspace, ...)` écrit dans
> `ctx.workspace` (= `tmp_path/"workspace"`).

- [ ] **Step 2: Lancer pour vérifier l'échec**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/pipeline/handlers/test_phase_6_translation.py -k "persists_cross_lang" -v`
Expected: FAIL (glossaire EN contient encore « Bilan » ; pas de `cross_lang`)

- [ ] **Step 3: Helper de rendu déterministe du glossaire localisé**

Dans `phase_6_translation.py`, ajouter un helper qui construit les ``Term`` localisés
et délègue à `render_glossary_markdown_table` (import paresseux comme l'existant) :

```python
def _render_localized_glossary(
    localized: list[_LocalizedTerm], payload: dict[str, Any], language: Language
) -> str:
    """Rend ``glossary.{language}.md`` à partir des termes localisés.

    Termes/définitions localisés ; acronyme + ``acronym_expansion`` repris du master
    (invariants). Aligné par ordre sur ``payload['terms']``.
    """
    from fahmi2.domain.glossary import (  # noqa: PLC0415
        Term,
        render_glossary_markdown_table,
    )

    master = payload.get("terms", [])
    terms = [
        Term(
            term=loc.term,
            definition=loc.definition,
            acronym=str(raw["acronym"]) if raw.get("acronym") else None,
            acronym_expansion=(
                str(raw["acronym_expansion"]) if raw.get("acronym_expansion") else None
            ),
        )
        for loc, raw in zip(localized, master, strict=True)
    ]
    return render_glossary_markdown_table(language=language, terms=terms)
```

- [ ] **Step 4: Réorganiser `execute` (2 étapes + persistance)**

Remplacer le corps de `execute` après le chargement des masters par : (1) étape de
localisation par langue, rendu + écriture des glossaires, calcul de
`cross_lang_by_language` ; (2) persistance `cross_lang` ; (3) tâches de traduction
(per-source + consolidé) en parallèle avec l'indice par langue.

Remplacer la boucle existante `for target in ... : self._collect_for_language(...)`
+ `map_bounded(...)` + `return build_succeeded_phase(...)` par (localisation
**parallélisée** par langue, puis rendu/persistance séquentiels, puis traductions
parallélisées) :

```python
        # Étape 1 — localisation parallèle des glossaires (1 appel LLM par langue
        # cible ≠ source). map_bounded préserve l'ordre et honore le pause_token.
        non_source_targets = [
            t for t in ctx.settings.output_languages
            if t is not ctx.settings.source_language
        ]
        localization_results = map_bounded(
            lambda target: (target, *self._localize_glossary(
                ctx, target=target, payload=glossary_master
            )),
            non_source_targets,
            max_workers=ctx.settings.parallelism.llm_workers,
            pause_token=ctx.pause_token,
        )
        cross_lang_by_language: dict[Language, dict[str, str]] = {}
        localization_cost = 0.0
        for target, localized, cost in localization_results:
            localization_cost += cost
            cross_lang_by_language[target] = {loc.source: loc.term for loc in localized}
            ctx.artifacts.write_text_atomic(
                ctx.output_dir / glossary_doc_filename(target),
                _render_localized_glossary(localized, glossary_master, target),
            )
        # Glossaire de la langue source (si produite) : rendu master, aucun appel LLM.
        if ctx.settings.source_language in ctx.settings.output_languages:
            ctx.artifacts.write_text_atomic(
                ctx.output_dir / glossary_doc_filename(ctx.settings.source_language),
                _render_master_glossary(glossary_master, ctx.settings.source_language),
            )
        _persist_cross_lang(ctx, glossary_master, cross_lang_by_language)

        # Étape 2 — traductions documentaires (per-source + consolidé) en parallèle.
        tasks: list[_TranslationTask] = []
        for target in ctx.settings.output_languages:
            self._collect_doc_tasks(
                ctx,
                target=target,
                consolidated_master_md=consolidated_master,
                per_source_structured=per_source_structured,
                tasks=tasks,
            )
        costs = map_bounded(
            lambda task: self._run_translation(ctx, task, cross_lang_by_language),
            tasks,
            max_workers=ctx.settings.parallelism.llm_workers,
            pause_token=ctx.pause_token,
        )
        return build_succeeded_phase(
            phase_id=self.phase_id,
            artifact_path=ctx.output_dir,
            started_at=started_at,
            cost_usd=localization_cost + sum(costs),
        )
```

Renommer/raccourcir `_collect_for_language` en `_collect_doc_tasks` : **retirer** le
bloc glossaire (désormais traité ci-dessus), garder per-source + consolidé :

```python
    def _collect_doc_tasks(
        self,
        ctx: PhaseContext,
        *,
        target: Language,
        consolidated_master_md: str,
        per_source_structured: dict[str, str],
        tasks: list[_TranslationTask],
    ) -> None:
        """Écrit les copies (langue source) et empile les traductions (per-source +
        consolidé) pour les autres langues. Le glossaire est traité en amont."""
        is_source = target is ctx.settings.source_language
        for source_id, structured_md in per_source_structured.items():
            target_path = (
                ctx.output_dir / _PER_VIDEO_OUTPUT_SUBDIR / target.value / f"{source_id}.md"
            )
            if is_source:
                ctx.artifacts.write_text_atomic(target_path, structured_md)
            else:
                tasks.append(_TranslationTask(structured_md, target, target_path))
        consolidated_target = ctx.output_dir / consolidated_doc_filename(target)
        if is_source:
            ctx.artifacts.write_text_atomic(consolidated_target, consolidated_master_md)
        else:
            tasks.append(
                _TranslationTask(consolidated_master_md, target, consolidated_target)
            )
```

Ajouter le rendu du glossaire **source** (master) et la persistance :

```python
def _render_master_glossary(payload: dict[str, Any], language: Language) -> str:
    """Rend le glossaire master tel quel (langue source) en Markdown."""
    from fahmi2.domain.glossary import (  # noqa: PLC0415
        parse_glossary_master_terms,
        render_glossary_markdown_table,
    )

    return render_glossary_markdown_table(
        language=language, terms=parse_glossary_master_terms(payload)
    )


def _persist_cross_lang(
    ctx: PhaseContext,
    payload: dict[str, Any],
    cross_lang_by_language: dict[Language, dict[str, str]],
) -> None:
    """Réécrit ``glossary_master.json`` en ajoutant ``cross_lang`` à chaque terme.

    Écriture atomique. Clés = codes langue (round-trip ``parse_glossary_master_terms``).
    """
    for raw in payload.get("terms", []):
        source = str(raw.get("term", ""))
        raw["cross_lang"] = {
            lang.value: mapping[source]
            for lang, mapping in cross_lang_by_language.items()
            if source in mapping
        }
    ctx.artifacts.write_json_atomic(
        ctx.workspace / _GLOSSARY_MASTER_FILENAME, payload
    )
```

Mettre à jour `_run_translation` + `_translate` pour recevoir
`cross_lang_by_language` (au lieu de `glossary_master_payload`) et l'utiliser dans
`_glossary_terms_for_template` :

```python
    def _run_translation(
        self, ctx: PhaseContext, task: _TranslationTask,
        cross_lang_by_language: dict[Language, dict[str, str]],
    ) -> float:
        translated, cost = self._translate(
            ctx, task.source_markdown, task.target, cross_lang_by_language
        )
        ctx.artifacts.write_text_atomic(task.target_path, translated)
        return cost
```

Dans `_translate`, remplacer l'argument `glossary_master_payload` par
`cross_lang_by_language` et l'appel :

```python
            glossary_terms=_glossary_terms_for_template(
                cross_lang_by_language.get(target, {})
            ),
```

Remplacer `_glossary_terms_for_template` :

```python
def _glossary_terms_for_template(
    cross_lang: dict[str, str]
) -> list[dict[str, str]]:
    """Construit la liste ``[{source, target}]`` injectée dans le prompt de
    traduction depuis le mapping ``terme_source -> terme_localisé`` d'une langue."""
    return [{"source": s, "target": t} for s, t in cross_lang.items()]
```

Supprimer l'ancienne `_render_glossary_md` (remplacée par `_render_master_glossary`
et `_render_localized_glossary`).

- [ ] **Step 5: Lancer le test de flux + les tests phase 6 existants**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/pipeline/handlers/test_phase_6_translation.py -v`
Expected: PASS (mettre à jour les tests existants qui s'appuyaient sur la traduction
de la table glossaire ou sur l'ancienne signature de `_glossary_terms_for_template` /
`_render_glossary_md`).

- [ ] **Step 6: Commit**

```bash
git add src/fahmi2/pipeline/handlers/phase_6_translation.py tests/unit/pipeline/handlers/test_phase_6_translation.py
git commit -m "feat(pipeline): phase 6 localise le glossaire + persiste cross_lang (flux 2 etapes)"
```

---

## Task 5 : Clarifier le prompt de traduction (utiliser l'équivalent cible)

**Files:**
- Modify: `src/fahmi2/infra/prompts/defaults/phase_6_translation.j2`

- [ ] **Step 1: Modifier la consigne**

Dans `phase_6_translation.j2`, remplacer la ligne d'instruction sur les termes :

```
- Respectant l'orthographe et le sens des termes du glossaire ci-dessous
```

par :

```
- **Utilisant systématiquement l'équivalent cible indiqué** pour chaque terme du
  glossaire ci-dessous (rends le terme avec l'équivalent de droite, pas la forme source)
```

- [ ] **Step 2: Vérifier le rendu + suite phase 6**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/pipeline -q`
Expected: PASS (le rendu du template ne casse aucun test ; pas de variable nouvelle).

- [ ] **Step 3: Commit**

```bash
git add src/fahmi2/infra/prompts/defaults/phase_6_translation.j2
git commit -m "feat(prompts): traduction utilise l'equivalent cible du glossaire"
```

---

## Task 6 : Propagation Pédagogie (pré-localisation à `content_lang`)

**Files:**
- Modify: `src/fahmi2/app/supports_orchestrator.py`
- Test: `tests/unit/app/test_supports_orchestrator.py` (ou test pédagogie sources)

- [ ] **Step 1: Écrire le test qui échoue**

Ajouter un test vérifiant que le glossaire passé au générateur est localisé à la
langue de contenu. Le plus simple : tester que l'orchestrateur stocke `content_lang`
et pré-localise. Si un test d'intégration est trop lourd, tester le helper
d'orchestration extrait. **Test ciblé** (vérifie la localisation en bout de chaîne
via un faux générateur capturant son `glossary`) — sinon, asserter sur les artefacts.
Exemple minimal d'assertion d'unité sur la pré-localisation :

```python
def test_orchestrator_prelocalizes_glossary_to_content_language() -> None:
    from fahmi2.domain.enums import Language
    from fahmi2.domain.glossary import Term, localize_glossary_terms

    glossary = (Term(term="Bilan", definition="d",
                     cross_lang={Language.EN: "Balance sheet"}),)
    # Contrat attendu : on injecte localize_glossary_terms(glossary, content_lang)
    localized = localize_glossary_terms(glossary, Language.EN)
    assert localized[0].term == "Balance sheet"
```

> Ce test verrouille le **contrat** (le helper domaine). L'assertion d'intégration
> réelle (le générateur reçoit le glossaire localisé) se fait via les tests
> d'orchestrateur existants : adapter pour vérifier que `_run_one` reçoit un glossaire
> dont les termes sont localisés à `content_lang` (capturer l'argument).

- [ ] **Step 2: Conserver `content_lang` + pré-localiser**

Dans `supports_orchestrator.py`, importer le helper :

```python
from fahmi2.domain.glossary import Term, localize_glossary_terms
```

Modifier la construction de `per_language` pour **mémoriser `content_lang`** :

```python
        per_language: dict[
            Language, tuple[Language | None, int | None, tuple[Chapter, ...]]
        ] = {}
        for language in pedagogy.languages:
            content_lang = resolve_content_language(
                ctx.generation_output_dir, language, source_language
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
            per_language[language] = (content_lang, source_mtime, chapters)
```

Dans `_run_task`, déplier `content_lang` et passer un glossaire **pré-localisé** à
`_run_one` :

```python
            content_lang, source_mtime, chapters = per_language[language]
            localized_glossary = (
                localize_glossary_terms(glossary, content_lang)
                if content_lang is not None
                else glossary
            )
            cost, failed = self._run_one(
                ctx,
                manifest=manifest,
                manifest_lock=manifest_lock,
                support_type=support_type,
                language=language,
                chapters=chapters,
                glossary=localized_glossary,
                settings_hash=settings_hash,
                source_mtime_ns=source_mtime,
                regenerate=regenerate,
            )
```

(Les générateurs et `format_glossary_terms` restent inchangés : ils reçoivent un
glossaire déjà localisé.)

- [ ] **Step 3: Lancer les tests pédagogie**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/app/test_supports_orchestrator.py tests/unit/pedagogy -q`
Expected: PASS (adapter les tests qui dépaquetaient `per_language` en 2-uplets).

- [ ] **Step 4: Commit**

```bash
git add src/fahmi2/app/supports_orchestrator.py tests/
git commit -m "feat(pedagogie): glossaire pre-localise a la langue de contenu (cross_lang)"
```

---

## Task 7 : Propagation Dialogue (pré-localisation du corpus glossaire)

**Files:**
- Modify: `src/fahmi2/chat/corpus.py`
- Test: `tests/unit/chat/test_corpus.py`

- [ ] **Step 1: Écrire le test qui échoue**

Ajouter dans `tests/unit/chat/test_corpus.py` un test : un `glossary_master.json` avec
`cross_lang` → les chunks de glossaire d'un corpus EN utilisent le terme localisé.

```python
def test_corpus_glossary_chunks_use_localized_term(tmp_path: Path) -> None:
    # seed consolidated.en.md minimal + glossary_master.json avec cross_lang
    output_dir = tmp_path / "output"; output_dir.mkdir()
    (output_dir / "consolidated.en.md").write_text("# Cours\n\n## Intro\n\nx\n", encoding="utf-8")
    (tmp_path / "glossary_master.json").write_text(_json.dumps({"terms": [
        {"term": "Bilan", "definition": "doc", "cross_lang": {"en": "Balance sheet"}}
    ]}, ensure_ascii=False), encoding="utf-8")
    chunks = load_corpus_chunks(
        generation_output_dir=output_dir, generation_dir=tmp_path, language=Language.EN
    )
    glossary_chunks = [c for c in chunks if c.origin == "glossary"]
    assert any("Balance sheet" in c.text for c in glossary_chunks)
    assert not any("Bilan" in c.text for c in glossary_chunks)
```

- [ ] **Step 2: Lancer pour vérifier l'échec**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/chat/test_corpus.py -k "localized_term" -v`
Expected: FAIL (chunk contient « Bilan »)

- [ ] **Step 3: Pré-localiser dans `load_corpus_chunks`**

Dans `src/fahmi2/chat/corpus.py`, importer le helper et pré-localiser :

```python
from fahmi2.domain.glossary import Term, localize_glossary_terms
```

Modifier `load_corpus_chunks` :

```python
    chunks.extend(
        _glossary_chunks(
            localize_glossary_terms(load_glossary_master_terms(generation_dir), language)
        )
    )
```

(`_glossary_chunks` reste inchangé : il reçoit des termes déjà localisés.)

- [ ] **Step 4: Lancer les tests Dialogue**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/chat/test_corpus.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/fahmi2/chat/corpus.py tests/unit/chat/test_corpus.py
git commit -m "feat(dialogue): chunks de glossaire pre-localises a la langue du corpus"
```

---

## Task 8 : Documentation + vérifications finales

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Mettre à jour `CLAUDE.md`**

- Section pipeline / phase 6 : la phase 6 **localise les termes du glossaire** (appel
  LLM structuré, politique DNT par langue), persiste `cross_lang` dans
  `glossary_master.json`, et le glossaire **n'est plus une `_TranslationTask`** (rendu
  déterministe).
- Mécanismes transverses : ajouter une puce **Localisation terminologique** —
  `domain/glossary.localize_glossary_terms` (source unique) ; Pédagogie
  (`SupportsOrchestrator`) et Dialogue (`corpus.load_corpus_chunks`) pré-localisent le
  glossaire à la **langue de contenu** qu'ils chargent ; définitions en aval restent
  en langue source (limite assumée).

- [ ] **Step 2: Vérifier l'impact `CostEstimator` (phase 6)**

Inspecter `src/fahmi2/app/cost_estimator.py` (et `tests/unit/app/test_cost_estimator.py`)
pour la phase 6. La localisation **remplace** l'ancienne traduction de la table
glossaire (1 appel/langue, ordre de grandeur similaire) → aucun ajustement attendu si
l'estimateur ne **détaille pas** le glossaire séparément. S'il l'itémise (peu probable),
ajuster pour refléter l'appel de localisation. Documenter le constat ; ne modifier que
si nécessaire (sinon, laisser tel quel et noter « impact négligeable, vérifié »).

- [ ] **Step 3: Suite complète**

Run: `.venv\Scripts\python.exe -m pytest`
Expected: tous verts.

- [ ] **Step 4: Lint + typage**

Run: `.venv\Scripts\python.exe -m ruff check .`
Run: `.venv\Scripts\python.exe -m mypy src tests`
Expected: `All checks passed!` / `Success`.

- [ ] **Step 5: Repasser si nécessaire** jusqu'à zéro défaut.

- [ ] **Step 6: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: localisation terminologique du glossaire (phase 6, pedagogie, dialogue)"
```

---

## Self-review (couverture du spec)

- §2 politique DNT → Task 2 (prompt) ✓
- §3 principe unificateur (`cross_lang[L]`, L = langue de contenu) → Tasks 4/6/7 ✓
- §4 mécanisme phase 6 (localisation structurée, 2 étapes, persistance) → Tasks 3/4 ✓
- §4.2 sortie JSON + appariement par `source` + repli → Task 3 ✓
- §5 propagation (eager, producteur) → Tasks 1/6/7 ✓
- §5.1 limite définitions en aval → assumée (Tasks 6/7 ne localisent que le terme) ✓
- §6 fraîcheur → persistance pendant la génération (Task 4) ✓
- §7 migration → repli sur terme source (helper Task 1) ✓
- §9 composants → couverts ✓
- §10 tests → Tasks 1-7 ✓ ; §11 doc → Task 8 ✓
