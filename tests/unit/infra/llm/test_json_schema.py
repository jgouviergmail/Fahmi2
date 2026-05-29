"""Tests des helpers de parsing JSON typé (``infra/llm/json_schema``)."""

from __future__ import annotations

import pytest

from fahmi2.core.errors.exceptions import LLMError
from fahmi2.infra.llm.json_schema import (
    require_bool,
    require_int,
    require_list,
    require_mapping,
    require_str,
    require_str_list,
    schema_error,
)

_CTX = "test"


def test_schema_error_code() -> None:
    err = schema_error(_CTX, "détail")
    assert err.code == "LLM.INVALID_SCHEMA"


def test_require_mapping_ok_et_ko() -> None:
    assert require_mapping({"a": 1}, context_label=_CTX) == {"a": 1}
    with pytest.raises(LLMError):
        require_mapping([1, 2], context_label=_CTX)


def test_require_list_ok_et_ko() -> None:
    assert require_list({"a": [1, 2]}, "a", context_label=_CTX) == [1, 2]
    with pytest.raises(LLMError):
        require_list({}, "a", context_label=_CTX)


def test_require_str_rejette_vide_et_non_str() -> None:
    assert require_str({"a": "x"}, "a", context_label=_CTX) == "x"
    with pytest.raises(LLMError):
        require_str({"a": "  "}, "a", context_label=_CTX)
    with pytest.raises(LLMError):
        require_str({"a": 1}, "a", context_label=_CTX)


def test_require_int_rejette_bool() -> None:
    assert require_int({"a": 3}, "a", context_label=_CTX) == 3
    with pytest.raises(LLMError):
        require_int({"a": True}, "a", context_label=_CTX)


def test_require_bool() -> None:
    assert require_bool({"a": True}, "a", context_label=_CTX) is True
    with pytest.raises(LLMError):
        require_bool({"a": 1}, "a", context_label=_CTX)


def test_require_str_list_ecarte_vides_et_rejette_vide() -> None:
    assert require_str_list({"a": ["x", "", "y"]}, "a", context_label=_CTX) == (
        "x",
        "y",
    )
    with pytest.raises(LLMError):
        require_str_list({"a": ["", "  "]}, "a", context_label=_CTX)
