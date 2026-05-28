"""Système d'internationalisation (i18n) de l'UI Fahmi2.

L'application utilise la pile native Qt :

- les chaînes d'interface sont marquées par :py:meth:`QObject.tr` (méthodes
  d'instance) ou :func:`QCoreApplication.translate` (fonctions libres), avec
  :func:`QT_TR_NOOP`/:func:`QT_TRANSLATE_NOOP` pour les chaînes au niveau
  module ;
- ``pyside6-lupdate`` extrait les chaînes vers des fichiers ``.ts`` ;
- Qt Linguist (ou un éditeur de texte) ajoute les traductions ;
- ``pyside6-lrelease`` compile les ``.ts`` en ``.qm`` binaires chargés au
  démarrage.

La langue source est le **français** (les chaînes en code sont donc en
français — pas de "code in English" comme conventionnellement en Qt).
``AppLanguage.FR`` correspond à la langue source : aucun fichier ``.qm``
n'est requis pour l'afficher.

Extensibilité : ajouter une langue = ajouter une valeur à :class:`AppLanguage`,
créer ``fahmi2_<code>.ts`` (via ``scripts/i18n_extract.py``), traduire,
compiler (``scripts/i18n_compile.py``). Aucune autre modification de code.

L'enum :class:`AppLanguage` et les libellés vivent dans
:mod:`fahmi2.i18n.languages` (module **pur Python sans dépendance Qt**) pour
permettre aux services non-UI (par exemple :mod:`fahmi2.app.ui_preferences`)
de les utiliser sans charger ``PySide6.QtCore.QTranslator``. Le présent
paquet ré-exporte ces symboles pour rester l'API publique unique.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Final

from PySide6.QtCore import QLocale, QTranslator
from PySide6.QtWidgets import QApplication

from fahmi2.i18n.languages import DEFAULT_LANGUAGE, LANGUAGE_LABELS, AppLanguage

#: Préfixe des fichiers de traduction (``fahmi2_<code>.ts`` / ``.qm``).
_TRANSLATION_PREFIX: Final[str] = "fahmi2_"
#: Suffixe des fichiers compilés.
_TRANSLATION_SUFFIX: Final[str] = ".qm"
#: Nom du sous-dossier abritant les ``.qm`` compilés (dans le paquet ``i18n``).
_COMPILED_DIRNAME: Final[str] = "compiled"

#: Cache du ``QTranslator`` actif (par ``QApplication``).
#:
#: Pourquoi ce cache ? Lorsqu'on change de langue, il faut désinstaller le
#: traducteur précédent. Stocker la référence directement comme attribut sur
#: l'``QApplication`` (``app._fahmi2_translator = ...``) mute dynamiquement
#: un type C++ enveloppé — moins propre que d'isoler la référence côté
#: Python. Mapping indexé par ``id(app)`` (clé stable tant que l'app vit ;
#: pas de fuite car on désinstalle systématiquement le précédent avant d'en
#: poser un nouveau).
_ACTIVE_TRANSLATORS: dict[int, QTranslator] = {}


def bundled_translations_dir() -> Path:
    """Retourne le dossier des ``.qm`` compilés bundlés avec l'application.

    - En mode développement : ``src/fahmi2/i18n/compiled/`` (résolu via
      ``__file__`` — vit à côté de ce module).
    - En mode packagé (PyInstaller) : ``<bundle_root>/fahmi2/i18n/compiled/``
      via ``sys._MEIPASS`` (l'analyse d'imports + ``collect_submodules`` du
      ``.spec`` recopie le paquet, mais pas les ``.qm`` qu'il faut ajouter
      explicitement dans ``datas`` ; cf. ``packaging/fahmi2.spec``).

    Le dossier n'a pas besoin d'exister : si aucun ``.qm`` n'y est présent,
    :func:`install_translator` retourne ``None`` (l'UI reste en langue source,
    best-effort).

    Returns:
        Le chemin résolu vers ``i18n/compiled/``.
    """
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass) / "fahmi2" / "i18n" / _COMPILED_DIRNAME
    return Path(__file__).resolve().parent / _COMPILED_DIRNAME


def install_translator(
    app: QApplication, language: AppLanguage, translations_dir: Path
) -> QTranslator | None:
    """Installe le ``QTranslator`` correspondant à ``language`` sur ``app``.

    Désinstalle tout traducteur précédent posé par cette fonction (via le
    cache module-level :data:`_ACTIVE_TRANSLATORS`) puis :

    - si ``language`` est la langue source (:data:`AppLanguage.FR`) : aucun
      traducteur n'est nécessaire, retourne ``None``.
    - sinon : charge ``fahmi2_<code>.qm`` depuis ``translations_dir`` et
      l'installe ; retourne le traducteur installé. Si le ``.qm`` est absent
      ou invalide, l'UI reste en langue source (best-effort — un défaut de
      traduction ne doit jamais empêcher l'app de démarrer).

    Aligne aussi :func:`QLocale.setDefault` pour que les widgets natifs Qt
    (boutons standard, formatages de dates/nombres) suivent la langue choisie.

    Args:
        app: ``QApplication`` cible.
        language: Langue à installer.
        translations_dir: Dossier des ``.qm`` compilés (typiquement
            ``i18n/compiled/`` dans le bundle).

    Returns:
        Le ``QTranslator`` installé, ou ``None`` si aucune traduction n'est
        nécessaire / disponible.
    """
    app_key = id(app)
    previous = _ACTIVE_TRANSLATORS.pop(app_key, None)
    if previous is not None:
        app.removeTranslator(previous)
        # Détache et programme la destruction du précédent : sans cela, le
        # ``QTranslator`` reste enfant de l'``QApplication`` côté C++ et
        # continue de recevoir des événements ``LanguageChange``, ce qui peut
        # interagir avec d'autres widgets dans la session de tests
        # (corruption mémoire observée). ``deleteLater`` est le pattern Qt
        # canonique pour un cleanup sûr en présence d'événements en vol.
        previous.setParent(None)
        previous.deleteLater()

    QLocale.setDefault(QLocale(language.value))

    if language is AppLanguage.FR:
        return None

    qm_path = translations_dir / f"{_TRANSLATION_PREFIX}{language.value}{_TRANSLATION_SUFFIX}"
    translator = QTranslator(app)
    if not qm_path.exists() or not translator.load(str(qm_path)):
        # Best-effort : ``.qm`` absent ou invalide → on reste en langue source.
        # Le translator non chargé est aussi nettoyé pour ne pas laisser un
        # QObject orphelin attaché à l'app.
        translator.setParent(None)
        translator.deleteLater()
        return None
    app.installTranslator(translator)
    _ACTIVE_TRANSLATORS[app_key] = translator
    return translator


__all__ = [
    "DEFAULT_LANGUAGE",
    "LANGUAGE_LABELS",
    "AppLanguage",
    "bundled_translations_dir",
    "install_translator",
]
