# Plan 01 — Socle : `core/` + `domain/` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construire le socle technique (transverse `core/` + entités de domaine `domain/`) sur lequel toutes les couches supérieures s'appuieront, avec une couverture de tests ≥ 95 % sur `domain/` et ≥ 90 % sur `core/`.

**Architecture:** Couches pures sans dépendance externe (pas de Qt, pas d'HTTP, pas de SQL). `core/` regroupe les fondations transverses (logging structuré, hiérarchie d'erreurs, retry, config, migrations stub, retrieval interface, identifiants). `domain/` regroupe les entités et machines d'état (Project, Run, Phase, Glossary, etc.).

**Tech Stack:** Python 3.11/3.12, pytest, pytest-cov, ruff, mypy, structlog, tenacity, python-ulid, pydantic v2, jinja2 (déclarés mais pas tous utilisés ici).

**Référence spec :** [docs/superpowers/specs/2026-05-19-fahmi2-design.md](../specs/2026-05-19-fahmi2-design.md) — sections 3 (architecture), 4 (modèle de domaine), 8 (erreurs), 13 (migrations).

---

## File structure (à produire dans ce plan)

```
fahmi2/
├── pyproject.toml                              ← Task 1
├── .gitignore                                  ← déjà présent
├── .pre-commit-config.yaml                     ← Task 1
├── README.md                                   ← Task 1 (squelette minimal)
├── src/fahmi2/
│   ├── __init__.py                             ← Task 1
│   ├── core/
│   │   ├── __init__.py
│   │   ├── ids.py                              ← Task 2
│   │   ├── errors/
│   │   │   ├── __init__.py
│   │   │   ├── severity.py                     ← Task 3
│   │   │   ├── exceptions.py                   ← Task 4
│   │   │   ├── error_info.py                   ← Task 4
│   │   │   └── messages.py                     ← Task 5
│   │   ├── logging/
│   │   │   ├── __init__.py
│   │   │   ├── event.py                        ← Task 6
│   │   │   ├── sink.py                         ← Task 7
│   │   │   └── jsonl_sink.py                   ← Task 8
│   │   ├── retry/
│   │   │   ├── __init__.py
│   │   │   ├── policy.py                       ← Task 9
│   │   │   └── runner.py                       ← Task 10
│   │   ├── config/
│   │   │   ├── __init__.py
│   │   │   ├── paths.py                        ← Task 11
│   │   │   └── app_config.py                   ← Task 12
│   │   ├── migrations/
│   │   │   ├── __init__.py
│   │   │   └── runner.py                       ← Task 13
│   │   └── retrieval/
│   │       ├── __init__.py
│   │       └── interface.py                    ← Task 14
│   └── domain/
│       ├── __init__.py
│       ├── enums.py                            ← Task 15
│       ├── ids.py                              ← Task 16
│       ├── glossary.py                         ← Task 17
│       ├── phase.py                            ← Task 18
│       ├── video.py                            ← Task 19
│       ├── run.py                              ← Task 20
│       ├── project.py                          ← Task 21
│       └── state_machine.py                    ← Task 22
└── tests/
    ├── __init__.py
    ├── conftest.py                             ← Task 1
    ├── unit/
    │   ├── core/
    │   │   ├── test_ids.py                     ← Task 2
    │   │   ├── test_severity.py                ← Task 3
    │   │   ├── test_exceptions.py              ← Task 4
    │   │   ├── test_messages.py                ← Task 5
    │   │   ├── test_log_event.py               ← Task 6
    │   │   ├── test_sink.py                    ← Task 7
    │   │   ├── test_jsonl_sink.py              ← Task 8
    │   │   ├── test_retry_policy.py            ← Task 9
    │   │   ├── test_retry_runner.py            ← Task 10
    │   │   ├── test_paths.py                   ← Task 11
    │   │   ├── test_app_config.py              ← Task 12
    │   │   ├── test_migration_runner.py        ← Task 13
    │   │   └── test_retrieval_interface.py     ← Task 14
    │   └── domain/
    │       ├── test_enums.py                   ← Task 15
    │       ├── test_domain_ids.py              ← Task 16
    │       ├── test_glossary.py                ← Task 17
    │       ├── test_phase.py                   ← Task 18
    │       ├── test_video.py                   ← Task 19
    │       ├── test_run.py                     ← Task 20
    │       ├── test_project.py                 ← Task 21
    │       └── test_state_machine.py           ← Task 22
    └── fixtures/
        └── __init__.py
```

**Principe TDD** : pour chaque task, on écrit d'abord le test (qui doit échouer pour la bonne raison), puis l'implémentation minimale, puis on vérifie que le test passe, puis on commit. Pas d'implémentation sans test rouge préalable.

---

### Task 1: Scaffold projet + tooling

**Files:**
- Create: `pyproject.toml`
- Create: `.pre-commit-config.yaml`
- Create: `README.md`
- Create: `src/fahmi2/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `tests/unit/__init__.py`
- Create: `tests/unit/core/__init__.py`
- Create: `tests/unit/domain/__init__.py`
- Create: `tests/fixtures/__init__.py`

- [ ] **Step 1.1 : Créer `pyproject.toml`**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "fahmi2"
version = "0.1.0.dev0"
description = "Local desktop app converting pedagogical video lectures to consolidated Markdown documents."
authors = [{ name = "Fahmi2 contributors" }]
readme = "README.md"
requires-python = ">=3.11,<3.13"
license = { text = "Proprietary" }

dependencies = [
  "PySide6>=6.7,<7",
  "faster-whisper>=1.0,<2",
  "openai>=1.40,<2",
  "ffmpeg-python>=0.2,<0.3",
  "pywin32>=306; sys_platform == 'win32'",
  "jinja2>=3.1,<4",
  "pydantic>=2,<3",
  "python-ulid>=2,<3",
  "structlog>=24,<25",
  "tenacity>=9,<10",
  "scikit-learn>=1.5,<2",
]

[project.optional-dependencies]
dev = [
  "pytest>=8",
  "pytest-cov>=5",
  "pytest-qt>=4.4",
  "responses>=0.25",
  "ruff>=0.6",
  "mypy>=1.11",
  "pre-commit>=3.8",
]

[tool.hatch.build.targets.wheel]
packages = ["src/fahmi2"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra --strict-markers --strict-config"
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]

[tool.coverage.run]
source = ["src/fahmi2"]
branch = true

[tool.coverage.report]
exclude_lines = [
  "pragma: no cover",
  "raise NotImplementedError",
  "if TYPE_CHECKING:",
  "@overload",
]
show_missing = true

[tool.ruff]
line-length = 100
target-version = "py311"
src = ["src", "tests"]

[tool.ruff.lint]
select = ["E", "F", "W", "B", "C90", "N", "UP", "ANN", "S", "PL", "I"]
ignore = ["ANN101", "ANN102", "S101", "PLR0913"]
# ANN101/ANN102 = self/cls annotation (deprecated rules)
# S101 = use of assert (OK in tests)
# PLR0913 = too many arguments (settings classes legitimately have many)

[tool.ruff.lint.per-file-ignores]
"tests/**/*.py" = ["S", "PLR2004", "ANN"]

[tool.mypy]
python_version = "3.11"
strict = true
warn_unreachable = true
warn_return_any = true
no_implicit_reexport = true
disallow_untyped_decorators = true
files = ["src/fahmi2", "tests"]

[[tool.mypy.overrides]]
module = ["pywin32.*", "win32crypt.*", "ffmpeg.*", "faster_whisper.*"]
ignore_missing_imports = true
```

- [ ] **Step 1.2 : Créer `.pre-commit-config.yaml`**

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.6.9
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.11.2
    hooks:
      - id: mypy
        additional_dependencies:
          - pydantic>=2
          - structlog
          - tenacity
          - python-ulid
        args: [--strict]
        files: ^src/
```

- [ ] **Step 1.3 : Créer `README.md` minimal**

```markdown
# Fahmi2

Local desktop application that transforms pedagogical video lectures (MP4, FR/EN) into structured Markdown documents with glossary and consolidated output.

See [docs/superpowers/specs/](docs/superpowers/specs/) for design documentation.

## Development setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
pre-commit install
pytest
```
```

- [ ] **Step 1.4 : Créer les fichiers `__init__.py` vides** dans `src/fahmi2/`, `tests/`, `tests/unit/`, `tests/unit/core/`, `tests/unit/domain/`, `tests/fixtures/`.

- [ ] **Step 1.5 : Créer `tests/conftest.py`** (vide pour l'instant mais présent pour la suite)

```python
"""Pytest fixtures globales."""
```

- [ ] **Step 1.6 : Vérifier l'installation et le scaffold**

Run:
```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
pytest --collect-only
ruff check .
mypy src
```
Expected: `pytest --collect-only` ne trouve aucun test (normal), `ruff` et `mypy` passent sans erreur.

- [ ] **Step 1.7 : Commit**

```bash
git add pyproject.toml .pre-commit-config.yaml README.md src/ tests/
git commit -m "chore: bootstrap projet (pyproject, tooling, structure)"
```

---

### Task 2: `core/ids.py` — Identifiants ULID

**Files:**
- Create: `src/fahmi2/core/__init__.py` (vide)
- Create: `src/fahmi2/core/ids.py`
- Test: `tests/unit/core/test_ids.py`

- [ ] **Step 2.1 : Créer le test failing dans `tests/unit/core/test_ids.py`**

```python
"""Tests des helpers ULID."""

from datetime import datetime, timezone

import pytest

from fahmi2.core.ids import new_ulid, parse_ulid, ulid_to_datetime


def test_new_ulid_returns_26_char_string() -> None:
    value = new_ulid()
    assert isinstance(value, str)
    assert len(value) == 26


def test_new_ulid_returns_unique_values() -> None:
    values = {new_ulid() for _ in range(100)}
    assert len(values) == 100


def test_new_ulid_is_monotonic_in_time() -> None:
    ulids = [new_ulid() for _ in range(10)]
    assert ulids == sorted(ulids), "ULIDs générés successivement doivent être ordonnés"


def test_parse_ulid_accepts_valid_ulid() -> None:
    original = new_ulid()
    parsed = parse_ulid(original)
    assert parsed == original


def test_parse_ulid_rejects_invalid() -> None:
    with pytest.raises(ValueError):
        parse_ulid("not-a-ulid")


def test_ulid_to_datetime_returns_utc_aware() -> None:
    value = new_ulid()
    dt = ulid_to_datetime(value)
    assert dt.tzinfo is not None
    assert dt.tzinfo.utcoffset(dt) == timezone.utc.utcoffset(dt)
```

- [ ] **Step 2.2 : Vérifier que les tests échouent**

Run: `pytest tests/unit/core/test_ids.py -v`
Expected: FAIL avec `ModuleNotFoundError: No module named 'fahmi2.core.ids'`

- [ ] **Step 2.3 : Créer `src/fahmi2/core/__init__.py`** (vide)

- [ ] **Step 2.4 : Implémenter `src/fahmi2/core/ids.py`**

```python
"""Identifiants stables (ULID) pour les entités du domaine.

Les ULID combinent un timestamp millisecondes et une partie aléatoire, ce qui
garantit à la fois l'unicité et un ordre chronologique naturel — utile pour
le tri stable des projets/runs/vidéos sans index supplémentaire.
"""

from __future__ import annotations

from datetime import datetime, timezone

from ulid import ULID


def new_ulid() -> str:
    """Génère un nouvel identifiant ULID encodé Crockford base32.

    Returns:
        Chaîne de 26 caractères correspondant à un ULID monotonement croissant.
    """
    return str(ULID())


def parse_ulid(value: str) -> str:
    """Valide qu'une chaîne est un ULID et la retourne normalisée.

    Args:
        value: Chaîne candidate.

    Returns:
        L'ULID validé sous forme de chaîne normalisée.

    Raises:
        ValueError: Si la chaîne n'est pas un ULID valide.
    """
    try:
        return str(ULID.from_str(value))
    except (ValueError, TypeError) as exc:
        raise ValueError(f"Invalid ULID: {value!r}") from exc


def ulid_to_datetime(value: str) -> datetime:
    """Extrait le timestamp encodé dans un ULID.

    Args:
        value: ULID valide (sera validé en interne).

    Returns:
        Datetime UTC correspondant à la portion timestamp du ULID.

    Raises:
        ValueError: Si la chaîne n'est pas un ULID valide.
    """
    ulid_obj = ULID.from_str(parse_ulid(value))
    return datetime.fromtimestamp(ulid_obj.timestamp, tz=timezone.utc)
```

- [ ] **Step 2.5 : Vérifier que les tests passent**

Run: `pytest tests/unit/core/test_ids.py -v`
Expected: 6/6 PASS

- [ ] **Step 2.6 : Commit**

```bash
git add src/fahmi2/core/__init__.py src/fahmi2/core/ids.py tests/unit/core/test_ids.py
git commit -m "feat(core): helpers ULID pour identifiants stables"
```

---

### Task 3: `core/errors/severity.py` — Severity enum

**Files:**
- Create: `src/fahmi2/core/errors/__init__.py` (vide)
- Create: `src/fahmi2/core/errors/severity.py`
- Test: `tests/unit/core/test_severity.py`

- [ ] **Step 3.1 : Test failing**

```python
"""Tests de l'énumération Severity."""

from fahmi2.core.errors.severity import Severity


def test_severity_has_four_levels() -> None:
    assert {s.value for s in Severity} == {"info", "warning", "error", "fatal"}


def test_severity_ordering() -> None:
    assert Severity.INFO < Severity.WARNING < Severity.ERROR < Severity.FATAL


def test_severity_from_string() -> None:
    assert Severity("warning") is Severity.WARNING
```

- [ ] **Step 3.2 : Run, vérifier l'échec**

Run: `pytest tests/unit/core/test_severity.py -v`
Expected: FAIL avec ModuleNotFoundError

- [ ] **Step 3.3 : Implémenter**

`src/fahmi2/core/errors/__init__.py` :
```python
"""Hiérarchie d'exceptions et codes d'erreur de Fahmi2."""
```

`src/fahmi2/core/errors/severity.py` :
```python
"""Niveaux de sévérité utilisés par la hiérarchie d'exceptions."""

from __future__ import annotations

from enum import IntEnum


class Severity(IntEnum):
    """Niveau de sévérité d'une erreur ou d'un événement de log.

    L'ordre est significatif : INFO < WARNING < ERROR < FATAL. Les sinks de log
    peuvent filtrer en comparant directement les valeurs.
    """

    INFO = 10
    WARNING = 20
    ERROR = 30
    FATAL = 40

    def __str__(self) -> str:
        return self.name.lower()

    @classmethod
    def _missing_(cls, value: object) -> Severity | None:
        if isinstance(value, str):
            for member in cls:
                if member.name.lower() == value.lower():
                    return member
        return None
```

- [ ] **Step 3.4 : Run, vérifier le pass**

Run: `pytest tests/unit/core/test_severity.py -v`
Expected: 3/3 PASS

- [ ] **Step 3.5 : Commit**

```bash
git add src/fahmi2/core/errors/ tests/unit/core/test_severity.py
git commit -m "feat(core/errors): enum Severity ordonnable"
```

---

### Task 4: `core/errors/exceptions.py` + `error_info.py` — hiérarchie d'exceptions

**Files:**
- Create: `src/fahmi2/core/errors/error_info.py`
- Create: `src/fahmi2/core/errors/exceptions.py`
- Test: `tests/unit/core/test_exceptions.py`

- [ ] **Step 4.1 : Test failing**

```python
"""Tests de la hiérarchie d'exceptions Fahmi2."""

import pytest

from fahmi2.core.errors.error_info import ErrorInfo
from fahmi2.core.errors.exceptions import (
    BudgetExceededError,
    ConfigError,
    Fahmi2Error,
    FFmpegError,
    LLMError,
    PausedError,
    PermanentError,
    StorageError,
    STTError,
    TransientError,
)
from fahmi2.core.errors.severity import Severity


def test_fahmi2_error_carries_code_and_severity() -> None:
    err = Fahmi2Error(code="TEST.X", user_message="oups", severity=Severity.ERROR)
    assert err.code == "TEST.X"
    assert err.user_message == "oups"
    assert err.severity is Severity.ERROR
    assert err.technical_details == {}


def test_fahmi2_error_accepts_technical_details() -> None:
    err = Fahmi2Error(
        code="TEST.X",
        user_message="oups",
        severity=Severity.ERROR,
        technical_details={"status_code": 503},
    )
    assert err.technical_details["status_code"] == 503


def test_fahmi2_error_str_includes_code_and_message() -> None:
    err = Fahmi2Error(code="TEST.X", user_message="oups", severity=Severity.ERROR)
    assert "TEST.X" in str(err)
    assert "oups" in str(err)


def test_transient_and_permanent_are_subclasses() -> None:
    assert issubclass(TransientError, Fahmi2Error)
    assert issubclass(PermanentError, Fahmi2Error)


def test_domain_specific_errors_inherit_from_base() -> None:
    for cls in (STTError, LLMError, FFmpegError, StorageError, ConfigError):
        assert issubclass(cls, Fahmi2Error)


def test_budget_exceeded_is_distinct() -> None:
    err = BudgetExceededError(
        code="BUDGET.EXCEEDED",
        user_message="plafond dépassé",
        severity=Severity.WARNING,
    )
    assert isinstance(err, Fahmi2Error)
    assert not isinstance(err, TransientError)


def test_paused_error_is_distinct() -> None:
    err = PausedError(
        code="RUN.PAUSED",
        user_message="pause demandée",
        severity=Severity.INFO,
    )
    assert isinstance(err, Fahmi2Error)


def test_error_info_serializes_to_dict() -> None:
    info = ErrorInfo(
        code="TEST.X",
        user_message="oups",
        severity=Severity.ERROR,
        technical_details={"k": "v"},
        traceback="trace…",
    )
    payload = info.to_dict()
    assert payload["code"] == "TEST.X"
    assert payload["severity"] == "error"
    assert payload["technical_details"] == {"k": "v"}
    assert payload["traceback"] == "trace…"


def test_error_info_from_exception_captures_traceback() -> None:
    try:
        raise Fahmi2Error(
            code="TEST.X",
            user_message="oups",
            severity=Severity.ERROR,
            technical_details={"k": "v"},
        )
    except Fahmi2Error as exc:
        info = ErrorInfo.from_exception(exc)
    assert info.code == "TEST.X"
    assert info.user_message == "oups"
    assert info.severity is Severity.ERROR
    assert "TEST.X" in (info.traceback or "")


def test_error_info_from_arbitrary_exception() -> None:
    try:
        raise ValueError("plain")
    except ValueError as exc:
        info = ErrorInfo.from_exception(exc)
    assert info.code == "UNEXPECTED.VALUE_ERROR"
    assert info.severity is Severity.ERROR
    assert "plain" in info.user_message
```

- [ ] **Step 4.2 : Vérifier l'échec**

Run: `pytest tests/unit/core/test_exceptions.py -v`
Expected: FAIL

- [ ] **Step 4.3 : Implémenter `src/fahmi2/core/errors/error_info.py`**

```python
"""Représentation sérialisable d'une erreur, utilisée par les logs et l'UI."""

from __future__ import annotations

import traceback as tb_module
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from fahmi2.core.errors.severity import Severity

if TYPE_CHECKING:
    pass


@dataclass(frozen=True)
class ErrorInfo:
    """Snapshot immuable et sérialisable d'une erreur survenue dans l'app."""

    code: str
    user_message: str
    severity: Severity
    technical_details: dict[str, Any] = field(default_factory=dict)
    traceback: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Sérialise au format dict JSON-friendly."""
        return {
            "code": self.code,
            "user_message": self.user_message,
            "severity": str(self.severity),
            "technical_details": dict(self.technical_details),
            "traceback": self.traceback,
        }

    @classmethod
    def from_exception(cls, exc: BaseException) -> ErrorInfo:
        """Construit un ErrorInfo à partir d'une exception.

        Pour les Fahmi2Error, on récupère directement les attributs.
        Pour les autres, on dérive un code générique et on capture le traceback.
        """
        from fahmi2.core.errors.exceptions import Fahmi2Error  # eviter cycle

        tb = "".join(tb_module.format_exception(type(exc), exc, exc.__traceback__))

        if isinstance(exc, Fahmi2Error):
            return cls(
                code=exc.code,
                user_message=exc.user_message,
                severity=exc.severity,
                technical_details=dict(exc.technical_details),
                traceback=tb,
            )

        return cls(
            code=f"UNEXPECTED.{type(exc).__name__.upper()}",
            user_message=str(exc) or type(exc).__name__,
            severity=Severity.ERROR,
            technical_details={"exception_type": type(exc).__name__},
            traceback=tb,
        )
```

- [ ] **Step 4.4 : Implémenter `src/fahmi2/core/errors/exceptions.py`**

```python
"""Hiérarchie d'exceptions Fahmi2.

Chaque exception porte un *code stable* (ex: "LLM.RATE_LIMIT"), un *user_message*
en français destiné à l'UI, une *severity*, et des *technical_details* riches
réservés aux logs.
"""

from __future__ import annotations

from typing import Any

from fahmi2.core.errors.severity import Severity


class Fahmi2Error(Exception):
    """Base de toutes les exceptions levées par l'application."""

    def __init__(
        self,
        *,
        code: str,
        user_message: str,
        severity: Severity,
        technical_details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(f"[{code}] {user_message}")
        self.code = code
        self.user_message = user_message
        self.severity = severity
        self.technical_details: dict[str, Any] = dict(technical_details or {})


class TransientError(Fahmi2Error):
    """Erreur transitoire — éligible à un retry par la RetryPolicy."""


class PermanentError(Fahmi2Error):
    """Erreur permanente — pas de retry, remontée immédiate."""


class BudgetExceededError(Fahmi2Error):
    """Plafond de coût atteint pendant un run — déclenche une pause propre."""


class PausedError(Fahmi2Error):
    """Levée pour signaler une pause utilisateur volontaire."""


class STTError(Fahmi2Error):
    """Erreur du sous-système speech-to-text."""


class LLMError(Fahmi2Error):
    """Erreur du sous-système LLM."""


class FFmpegError(Fahmi2Error):
    """Erreur d'extraction audio via ffmpeg."""


class StorageError(Fahmi2Error):
    """Erreur de stockage (SQLite, FS, secrets)."""


class ConfigError(Fahmi2Error):
    """Configuration invalide ou incohérente."""
```

- [ ] **Step 4.5 : Run tests**

Run: `pytest tests/unit/core/test_exceptions.py -v`
Expected: 10/10 PASS

- [ ] **Step 4.6 : Commit**

```bash
git add src/fahmi2/core/errors/exceptions.py src/fahmi2/core/errors/error_info.py tests/unit/core/test_exceptions.py
git commit -m "feat(core/errors): hierarchie d'exceptions Fahmi2 + ErrorInfo serialisable"
```

---

### Task 5: `core/errors/messages.py` — mapping codes → messages UI

**Files:**
- Create: `src/fahmi2/core/errors/messages.py`
- Create: `src/fahmi2/core/errors/messages.fr.json`
- Test: `tests/unit/core/test_messages.py`

- [ ] **Step 5.1 : Test failing**

```python
"""Tests du registre de messages utilisateurs."""

import pytest

from fahmi2.core.errors.messages import (
    UserFacingMessage,
    get_message,
    has_message,
    register_message,
)


def test_get_known_code_returns_message() -> None:
    msg = get_message("LLM.AUTH_INVALID")
    assert isinstance(msg, UserFacingMessage)
    assert "DeepSeek" in msg.title or "clé" in msg.title.lower()
    assert msg.body  # non vide


def test_get_unknown_code_returns_fallback() -> None:
    msg = get_message("DOES.NOT.EXIST")
    assert msg.title  # fallback générique
    assert "DOES.NOT.EXIST" in msg.body  # code mentionné pour debug


def test_has_message_distinguishes_known_unknown() -> None:
    assert has_message("LLM.AUTH_INVALID")
    assert not has_message("DOES.NOT.EXIST")


def test_register_message_adds_new_code() -> None:
    register_message(
        "TEST.CUSTOM",
        UserFacingMessage(title="Custom", body="body", actions=[]),
    )
    assert has_message("TEST.CUSTOM")
    assert get_message("TEST.CUSTOM").title == "Custom"
```

- [ ] **Step 5.2 : Vérifier l'échec**

Run: `pytest tests/unit/core/test_messages.py -v`
Expected: FAIL

- [ ] **Step 5.3 : Créer `src/fahmi2/core/errors/messages.fr.json`**

```json
{
  "LLM.AUTH_INVALID": {
    "title": "Clé DeepSeek invalide",
    "body": "La clé API DeepSeek est refusée par le serveur. Vérifie-la dans Paramètres › Clés API.",
    "actions": [{"label": "Ouvrir les paramètres", "action": "open_settings"}]
  },
  "LLM.RATE_LIMIT": {
    "title": "Limite de débit DeepSeek atteinte",
    "body": "Trop de requêtes en peu de temps. L'application réessaie automatiquement avec un délai croissant.",
    "actions": []
  },
  "LLM.SERVER_ERROR": {
    "title": "Erreur serveur DeepSeek",
    "body": "Le service DeepSeek est temporairement indisponible. Reprise automatique en cours.",
    "actions": []
  },
  "LLM.BAD_REQUEST": {
    "title": "Requête DeepSeek rejetée",
    "body": "La requête envoyée à DeepSeek est invalide. Consulte les logs pour le détail technique.",
    "actions": [{"label": "Ouvrir les logs", "action": "open_logs"}]
  },
  "STT.MODEL_LOAD_FAILED": {
    "title": "Échec de chargement du modèle Whisper",
    "body": "Le modèle faster-whisper-large-v3-turbo n'a pas pu être chargé. Vérifie que ton GPU est disponible et que le téléchargement du modèle est complet.",
    "actions": []
  },
  "STT.GPU_OOM": {
    "title": "Mémoire GPU insuffisante",
    "body": "Le GPU manque de mémoire pour traiter cette vidéo. Ferme les autres applications qui utilisent le GPU et reprends.",
    "actions": []
  },
  "STT.GPU_UNAVAILABLE": {
    "title": "GPU NVIDIA introuvable",
    "body": "Le mode de transcription local nécessite un GPU NVIDIA compatible CUDA. Passe sur le mode OpenAI cloud dans les paramètres du projet.",
    "actions": [{"label": "Ouvrir les paramètres du projet", "action": "open_project_settings"}]
  },
  "FFMPEG.NO_AUDIO_STREAM": {
    "title": "Vidéo sans piste audio",
    "body": "Cette vidéo MP4 ne contient pas de piste audio détectable. Elle a été marquée en échec et le run continue avec les autres vidéos.",
    "actions": []
  },
  "STORAGE.NO_SPACE": {
    "title": "Espace disque insuffisant",
    "body": "Le disque ne contient plus assez d'espace pour stocker les artefacts. Libère de la place et reprends.",
    "actions": []
  },
  "STORAGE.READ_DENIED": {
    "title": "Lecture refusée",
    "body": "L'application ne peut pas lire le dossier d'entrée. Vérifie les permissions ou choisis un autre dossier.",
    "actions": []
  },
  "CONFIG.INPUT_FOLDER_EMPTY": {
    "title": "Dossier d'entrée vide",
    "body": "Le dossier d'entrée ne contient aucune vidéo prise en charge (.mp4, .m4v, .mkv, .mov, .webm).",
    "actions": []
  },
  "BUDGET.EXCEEDED": {
    "title": "Plafond de budget atteint",
    "body": "Le plafond de coût défini pour ce projet a été atteint. Le run a été mis en pause à la prochaine frontière sûre.",
    "actions": [{"label": "Relever le plafond et reprendre", "action": "raise_budget"}]
  },
  "RUN.PAUSED": {
    "title": "Run en pause",
    "body": "Le run est en pause à la demande de l'utilisateur. Reprise possible à tout moment.",
    "actions": [{"label": "Reprendre", "action": "resume_run"}]
  },
  "PROMPT.INVALID_OVERRIDE": {
    "title": "Surcouche de prompt invalide",
    "body": "Le fichier de prompt personnalisé contient une erreur de syntaxe Jinja2. L'application est revenue au template par défaut. Consulte les logs.",
    "actions": [{"label": "Ouvrir l'éditeur de prompts", "action": "open_prompt_editor"}]
  }
}
```

- [ ] **Step 5.4 : Implémenter `src/fahmi2/core/errors/messages.py`**

```python
"""Registre statique des messages destinés à l'utilisateur, par code d'erreur."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from importlib.resources import files
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

_FALLBACK_TITLE = "Une erreur est survenue"
_FALLBACK_BODY_TEMPLATE = (
    "Code d'erreur : {code}. Consulte les logs pour le détail technique."
)


@dataclass(frozen=True)
class UserAction:
    """Action proposée à l'utilisateur depuis une boîte de dialogue d'erreur."""

    label: str
    action: str


@dataclass(frozen=True)
class UserFacingMessage:
    """Message localisé destiné à l'UI (titre, corps, actions optionnelles)."""

    title: str
    body: str
    actions: list[UserAction] = field(default_factory=list)


def _load_messages() -> dict[str, UserFacingMessage]:
    raw = json.loads(
        files("fahmi2.core.errors").joinpath("messages.fr.json").read_text(encoding="utf-8")
    )
    result: dict[str, UserFacingMessage] = {}
    for code, payload in raw.items():
        actions = [UserAction(**a) for a in payload.get("actions", [])]
        result[code] = UserFacingMessage(
            title=payload["title"],
            body=payload["body"],
            actions=actions,
        )
    return result


_REGISTRY: dict[str, UserFacingMessage] = _load_messages()


def has_message(code: str) -> bool:
    """Indique si un message est enregistré pour ce code."""
    return code in _REGISTRY


def get_message(code: str) -> UserFacingMessage:
    """Récupère le message correspondant à un code, ou un fallback générique."""
    if code in _REGISTRY:
        return _REGISTRY[code]
    return UserFacingMessage(
        title=_FALLBACK_TITLE,
        body=_FALLBACK_BODY_TEMPLATE.format(code=code),
        actions=[],
    )


def register_message(code: str, message: UserFacingMessage) -> None:
    """Ajoute (ou écrase) un message pour un code donné. Utile pour les tests."""
    _REGISTRY[code] = message
```

- [ ] **Step 5.5 : Run tests**

Run: `pytest tests/unit/core/test_messages.py -v`
Expected: 4/4 PASS

- [ ] **Step 5.6 : Commit**

```bash
git add src/fahmi2/core/errors/messages.py src/fahmi2/core/errors/messages.fr.json tests/unit/core/test_messages.py
git commit -m "feat(core/errors): registre de messages UI par code"
```

---

### Task 6: `core/logging/event.py` — LogEvent

**Files:**
- Create: `src/fahmi2/core/logging/__init__.py`
- Create: `src/fahmi2/core/logging/event.py`
- Test: `tests/unit/core/test_log_event.py`

- [ ] **Step 6.1 : Test failing**

```python
"""Tests de la dataclass LogEvent."""

from datetime import datetime, timezone

from fahmi2.core.errors.severity import Severity
from fahmi2.core.logging.event import LogEvent


def test_log_event_minimal() -> None:
    ts = datetime.now(tz=timezone.utc)
    ev = LogEvent(timestamp=ts, severity=Severity.INFO, code="X", message="hello")
    assert ev.timestamp == ts
    assert ev.severity is Severity.INFO
    assert ev.code == "X"
    assert ev.message == "hello"
    assert ev.run_id is None
    assert ev.extra == {}


def test_log_event_serializes_to_dict() -> None:
    ts = datetime(2026, 5, 19, 12, 0, 0, tzinfo=timezone.utc)
    ev = LogEvent(
        timestamp=ts,
        severity=Severity.WARNING,
        code="PHASE_STARTED",
        message="…",
        run_id="01HABC",
        phase_id="phase_3_reformulation",
        video_id="01VID",
        extra={"tokens": 1234},
    )
    payload = ev.to_dict()
    assert payload["timestamp"] == "2026-05-19T12:00:00+00:00"
    assert payload["severity"] == "warning"
    assert payload["code"] == "PHASE_STARTED"
    assert payload["run_id"] == "01HABC"
    assert payload["phase_id"] == "phase_3_reformulation"
    assert payload["video_id"] == "01VID"
    assert payload["extra"] == {"tokens": 1234}


def test_log_event_to_dict_excludes_none_optionals() -> None:
    ts = datetime.now(tz=timezone.utc)
    ev = LogEvent(timestamp=ts, severity=Severity.INFO, code="X", message="m")
    payload = ev.to_dict()
    assert payload["run_id"] is None
    assert payload["phase_id"] is None
    assert payload["video_id"] is None
```

- [ ] **Step 6.2 : Run, vérifier l'échec**

Run: `pytest tests/unit/core/test_log_event.py -v`
Expected: FAIL

- [ ] **Step 6.3 : Implémenter**

`src/fahmi2/core/logging/__init__.py` :
```python
"""Sous-système de logging structuré."""
```

`src/fahmi2/core/logging/event.py` :
```python
"""Modèle d'événement de log structuré.

Tous les sinks (JSONL, Qt, console) consomment des LogEvent. Les LogEvent sont
immuables et sérialisables en JSON sans transformation supplémentaire.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from fahmi2.core.errors.severity import Severity


@dataclass(frozen=True)
class LogEvent:
    """Événement de log structuré.

    Attributes:
        timestamp: Datetime aware (UTC recommandé).
        severity: Niveau de sévérité (Severity.INFO/WARNING/ERROR/FATAL).
        code: Code stable identifiant le type d'événement.
        message: Texte libre destiné au lecteur.
        run_id: ULID du Run associé, optionnel.
        phase_id: Identifiant de la phase associée, optionnel.
        video_id: ULID de la vidéo associée, optionnel.
        extra: Métadonnées additionnelles (sérialisable JSON).
    """

    timestamp: datetime
    severity: Severity
    code: str
    message: str
    run_id: str | None = None
    phase_id: str | None = None
    video_id: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Sérialise en dict JSON-friendly."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "severity": str(self.severity),
            "code": self.code,
            "message": self.message,
            "run_id": self.run_id,
            "phase_id": self.phase_id,
            "video_id": self.video_id,
            "extra": dict(self.extra),
        }
```

- [ ] **Step 6.4 : Run, vérifier PASS**

Run: `pytest tests/unit/core/test_log_event.py -v`
Expected: 3/3 PASS

- [ ] **Step 6.5 : Commit**

```bash
git add src/fahmi2/core/logging/__init__.py src/fahmi2/core/logging/event.py tests/unit/core/test_log_event.py
git commit -m "feat(core/logging): LogEvent structure immuable"
```

---

### Task 7: `core/logging/sink.py` — interface LogSink + redaction des secrets

**Files:**
- Create: `src/fahmi2/core/logging/sink.py`
- Test: `tests/unit/core/test_sink.py`

- [ ] **Step 7.1 : Test failing**

```python
"""Tests de l'interface LogSink et de la redaction des secrets."""

from datetime import datetime, timezone

import pytest

from fahmi2.core.errors.severity import Severity
from fahmi2.core.logging.event import LogEvent
from fahmi2.core.logging.sink import (
    LogSink,
    MinSeverityFilter,
    SecretRedactor,
    register_secret,
    unregister_secret,
)


class _CapturingSink(LogSink):
    def __init__(self, min_severity: Severity = Severity.INFO) -> None:
        super().__init__(min_severity=min_severity)
        self.events: list[LogEvent] = []

    def _write(self, event: LogEvent) -> None:
        self.events.append(event)


def _evt(message: str = "msg", severity: Severity = Severity.INFO) -> LogEvent:
    return LogEvent(
        timestamp=datetime.now(tz=timezone.utc),
        severity=severity,
        code="X",
        message=message,
    )


def test_sink_emits_passes_event_through_redactor_and_filter() -> None:
    sink = _CapturingSink(min_severity=Severity.INFO)
    sink.emit(_evt("hello"))
    assert len(sink.events) == 1


def test_min_severity_filter_drops_below() -> None:
    f = MinSeverityFilter(Severity.WARNING)
    assert not f.allow(_evt(severity=Severity.INFO))
    assert f.allow(_evt(severity=Severity.WARNING))
    assert f.allow(_evt(severity=Severity.ERROR))


def test_sink_drops_below_min_severity() -> None:
    sink = _CapturingSink(min_severity=Severity.WARNING)
    sink.emit(_evt(severity=Severity.INFO))
    assert sink.events == []


def test_secret_redactor_replaces_registered_value() -> None:
    register_secret("sk-abc123")
    try:
        redactor = SecretRedactor()
        assert redactor.redact("voici sk-abc123 dans un texte") == "voici *** dans un texte"
    finally:
        unregister_secret("sk-abc123")


def test_sink_redacts_secrets_in_message_and_extra() -> None:
    register_secret("sk-abc123")
    try:
        sink = _CapturingSink()
        ev = LogEvent(
            timestamp=datetime.now(tz=timezone.utc),
            severity=Severity.INFO,
            code="X",
            message="key=sk-abc123",
            extra={"prompt": "use sk-abc123"},
        )
        sink.emit(ev)
        assert "sk-abc123" not in sink.events[0].message
        assert "sk-abc123" not in sink.events[0].extra["prompt"]
    finally:
        unregister_secret("sk-abc123")


def test_register_secret_ignores_empty_or_short() -> None:
    with pytest.raises(ValueError):
        register_secret("")
    with pytest.raises(ValueError):
        register_secret("ab")
```

- [ ] **Step 7.2 : Run, vérifier l'échec**

Run: `pytest tests/unit/core/test_sink.py -v`
Expected: FAIL

- [ ] **Step 7.3 : Implémenter `src/fahmi2/core/logging/sink.py`**

```python
"""Abstraction LogSink + redaction globale des secrets.

Tout sink concret hérite de LogSink, applique un filtrage par sévérité minimale
puis une passe de redaction des secrets enregistrés via register_secret avant
de déléguer l'écriture effective à _write.
"""

from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from dataclasses import replace
from typing import Any

from fahmi2.core.errors.severity import Severity
from fahmi2.core.logging.event import LogEvent

_REDACTION_PLACEHOLDER = "***"
_MIN_SECRET_LENGTH = 4

_secret_lock = threading.Lock()
_secrets: set[str] = set()


def register_secret(value: str) -> None:
    """Enregistre une valeur sensible à masquer dans tous les logs futurs.

    Args:
        value: Valeur secrète (clé API, token, etc.).

    Raises:
        ValueError: Si la valeur est trop courte ou vide (risque de matching massif).
    """
    if not value or len(value) < _MIN_SECRET_LENGTH:
        raise ValueError(
            f"Secret value must be at least {_MIN_SECRET_LENGTH} characters"
        )
    with _secret_lock:
        _secrets.add(value)


def unregister_secret(value: str) -> None:
    """Désenregistre une valeur (utile pour les tests)."""
    with _secret_lock:
        _secrets.discard(value)


class SecretRedactor:
    """Remplace toutes les occurrences des secrets enregistrés par ***."""

    def redact(self, text: str) -> str:
        with _secret_lock:
            secrets = tuple(_secrets)
        for secret in secrets:
            text = text.replace(secret, _REDACTION_PLACEHOLDER)
        return text

    def redact_value(self, value: Any) -> Any:
        if isinstance(value, str):
            return self.redact(value)
        if isinstance(value, dict):
            return {k: self.redact_value(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self.redact_value(v) for v in value]
        return value


class MinSeverityFilter:
    """Garde uniquement les événements >= un seuil minimal."""

    def __init__(self, min_severity: Severity) -> None:
        self.min_severity = min_severity

    def allow(self, event: LogEvent) -> bool:
        return event.severity >= self.min_severity


class LogSink(ABC):
    """Abstraction d'un sink de logs.

    Les sous-classes implémentent _write pour persister/afficher l'événement.
    emit() est le point d'entrée standard : il filtre par sévérité puis applique
    la redaction des secrets avant de déléguer à _write.
    """

    def __init__(self, *, min_severity: Severity = Severity.INFO) -> None:
        self._filter = MinSeverityFilter(min_severity)
        self._redactor = SecretRedactor()

    def emit(self, event: LogEvent) -> None:
        if not self._filter.allow(event):
            return
        redacted = replace(
            event,
            message=self._redactor.redact(event.message),
            extra=self._redactor.redact_value(event.extra),
        )
        self._write(redacted)

    @abstractmethod
    def _write(self, event: LogEvent) -> None:
        """Méthode à implémenter par les sous-classes."""
```

- [ ] **Step 7.4 : Run, vérifier PASS**

Run: `pytest tests/unit/core/test_sink.py -v`
Expected: 6/6 PASS

- [ ] **Step 7.5 : Commit**

```bash
git add src/fahmi2/core/logging/sink.py tests/unit/core/test_sink.py
git commit -m "feat(core/logging): LogSink + redaction globale des secrets"
```

---

### Task 8: `core/logging/jsonl_sink.py` — sink JSONL fichier

**Files:**
- Create: `src/fahmi2/core/logging/jsonl_sink.py`
- Test: `tests/unit/core/test_jsonl_sink.py`

- [ ] **Step 8.1 : Test failing**

```python
"""Tests du sink fichier JSONL."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from fahmi2.core.errors.severity import Severity
from fahmi2.core.logging.event import LogEvent
from fahmi2.core.logging.jsonl_sink import JsonlFileSink


def _evt(code: str = "X", severity: Severity = Severity.INFO) -> LogEvent:
    return LogEvent(
        timestamp=datetime(2026, 5, 19, 12, 0, 0, tzinfo=timezone.utc),
        severity=severity,
        code=code,
        message="m",
    )


def test_jsonl_sink_writes_one_line_per_event(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    sink = JsonlFileSink(path)
    try:
        sink.emit(_evt("A"))
        sink.emit(_evt("B"))
    finally:
        sink.close()

    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["code"] == "A"
    assert json.loads(lines[1])["code"] == "B"


def test_jsonl_sink_creates_parent_dir(tmp_path: Path) -> None:
    path = tmp_path / "sub" / "events.jsonl"
    sink = JsonlFileSink(path)
    sink.close()
    assert path.exists()


def test_jsonl_sink_respects_min_severity(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    sink = JsonlFileSink(path, min_severity=Severity.WARNING)
    try:
        sink.emit(_evt("low", severity=Severity.INFO))
        sink.emit(_evt("high", severity=Severity.WARNING))
    finally:
        sink.close()
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["code"] == "high"


def test_jsonl_sink_can_be_used_as_context_manager(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    with JsonlFileSink(path) as sink:
        sink.emit(_evt())
    assert path.read_text(encoding="utf-8").strip()
```

- [ ] **Step 8.2 : Run, vérifier l'échec**

Run: `pytest tests/unit/core/test_jsonl_sink.py -v`
Expected: FAIL

- [ ] **Step 8.3 : Implémenter**

```python
"""Sink d'écriture des LogEvent en JSON lignes (.jsonl)."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from types import TracebackType
from typing import IO

from fahmi2.core.errors.severity import Severity
from fahmi2.core.logging.event import LogEvent
from fahmi2.core.logging.sink import LogSink


class JsonlFileSink(LogSink):
    """Écrit chaque LogEvent sous forme d'une ligne JSON dans un fichier .jsonl.

    Thread-safe : un verrou interne sérialise les écritures concurrentes.
    Le fichier est ouvert en mode append + utf-8 + line-buffering pour limiter
    la perte de données en cas de crash.
    """

    def __init__(self, path: Path, *, min_severity: Severity = Severity.INFO) -> None:
        super().__init__(min_severity=min_severity)
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._fp: IO[str] | None = self._path.open("a", encoding="utf-8", buffering=1)

    def _write(self, event: LogEvent) -> None:
        line = json.dumps(event.to_dict(), ensure_ascii=False, separators=(",", ":"))
        with self._lock:
            if self._fp is None:
                raise RuntimeError("JsonlFileSink is closed")
            self._fp.write(line + "\n")

    def close(self) -> None:
        with self._lock:
            if self._fp is not None:
                self._fp.flush()
                self._fp.close()
                self._fp = None

    def __enter__(self) -> JsonlFileSink:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()
```

- [ ] **Step 8.4 : Run, vérifier PASS**

Run: `pytest tests/unit/core/test_jsonl_sink.py -v`
Expected: 4/4 PASS

- [ ] **Step 8.5 : Commit**

```bash
git add src/fahmi2/core/logging/jsonl_sink.py tests/unit/core/test_jsonl_sink.py
git commit -m "feat(core/logging): JsonlFileSink thread-safe"
```

---

### Task 9: `core/retry/policy.py` — RetryPolicy

**Files:**
- Create: `src/fahmi2/core/retry/__init__.py`
- Create: `src/fahmi2/core/retry/policy.py`
- Test: `tests/unit/core/test_retry_policy.py`

- [ ] **Step 9.1 : Test failing**

```python
"""Tests de la RetryPolicy."""

import pytest

from fahmi2.core.retry.policy import RetryDecision, RetryPolicy


def test_default_policy_values() -> None:
    p = RetryPolicy()
    assert p.max_attempts == 5
    assert p.initial_delay_seconds == 1.0
    assert p.max_delay_seconds == 60.0
    assert p.backoff_multiplier == 2.0
    assert p.jitter is True


def test_compute_delay_grows_exponentially() -> None:
    p = RetryPolicy(
        initial_delay_seconds=1.0,
        max_delay_seconds=60.0,
        backoff_multiplier=2.0,
        jitter=False,
    )
    assert p.compute_delay(attempt=1) == 1.0
    assert p.compute_delay(attempt=2) == 2.0
    assert p.compute_delay(attempt=3) == 4.0
    assert p.compute_delay(attempt=4) == 8.0


def test_compute_delay_caps_at_max() -> None:
    p = RetryPolicy(
        initial_delay_seconds=10.0,
        max_delay_seconds=15.0,
        backoff_multiplier=2.0,
        jitter=False,
    )
    assert p.compute_delay(attempt=1) == 10.0
    assert p.compute_delay(attempt=2) == 15.0
    assert p.compute_delay(attempt=5) == 15.0


def test_jitter_stays_within_bounds() -> None:
    p = RetryPolicy(
        initial_delay_seconds=10.0,
        max_delay_seconds=100.0,
        backoff_multiplier=2.0,
        jitter=True,
    )
    for attempt in range(1, 6):
        base = min(10.0 * (2.0 ** (attempt - 1)), 100.0)
        for _ in range(100):
            d = p.compute_delay(attempt=attempt)
            assert 0.5 * base <= d <= 1.5 * base


def test_retry_decision_values() -> None:
    assert RetryDecision.RETRY.name == "RETRY"
    assert RetryDecision.NO_RETRY.name == "NO_RETRY"
    assert RetryDecision.RAISE_BUDGET.name == "RAISE_BUDGET"


def test_policy_validates_positive_max_attempts() -> None:
    with pytest.raises(ValueError):
        RetryPolicy(max_attempts=0)
    with pytest.raises(ValueError):
        RetryPolicy(max_attempts=-1)
```

- [ ] **Step 9.2 : Run, vérifier l'échec**

Run: `pytest tests/unit/core/test_retry_policy.py -v`
Expected: FAIL

- [ ] **Step 9.3 : Implémenter**

`src/fahmi2/core/retry/__init__.py` :
```python
"""Politique de retry et runner associé."""
```

`src/fahmi2/core/retry/policy.py` :
```python
"""Définition de RetryPolicy et énumération des décisions de retry."""

from __future__ import annotations

import random
from dataclasses import dataclass
from enum import Enum, auto


class RetryDecision(Enum):
    """Décision à prendre face à une exception levée par une opération à retry."""

    RETRY = auto()
    NO_RETRY = auto()
    RAISE_BUDGET = auto()


@dataclass(frozen=True)
class RetryPolicy:
    """Politique de retry exponentielle bornée avec jitter optionnel."""

    max_attempts: int = 5
    initial_delay_seconds: float = 1.0
    max_delay_seconds: float = 60.0
    backoff_multiplier: float = 2.0
    jitter: bool = True

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        if self.initial_delay_seconds <= 0:
            raise ValueError("initial_delay_seconds must be > 0")
        if self.max_delay_seconds < self.initial_delay_seconds:
            raise ValueError("max_delay_seconds must be >= initial_delay_seconds")
        if self.backoff_multiplier < 1:
            raise ValueError("backoff_multiplier must be >= 1")

    def compute_delay(self, *, attempt: int) -> float:
        """Calcule le délai d'attente avant la tentative `attempt` (1-indexed).

        Args:
            attempt: Numéro de tentative (1 = première retry après l'échec initial).

        Returns:
            Délai en secondes, borné par max_delay_seconds, éventuellement bruité.
        """
        if attempt < 1:
            raise ValueError("attempt must be >= 1")
        base = min(
            self.initial_delay_seconds * (self.backoff_multiplier ** (attempt - 1)),
            self.max_delay_seconds,
        )
        if not self.jitter:
            return base
        return base * random.uniform(0.5, 1.5)  # noqa: S311 — non-crypto
```

- [ ] **Step 9.4 : Run, vérifier PASS**

Run: `pytest tests/unit/core/test_retry_policy.py -v`
Expected: 6/6 PASS

- [ ] **Step 9.5 : Commit**

```bash
git add src/fahmi2/core/retry/__init__.py src/fahmi2/core/retry/policy.py tests/unit/core/test_retry_policy.py
git commit -m "feat(core/retry): RetryPolicy avec backoff exponentiel et jitter"
```

---

### Task 10: `core/retry/runner.py` — fonction with_retry()

**Files:**
- Create: `src/fahmi2/core/retry/runner.py`
- Test: `tests/unit/core/test_retry_runner.py`

- [ ] **Step 10.1 : Test failing**

```python
"""Tests du runner with_retry()."""

import pytest

from fahmi2.core.errors.exceptions import (
    BudgetExceededError,
    Fahmi2Error,
    PermanentError,
    TransientError,
)
from fahmi2.core.errors.severity import Severity
from fahmi2.core.retry.policy import RetryDecision, RetryPolicy
from fahmi2.core.retry.runner import with_retry


def _make_error(cls: type[Fahmi2Error] = TransientError) -> Fahmi2Error:
    return cls(code="X", user_message="oops", severity=Severity.ERROR)


def _classifier_default(exc: BaseException) -> RetryDecision:
    if isinstance(exc, BudgetExceededError):
        return RetryDecision.RAISE_BUDGET
    if isinstance(exc, TransientError):
        return RetryDecision.RETRY
    return RetryDecision.NO_RETRY


def test_with_retry_returns_value_on_first_attempt() -> None:
    calls = {"n": 0}

    def fn() -> str:
        calls["n"] += 1
        return "ok"

    result = with_retry(fn, policy=RetryPolicy(jitter=False), classify=_classifier_default)
    assert result == "ok"
    assert calls["n"] == 1


def test_with_retry_retries_until_success() -> None:
    calls = {"n": 0}

    def fn() -> str:
        calls["n"] += 1
        if calls["n"] < 3:
            raise _make_error(TransientError)
        return "ok"

    result = with_retry(
        fn,
        policy=RetryPolicy(max_attempts=5, initial_delay_seconds=0.001, jitter=False),
        classify=_classifier_default,
    )
    assert result == "ok"
    assert calls["n"] == 3


def test_with_retry_raises_after_max_attempts() -> None:
    def fn() -> None:
        raise _make_error(TransientError)

    with pytest.raises(TransientError):
        with_retry(
            fn,
            policy=RetryPolicy(max_attempts=3, initial_delay_seconds=0.001, jitter=False),
            classify=_classifier_default,
        )


def test_with_retry_no_retry_decision_raises_immediately() -> None:
    calls = {"n": 0}

    def fn() -> None:
        calls["n"] += 1
        raise _make_error(PermanentError)

    with pytest.raises(PermanentError):
        with_retry(
            fn,
            policy=RetryPolicy(max_attempts=5, initial_delay_seconds=0.001, jitter=False),
            classify=_classifier_default,
        )
    assert calls["n"] == 1


def test_with_retry_raises_budget_immediately() -> None:
    calls = {"n": 0}

    def fn() -> None:
        calls["n"] += 1
        raise BudgetExceededError(
            code="BUDGET.EXCEEDED",
            user_message="oups",
            severity=Severity.WARNING,
        )

    with pytest.raises(BudgetExceededError):
        with_retry(
            fn,
            policy=RetryPolicy(max_attempts=5, initial_delay_seconds=0.001, jitter=False),
            classify=_classifier_default,
        )
    assert calls["n"] == 1


def test_with_retry_propagates_unexpected_exceptions() -> None:
    def fn() -> None:
        raise ValueError("plain")

    with pytest.raises(ValueError):
        with_retry(
            fn,
            policy=RetryPolicy(max_attempts=3, initial_delay_seconds=0.001, jitter=False),
            classify=_classifier_default,
        )
```

- [ ] **Step 10.2 : Run, vérifier l'échec**

Run: `pytest tests/unit/core/test_retry_runner.py -v`
Expected: FAIL

- [ ] **Step 10.3 : Implémenter**

```python
"""Exécution d'une fonction avec retry exponentiel et classification d'erreur."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import TypeVar

from fahmi2.core.retry.policy import RetryDecision, RetryPolicy

T = TypeVar("T")


def with_retry(
    fn: Callable[[], T],
    *,
    policy: RetryPolicy,
    classify: Callable[[BaseException], RetryDecision],
    sleep: Callable[[float], None] = time.sleep,
) -> T:
    """Exécute fn avec retry selon la policy et la fonction de classification.

    Args:
        fn: Fonction sans argument à exécuter.
        policy: Politique de retry (nombre d'essais, backoff, jitter).
        classify: Fonction qui décide RETRY / NO_RETRY / RAISE_BUDGET face à une exception.
        sleep: Fonction d'attente, injectable pour les tests.

    Returns:
        La valeur retournée par fn lors d'une exécution réussie.

    Raises:
        BaseException: La dernière exception levée par fn si toutes les tentatives échouent
            ou si classify retourne NO_RETRY / RAISE_BUDGET.
    """
    last_exc: BaseException | None = None
    for attempt in range(1, policy.max_attempts + 1):
        try:
            return fn()
        except BaseException as exc:  # noqa: BLE001 — on relaie via classify
            last_exc = exc
            decision = classify(exc)
            if decision is RetryDecision.NO_RETRY:
                raise
            if decision is RetryDecision.RAISE_BUDGET:
                raise
            # RETRY
            if attempt >= policy.max_attempts:
                raise
            sleep(policy.compute_delay(attempt=attempt))
    # Inatteignable (boucle ci-dessus retourne ou lève), mais nécessaire pour mypy
    assert last_exc is not None
    raise last_exc
```

- [ ] **Step 10.4 : Run, vérifier PASS**

Run: `pytest tests/unit/core/test_retry_runner.py -v`
Expected: 6/6 PASS

- [ ] **Step 10.5 : Commit**

```bash
git add src/fahmi2/core/retry/runner.py tests/unit/core/test_retry_runner.py
git commit -m "feat(core/retry): runner with_retry() avec classifier injectable"
```

---

### Task 11: `core/config/paths.py` — chemins standards Windows

**Files:**
- Create: `src/fahmi2/core/config/__init__.py`
- Create: `src/fahmi2/core/config/paths.py`
- Test: `tests/unit/core/test_paths.py`

- [ ] **Step 11.1 : Test failing**

```python
"""Tests de la résolution des chemins standards Windows."""

from pathlib import Path

import pytest

from fahmi2.core.config.paths import AppPaths


def test_paths_uses_env_appdata(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("APPDATA", str(tmp_path / "Roaming"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "Local"))
    paths = AppPaths.default()
    assert paths.appdata == tmp_path / "Roaming" / "Fahmi2"
    assert paths.localappdata == tmp_path / "Local" / "Fahmi2"


def test_paths_secrets_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("APPDATA", str(tmp_path / "Roaming"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "Local"))
    paths = AppPaths.default()
    assert paths.secrets_file == tmp_path / "Roaming" / "Fahmi2" / "secrets.dat"


def test_paths_models_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("APPDATA", str(tmp_path / "Roaming"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "Local"))
    paths = AppPaths.default()
    assert paths.models_dir == tmp_path / "Local" / "Fahmi2" / "models"


def test_paths_projects_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("APPDATA", str(tmp_path / "Roaming"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "Local"))
    paths = AppPaths.default()
    assert paths.projects_dir == tmp_path / "Roaming" / "Fahmi2" / "projects"


def test_paths_prompts_override_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("APPDATA", str(tmp_path / "Roaming"))
    paths = AppPaths.default()
    assert paths.prompts_override_dir == tmp_path / "Roaming" / "Fahmi2" / "prompts"


def test_paths_ensure_creates_directories(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("APPDATA", str(tmp_path / "Roaming"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "Local"))
    paths = AppPaths.default()
    paths.ensure_dirs()
    assert paths.appdata.is_dir()
    assert paths.localappdata.is_dir()
    assert paths.projects_dir.is_dir()
    assert paths.prompts_override_dir.is_dir()
    assert paths.models_dir.is_dir()


def test_paths_missing_appdata_falls_back(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("APPDATA", raising=False)
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "user"))
    paths = AppPaths.default()
    assert paths.appdata == tmp_path / "user" / "AppData" / "Roaming" / "Fahmi2"
```

- [ ] **Step 11.2 : Run, vérifier l'échec**

Run: `pytest tests/unit/core/test_paths.py -v`
Expected: FAIL

- [ ] **Step 11.3 : Implémenter**

`src/fahmi2/core/config/__init__.py` :
```python
"""Configuration et chemins de l'application."""
```

`src/fahmi2/core/config/paths.py` :
```python
"""Résolution des chemins standards Windows utilisés par l'application.

Suit les conventions Windows : APPDATA pour les données utilisateur synchronisables
(profils itinérants), LOCALAPPDATA pour les caches volumineux (modèles whisper).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

_APP_FOLDER = "Fahmi2"


def _resolve_env_dir(env_var: str, fallback_relative: str) -> Path:
    """Résout une variable d'environnement Windows, avec fallback sur USERPROFILE."""
    value = os.environ.get(env_var)
    if value:
        return Path(value)
    profile = os.environ.get("USERPROFILE")
    if profile:
        return Path(profile) / fallback_relative
    return Path.home() / fallback_relative


@dataclass(frozen=True)
class AppPaths:
    """Conteneur immutable des chemins applicatifs résolus."""

    appdata: Path
    localappdata: Path

    @classmethod
    def default(cls) -> AppPaths:
        """Résolution standard pour Windows (avec fallbacks)."""
        return cls(
            appdata=_resolve_env_dir("APPDATA", "AppData/Roaming") / _APP_FOLDER,
            localappdata=_resolve_env_dir("LOCALAPPDATA", "AppData/Local") / _APP_FOLDER,
        )

    @property
    def secrets_file(self) -> Path:
        return self.appdata / "secrets.dat"

    @property
    def projects_dir(self) -> Path:
        return self.appdata / "projects"

    @property
    def prompts_override_dir(self) -> Path:
        return self.appdata / "prompts"

    @property
    def models_dir(self) -> Path:
        return self.localappdata / "models"

    @property
    def backups_dir(self) -> Path:
        return self.appdata / "backups"

    def ensure_dirs(self) -> None:
        """Crée tous les répertoires standards s'ils n'existent pas."""
        for path in (
            self.appdata,
            self.localappdata,
            self.projects_dir,
            self.prompts_override_dir,
            self.models_dir,
            self.backups_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)
```

- [ ] **Step 11.4 : Run, vérifier PASS**

Run: `pytest tests/unit/core/test_paths.py -v`
Expected: 7/7 PASS

- [ ] **Step 11.5 : Commit**

```bash
git add src/fahmi2/core/config/__init__.py src/fahmi2/core/config/paths.py tests/unit/core/test_paths.py
git commit -m "feat(core/config): resolution des chemins Windows standards"
```

---

### Task 12: `core/config/app_config.py` — AppConfig

**Files:**
- Create: `src/fahmi2/core/config/app_config.py`
- Test: `tests/unit/core/test_app_config.py`

- [ ] **Step 12.1 : Test failing**

```python
"""Tests de AppConfig (configuration globale immutable)."""

from pathlib import Path

from fahmi2.core.config.app_config import AppConfig
from fahmi2.core.config.paths import AppPaths


def test_app_config_defaults(tmp_path: Path) -> None:
    paths = AppPaths(appdata=tmp_path / "app", localappdata=tmp_path / "local")
    cfg = AppConfig(paths=paths)
    assert cfg.paths is paths
    assert cfg.ui_log_level_default == "INFO"
    assert cfg.theme == "system"
    assert cfg.last_project_id is None


def test_app_config_can_set_optional_fields(tmp_path: Path) -> None:
    paths = AppPaths(appdata=tmp_path / "app", localappdata=tmp_path / "local")
    cfg = AppConfig(
        paths=paths,
        ui_log_level_default="WARNING",
        theme="dark",
        last_project_id="01HABC",
    )
    assert cfg.ui_log_level_default == "WARNING"
    assert cfg.theme == "dark"
    assert cfg.last_project_id == "01HABC"
```

- [ ] **Step 12.2 : Run, vérifier l'échec**

Run: `pytest tests/unit/core/test_app_config.py -v`
Expected: FAIL

- [ ] **Step 12.3 : Implémenter**

```python
"""Configuration globale immutable de l'application."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from fahmi2.core.config.paths import AppPaths

LogLevelName = Literal["DEBUG", "INFO", "WARNING", "ERROR"]
ThemeName = Literal["system", "light", "dark"]


@dataclass(frozen=True)
class AppConfig:
    """Configuration globale (préférences UI + chemins).

    Cette dataclass représente l'état persistant *côté machine de l'utilisateur*
    pour les préférences générales — pas les paramètres d'un projet, qui vivent
    dans ProjectSettings.
    """

    paths: AppPaths
    ui_log_level_default: LogLevelName = "INFO"
    theme: ThemeName = "system"
    last_project_id: str | None = None
```

- [ ] **Step 12.4 : Run, vérifier PASS**

Run: `pytest tests/unit/core/test_app_config.py -v`
Expected: 2/2 PASS

- [ ] **Step 12.5 : Commit**

```bash
git add src/fahmi2/core/config/app_config.py tests/unit/core/test_app_config.py
git commit -m "feat(core/config): AppConfig pour preferences globales"
```

---

### Task 13: `core/migrations/runner.py` — MigrationRunner stub

**Files:**
- Create: `src/fahmi2/core/migrations/__init__.py`
- Create: `src/fahmi2/core/migrations/runner.py`
- Test: `tests/unit/core/test_migration_runner.py`

- [ ] **Step 13.1 : Test failing**

```python
"""Tests du MigrationRunner."""

from dataclasses import dataclass

import pytest

from fahmi2.core.migrations.runner import Migration, MigrationRunner


@dataclass
class _MutableState:
    schema_version: int = 0
    applied: list[int] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.applied is None:
            self.applied = []


def _make_migration(from_v: int, to_v: int) -> Migration[_MutableState]:
    def _apply(s: _MutableState) -> None:
        s.applied.append(to_v)
        s.schema_version = to_v

    return Migration(from_version=from_v, to_version=to_v, apply=_apply)


def test_runner_applies_no_migration_when_uptodate() -> None:
    state = _MutableState(schema_version=2)
    runner = MigrationRunner[_MutableState](
        migrations=[_make_migration(1, 2), _make_migration(2, 3)],
        target_version=2,
    )
    runner.run(state)
    assert state.applied == []


def test_runner_applies_one_migration() -> None:
    state = _MutableState(schema_version=1)
    runner = MigrationRunner[_MutableState](
        migrations=[_make_migration(1, 2)],
        target_version=2,
    )
    runner.run(state)
    assert state.applied == [2]
    assert state.schema_version == 2


def test_runner_applies_chain() -> None:
    state = _MutableState(schema_version=1)
    runner = MigrationRunner[_MutableState](
        migrations=[
            _make_migration(1, 2),
            _make_migration(2, 3),
            _make_migration(3, 4),
        ],
        target_version=4,
    )
    runner.run(state)
    assert state.applied == [2, 3, 4]
    assert state.schema_version == 4


def test_runner_raises_when_no_path() -> None:
    state = _MutableState(schema_version=1)
    runner = MigrationRunner[_MutableState](
        migrations=[_make_migration(2, 3)],
        target_version=3,
    )
    with pytest.raises(RuntimeError):
        runner.run(state)


def test_runner_refuses_downgrade() -> None:
    state = _MutableState(schema_version=5)
    runner = MigrationRunner[_MutableState](
        migrations=[_make_migration(1, 2)],
        target_version=2,
    )
    with pytest.raises(RuntimeError):
        runner.run(state)
```

- [ ] **Step 13.2 : Run, vérifier l'échec**

Run: `pytest tests/unit/core/test_migration_runner.py -v`
Expected: FAIL

- [ ] **Step 13.3 : Implémenter**

`src/fahmi2/core/migrations/__init__.py` :
```python
"""Système de migrations forward-only pour les artefacts persistants."""
```

`src/fahmi2/core/migrations/runner.py` :
```python
"""Runner de migrations forward-only avec chaînage automatique."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic, Protocol, TypeVar

S = TypeVar("S")


class _HasSchemaVersion(Protocol):
    schema_version: int


SS = TypeVar("SS", bound=_HasSchemaVersion)


@dataclass(frozen=True)
class Migration(Generic[S]):
    """Migration unitaire d'un schéma vX vers vX+1.

    `apply` doit muter `state` en place et mettre à jour `state.schema_version`.
    """

    from_version: int
    to_version: int
    apply: Callable[[S], None]


class MigrationRunner(Generic[SS]):
    """Applique en chaîne les migrations nécessaires pour atteindre target_version.

    Migrations forward-only : refuse les downgrades (target < current).
    """

    def __init__(
        self,
        *,
        migrations: list[Migration[SS]],
        target_version: int,
    ) -> None:
        self._by_from: dict[int, Migration[SS]] = {m.from_version: m for m in migrations}
        self._target = target_version

    def run(self, state: SS) -> None:
        if state.schema_version > self._target:
            raise RuntimeError(
                f"Cannot downgrade schema from v{state.schema_version} to v{self._target}"
            )
        while state.schema_version < self._target:
            current = state.schema_version
            mig = self._by_from.get(current)
            if mig is None:
                raise RuntimeError(
                    f"No migration path from v{current} towards v{self._target}"
                )
            mig.apply(state)
            if state.schema_version <= current:
                raise RuntimeError(
                    f"Migration {mig.from_version}->{mig.to_version} did not advance "
                    f"schema_version (got v{state.schema_version})"
                )
```

- [ ] **Step 13.4 : Run, vérifier PASS**

Run: `pytest tests/unit/core/test_migration_runner.py -v`
Expected: 5/5 PASS

- [ ] **Step 13.5 : Commit**

```bash
git add src/fahmi2/core/migrations/ tests/unit/core/test_migration_runner.py
git commit -m "feat(core/migrations): MigrationRunner forward-only generique"
```

---

### Task 14: `core/retrieval/interface.py` — GlossaryRetriever interface

**Files:**
- Create: `src/fahmi2/core/retrieval/__init__.py`
- Create: `src/fahmi2/core/retrieval/interface.py`
- Test: `tests/unit/core/test_retrieval_interface.py`

L'implémentation TF-IDF concrète sera produite par le **Plan 04** (Retrieval). Ici on définit uniquement l'interface stable et une implémentation triviale "passthrough" pour permettre aux tests des autres modules de s'appuyer sur l'interface sans dépendre encore de scikit-learn.

- [ ] **Step 14.1 : Test failing**

```python
"""Tests de l'interface GlossaryRetriever et de son implémentation triviale."""

from fahmi2.core.retrieval.interface import GlossaryRetriever, PassthroughRetriever


def test_passthrough_returns_all_terms_unchanged() -> None:
    retriever = PassthroughRetriever()
    terms = ["alpha", "beta", "gamma"]
    result = retriever.retrieve(query="anything", terms=terms, top_k=10)
    assert result == terms


def test_passthrough_respects_top_k() -> None:
    retriever = PassthroughRetriever()
    terms = ["alpha", "beta", "gamma"]
    result = retriever.retrieve(query="anything", terms=terms, top_k=2)
    assert result == ["alpha", "beta"]


def test_passthrough_handles_empty() -> None:
    retriever = PassthroughRetriever()
    result = retriever.retrieve(query="x", terms=[], top_k=10)
    assert result == []


def test_passthrough_satisfies_protocol() -> None:
    # Sanity check : PassthroughRetriever satisfait bien le Protocol
    retriever: GlossaryRetriever = PassthroughRetriever()
    _ = retriever.retrieve(query="x", terms=["y"], top_k=1)
```

- [ ] **Step 14.2 : Run, vérifier l'échec**

Run: `pytest tests/unit/core/test_retrieval_interface.py -v`
Expected: FAIL

- [ ] **Step 14.3 : Implémenter**

`src/fahmi2/core/retrieval/__init__.py` :
```python
"""Interface de retrieval pour le top-K du glossaire."""
```

`src/fahmi2/core/retrieval/interface.py` :
```python
"""Interface stable pour le retrieval top-K du glossaire injecté en contexte LLM.

L'implémentation TF-IDF concrète vit dans un autre module (livraison Plan 04).
Cette interface permet de tester les phases LLM sans dépendre encore de
scikit-learn et autorise un swap futur vers embeddings.
"""

from __future__ import annotations

from typing import Protocol


class GlossaryRetriever(Protocol):
    """Sélectionne les termes du glossaire les plus pertinents pour un contenu."""

    def retrieve(self, *, query: str, terms: list[str], top_k: int) -> list[str]:
        """Retourne au plus top_k termes du glossaire, classés par pertinence.

        Args:
            query: Texte (chunk de contenu) pour lequel on cherche des termes pertinents.
            terms: Liste candidate des termes du glossaire.
            top_k: Nombre maximal de termes à retourner.

        Returns:
            Sous-liste de `terms`, triée par pertinence décroissante, taille <= top_k.
        """


class PassthroughRetriever:
    """Implémentation triviale qui renvoie les premiers top_k termes inchangés.

    Utile pour les tests et pour les contextes où le glossaire est petit
    (pas besoin de retrieval réel).
    """

    def retrieve(self, *, query: str, terms: list[str], top_k: int) -> list[str]:
        del query  # non utilisé
        return list(terms[:top_k])
```

- [ ] **Step 14.4 : Run, vérifier PASS**

Run: `pytest tests/unit/core/test_retrieval_interface.py -v`
Expected: 4/4 PASS

- [ ] **Step 14.5 : Commit**

```bash
git add src/fahmi2/core/retrieval/ tests/unit/core/test_retrieval_interface.py
git commit -m "feat(core/retrieval): interface GlossaryRetriever + Passthrough"
```

---

### Task 15: `domain/enums.py` — Énumérations du domaine

**Files:**
- Create: `src/fahmi2/domain/__init__.py`
- Create: `src/fahmi2/domain/enums.py`
- Test: `tests/unit/domain/test_enums.py`

- [ ] **Step 15.1 : Test failing**

```python
"""Tests des énumérations du domaine."""

import pytest

from fahmi2.domain.enums import (
    Language,
    LLMModel,
    PhaseId,
    PhaseStatus,
    RunStatus,
    SttProvider,
    StylePreset,
)


def test_language_values() -> None:
    assert {lang.value for lang in Language} == {"fr", "en"}


def test_style_preset_values() -> None:
    assert {s.value for s in StylePreset} == {
        "decontracte",
        "standard",
        "professionnel",
        "academique",
    }


def test_phase_id_has_eight_phases() -> None:
    # phase 0 (STT) + phases 1..7 (LLM)
    assert len(list(PhaseId)) == 8


def test_phase_id_values_are_namespaced() -> None:
    for pid in PhaseId:
        assert pid.value.startswith("phase_")


def test_run_status_values() -> None:
    assert {s.value for s in RunStatus} == {
        "created",
        "running",
        "paused",
        "cancelled",
        "completed",
        "failed",
    }


def test_phase_status_values() -> None:
    assert {s.value for s in PhaseStatus} == {
        "pending",
        "running",
        "succeeded",
        "failed",
        "skipped",
    }


def test_stt_provider_values() -> None:
    assert {p.value for p in SttProvider} == {"faster_whisper_local", "openai_cloud"}


def test_llm_model_values() -> None:
    assert {m.value for m in LLMModel} == {"deepseek-v4-flash", "deepseek-v4-pro"}


def test_enum_from_str() -> None:
    assert Language("fr") is Language.FR
    assert RunStatus("running") is RunStatus.RUNNING


def test_enum_rejects_unknown() -> None:
    with pytest.raises(ValueError):
        Language("de")
```

- [ ] **Step 15.2 : Run, vérifier l'échec**

Run: `pytest tests/unit/domain/test_enums.py -v`
Expected: FAIL

- [ ] **Step 15.3 : Implémenter**

`src/fahmi2/domain/__init__.py` :
```python
"""Entités, énumérations et machines d'état du domaine."""
```

`src/fahmi2/domain/enums.py` :
```python
"""Énumérations stables du domaine Fahmi2."""

from __future__ import annotations

from enum import StrEnum


class Language(StrEnum):
    """Langues supportées en v1 (entrée et sortie)."""

    FR = "fr"
    EN = "en"


class StylePreset(StrEnum):
    """Style de rendu de la reformulation."""

    DECONTRACTE = "decontracte"
    STANDARD = "standard"
    PROFESSIONNEL = "professionnel"
    ACADEMIQUE = "academique"


class PhaseId(StrEnum):
    """Identifiants stables des phases du pipeline."""

    STT = "phase_0_stt"
    TERM_EXTRACTION = "phase_1_term_extraction"
    GLOSSARY_RECONCILIATION = "phase_2_glossary_reconciliation"
    REFORMULATION = "phase_3_reformulation"
    STRUCTURATION = "phase_4_structuration"
    CONSOLIDATION = "phase_5_consolidation"
    TRANSLATION = "phase_6_translation"
    COHERENCE = "phase_7_coherence"


class RunStatus(StrEnum):
    """État global d'un Run."""

    CREATED = "created"
    RUNNING = "running"
    PAUSED = "paused"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    FAILED = "failed"


class PhaseStatus(StrEnum):
    """État d'exécution d'une phase pour une vidéo (ou pour le batch entier)."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"


class SttProvider(StrEnum):
    """Providers de speech-to-text supportés."""

    FASTER_WHISPER_LOCAL = "faster_whisper_local"
    OPENAI_CLOUD = "openai_cloud"


class LLMModel(StrEnum):
    """Modèles DeepSeek supportés."""

    DEEPSEEK_V4_FLASH = "deepseek-v4-flash"
    DEEPSEEK_V4_PRO = "deepseek-v4-pro"
```

- [ ] **Step 15.4 : Run, vérifier PASS**

Run: `pytest tests/unit/domain/test_enums.py -v`
Expected: 10/10 PASS

- [ ] **Step 15.5 : Commit**

```bash
git add src/fahmi2/domain/__init__.py src/fahmi2/domain/enums.py tests/unit/domain/test_enums.py
git commit -m "feat(domain): enums (Language, StylePreset, PhaseId, RunStatus, ...)"
```

---

### Task 16: `domain/ids.py` — wrappers d'identifiants typés

**Files:**
- Create: `src/fahmi2/domain/ids.py`
- Test: `tests/unit/domain/test_domain_ids.py`

- [ ] **Step 16.1 : Test failing**

```python
"""Tests des wrappers d'identifiants typés du domaine."""

import pytest

from fahmi2.domain.ids import ProjectId, RunId, VideoId


def test_project_id_wraps_string() -> None:
    pid = ProjectId.new()
    assert isinstance(pid.value, str)
    assert len(pid.value) == 26


def test_run_id_wraps_string() -> None:
    rid = RunId.new()
    assert isinstance(rid.value, str)


def test_video_id_wraps_string() -> None:
    vid = VideoId.new()
    assert isinstance(vid.value, str)


def test_ids_are_distinct_types() -> None:
    pid = ProjectId.new()
    rid = RunId.new()
    assert pid != rid  # type: ignore[comparison-overlap]


def test_ids_equal_themselves() -> None:
    pid = ProjectId.new()
    same = ProjectId(value=pid.value)
    assert pid == same


def test_ids_are_hashable() -> None:
    pid = ProjectId.new()
    s = {pid, ProjectId(value=pid.value)}
    assert len(s) == 1


def test_ids_validate_format() -> None:
    with pytest.raises(ValueError):
        ProjectId(value="not-a-ulid")
```

- [ ] **Step 16.2 : Run, vérifier l'échec**

Run: `pytest tests/unit/domain/test_domain_ids.py -v`
Expected: FAIL

- [ ] **Step 16.3 : Implémenter**

```python
"""Wrappers typés pour les identifiants du domaine.

Trois types distincts pour éviter les confusions cross-type au type-check :
ProjectId, RunId, VideoId. Tous reposent sur ULID en interne.
"""

from __future__ import annotations

from dataclasses import dataclass

from fahmi2.core.ids import new_ulid, parse_ulid


@dataclass(frozen=True)
class ProjectId:
    """Identifiant stable d'un Projet."""

    value: str

    def __post_init__(self) -> None:
        parse_ulid(self.value)  # raise ValueError si invalide

    @classmethod
    def new(cls) -> ProjectId:
        return cls(value=new_ulid())


@dataclass(frozen=True)
class RunId:
    """Identifiant stable d'un Run."""

    value: str

    def __post_init__(self) -> None:
        parse_ulid(self.value)

    @classmethod
    def new(cls) -> RunId:
        return cls(value=new_ulid())


@dataclass(frozen=True)
class VideoId:
    """Identifiant stable d'une vidéo dans un Project."""

    value: str

    def __post_init__(self) -> None:
        parse_ulid(self.value)

    @classmethod
    def new(cls) -> VideoId:
        return cls(value=new_ulid())
```

- [ ] **Step 16.4 : Run, vérifier PASS**

Run: `pytest tests/unit/domain/test_domain_ids.py -v`
Expected: 7/7 PASS

- [ ] **Step 16.5 : Commit**

```bash
git add src/fahmi2/domain/ids.py tests/unit/domain/test_domain_ids.py
git commit -m "feat(domain): identifiants types ProjectId/RunId/VideoId"
```

---

### Task 17: `domain/glossary.py` — Term + Glossary

**Files:**
- Create: `src/fahmi2/domain/glossary.py`
- Test: `tests/unit/domain/test_glossary.py`

- [ ] **Step 17.1 : Test failing**

```python
"""Tests des entités Term et Glossary."""

import pytest

from fahmi2.domain.enums import Language
from fahmi2.domain.glossary import Glossary, Term
from fahmi2.domain.ids import VideoId


def test_term_minimal() -> None:
    t = Term(term="PIB", definition="produit intérieur brut")
    assert t.term == "PIB"
    assert t.definition == "produit intérieur brut"
    assert t.sources == ()
    assert t.aliases == ()
    assert t.cross_lang == {}


def test_term_with_sources_and_aliases() -> None:
    vid = VideoId.new()
    t = Term(
        term="PIB",
        definition="produit intérieur brut",
        sources=(vid,),
        aliases=("Produit Intérieur Brut",),
        cross_lang={Language.EN: "GDP"},
    )
    assert t.sources == (vid,)
    assert t.aliases == ("Produit Intérieur Brut",)
    assert t.cross_lang[Language.EN] == "GDP"


def test_term_is_frozen() -> None:
    t = Term(term="X", definition="x")
    with pytest.raises(Exception):  # FrozenInstanceError
        t.term = "Y"  # type: ignore[misc]


def test_glossary_empty() -> None:
    g = Glossary(language=Language.FR, terms=())
    assert g.language is Language.FR
    assert len(g) == 0
    assert list(g) == []


def test_glossary_with_terms() -> None:
    terms = (
        Term(term="PIB", definition="..."),
        Term(term="Inflation", definition="..."),
    )
    g = Glossary(language=Language.FR, terms=terms)
    assert len(g) == 2
    assert {t.term for t in g} == {"PIB", "Inflation"}


def test_glossary_find_returns_term_or_none() -> None:
    terms = (Term(term="PIB", definition="..."),)
    g = Glossary(language=Language.FR, terms=terms)
    assert g.find("PIB") is terms[0]
    assert g.find("XYZ") is None


def test_glossary_find_is_case_sensitive() -> None:
    terms = (Term(term="PIB", definition="..."),)
    g = Glossary(language=Language.FR, terms=terms)
    assert g.find("pib") is None  # case-sensitive volontairement, alias servent à la normalisation


def test_glossary_with_added_term_returns_new_instance() -> None:
    g = Glossary(language=Language.FR, terms=())
    new = g.with_added_term(Term(term="PIB", definition="..."))
    assert len(g) == 0
    assert len(new) == 1
```

- [ ] **Step 17.2 : Run, vérifier l'échec**

Run: `pytest tests/unit/domain/test_glossary.py -v`
Expected: FAIL

- [ ] **Step 17.3 : Implémenter**

```python
"""Entités Term et Glossary (immuables)."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field

from fahmi2.domain.enums import Language
from fahmi2.domain.ids import VideoId


@dataclass(frozen=True)
class Term:
    """Terme du glossaire avec définition contextualisée.

    Attributes:
        term: Le terme tel qu'il apparaît dans le contenu.
        definition: Définition contextuelle produite par les phases LLM.
        sources: Vidéos d'où le terme a été extrait.
        aliases: Variantes orthographiques ou rédactionnelles connues.
        cross_lang: Mapping langue → traduction (alimenté par la phase 6).
    """

    term: str
    definition: str
    sources: tuple[VideoId, ...] = ()
    aliases: tuple[str, ...] = ()
    cross_lang: dict[Language, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Glossary:
    """Glossaire pour une langue donnée."""

    language: Language
    terms: tuple[Term, ...]

    def __len__(self) -> int:
        return len(self.terms)

    def __iter__(self) -> Iterator[Term]:
        return iter(self.terms)

    def find(self, term: str) -> Term | None:
        """Retourne le Term correspondant exactement (case-sensitive) ou None."""
        for t in self.terms:
            if t.term == term:
                return t
        return None

    def with_added_term(self, term: Term) -> Glossary:
        """Retourne un nouveau Glossary avec ce terme ajouté."""
        return Glossary(language=self.language, terms=(*self.terms, term))
```

- [ ] **Step 17.4 : Run, vérifier PASS**

Run: `pytest tests/unit/domain/test_glossary.py -v`
Expected: 8/8 PASS

- [ ] **Step 17.5 : Commit**

```bash
git add src/fahmi2/domain/glossary.py tests/unit/domain/test_glossary.py
git commit -m "feat(domain): entites Term et Glossary immuables"
```

---

### Task 18: `domain/phase.py` — PhaseConfig + PhaseExecution

**Files:**
- Create: `src/fahmi2/domain/phase.py`
- Test: `tests/unit/domain/test_phase.py`

- [ ] **Step 18.1 : Test failing**

```python
"""Tests des entités PhaseConfig et PhaseExecution."""

from datetime import datetime, timezone

import pytest

from fahmi2.core.errors.error_info import ErrorInfo
from fahmi2.core.errors.severity import Severity
from fahmi2.domain.enums import PhaseId, PhaseStatus
from fahmi2.domain.phase import PhaseConfig, PhaseExecution


def test_phase_config_defaults() -> None:
    cfg = PhaseConfig()
    assert cfg.enabled_thinking is False
    assert cfg.temperature == 0.3
    assert cfg.max_retries == 5


def test_phase_config_validates_temperature() -> None:
    with pytest.raises(ValueError):
        PhaseConfig(temperature=-0.1)
    with pytest.raises(ValueError):
        PhaseConfig(temperature=2.1)


def test_phase_config_validates_max_retries() -> None:
    with pytest.raises(ValueError):
        PhaseConfig(max_retries=-1)


def test_phase_execution_minimal() -> None:
    ex = PhaseExecution(phase_id=PhaseId.STT, status=PhaseStatus.PENDING)
    assert ex.phase_id is PhaseId.STT
    assert ex.status is PhaseStatus.PENDING
    assert ex.started_at is None
    assert ex.finished_at is None
    assert ex.artifact_path is None
    assert ex.retry_count == 0
    assert ex.cost_usd == 0.0
    assert ex.error is None


def test_phase_execution_with_full_state() -> None:
    info = ErrorInfo(code="X", user_message="oups", severity=Severity.ERROR)
    started = datetime(2026, 5, 19, 12, 0, 0, tzinfo=timezone.utc)
    finished = datetime(2026, 5, 19, 12, 0, 5, tzinfo=timezone.utc)
    ex = PhaseExecution(
        phase_id=PhaseId.REFORMULATION,
        status=PhaseStatus.FAILED,
        started_at=started,
        finished_at=finished,
        retry_count=3,
        cost_usd=0.42,
        error=info,
    )
    assert ex.status is PhaseStatus.FAILED
    assert ex.retry_count == 3
    assert ex.cost_usd == 0.42
    assert ex.error is info


def test_phase_execution_with_status_returns_new() -> None:
    ex = PhaseExecution(phase_id=PhaseId.STT, status=PhaseStatus.PENDING)
    new = ex.with_status(PhaseStatus.RUNNING)
    assert new is not ex
    assert new.status is PhaseStatus.RUNNING
    assert ex.status is PhaseStatus.PENDING
```

- [ ] **Step 18.2 : Run, vérifier l'échec**

Run: `pytest tests/unit/domain/test_phase.py -v`
Expected: FAIL

- [ ] **Step 18.3 : Implémenter**

```python
"""Entités PhaseConfig (paramètres) et PhaseExecution (état d'exécution)."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path

from fahmi2.core.errors.error_info import ErrorInfo
from fahmi2.domain.enums import PhaseId, PhaseStatus


@dataclass(frozen=True)
class PhaseConfig:
    """Paramètres LLM d'une phase (configurable par projet).

    Attributes:
        enabled_thinking: Active ou non le mode raisonnement DeepSeek.
        temperature: Température LLM (0..2).
        max_retries: Nombre max de tentatives (cf. RetryPolicy).
    """

    enabled_thinking: bool = False
    temperature: float = 0.3
    max_retries: int = 5

    def __post_init__(self) -> None:
        if not 0.0 <= self.temperature <= 2.0:
            raise ValueError(f"temperature must be in [0, 2], got {self.temperature}")
        if self.max_retries < 0:
            raise ValueError(f"max_retries must be >= 0, got {self.max_retries}")


@dataclass(frozen=True)
class PhaseExecution:
    """État d'exécution d'une phase (pour une vidéo ou pour le batch)."""

    phase_id: PhaseId
    status: PhaseStatus
    started_at: datetime | None = None
    finished_at: datetime | None = None
    artifact_path: Path | None = None
    retry_count: int = 0
    cost_usd: float = 0.0
    error: ErrorInfo | None = None

    def with_status(self, status: PhaseStatus) -> PhaseExecution:
        """Retourne une copie avec un nouveau status."""
        return replace(self, status=status)
```

- [ ] **Step 18.4 : Run, vérifier PASS**

Run: `pytest tests/unit/domain/test_phase.py -v`
Expected: 6/6 PASS

- [ ] **Step 18.5 : Commit**

```bash
git add src/fahmi2/domain/phase.py tests/unit/domain/test_phase.py
git commit -m "feat(domain): PhaseConfig et PhaseExecution"
```

---

### Task 19: `domain/video.py` — VideoExecution

**Files:**
- Create: `src/fahmi2/domain/video.py`
- Test: `tests/unit/domain/test_video.py`

- [ ] **Step 19.1 : Test failing**

```python
"""Tests de l'entité VideoExecution."""

from pathlib import Path

from fahmi2.domain.enums import Language, PhaseId, PhaseStatus
from fahmi2.domain.ids import VideoId
from fahmi2.domain.phase import PhaseExecution
from fahmi2.domain.video import VideoExecution


def test_video_execution_minimal() -> None:
    vid = VideoId.new()
    ve = VideoExecution(video_id=vid, source_path=Path("video.mp4"))
    assert ve.video_id is vid
    assert ve.source_path == Path("video.mp4")
    assert ve.detected_language is None
    assert ve.phase_executions == {}


def test_video_execution_with_phases() -> None:
    vid = VideoId.new()
    pe = PhaseExecution(phase_id=PhaseId.STT, status=PhaseStatus.SUCCEEDED)
    ve = VideoExecution(
        video_id=vid,
        source_path=Path("video.mp4"),
        detected_language=Language.FR,
        phase_executions={PhaseId.STT: pe},
    )
    assert ve.detected_language is Language.FR
    assert ve.phase_executions[PhaseId.STT] is pe


def test_video_execution_phase_status_helper() -> None:
    vid = VideoId.new()
    pe = PhaseExecution(phase_id=PhaseId.STT, status=PhaseStatus.SUCCEEDED)
    ve = VideoExecution(
        video_id=vid,
        source_path=Path("video.mp4"),
        phase_executions={PhaseId.STT: pe},
    )
    assert ve.phase_status(PhaseId.STT) is PhaseStatus.SUCCEEDED
    assert ve.phase_status(PhaseId.REFORMULATION) is PhaseStatus.PENDING
```

- [ ] **Step 19.2 : Run, vérifier l'échec**

Run: `pytest tests/unit/domain/test_video.py -v`
Expected: FAIL

- [ ] **Step 19.3 : Implémenter**

```python
"""Entité VideoExecution — état d'exécution d'une vidéo dans un Run."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from fahmi2.domain.enums import Language, PhaseId, PhaseStatus
from fahmi2.domain.ids import VideoId
from fahmi2.domain.phase import PhaseExecution


@dataclass(frozen=True)
class VideoExecution:
    """État d'exécution d'une vidéo dans un Run.

    Attributes:
        video_id: Identifiant stable de la vidéo dans le projet.
        source_path: Chemin du fichier source.
        detected_language: Langue détectée par whisper (None tant que STT non exécuté).
        phase_executions: Mapping PhaseId → PhaseExecution pour les phases par-vidéo
            (phases 0, 1, 3, 4, 6, 7). Les phases batch (2, 5) sont au niveau du Run.
    """

    video_id: VideoId
    source_path: Path
    detected_language: Language | None = None
    phase_executions: dict[PhaseId, PhaseExecution] = field(default_factory=dict)

    def phase_status(self, phase_id: PhaseId) -> PhaseStatus:
        """Retourne le PhaseStatus pour cette phase, ou PENDING si non commencée."""
        pe = self.phase_executions.get(phase_id)
        return pe.status if pe is not None else PhaseStatus.PENDING
```

- [ ] **Step 19.4 : Run, vérifier PASS**

Run: `pytest tests/unit/domain/test_video.py -v`
Expected: 3/3 PASS

- [ ] **Step 19.5 : Commit**

```bash
git add src/fahmi2/domain/video.py tests/unit/domain/test_video.py
git commit -m "feat(domain): VideoExecution"
```

---

### Task 20: `domain/run.py` — Run

**Files:**
- Create: `src/fahmi2/domain/run.py`
- Test: `tests/unit/domain/test_run.py`

L'entité `Run` dépend de `ProjectSettings` (snapshot). Comme `ProjectSettings` n'est pas encore défini, on utilise `typing.TYPE_CHECKING` pour briser le cycle et on type avec une string forward-ref. `ProjectSettings` arrive en Task 21.

- [ ] **Step 20.1 : Test failing**

```python
"""Tests de l'entité Run."""

from datetime import datetime, timezone

from fahmi2.domain.enums import PhaseId, PhaseStatus, RunStatus
from fahmi2.domain.ids import ProjectId, RunId
from fahmi2.domain.phase import PhaseExecution
from fahmi2.domain.run import Run


def test_run_minimal() -> None:
    rid = RunId.new()
    pid = ProjectId.new()
    started = datetime(2026, 5, 19, 12, 0, 0, tzinfo=timezone.utc)
    run = Run(
        id=rid,
        project_id=pid,
        started_at=started,
        status=RunStatus.CREATED,
        settings_snapshot={"name": "test"},  # mocké, ProjectSettings vient en Task 21
    )
    assert run.id is rid
    assert run.project_id is pid
    assert run.started_at == started
    assert run.finished_at is None
    assert run.status is RunStatus.CREATED
    assert run.cost_usd == 0.0
    assert run.videos == ()
    assert run.phase_executions == {}


def test_run_with_videos_and_phases() -> None:
    pe = PhaseExecution(phase_id=PhaseId.GLOSSARY_RECONCILIATION, status=PhaseStatus.SUCCEEDED)
    run = Run(
        id=RunId.new(),
        project_id=ProjectId.new(),
        started_at=datetime(2026, 5, 19, 12, 0, 0, tzinfo=timezone.utc),
        status=RunStatus.RUNNING,
        settings_snapshot={"name": "test"},
        cost_usd=1.5,
        phase_executions={PhaseId.GLOSSARY_RECONCILIATION: pe},
    )
    assert run.cost_usd == 1.5
    assert run.phase_executions[PhaseId.GLOSSARY_RECONCILIATION] is pe


def test_run_with_status_returns_new_instance() -> None:
    run = Run(
        id=RunId.new(),
        project_id=ProjectId.new(),
        started_at=datetime.now(tz=timezone.utc),
        status=RunStatus.CREATED,
        settings_snapshot={"name": "test"},
    )
    new = run.with_status(RunStatus.RUNNING)
    assert new is not run
    assert new.status is RunStatus.RUNNING
    assert run.status is RunStatus.CREATED


def test_run_with_added_cost() -> None:
    run = Run(
        id=RunId.new(),
        project_id=ProjectId.new(),
        started_at=datetime.now(tz=timezone.utc),
        status=RunStatus.RUNNING,
        settings_snapshot={"name": "test"},
        cost_usd=1.0,
    )
    new = run.with_added_cost(0.5)
    assert new.cost_usd == 1.5
    assert run.cost_usd == 1.0
```

**Note:** Le test utilise `settings_snapshot={"name": "test"}` comme placeholder typé `Any` pour ne pas dépendre de `ProjectSettings` qui sera défini en Task 21. C'est un compromis acceptable car la version finale (Task 21) viendra resserrer le type.

- [ ] **Step 20.2 : Run, vérifier l'échec**

Run: `pytest tests/unit/domain/test_run.py -v`
Expected: FAIL

- [ ] **Step 20.3 : Implémenter**

```python
"""Entité Run — exécution complète d'un Project à un instant t."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import TYPE_CHECKING, Any

from fahmi2.domain.enums import PhaseId, RunStatus
from fahmi2.domain.ids import ProjectId, RunId
from fahmi2.domain.phase import PhaseExecution
from fahmi2.domain.video import VideoExecution

if TYPE_CHECKING:
    from fahmi2.domain.project import ProjectSettings  # noqa: F401 — forward-ref


@dataclass(frozen=True)
class Run:
    """Représente une exécution complète d'un Project.

    Les `videos` et `phase_executions` sont mis à jour par le pipeline. Le
    `settings_snapshot` est une copie immuable des ProjectSettings au moment du
    démarrage du run : modifier le Project après lancement n'affecte pas le Run
    en cours.

    Attributes:
        videos: Tuple immuable des VideoExecution (1 par vidéo du dossier d'entrée).
        phase_executions: Mapping pour les phases batch (2, 5) au niveau Run.
    """

    id: RunId
    project_id: ProjectId
    started_at: datetime
    status: RunStatus
    settings_snapshot: Any  # ProjectSettings — forward-ref, défini en Task 21
    finished_at: datetime | None = None
    cost_usd: float = 0.0
    videos: tuple[VideoExecution, ...] = ()
    phase_executions: dict[PhaseId, PhaseExecution] = field(default_factory=dict)

    def with_status(self, status: RunStatus) -> Run:
        return replace(self, status=status)

    def with_added_cost(self, amount: float) -> Run:
        return replace(self, cost_usd=self.cost_usd + amount)

    def with_finished_at(self, ts: datetime) -> Run:
        return replace(self, finished_at=ts)
```

- [ ] **Step 20.4 : Run, vérifier PASS**

Run: `pytest tests/unit/domain/test_run.py -v`
Expected: 4/4 PASS

- [ ] **Step 20.5 : Commit**

```bash
git add src/fahmi2/domain/run.py tests/unit/domain/test_run.py
git commit -m "feat(domain): entite Run avec snapshot immuable des settings"
```

---

### Task 21: `domain/project.py` — ProjectSettings + Project + ParallelismConfig

**Files:**
- Create: `src/fahmi2/domain/project.py`
- Test: `tests/unit/domain/test_project.py`

- [ ] **Step 21.1 : Test failing**

```python
"""Tests des entités Project, ProjectSettings, ParallelismConfig."""

from pathlib import Path

import pytest

from fahmi2.domain.enums import Language, LLMModel, PhaseId, SttProvider, StylePreset
from fahmi2.domain.ids import ProjectId
from fahmi2.domain.phase import PhaseConfig
from fahmi2.domain.project import ParallelismConfig, Project, ProjectSettings


def _make_settings(**overrides: object) -> ProjectSettings:
    base = {
        "name": "Test Project",
        "input_folder": Path("./input"),
        "workspace_folder": Path("./workspace"),
        "source_language": Language.FR,
        "output_languages": (Language.FR,),
        "style_preset": StylePreset.STANDARD,
        "style_directives": "",
        "stt_provider": SttProvider.OPENAI_CLOUD,
        "llm_model": LLMModel.DEEPSEEK_V4_FLASH,
        "phases_config": {pid: PhaseConfig() for pid in PhaseId if pid is not PhaseId.STT},
        "cost_ceiling_usd": None,
        "parallelism": ParallelismConfig(),
        "delete_audio_after_stt": True,
    }
    base.update(overrides)
    return ProjectSettings(**base)  # type: ignore[arg-type]


def test_parallelism_config_defaults() -> None:
    p = ParallelismConfig()
    assert p.stt_cloud_workers == 3
    assert p.llm_workers == 4


def test_parallelism_config_validates_positive() -> None:
    with pytest.raises(ValueError):
        ParallelismConfig(stt_cloud_workers=0)
    with pytest.raises(ValueError):
        ParallelismConfig(llm_workers=-1)


def test_settings_requires_source_in_output() -> None:
    with pytest.raises(ValueError):
        _make_settings(source_language=Language.FR, output_languages=(Language.EN,))


def test_settings_accepts_source_in_output() -> None:
    s = _make_settings(source_language=Language.FR, output_languages=(Language.FR, Language.EN))
    assert Language.FR in s.output_languages


def test_settings_requires_at_least_one_output_language() -> None:
    with pytest.raises(ValueError):
        _make_settings(output_languages=())


def test_settings_requires_all_llm_phases_configured() -> None:
    incomplete = {PhaseId.TERM_EXTRACTION: PhaseConfig()}
    with pytest.raises(ValueError):
        _make_settings(phases_config=incomplete)


def test_settings_must_not_configure_stt_phase() -> None:
    # phases_config concerne les phases LLM uniquement (1..7), pas STT
    invalid = {pid: PhaseConfig() for pid in PhaseId}  # inclut phase_0_stt
    with pytest.raises(ValueError):
        _make_settings(phases_config=invalid)


def test_settings_cost_ceiling_positive() -> None:
    with pytest.raises(ValueError):
        _make_settings(cost_ceiling_usd=-1.0)


def test_project_minimal() -> None:
    from datetime import datetime, timezone

    pid = ProjectId.new()
    s = _make_settings()
    created = datetime(2026, 5, 19, 12, 0, 0, tzinfo=timezone.utc)
    project = Project(id=pid, settings=s, created_at=created)
    assert project.id is pid
    assert project.settings is s
    assert project.created_at == created
    assert project.last_run_at is None
    assert project.runs == ()
```

- [ ] **Step 21.2 : Run, vérifier l'échec**

Run: `pytest tests/unit/domain/test_project.py -v`
Expected: FAIL

- [ ] **Step 21.3 : Implémenter**

```python
"""Entités Project, ProjectSettings, ParallelismConfig."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from fahmi2.domain.enums import (
    Language,
    LLMModel,
    PhaseId,
    SttProvider,
    StylePreset,
)
from fahmi2.domain.ids import ProjectId, RunId
from fahmi2.domain.phase import PhaseConfig


@dataclass(frozen=True)
class ParallelismConfig:
    """Configuration de parallélisme du pipeline.

    Note: STT local est toujours séquentiel (1 GPU). Seuls STT cloud et LLM
    sont parallélisables.
    """

    stt_cloud_workers: int = 3
    llm_workers: int = 4

    def __post_init__(self) -> None:
        if self.stt_cloud_workers < 1:
            raise ValueError("stt_cloud_workers must be >= 1")
        if self.llm_workers < 1:
            raise ValueError("llm_workers must be >= 1")


_LLM_PHASES: frozenset[PhaseId] = frozenset(p for p in PhaseId if p is not PhaseId.STT)


@dataclass(frozen=True)
class ProjectSettings:
    """Paramètres complets d'un Project.

    Les phases LLM (1..7) doivent toutes être configurées dans `phases_config`.
    `output_languages` doit toujours contenir `source_language`.
    """

    name: str
    input_folder: Path
    workspace_folder: Path
    source_language: Language
    output_languages: tuple[Language, ...]
    style_preset: StylePreset
    style_directives: str
    stt_provider: SttProvider
    llm_model: LLMModel
    phases_config: dict[PhaseId, PhaseConfig]
    cost_ceiling_usd: float | None
    parallelism: ParallelismConfig
    delete_audio_after_stt: bool

    def __post_init__(self) -> None:
        if not self.output_languages:
            raise ValueError("output_languages must contain at least one language")
        if self.source_language not in self.output_languages:
            raise ValueError(
                f"output_languages must contain source_language ({self.source_language})"
            )
        configured = set(self.phases_config)
        expected = set(_LLM_PHASES)
        if configured != expected:
            missing = expected - configured
            extra = configured - expected
            raise ValueError(
                f"phases_config must cover exactly LLM phases (1..7). "
                f"Missing: {sorted(missing)}, Extra: {sorted(extra)}"
            )
        if self.cost_ceiling_usd is not None and self.cost_ceiling_usd < 0:
            raise ValueError(
                f"cost_ceiling_usd must be >= 0 or None, got {self.cost_ceiling_usd}"
            )


@dataclass(frozen=True)
class Project:
    """Un Projet utilisateur persistant avec son historique de runs."""

    id: ProjectId
    settings: ProjectSettings
    created_at: datetime
    last_run_at: datetime | None = None
    runs: tuple[RunId, ...] = ()
```

- [ ] **Step 21.4 : Run, vérifier PASS**

Run: `pytest tests/unit/domain/test_project.py -v`
Expected: 9/9 PASS

- [ ] **Step 21.5 : Commit**

```bash
git add src/fahmi2/domain/project.py tests/unit/domain/test_project.py
git commit -m "feat(domain): Project + ProjectSettings + ParallelismConfig"
```

---

### Task 22: `domain/state_machine.py` — validateurs de transitions

**Files:**
- Create: `src/fahmi2/domain/state_machine.py`
- Test: `tests/unit/domain/test_state_machine.py`

- [ ] **Step 22.1 : Test failing**

```python
"""Tests des validateurs de transitions d'état."""

import pytest

from fahmi2.domain.enums import PhaseStatus, RunStatus
from fahmi2.domain.state_machine import (
    InvalidTransitionError,
    can_transition_phase,
    can_transition_run,
    validate_transition_phase,
    validate_transition_run,
)


# RunStatus transitions valides :
# CREATED -> RUNNING
# RUNNING -> PAUSED, CANCELLED, COMPLETED, FAILED
# PAUSED  -> RUNNING, CANCELLED
# COMPLETED / CANCELLED / FAILED : terminales

@pytest.mark.parametrize(
    ("from_s", "to_s", "expected"),
    [
        (RunStatus.CREATED, RunStatus.RUNNING, True),
        (RunStatus.CREATED, RunStatus.PAUSED, False),
        (RunStatus.RUNNING, RunStatus.PAUSED, True),
        (RunStatus.RUNNING, RunStatus.COMPLETED, True),
        (RunStatus.RUNNING, RunStatus.CANCELLED, True),
        (RunStatus.RUNNING, RunStatus.FAILED, True),
        (RunStatus.RUNNING, RunStatus.CREATED, False),
        (RunStatus.PAUSED, RunStatus.RUNNING, True),
        (RunStatus.PAUSED, RunStatus.CANCELLED, True),
        (RunStatus.PAUSED, RunStatus.COMPLETED, False),
        (RunStatus.COMPLETED, RunStatus.RUNNING, False),
        (RunStatus.CANCELLED, RunStatus.RUNNING, False),
        (RunStatus.FAILED, RunStatus.RUNNING, False),
        (RunStatus.RUNNING, RunStatus.RUNNING, False),  # même état refusé
    ],
)
def test_run_transitions(from_s: RunStatus, to_s: RunStatus, expected: bool) -> None:
    assert can_transition_run(from_s, to_s) is expected


def test_validate_run_raises_on_invalid() -> None:
    with pytest.raises(InvalidTransitionError):
        validate_transition_run(RunStatus.COMPLETED, RunStatus.RUNNING)


def test_validate_run_passes_on_valid() -> None:
    validate_transition_run(RunStatus.CREATED, RunStatus.RUNNING)  # ne lève pas


# PhaseStatus transitions valides :
# PENDING -> RUNNING, SKIPPED
# RUNNING -> SUCCEEDED, FAILED
# FAILED  -> RUNNING (rejeu manuel)
# SUCCEEDED / SKIPPED : terminaux pour l'exec courante

@pytest.mark.parametrize(
    ("from_s", "to_s", "expected"),
    [
        (PhaseStatus.PENDING, PhaseStatus.RUNNING, True),
        (PhaseStatus.PENDING, PhaseStatus.SKIPPED, True),
        (PhaseStatus.PENDING, PhaseStatus.SUCCEEDED, False),
        (PhaseStatus.RUNNING, PhaseStatus.SUCCEEDED, True),
        (PhaseStatus.RUNNING, PhaseStatus.FAILED, True),
        (PhaseStatus.RUNNING, PhaseStatus.SKIPPED, False),
        (PhaseStatus.FAILED, PhaseStatus.RUNNING, True),  # rejeu
        (PhaseStatus.SUCCEEDED, PhaseStatus.RUNNING, False),
        (PhaseStatus.SKIPPED, PhaseStatus.RUNNING, False),
    ],
)
def test_phase_transitions(
    from_s: PhaseStatus, to_s: PhaseStatus, expected: bool
) -> None:
    assert can_transition_phase(from_s, to_s) is expected


def test_validate_phase_raises_on_invalid() -> None:
    with pytest.raises(InvalidTransitionError):
        validate_transition_phase(PhaseStatus.SUCCEEDED, PhaseStatus.RUNNING)
```

- [ ] **Step 22.2 : Run, vérifier l'échec**

Run: `pytest tests/unit/domain/test_state_machine.py -v`
Expected: FAIL

- [ ] **Step 22.3 : Implémenter**

```python
"""Validateurs de transitions d'état pour Run et Phase."""

from __future__ import annotations

from fahmi2.domain.enums import PhaseStatus, RunStatus


class InvalidTransitionError(ValueError):
    """Levée lors d'une tentative de transition d'état invalide."""


_RUN_TRANSITIONS: dict[RunStatus, frozenset[RunStatus]] = {
    RunStatus.CREATED: frozenset({RunStatus.RUNNING}),
    RunStatus.RUNNING: frozenset(
        {
            RunStatus.PAUSED,
            RunStatus.CANCELLED,
            RunStatus.COMPLETED,
            RunStatus.FAILED,
        }
    ),
    RunStatus.PAUSED: frozenset({RunStatus.RUNNING, RunStatus.CANCELLED}),
    RunStatus.CANCELLED: frozenset(),
    RunStatus.COMPLETED: frozenset(),
    RunStatus.FAILED: frozenset(),
}


_PHASE_TRANSITIONS: dict[PhaseStatus, frozenset[PhaseStatus]] = {
    PhaseStatus.PENDING: frozenset({PhaseStatus.RUNNING, PhaseStatus.SKIPPED}),
    PhaseStatus.RUNNING: frozenset({PhaseStatus.SUCCEEDED, PhaseStatus.FAILED}),
    PhaseStatus.FAILED: frozenset({PhaseStatus.RUNNING}),
    PhaseStatus.SUCCEEDED: frozenset(),
    PhaseStatus.SKIPPED: frozenset(),
}


def can_transition_run(from_status: RunStatus, to_status: RunStatus) -> bool:
    """True si la transition Run from_status -> to_status est autorisée."""
    return to_status in _RUN_TRANSITIONS.get(from_status, frozenset())


def validate_transition_run(from_status: RunStatus, to_status: RunStatus) -> None:
    """Lève InvalidTransitionError si la transition n'est pas autorisée."""
    if not can_transition_run(from_status, to_status):
        raise InvalidTransitionError(
            f"Invalid Run transition {from_status} -> {to_status}"
        )


def can_transition_phase(from_status: PhaseStatus, to_status: PhaseStatus) -> bool:
    """True si la transition Phase from_status -> to_status est autorisée."""
    return to_status in _PHASE_TRANSITIONS.get(from_status, frozenset())


def validate_transition_phase(from_status: PhaseStatus, to_status: PhaseStatus) -> None:
    """Lève InvalidTransitionError si la transition n'est pas autorisée."""
    if not can_transition_phase(from_status, to_status):
        raise InvalidTransitionError(
            f"Invalid Phase transition {from_status} -> {to_status}"
        )
```

- [ ] **Step 22.4 : Run, vérifier PASS**

Run: `pytest tests/unit/domain/test_state_machine.py -v`
Expected: tous PASS (incluant les 14 cas paramétrés + 4 autres tests)

- [ ] **Step 22.5 : Commit**

```bash
git add src/fahmi2/domain/state_machine.py tests/unit/domain/test_state_machine.py
git commit -m "feat(domain): validateurs de transitions d'etat Run et Phase"
```

---

### Task 23: Vérification finale et tag de jalon

- [ ] **Step 23.1 : Lancer la suite complète**

Run:
```powershell
pytest --cov=src/fahmi2 --cov-report=term-missing
ruff check .
mypy src
```

Expected:
- Tous les tests passent (`X passed`)
- Couverture globale ≥ 90 %, ≥ 95 % sur `domain/`
- `ruff` aucun warning
- `mypy --strict` zéro erreur

- [ ] **Step 23.2 : Tag git de fin de jalon**

```bash
git tag -a milestone-01-socle -m "Milestone 01 : Socle (core + domain) terminé"
```

- [ ] **Step 23.3 : Commit de fin de jalon si nécessaire**

S'il reste des fichiers générés ou modifiés non commités, créer un commit de finalisation :

```bash
git status
git add -A   # uniquement si pertinent — vérifier d'abord
git commit -m "chore: finalisation milestone-01-socle"
```

---

## Self-review checklist (à exécuter en fin de plan)

Après avoir implémenté toutes les tâches :

- [ ] **Couverture spec :** chaque entité / utilitaire mentionné en section 3.2 et 4 de la spec a un fichier correspondant et des tests
- [ ] **Pas de placeholder TBD/TODO** dans le code livré
- [ ] **Noms cohérents** : `Severity`, `LogEvent`, `RetryPolicy`, `Migration`, `Term`, `Glossary`, `PhaseConfig`, `PhaseExecution`, `VideoExecution`, `Run`, `ProjectSettings`, `Project`, `ParallelismConfig`, `InvalidTransitionError`
- [ ] **Aucun import circulaire** (vérifier par `python -c "import fahmi2.domain.run, fahmi2.domain.project"`)
- [ ] **`ruff` + `mypy --strict` propres**
- [ ] **Couverture domaine ≥ 95 %, core ≥ 90 %**

---

## Suite — plans à venir

| Plan | Périmètre | Pré-requis |
|------|-----------|------------|
| **Plan 02** | Infra basique (sqlite_state WAL, fs_artifacts atomique, dpapi_store) | Plan 01 |
| **Plan 03** | Adapters STT (ffmpeg, faster-whisper, openai-whisper), LLM (deepseek), retrieval TF-IDF concret | Plan 01, 02 |
| **Plan 04** | PipelineEngine + phase 0 STT + EventBus + PauseToken | Plans 01-03 |
| **Plan 05** | Phases LLM 1→7 (prompts + handlers + tests) | Plan 04 |
| **Plan 06** | GlossaryReconciler + injection top-K | Plan 05 |
| **Plan 07** | App services (ProjectService, RunOrchestrator, CostEstimator, SettingsService, HardwareProbe) | Plan 06 |
| **Plan 08** | UI socle (MainWindow, RunMatrixView, StatsStrip, LogsDock, QtEventBus, viewmodels) | Plan 07 |
| **Plan 09** | UI dialogues (NewProject, GlobalSettings, PhaseDetail, PromptEditor, ProjectReport) | Plan 08 |
| **Plan 10** | End-to-end + tests d'intégration + MigrationRunner v01 baseline | Plan 09 |
| **Plan 11** | Packaging (PyInstaller spec, bundle ffmpeg, script make-portable-zip.ps1) | Plan 10 |
| **Plan 12** | Documentation utilisateur (README détaillé, guide démarrage rapide) | Plan 11 |

Chaque plan suivant sera produit par une invocation distincte du skill `writing-plans`.
