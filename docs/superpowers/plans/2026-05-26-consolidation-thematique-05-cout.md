# Lot 5 — Coût par mode de consolidation

> Sous-skill d'exécution : superpowers:executing-plans. Étapes en `- [ ]`.
> **Dépend de** : Lot 1.

**But du lot :** `CostEstimator.estimate` prend en compte `consolidation_mode` ;
en `THEMATIC`, la phase 5 utilise un jeu de facteurs dédié (plus élevé). Pas
d'enforcement runtime (cf. spec §6 : la génération n'en a pas).

---

### Task 5.1 : Facteur thématique dans `CostEstimator`

**Files:**
- Modify: `src/fahmi2/app/cost_estimator.py`
- Test: `tests/unit/app/test_cost_estimator.py`

- [ ] **Step 1 : Test — thématique plus cher qu'ordonné, ordonné inchangé**

```python
def test_thematic_consolidation_costs_more_than_ordered() -> None:
    from fahmi2.app.cost_estimator import CostEstimator, SourceWeight
    from fahmi2.domain.enums import (
        ConsolidationMode, LLMModel, PhaseId, SttProvider,
    )

    weights = [SourceWeight(audio_seconds=600.0, text_tokens=0.0) for _ in range(3)]
    est = CostEstimator()
    ordered = est.estimate(
        source_weights=weights, stt_provider=SttProvider.FASTER_WHISPER_LOCAL,
        llm_model=LLMModel.DEEPSEEK_V4_PRO,
        consolidation_mode=ConsolidationMode.ORDERED,
    )
    thematic = est.estimate(
        source_weights=weights, stt_provider=SttProvider.FASTER_WHISPER_LOCAL,
        llm_model=LLMModel.DEEPSEEK_V4_PRO,
        consolidation_mode=ConsolidationMode.THEMATIC,
    )
    assert thematic.per_phase_usd[PhaseId.CONSOLIDATION] > ordered.per_phase_usd[PhaseId.CONSOLIDATION]


def test_estimate_defaults_to_ordered_when_mode_absent() -> None:
    # backward-compat : appel sans consolidation_mode -> comportement ORDERED actuel
    from fahmi2.app.cost_estimator import CostEstimator, SourceWeight
    from fahmi2.domain.enums import LLMModel, SttProvider

    est = CostEstimator()
    res = est.estimate(
        source_weights=[SourceWeight(600.0, 0.0)],
        stt_provider=SttProvider.FASTER_WHISPER_LOCAL,
        llm_model=LLMModel.DEEPSEEK_V4_PRO,
    )
    assert res.total_usd >= 0
```

- [ ] **Step 2 : Lancer → échec** (`unexpected keyword argument 'consolidation_mode'`)

Run: `.venv\Scripts\python.exe -m pytest tests/unit/app/test_cost_estimator.py -k thematic -v`

- [ ] **Step 3 : Implémenter**

Dans `cost_estimator.py` :

1. Importer `ConsolidationMode` depuis `fahmi2.domain.enums`.
2. Ajouter une constante facteur thématique (à côté de `_LOAD_FACTORS`) :

```python
# Facteur dédié de la phase 5 en mode THEMATIC : T1 (relevé par source) +
# plan + rédaction par chapitre + méta. Plus coûteux que le mode ORDERED.
_THEMATIC_CONSOLIDATION_FACTOR = _PhaseLoadFactor(
    input_per_source=0.0,
    output_per_source=0.0,
    is_per_source=False,
    batch_input_multiplier=1.2,   # plan + relecture des éléments par chapitre
    batch_output_factor=1.2,      # document synthétisé
    sub_loop_per_source=1.0,      # T1 relit chaque source en entier
    sub_loop_output_factor=0.3,   # relevé factuel par source
)
```

3. Ajouter le paramètre keyword-only `consolidation_mode: ConsolidationMode =
   ConsolidationMode.ORDERED` à `CostEstimator.estimate` (docstring à compléter) et
   le propager à `_llm_cost_per_phase`.
4. Dans `_llm_cost_per_phase`, ajouter `consolidation_mode` en paramètre ; à
   l'intérieur de la boucle, choisir le facteur de la phase CONSOLIDATION selon le
   mode :

```python
        for phase_id, factor in _LOAD_FACTORS.items():
            if (
                phase_id is PhaseId.CONSOLIDATION
                and consolidation_mode is ConsolidationMode.THEMATIC
            ):
                factor = _THEMATIC_CONSOLIDATION_FACTOR
            # ... suite inchangée ...
```

- [ ] **Step 4 : Lancer → succès**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/app/test_cost_estimator.py -v`
Expected: PASS (anciens tests inchangés : défaut ORDERED).

- [ ] **Step 5 : Commit**

```powershell
git add src/fahmi2/app/cost_estimator.py tests/unit/app/test_cost_estimator.py
git commit -m "feat(cost): facteur dedie pour la consolidation thematique"
```

---

### Task 5.2 : Brancher le mode au point d'estimation

**Files:**
- Modify: `src/fahmi2/ui/generation_controller.py`

- [ ] **Step 1 : Localiser les appels à `.estimate(`**

Run: `.venv\Scripts\python.exe -m pytest -q` *(baseline verte)* puis repérer :
Grep `CostEstimator(` et `.estimate(` dans `generation_controller.py`.

- [ ] **Step 2 : Passer le mode**

À chaque appel `CostEstimator().estimate(...)` qui dispose des `GenerationSettings`
(`settings`/`project.generation`), ajouter l'argument :

```python
            consolidation_mode=settings.consolidation_mode,
```

(utiliser `project.generation.consolidation_mode` selon la variable disponible au
point d'appel).

- [ ] **Step 3 : Vérifs de lot + commit**

```powershell
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m mypy src tests
git add src/fahmi2/ui/generation_controller.py
git commit -m "feat(ui): l'estimation de cout tient compte du mode de consolidation"
```
