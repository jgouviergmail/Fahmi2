"""Registre statique des messages destinés à l'utilisateur, par code d'erreur."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from importlib.resources import files
from typing import Any

_MESSAGES_RESOURCE_PACKAGE = "fahmi2.core.errors"
_MESSAGES_RESOURCE_NAME = "messages.fr.json"
_FALLBACK_TITLE = "Une erreur est survenue"
_FALLBACK_BODY_TEMPLATE = (
    "Code d'erreur : {code}. Consulte les logs pour le détail technique."
)


@dataclass(frozen=True)
class UserAction:
    """Action proposée à l'utilisateur depuis une boîte de dialogue d'erreur.

    Attributes:
        label: Libellé du bouton affiché.
        action: Identifiant stable de l'action côté UI.
    """

    label: str
    action: str


@dataclass(frozen=True)
class UserFacingMessage:
    """Message localisé destiné à l'UI (titre, corps, actions optionnelles).

    Attributes:
        title: Titre court à afficher (boîte de dialogue, toast).
        body: Description plus détaillée à destination de l'utilisateur.
        actions: Liste d'actions cliquables associées au message.
    """

    title: str
    body: str
    actions: tuple[UserAction, ...] = field(default_factory=tuple)


def _load_messages_from_resource() -> dict[str, UserFacingMessage]:
    """Charge les messages depuis le fichier JSON bundlé.

    Returns:
        Mapping ``code → UserFacingMessage`` extrait du JSON ressource.
    """
    raw_text = (
        files(_MESSAGES_RESOURCE_PACKAGE).joinpath(_MESSAGES_RESOURCE_NAME).read_text(
            encoding="utf-8"
        )
    )
    raw: dict[str, dict[str, Any]] = json.loads(raw_text)
    result: dict[str, UserFacingMessage] = {}
    for code, payload in raw.items():
        actions = tuple(UserAction(**a) for a in payload.get("actions", []))
        result[code] = UserFacingMessage(
            title=payload["title"],
            body=payload["body"],
            actions=actions,
        )
    return result


_REGISTRY: dict[str, UserFacingMessage] = _load_messages_from_resource()


def has_message(code: str) -> bool:
    """Indique si un message est enregistré pour ce code.

    Args:
        code: Code d'erreur à vérifier.

    Returns:
        ``True`` si un message est enregistré.
    """
    return code in _REGISTRY


def get_message(code: str) -> UserFacingMessage:
    """Récupère le message correspondant à un code, ou un fallback générique.

    Args:
        code: Code d'erreur.

    Returns:
        Le message localisé, ou un fallback générique mentionnant le code brut.
    """
    if code in _REGISTRY:
        return _REGISTRY[code]
    return UserFacingMessage(
        title=_FALLBACK_TITLE,
        body=_FALLBACK_BODY_TEMPLATE.format(code=code),
        actions=(),
    )


def register_message(code: str, message: UserFacingMessage) -> None:
    """Ajoute (ou écrase) un message pour un code donné.

    Args:
        code: Code d'erreur à enregistrer.
        message: Message à associer.
    """
    _REGISTRY[code] = message


def reset_registry_for_tests() -> None:
    """Réinitialise le registre aux messages bundlés (usage tests uniquement)."""
    _REGISTRY.clear()
    _REGISTRY.update(_load_messages_from_resource())
