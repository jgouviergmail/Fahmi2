"""Tokens centralisés du système de design (palettes light/dark, ombres, modes).

Source unique de référence Python pour les couleurs, paramètres d'ombre et le
mode d'apparence. Les fichiers QSS (``light_fluent.qss`` /
``dark_fluent.qss``) répliquent les valeurs en hexadécimal littéral
(QSS ne supportant pas les variables) ; la synchronisation est garantie par
convention et le test ``tests/unit/ui/test_theme_sync.py``.

Expose :

- ``ThemeMode`` : mode d'apparence (système / clair / sombre).
- ``TokenPalette`` : palette d'un mode (couleurs + spec d'ombre).
- ``LIGHT_TOKENS`` / ``DARK_TOKENS`` : palettes des deux modes.
- ``current_palette`` / ``set_current_palette`` : palette effective courante
  (mise à jour par ``apply_theme``), utilisée notamment par
  ``install_shadow`` pour appliquer une ombre adaptée au thème actif.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from PySide6.QtGui import QColor


class ThemeMode(StrEnum):
    """Mode d'apparence sélectionné par l'utilisateur.

    ``SYSTEM`` suit le mode du système (Qt 6.5+ : ``QStyleHints.colorScheme``).
    """

    SYSTEM = "system"
    LIGHT = "light"
    DARK = "dark"


@dataclass(frozen=True)
class ShadowSpec:
    """Spécification d'une ombre douce pour ``QGraphicsDropShadowEffect``.

    Attributes:
        blur_radius: Rayon de flou.
        x_offset: Décalage horizontal.
        y_offset: Décalage vertical.
        color: Couleur de l'ombre (alpha inclus).
    """

    blur_radius: float
    x_offset: float
    y_offset: float
    color: QColor


@dataclass(frozen=True)
class TokenPalette:
    """Palette de tokens d'un mode d'apparence (clair ou sombre).

    Toutes les couleurs sont des chaînes hexadécimales ``#rrggbb`` directement
    consommables par Qt (QSS, ``QColor``).

    Attributes:
        name: Identifiant court (``"light"`` ou ``"dark"``).
        bg: Fond de fenêtre.
        surface: Surface des cartes / menus / popovers.
        surface_soft: Surface des listes de navigation.
        surface_elevated: Surface des éléments « surélevés » (popups,
            tooltips).
        border: Bordure de champ.
        border_card: Bordure de carte.
        divider: Séparateur fin.
        text_1: Texte principal.
        text_2: Libellé secondaire.
        text_3: Texte d'aide, micro-info.
        accent: Accent primaire.
        accent_hover: Hover du primaire.
        accent_pressed: Pressed du primaire.
        accent_soft: Surface accentuée douce (sélection, pilule).
        accent_strong: Texte sur fond ``accent_soft``.
        success: Statut succès (texte).
        success_bg: Surface succès (badge).
        warning: Statut attention.
        warning_bg: Surface attention.
        danger: Statut erreur / destructif.
        danger_bg: Surface erreur.
        info: Statut info / skipped / neutre (texte). Couleur distincte des
            autres statuts pour ne pas signaler une attention. Utilisé par la
            matrice de coût pour le statut ``SKIPPED``.
        info_bg: Surface info / skipped (badge).
        shadow_card: Ombre des cartes.
    """

    name: str
    bg: str
    surface: str
    surface_soft: str
    surface_elevated: str
    border: str
    border_card: str
    divider: str
    text_1: str
    text_2: str
    text_3: str
    accent: str
    accent_hover: str
    accent_pressed: str
    accent_soft: str
    accent_strong: str
    success: str
    success_bg: str
    warning: str
    warning_bg: str
    danger: str
    danger_bg: str
    info: str
    info_bg: str
    shadow_card: ShadowSpec


#: Palette du mode clair (baseline conservée).
LIGHT_TOKENS: Final[TokenPalette] = TokenPalette(
    name="light",
    bg="#f5f7fb",
    surface="#ffffff",
    surface_soft="#fbfcfe",
    surface_elevated="#ffffff",
    border="#d6dae0",
    border_card="#e9ecf1",
    divider="#eef0f4",
    text_1="#1f2328",
    text_2="#57606a",
    text_3="#8b95a1",
    accent="#0078d4",
    accent_hover="#1086e8",
    accent_pressed="#006abf",
    accent_soft="#e3f0fb",
    accent_strong="#0a4f93",
    success="#1a7f37",
    success_bg="#e6f6ec",
    warning="#b45309",
    warning_bg="#fef3c7",
    danger="#cf222e",
    danger_bg="#fcebec",
    info="#5b4cc7",
    info_bg="#f1eefb",
    shadow_card=ShadowSpec(
        blur_radius=22.0,
        x_offset=0.0,
        y_offset=4.0,
        # rgba(15,23,42,0.10) — soft, baseline-faithful.
        color=QColor(15, 23, 42, 26),
    ),
)


#: Palette du mode sombre (miroir token-pour-token).
DARK_TOKENS: Final[TokenPalette] = TokenPalette(
    name="dark",
    bg="#11151c",
    surface="#1a1f27",
    surface_soft="#161b22",
    surface_elevated="#222831",
    border="#2a2f38",
    border_card="#262b34",
    divider="#232831",
    text_1="#e6e9ef",
    text_2="#9aa3b2",
    text_3="#6e7787",
    accent="#4aa3ee",
    accent_hover="#67b3f1",
    accent_pressed="#3a93de",
    accent_soft="#15314d",
    accent_strong="#9cc8f4",
    success="#3fb950",
    success_bg="#122c1a",
    warning="#d29922",
    warning_bg="#2c1f0f",
    danger="#f85149",
    danger_bg="#2c1419",
    info="#b5a3e3",
    info_bg="#241e3a",
    shadow_card=ShadowSpec(
        blur_radius=24.0,
        x_offset=0.0,
        y_offset=6.0,
        # rgba(0,0,0,0.45) — plus marqué pour ressortir sur fond sombre.
        color=QColor(0, 0, 0, 115),
    ),
)


def palette_for(mode: ThemeMode) -> TokenPalette:
    """Retourne la palette correspondant à un mode résolu (clair ou sombre).

    Args:
        mode: Mode résolu (``LIGHT`` ou ``DARK`` ; ``SYSTEM`` est résolu en
            amont par ``apply_theme``).

    Returns:
        La palette correspondante.

    Raises:
        ValueError: Si ``mode`` est ``SYSTEM`` (non résolu) ou inconnu.
    """
    if mode is ThemeMode.LIGHT:
        return LIGHT_TOKENS
    if mode is ThemeMode.DARK:
        return DARK_TOKENS
    raise ValueError(f"palette_for: mode non résolu : {mode!r}")


# État de runtime : palette effectivement appliquée. Encapsulé dans un
# dictionnaire pour éviter ``global`` et permettre l'extension ultérieure.
_STATE: dict[str, TokenPalette] = {"current": LIGHT_TOKENS}


def current_palette() -> TokenPalette:
    """Retourne la palette du thème effectivement appliqué.

    Returns:
        ``LIGHT_TOKENS`` ou ``DARK_TOKENS`` selon le thème actif (mis à jour
        par ``apply_theme``).
    """
    return _STATE["current"]


def set_current_palette(palette: TokenPalette) -> None:
    """Met à jour la palette active (appelé par ``apply_theme``).

    Args:
        palette: Palette à activer.
    """
    _STATE["current"] = palette


__all__ = [
    "DARK_TOKENS",
    "LIGHT_TOKENS",
    "ShadowSpec",
    "ThemeMode",
    "TokenPalette",
    "current_palette",
    "palette_for",
    "set_current_palette",
]
