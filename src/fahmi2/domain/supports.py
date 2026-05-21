"""Entités structurées des supports de révision (immuables).

Représentations consommées par les exports SP3 (Anki, Markdown/PDF) et écrites
sur disque (JSON + Markdown rendu). Le ``source_ref`` trace l'origine (terme de
glossaire ou ancre/chapitre du document consolidé).
"""

from __future__ import annotations

from dataclasses import dataclass

from fahmi2.domain.enums import Language, SupportType

#: Nombre minimal de propositions pour un item de QCM.
_MIN_QCM_CHOICES = 2
#: Nombre maximal de propositions pour un item de QCM (lettres A..Z au rendu).
_MAX_QCM_CHOICES = 26


@dataclass(frozen=True)
class Flashcard:
    """Carte recto/verso.

    Attributes:
        front: Recto (terme / acronyme / question).
        back: Verso (définition / réponse).
        source_ref: Référence d'origine (terme de glossaire ou ancre de chapitre).
        tags: Étiquettes (type de support, langue…), pour l'export Anki.
    """

    front: str
    back: str
    source_ref: str
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class QcmItem:
    """Question à choix multiple.

    Attributes:
        question: Énoncé de la question.
        choices: Propositions (au moins ``_MIN_QCM_CHOICES``).
        correct_index: Index (0-based) de la bonne proposition dans ``choices``.
        justification: Explication de la bonne réponse.
        source_ref: Référence d'origine (ancre de chapitre).
    """

    question: str
    choices: tuple[str, ...]
    correct_index: int
    justification: str
    source_ref: str

    def __post_init__(self) -> None:
        if len(self.choices) < _MIN_QCM_CHOICES:
            raise ValueError(
                f"choices must contain at least {_MIN_QCM_CHOICES} options"
            )
        if len(self.choices) > _MAX_QCM_CHOICES:
            raise ValueError(
                f"choices must contain at most {_MAX_QCM_CHOICES} options"
            )
        if not 0 <= self.correct_index < len(self.choices):
            raise ValueError(
                f"correct_index must be in [0, {len(self.choices)}), "
                f"got {self.correct_index}"
            )


@dataclass(frozen=True)
class TrueFalseItem:
    """Affirmation vrai/faux justifiée.

    Attributes:
        statement: Affirmation à évaluer.
        is_true: ``True`` si l'affirmation est vraie.
        justification: Explication.
        source_ref: Référence d'origine.
    """

    statement: str
    is_true: bool
    justification: str
    source_ref: str


@dataclass(frozen=True)
class ClozeItem:
    """Texte à trous.

    Attributes:
        text: Texte avec marqueurs de trous (``___``).
        answers: Réponses attendues, dans l'ordre des trous (non vide).
        source_ref: Référence d'origine.
    """

    text: str
    answers: tuple[str, ...]
    source_ref: str

    def __post_init__(self) -> None:
        if not self.answers:
            raise ValueError("answers must contain at least one answer")


@dataclass(frozen=True)
class OpenQuestion:
    """Question ouverte avec éléments de réponse attendus.

    Attributes:
        question: Énoncé.
        expected_points: Points clés attendus dans la réponse.
        source_ref: Référence d'origine.
    """

    question: str
    expected_points: tuple[str, ...]
    source_ref: str


@dataclass(frozen=True)
class RevisionSheet:
    """Fiche de révision d'un chapitre.

    Attributes:
        chapter_title: Titre du chapitre.
        summary_markdown: Synthèse Markdown du chapitre.
        source_ref: Référence d'origine.
    """

    chapter_title: str
    summary_markdown: str
    source_ref: str


@dataclass(frozen=True)
class KeyPoints:
    """Points clés d'un chapitre.

    Attributes:
        chapter_title: Titre du chapitre.
        points: Puces (idées clés).
        source_ref: Référence d'origine.
    """

    chapter_title: str
    points: tuple[str, ...]
    source_ref: str


@dataclass(frozen=True)
class MockExamSection:
    """Section d'un examen blanc.

    Attributes:
        title: Titre de la section.
        statement_markdown: Énoncé Markdown de la section.
    """

    title: str
    statement_markdown: str


@dataclass(frozen=True)
class MockExam:
    """Examen blanc composite.

    Attributes:
        title: Titre de l'examen.
        sections: Sections (énoncés).
        grading_markdown: Barème / corrigé Markdown.
    """

    title: str
    sections: tuple[MockExamSection, ...]
    grading_markdown: str


#: Union des entités structurées portées par un ``SupportArtifact``.
SupportItem = (
    Flashcard
    | QcmItem
    | TrueFalseItem
    | ClozeItem
    | OpenQuestion
    | RevisionSheet
    | KeyPoints
    | MockExam
)


@dataclass(frozen=True)
class SupportArtifact:
    """Enveloppe unifiée d'un support généré (écrite en JSON + Markdown).

    Attributes:
        support_type: Type de support.
        language: Langue du support.
        items: Entités structurées (cartes, questions…).
        rendered_markdown: Rendu Markdown lisible du support (sujet).
        correction_markdown: Corrigé séparé Markdown, ou ``None`` si le support
            n'est pas évaluatif ou si le corrigé est intégré au rendu.
        cost_usd: Coût LLM de génération (0.0 pour les supports sans LLM).
    """

    support_type: SupportType
    language: Language
    items: tuple[SupportItem, ...]
    rendered_markdown: str
    correction_markdown: str | None = None
    cost_usd: float = 0.0

    def __post_init__(self) -> None:
        if self.cost_usd < 0:
            raise ValueError(f"cost_usd must be >= 0, got {self.cost_usd}")
