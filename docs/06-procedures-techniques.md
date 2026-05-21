# Fahmi2 — Procédures techniques (développeur)

Cookbook de commandes pour la maintenance, le développement et la
distribution de Fahmi2.

## 1. Setup environnement

### 1.1 Création du venv et installation

```powershell
# Python 3.12 explicite (recommandé)
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1

# Mise à jour pip puis installation editable
python -m pip install --upgrade pip
pip install -e ".[dev]"
pip install pyinstaller>=6.10

# Activation des hooks pre-commit (lint + types + tests rapides)
pre-commit install
```

### 1.2 Mise à jour des dépendances

```powershell
# Voir ce qui est obsolète
pip list --outdated

# Mettre à jour une dépendance précise
pip install --upgrade <package>

# Mettre à jour le projet en mode editable
pip install --upgrade -e ".[dev]"
```

## 2. Tests

### 2.1 Lancer toute la suite

```powershell
pytest
```

### 2.2 Lancer un sous-ensemble

```powershell
# Une couche
pytest tests/unit/domain
pytest tests/unit/core
pytest tests/unit/infra
pytest tests/unit/app
pytest tests/unit/ui
pytest tests/unit/pipeline
pytest tests/e2e

# Un fichier
pytest tests/unit/core/test_paths.py

# Un seul test
pytest tests/unit/core/test_paths.py::test_paths_uses_env_appdata -v
```

### 2.3 Couverture

```powershell
# Affichage en console
pytest --cov=src/fahmi2 --cov-report=term-missing

# Rapport HTML
pytest --cov=src/fahmi2 --cov-report=html
# Ouvrir htmlcov/index.html
```

### 2.4 Tests en mode verbeux avec arrêt au premier échec

```powershell
pytest -v -x
```

### 2.5 Re-run uniquement les tests échoués

```powershell
pytest --lf
```

### 2.6 Markers et exclusions

```powershell
# Exclure les tests E2E (rapides uniquement)
pytest --ignore=tests/e2e

# Tests qui matchent un pattern
pytest -k "test_engine"
```

## 3. Linting et formatage

### 3.1 Ruff (linter + formatter)

```powershell
# Linter (check seulement)
ruff check .

# Linter avec auto-fix des erreurs corrigibles
ruff check --fix .

# Formatter (équivalent black)
ruff format .

# Vérification du formatage sans le modifier
ruff format --check .
```

### 3.2 mypy (type checker)

```powershell
# Strict (config dans pyproject.toml)
mypy src tests

# Sur un fichier
mypy src/fahmi2/pipeline/engine.py

# Mode incrémental (cache)
mypy --incremental src tests
```

### 3.3 Pre-commit (avant chaque commit)

```powershell
# Exécuter tous les hooks sur les fichiers modifiés
pre-commit run

# Exécuter tous les hooks sur toute la base
pre-commit run --all-files

# Hook spécifique
pre-commit run ruff
pre-commit run mypy
```

## 4. Lancement de l'application en mode dev

```powershell
# Lance la fenêtre principale
python -m fahmi2.ui.app_main

# Avec un répertoire APPDATA isolé (utile pour tests manuels)
$env:APPDATA = "C:\Temp\Fahmi2-test"
python -m fahmi2.ui.app_main
```

## 5. Packaging et distribution

### 5.1 Build complet en une commande

```powershell
.\packaging\build.ps1
.\packaging\make-portable-zip.ps1
```

Le `.zip` final apparaît dans `dist/Fahmi2-<version>-win64.zip`.

### 5.2 Étapes individuelles

```powershell
# Télécharger ffmpeg portable (idempotent)
.\packaging\fetch-ffmpeg.ps1

# Build PyInstaller uniquement
pyinstaller packaging/fahmi2.spec --noconfirm --clean

# Génération du .zip uniquement (après un build)
.\packaging\make-portable-zip.ps1
```

### 5.3 Tester l'EXE buildé

```powershell
.\dist\Fahmi2\Fahmi2.exe
```

### 5.4 Vérifier la taille du bundle

```powershell
Get-ChildItem dist/Fahmi2 -Recurse | Measure-Object -Property Length -Sum |
    Select-Object @{n='SizeMB';e={[math]::Round($_.Sum / 1MB, 1)}}
```

### 5.5 Vérifier le hash SHA256 du .zip distribué

```powershell
Get-FileHash dist/Fahmi2-*.zip -Algorithm SHA256
```

## 6. Gestion git

### 6.1 Workflow standard

```powershell
git status
git diff
git add <fichiers>
git commit -m "type(scope): message"
git push
```

### 6.2 Conventions de commit

- `feat(scope):` nouvelle fonctionnalité
- `fix(scope):` correction de bug
- `refactor(scope):` refactorisation sans changement de comportement
- `docs(scope):` documentation
- `test(scope):` tests
- `chore:` tâche de maintenance (dépendances, config)

Exemples :

```
feat(pipeline/handlers): Phase 5 consolidation
fix(infra/llm): mapping correct des erreurs DeepSeek 5xx
docs(installation): clarifier la procédure SmartScreen
chore(deps): bump scikit-learn vers 1.8
```

### 6.3 Tags de jalons

```powershell
# Lister
git tag

# Créer un tag annoté
git tag -a milestone-XX-<nom> -m "Description du jalon"

# Pousser les tags
git push --tags
```

## 7. Migrations de schéma SQLite

### 7.1 Créer une nouvelle migration

1. Créer `src/fahmi2/core/migrations/vNN_to_vMM.py` :

```python
from fahmi2.core.migrations.runner import Migration

def _apply(state):
    # ALTER TABLE ou logique de migration
    state.schema_version = MM

def vNN_to_vMM_migration():
    return Migration(from_version=NN, to_version=MM, apply=_apply)
```

2. Enregistrer la migration dans le `MigrationRunner` au démarrage (cf.
   `app_main.py`, à étendre dans une prochaine version).

3. Incrémenter `SCHEMA_VERSION` dans
   `src/fahmi2/infra/storage/sqlite_state.py`.

4. Mettre à jour `_schema.sql` pour refléter le schéma cible.

5. Ajouter des tests dans `tests/unit/core/`.

## 8. Debugging

### 8.1 Logs de l'app

```powershell
# En mode dev, les logs sont par défaut sur stderr en plus du fichier
python -m fahmi2.ui.app_main 2>&1 | Tee-Object -FilePath "debug.log"
```

### 8.2 Inspecter une base SQLite

```powershell
# Avec sqlite3 CLI (à installer séparément si absent)
sqlite3 "$env:APPDATA\Fahmi2\projects.db"

# Quelques requêtes utiles
.tables
.schema phase_executions
SELECT * FROM projects;
SELECT run_id, phase_id, video_id, status FROM phase_executions
  WHERE run_id = '...' ORDER BY id;
```

### 8.3 Inspecter un fichier `events.jsonl`

```powershell
# Compter par sévérité
Get-Content events.jsonl | ConvertFrom-Json |
    Group-Object severity | Format-Table Name, Count

# Lister les erreurs
Get-Content events.jsonl | ConvertFrom-Json |
    Where-Object severity -in @("error","fatal") |
    Select-Object timestamp, code, message
```

### 8.4 Debugger interactif (pdb)

```python
import pdb
pdb.set_trace()  # à insérer dans le code
```

Lancer ensuite `python -m fahmi2.ui.app_main`. Le debugger sera actif au
point d'insertion.

### 8.5 Reproduire un bug avec un état SQLite isolé

```powershell
# Copier une DB de prod vers un espace de test
Copy-Item "$env:APPDATA\Fahmi2\projects.db" "C:\Temp\bug-repro.db"

# Lancer avec APPDATA redirigé
$env:APPDATA = "C:\Temp\bug-repro"
mkdir "C:\Temp\bug-repro\Fahmi2"
Copy-Item "C:\Temp\bug-repro.db" "C:\Temp\bug-repro\Fahmi2\projects.db"
python -m fahmi2.ui.app_main
```

## 9. Performances

### 9.1 Profiling

```powershell
# Profil cProfile
python -m cProfile -o profile.out -m fahmi2.ui.app_main

# Analyser avec snakeviz
pip install snakeviz
snakeviz profile.out
```

### 9.2 Mémoire

```powershell
pip install memory-profiler
python -m memory_profiler script.py
```

## 10. Mise à jour de la version

1. Modifier `version = "..."` dans `pyproject.toml`.
2. Ajouter une entrée dans `CHANGELOG.md`.
3. Commit `chore: bump version to X.Y.Z`.
4. Tag `git tag -a vX.Y.Z -m "..."`.
5. Push : `git push && git push --tags`.
6. Builder et distribuer le `.zip` correspondant.

## 11. Ajouter une nouvelle phase au pipeline

1. Créer `src/fahmi2/pipeline/handlers/phase_N_xxx.py` qui hérite de
   `PhaseHandler`. Si la phase est **per-vidéo et parallélisable** (unités
   indépendantes, I/O-bound), surcharger `max_parallel_workers(ctx)` pour
   retourner le pool voulu (défaut hérité : `1` = séquentiel). Pour une phase
   batch, paralléliser ses boucles internes via `core/concurrency/map_bounded`.
2. Créer le template Jinja2 par défaut dans
   `src/fahmi2/infra/prompts/defaults/phase_N_xxx.j2`.
3. Ajouter `PhaseId.XXX` dans `src/fahmi2/domain/enums.py`.
4. Mettre à jour `_PIPELINE_ORDER` dans
   `src/fahmi2/pipeline/phase_registry.py`.
5. Enregistrer le handler dans la construction du `PhaseRegistry` (cf.
   tests E2E et `app_main.py`).
6. Ajouter le bind du multiplicateur de coût dans `_LOAD_FACTORS` dans
   `src/fahmi2/app/cost_estimator.py`.
7. Écrire les tests : `tests/unit/pipeline/handlers/test_phase_N_xxx.py`.
8. Lancer la suite complète + lint + types.

## 12. Ajouter un nouveau provider LLM

1. Implémenter `LLMProvider` (Protocol) dans
   `src/fahmi2/infra/llm/<provider>_adapter.py`.
2. Ajouter une grille de tarifs dans `src/fahmi2/infra/llm/_pricing.py`.
3. Étendre l'enum `LLMModel` dans `src/fahmi2/domain/enums.py`.
4. Exposer le modèle dans les vues de réglages (`GenerationSettingsView` /
   `PedagogySettingsView`) — combos alimentés par l'enum `LLMModel` (le
   `NewProjectDialog` ne porte plus que le nom + l'emplacement du projet).
5. Écrire les tests (avec mock du SDK ou `responses`).

## 13. Audit qualité

Avant chaque release, dérouler :

```powershell
# 1. Tests complets
pytest --cov=src/fahmi2 --cov-report=term-missing

# 2. Lint propre
ruff check .

# 3. Types stricts
mypy src tests

# 4. Couverture seuils
# (devrait être >= 85 % global)

# 5. Build packaging
.\packaging\build.ps1

# 6. Test manuel de l'EXE buildé
.\dist\Fahmi2\Fahmi2.exe

# 7. Génération du .zip
.\packaging\make-portable-zip.ps1

# 8. Vérification du .zip sur une machine cible
```
