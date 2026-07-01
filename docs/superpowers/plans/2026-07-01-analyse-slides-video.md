# Analyse des slides dans les vidéos — Plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans
> to implement this plan task-by-task (préférence utilisateur : exécution
> **inline**, pas de subagents). Steps use checkbox (`- [ ]`) syntax for
> tracking.

**Objectif :** option par source vidéo/YouTube qui extrait le contenu des
slides (texte + description des visuels) via un modèle vision OpenAI et
l'intercale, horodaté, dans la `Transcription` de phase 0.

**Architecture :** échantillonnage ffmpeg → hachage perceptuel par tuiles
(2 passes : masque de bruit + région dynamique, double seuil sur la fraction
de région changée) → 1 image « état final » par slide → analyse vision
parallélisée (`map_bounded`) → fusion en segments horodatés. Ports/adapters
(`infra/vision/` miroir d'`infra/embeddings/`), option persistée pattern
`excluded_sources`, coût estimé + réel attribué à la phase 0.

**Spec :** `docs/superpowers/specs/2026-07-01-analyse-slides-video-design.md`

**Stack :** Python 3.12, PySide6, Pillow (déjà dépendance), openai SDK (déjà
dépendance), ffmpeg bundlé, pytest / ruff / mypy --strict.

## Contraintes globales

- **Tout en français dans le code** : commentaires, docstrings, messages
  utilisateur, logs, messages de commit — orthographe parfaite avec accents.
- **Google Python Style Guide** : docstrings `Args`/`Returns`/`Raises`,
  docstring de module sur chaque fichier.
- **Aucun nombre/chaîne magique** : tout en constantes de module.
- Entités domaine immuables `@dataclass(frozen=True)`.
- Vérification systématique en fin de tâche : la suite ciblée de la tâche,
  puis en fin de plan `pytest` + `ruff check .` + `mypy src tests` **tous
  propres** (répéter jusqu'à zéro défaut).
- Interpréteur : `.venv\Scripts\python.exe` (jamais `python` nu).
- Migration *lenient* du blob settings v2 : champ absent = défaut.
- Repasse qualité obligatoire en fin de plan (préférence utilisateur).

## Structure de fichiers (vue d'ensemble)

| Fichier | Rôle | Tâche |
|---|---|---|
| `src/fahmi2/domain/enums.py` | + enum `VisionModel` | 1 |
| `src/fahmi2/domain/generation.py` | + `slides_sources`, `vision_model` | 1 |
| `src/fahmi2/infra/storage/sqlite_state.py` | sérialisation des 2 champs | 1 |
| `src/fahmi2/core/errors/exceptions.py` | + `VisionError` | 2 |
| `src/fahmi2/infra/vision/interface.py` | port + `SlideContent`/`SlideAnalysis`/`AnalyzedSlide` | 2 |
| `src/fahmi2/infra/vision/_pricing.py` | tarifs + estimation par slide | 2 |
| `src/fahmi2/infra/vision/_fakes.py` | `FakeVisionProvider` | 2 |
| `src/fahmi2/infra/prompts/defaults/phase_0_slide_analysis.j2` | prompt vision | 3 |
| `src/fahmi2/app/prompts_service.py` | entrée catalogue | 3 |
| `src/fahmi2/infra/vision/openai_vision.py` | `OpenAIVisionAdapter` | 3 |
| `src/fahmi2/infra/video/_constants.py` | toutes les constantes détection | 4 |
| `src/fahmi2/infra/video/tiles.py` | dHash par tuiles (pur) | 4 |
| `src/fahmi2/infra/video/grouping.py` | regroupement 2 passes (pur) | 4 |
| `src/fahmi2/infra/video/frame_extractor.py` | `SlideFrameExtractor` (ffmpeg) | 5 |
| `src/fahmi2/infra/ingestion/slide_merge.py` | fusion horodatée (pur) | 6 |
| `src/fahmi2/infra/vision/slide_analyzer.py` | façade `SlideAnalyzer` | 7 |
| `src/fahmi2/infra/ingestion/*` | protocole + ingesteurs + dispatcher | 8 |
| `src/fahmi2/pipeline/{events,phase_handler}.py`, `handlers/phase_0_stt.py` | flag per-source + coût + événement | 9 |
| `src/fahmi2/ui/generation_controller.py` | DI + validation clé + log | 9, 10 |
| `src/fahmi2/app/{_cost_common,cost_estimator}.py` | poste vision | 10 |
| `src/fahmi2/ui/widgets/source_order_view.py` | cases « slides » | 11 |
| `src/fahmi2/ui/_model_labels.py`, `ui/dialogs/generation_settings_view.py` | combo modèle vision + persistance | 11 |
| `src/fahmi2/i18n/translations/fahmi2_en.ts` (+ compiled) | traductions EN | 12 |
| `CLAUDE.md`, `README.md`, `packaging/README.md` | docs | 13 |

---

### Tâche 1 : Domaine — `VisionModel` + champs `GenerationSettings` + sérialisation

**Files:**
- Modify: `src/fahmi2/domain/enums.py` (après `EmbeddingModel`, ~ligne 138)
- Modify: `src/fahmi2/domain/generation.py` (champs + docstring)
- Modify: `src/fahmi2/infra/storage/sqlite_state.py` (~lignes 180 et 250)
- Test: `tests/unit/infra/storage/test_sqlite_state.py`

**Interfaces:**
- Produces: `VisionModel { GPT_5_MINI="gpt-5-mini", GPT_5_NANO="gpt-5-nano",
  GPT_5_4_MINI="gpt-5.4-mini" }` ; `GenerationSettings.slides_sources:
  tuple[str, ...]` (clés `InputSource.order_key()`) ;
  `GenerationSettings.vision_model: VisionModel`.

- [ ] **Étape 1 : test d'aller-retour de sérialisation (échec attendu)**

Dans `tests/unit/infra/storage/test_sqlite_state.py`, ajouter (imports :
`VisionModel` depuis `fahmi2.domain.enums`, `_serialize_generation_settings`
/ `_deserialize_generation_settings` depuis
`fahmi2.infra.storage.sqlite_state` — suivre le style des tests existants
du fichier) :

```python
def test_settings_roundtrip_slides_fields(make_generation_settings) -> None:
    """slides_sources et vision_model survivent à l'aller-retour JSON."""
    settings = make_generation_settings(
        slides_sources=("cours1.mp4", "https://youtu.be/xyz"),
        vision_model=VisionModel.GPT_5_NANO,
    )
    payload = _serialize_generation_settings(settings)
    restored = _deserialize_generation_settings(payload)
    assert restored.slides_sources == ("cours1.mp4", "https://youtu.be/xyz")
    assert restored.vision_model is VisionModel.GPT_5_NANO


def test_settings_lenient_defaults_slides_fields(make_generation_settings) -> None:
    """Blob v2 antérieur (champs absents) : défauts appliqués (migration lenient)."""
    payload = _serialize_generation_settings(make_generation_settings())
    payload.pop("slides_sources")
    payload.pop("vision_model")
    restored = _deserialize_generation_settings(payload)
    assert restored.slides_sources == ()
    assert restored.vision_model is VisionModel.GPT_5_MINI
```

- [ ] **Étape 2 : vérifier l'échec**

Run : `.venv\Scripts\python.exe -m pytest tests/unit/infra/storage/test_sqlite_state.py -k slides -v`
Attendu : FAIL (`ImportError: cannot import name 'VisionModel'`).

- [ ] **Étape 3 : implémenter**

`domain/enums.py`, après `EmbeddingModel` :

```python
class VisionModel(StrEnum):
    """Modèles vision OpenAI supportés (analyse des slides des vidéos).

    Utilisés quand l'option « analyser les slides » est activée sur une
    source vidéo/YouTube (phase 0) : lecture fidèle du texte des slides +
    description des éléments visuels. Le défaut privilégie le rapport
    qualité/prix (tarifs vérifiés 2026-07).
    """

    GPT_5_MINI = "gpt-5-mini"      # défaut : meilleur rapport qualité/prix
    GPT_5_NANO = "gpt-5-nano"      # économique (slides textuelles simples)
    GPT_5_4_MINI = "gpt-5.4-mini"  # qualité supérieure (slides très denses)
```

`domain/generation.py` — importer `VisionModel`, ajouter après
`excluded_sources` (champ + docstring de classe) :

```python
    slides_sources: tuple[str, ...] = ()
    vision_model: VisionModel = VisionModel.GPT_5_MINI
```

Docstring (dans la section `Attributes`) :

```text
        slides_sources: Clés stables (``InputSource.order_key()``) des sources
            vidéo/YouTube dont l'analyse des slides est activée (contenu des
            slides intercalé dans la transcription, phase 0). Réconciliées au
            scan comme ``excluded_sources`` (clés obsolètes ignorées).
        vision_model: Modèle vision OpenAI utilisé pour lire les slides.
```

`infra/storage/sqlite_state.py` — importer `VisionModel` ; dans
`_serialize_generation_settings` (après `"excluded_sources"`) :

```python
        "slides_sources": list(gen.slides_sources),
        "vision_model": str(gen.vision_model),
```

Dans `_deserialize_generation_settings` (après `excluded_sources=...`) :

```python
        slides_sources=tuple(payload.get("slides_sources", [])),
        vision_model=VisionModel(
            payload.get("vision_model", VisionModel.GPT_5_MINI)
        ),
```

- [ ] **Étape 4 : vérifier le succès**

Run : `.venv\Scripts\python.exe -m pytest tests/unit/infra/storage/test_sqlite_state.py tests/unit/domain -v`
Attendu : PASS (tous).

- [ ] **Étape 5 : commit**

```bash
git add -A && git commit -m "feat(domaine): enum VisionModel + slides_sources/vision_model dans GenerationSettings (sérialisation lenient)"
```

---

### Tâche 2 : Port vision — `VisionError`, `interface.py`, `_pricing.py`, `_fakes.py`

**Files:**
- Modify: `src/fahmi2/core/errors/exceptions.py` (après `EmbeddingError`, ~ligne 74)
- Create: `src/fahmi2/infra/vision/__init__.py`
- Create: `src/fahmi2/infra/vision/interface.py`
- Create: `src/fahmi2/infra/vision/_pricing.py`
- Create: `src/fahmi2/infra/vision/_fakes.py`
- Test: `tests/unit/infra/vision/__init__.py` (vide) + `tests/unit/infra/vision/test_pricing.py`

**Interfaces:**
- Produces: `SlideContent(text, visuals_description)` + `.is_empty()` ;
  `SlideAnalysis(content: SlideContent, cost_usd: float)` ;
  `AnalyzedSlide(start_seconds: float, end_seconds: float, content: SlideContent)` ;
  protocole `SlideVisionProvider.analyze_slide(image_path: Path, *, language:
  Language) -> SlideAnalysis` ; `vision_cost_usd(*, model, input_tokens,
  output_tokens) -> float` ; `estimated_cost_per_slide_usd(model: str) -> float` ;
  `FakeVisionProvider`.
- Note vs spec : le port ne porte **pas** `consumed_cost_usd()` global —
  chaque `analyze_slide` renvoie son coût (`SlideAnalysis.cost_usd`), seule
  forme fiable pour l'**attribution per-source** quand plusieurs sources
  tournent en parallèle (le cumul global serait racé).

- [ ] **Étape 1 : test du pricing (échec attendu)**

`tests/unit/infra/vision/test_pricing.py` :

```python
"""Tests de la grille tarifaire vision (USD/token + estimation par slide)."""

from fahmi2.infra.vision._pricing import (
    ESTIMATED_INPUT_TOKENS_PER_SLIDE,
    ESTIMATED_OUTPUT_TOKENS_PER_SLIDE,
    estimated_cost_per_slide_usd,
    vision_cost_usd,
)


def test_vision_cost_usd_gpt5_mini() -> None:
    """1M tokens entrée + 1M sortie au tarif gpt-5-mini."""
    cost = vision_cost_usd(
        model="gpt-5-mini", input_tokens=1_000_000, output_tokens=1_000_000
    )
    assert cost == 0.25 + 2.00


def test_vision_cost_usd_zero_tokens() -> None:
    assert vision_cost_usd(model="gpt-5-mini", input_tokens=0, output_tokens=0) == 0.0


def test_vision_cost_usd_unknown_model_falls_back() -> None:
    """Modèle inconnu : retombe sur le tarif par défaut (pas d'exception)."""
    assert vision_cost_usd(
        model="gpt-9-futur", input_tokens=1_000_000, output_tokens=0
    ) == 0.25


def test_estimated_cost_per_slide_consistent() -> None:
    """L'estimation par slide découle des tokens estimés et de la grille."""
    expected = vision_cost_usd(
        model="gpt-5-mini",
        input_tokens=ESTIMATED_INPUT_TOKENS_PER_SLIDE,
        output_tokens=ESTIMATED_OUTPUT_TOKENS_PER_SLIDE,
    )
    assert estimated_cost_per_slide_usd("gpt-5-mini") == expected
```

- [ ] **Étape 2 : vérifier l'échec** — Run :
`.venv\Scripts\python.exe -m pytest tests/unit/infra/vision -v` → FAIL (module absent).

- [ ] **Étape 3 : implémenter**

`core/errors/exceptions.py`, après `EmbeddingError` :

```python
class VisionError(Fahmi2Error):
    """Erreur du sous-système vision (analyse des slides des vidéos)."""
```

`infra/vision/__init__.py` :

```python
"""Sous-système vision : analyse du contenu des slides extraites des vidéos."""
```

`infra/vision/interface.py` :

```python
"""Port ``SlideVisionProvider`` et types associés.

Contrat du fournisseur d'analyse vision de slides (adapter OpenAI en
production, fake déterministe en tests) et structures immuables échangées
avec l'ingestion : contenu extrait d'une slide, résultat d'appel (contenu +
coût), slide analysée horodatée.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from fahmi2.domain.enums import Language


@dataclass(frozen=True)
class SlideContent:
    """Contenu extrait d'une slide par le modèle vision.

    Attributes:
        text: Transcription fidèle du texte visible (vide si aucun).
        visuals_description: Description synthétique des éléments visuels
            porteurs de sens (vide si aucun).
    """

    text: str
    visuals_description: str

    def is_empty(self) -> bool:
        """``True`` si la slide n'a produit aucun contenu exploitable.

        Returns:
            ``True`` quand texte et description sont vides (frame sans slide).
        """
        return not self.text.strip() and not self.visuals_description.strip()


@dataclass(frozen=True)
class SlideAnalysis:
    """Résultat d'un appel vision sur une image de slide.

    Attributes:
        content: Contenu extrait.
        cost_usd: Coût réel de l'appel (USD) — porté par appel pour permettre
            l'attribution per-source sous parallélisme.
    """

    content: SlideContent
    cost_usd: float


@dataclass(frozen=True)
class AnalyzedSlide:
    """Une slide analysée, horodatée sur sa plage d'affichage dans la vidéo.

    Attributes:
        start_seconds: Début d'affichage de la slide (s).
        end_seconds: Fin d'affichage (s, >= start_seconds).
        content: Contenu extrait par le modèle vision.
    """

    start_seconds: float
    end_seconds: float
    content: SlideContent


class SlideVisionProvider(Protocol):
    """Contrat d'un fournisseur d'analyse vision de slides."""

    def analyze_slide(
        self, image_path: Path, *, language: Language
    ) -> SlideAnalysis:
        """Analyse l'image d'une slide (texte fidèle + description des visuels).

        Args:
            image_path: Image JPEG/PNG de la frame représentative de la slide.
            language: Langue de sortie (langue détectée par le STT — le
                transcript fusionné reste monolingue).

        Returns:
            Le ``SlideAnalysis`` (contenu, éventuellement vide, + coût USD).

        Raises:
            VisionError: En cas d'échec d'appel (auth, rate-limit, API).
        """
```

`infra/vision/_pricing.py` (miroir d'`infra/embeddings/_pricing.py`) :

```python
"""Tarifs des modèles vision (USD par million de tokens) + estimation par slide.

Grille **extensible** : ajouter un modèle = une entrée par dict. Un modèle
inconnu retombe sur le tarif par défaut (celui de ``gpt-5-mini``) plutôt que
de lever — un nouveau modèle non encore tarifé ne casse pas le calcul.
Tarifs vérifiés en 2026-07 (https://developers.openai.com/api/docs/pricing).
"""

from __future__ import annotations

_TOKENS_PER_MILLION = 1_000_000

#: USD / million de tokens d'entrée, par identifiant de modèle vision.
_USD_PER_MILLION_INPUT_TOKENS: dict[str, float] = {
    "gpt-5-mini": 0.25,
    "gpt-5-nano": 0.05,
    "gpt-5.4-mini": 0.75,
}
#: USD / million de tokens de sortie, par identifiant de modèle vision.
_USD_PER_MILLION_OUTPUT_TOKENS: dict[str, float] = {
    "gpt-5-mini": 2.00,
    "gpt-5-nano": 0.40,
    "gpt-5.4-mini": 4.50,
}
_DEFAULT_USD_PER_MILLION_INPUT = 0.25
_DEFAULT_USD_PER_MILLION_OUTPUT = 2.00

#: Tokens d'entrée estimés par slide (image ~1280 px encodée en patches +
#: prompt d'analyse) — pour l'estimation pré-run.
ESTIMATED_INPUT_TOKENS_PER_SLIDE = 1_800
#: Tokens de sortie estimés par slide (texte transcrit + description).
ESTIMATED_OUTPUT_TOKENS_PER_SLIDE = 350


def vision_cost_usd(*, model: str, input_tokens: int, output_tokens: int) -> float:
    """Calcule le coût USD d'un appel vision.

    Args:
        model: Identifiant du modèle vision.
        input_tokens: Tokens d'entrée facturés (champ ``usage`` de l'API).
        output_tokens: Tokens de sortie facturés.

    Returns:
        Le coût en USD (0 si aucun token).
    """
    rate_in = _USD_PER_MILLION_INPUT_TOKENS.get(model, _DEFAULT_USD_PER_MILLION_INPUT)
    rate_out = _USD_PER_MILLION_OUTPUT_TOKENS.get(
        model, _DEFAULT_USD_PER_MILLION_OUTPUT
    )
    return (
        max(0, input_tokens) / _TOKENS_PER_MILLION * rate_in
        + max(0, output_tokens) / _TOKENS_PER_MILLION * rate_out
    )


def estimated_cost_per_slide_usd(model: str) -> float:
    """Coût estimé d'une slide (estimation pré-run du ``CostEstimator``).

    Args:
        model: Identifiant du modèle vision.

    Returns:
        Le coût USD estimé d'un appel vision sur une slide typique.
    """
    return vision_cost_usd(
        model=model,
        input_tokens=ESTIMATED_INPUT_TOKENS_PER_SLIDE,
        output_tokens=ESTIMATED_OUTPUT_TOKENS_PER_SLIDE,
    )
```

`infra/vision/_fakes.py` :

```python
"""Doubles de test du sous-système vision."""

from __future__ import annotations

from pathlib import Path

from fahmi2.domain.enums import Language
from fahmi2.infra.vision.interface import SlideAnalysis, SlideContent

_DEFAULT_CONTENT = SlideContent(
    text="Texte de slide factice", visuals_description="Un schéma factice"
)
_DEFAULT_COST_USD = 0.001


class FakeVisionProvider:
    """Provider vision déterministe pour les tests.

    Attributes:
        calls: Chemins d'images reçus, dans l'ordre des appels.
    """

    def __init__(
        self,
        *,
        content: SlideContent = _DEFAULT_CONTENT,
        cost_per_call_usd: float = _DEFAULT_COST_USD,
        empty_names: frozenset[str] = frozenset(),
    ) -> None:
        """Construit le fake.

        Args:
            content: Contenu renvoyé pour chaque image analysée.
            cost_per_call_usd: Coût simulé par appel.
            empty_names: Noms de fichiers (``Path.name``) pour lesquels un
                contenu vide est renvoyé (simule une frame sans slide).
        """
        self._content = content
        self._cost = cost_per_call_usd
        self._empty_names = empty_names
        self.calls: list[Path] = []

    def analyze_slide(
        self, image_path: Path, *, language: Language
    ) -> SlideAnalysis:
        """Renvoie le contenu configuré (cf. ``SlideVisionProvider``).

        Args:
            image_path: Image reçue (enregistrée dans ``calls``).
            language: Langue demandée (ignorée).

        Returns:
            Le ``SlideAnalysis`` simulé.
        """
        del language
        self.calls.append(image_path)
        if image_path.name in self._empty_names:
            return SlideAnalysis(
                content=SlideContent(text="", visuals_description=""),
                cost_usd=self._cost,
            )
        return SlideAnalysis(content=self._content, cost_usd=self._cost)
```

- [ ] **Étape 4 : vérifier** — Run :
`.venv\Scripts\python.exe -m pytest tests/unit/infra/vision -v` → PASS.

- [ ] **Étape 5 : commit**

```bash
git add -A && git commit -m "feat(vision): port SlideVisionProvider + pricing + fake (VisionError)"
```

---

### Tâche 3 : Prompt `phase_0_slide_analysis.j2` + catalogue + `OpenAIVisionAdapter`

**Files:**
- Create: `src/fahmi2/infra/prompts/defaults/phase_0_slide_analysis.j2`
- Modify: `src/fahmi2/app/prompts_service.py` (catalogue, avant les entrées `pedagogy_*`)
- Create: `src/fahmi2/infra/vision/openai_vision.py`
- Test: `tests/unit/infra/vision/test_openai_vision.py`
- Test: vérifier que le test existant du catalogue prompts (s'il énumère les templates) passe — sinon l'ajuster.

**Interfaces:**
- Consumes: `SlideContent`/`SlideAnalysis` (T2), `PromptLoader.render(name,
  **context)`, `language_label(language)` de `fahmi2.domain.languages`,
  `vision_cost_usd` (T2).
- Produces: `OpenAIVisionAdapter(api_key=..., prompts=..., client=None,
  model=str(VisionModel.GPT_5_MINI))` conforme à `SlideVisionProvider`.
- Nom du template : `phase_0_slide_analysis` (convention `phase_N_*` du
  catalogue, précisé vs le nom générique de la spec).

- [ ] **Étape 1 : tests de l'adapter (échec attendu)**

`tests/unit/infra/vision/test_openai_vision.py` :

```python
"""Tests de l'adapter vision OpenAI (client factice, parsing JSON, coûts)."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from fahmi2.core.errors.exceptions import VisionError
from fahmi2.domain.enums import Language
from fahmi2.infra.prompts.loader import PromptLoader
from fahmi2.infra.vision.openai_vision import OpenAIVisionAdapter


class _FakeCompletions:
    def __init__(self, payload: str, usage: SimpleNamespace) -> None:
        self._payload = payload
        self._usage = usage
        self.last_kwargs: dict[str, object] = {}

    def create(self, **kwargs: object) -> SimpleNamespace:
        self.last_kwargs = kwargs
        message = SimpleNamespace(content=self._payload)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=message)], usage=self._usage
        )


def _fake_client(payload: str, *, prompt_tokens: int = 100, completion_tokens: int = 50):
    completions = _FakeCompletions(
        payload,
        SimpleNamespace(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens),
    )
    return SimpleNamespace(chat=SimpleNamespace(completions=completions)), completions


@pytest.fixture
def image_file(tmp_path: Path) -> Path:
    path = tmp_path / "slide.jpg"
    path.write_bytes(b"\xff\xd8\xff\xdbfake-jpeg")
    return path


def test_analyze_slide_parses_json_and_cost(image_file: Path) -> None:
    payload = json.dumps({"texte": "Titre de la slide", "visuels": "Un graphique"})
    client, completions = _fake_client(payload)
    adapter = OpenAIVisionAdapter(
        api_key="sk-test", prompts=PromptLoader(), client=client
    )
    analysis = adapter.analyze_slide(image_file, language=Language.FR)
    assert analysis.content.text == "Titre de la slide"
    assert analysis.content.visuals_description == "Un graphique"
    assert analysis.cost_usd > 0.0
    assert completions.last_kwargs["response_format"] == {"type": "json_object"}


def test_analyze_slide_empty_content(image_file: Path) -> None:
    payload = json.dumps({"texte": "", "visuels": ""})
    client, _ = _fake_client(payload)
    adapter = OpenAIVisionAdapter(api_key="sk-test", prompts=PromptLoader(), client=client)
    assert adapter.analyze_slide(image_file, language=Language.FR).content.is_empty()


def test_analyze_slide_invalid_json_raises_vision_error(image_file: Path) -> None:
    client, _ = _fake_client("pas du JSON")
    adapter = OpenAIVisionAdapter(api_key="sk-test", prompts=PromptLoader(), client=client)
    with pytest.raises(VisionError) as excinfo:
        adapter.analyze_slide(image_file, language=Language.FR)
    assert excinfo.value.code == "VISION.INVALID_RESPONSE"
```

- [ ] **Étape 2 : vérifier l'échec** — Run :
`.venv\Scripts\python.exe -m pytest tests/unit/infra/vision/test_openai_vision.py -v` → FAIL.

- [ ] **Étape 3 : implémenter**

`infra/prompts/defaults/phase_0_slide_analysis.j2` :

```jinja2
Tu analyses l'image d'une diapositive (slide) extraite d'une vidéo de cours.
La slide peut occuper tout l'écran, une moitié de l'image, ou une fenêtre ;
l'image peut aussi montrer un présentateur, une webcam incrustée ou un décor :
ignore tout ce qui n'est pas le contenu pédagogique de la slide ou de
l'illustration.

Réponds en {{ language_label }} par un objet JSON strict, sans texte hors JSON :
{
  "texte": "transcription fidèle du texte visible de la slide (chaîne vide si aucun texte)",
  "visuels": "description synthétique des éléments visuels porteurs de sens — schémas, graphiques, tableaux, images (chaîne vide si aucun)"
}

Règles :
- Transcris le texte fidèlement (titres, puces, formules, légendes), sans le résumer.
- Décris les visuels pour un lecteur qui ne voit pas l'image (axes, tendances, relations, étapes).
- Si aucune slide ni illustration n'est visible (plan orateur seul, écran vide), renvoie deux chaînes vides.
```

`app/prompts_service.py` — entrée catalogue (après les entrées `phase_0`…
en tête des phases, à la position triée par phase) :

```python
    PromptTemplateMeta(
        name="phase_0_slide_analysis",
        display_name="Phase 0 — Analyse des slides (vision)",
        description=(
            "Analyse vision d'une image de slide : transcription fidèle du "
            "texte + description des éléments visuels. Utilisé quand "
            "l'option « analyser les slides » est activée sur une source "
            "vidéo/YouTube."
        ),
    ),
```

`infra/vision/openai_vision.py` (miroir d'`openai_adapter.py` embeddings —
mapping d'erreurs identique, préfixe `VISION.`) :

```python
"""``OpenAIVisionAdapter`` — analyse de slides via l'API vision OpenAI.

Utilise le SDK ``openai`` (déjà présent pour Whisper cloud et les
embeddings). Le modèle est configurable (cf.
:class:`fahmi2.domain.enums.VisionModel`), défaut ``gpt-5-mini``. Sortie en
**JSON mode** (objet ``{"texte", "visuels"}``), parsing *lenient* (clés
manquantes = chaînes vides). Le prompt est chargé via ``PromptLoader``
(défaut bundlé ``phase_0_slide_analysis.j2``, override ``%APPDATA%``).
"""

from __future__ import annotations

import base64
import json
from pathlib import Path

from openai import APIError, APIStatusError, AuthenticationError, OpenAI, RateLimitError

from fahmi2.core.errors.exceptions import VisionError
from fahmi2.core.errors.severity import Severity
from fahmi2.domain.enums import Language, VisionModel
from fahmi2.domain.languages import language_label
from fahmi2.infra.prompts.loader import PromptLoader
from fahmi2.infra.vision._pricing import vision_cost_usd
from fahmi2.infra.vision.interface import SlideAnalysis, SlideContent

_MODEL = str(VisionModel.GPT_5_MINI)
_PROVIDER_NAME = "openai-vision"
_PROMPT_NAME = "phase_0_slide_analysis"
_JSON_RESPONSE_FORMAT: dict[str, str] = {"type": "json_object"}
_IMAGE_MIME = "image/jpeg"
_TEXT_KEY = "texte"
_VISUALS_KEY = "visuels"


def _map_vision_error(
    exc: APIStatusError | RateLimitError | AuthenticationError | APIError,
) -> VisionError:
    """Convertit une exception OpenAI en ``VisionError`` typée (message FR).

    Args:
        exc: Exception levée par le SDK OpenAI.

    Returns:
        La ``VisionError`` correspondante.
    """
    if isinstance(exc, AuthenticationError):
        return VisionError(
            code="VISION.AUTH_INVALID",
            user_message=(
                "La clé OpenAI est refusée pour l'analyse des slides. "
                "Vérifie-la dans Paramètres › Clés API."
            ),
            severity=Severity.ERROR,
            technical_details={"provider": _PROVIDER_NAME},
        )
    if isinstance(exc, RateLimitError):
        return VisionError(
            code="VISION.RATE_LIMIT",
            user_message="Limite de débit OpenAI atteinte (analyse des slides).",
            severity=Severity.WARNING,
            technical_details={"provider": _PROVIDER_NAME},
        )
    return VisionError(
        code="VISION.API_ERROR",
        user_message="Échec de l'analyse vision d'une slide.",
        severity=Severity.ERROR,
        technical_details={"provider": _PROVIDER_NAME, "error": str(exc)},
    )


class OpenAIVisionAdapter:
    """Fournisseur d'analyse vision de slides (OpenAI)."""

    def __init__(
        self,
        *,
        api_key: str,
        prompts: PromptLoader,
        client: OpenAI | None = None,
        model: str = _MODEL,
    ) -> None:
        """Construit l'adaptateur.

        Args:
            api_key: Clé API OpenAI.
            prompts: Loader de templates (défauts bundlés + overrides).
            client: Client OpenAI injectable (tests).
            model: Identifiant du modèle vision.
        """
        self._client = client or OpenAI(api_key=api_key)
        self._prompts = prompts
        self._model = model

    def analyze_slide(
        self, image_path: Path, *, language: Language
    ) -> SlideAnalysis:
        """Analyse l'image d'une slide (cf. ``SlideVisionProvider``).

        Args:
            image_path: Image JPEG de la frame représentative.
            language: Langue de sortie (langue détectée par le STT).

        Returns:
            Le ``SlideAnalysis`` (contenu + coût réel USD).

        Raises:
            VisionError: Échec d'appel API ou réponse non-JSON.
        """
        prompt = self._prompts.render(
            _PROMPT_NAME, language_label=language_label(language)
        )
        encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                response_format=_JSON_RESPONSE_FORMAT,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{_IMAGE_MIME};base64,{encoded}"
                                },
                            },
                        ],
                    }
                ],
            )
        except (APIError, APIStatusError, AuthenticationError, RateLimitError) as exc:
            raise _map_vision_error(exc) from exc
        raw = response.choices[0].message.content or ""
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise VisionError(
                code="VISION.INVALID_RESPONSE",
                user_message="Le modèle vision a renvoyé une réponse illisible.",
                severity=Severity.ERROR,
                technical_details={"provider": _PROVIDER_NAME, "raw": raw[:500]},
            ) from exc
        content = SlideContent(
            text=str(payload.get(_TEXT_KEY, "")),
            visuals_description=str(payload.get(_VISUALS_KEY, "")),
        )
        usage = response.usage
        cost = vision_cost_usd(
            model=self._model,
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
        )
        return SlideAnalysis(content=content, cost_usd=cost)
```

- [ ] **Étape 4 : vérifier** — Run :
`.venv\Scripts\python.exe -m pytest tests/unit/infra/vision tests/unit/app/test_prompts_service.py -v`
(adapter le chemin du test prompts_service s'il diffère) → PASS.

- [ ] **Étape 5 : commit**

```bash
git add -A && git commit -m "feat(vision): adapter OpenAI (JSON mode) + prompt phase_0_slide_analysis éditable"
```

---

### Tâche 4 : Détection — `_constants.py`, `tiles.py`, `grouping.py` (purs)

**Files:**
- Create: `src/fahmi2/infra/video/__init__.py`
- Create: `src/fahmi2/infra/video/_constants.py`
- Create: `src/fahmi2/infra/video/tiles.py`
- Create: `src/fahmi2/infra/video/grouping.py`
- Test: `tests/unit/infra/video/__init__.py` (vide) + `tests/unit/infra/video/test_grouping.py`

**Interfaces:**
- Produces: `tile_dhashes(image: PIL.Image.Image, *, grid_size, hash_size)
  -> tuple[int, ...]` ; `changed_tiles(previous, current, *, min_bits) ->
  tuple[bool, ...]` ; `FrameSample(time_seconds, tile_hashes)` ;
  `SlideGroup(start_seconds, end_seconds, representative_index)` ;
  `SlideGroupingResult(groups, dropped_groups)` ;
  `group_slides(samples, *, duration_seconds) -> SlideGroupingResult`.

- [ ] **Étape 1 : tests du regroupement (échec attendu)**

`tests/unit/infra/video/test_grouping.py` :

```python
"""Tests du regroupement de frames en slides (tuiles, 2 passes, plafonds)."""

from fahmi2.infra.video._constants import TILE_GRID_SIZE
from fahmi2.infra.video.grouping import FrameSample, group_slides

_N_TILES = TILE_GRID_SIZE * TILE_GRID_SIZE
#: Valeurs de hash « très différentes » (64 bits opposés) pour forcer un
#: changement de tuile, et identiques pour l'absence de changement.
_A = 0
_B = (1 << 64) - 1


def _sample(t: float, changed: set[int], base: dict[int, int] | None = None) -> FrameSample:
    """Frame dont les tuiles de ``changed`` valent _B (les autres _A ou base)."""
    hashes = [(base or {}).get(i, _A) for i in range(_N_TILES)]
    for i in changed:
        hashes[i] = _B
    return FrameSample(time_seconds=t, tile_hashes=tuple(hashes))


def test_video_statique_donne_une_seule_slide() -> None:
    samples = [_sample(t=2.0 * i, changed=set()) for i in range(10)]
    result = group_slides(samples, duration_seconds=20.0)
    assert len(result.groups) == 1
    assert result.groups[0].start_seconds == 0.0
    assert result.groups[0].end_seconds == 20.0
    assert result.dropped_groups == 0


def test_deux_slides_plein_ecran() -> None:
    """Transition franche à t=10 s : 2 groupes, représentative = état final."""
    all_tiles = set(range(_N_TILES))
    samples = [_sample(2.0 * i, set()) for i in range(5)]
    samples += [_sample(10.0 + 2.0 * i, all_tiles) for i in range(5)]
    result = group_slides(samples, duration_seconds=20.0)
    assert len(result.groups) == 2
    first, second = result.groups
    assert first.start_seconds == 0.0
    assert first.end_seconds == 10.0
    assert second.start_seconds == 10.0
    assert second.end_seconds == 20.0
    assert first.representative_index == 4   # dernière frame avant transition
    assert second.representative_index == 9  # état final de la 2e slide


def test_devoilement_progressif_reste_une_slide() -> None:
    """Une puce (1 tuile) apparaît à chaque frame : 1 groupe, repr = dernière."""
    samples = [_sample(2.0 * i, set(range(i))) for i in range(5)]
    result = group_slides(samples, duration_seconds=10.0)
    assert len(result.groups) == 1
    assert result.groups[0].representative_index == 4


def test_slide_fenetree_petite_fenetre_detectee() -> None:
    """Seules les tuiles 0..7 bougent (fenêtre ~12 %) : le flip complet de la
    fenêtre est bien une nouvelle slide (fraction relative à la région
    dynamique, pas à la frame entière)."""
    window = set(range(8))
    samples = [_sample(2.0 * i, set()) for i in range(5)]
    samples += [_sample(10.0 + 2.0 * i, window) for i in range(5)]
    result = group_slides(samples, duration_seconds=20.0)
    assert len(result.groups) == 2


def test_webcam_bruyante_exclue_du_masque() -> None:
    """Les tuiles 60..63 changent à chaque frame (webcam) : pas de fausses
    slides ; une vraie transition sur les autres tuiles reste détectée."""
    noisy = set(range(60, 64))
    slide_zone = set(range(32))
    samples = []
    for i in range(5):
        samples.append(_sample(2.0 * i, noisy if i % 2 else set()))
    for i in range(5):
        changed = slide_zone | (noisy if i % 2 else set())
        samples.append(_sample(10.0 + 2.0 * i, changed))
    result = group_slides(samples, duration_seconds=20.0)
    assert len(result.groups) == 2


def test_plafond_de_slides() -> None:
    """Détection instable (nouvelle slide à chaque frame) : plafond appliqué."""
    all_tiles = set(range(_N_TILES))
    samples = [
        _sample(2.0 * i, all_tiles if i % 2 else set()) for i in range(240)
    ]
    result = group_slides(samples, duration_seconds=480.0)  # 8 min → cap 32
    assert result.dropped_groups > 0
    assert len(result.groups) <= 32


def test_dedoublonnage_slides_consecutives_identiques() -> None:
    """Flash transitoire (frame unique très différente puis retour) : les deux
    groupes au contenu identique sont fusionnés."""
    all_tiles = set(range(_N_TILES))
    samples = [_sample(2.0 * i, set()) for i in range(4)]
    samples.append(_sample(8.0, all_tiles))   # flash
    samples += [_sample(10.0 + 2.0 * i, set()) for i in range(4)]
    result = group_slides(samples, duration_seconds=18.0)
    reprs = {g.representative_index for g in result.groups}
    # le flash crée au plus un groupe distinct ; les groupes « même contenu »
    # (avant/après) ne sont pas dupliqués
    assert len(result.groups) <= 2
    assert reprs  # non vide
```

- [ ] **Étape 2 : vérifier l'échec** — Run :
`.venv\Scripts\python.exe -m pytest tests/unit/infra/video -v` → FAIL (module absent).

- [ ] **Étape 3 : implémenter**

`infra/video/__init__.py` :

```python
"""Sous-système vidéo : extraction et détection des slides dans les vidéos."""
```

`infra/video/_constants.py` :

```python
"""Constantes du sous-système d'extraction de slides.

Tous les nombres magiques de la détection sont centralisés ici (directive
n° 1) : ajustables sans toucher à la logique — c'est le levier de correction
prévu pour les vidéos atypiques (cf. spec, « risque résiduel assumé »).
"""

#: Intervalle d'échantillonnage des frames (secondes).
SAMPLE_INTERVAL_SECONDS = 2.0
#: Côté maximal des frames extraites (px) — lisibilité des slides vs tokens image.
MAX_FRAME_DIMENSION_PX = 1280
#: Qualité JPEG des frames extraites (échelle ffmpeg ``-q:v``, 2-5 = très bonne).
FFMPEG_JPEG_QUALITY = 3
#: Taille de la grille de tuiles (N × N) du hachage perceptuel localisé.
TILE_GRID_SIZE = 8
#: Taille du dHash par tuile (le hash porte ``taille²`` bits).
TILE_HASH_SIZE = 8
#: Distance de Hamming minimale pour considérer une tuile comme « changée ».
TILE_CHANGED_MIN_BITS = 6
#: Fraction des transitions au-delà de laquelle une tuile est jugée bruyante
#: (webcam incrustée, vidéo dans la slide) et exclue de la mesure.
NOISY_TILE_CHANGE_RATIO = 0.5
#: Sous cette fraction de la région dynamique : image identique.
F_LOW = 0.05
#: Au-delà de cette fraction de la région dynamique : nouvelle slide.
#: Entre les deux : même slide en dévoilement progressif.
F_HIGH = 0.55
#: Plafond de slides analysées par minute de vidéo (garde-fou de coût).
MAX_SLIDES_PER_MINUTE = 4.0
#: Plafond absolu de slides analysées par vidéo.
MAX_SLIDES_ABSOLUTE = 300
#: Fraction maximale de région dynamique différente entre les représentantes
#: de deux slides consécutives pour les fusionner (re-détection parasite).
INTER_SLIDE_DEDUP_MAX_RATIO = 0.05
```

`infra/video/tiles.py` :

```python
"""Hachage perceptuel par tuiles (dHash) d'une frame vidéo.

Un dHash *global* dilue un changement de slide fenêtrée ; la frame est donc
découpée en grille de tuiles, chacune hachée indépendamment. Les fonctions
sont pures (Pillow uniquement, aucun I/O).
"""

from __future__ import annotations

from PIL import Image

from fahmi2.infra.video._constants import (
    TILE_CHANGED_MIN_BITS,
    TILE_GRID_SIZE,
    TILE_HASH_SIZE,
)


def tile_dhashes(
    image: Image.Image,
    *,
    grid_size: int = TILE_GRID_SIZE,
    hash_size: int = TILE_HASH_SIZE,
) -> tuple[int, ...]:
    """Calcule le dHash de chaque tuile d'une grille ``grid_size × grid_size``.

    Args:
        image: Frame à hacher (tout mode Pillow ; convertie en niveaux de gris).
        grid_size: Nombre de tuiles par côté.
        hash_size: Côté du dHash (le hash d'une tuile porte ``hash_size²`` bits).

    Returns:
        Un entier de hash par tuile, ordre ligne par ligne.
    """
    gray = image.convert("L")
    width, height = gray.size
    hashes: list[int] = []
    for row in range(grid_size):
        for col in range(grid_size):
            box = (
                col * width // grid_size,
                row * height // grid_size,
                (col + 1) * width // grid_size,
                (row + 1) * height // grid_size,
            )
            tile = gray.crop(box).resize(
                (hash_size + 1, hash_size), Image.Resampling.LANCZOS
            )
            pixels = list(tile.getdata())
            bits = 0
            for y in range(hash_size):
                for x in range(hash_size):
                    left = pixels[y * (hash_size + 1) + x]
                    right = pixels[y * (hash_size + 1) + x + 1]
                    bits = (bits << 1) | (1 if left > right else 0)
            hashes.append(bits)
    return tuple(hashes)


def hamming_distance(a: int, b: int) -> int:
    """Distance de Hamming entre deux hashes.

    Args:
        a: Premier hash.
        b: Second hash.

    Returns:
        Le nombre de bits différents.
    """
    return (a ^ b).bit_count()


def changed_tiles(
    previous: tuple[int, ...],
    current: tuple[int, ...],
    *,
    min_bits: int = TILE_CHANGED_MIN_BITS,
) -> tuple[bool, ...]:
    """Marque les tuiles ayant significativement changé entre deux frames.

    Args:
        previous: Hashes par tuile de la frame précédente.
        current: Hashes par tuile de la frame courante (même taille).
        min_bits: Distance de Hamming minimale pour marquer un changement.

    Returns:
        Un booléen par tuile (``True`` = changée).
    """
    return tuple(
        hamming_distance(p, c) >= min_bits
        for p, c in zip(previous, current, strict=True)
    )
```

`infra/video/grouping.py` :

```python
"""Regroupement des frames échantillonnées en slides (2 passes, pur).

Passe 1 — cartographie : statistiques de changement par tuile sur toute la
vidéo → masque de bruit temporel (tuiles changeant en permanence : webcam,
vidéo incrustée) et région dynamique (tuiles ayant changé au moins une fois,
hors masque — de fait, la zone de slide). Passe 2 — regroupement : double
seuil sur la **fraction de la région dynamique** changeant simultanément,
insensible au fenêtrage de la slide. Garde-fous : plafond de slides
(coût borné) et fusion des re-détections parasites consécutives.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from fahmi2.infra.video._constants import (
    F_HIGH,
    F_LOW,
    INTER_SLIDE_DEDUP_MAX_RATIO,
    MAX_SLIDES_ABSOLUTE,
    MAX_SLIDES_PER_MINUTE,
    NOISY_TILE_CHANGE_RATIO,
)
from fahmi2.infra.video.tiles import changed_tiles

_SECONDS_PER_MINUTE = 60.0


@dataclass(frozen=True)
class FrameSample:
    """Un échantillon de frame vidéo haché par tuiles.

    Attributes:
        time_seconds: Horodatage de la frame dans la vidéo.
        tile_hashes: dHash de chaque tuile (cf. ``tiles.tile_dhashes``).
    """

    time_seconds: float
    tile_hashes: tuple[int, ...]


@dataclass(frozen=True)
class SlideGroup:
    """Un groupe de frames formant une slide affichée sur une plage temporelle.

    Attributes:
        start_seconds: Début d'affichage.
        end_seconds: Fin d'affichage.
        representative_index: Index (dans les échantillons) de la frame
            représentative — l'état final de la slide.
    """

    start_seconds: float
    end_seconds: float
    representative_index: int


@dataclass(frozen=True)
class SlideGroupingResult:
    """Résultat du regroupement.

    Attributes:
        groups: Slides détectées, ordonnées temporellement.
        dropped_groups: Groupes ignorés par les plafonds (détection instable).
    """

    groups: tuple[SlideGroup, ...]
    dropped_groups: int


def group_slides(
    samples: Sequence[FrameSample], *, duration_seconds: float
) -> SlideGroupingResult:
    """Regroupe les frames échantillonnées en slides (2 passes).

    Args:
        samples: Échantillons ordonnés temporellement (≥ 0).
        duration_seconds: Durée de la vidéo (clôture du dernier groupe et
            calcul du plafond de slides).

    Returns:
        Le ``SlideGroupingResult`` (groupes plafonnés + nombre d'ignorés).
    """
    if not samples:
        return SlideGroupingResult(groups=(), dropped_groups=0)
    if len(samples) == 1:
        only = SlideGroup(
            start_seconds=samples[0].time_seconds,
            end_seconds=duration_seconds,
            representative_index=0,
        )
        return SlideGroupingResult(groups=(only,), dropped_groups=0)

    # Passe 1 — cartographie des changements par tuile.
    n_tiles = len(samples[0].tile_hashes)
    transitions = [
        changed_tiles(samples[i - 1].tile_hashes, samples[i].tile_hashes)
        for i in range(1, len(samples))
    ]
    change_counts = [0] * n_tiles
    for changes in transitions:
        for tile, changed in enumerate(changes):
            if changed:
                change_counts[tile] += 1
    n_transitions = len(transitions)
    noisy = [
        change_counts[tile] / n_transitions >= NOISY_TILE_CHANGE_RATIO
        for tile in range(n_tiles)
    ]
    dynamic = [
        change_counts[tile] > 0 and not noisy[tile] for tile in range(n_tiles)
    ]
    dynamic_count = sum(dynamic)
    if dynamic_count == 0:
        # Vidéo statique (une seule slide affichée en continu) ou 100 % bruit :
        # un seul groupe couvrant toute la vidéo, état final = dernière frame.
        only = SlideGroup(
            start_seconds=samples[0].time_seconds,
            end_seconds=duration_seconds,
            representative_index=len(samples) - 1,
        )
        return SlideGroupingResult(groups=(only,), dropped_groups=0)

    # Passe 2 — regroupement par fraction de la région dynamique.
    groups: list[SlideGroup] = []
    current_start = samples[0].time_seconds
    current_repr = 0
    for i, changes in enumerate(transitions, start=1):
        changed_dynamic = sum(
            1 for tile in range(n_tiles) if changes[tile] and dynamic[tile]
        )
        fraction = changed_dynamic / dynamic_count
        if fraction < F_LOW:
            continue  # image identique
        if fraction < F_HIGH:
            current_repr = i  # même slide, état plus récent (dévoilement)
            continue
        groups.append(
            SlideGroup(
                start_seconds=current_start,
                end_seconds=samples[i].time_seconds,
                representative_index=max(current_repr, i - 1),
            )
        )
        current_start = samples[i].time_seconds
        current_repr = i
    groups.append(
        SlideGroup(
            start_seconds=current_start,
            end_seconds=duration_seconds,
            representative_index=max(current_repr, len(samples) - 1),
        )
    )

    deduped = _merge_consecutive_duplicates(groups, samples, dynamic, dynamic_count)
    return _apply_caps(deduped, duration_seconds)


def _merge_consecutive_duplicates(
    groups: list[SlideGroup],
    samples: Sequence[FrameSample],
    dynamic: list[bool],
    dynamic_count: int,
) -> list[SlideGroup]:
    """Fusionne les groupes consécutifs au contenu quasi identique.

    Args:
        groups: Groupes issus de la passe 2.
        samples: Échantillons (accès aux hashes des représentantes).
        dynamic: Masque de la région dynamique.
        dynamic_count: Taille de la région dynamique (> 0).

    Returns:
        Les groupes fusionnés (re-détections parasites absorbées).
    """
    merged: list[SlideGroup] = []
    for group in groups:
        if merged:
            previous = merged[-1]
            diff = changed_tiles(
                samples[previous.representative_index].tile_hashes,
                samples[group.representative_index].tile_hashes,
            )
            diff_dynamic = sum(
                1 for tile, changed in enumerate(diff) if changed and dynamic[tile]
            )
            if diff_dynamic / dynamic_count <= INTER_SLIDE_DEDUP_MAX_RATIO:
                merged[-1] = SlideGroup(
                    start_seconds=previous.start_seconds,
                    end_seconds=group.end_seconds,
                    representative_index=group.representative_index,
                )
                continue
        merged.append(group)
    return merged


def _apply_caps(
    groups: list[SlideGroup], duration_seconds: float
) -> SlideGroupingResult:
    """Applique les plafonds slides/minute et absolu (coût borné).

    Args:
        groups: Groupes dédoublonnés.
        duration_seconds: Durée de la vidéo.

    Returns:
        Le résultat final (groupes conservés + nombre d'ignorés).
    """
    per_minute_cap = int(
        duration_seconds / _SECONDS_PER_MINUTE * MAX_SLIDES_PER_MINUTE
    )
    cap = max(1, min(MAX_SLIDES_ABSOLUTE, per_minute_cap))
    dropped = max(0, len(groups) - cap)
    return SlideGroupingResult(groups=tuple(groups[:cap]), dropped_groups=dropped)
```

- [ ] **Étape 4 : vérifier** — Run :
`.venv\Scripts\python.exe -m pytest tests/unit/infra/video -v` → PASS.
Ajuster les seuils/tests si un cas échoue (les tests encodent le comportement
attendu de la spec ; corriger la logique, pas l'intention du test).

- [ ] **Étape 5 : commit**

```bash
git add -A && git commit -m "feat(video): détection de slides par tuiles (2 passes, masque de bruit, région dynamique, plafonds)"
```

---

### Tâche 5 : `SlideFrameExtractor` (échantillonnage ffmpeg)

**Files:**
- Create: `src/fahmi2/infra/video/frame_extractor.py`
- Test: `tests/unit/infra/video/test_frame_extractor.py`

**Interfaces:**
- Consumes: `tile_dhashes`, `group_slides`, constantes (T4) ;
  `DEFAULT_FFMPEG_BINARY`, `FFMPEG_LOGLEVEL_ERROR` de
  `fahmi2.infra.audio._ffmpeg_common` ; `FFmpegError`.
- Produces: `SlideFrame(start_seconds, end_seconds, image_path)` ;
  `SlideExtractionResult(frames: tuple[SlideFrame, ...], dropped_groups: int)` ;
  `SlideFrameExtractor(ffmpeg_binary=None).extract(video_path, frames_dir, *,
  duration_seconds) -> SlideExtractionResult` (frames JPEG nommées
  `%06d.jpg`, horodatage = ``(n° - 1) × SAMPLE_INTERVAL_SECONDS``).

- [ ] **Étape 1 : test (échec attendu)**

`tests/unit/infra/video/test_frame_extractor.py` :

```python
"""Tests de l'extracteur de frames (échantillonnage ffmpeg simulé)."""

from pathlib import Path

from PIL import Image

from fahmi2.infra.video.frame_extractor import SlideFrameExtractor


class _StubExtractor(SlideFrameExtractor):
    """Remplace l'appel ffmpeg par l'écriture de frames synthétiques."""

    def __init__(self, frames: list[Image.Image]) -> None:
        super().__init__(ffmpeg_binary="ffmpeg-inutilise")
        self._frames = frames

    def _sample_frames(self, video_path: Path, frames_dir: Path) -> None:
        del video_path
        for i, img in enumerate(self._frames, start=1):
            img.save(frames_dir / f"{i:06d}.jpg")


def _solid(color: tuple[int, int, int]) -> Image.Image:
    return Image.new("RGB", (320, 180), color)


def test_extract_deux_slides(tmp_path: Path) -> None:
    """5 frames noires puis 5 blanches : 2 slides, représentative lisible."""
    frames = [_solid((0, 0, 0))] * 5 + [_solid((255, 255, 255))] * 5
    extractor = _StubExtractor(frames)
    result = extractor.extract(
        tmp_path / "video.mp4", tmp_path / "frames", duration_seconds=20.0
    )
    assert len(result.frames) == 2
    first, second = result.frames
    assert first.start_seconds == 0.0
    assert second.end_seconds == 20.0
    assert first.image_path.exists()
    assert second.image_path.exists()


def test_extract_aucune_frame(tmp_path: Path) -> None:
    """ffmpeg n'a rien produit (vidéo sans piste vidéo) : résultat vide."""
    extractor = _StubExtractor([])
    result = extractor.extract(
        tmp_path / "video.mp4", tmp_path / "frames", duration_seconds=20.0
    )
    assert result.frames == ()
    assert result.dropped_groups == 0
```

- [ ] **Étape 2 : vérifier l'échec** — Run :
`.venv\Scripts\python.exe -m pytest tests/unit/infra/video/test_frame_extractor.py -v` → FAIL.

- [ ] **Étape 3 : implémenter**

`infra/video/frame_extractor.py` :

```python
"""Échantillonnage ffmpeg d'une vidéo en frames JPEG + détection des slides.

Une passe ``ffmpeg`` produit une frame réduite toutes les
``SAMPLE_INTERVAL_SECONDS`` ; les frames sont hachées par tuiles puis
regroupées en slides (cf. ``grouping``). L'appel ffmpeg est isolé dans
``_sample_frames`` (surchargeable en test).
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from fahmi2.core.errors.exceptions import FFmpegError
from fahmi2.core.errors.severity import Severity
from fahmi2.infra.audio._ffmpeg_common import (
    DEFAULT_FFMPEG_BINARY,
    FFMPEG_LOGLEVEL_ERROR,
)
from fahmi2.infra.video._constants import (
    FFMPEG_JPEG_QUALITY,
    MAX_FRAME_DIMENSION_PX,
    SAMPLE_INTERVAL_SECONDS,
)
from fahmi2.infra.video.grouping import FrameSample, group_slides
from fahmi2.infra.video.tiles import tile_dhashes

_FRAME_PATTERN = "%06d.jpg"
_FRAME_GLOB = "*.jpg"
#: Délai maximal de l'échantillonnage (s) — généreux pour les longues vidéos.
_SAMPLING_TIMEOUT_SECONDS = 1800.0


@dataclass(frozen=True)
class SlideFrame:
    """La frame représentative d'une slide, avec sa plage d'affichage.

    Attributes:
        start_seconds: Début d'affichage de la slide.
        end_seconds: Fin d'affichage.
        image_path: Frame JPEG représentative (état final de la slide).
    """

    start_seconds: float
    end_seconds: float
    image_path: Path


@dataclass(frozen=True)
class SlideExtractionResult:
    """Résultat de l'extraction des slides d'une vidéo.

    Attributes:
        frames: Slides détectées, ordonnées temporellement.
        dropped_groups: Slides ignorées par les plafonds (détection instable).
    """

    frames: tuple[SlideFrame, ...]
    dropped_groups: int


class SlideFrameExtractor:
    """Échantillonne une vidéo et en extrait les frames de slides."""

    def __init__(self, *, ffmpeg_binary: str | None = None) -> None:
        """Construit l'extracteur.

        Args:
            ffmpeg_binary: Chemin de ``ffmpeg`` (``None`` = depuis ``PATH``).
        """
        self._ffmpeg = ffmpeg_binary or DEFAULT_FFMPEG_BINARY

    def extract(
        self, video_path: Path, frames_dir: Path, *, duration_seconds: float
    ) -> SlideExtractionResult:
        """Extrait les slides de ``video_path``.

        Args:
            video_path: Vidéo source.
            frames_dir: Dossier de travail des frames (créé si absent ; le
                nettoyage relève de l'appelant, cf. ``SlideAnalyzer``).
            duration_seconds: Durée de la vidéo (bornage du dernier groupe et
                plafond de slides).

        Returns:
            Le ``SlideExtractionResult``.

        Raises:
            FFmpegError: Si l'échantillonnage ffmpeg échoue.
        """
        frames_dir.mkdir(parents=True, exist_ok=True)
        self._sample_frames(video_path, frames_dir)
        paths = sorted(frames_dir.glob(_FRAME_GLOB))
        if not paths:
            return SlideExtractionResult(frames=(), dropped_groups=0)
        samples: list[FrameSample] = []
        for index, path in enumerate(paths):
            with Image.open(path) as image:
                hashes = tile_dhashes(image)
            samples.append(
                FrameSample(
                    time_seconds=index * SAMPLE_INTERVAL_SECONDS,
                    tile_hashes=hashes,
                )
            )
        effective_duration = (
            duration_seconds
            if duration_seconds > 0
            else len(paths) * SAMPLE_INTERVAL_SECONDS
        )
        grouping = group_slides(samples, duration_seconds=effective_duration)
        frames = tuple(
            SlideFrame(
                start_seconds=group.start_seconds,
                end_seconds=group.end_seconds,
                image_path=paths[group.representative_index],
            )
            for group in grouping.groups
        )
        return SlideExtractionResult(
            frames=frames, dropped_groups=grouping.dropped_groups
        )

    def _sample_frames(self, video_path: Path, frames_dir: Path) -> None:
        """Écrit une frame JPEG réduite toutes les ``SAMPLE_INTERVAL_SECONDS``.

        Args:
            video_path: Vidéo source.
            frames_dir: Dossier de sortie (``%06d.jpg``).

        Raises:
            FFmpegError: ``FFMPEG.FRAME_EXTRACTION_FAILED`` en cas d'échec.
        """
        scale = f"scale='min({MAX_FRAME_DIMENSION_PX},iw)':-2"
        cmd = [
            self._ffmpeg,
            "-hide_banner",
            "-loglevel",
            FFMPEG_LOGLEVEL_ERROR,
            "-i",
            str(video_path),
            "-vf",
            f"fps=1/{SAMPLE_INTERVAL_SECONDS},{scale}",
            "-q:v",
            str(FFMPEG_JPEG_QUALITY),
            str(frames_dir / _FRAME_PATTERN),
        ]
        try:
            subprocess.run(  # noqa: S603
                cmd,
                check=True,
                capture_output=True,
                timeout=_SAMPLING_TIMEOUT_SECONDS,
            )
        except FileNotFoundError as exc:
            raise FFmpegError(
                code="FFMPEG.NOT_FOUND",
                user_message="ffmpeg est introuvable pour extraire les slides.",
                severity=Severity.FATAL,
                technical_details={"ffmpeg_binary": self._ffmpeg},
            ) from exc
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            stderr = ""
            if isinstance(exc, subprocess.CalledProcessError) and exc.stderr:
                stderr = exc.stderr.decode("utf-8", errors="replace")
            raise FFmpegError(
                code="FFMPEG.FRAME_EXTRACTION_FAILED",
                user_message=(
                    "L'extraction des images de slides a échoué (vidéo "
                    "illisible ou sans piste vidéo)."
                ),
                severity=Severity.ERROR,
                technical_details={"video": str(video_path), "stderr": stderr},
            ) from exc
```

Nota : si `_ffmpeg_common` n'expose pas exactement
`DEFAULT_FFMPEG_BINARY`/`FFMPEG_LOGLEVEL_ERROR` sous ces noms, reprendre les
noms réels du module (ils existent — cf. imports de
`infra/audio/ffmpeg_extractor.py`).

- [ ] **Étape 4 : vérifier** — Run :
`.venv\Scripts\python.exe -m pytest tests/unit/infra/video -v` → PASS.

- [ ] **Étape 5 : commit**

```bash
git add -A && git commit -m "feat(video): SlideFrameExtractor — échantillonnage ffmpeg + regroupement en slides"
```

---

### Tâche 6 : Fusion horodatée — `slide_merge.py`

**Files:**
- Create: `src/fahmi2/infra/ingestion/slide_merge.py`
- Test: `tests/unit/infra/ingestion/test_slide_merge.py`

**Interfaces:**
- Consumes: `Transcription`/`TranscriptionSegment` (`infra/stt/interface`),
  `AnalyzedSlide`/`SlideContent` (T2).
- Produces: `merge_slides_into_transcription(transcription, slides) ->
  Transcription` ; `format_timestamp(seconds: float) -> str` (`mm:ss`,
  `h:mm:ss` au-delà d'une heure).

- [ ] **Étape 1 : tests (échec attendu)**

`tests/unit/infra/ingestion/test_slide_merge.py` :

```python
"""Tests de la fusion des slides dans la transcription horodatée."""

from fahmi2.domain.enums import Language
from fahmi2.infra.ingestion.slide_merge import (
    format_timestamp,
    merge_slides_into_transcription,
)
from fahmi2.infra.stt.interface import Transcription, TranscriptionSegment
from fahmi2.infra.vision.interface import AnalyzedSlide, SlideContent


def _transcription() -> Transcription:
    return Transcription(
        segments=(
            TranscriptionSegment(0.0, 10.0, "Bonjour à tous."),
            TranscriptionSegment(10.0, 20.0, "Passons au premier point."),
            TranscriptionSegment(20.0, 30.0, "Voici le second point."),
        ),
        detected_language=Language.FR,
        duration_seconds=30.0,
    )


def test_format_timestamp() -> None:
    assert format_timestamp(0.0) == "00:00"
    assert format_timestamp(754.0) == "12:34"
    assert format_timestamp(3725.0) == "1:02:05"


def test_fusion_intercale_aux_bons_timestamps() -> None:
    slides = [
        AnalyzedSlide(10.0, 20.0, SlideContent("Plan du cours", "Un sommaire")),
    ]
    merged = merge_slides_into_transcription(_transcription(), slides)
    texts = [s.text for s in merged.segments]
    assert len(merged.segments) == 4
    assert texts[1] == "Bonjour à tous." or texts[0] == "Bonjour à tous."
    slide_index = next(i for i, t in enumerate(texts) if t.startswith("[Slide"))
    assert texts[slide_index] == (
        "[Slide affichée de 00:10 à 00:20] Plan du cours — Visuels : Un sommaire"
    )
    # ordre temporel préservé
    starts = [s.start_seconds for s in merged.segments]
    assert starts == sorted(starts)


def test_slide_vide_non_injectee() -> None:
    slides = [AnalyzedSlide(10.0, 20.0, SlideContent("", "  "))]
    merged = merge_slides_into_transcription(_transcription(), slides)
    assert len(merged.segments) == 3


def test_slide_sans_texte_avec_visuels() -> None:
    slides = [AnalyzedSlide(0.0, 10.0, SlideContent("", "Un diagramme de flux"))]
    merged = merge_slides_into_transcription(_transcription(), slides)
    slide_seg = next(s for s in merged.segments if s.text.startswith("[Slide"))
    assert slide_seg.text == (
        "[Slide affichée de 00:00 à 00:10] Visuels : Un diagramme de flux"
    )


def test_aucune_slide_transcription_inchangee() -> None:
    original = _transcription()
    assert merge_slides_into_transcription(original, []) is original
```

- [ ] **Étape 2 : vérifier l'échec** — Run :
`.venv\Scripts\python.exe -m pytest tests/unit/infra/ingestion/test_slide_merge.py -v` → FAIL.

- [ ] **Étape 3 : implémenter**

`infra/ingestion/slide_merge.py` :

```python
"""Fusion des slides analysées dans la transcription horodatée (pur).

Chaque slide non vide devient un ``TranscriptionSegment`` intercalé aux
timestamps de sa plage d'affichage : les phases aval (1..7) voient le contenu
des slides adjacent aux propos oraux qui les commentent, sans modification.
Libellés en français (cohérents avec les prompts FR gelés du pipeline).
"""

from __future__ import annotations

from collections.abc import Sequence

from fahmi2.infra.stt.interface import Transcription, TranscriptionSegment
from fahmi2.infra.vision.interface import AnalyzedSlide

_SECONDS_PER_HOUR = 3600
_SECONDS_PER_MINUTE = 60
_SLIDE_TEMPLATE = "[Slide affichée de {start} à {end}] {body}"
_VISUALS_SEPARATOR = " — Visuels : "
_VISUALS_ONLY_PREFIX = "Visuels : "


def format_timestamp(seconds: float) -> str:
    """Met en forme un horodatage ``mm:ss`` (``h:mm:ss`` au-delà d'une heure).

    Args:
        seconds: Position dans la vidéo (s, bornée à 0).

    Returns:
        L'horodatage lisible.
    """
    total = int(max(0.0, seconds))
    hours, remainder = divmod(total, _SECONDS_PER_HOUR)
    minutes, secs = divmod(remainder, _SECONDS_PER_MINUTE)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def merge_slides_into_transcription(
    transcription: Transcription, slides: Sequence[AnalyzedSlide]
) -> Transcription:
    """Intercale le contenu des slides dans la transcription.

    Args:
        transcription: Transcription audio d'origine.
        slides: Slides analysées (les vides sont ignorées).

    Returns:
        Une nouvelle ``Transcription`` aux segments ordonnés temporellement
        (la transcription d'origine, inchangée, si aucune slide à injecter).
    """
    inserts: list[TranscriptionSegment] = []
    for slide in slides:
        if slide.content.is_empty():
            continue
        text = slide.content.text.strip()
        visuals = slide.content.visuals_description.strip()
        if text and visuals:
            body = f"{text}{_VISUALS_SEPARATOR}{visuals}"
        elif text:
            body = text
        else:
            body = f"{_VISUALS_ONLY_PREFIX}{visuals}"
        inserts.append(
            TranscriptionSegment(
                start_seconds=slide.start_seconds,
                end_seconds=max(slide.end_seconds, slide.start_seconds),
                text=_SLIDE_TEMPLATE.format(
                    start=format_timestamp(slide.start_seconds),
                    end=format_timestamp(slide.end_seconds),
                    body=body,
                ),
            )
        )
    if not inserts:
        return transcription
    merged = sorted(
        [*transcription.segments, *inserts],
        key=lambda segment: (segment.start_seconds, segment.end_seconds),
    )
    return Transcription(
        segments=tuple(merged),
        detected_language=transcription.detected_language,
        duration_seconds=transcription.duration_seconds,
    )
```

- [ ] **Étape 4 : vérifier** — Run :
`.venv\Scripts\python.exe -m pytest tests/unit/infra/ingestion/test_slide_merge.py -v` → PASS.

- [ ] **Étape 5 : commit**

```bash
git add -A && git commit -m "feat(ingestion): fusion horodatée des slides dans la transcription"
```

---

### Tâche 7 : Façade `SlideAnalyzer`

**Files:**
- Create: `src/fahmi2/infra/vision/slide_analyzer.py`
- Test: `tests/unit/infra/vision/test_slide_analyzer.py`

**Interfaces:**
- Consumes: `SlideFrameExtractor`/`SlideExtractionResult`/`SlideFrame` (T5),
  `SlideVisionProvider`/`AnalyzedSlide` (T2), `map_bounded` + `PauseToken`
  (`core/concurrency`), `with_retry`/`RetryPolicy`/`default_classify`
  (`core/retry`).
- Produces: `SlideAnalysisReport(slides: tuple[AnalyzedSlide, ...],
  cost_usd: float, dropped_groups: int)` ;
  `SlideAnalyzer(frame_extractor=..., vision_provider=..., llm_workers=...,
  pause_token=None)` avec `analyze(video_path, source_id, *, workspace,
  language, duration_seconds) -> SlideAnalysisReport` (frames sous
  `workspace/frames/<source_id>/`, supprimées en ``finally``) et
  `consumed_cost_usd_for(source_id) -> float` /
  `dropped_groups_for(source_id) -> int` (thread-safe, pour l'attribution
  per-source par la phase 0).

- [ ] **Étape 1 : tests (échec attendu)**

`tests/unit/infra/vision/test_slide_analyzer.py` :

```python
"""Tests de la façade SlideAnalyzer (extraction stub + vision fake)."""

from pathlib import Path

from PIL import Image

from fahmi2.domain.enums import Language
from fahmi2.infra.vision._fakes import FakeVisionProvider
from fahmi2.infra.video.frame_extractor import (
    SlideExtractionResult,
    SlideFrame,
    SlideFrameExtractor,
)
from fahmi2.infra.vision.slide_analyzer import SlideAnalyzer


class _StubFrameExtractor(SlideFrameExtractor):
    """Renvoie des frames pré-écrites sans appeler ffmpeg."""

    def __init__(self, dropped: int = 0) -> None:
        super().__init__(ffmpeg_binary="inutilise")
        self._dropped = dropped

    def extract(
        self, video_path: Path, frames_dir: Path, *, duration_seconds: float
    ) -> SlideExtractionResult:
        del video_path, duration_seconds
        frames_dir.mkdir(parents=True, exist_ok=True)
        paths = []
        for i in range(3):
            p = frames_dir / f"{i:06d}.jpg"
            Image.new("RGB", (32, 32), (i * 40, 0, 0)).save(p)
            paths.append(p)
        return SlideExtractionResult(
            frames=(
                SlideFrame(0.0, 10.0, paths[0]),
                SlideFrame(10.0, 20.0, paths[1]),
                SlideFrame(20.0, 30.0, paths[2]),
            ),
            dropped_groups=self._dropped,
        )


def _analyzer(tmp_path: Path, *, dropped: int = 0) -> tuple[SlideAnalyzer, FakeVisionProvider]:
    provider = FakeVisionProvider(cost_per_call_usd=0.002)
    analyzer = SlideAnalyzer(
        frame_extractor=_StubFrameExtractor(dropped=dropped),
        vision_provider=provider,
        llm_workers=2,
    )
    return analyzer, provider


def test_analyze_produit_slides_horodatees_et_cout(tmp_path: Path) -> None:
    analyzer, provider = _analyzer(tmp_path)
    report = analyzer.analyze(
        tmp_path / "v.mp4",
        "src-1",
        workspace=tmp_path,
        language=Language.FR,
        duration_seconds=30.0,
    )
    assert len(report.slides) == 3
    assert report.slides[0].start_seconds == 0.0
    assert report.cost_usd == 3 * 0.002
    assert len(provider.calls) == 3
    assert analyzer.consumed_cost_usd_for("src-1") == report.cost_usd
    assert analyzer.consumed_cost_usd_for("inconnu") == 0.0


def test_analyze_nettoie_les_frames(tmp_path: Path) -> None:
    analyzer, _ = _analyzer(tmp_path)
    analyzer.analyze(
        tmp_path / "v.mp4",
        "src-1",
        workspace=tmp_path,
        language=Language.FR,
        duration_seconds=30.0,
    )
    assert not (tmp_path / "frames" / "src-1").exists()


def test_analyze_expose_les_groupes_ignores(tmp_path: Path) -> None:
    analyzer, _ = _analyzer(tmp_path, dropped=7)
    report = analyzer.analyze(
        tmp_path / "v.mp4",
        "src-1",
        workspace=tmp_path,
        language=Language.FR,
        duration_seconds=30.0,
    )
    assert report.dropped_groups == 7
    assert analyzer.dropped_groups_for("src-1") == 7
```

- [ ] **Étape 2 : vérifier l'échec** — Run :
`.venv\Scripts\python.exe -m pytest tests/unit/infra/vision/test_slide_analyzer.py -v` → FAIL.

- [ ] **Étape 3 : implémenter**

`infra/vision/slide_analyzer.py` :

```python
"""Façade ``SlideAnalyzer`` : frames (ffmpeg) → analyse vision → slides.

Compose ``SlideFrameExtractor`` et ``SlideVisionProvider`` : extraction des
frames représentatives, analyse vision **parallélisée** (``map_bounded``
borné par ``llm_workers``, ordre préservé, honore le ``PauseToken``), retry
par appel (``core/retry``), nettoyage best-effort des frames. Les coûts et
avertissements sont mémorisés **par source** (thread-safe) pour l'attribution
per-source de la phase 0.
"""

from __future__ import annotations

import shutil
import threading
from dataclasses import dataclass
from pathlib import Path

from fahmi2.core.concurrency import PauseToken, map_bounded
from fahmi2.core.retry.classification import default_classify
from fahmi2.core.retry.policy import RetryPolicy
from fahmi2.core.retry.runner import with_retry
from fahmi2.domain.enums import Language
from fahmi2.infra.video.frame_extractor import SlideFrame, SlideFrameExtractor
from fahmi2.infra.vision.interface import (
    AnalyzedSlide,
    SlideAnalysis,
    SlideVisionProvider,
)

_FRAMES_SUBDIR = "frames"


@dataclass(frozen=True)
class SlideAnalysisReport:
    """Résultat de l'analyse des slides d'une vidéo.

    Attributes:
        slides: Slides analysées, horodatées, ordonnées temporellement.
        cost_usd: Coût vision total de cette vidéo (USD).
        dropped_groups: Slides ignorées par les plafonds (détection instable).
    """

    slides: tuple[AnalyzedSlide, ...]
    cost_usd: float
    dropped_groups: int


class SlideAnalyzer:
    """Analyse les slides d'une vidéo (extraction + vision parallélisée)."""

    def __init__(
        self,
        *,
        frame_extractor: SlideFrameExtractor,
        vision_provider: SlideVisionProvider,
        llm_workers: int,
        pause_token: PauseToken | None = None,
        retry_policy: RetryPolicy | None = None,
    ) -> None:
        """Construit la façade.

        Args:
            frame_extractor: Extracteur de frames de slides (ffmpeg).
            vision_provider: Fournisseur d'analyse vision.
            llm_workers: Concurrence maximale des appels vision (>= 1).
            pause_token: Jeton coopératif pause/annulation du run.
            retry_policy: Politique de retry des appels vision (défaut :
                ``RetryPolicy()``).
        """
        self._frame_extractor = frame_extractor
        self._vision = vision_provider
        self._llm_workers = max(1, llm_workers)
        self._pause_token = pause_token
        self._retry_policy = retry_policy or RetryPolicy()
        self._lock = threading.Lock()
        self._costs_by_source: dict[str, float] = {}
        self._dropped_by_source: dict[str, int] = {}

    def analyze(
        self,
        video_path: Path,
        source_id: str,
        *,
        workspace: Path,
        language: Language,
        duration_seconds: float,
    ) -> SlideAnalysisReport:
        """Extrait puis analyse les slides de ``video_path``.

        Args:
            video_path: Vidéo source.
            source_id: Identifiant de la source (nom du sous-dossier frames et
                clé d'attribution du coût).
            workspace: Dossier de travail du run.
            language: Langue de sortie de l'analyse (détectée par le STT).
            duration_seconds: Durée de la vidéo.

        Returns:
            Le ``SlideAnalysisReport`` (slides + coût + slides ignorées).

        Raises:
            FFmpegError: Échec de l'échantillonnage.
            VisionError: Échec d'analyse après épuisement des retries.
        """
        frames_dir = workspace / _FRAMES_SUBDIR / source_id
        try:
            extraction = self._frame_extractor.extract(
                video_path, frames_dir, duration_seconds=duration_seconds
            )

            def _analyze_one(frame: SlideFrame) -> SlideAnalysis:
                return with_retry(
                    lambda: self._vision.analyze_slide(
                        frame.image_path, language=language
                    ),
                    policy=self._retry_policy,
                    classify=default_classify,
                )

            analyses = map_bounded(
                _analyze_one,
                extraction.frames,
                max_workers=self._llm_workers,
                pause_token=self._pause_token,
            )
            slides = tuple(
                AnalyzedSlide(
                    start_seconds=frame.start_seconds,
                    end_seconds=frame.end_seconds,
                    content=analysis.content,
                )
                for frame, analysis in zip(extraction.frames, analyses, strict=True)
            )
            cost = sum(analysis.cost_usd for analysis in analyses)
            with self._lock:
                self._costs_by_source[source_id] = cost
                self._dropped_by_source[source_id] = extraction.dropped_groups
            return SlideAnalysisReport(
                slides=slides,
                cost_usd=cost,
                dropped_groups=extraction.dropped_groups,
            )
        finally:
            shutil.rmtree(frames_dir, ignore_errors=True)

    def consumed_cost_usd_for(self, source_id: str) -> float:
        """Coût vision consommé pour une source (0 si non analysée).

        Args:
            source_id: Identifiant de la source.

        Returns:
            Le coût USD de l'analyse de cette source.
        """
        with self._lock:
            return self._costs_by_source.get(source_id, 0.0)

    def dropped_groups_for(self, source_id: str) -> int:
        """Nombre de slides ignorées par les plafonds pour une source.

        Args:
            source_id: Identifiant de la source.

        Returns:
            Le nombre de groupes ignorés (0 si détection stable).
        """
        with self._lock:
            return self._dropped_by_source.get(source_id, 0)
```

Nota imports : vérifier les chemins réels de `map_bounded`/`PauseToken`
(`fahmi2.core.concurrency` exporte-t-il les deux ? sinon importer depuis les
sous-modules comme le fait `pipeline/engine.py`) et de
`with_retry`/`RetryPolicy`/`default_classify` (mêmes imports que
`pedagogy/generators/_base.py`).

- [ ] **Étape 4 : vérifier** — Run :
`.venv\Scripts\python.exe -m pytest tests/unit/infra/vision -v` → PASS.

- [ ] **Étape 5 : commit**

```bash
git add -A && git commit -m "feat(vision): façade SlideAnalyzer — extraction + vision parallélisée + coûts per-source"
```

---

### Tâche 8 : Ingestion — protocole, `MediaIngestor`, `YoutubeIngestor`, dispatcher, fakes

**Files:**
- Modify: `src/fahmi2/infra/ingestion/interface.py` (`IngestionDeps` + protocole)
- Modify: `src/fahmi2/infra/ingestion/media_ingestor.py`
- Modify: `src/fahmi2/infra/ingestion/document_ingestor.py` (kwarg ignoré)
- Modify: `src/fahmi2/infra/ingestion/youtube_downloader.py` (+ `download_video`)
- Modify: `src/fahmi2/infra/ingestion/youtube_ingestor.py`
- Modify: `src/fahmi2/infra/ingestion/dispatcher.py` (pass-through du kwarg)
- Modify: `src/fahmi2/infra/ingestion/_fakes.py` (signatures)
- Test: `tests/unit/infra/ingestion/test_media_ingestor.py`,
  `tests/unit/infra/ingestion/test_youtube_ingestor.py`

**Interfaces:**
- Consumes: `SlideAnalyzer` (T7), `merge_slides_into_transcription` (T6).
- Produces: `IngestionDeps(..., slide_analyzer: SlideAnalyzer | None = None)` ;
  `SourceIngestor.ingest(..., analyze_slides: bool = False)` (protocole,
  dispatcher et les 3 ingesteurs) ;
  `YoutubeDownloader.download_video(url, dest_dir, stem) -> Path`.

- [ ] **Étape 1 : tests (échec attendu)**

Ajouter à `tests/unit/infra/ingestion/test_media_ingestor.py` (réutiliser
les fakes/fixtures existants du fichier pour `deps` ; adapter les noms) :

```python
def test_video_avec_slides_fusionne_le_contenu(tmp_path, ...) -> None:
    """analyze_slides=True + vidéo : les segments slides sont intercalés."""
    # deps avec slide_analyzer stub renvoyant 1 AnalyzedSlide non vide
    # (utiliser un stub minimal conforme au duck-typing de SlideAnalyzer :
    #  méthode analyze(...) -> SlideAnalysisReport)
    ...
    transcription = ingestor.ingest(
        source_video, "src-1", deps, language_hint=None,
        delete_audio_after=False, analyze_slides=True,
    )
    assert any(s.text.startswith("[Slide") for s in transcription.segments)


def test_video_sans_option_ignore_les_slides(...) -> None:
    """analyze_slides=False : le slide_analyzer n'est jamais appelé."""


def test_audio_avec_option_ignore_les_slides(...) -> None:
    """Une source AUDIO n'est jamais analysée même avec analyze_slides=True."""


def test_option_sans_analyzer_disponible(...) -> None:
    """slide_analyzer=None (pas de clé OpenAI) : transcription inchangée."""
```

Écrire ces 4 tests **complets** en s'appuyant sur les doubles existants du
fichier (`FakeSTTProvider`, ffmpeg fake) ; le stub analyzer :

```python
class _StubSlideAnalyzer:
    def __init__(self, slides: tuple[AnalyzedSlide, ...]) -> None:
        self._slides = slides
        self.calls: list[str] = []

    def analyze(self, video_path, source_id, *, workspace, language, duration_seconds):
        self.calls.append(source_id)
        return SlideAnalysisReport(slides=self._slides, cost_usd=0.01, dropped_groups=0)

    def consumed_cost_usd_for(self, source_id: str) -> float:
        return 0.01 if source_id in self.calls else 0.0

    def dropped_groups_for(self, source_id: str) -> int:
        return 0
```

Ajouter à `tests/unit/infra/ingestion/test_youtube_ingestor.py` :

```python
def test_youtube_avec_slides_telecharge_la_video(...) -> None:
    """analyze_slides=True : download_video est appelé (pas download_audio)
    et la source déléguée au MediaIngestor est de kind VIDEO."""


def test_youtube_sans_slides_telecharge_l_audio(...) -> None:
    """Comportement historique préservé (download_audio)."""
```

(Compléter avec le fake downloader existant du fichier, en lui ajoutant
`download_video` qui enregistre l'appel et écrit un fichier factice.)

- [ ] **Étape 2 : vérifier l'échec** — Run :
`.venv\Scripts\python.exe -m pytest tests/unit/infra/ingestion -v` → FAIL
(TypeError sur `analyze_slides`).

- [ ] **Étape 3 : implémenter**

`interface.py` — `IngestionDeps` gagne (import sous `TYPE_CHECKING` pour
éviter un cycle si nécessaire, sinon import direct) :

```python
    slide_analyzer: SlideAnalyzer | None = None
```

(docstring : « Analyseur de slides (``None`` = option indisponible — pas de
clé OpenAI). ») et le protocole `SourceIngestor.ingest` gagne le paramètre
keyword documenté :

```python
        analyze_slides: bool = False,
```

`media_ingestor.py` :

```python
from fahmi2.infra.ingestion.slide_merge import merge_slides_into_transcription

    def ingest(
        self,
        source: InputSource,
        source_id: str,
        deps: IngestionDeps,
        *,
        language_hint: Language | None,
        delete_audio_after: bool,
        analyze_slides: bool = False,
    ) -> Transcription:
        audio_path = deps.workspace / _AUDIO_SUBDIR / f"{source_id}{_AUDIO_EXTENSION}"
        try:
            deps.ffmpeg.extract(source.as_path, audio_path)
            transcription = deps.stt_provider.transcribe(
                audio_path, language_hint=language_hint
            )
        finally:
            if delete_audio_after:
                safe_delete(audio_path)
        if (
            analyze_slides
            and source.kind is SourceKind.VIDEO
            and deps.slide_analyzer is not None
        ):
            report = deps.slide_analyzer.analyze(
                source.as_path,
                source_id,
                workspace=deps.workspace,
                language=transcription.detected_language,
                duration_seconds=transcription.duration_seconds,
            )
            transcription = merge_slides_into_transcription(
                transcription, report.slides
            )
        return transcription
```

(Mettre à jour la docstring : `analyze_slides` + `Raises: VisionError`.)

`youtube_downloader.py` — constante + méthode protocole + adapter. Format
**progressif** ≤ 720p (un seul fichier, pas de merge nécessitant
`--ffmpeg-location`) :

```python
_VIDEO_FORMAT_720P = "best[height<=720][ext=mp4]/best[height<=720]/best"
```

Protocole : ajouter `download_video(self, url: str, dest_dir: Path, stem:
str) -> Path` (docstring parallèle à `download_audio`). Adapter : factoriser
le corps de `download_audio` en

```python
    def _download(self, url: str, dest_dir: Path, stem: str, fmt: str) -> Path:
        # corps actuel de download_audio avec ``fmt`` à la place de
        # _BESTAUDIO_FORMAT (messages d'erreur inchangés)
```

puis :

```python
    def download_audio(self, url: str, dest_dir: Path, stem: str) -> Path:
        return self._download(url, dest_dir, stem, _BESTAUDIO_FORMAT)

    def download_video(self, url: str, dest_dir: Path, stem: str) -> Path:
        return self._download(url, dest_dir, stem, _VIDEO_FORMAT_720P)
```

`youtube_ingestor.py` :

```python
    def ingest(
        self,
        source: InputSource,
        source_id: str,
        deps: IngestionDeps,
        *,
        language_hint: Language | None,
        delete_audio_after: bool,
        analyze_slides: bool = False,
    ) -> Transcription:
        downloads_dir = deps.workspace / _DOWNLOADS_SUBDIR
        with_slides = analyze_slides and deps.slide_analyzer is not None
        if with_slides:
            downloaded = self._downloader.download_video(
                source.location, downloads_dir, source_id
            )
            media_kind = SourceKind.VIDEO
        else:
            downloaded = self._downloader.download_audio(
                source.location, downloads_dir, source_id
            )
            media_kind = SourceKind.AUDIO
        try:
            media_source = InputSource(kind=media_kind, location=str(downloaded))
            return self._media_ingestor.ingest(
                media_source,
                source_id,
                deps,
                language_hint=language_hint,
                delete_audio_after=delete_audio_after,
                analyze_slides=with_slides,
            )
        finally:
            safe_delete(downloaded)
```

`document_ingestor.py` : ajouter `analyze_slides: bool = False` à la
signature, `del analyze_slides` (ou commentaire « ignoré : un document n'a
pas de slides ») + docstring. `dispatcher.py` : ajouter le kwarg à
`IngestionDispatcher.ingest` et le transmettre. `_fakes.py` : aligner les
signatures des fakes d'ingesteurs.

- [ ] **Étape 4 : vérifier** — Run :
`.venv\Scripts\python.exe -m pytest tests/unit/infra/ingestion -v` → PASS.

- [ ] **Étape 5 : commit**

```bash
git add -A && git commit -m "feat(ingestion): option analyze_slides — MediaIngestor fusionne les slides, YouTube télécharge la vidéo 720p"
```

---

### Tâche 9 : Phase 0 + événement d'avertissement + DI contrôleur

**Files:**
- Modify: `src/fahmi2/pipeline/events.py` (+ `SlideDetectionWarning` + union)
- Modify: `src/fahmi2/pipeline/phase_handler.py` (`PhaseContext.slide_analyzer`)
- Modify: `src/fahmi2/pipeline/handlers/phase_0_stt.py`
- Modify: `src/fahmi2/ui/generation_controller.py` (DI + `_validate_keys` +
  `_to_log_event`)
- Test: `tests/unit/pipeline/handlers/test_phase_0_stt.py`

**Interfaces:**
- Consumes: `SlideAnalyzer` (T7), `analyze_slides` (T8),
  `GenerationSettings.slides_sources` (T1).
- Produces: `PhaseContext.slide_analyzer: SlideAnalyzer | None = None` ;
  événement `SlideDetectionWarning(run_id, source_id, dropped_groups,
  timestamp)` dans l'union `PipelineEvent` ;
  `build_slide_frame_extractor_from_runtime()` n'existe pas — le contrôleur
  construit `SlideFrameExtractor(ffmpeg_binary=resolve_ffmpeg_binary_or_none())`.

- [ ] **Étape 1 : tests du handler (échec attendu)**

Ajouter à `tests/unit/pipeline/handlers/test_phase_0_stt.py` (réutiliser la
fabrique de `PhaseContext` du fichier ; la compléter d'un paramètre
`slide_analyzer`) :

```python
def test_phase0_active_les_slides_pour_la_source_flaggee(...) -> None:
    """order_key ∈ slides_sources : l'ingest reçoit analyze_slides=True et le
    coût vision per-source s'ajoute au coût STT de la PhaseExecution."""
    # settings = make_generation_settings(slides_sources=("video.mp4",))
    # dispatcher fake qui enregistre analyze_slides
    # slide_analyzer stub : consumed_cost_usd_for("...") == 0.05, dropped == 0
    # asserts : dispatcher.last_analyze_slides is True
    #           execution.cost_usd == cout_stt + 0.05


def test_phase0_sans_flag_pas_d_analyse(...) -> None:
    """order_key ∉ slides_sources : analyze_slides=False, coût STT seul."""


def test_phase0_publie_l_avertissement_detection_instable(...) -> None:
    """dropped_groups > 0 : un SlideDetectionWarning est publié sur le bus."""
```

Écrire ces tests complets sur le modèle des tests existants du fichier
(fakes de dispatcher/STT déjà présents).

- [ ] **Étape 2 : vérifier l'échec** — Run :
`.venv\Scripts\python.exe -m pytest tests/unit/pipeline/handlers/test_phase_0_stt.py -v` → FAIL.

- [ ] **Étape 3 : implémenter**

`pipeline/events.py` — après `RetryAttempt` :

```python
@dataclass(frozen=True)
class SlideDetectionWarning:
    """Avertit d'une détection de slides instable pour une source (phase 0).

    Attributes:
        run_id: Run concerné.
        source_id: Source dont la détection a atteint les plafonds.
        dropped_groups: Nombre de slides ignorées (coût borné, contenu perdu).
        timestamp: Horodatage de l'événement.
    """

    run_id: RunId
    source_id: SourceId
    dropped_groups: int
    timestamp: datetime
```

et l'ajouter à l'union `PipelineEvent`.

`pipeline/phase_handler.py` — import (`from fahmi2.infra.vision.slide_analyzer
import SlideAnalyzer`) + champ en fin de `PhaseContext` :

```python
    slide_analyzer: SlideAnalyzer | None = None
```

(+ ligne `Attributes`). Les champs existants n'ayant pas de défaut, l'ajout
en fin avec défaut ne casse aucun appel positionnel.

`handlers/phase_0_stt.py` — dans `execute` :

```python
        analyze_slides = source.source.order_key() in ctx.settings.slides_sources
        deps = IngestionDeps(
            workspace=ctx.workspace,
            artifacts=ctx.artifacts,
            stt_provider=ctx.stt_provider,
            ffmpeg=ctx.ffmpeg,
            slide_analyzer=ctx.slide_analyzer,
        )
        transcription = ctx.ingestion.ingest(
            source.source,
            source.source_id.value,
            deps,
            language_hint=ctx.settings.source_language,
            delete_audio_after=ctx.settings.delete_audio_after_stt,
            analyze_slides=analyze_slides,
        )
        cost = ctx.stt_provider.estimate_cost(transcription.duration_seconds)
        if analyze_slides and ctx.slide_analyzer is not None:
            cost += ctx.slide_analyzer.consumed_cost_usd_for(source.source_id.value)
            dropped = ctx.slide_analyzer.dropped_groups_for(source.source_id.value)
            if dropped > 0:
                ctx.event_bus.publish(
                    SlideDetectionWarning(
                        run_id=ctx.run.id,
                        source_id=source.source_id,
                        dropped_groups=dropped,
                        timestamp=datetime.now(tz=UTC),
                    )
                )
```

`ui/generation_controller.py` :

1. `_validate_keys` — remplacer la condition :

```python
        needs_openai = (
            project.generation.stt_provider is SttProvider.OPENAI_CLOUD
            or bool(project.generation.slides_sources)
        )
```

et enrichir le message existant de la clé manquante (« … requis par le STT
cloud ou l'analyse des slides. »).

2. Nouvelle méthode privée :

```python
    def _build_slide_analyzer(self, project: Project) -> SlideAnalyzer | None:
        """Construit l'analyseur de slides si l'option est activée.

        Args:
            project: Projet en cours (settings génération non ``None``).

        Returns:
            La façade configurée, ou ``None`` si aucune source n'a l'option.
        """
        from fahmi2.core.config.paths import (  # noqa: PLC0415 — éviter cycle
            resolve_ffmpeg_binary_or_none,
        )

        settings = project.generation
        if settings is None or not settings.slides_sources:
            return None
        vision = OpenAIVisionAdapter(
            api_key=self._secrets_service.get_openai_api_key(),
            prompts=PromptLoader(override_dir=self._app_paths.prompts_override_dir),
            model=str(settings.vision_model),
        )
        return SlideAnalyzer(
            frame_extractor=SlideFrameExtractor(
                ffmpeg_binary=resolve_ffmpeg_binary_or_none()
            ),
            vision_provider=vision,
            llm_workers=settings.parallelism.llm_workers,
            pause_token=self._current_pause_token,
        )
```

3. Construction du `PhaseContext` (~ligne 601) : ajouter
`slide_analyzer=self._build_slide_analyzer(self._current_project),`.

4. `_to_log_event` — avant le fallback :

```python
    if isinstance(event, SlideDetectionWarning):
        return LogEvent(
            timestamp=event.timestamp,
            severity=Severity.WARNING,
            code="SLIDES_DETECTION_UNSTABLE",
            message=(
                f"Détection de slides instable pour la source "
                f"{event.source_id.value[:8]}… : {event.dropped_groups} "
                f"image(s) ignorée(s) par les plafonds (coût borné ; contenu "
                f"de slides potentiellement incomplet)."
            ),
            run_id=event.run_id.value,
            source_id=event.source_id.value,
            extra={"dropped_groups": event.dropped_groups},
        )
```

(Vérifier la signature réelle de `LogEvent` — `source_id`/`extra` — et
s'aligner.)

- [ ] **Étape 4 : vérifier** — Run :
`.venv\Scripts\python.exe -m pytest tests/unit/pipeline tests/unit/ui -v` → PASS.

- [ ] **Étape 5 : commit**

```bash
git add -A && git commit -m "feat(pipeline): phase 0 — analyse des slides per-source, coût vision attribué, avertissement détection instable"
```

---

### Tâche 10 : Coûts — `SourceWeight.slide_count`, poste vision, contrôleur

**Files:**
- Modify: `src/fahmi2/app/_cost_common.py` (2 constantes)
- Modify: `src/fahmi2/app/cost_estimator.py`
- Modify: `src/fahmi2/ui/generation_controller.py` (`_source_weight` + appel `estimate`)
- Test: `tests/unit/app/test_cost_estimator.py`

**Interfaces:**
- Consumes: `estimated_cost_per_slide_usd` (T2), `VisionModel` (T1).
- Produces: `SourceWeight(..., slide_count: float = 0.0)` ;
  `CostEstimator.estimate(..., vision_model: VisionModel =
  VisionModel.GPT_5_MINI)` ; `CostEstimation.vision_usd: float` (inclus dans
  `total_usd` et dans `per_phase_usd[PhaseId.STT]`) ; constantes
  `ESTIMATED_SLIDES_PER_MINUTE = 1.0` et `SLIDE_TEXT_TOKENS_PER_SLIDE = 250`
  dans `_cost_common`.

- [ ] **Étape 1 : tests (échec attendu)**

Ajouter à `tests/unit/app/test_cost_estimator.py` :

```python
def test_estimate_ajoute_le_poste_vision() -> None:
    """slide_count > 0 : vision_usd > 0, inclus dans total et phase 0."""
    with_slides = CostEstimator().estimate(
        source_weights=[SourceWeight(audio_seconds=600.0, text_tokens=0.0, slide_count=10.0)],
        stt_provider=SttProvider.FASTER_WHISPER_LOCAL,
        llm_model=LLMModel.DEEPSEEK_CHAT,
    )
    without = CostEstimator().estimate(
        source_weights=[SourceWeight(audio_seconds=600.0, text_tokens=0.0)],
        stt_provider=SttProvider.FASTER_WHISPER_LOCAL,
        llm_model=LLMModel.DEEPSEEK_CHAT,
    )
    assert with_slides.vision_usd > 0.0
    assert without.vision_usd == 0.0
    assert with_slides.total_usd > without.total_usd
    assert (
        with_slides.per_phase_usd[PhaseId.STT]
        > without.per_phase_usd[PhaseId.STT]
    )


def test_estimate_slides_grossissent_le_volume_aval() -> None:
    """Le texte des slides augmente le coût LLM (phases 1/3/4/5)."""
    with_slides = CostEstimator().estimate(
        source_weights=[SourceWeight(audio_seconds=600.0, text_tokens=0.0, slide_count=10.0)],
        stt_provider=SttProvider.FASTER_WHISPER_LOCAL,
        llm_model=LLMModel.DEEPSEEK_CHAT,
    )
    without = CostEstimator().estimate(
        source_weights=[SourceWeight(audio_seconds=600.0, text_tokens=0.0)],
        stt_provider=SttProvider.FASTER_WHISPER_LOCAL,
        llm_model=LLMModel.DEEPSEEK_CHAT,
    )
    assert with_slides.llm_usd > without.llm_usd
```

(Aligner `LLMModel.DEEPSEEK_CHAT` sur le membre réel de l'enum utilisé dans
les tests existants du fichier.)

- [ ] **Étape 2 : vérifier l'échec** — Run :
`.venv\Scripts\python.exe -m pytest tests/unit/app/test_cost_estimator.py -v` → FAIL.

- [ ] **Étape 3 : implémenter**

`app/_cost_common.py` :

```python
#: Slides estimées par minute de vidéo (estimation pré-run, cours typique).
ESTIMATED_SLIDES_PER_MINUTE = 1.0
#: Tokens de texte injectés dans la transcription par slide analysée
#: (grossit le volume d'entrée des phases LLM aval).
SLIDE_TEXT_TOKENS_PER_SLIDE = 250.0
```

`app/cost_estimator.py` :
- `SourceWeight` : champ `slide_count: float = 0.0` + docstring.
- `_base_tokens` : `return audio_tokens + weight.text_tokens +
  weight.slide_count * SLIDE_TEXT_TOKENS_PER_SLIDE`.
- `CostEstimation` : champ `vision_usd: float` (+ docstring ; passer tous
  les sites de construction).
- `estimate(...)` : paramètre `vision_model: VisionModel =
  VisionModel.GPT_5_MINI` ; calcul :

```python
        total_slides = sum(w.slide_count for w in source_weights)
        vision_cost = total_slides * estimated_cost_per_slide_usd(str(vision_model))
```

puis `per_phase_usd[PhaseId.STT] = stt_cost + vision_cost`, `total_usd`
(et la fourchette `cost_range`) incluant `vision_cost`, champ
`vision_usd=vision_cost`.

`ui/generation_controller.py` :
- `_source_weight` : calculer le nombre de slides estimé quand la clé est
  flaggée —

```python
def _estimated_slide_count(
    source: SourceExecution, audio_seconds: float, settings: GenerationSettings
) -> float:
    """Nombre de slides estimé pour l'option « analyser les slides ».

    Args:
        source: Source évaluée.
        audio_seconds: Durée audio estimée de la source.
        settings: Réglages (liste des sources flaggées).

    Returns:
        ``durée × ESTIMATED_SLIDES_PER_MINUTE`` si la source est flaggée,
        0 sinon.
    """
    if source.source.order_key() not in settings.slides_sources:
        return 0.0
    return audio_seconds / 60.0 * ESTIMATED_SLIDES_PER_MINUTE
```

et passer `slide_count=_estimated_slide_count(source, duration, settings)`
dans les branches YOUTUBE et VIDEO/AUDIO (un AUDIO n'est jamais flaggé côté
UI ; la fonction renvoie 0 par construction si la clé n'y est pas).
- Appel `estimate(...)` (~ligne 802) : ajouter
  `vision_model=settings.vision_model,`.

- [ ] **Étape 4 : vérifier** — Run :
`.venv\Scripts\python.exe -m pytest tests/unit/app -v` → PASS.

- [ ] **Étape 5 : commit**

```bash
git add -A && git commit -m "feat(coûts): poste vision dans l'estimation (slide_count, vision_model, volume aval)"
```

---

### Tâche 11 : UI — cases « slides » dans `SourceOrderView`, combo modèle vision, persistance

**Files:**
- Modify: `src/fahmi2/ui/widgets/source_order_view.py`
- Modify: `src/fahmi2/ui/_model_labels.py` (+ `vision_model_labels`)
- Modify: `src/fahmi2/ui/dialogs/generation_settings_view.py`
- Test: `tests/unit/ui/test_source_order_view.py`

**Interfaces:**
- Consumes: `VisionModel` (T1), `GenerationSettings.slides_sources` (T1).
- Produces: `SourceOrderView.populate(..., slides: Sequence[str] = ())` et
  `SourceOrderView.slides_sources() -> tuple[str, ...]` ;
  `vision_model_labels() -> dict[VisionModel, str]`.

- [ ] **Étape 1 : tests du widget (échec attendu)**

Ajouter à `tests/unit/ui/test_source_order_view.py` (style pytest-qt du
fichier) :

```python
def test_case_slides_cochable_uniquement_video_youtube(qtbot) -> None:
    view = SourceOrderView()
    qtbot.addWidget(view)
    sources = [
        InputSource(SourceKind.VIDEO, "a.mp4"),
        InputSource(SourceKind.AUDIO, "b.mp3"),
        InputSource(SourceKind.YOUTUBE, "https://youtu.be/x"),
        InputSource(SourceKind.DOCUMENT, "c.pdf"),
    ]
    view.populate(
        sources,
        included=["a.mp4", "b.mp3", "https://youtu.be/x", "c.pdf"],
        excluded=[],
        known=set(),
        slides=["a.mp4"],
    )
    assert view.slides_sources() == ("a.mp4",)
    video_item = view._included.item(0)
    audio_item = view._included.item(1)
    assert video_item.flags() & Qt.ItemFlag.ItemIsUserCheckable
    assert not (audio_item.flags() & Qt.ItemFlag.ItemIsUserCheckable)
    assert video_item.checkState() == Qt.CheckState.Checked


def test_cocher_une_video_l_ajoute_aux_slides(qtbot) -> None:
    view = SourceOrderView()
    qtbot.addWidget(view)
    view.populate(
        [InputSource(SourceKind.YOUTUBE, "https://youtu.be/x")],
        included=["https://youtu.be/x"],
        excluded=[],
        known=set(),
        slides=[],
    )
    view._included.item(0).setCheckState(Qt.CheckState.Checked)
    assert view.slides_sources() == ("https://youtu.be/x",)
```

- [ ] **Étape 2 : vérifier l'échec** — Run :
`.venv\Scripts\python.exe -m pytest tests/unit/ui/test_source_order_view.py -v` → FAIL.

- [ ] **Étape 3 : implémenter**

`source_order_view.py` :
- Docstring module : mentionner la case « analyser les slides ».
- Constante `_SLIDES_KINDS: Final[frozenset[SourceKind]] =
  frozenset({SourceKind.VIDEO, SourceKind.YOUTUBE})`.
- État : `self._slides: set[str] = set()` dans `__init__`.
- `populate(..., slides: Sequence[str] = ())` : `self._slides = set(slides)`
  avant le remplissage.
- `_make_item` :

```python
        item = QListWidgetItem(f"[{_KIND_LABELS[kind]}] {key}{badge}")
        item.setData(_KEY_ROLE, key)
        if kind in _SLIDES_KINDS:
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                Qt.CheckState.Checked
                if key in self._slides
                else Qt.CheckState.Unchecked
            )
            item.setToolTip(
                self.tr(
                    "Analyser les slides/illustrations de cette vidéo "
                    "(modèle vision OpenAI — clé OpenAI requise)"
                )
            )
        return item
```

- Nouvelle API :

```python
    def slides_sources(self) -> tuple[str, ...]:
        """Clés des sources dont la case « analyser les slides » est cochée."""
        keys: list[str] = []
        for widget in (self._included, self._excluded):
            for i in range(widget.count()):
                item = widget.item(i)
                if item is not None and item.checkState() is Qt.CheckState.Checked:
                    keys.append(str(item.data(_KEY_ROLE)))
        return tuple(keys)
```

- Note d'aide dans `_build_layout`, sous le titre de la liste des incluses :

```python
        self._slides_hint = QLabel(
            self.tr(
                "☑ sur une vidéo/YouTube = analyser ses slides "
                "(contenu intégré à la synthèse ; clé OpenAI requise)"
            ),
            self,
        )
        self._slides_hint.setWordWrap(True)
```

(ajouté au layout après la liste des incluses).

`ui/_model_labels.py` — sur le modèle exact de `_CLOUD_STT_MODEL_SOURCES` /
`cloud_stt_model_labels` (même contexte de traduction `_tr`) :

```python
_VISION_MODEL_SOURCES: dict[VisionModel, str] = {
    VisionModel.GPT_5_MINI: QT_TRANSLATE_NOOP(
        "ModelLabels", "gpt-5-mini — recommandé (meilleur rapport qualité/prix)"
    ),
    VisionModel.GPT_5_NANO: QT_TRANSLATE_NOOP(
        "ModelLabels", "gpt-5-nano — économique (slides simples)"
    ),
    VisionModel.GPT_5_4_MINI: QT_TRANSLATE_NOOP(
        "ModelLabels", "gpt-5.4-mini — qualité supérieure (slides denses)"
    ),
}


def vision_model_labels() -> dict[VisionModel, str]:
    """Libellés traduits des modèles vision (analyse des slides)."""
    return {model: _tr(source) for model, source in _VISION_MODEL_SOURCES.items()}
```

(Aligner le nom de contexte `"ModelLabels"` sur celui réellement utilisé
dans le module.)

`generation_settings_view.py` :
- `_build_stt_fields` : `self._vision_model_combo = labeled_enum_combo(self,
  vision_model_labels())`.
- Dans la carte des modèles (~ligne 510) :
  `model_form.addRow(self.tr("Modèle vision (slides)"), self._vision_model_combo)`.
- Chargement (~ligne 736) :

```python
        vision_idx = self._vision_model_combo.findData(generation.vision_model)
        if vision_idx >= 0:
            self._vision_model_combo.setCurrentIndex(vision_idx)
```

- `_refresh_source_order` : paramètre `slides: Sequence[str] | None = None`,
  défaut `self._source_order_view.slides_sources()` (même logique que
  `order`/`excl`), et passage `slides=...` à `populate`. Au chargement
  initial des settings, appeler avec `slides=generation.slides_sources`.
- Sauvegarde (~ligne 798) :

```python
            slides_sources=self._source_order_view.slides_sources(),
            vision_model=VisionModel(self._vision_model_combo.currentData()),
```

- [ ] **Étape 4 : vérifier** — Run :
`.venv\Scripts\python.exe -m pytest tests/unit/ui -v` → PASS.

- [ ] **Étape 5 : commit**

```bash
git add -A && git commit -m "feat(ui): case « analyser les slides » par source + sélecteur du modèle vision"
```

---

### Tâche 12 : i18n — extraction, traductions EN, compilation, garde-fous

**Files:**
- Modify: `src/fahmi2/i18n/translations/fahmi2_en.ts` (via extraction puis édition)
- Modify: `tests/unit/i18n/test_i18n.py`

**Interfaces:**
- Consumes: toutes les chaînes `self.tr()`/`QT_TRANSLATE_NOOP` ajoutées
  (T9 : message clé OpenAI enrichi ; T11 : tooltip, hint, ligne de
  formulaire, libellés modèles vision).

- [ ] **Étape 1 : extraire les sources**

Run : `.venv\Scripts\python.exe scripts\i18n_extract.py`
Attendu : `fahmi2_en.ts` contient les nouvelles entrées `<message>` non
traduites (`type="unfinished"`).

- [ ] **Étape 2 : traduire en anglais**

Éditer `fahmi2_en.ts` — remplir `<translation>` pour chaque nouvelle chaîne :

| Source FR | Traduction EN |
|---|---|
| `Analyser les slides/illustrations de cette vidéo (modèle vision OpenAI — clé OpenAI requise)` | `Analyze this video's slides/illustrations (OpenAI vision model — OpenAI key required)` |
| `☑ sur une vidéo/YouTube = analyser ses slides (contenu intégré à la synthèse ; clé OpenAI requise)` | `☑ on a video/YouTube source = analyze its slides (content merged into the synthesis; OpenAI key required)` |
| `Modèle vision (slides)` | `Vision model (slides)` |
| `gpt-5-mini — recommandé (meilleur rapport qualité/prix)` | `gpt-5-mini — recommended (best quality/price ratio)` |
| `gpt-5-nano — économique (slides simples)` | `gpt-5-nano — budget (simple slides)` |
| `gpt-5.4-mini — qualité supérieure (slides denses)` | `gpt-5.4-mini — higher quality (dense slides)` |
| (message clé OpenaI enrichi de `_validate_keys`, texte exact selon T9) | traduction correspondante |

- [ ] **Étape 3 : compiler**

Run : `.venv\Scripts\python.exe scripts\i18n_compile.py`
Attendu : `src/fahmi2/i18n/compiled/fahmi2_en.qm` régénéré sans erreur.

- [ ] **Étape 4 : garde-fous**

Ajouter à la paramétrisation de `tests/unit/i18n/test_i18n.py` (suivre le
format exact des entrées existantes — contexte, source FR, attendu EN) au
moins : le tooltip de la case slides (`SourceOrderView`), la ligne « Modèle
vision (slides) » (`GenerationSettingsView`) et un libellé de modèle vision
(`ModelLabels`).

Run : `.venv\Scripts\python.exe -m pytest tests/unit/i18n -v` → PASS.

- [ ] **Étape 5 : commit**

```bash
git add -A && git commit -m "i18n: traductions EN des chaînes de l'analyse des slides + garde-fous"
```

---

### Tâche 13 : Documentation + vérification finale

**Files:**
- Modify: `CLAUDE.md` (section « Cross-cutting mechanisms » : nouveau point
  **Slide analysis** ; arborescence `infra/` : `video/`, `vision/`,
  `slide_merge`, prompt `phase_0_slide_analysis`, événement
  `SlideDetectionWarning`, enum `VisionModel`)
- Modify: `README.md` (fonctionnalité côté utilisateur, en anglais)
- Modify: `packaging/README.md` (note : prompt couvert par le glob des
  defaults existant du `.spec` ; **vérifier** que le `.spec` local bundle
  bien `infra/prompts/defaults/*.j2` par glob — sinon le patcher localement
  et le noter)

- [ ] **Étape 1 : documenter** — CLAUDE.md (en anglais, style des points
  existants) : option per-source, chaîne ffmpeg → tuiles 2 passes → vision →
  fusion, garde-fous (plafonds, dédoublonnage, masque de bruit), coût
  (poste vision + `SLIDE_TEXT_TOKENS_PER_SLIDE`), YouTube 720p progressif,
  précondition clé OpenAI, latin/CJK sans restriction (la langue de sortie
  vision = langue détectée). README.md : paragraphe utilisateur. Mettre à
  jour la ligne « prompts » du CLAUDE.md (le catalogue passe à « 8 phases +
  3 thematic + **1 slide-analysis** + 8 pedagogy + 3 chat + 5 visuals »).

- [ ] **Étape 2 : vérification finale complète (répéter jusqu'à zéro défaut)**

```powershell
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m mypy src tests
```

Attendu : suite entière verte, ruff sans erreur, mypy strict sans erreur.
Relancer `pytest` 3 fois (stabilité, convention du projet).

- [ ] **Étape 3 : commit final**

```bash
git add -A && git commit -m "docs: analyse des slides — CLAUDE.md, README, note packaging"
```

---

## Auto-revue du plan (faite à la rédaction)

- **Couverture spec** : option per-source (T1, T11), extraction/tuiles/2
  passes/plafonds/dédoublonnage (T4, T5), vision + prompt + JSON mode +
  retry (T3, T7), fusion horodatée + slide vide + `h:mm:ss` (T6), YouTube
  720p (T8), précondition clé (T9), coût estimé + réel per-source (T9, T10),
  avertissement journalisé (T9), UI + i18n (T11, T12), docs (T13).
- **Écarts spec assumés** (documentés dans les tâches) : nom du prompt
  `phase_0_slide_analysis` (convention du catalogue) ; le port renvoie le
  coût **par appel** au lieu d'un cumul global (attribution per-source
  fiable sous parallélisme) ; l'avertissement passe par un nouvel événement
  `SlideDetectionWarning` (canal Logs existant).
- **Types cohérents** : `SlideContent`/`SlideAnalysis`/`AnalyzedSlide` (T2)
  consommés par T3/T6/T7 ; `SlideFrame`/`SlideExtractionResult` (T5) par
  T7 ; `SlideAnalysisReport` (T7) par T8/T9 ; `slides_sources`/`VisionModel`
  (T1) par T9/T10/T11.
