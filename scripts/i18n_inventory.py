"""Inventaire des chaînes UI à migrer vers Qt tr().

Parcourt ``src/fahmi2/ui/`` et compte, pour chaque fichier, les chaînes
littérales candidates à la traduction (string literals contenant au moins
une lettre, longueur > 1, en dehors des docstrings et des commentaires —
filtrage par ``ast.walk`` + ``ast.get_docstring``). Sortie : un tableau
trié décroissant + total global, pour mesurer l'ampleur de la migration
i18n et identifier les fichiers à attaquer en premier.

Lance sans argument :

    .venv\\Scripts\\python.exe scripts\\i18n_inventory.py
"""

from __future__ import annotations

import ast
import sys
from collections import Counter
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_UI_DIR = _REPO_ROOT / "src" / "fahmi2" / "ui"
_MIN_LENGTH = 2


def _is_candidate(value: str) -> bool:
    """Filtre les chaînes candidates à la traduction.

    Args:
        value: Chaîne littérale.

    Returns:
        ``True`` si la chaîne a au moins une lettre et > 1 caractère.
    """
    if len(value) < _MIN_LENGTH:
        return False
    return any(ch.isalpha() for ch in value)


def _is_docstring(node: ast.AST, parents: dict[int, ast.AST]) -> bool:
    """Vrai si ``node`` est la première instruction (docstring) d'un container.

    Args:
        node: Nœud ``ast.Constant`` (chaîne).
        parents: Mapping ``id(child) -> parent`` calculé en amont.

    Returns:
        ``True`` si le nœud est une docstring de module/classe/fonction.
    """
    parent = parents.get(id(node))
    if parent is None:
        return False
    grand = parents.get(id(parent))
    if grand is None:
        return False
    if not isinstance(parent, ast.Expr):
        return False
    if not isinstance(
        grand, ast.Module | ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef
    ):
        return False
    body = grand.body
    return bool(body) and body[0] is parent


def _count_strings(path: Path) -> int:
    """Compte les chaînes littérales candidates dans un fichier Python.

    Args:
        path: Fichier source.

    Returns:
        Nombre de chaînes candidates.
    """
    try:
        source = path.read_text(encoding="utf-8")
    except OSError:
        return 0
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return 0

    parents: dict[int, ast.AST] = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[id(child)] = parent

    count = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant):
            continue
        if not isinstance(node.value, str):
            continue
        if _is_docstring(node, parents):
            continue
        if not _is_candidate(node.value):
            continue
        count += 1
    return count


def main() -> int:
    """Affiche l'inventaire.

    Returns:
        Code de sortie.
    """
    counts: Counter[Path] = Counter()
    for path in sorted(_UI_DIR.rglob("*.py")):
        n = _count_strings(path)
        if n > 0:
            counts[path] = n

    total = sum(counts.values())
    print(f"Inventaire des chaînes UI candidates (racine: {_UI_DIR.relative_to(_REPO_ROOT)})\n")
    print(f"{'Fichier':<70} {'Chaînes':>8}")
    print("-" * 80)
    for path, n in counts.most_common():
        rel = path.relative_to(_REPO_ROOT).as_posix()
        print(f"{rel:<70} {n:>8}")
    print("-" * 80)
    print(f"{'TOTAL':<70} {total:>8}")
    print(f"\nFichiers concernés : {len(counts)} / {sum(1 for _ in _UI_DIR.rglob('*.py'))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
