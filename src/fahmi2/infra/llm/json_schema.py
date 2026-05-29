"""Helpers de validation/parsing de JSON typé issu d'un LLM.

Module **neutre partagé** (``infra/llm``) : valide les objets JSON décodés d'une
réponse LLM et lève une ``LLMError`` (``LLM.INVALID_SCHEMA``, non retryable) en cas
de structure inattendue. Réutilisé par les générateurs de la Pédagogie **et** les
extracteurs des Visualisations (source unique, zéro duplication).
"""

from __future__ import annotations

from typing import Any

from fahmi2.core.errors.exceptions import LLMError
from fahmi2.core.errors.severity import Severity

_INVALID_SCHEMA_CODE = "LLM.INVALID_SCHEMA"


def schema_error(context_label: str, detail: str) -> LLMError:
    """Construit une ``LLMError`` de schéma invalide (non retryable).

    Args:
        context_label: Libellé de contexte (ex: ``"qcm:1"``).
        detail: Détail du problème de schéma.

    Returns:
        L'``LLMError`` (``LLM.INVALID_SCHEMA``).
    """
    return LLMError(
        code=_INVALID_SCHEMA_CODE,
        user_message=f"Réponse du LLM inattendue pour {context_label} : {detail}",
        severity=Severity.ERROR,
        technical_details={"context_label": context_label, "detail": detail},
    )


def require_mapping(value: Any, *, context_label: str) -> dict[str, Any]:  # noqa: ANN401
    """Exige un objet JSON (dict).

    Args:
        value: Valeur décodée.
        context_label: Libellé de contexte (messages d'erreur).

    Returns:
        Le dict.

    Raises:
        LLMError: Si ``value`` n'est pas un dict.
    """
    if not isinstance(value, dict):
        raise schema_error(context_label, "objet JSON attendu")
    return value


def require_list(
    mapping: dict[str, Any], key: str, *, context_label: str
) -> list[Any]:
    """Exige une liste à ``key``.

    Args:
        mapping: Objet JSON.
        key: Clé attendue.
        context_label: Libellé de contexte.

    Returns:
        La liste.

    Raises:
        LLMError: Si la valeur n'est pas une liste.
    """
    value = mapping.get(key)
    if not isinstance(value, list):
        raise schema_error(context_label, f"liste attendue pour « {key} »")
    return value


def require_str(mapping: dict[str, Any], key: str, *, context_label: str) -> str:
    """Exige une chaîne non vide à ``key``.

    Args:
        mapping: Objet JSON.
        key: Clé attendue.
        context_label: Libellé de contexte.

    Returns:
        La chaîne.

    Raises:
        LLMError: Si la valeur n'est pas une chaîne non vide.
    """
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        raise schema_error(context_label, f"chaîne attendue pour « {key} »")
    return value


def require_int(mapping: dict[str, Any], key: str, *, context_label: str) -> int:
    """Exige un entier à ``key`` (rejette ``bool``).

    Args:
        mapping: Objet JSON.
        key: Clé attendue.
        context_label: Libellé de contexte.

    Returns:
        L'entier.

    Raises:
        LLMError: Si la valeur n'est pas un entier.
    """
    value = mapping.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise schema_error(context_label, f"entier attendu pour « {key} »")
    return value


def require_bool(mapping: dict[str, Any], key: str, *, context_label: str) -> bool:
    """Exige un booléen à ``key``.

    Args:
        mapping: Objet JSON.
        key: Clé attendue.
        context_label: Libellé de contexte.

    Returns:
        Le booléen.

    Raises:
        LLMError: Si la valeur n'est pas un booléen.
    """
    value = mapping.get(key)
    if not isinstance(value, bool):
        raise schema_error(context_label, f"booléen attendu pour « {key} »")
    return value


def require_str_list(
    mapping: dict[str, Any], key: str, *, context_label: str
) -> tuple[str, ...]:
    """Exige une liste de chaînes non vide à ``key``.

    Args:
        mapping: Objet JSON.
        key: Clé attendue.
        context_label: Libellé de contexte.

    Returns:
        Le tuple de chaînes (vides écartées).

    Raises:
        LLMError: Si aucune chaîne exploitable n'est trouvée.
    """
    raw = require_list(mapping, key, context_label=context_label)
    out = [str(x) for x in raw if str(x).strip()]
    if not out:
        raise schema_error(context_label, f"liste de chaînes attendue pour « {key} »")
    return tuple(out)
