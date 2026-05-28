"""Enum :class:`AppLanguage` et constantes de langue (module pur, sans Qt).

Extrait des seuls types Python (StrEnum + libellés) afin que les services
non-UI (par exemple :mod:`fahmi2.app.ui_preferences`) puissent référencer la
langue d'interface **sans** tirer toute la pile ``PySide6.QtCore`` /
``QTranslator`` à l'import.

Le paquet :mod:`fahmi2.i18n` ré-exporte ces symboles pour rester l'API
publique unique côté UI.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final


class AppLanguage(StrEnum):
    """Langues disponibles pour l'interface utilisateur.

    Les valeurs sont les **codes ISO 639-1** (``"fr"``, ``"en"``, …), utilisées
    à la fois comme clé persistée dans ``ui_prefs.json`` et comme suffixe des
    fichiers de traduction (``fahmi2_<code>.qm``).

    ``FR`` est la **langue source** (les chaînes en code sont en français) ;
    elle ne nécessite aucun fichier de traduction. Les autres langues sont
    chargées dynamiquement depuis ``i18n/compiled/fahmi2_<code>.qm`` au
    démarrage.

    Attributes:
        FR: Français (langue source — défaut).
        EN: English (anglais).
    """

    FR = "fr"
    EN = "en"


#: Libellés des langues affichés dans le sélecteur d'apparence (UI).
#:
#: Chaque langue est nommée dans **sa propre langue** — un anglophone qui
#: ouvre une UI en français doit pouvoir reconnaître « English » sans avoir
#: à parler français (et vice-versa). Convention universelle des sélecteurs
#: de langue (Wikipedia, Windows, macOS).
LANGUAGE_LABELS: Final[dict[AppLanguage, str]] = {
    AppLanguage.FR: "Français",
    AppLanguage.EN: "English",
}

#: Langue par défaut (langue source) si aucune préférence persistée.
DEFAULT_LANGUAGE: Final[AppLanguage] = AppLanguage.FR


__all__ = ["DEFAULT_LANGUAGE", "LANGUAGE_LABELS", "AppLanguage"]
