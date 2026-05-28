"""Compile les ``.ts`` de ``i18n/translations/`` en ``.qm`` dans ``i18n/compiled/``.

Enveloppe ``pyside6-lrelease`` : pour chaque ``fahmi2_<code>.ts``, génère
``fahmi2_<code>.qm`` (format binaire chargé par ``QTranslator.load``). Le
dossier ``compiled/`` est destiné à être bundlé avec l'application
(``packaging/fahmi2.spec`` doit l'inclure dans ``datas``).

Lance sans argument :

    .venv\\Scripts\\python.exe scripts\\i18n_compile.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# Sur Windows, ``sys.stdout`` est cp1252 par défaut → caractères accentués et
# Unicode (« → », « ⚠ ») plantent en ``UnicodeEncodeError``. On bascule
# stdout/stderr en UTF-8 si possible.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

_REPO_ROOT = Path(__file__).resolve().parent.parent
_I18N_DIR = _REPO_ROOT / "src" / "fahmi2" / "i18n"
_TRANSLATIONS_DIR = _I18N_DIR / "translations"
_COMPILED_DIR = _I18N_DIR / "compiled"
_LRELEASE_BIN = _REPO_ROOT / ".venv" / "Scripts" / "pyside6-lrelease.exe"


def main() -> int:
    """Compile tous les ``.ts`` du dossier ``translations/`` en ``.qm``.

    Returns:
        Code de sortie (0 si succès).
    """
    if not _LRELEASE_BIN.exists():
        print(f"Erreur : pyside6-lrelease introuvable à {_LRELEASE_BIN}", file=sys.stderr)
        return 1

    _COMPILED_DIR.mkdir(parents=True, exist_ok=True)

    ts_files = sorted(_TRANSLATIONS_DIR.glob("fahmi2_*.ts"))
    if not ts_files:
        print(f"Aucun .ts trouvé dans {_TRANSLATIONS_DIR.relative_to(_REPO_ROOT)}.")
        print("Lance d'abord : .venv\\Scripts\\python.exe scripts\\i18n_extract.py")
        return 0

    last_code = 0
    for ts_path in ts_files:
        qm_path = _COMPILED_DIR / (ts_path.stem + ".qm")
        print(
            f"→ Compilation {ts_path.relative_to(_REPO_ROOT)} → "
            f"{qm_path.relative_to(_REPO_ROOT)}"
        )
        cmd = [str(_LRELEASE_BIN), str(ts_path), "-qm", str(qm_path)]
        result = subprocess.run(cmd, check=False)  # noqa: S603
        if result.returncode != 0:
            print(f"  ⚠ lrelease a renvoyé {result.returncode}", file=sys.stderr)
            last_code = result.returncode

    return last_code


if __name__ == "__main__":
    sys.exit(main())
