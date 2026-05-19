"""Loader de templates Jinja2 avec mécanisme de surcouche utilisateur.

Chargement à deux niveaux :

1. Templates par défaut bundlés dans ``infra/prompts/defaults/*.j2``.
2. Surcouche utilisateur dans ``%APPDATA%/Fahmi2/prompts/*.j2`` (si présente).

Quand un fichier ``<nom>.j2`` existe dans le dossier override, il prend la
priorité. Si l'override contient une erreur de syntaxe Jinja2, on retombe sur
le défaut et on émet un ``PROMPT.INVALID_OVERRIDE`` côté logs (le caller en
décide).
"""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path
from typing import Any

from jinja2 import Environment, TemplateSyntaxError, select_autoescape

from fahmi2.core.errors.exceptions import ConfigError
from fahmi2.core.errors.severity import Severity

_DEFAULTS_RESOURCE_PACKAGE = "fahmi2.infra.prompts.defaults"
_TEMPLATE_EXTENSION = ".j2"


class PromptLoader:
    """Charge et rend les prompts depuis défauts bundlés + override utilisateur."""

    def __init__(self, *, override_dir: Path | None = None) -> None:
        """Construit le loader.

        Args:
            override_dir: Dossier de surcouches utilisateur ``*.j2``. Si
                ``None`` ou inexistant, aucun override n'est appliqué.
        """
        self._override_dir = override_dir
        self._env = Environment(
            autoescape=select_autoescape(default=False, default_for_string=False),
            keep_trailing_newline=True,
            trim_blocks=False,
            lstrip_blocks=False,
        )

    def render(self, name: str, **context: Any) -> str:  # noqa: ANN401
        """Charge et rend le template ``name``.

        Args:
            name: Nom du template sans extension (ex: ``phase_3_reformulation``).
            **context: Variables Jinja2.

        Returns:
            Le prompt rendu.

        Raises:
            ConfigError: Si le template par défaut est introuvable ou si la
                surcouche ET le défaut sont invalides.
        """
        source = self._load_source(name)
        try:
            template = self._env.from_string(source)
        except TemplateSyntaxError as exc:
            raise ConfigError(
                code="PROMPT.INVALID_TEMPLATE",
                user_message=f"Template Jinja2 invalide : {name}",
                severity=Severity.ERROR,
                technical_details={"name": name, "error": str(exc)},
            ) from exc
        return template.render(**context)

    def _load_source(self, name: str) -> str:
        """Charge le source du template (override > défaut).

        Args:
            name: Nom du template sans extension.

        Returns:
            Le source Jinja2.

        Raises:
            ConfigError: Si le template par défaut est introuvable.
        """
        if self._override_dir is not None:
            override_path = self._override_dir / f"{name}{_TEMPLATE_EXTENSION}"
            if override_path.exists():
                override_source = override_path.read_text(encoding="utf-8")
                if self._is_valid_jinja(override_source):
                    return override_source
                # Sinon on retombe sur le défaut (signalé par le caller).
        return self._load_default_source(name)

    def _load_default_source(self, name: str) -> str:
        """Charge la version bundlée du template.

        Args:
            name: Nom du template.

        Returns:
            Le source Jinja2.

        Raises:
            ConfigError: Si introuvable.
        """
        try:
            return (
                files(_DEFAULTS_RESOURCE_PACKAGE)
                .joinpath(f"{name}{_TEMPLATE_EXTENSION}")
                .read_text(encoding="utf-8")
            )
        except FileNotFoundError as exc:
            raise ConfigError(
                code="PROMPT.NOT_FOUND",
                user_message=f"Template introuvable : {name}",
                severity=Severity.FATAL,
                technical_details={"name": name},
            ) from exc

    def _is_valid_jinja(self, source: str) -> bool:
        """Indique si ``source`` est syntaxiquement valide.

        Args:
            source: Source Jinja2.

        Returns:
            ``True`` si valide.
        """
        try:
            self._env.from_string(source)
        except TemplateSyntaxError:
            return False
        return True
