"""Helpers communs aux handlers de phase LLM.

Mutualise :

- L'appel au ``LLMProvider`` avec la ``PhaseConfig`` de la phase courante.
- La construction des labels lisibles (style, langue) pour les prompts.
- Le parsing des réponses JSON avec mapping d'erreur typée.
- La construction d'un ``PhaseExecution`` final cohérent.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fahmi2.domain.enums import Language, PhaseId, PhaseStatus, StylePreset
from fahmi2.domain.languages import language_label as _language_label
from fahmi2.domain.phase import PhaseExecution
from fahmi2.infra.llm.interface import LLMResponse
from fahmi2.infra.llm.invocation import invoke_llm_chat, parse_llm_json
from fahmi2.pipeline.phase_handler import PhaseContext

_STYLE_LABELS_FR: dict[StylePreset, str] = {
    StylePreset.DECONTRACTE: "décontracté",
    StylePreset.STANDARD: "standard",
    StylePreset.PROFESSIONNEL: "professionnel",
    StylePreset.ACADEMIQUE: "académique",
}


def style_label(style: StylePreset) -> str:
    """Libellé humain (FR) d'un ``StylePreset``.

    Args:
        style: Style preset.

    Returns:
        Le libellé (ex: ``"décontracté"``).
    """
    return _STYLE_LABELS_FR[style]


def language_label(language: Language) -> str:
    """Libellé humain (FR, minuscule) d'une ``Language``.

    Délègue à la source unique ``domain.languages`` (ré-export pour compat des
    handlers qui importent ``language_label`` depuis ce module).

    Args:
        language: Langue.

    Returns:
        Le libellé (ex: ``"français"``).
    """
    return _language_label(language)


def invoke_llm(
    ctx: PhaseContext,
    *,
    phase_id: PhaseId,
    system_prompt: str | None,
    user_prompt: str,
) -> LLMResponse:
    """Appelle le ``LLMProvider`` avec la ``PhaseConfig`` propre à ``phase_id``.

    Le plafond de tokens de sortie (anti-troncature) est celui de ``invoke_llm_chat``
    (``DEFAULT_MAX_OUTPUT_TOKENS``) — source unique partagée avec la pédagogie.

    Args:
        ctx: Contexte d'exécution.
        phase_id: Phase courante (sert à lire ``phases_config[phase_id]``).
        system_prompt: Prompt système optionnel.
        user_prompt: Prompt utilisateur (corps de la requête).

    Returns:
        ``LLMResponse``.
    """
    return invoke_llm_chat(
        ctx.llm_provider,
        model=str(ctx.settings.llm_model),
        config=ctx.settings.phases_config[phase_id],
        system_prompt=system_prompt,
        user_prompt=user_prompt,
    )


def parse_json_response(content: str, *, phase_id: PhaseId) -> Any:  # noqa: ANN401
    """Parse une réponse LLM JSON (délègue à ``parse_llm_json``).

    Args:
        content: Contenu textuel de la réponse LLM.
        phase_id: Phase courante (pour le message d'erreur).

    Returns:
        L'objet Python décodé.

    Raises:
        LLMError: ``LLM.INVALID_JSON`` si le contenu n'est pas du JSON valide.
    """
    return parse_llm_json(content, context_label=phase_id.value)


def build_succeeded_phase(
    *,
    phase_id: PhaseId,
    artifact_path: Path,
    started_at: datetime,
    cost_usd: float,
) -> PhaseExecution:
    """Construit une ``PhaseExecution`` SUCCEEDED standard.

    Args:
        phase_id: Phase.
        artifact_path: Chemin de l'artefact produit.
        started_at: Timestamp de début.
        cost_usd: Coût cumulé.

    Returns:
        Une ``PhaseExecution`` finalisée.
    """
    return PhaseExecution(
        phase_id=phase_id,
        status=PhaseStatus.SUCCEEDED,
        started_at=started_at,
        finished_at=datetime.now(tz=UTC),
        artifact_path=artifact_path,
        cost_usd=cost_usd,
    )


def utc_now() -> datetime:
    """Retourne l'horodatage UTC courant.

    Returns:
        ``datetime`` UTC aware.
    """
    return datetime.now(tz=UTC)


def load_glossary_master(workspace: Path) -> list[dict[str, Any]]:
    """Charge le glossaire master produit par la phase 2.

    Args:
        workspace: Dossier de travail du run.

    Returns:
        Liste des termes (dict). Liste vide si le master n'existe pas encore.
    """
    master_path = workspace / "glossary_master.json"
    if not master_path.exists():
        return []
    payload = json.loads(master_path.read_text(encoding="utf-8"))
    terms = payload.get("terms", [])
    return [dict(t) for t in terms]


def select_top_glossary_terms(
    master_terms: list[dict[str, Any]],
    *,
    query: str,
    retriever: Any,  # noqa: ANN401 — Protocol GlossaryRetriever
    top_k: int,
) -> list[dict[str, Any]]:
    """Sélectionne les ``top_k`` termes du glossaire master pertinents à ``query``.

    Args:
        master_terms: Termes du glossaire master.
        query: Texte de référence.
        retriever: ``GlossaryRetriever``.
        top_k: Borne supérieure.

    Returns:
        Sous-liste des termes (mêmes dicts que ``master_terms``).
    """
    if not master_terms:
        return []
    term_strings = [str(t["term"]) for t in master_terms]
    ranked = retriever.retrieve(query=query, terms=term_strings, top_k=top_k)
    by_term = {str(t["term"]): t for t in master_terms}
    return [by_term[r] for r in ranked if r in by_term]
