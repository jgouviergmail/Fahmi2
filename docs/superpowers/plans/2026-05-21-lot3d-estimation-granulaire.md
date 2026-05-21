# Lot 3d — Estimation granulaire + fourchette

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (inline, sans subagents).
> **Spec** : [`../specs/2026-05-21-dashboards-coherence-design.md`](../specs/2026-05-21-dashboards-coherence-design.md) §3.5.
> Steps en checkbox. Tout en français (accents). Travail directement sur `main`.

**Goal:** Estimation pré-run **granulaire** (par phase en génération ; par support
en pédagogie, déjà présent) avec **fourchette ±33 %** « indicative » sur le total et
**avertissement** si le haut de fourchette dépasse le plafond ; dialogues
d'estimation **harmonisés** (helper partagé).

**Architecture:** `_cost_common` gagne `ESTIMATE_UNCERTAINTY_RATIO` + `cost_range`.
`CostEstimator` expose `per_phase_usd` (refactor de `_llm_cost`). Les deux estimations
(`CostEstimation`, `PedagogyCostEstimation`) gagnent `low_usd`/`high_usd`. Un helper
UI partagé `show_cost_estimate` rend la décomposition + total à fourchette + plafond.

**Tech Stack:** Python 3.12, PySide6, pytest / pytest-qt.

---

## Task 1 : `_cost_common` — fourchette

**Files:**
- Modify : `src/fahmi2/app/_cost_common.py`
- Test : `tests/unit/app/test_cost_common.py` (créer)

- [ ] **Step 1 : test (échoue)**

Créer `tests/unit/app/test_cost_common.py` :

```python
"""Tests des helpers de coût partagés."""

from __future__ import annotations

import pytest

from fahmi2.app._cost_common import ESTIMATE_UNCERTAINTY_RATIO, cost_range


def test_cost_range_symmetric() -> None:
    low, high = cost_range(1.50)
    assert low == pytest.approx(1.50 * (1 - ESTIMATE_UNCERTAINTY_RATIO))
    assert high == pytest.approx(1.50 * (1 + ESTIMATE_UNCERTAINTY_RATIO))


def test_cost_range_zero() -> None:
    assert cost_range(0.0) == (0.0, 0.0)
```

- [ ] **Step 2 : échec**

Run : `.venv\Scripts\python.exe -m pytest tests/unit/app/test_cost_common.py -v`
Attendu : ÉCHEC (import).

- [ ] **Step 3 : implémenter**

Ajouter à `_cost_common.py` :

```python
#: Demi-largeur de la fourchette d'incertitude de l'estimation (±33 %).
#: Heuristique communiquée (« estimation indicative »), pas un intervalle statistique.
ESTIMATE_UNCERTAINTY_RATIO = 0.33


def cost_range(total_usd: float) -> tuple[float, float]:
    """Fourchette ``(bas, haut)`` autour d'un total à ``±ESTIMATE_UNCERTAINTY_RATIO``.

    Args:
        total_usd: Total estimé (ponctuel).

    Returns:
        ``(low, high)`` = ``(total*(1-r), total*(1+r))``.
    """
    return (
        total_usd * (1.0 - ESTIMATE_UNCERTAINTY_RATIO),
        total_usd * (1.0 + ESTIMATE_UNCERTAINTY_RATIO),
    )
```

- [ ] **Step 4 : succès + commit**

```powershell
.venv\Scripts\python.exe -m pytest tests/unit/app/test_cost_common.py -q
.venv\Scripts\python.exe -m ruff check . ; .venv\Scripts\python.exe -m mypy src tests
git add src/fahmi2/app/_cost_common.py tests/unit/app/test_cost_common.py
git commit -m @'
feat(app): cost_range + ESTIMATE_UNCERTAINTY_RATIO (fourchette +/-33%)

Helper partage de fourchette d'incertitude « indicative » pour les estimations.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
'@
```

---

## Task 2 : `CostEstimator` — décomposition par phase + fourchette

**Files:**
- Modify : `src/fahmi2/app/cost_estimator.py`
- Test : `tests/unit/app/test_cost_estimator.py`

- [ ] **Step 1 : tests (échouent)**

Ajouter à `tests/unit/app/test_cost_estimator.py` :

```python
def test_per_phase_breakdown_sums_to_total() -> None:
    est = CostEstimator().estimate(
        videos_durations_seconds=[600.0, 600.0],
        stt_provider=SttProvider.OPENAI_CLOUD,
        llm_model=LLMModel.DEEPSEEK_V4_FLASH,
        active_target_languages_count=1,
        translation_languages_count=0,
    )
    assert PhaseId.STT in est.per_phase_usd
    # STT + somme des phases LLM ~= total
    assert sum(est.per_phase_usd.values()) == pytest.approx(est.total_usd)
    assert est.per_phase_usd[PhaseId.STT] == pytest.approx(est.stt_usd)


def test_estimation_has_range() -> None:
    est = CostEstimator().estimate(
        videos_durations_seconds=[600.0],
        stt_provider=SttProvider.OPENAI_CLOUD,
        llm_model=LLMModel.DEEPSEEK_V4_FLASH,
    )
    assert est.low_usd < est.total_usd < est.high_usd
```

(Vérifier/compléter les imports du fichier : `pytest`, `PhaseId`, `SttProvider`,
`LLMModel`, `CostEstimator`.)

- [ ] **Step 2 : échec**

Run : `.venv\Scripts\python.exe -m pytest tests/unit/app/test_cost_estimator.py -k "per_phase or range" -v`
Attendu : ÉCHEC (`per_phase_usd`/`low_usd` absents).

- [ ] **Step 3 : implémenter**

Dans `cost_estimator.py` :

Imports : ajouter `cost_range` à l'import de `_cost_common`.

`CostEstimation` : ajouter les champs (après `total_audio_seconds`) :

```python
    per_phase_usd: dict[PhaseId, float]
    low_usd: float
    high_usd: float
```
et compléter la docstring (``per_phase_usd`` : coût estimé par phase, STT inclus ;
``low_usd``/``high_usd`` : fourchette ±33 %).

`estimate` : remplacer le calcul `llm_cost` + le `return` par :

```python
        llm_per_phase = self._llm_cost_per_phase(
            total_audio_seconds=total_audio_seconds,
            n_videos=n_videos,
            llm_model=llm_model,
            target_languages_count=active_target_languages_count,
            translation_languages_count=translation_languages_count,
            phases_config=phases_config or {},
        )
        llm_cost = sum(llm_per_phase.values())
        total = stt_cost + llm_cost
        low, high = cost_range(total)
        return CostEstimation(
            stt_usd=stt_cost,
            llm_usd=llm_cost,
            total_usd=total,
            total_audio_seconds=total_audio_seconds,
            per_phase_usd={PhaseId.STT: stt_cost, **llm_per_phase},
            low_usd=low,
            high_usd=high,
        )
```

Renommer `_llm_cost` en `_llm_cost_per_phase` et le faire **accumuler par phase**
dans un `dict[PhaseId, float]` au lieu d'un total scalaire : remplacer
`total = 0.0` / `total += …` / `return total` par
`per_phase: dict[PhaseId, float] = {}` ; chaque `+=` devient
`per_phase[phase_id] = per_phase.get(phase_id, 0.0) + …` (le sous-appel batch de la
phase 5 s'ajoute à la même clé `phase_id`) ; `return per_phase`.

- [ ] **Step 4 : succès**

Run : `.venv\Scripts\python.exe -m pytest tests/unit/app/test_cost_estimator.py -v`
Attendu : PASS (les tests existants + les 2 nouveaux).

- [ ] **Step 5 : Vérifs + commit**

```powershell
.venv\Scripts\python.exe -m pytest -q ; .venv\Scripts\python.exe -m ruff check . ; .venv\Scripts\python.exe -m mypy src tests
git add src/fahmi2/app/cost_estimator.py tests/unit/app/test_cost_estimator.py
git commit -m @'
feat(app): estimation generation par phase + fourchette

CostEstimation expose per_phase_usd (STT + phases LLM) et low_usd/high_usd
(+/-33%). _llm_cost refactore en _llm_cost_per_phase (dict).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
'@
```

---

## Task 3 : `PedagogyCostEstimation` — fourchette

**Files:**
- Modify : `src/fahmi2/app/pedagogy_cost_estimator.py`
- Test : `tests/unit/app/test_pedagogy_cost_estimator.py`

- [ ] **Step 1 : test (échoue)**

Ajouter à `tests/unit/app/test_pedagogy_cost_estimator.py` :

```python
def test_estimation_has_range(make_pedagogy_settings: Any) -> None:
    ped = make_pedagogy_settings(selected_supports=frozenset({SupportType.QCM}))
    est = PedagogyCostEstimator().estimate(
        pedagogy=ped, chapters_by_language={Language.FR: _chapters(3)}
    )
    assert est.low_usd < est.total_usd < est.high_usd
```

(Compléter l'import `SupportType` si nécessaire.)

- [ ] **Step 2 : échec**

Run : `.venv\Scripts\python.exe -m pytest tests/unit/app/test_pedagogy_cost_estimator.py -k range -v`
Attendu : ÉCHEC (`low_usd` absent).

- [ ] **Step 3 : implémenter**

Dans `pedagogy_cost_estimator.py` :

Imports : ajouter `cost_range` à l'import de `_cost_common`.

`PedagogyCostEstimation` : ajouter `low_usd: float` et `high_usd: float` (après
`chapters_total`) + docstring.

`estimate` : remplacer le `return` final par :

```python
        total = sum(per_support.values())
        low, high = cost_range(total)
        return PedagogyCostEstimation(
            per_support_usd=per_support,
            total_usd=total,
            chapters_total=chapters_total,
            low_usd=low,
            high_usd=high,
        )
```

- [ ] **Step 4 : succès + commit**

```powershell
.venv\Scripts\python.exe -m pytest tests/unit/app/test_pedagogy_cost_estimator.py -q
.venv\Scripts\python.exe -m pytest -q ; .venv\Scripts\python.exe -m ruff check . ; .venv\Scripts\python.exe -m mypy src tests
git add src/fahmi2/app/pedagogy_cost_estimator.py tests/unit/app/test_pedagogy_cost_estimator.py
git commit -m @'
feat(app): fourchette +/-33% sur l'estimation pedagogie

PedagogyCostEstimation expose low_usd/high_usd (cost_range partage).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
'@
```

---

## Task 4 : dialogue d'estimation harmonisé (helper partagé)

**Files:**
- Create : `src/fahmi2/ui/cost_estimate_dialog.py`
- Test : `tests/unit/ui/test_cost_estimate_dialog.py`
- Modify : `src/fahmi2/ui/generation_controller.py`
- Modify : `src/fahmi2/ui/pedagogy_controller.py`

- [ ] **Step 1 : test du rendu (échoue)**

Créer `tests/unit/ui/test_cost_estimate_dialog.py` :

```python
"""Tests du rendu des lignes du dialogue d'estimation partagé."""

from __future__ import annotations

from fahmi2.ui.cost_estimate_dialog import build_estimate_body


def test_body_includes_breakdown_total_and_range() -> None:
    body = build_estimate_body(
        header_lines=["<b>Projet :</b> P"],
        breakdown=[("STT", 0.18), ("Phase 1", 0.14)],
        total_usd=1.50,
        low_usd=1.00,
        high_usd=2.00,
        cost_ceiling_usd=None,
    )
    assert "STT" in body
    assert "≈ $1.50" in body
    assert "$1.00 – $2.00" in body
    assert "indicative" in body


def test_body_warns_when_high_exceeds_ceiling() -> None:
    body = build_estimate_body(
        header_lines=[],
        breakdown=[("STT", 0.18)],
        total_usd=1.50,
        low_usd=1.00,
        high_usd=2.00,
        cost_ceiling_usd=1.80,
    )
    assert "plafond" in body.lower()
    assert "dépasser" in body.lower() or "dépasse" in body.lower()
```

- [ ] **Step 2 : échec**

Run : `.venv\Scripts\python.exe -m pytest tests/unit/ui/test_cost_estimate_dialog.py -v`
Attendu : ÉCHEC (import).

- [ ] **Step 3 : implémenter le helper**

Créer `src/fahmi2/ui/cost_estimate_dialog.py` :

```python
"""Dialogue d'estimation de coût partagé (génération + pédagogie).

Rend une décomposition (par phase / par support) + un total à **fourchette**
(±33 %, format ``≈ $X`` + sous-info) + une ligne de plafond (marge ou avertissement
si le haut de fourchette dépasse le budget). Présentation unifiée des deux dialogues.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox, QWidget

_BREAKDOWN_DECIMALS = 4
_TOTAL_DECIMALS = 2
_RANGE_PCT = 33
_FOOTNOTE = (
    "<i>Estimation indicative basée sur des heuristiques DeepSeek (durées, "
    "tokens, multiplicateurs par phase et mode thinking). Fourchette ±33 %.</i>"
)
_GREEN = "#1a7f37"
_RED = "#cf222e"
_MUTED = "#57606a"


def build_estimate_body(
    *,
    header_lines: list[str],
    breakdown: list[tuple[str, float]],
    total_usd: float,
    low_usd: float,
    high_usd: float,
    cost_ceiling_usd: float | None,
) -> str:
    """Construit le corps HTML du dialogue d'estimation.

    Args:
        header_lines: Lignes d'en-tête (déjà formatées HTML).
        breakdown: Décomposition ``(libellé, coût ponctuel)``.
        total_usd: Total estimé (ponctuel).
        low_usd: Bas de fourchette.
        high_usd: Haut de fourchette.
        cost_ceiling_usd: Plafond éventuel.

    Returns:
        Corps HTML (lignes jointes par ``<br>``).
    """
    lines: list[str] = list(header_lines)
    if header_lines:
        lines.append("")
    lines.extend(
        f"<b>{label} :</b> ${cost:.{_BREAKDOWN_DECIMALS}f}" for label, cost in breakdown
    )
    lines.append("")
    lines.append(f"<b>Total estimé :</b> ≈ ${total_usd:.{_TOTAL_DECIMALS}f}")
    lines.append(
        f"<span style='color:{_MUTED};'>fourchette "
        f"${low_usd:.{_TOTAL_DECIMALS}f} – ${high_usd:.{_TOTAL_DECIMALS}f} "
        f"(±{_RANGE_PCT} %)</span>"
    )
    if cost_ceiling_usd is not None:
        lines.append(_ceiling_line(total_usd, high_usd, cost_ceiling_usd))
    return "<br>".join(lines) + "<br><br>" + _FOOTNOTE


def _ceiling_line(total_usd: float, high_usd: float, ceiling: float) -> str:
    """Ligne de plafond : marge sur le point estimé + avertissement fourchette.

    Args:
        total_usd: Total ponctuel.
        high_usd: Haut de fourchette.
        ceiling: Plafond.

    Returns:
        Ligne HTML.
    """
    margin = ceiling - total_usd
    if margin >= 0:
        base = (
            f"<b>Plafond :</b> ${ceiling:.2f} "
            f"<span style='color:{_GREEN};'>(marge ${margin:.2f})</span>"
        )
    else:
        base = (
            f"<b>Plafond :</b> ${ceiling:.2f} "
            f"<span style='color:{_RED};'>(dépassement ${-margin:.2f})</span>"
        )
    if high_usd > ceiling:
        base += (
            f"<br><span style='color:{_RED};'>⚠ le haut de fourchette "
            f"(${high_usd:.2f}) peut dépasser le plafond.</span>"
        )
    return base


def show_cost_estimate(
    parent: QWidget,
    *,
    title: str,
    header_lines: list[str],
    breakdown: list[tuple[str, float]],
    total_usd: float,
    low_usd: float,
    high_usd: float,
    cost_ceiling_usd: float | None,
) -> None:
    """Affiche le dialogue d'estimation (``QMessageBox`` RichText).

    Args:
        parent: Fenêtre parente.
        title: Titre de la fenêtre.
        header_lines: Lignes d'en-tête HTML.
        breakdown: Décomposition ``(libellé, coût)``.
        total_usd: Total ponctuel.
        low_usd: Bas de fourchette.
        high_usd: Haut de fourchette.
        cost_ceiling_usd: Plafond éventuel.
    """
    msg = QMessageBox(parent)
    msg.setWindowTitle(title)
    msg.setIcon(QMessageBox.Icon.Information)
    msg.setTextFormat(Qt.TextFormat.RichText)
    msg.setText(
        build_estimate_body(
            header_lines=header_lines,
            breakdown=breakdown,
            total_usd=total_usd,
            low_usd=low_usd,
            high_usd=high_usd,
            cost_ceiling_usd=cost_ceiling_usd,
        )
    )
    msg.exec()
```

- [ ] **Step 4 : succès du helper**

Run : `.venv\Scripts\python.exe -m pytest tests/unit/ui/test_cost_estimate_dialog.py -v`
Attendu : PASS (2 tests).

- [ ] **Step 5 : brancher la génération**

Dans `generation_controller.py`, remplacer le corps de `_show_cost_estimation_dialog`
par une délégation au helper (en construisant l'en-tête + la décomposition par
phase) :

```python
    from fahmi2.ui.cost_estimate_dialog import show_cost_estimate  # noqa: PLC0415

    duration_label = _format_duration_label(estimation.total_audio_seconds)
    header = [
        f"<b>Projet :</b> {project_name}",
        f"<b>Vidéos détectées :</b> {n_videos}",
        f"<b>Durée totale audio :</b> {duration_label}",
    ]
    breakdown = [
        (_PHASE_ESTIMATE_LABELS.get(phase_id, phase_id.value), cost)
        for phase_id, cost in estimation.per_phase_usd.items()
    ]
    show_cost_estimate(
        parent,
        title="Estimation du coût",
        header_lines=header,
        breakdown=breakdown,
        total_usd=estimation.total_usd,
        low_usd=estimation.low_usd,
        high_usd=estimation.high_usd,
        cost_ceiling_usd=cost_ceiling_usd,
    )
```

Ajouter en tête du module la table de libellés de phases (constante) :

```python
_PHASE_ESTIMATE_LABELS: dict[PhaseId, str] = {
    PhaseId.STT: "0 · STT",
    PhaseId.TERM_EXTRACTION: "1 · Extraction termes",
    PhaseId.GLOSSARY_RECONCILIATION: "2 · Réconciliation glossaire",
    PhaseId.REFORMULATION: "3 · Reformulation",
    PhaseId.STRUCTURATION: "4 · Structuration",
    PhaseId.CONSOLIDATION: "5 · Consolidation",
    PhaseId.TRANSLATION: "6 · Traduction",
    PhaseId.COHERENCE: "7 · Cohérence",
}
```
(importer `PhaseId` s'il ne l'est pas déjà ; retirer `_format_duration_label`
inutilisé si c'est le cas — sinon le garder.)

- [ ] **Step 6 : brancher la pédagogie**

Dans `pedagogy_controller.py`, remplacer le corps de `_show_pedagogy_cost_dialog`
par une délégation :

```python
    from fahmi2.ui.cost_estimate_dialog import show_cost_estimate  # noqa: PLC0415

    header = [
        f"<b>Projet :</b> {project_name}",
        f"<b>Chapitres (toutes langues) :</b> {estimation.chapters_total}",
    ]
    breakdown = [
        (support_label(support), cost)
        for support, cost in sorted(
            estimation.per_support_usd.items(), key=lambda kv: kv[0].value
        )
    ]
    show_cost_estimate(
        parent,
        title="Estimation du coût des supports",
        header_lines=header,
        breakdown=breakdown,
        total_usd=estimation.total_usd,
        low_usd=estimation.low_usd,
        high_usd=estimation.high_usd,
        cost_ceiling_usd=cost_ceiling_usd,
    )
```

- [ ] **Step 7 : `ruff --fix` + suite + mypy**

```powershell
.venv\Scripts\python.exe -m ruff check --fix .
.venv\Scripts\python.exe -m pytest -q ; .venv\Scripts\python.exe -m ruff check . ; .venv\Scripts\python.exe -m mypy src tests
```
Attendu : tout vert (`Qt` peut devenir inutilisé dans un contrôleur si plus utilisé
ailleurs — laisser ruff nettoyer).

- [ ] **Step 8 : commit**

```powershell
git add -A
git commit -m @'
feat(ui): dialogue d'estimation harmonise (decomposition + fourchette + plafond)

Helper partage show_cost_estimate / build_estimate_body : decomposition par phase
(generation) / par support (pedagogie), total a fourchette (format A : ≈ $X +
fourchette $low–$high ±33%), avertissement si le haut de fourchette depasse le
plafond. Les deux dialogues deleguent au helper.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
'@
```

---

## Clôture du Lot 3d (et du #3)

- [ ] `CHANGELOG.md` (Non publié) : « Modifié » (estimation granulaire par phase +
  fourchette ±33 % + avertissement plafond, dialogues harmonisés). Commit
  `docs(changelog): Lot 3d (estimation granulaire + fourchette)`.
- [ ] `docs/04-parametrage.md` / `docs/02` si l'estimation y est décrite (mention
  décomposition + fourchette).
- [ ] **#3 complet** (3a + 3b + 3c + 3d). Contrôle visuel : « Estimer le coût » des
  deux onglets montre la décomposition + la fourchette.

## Self-review

Couvre §3.5 : per-phase (génération) + fourchette (les deux) + avertissement plafond
+ dialogue harmonisé (helper partagé). Pas de placeholder : code exact. Types
cohérents (`cost_range`, `per_phase_usd`, `low_usd`/`high_usd`, `build_estimate_body`/
`show_cost_estimate`). Le rendu (`build_estimate_body`) est testé sans Qt ; les
contrôleurs délèguent. Décimales : décomposition 4, total/fourchette 2 (sous « ≈ »).
