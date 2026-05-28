"""Extrait les chaînes traduisibles vers ``src/fahmi2/i18n/translations/``.

Enveloppe ``pyside6-lupdate`` :

- parse récursivement ``src/fahmi2/`` (toutes les chaînes marquées par
  ``self.tr()``, ``QCoreApplication.translate(...)``, ``QT_TR_NOOP(...)``,
  ``QT_TRANSLATE_NOOP(...)``) ;
- met à jour le fichier ``.ts`` pour chaque langue cible (création si absent,
  fusion conservant les traductions existantes — c'est le comportement
  natif de ``lupdate``).

Convention :

- langue source = français → fichiers ``.ts`` portant les chaînes FR comme
  *source* ;
- langues cibles = toutes les valeurs de :class:`fahmi2.i18n.AppLanguage`
  **sauf** la langue source.

Lance sans argument :

    .venv\\Scripts\\python.exe scripts\\i18n_extract.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# Sur Windows, ``sys.stdout`` est cp1252 par défaut → caractères accentués et
# Unicode (« → », « ⚠ », « … ») plantent en ``UnicodeEncodeError``. On bascule
# stdout/stderr en UTF-8 si possible (no-op si déjà en UTF-8 ou non supporté).
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SRC_DIR = _REPO_ROOT / "src" / "fahmi2"
_TRANSLATIONS_DIR = _SRC_DIR / "i18n" / "translations"
_LUPDATE_BIN = _REPO_ROOT / ".venv" / "Scripts" / "pyside6-lupdate.exe"


def main() -> int:
    """Génère / met à jour les ``.ts`` pour toutes les langues cibles.

    Returns:
        Code de sortie (0 si succès, sinon dernier code d'erreur de lupdate).
    """
    # Import différé pour éviter de charger PySide6 inutilement si on ne fait
    # que vérifier les outils.
    from fahmi2.i18n import DEFAULT_LANGUAGE, AppLanguage  # noqa: PLC0415

    if not _LUPDATE_BIN.exists():
        print(f"Erreur : pyside6-lupdate introuvable à {_LUPDATE_BIN}", file=sys.stderr)
        return 1

    _TRANSLATIONS_DIR.mkdir(parents=True, exist_ok=True)

    # Liste des sources : tous les .py sous src/fahmi2 (lupdate accepte des
    # listes explicites de fichiers / dossiers).
    sources = [str(_SRC_DIR)]

    # Une langue cible = un .ts (langue source FR exclue : c'est la langue des
    # chaînes en code, donc rien à traduire).
    target_languages = [lang for lang in AppLanguage if lang is not DEFAULT_LANGUAGE]
    if not target_languages:
        print("Aucune langue cible (seule la langue source est définie).")
        return 0

    last_code = 0
    for lang in target_languages:
        ts_path = _TRANSLATIONS_DIR / f"fahmi2_{lang.value}.ts"
        print(f"→ Extraction vers {ts_path.relative_to(_REPO_ROOT)} …")
        cmd = [
            str(_LUPDATE_BIN),
            # ``pyside6-lupdate`` parse C++/JS par défaut — il faut explicitement
            # demander l'extension ``py`` pour qu'il scanne les sources Python.
            "-extensions",
            "py",
            *sources,
            "-ts",
            str(ts_path),
            "-source-language",
            DEFAULT_LANGUAGE.value,
            "-target-language",
            lang.value,
            "-no-obsolete",
        ]
        result = subprocess.run(cmd, check=False)  # noqa: S603
        if result.returncode != 0:
            print(f"  ⚠ lupdate a renvoyé {result.returncode}", file=sys.stderr)
            last_code = result.returncode

    return last_code


if __name__ == "__main__":
    sys.exit(main())
