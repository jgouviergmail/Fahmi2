"""Tests du module ``fahmi2.i18n`` (AppLanguage + install_translator).

Vérifie :

- la cohérence des libellés et des codes ISO ;
- la résolution du dossier des ``.qm`` bundlés en mode développement ;
- l'installation du ``QTranslator`` (chargement effectif du ``.qm`` pilote) ;
- la traduction effective d'une chaîne extraite (« Fichier » → « File »).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from PySide6.QtCore import QCoreApplication, QTranslator
from PySide6.QtWidgets import QApplication

from fahmi2.i18n import (
    DEFAULT_LANGUAGE,
    LANGUAGE_LABELS,
    AppLanguage,
    bundled_translations_dir,
    install_translator,
)

_PILOT_SOURCE = "Fichier"
_PILOT_TRANSLATED = "File"
_MAIN_WINDOW_CONTEXT = "MainWindow"

#: Chaînes critiques par contexte migré (filet anti-régression i18n-1).
#:
#: Couvre **au moins une chaîne par contexte** pour qu'un rename de libellé
#: dans le code source sans re-extraction (``scripts/i18n_extract.py``) ou
#: re-compilation (``scripts/i18n_compile.py``) fasse échouer la suite ici
#: plutôt que de laisser l'app EN silencieusement retomber sur la source FR.
#:
#: Format : ``(context, source FR, traduction EN attendue)``.
_TRANSLATION_SMOKE_TESTS: tuple[tuple[str, str, str], ...] = (
    ("MainWindow", "Fichier", "File"),
    ("MainWindow", "À propos de Fahmi2", "About Fahmi2"),
    ("GlobalSettingsDialog", "Redémarrage requis", "Restart required"),
    ("LogsDock", "Niveau minimum", "Minimum level"),
    ("LogsDock", "ERREUR", "ERROR"),
    ("ProjectsSidebar", "Modifier…", "Edit…"),
    ("ProjectHeaderBar", "🚀  Lancer", "🚀  Run"),
    ("StatsStripWidget", "Statut", "Status"),
    ("StatsStripWidget", "sources terminées", "sources completed"),
    ("StatusLabels", "En cours", "Running"),
    ("StatusLabels", "Terminé", "Completed"),
    ("ChatTab", "Dialogue", "Dialogue"),
    ("GenerationTab", "Génération", "Generation"),
    ("PedagogyTab", "Supports pédagogiques", "Revision materials"),
)


@pytest.fixture
def english_translator(qtbot: object) -> Iterator[None]:
    """Installe le ``.qm`` EN bundlé pour la durée d'un test, puis restaure FR.

    Skip silencieux si le ``.qm`` est absent (build propre, scripts non
    exécutés) — le test n'a pas de sens sans artefact.
    """
    del qtbot
    compiled_dir = bundled_translations_dir()
    qm_path = compiled_dir / "fahmi2_en.qm"
    if not qm_path.exists():
        pytest.skip(
            "Aucun fahmi2_en.qm bundlé — lance "
            ".venv\\Scripts\\python.exe scripts\\i18n_compile.py."
        )
    app = QApplication.instance()
    assert isinstance(app, QApplication)
    translator = install_translator(app, AppLanguage.EN, compiled_dir)
    assert isinstance(translator, QTranslator)
    try:
        yield
    finally:
        install_translator(app, AppLanguage.FR, compiled_dir)


def test_default_language_is_french() -> None:
    """La langue source (FR) est la valeur par défaut."""
    assert DEFAULT_LANGUAGE is AppLanguage.FR


def test_labels_are_native_for_each_language() -> None:
    """Chaque langue est libellée dans sa propre langue (convention)."""
    assert LANGUAGE_LABELS[AppLanguage.FR] == "Français"
    assert LANGUAGE_LABELS[AppLanguage.EN] == "English"


def test_all_languages_have_a_label() -> None:
    """Aucune langue ne doit être ajoutée sans son libellé natif (garde-fou)."""
    for lang in AppLanguage:
        assert lang in LANGUAGE_LABELS
        assert LANGUAGE_LABELS[lang].strip() != ""


def test_iso_codes_are_lowercase_two_letters() -> None:
    """Les codes ISO 639-1 sont des chaînes minuscules de 2 caractères."""
    for lang in AppLanguage:
        assert lang.value == lang.value.lower()
        assert len(lang.value) == 2


def test_bundled_translations_dir_resolves_in_dev() -> None:
    """En dev (``sys.frozen`` faux), le dossier est ``src/fahmi2/i18n/compiled``."""
    resolved = bundled_translations_dir()
    # Le chemin attendu se termine par ``fahmi2/i18n/compiled``.
    assert resolved.name == "compiled"
    assert resolved.parent.name == "i18n"
    assert resolved.parent.parent.name == "fahmi2"


def test_install_translator_for_source_language_returns_none(
    qtbot: object, tmp_path: Path
) -> None:
    """FR (langue source) ne nécessite aucun ``.qm`` → retour ``None``."""
    del qtbot
    app = QApplication.instance()
    assert isinstance(app, QApplication)
    assert install_translator(app, AppLanguage.FR, tmp_path) is None


def test_install_translator_returns_none_if_qm_missing(
    qtbot: object, tmp_path: Path
) -> None:
    """``.qm`` absent → ``None`` (best-effort, l'UI reste en langue source)."""
    del qtbot
    app = QApplication.instance()
    assert isinstance(app, QApplication)
    # tmp_path est vide → aucun fahmi2_en.qm
    assert install_translator(app, AppLanguage.EN, tmp_path) is None


def test_install_translator_loads_pilot_qm(qtbot: object) -> None:
    """Le ``.qm`` pilote (généré par scripts/i18n_compile.py) traduit MainWindow.

    Garde-fou bout-en-bout : ``Fichier`` (FR) → ``File`` (EN) après
    installation du traducteur. Si le ``.qm`` n'est pas présent (build
    propre, scripts non exécutés), le test est ignoré silencieusement —
    il est joué de nouveau dès que ``i18n_compile.py`` a tourné.
    """
    del qtbot
    compiled_dir = bundled_translations_dir()
    qm_path = compiled_dir / "fahmi2_en.qm"
    if not qm_path.exists():
        pytest.skip(
            "Aucun fahmi2_en.qm bundlé — lance "
            ".venv\\Scripts\\python.exe scripts\\i18n_compile.py."
        )

    app = QApplication.instance()
    assert isinstance(app, QApplication)
    translator = install_translator(app, AppLanguage.EN, compiled_dir)
    try:
        assert isinstance(translator, QTranslator)
        translated = QCoreApplication.translate(_MAIN_WINDOW_CONTEXT, _PILOT_SOURCE)
        assert translated == _PILOT_TRANSLATED
    finally:
        # Restauration : on remet la langue source pour ne pas polluer les
        # autres tests qui suivent.
        install_translator(app, AppLanguage.FR, compiled_dir)


@pytest.mark.parametrize(("context", "source_fr", "expected_en"), _TRANSLATION_SMOKE_TESTS)
def test_critical_strings_translate_to_english(
    english_translator: None,  # noqa: ARG001
    context: str,
    source_fr: str,
    expected_en: str,
) -> None:
    """Vérifie qu'une chaîne critique par contexte migré est bien traduite en EN.

    Filet anti-régression : si un développeur renomme une chaîne dans le
    code source sans relancer ``scripts/i18n_extract.py`` puis
    ``scripts/i18n_compile.py``, ``QCoreApplication.translate`` retourne
    silencieusement la nouvelle source FR (l'UI EN retombe en FR sans
    erreur). Ce test détecte la divergence avant qu'un utilisateur EN ne la
    rencontre.

    Args:
        english_translator: Fixture qui installe le ``.qm`` EN.
        context: Contexte Linguist (nom de classe ou identifiant manuel).
        source_fr: Chaîne FR du code source.
        expected_en: Traduction EN attendue dans le ``.qm`` compilé.
    """
    assert QCoreApplication.translate(context, source_fr) == expected_en
