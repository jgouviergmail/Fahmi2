"""Adapter d'export Anki (.apkg) via ``genanki``.

Convertit les artefacts de supports en cartes Anki : flashcards → note Basic,
cloze → note Cloze, QCM → note custom. GUID stables (ré-import sans doublon),
sous-decks par support, tags (support / langue / difficulté / chapitre).
"""

from __future__ import annotations

import hashlib
import re
import string
from dataclasses import dataclass
from pathlib import Path

import genanki

from fahmi2.domain.enums import SupportType
from fahmi2.domain.supports import ClozeItem, Flashcard, QcmItem, SupportItem
from fahmi2.pedagogy.artifact_reader import ParsedArtifact

# IDs de modèles Anki (fixes, choisis une fois pour toutes).
_BASIC_MODEL_ID = 1_607_392_319
_CLOZE_MODEL_ID = 1_607_392_320
_QCM_MODEL_ID = 1_607_392_321

_DECK_ID_MODULO = 1 << 31
_DECK_SEPARATOR = "::"
_CLOZE_MARKER = "___"
_CHOICE_LETTERS = string.ascii_uppercase
_CHOICE_SEPARATOR = "<br>"
_ENCODING_UTF8 = "utf-8"
#: Anki interdit les espaces dans les tags (séparateur de tags) : on les remplace.
_TAG_WHITESPACE_RE = re.compile(r"\s+")
_TAG_WHITESPACE_REPLACEMENT = "_"

_SUPPORT_LABELS: dict[SupportType, str] = {
    SupportType.FLASHCARDS_GLOSSARY: "Flashcards Glossaire",
    SupportType.FLASHCARDS_CONCEPTS: "Flashcards Concepts",
    SupportType.QCM: "QCM",
    SupportType.CLOZE: "Textes à trous",
}

_BASIC_MODEL = genanki.Model(
    _BASIC_MODEL_ID,
    "Fahmi2 Basic",
    fields=[{"name": "Recto"}, {"name": "Verso"}],
    templates=[
        {
            "name": "Carte",
            "qfmt": "{{Recto}}",
            "afmt": '{{FrontSide}}<hr id="answer">{{Verso}}',
        }
    ],
)
_CLOZE_MODEL = genanki.Model(
    _CLOZE_MODEL_ID,
    "Fahmi2 Cloze",
    fields=[{"name": "Texte"}],
    templates=[
        {"name": "Cloze", "qfmt": "{{cloze:Texte}}", "afmt": "{{cloze:Texte}}"}
    ],
    model_type=genanki.Model.CLOZE,
)
_QCM_MODEL = genanki.Model(
    _QCM_MODEL_ID,
    "Fahmi2 QCM",
    fields=[
        {"name": "Question"},
        {"name": "Choix"},
        {"name": "Reponse"},
        {"name": "Justification"},
    ],
    templates=[
        {
            "name": "QCM",
            "qfmt": "{{Question}}<br><br>{{Choix}}",
            "afmt": (
                '{{FrontSide}}<hr id="answer"><b>Réponse :</b> {{Reponse}}'
                "<br>{{Justification}}"
            ),
        }
    ],
)


@dataclass(frozen=True)
class AnkiExportResult:
    """Résultat d'un export Anki.

    Attributes:
        output_path: Chemin du fichier ``.apkg`` écrit.
        note_count: Nombre de notes exportées.
        deck_count: Nombre de sous-decks créés.
    """

    output_path: Path
    note_count: int
    deck_count: int


def _to_anki_cloze(text: str, answers: tuple[str, ...]) -> str:
    """Convertit un texte à trous ``___`` en syntaxe cloze Anki ``{{cN::…}}``.

    Args:
        text: Texte avec marqueurs ``___``.
        answers: Réponses, dans l'ordre des trous.

    Returns:
        Le texte au format cloze Anki (les trous excédentaires restent ``___``).
    """
    result = text
    for index, answer in enumerate(answers, start=1):
        if _CLOZE_MARKER not in result:
            break
        result = result.replace(_CLOZE_MARKER, f"{{{{c{index}::{answer}}}}}", 1)
    return result


def _sanitize_tag(value: str) -> str:
    """Rend une valeur compatible avec un tag Anki (sans espace).

    Anki sépare les tags sur les espaces ; ``genanki`` lève d'ailleurs si un tag
    en contient. Les termes de glossaire multi-mots (``source_ref``) doivent donc
    être assainis (espaces → ``_``).

    Args:
        value: Valeur brute (terme, ancre de chapitre, niveau…).

    Returns:
        La valeur sans espace (chaque suite d'espaces remplacée par ``_``).
    """
    return _TAG_WHITESPACE_RE.sub(_TAG_WHITESPACE_REPLACEMENT, value.strip())


def _stable_deck_id(name: str) -> int:
    """ID de deck stable dérivé du nom (sha256 borné, > 0).

    Args:
        name: Nom complet du deck.

    Returns:
        Un entier stable dans ``[1, 2**31]``.
    """
    digest = hashlib.sha256(name.encode(_ENCODING_UTF8)).hexdigest()
    return int(digest[:8], 16) % _DECK_ID_MODULO + 1


def _render_choices(item: QcmItem) -> str:
    """Rend les propositions d'un QCM en HTML (``A. … <br> B. …``).

    Args:
        item: Question à choix multiples.

    Returns:
        Les propositions formatées.
    """
    return _CHOICE_SEPARATOR.join(
        f"{_CHOICE_LETTERS[index]}. {choice}"
        for index, choice in enumerate(item.choices)
    )


class GenankiExporter:
    """Exporte des ``ParsedArtifact`` vers un fichier ``.apkg``."""

    def export_to_file(
        self,
        artifacts: list[ParsedArtifact],
        *,
        deck_root: str,
        difficulty: str,
        output_path: Path,
    ) -> AnkiExportResult:
        """Construit les decks/notes et écrit le paquet Anki.

        Args:
            artifacts: Artefacts désérialisés (exportables).
            deck_root: Racine du nom de deck (nom du projet).
            difficulty: Difficulté (tag), ex. ``"licence"``.
            output_path: Chemin du ``.apkg`` à écrire.

        Returns:
            ``AnkiExportResult``.
        """
        decks: dict[str, genanki.Deck] = {}
        note_count = 0
        for artifact in artifacts:
            deck = self._deck_for(decks, deck_root, artifact.support_type)
            for item in artifact.items:
                note = self._note_for(artifact, item, difficulty=difficulty)
                if note is not None:
                    deck.add_note(note)
                    note_count += 1
        output_path.parent.mkdir(parents=True, exist_ok=True)
        genanki.Package(list(decks.values())).write_to_file(str(output_path))
        return AnkiExportResult(
            output_path=output_path, note_count=note_count, deck_count=len(decks)
        )

    def _deck_for(
        self,
        decks: dict[str, genanki.Deck],
        deck_root: str,
        support_type: SupportType,
    ) -> genanki.Deck:
        """Retourne (en le créant au besoin) le sous-deck d'un support.

        Args:
            decks: Cache des decks par nom.
            deck_root: Racine du nom de deck.
            support_type: Type de support.

        Returns:
            Le ``genanki.Deck`` correspondant.
        """
        label = _SUPPORT_LABELS.get(support_type, support_type.value)
        name = f"{deck_root}{_DECK_SEPARATOR}{label}"
        deck = decks.get(name)
        if deck is None:
            deck = genanki.Deck(_stable_deck_id(name), name)
            decks[name] = deck
        return deck

    def _note_for(
        self, artifact: ParsedArtifact, item: SupportItem, *, difficulty: str
    ) -> genanki.Note | None:
        """Construit la note Anki d'un item, ou ``None`` si non mappable.

        Args:
            artifact: Artefact source (support/langue).
            item: Item à convertir.
            difficulty: Difficulté (tag).

        Returns:
            La ``genanki.Note``, ou ``None`` si le type d'item n'est pas mappable.
        """
        if isinstance(item, Flashcard):
            return genanki.Note(
                model=_BASIC_MODEL,
                fields=[item.front, item.back],
                guid=self._note_guid(artifact, item.front),
                tags=self._tags(artifact, difficulty, item.source_ref),
            )
        if isinstance(item, ClozeItem):
            return genanki.Note(
                model=_CLOZE_MODEL,
                fields=[_to_anki_cloze(item.text, item.answers)],
                guid=self._note_guid(artifact, item.text),
                tags=self._tags(artifact, difficulty, item.source_ref),
            )
        if isinstance(item, QcmItem):
            answer = f"{_CHOICE_LETTERS[item.correct_index]}. {item.choices[item.correct_index]}"
            return genanki.Note(
                model=_QCM_MODEL,
                fields=[
                    item.question,
                    _render_choices(item),
                    answer,
                    item.justification,
                ],
                guid=self._note_guid(artifact, item.question),
                tags=self._tags(artifact, difficulty, item.source_ref),
            )
        return None

    @staticmethod
    def _note_guid(artifact: ParsedArtifact, key: str) -> str:
        """GUID stable d'une note (ré-import sans doublon).

        Args:
            artifact: Artefact source.
            key: Clé de contenu (recto / texte / question).

        Returns:
            Un GUID déterministe.
        """
        return str(
            genanki.guid_for(
                artifact.support_type.value, artifact.language.value, key
            )
        )

    @staticmethod
    def _tags(artifact: ParsedArtifact, difficulty: str, source_ref: str) -> list[str]:
        """Construit les tags d'une note (sans espace, compatibles Anki).

        Args:
            artifact: Artefact source.
            difficulty: Difficulté.
            source_ref: Référence d'origine (ancre de chapitre / terme).

        Returns:
            La liste des tags.
        """
        return [
            artifact.support_type.value,
            f"langue:{artifact.language.value}",
            f"niveau:{_sanitize_tag(difficulty)}",
            f"chapitre:{_sanitize_tag(source_ref)}",
        ]
