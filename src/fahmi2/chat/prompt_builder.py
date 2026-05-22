"""Assemblage des messages LLM du chat (système + historique + question).

Le prompt système (strict ou augmenté) embarque les passages numérotés du corpus
et le glossaire pertinent. Un garde-fou élague l'historique le plus ancien si le
budget de contexte est dépassé (fenêtre glissante, cf. spec §10.3).
"""

from __future__ import annotations

from fahmi2.core.text_metrics import estimate_tokens
from fahmi2.domain.chat import ChatMessage, ChatSettings, RetrievedPassage
from fahmi2.domain.enums import ChatGroundingMode, Language
from fahmi2.infra.llm.interface import Message
from fahmi2.infra.prompts.loader import PromptLoader
from fahmi2.pedagogy.labels import language_label

_PROMPT_STRICT = "chat_strict"
_PROMPT_AUGMENTED = "chat_augmented"
_MAX_HISTORY_TOKENS = 100_000  # garde-fou : fenêtre glissante au-delà (cf. §10.3)
_PASSAGE_HEADER = "§{n} — {chapter} › {section}"

_PROMPT_BY_MODE = {
    ChatGroundingMode.STRICT: _PROMPT_STRICT,
    ChatGroundingMode.AUGMENTED: _PROMPT_AUGMENTED,
}


def format_passages(passages: tuple[RetrievedPassage, ...]) -> str:
    """Formate les passages récupérés en bloc numéroté (§1, §2, …).

    Args:
        passages: Passages récupérés, dans l'ordre de pertinence.

    Returns:
        Bloc texte numéroté pour injection dans le prompt système.
    """
    blocks: list[str] = []
    for index, passage in enumerate(passages, start=1):
        chunk = passage.chunk
        header = _PASSAGE_HEADER.format(
            n=index, chapter=chunk.chapter_title, section=chunk.section_title
        )
        blocks.append(f"{header}\n{chunk.text}")
    return "\n\n".join(blocks)


def truncate_history(
    history: tuple[ChatMessage, ...], *, max_tokens: int = _MAX_HISTORY_TOKENS
) -> tuple[ChatMessage, ...]:
    """Conserve les tours les plus récents tenant dans ``max_tokens`` (estimé).

    Args:
        history: Historique complet (du plus ancien au plus récent).
        max_tokens: Budget de tokens estimé pour l'historique injecté.

    Returns:
        Sous-suite **suffixe** (tours récents) tenant dans le budget.
    """
    kept: list[ChatMessage] = []
    total = 0
    for message in reversed(history):
        total += estimate_tokens(message.content)
        if total > max_tokens and kept:
            break
        kept.append(message)
    kept.reverse()
    return tuple(kept)


def build_chat_messages(
    *,
    question: str,
    passages: tuple[RetrievedPassage, ...],
    glossary_text: str,
    history: tuple[ChatMessage, ...],
    settings: ChatSettings,
    language: Language,
    prompt_loader: PromptLoader,
) -> list[Message]:
    """Assemble la liste de messages LLM (système + historique + question).

    Args:
        question: Question de l'utilisateur.
        passages: Passages récupérés à citer.
        glossary_text: Glossaire pertinent déjà formaté (vide si aucun).
        history: Historique de la conversation (hors question courante).
        settings: Réglages du chat (mode de fidélité).
        language: Langue de réponse.
        prompt_loader: Loader de templates (override > défaut).

    Returns:
        Liste ordonnée de ``Message`` prête pour ``LLMProvider``.
    """
    system_prompt = prompt_loader.render(
        _PROMPT_BY_MODE[settings.grounding_mode],
        output_language_label=language_label(language),
        glossary_terms=glossary_text,
        passages=format_passages(passages),
    )
    messages: list[Message] = [Message(role="system", content=system_prompt)]
    for message in truncate_history(history):
        messages.append(Message(role=message.role, content=message.content))
    messages.append(Message(role="user", content=question))
    return messages
