"""Helpers communs aux handlers de phase LLM.

Mutualise :

- L'appel au ``LLMProvider`` avec la ``PhaseConfig`` de la phase courante.
- La construction des labels lisibles (style, langue) pour les prompts.
- Le parsing des réponses JSON avec mapping d'erreur typée.
- La construction d'un ``PhaseExecution`` final cohérent.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from types import MappingProxyType
from typing import Any

from fahmi2.core.errors.exceptions import StorageError
from fahmi2.core.errors.severity import Severity
from fahmi2.domain.enums import Language, PhaseId, PhaseStatus, StylePreset
from fahmi2.domain.ids import SourceId
from fahmi2.domain.languages import language_label as _language_label
from fahmi2.domain.phase import PhaseExecution
from fahmi2.infra.llm.interface import LLMResponse
from fahmi2.infra.llm.invocation import invoke_llm_chat, parse_llm_json
from fahmi2.pipeline.phase_handler import PhaseContext
from fahmi2.pipeline.workspace_layout import (
    glossary_master_path,
    reformulated_path,
    transcript_path,
)

_STYLE_LABELS_FR: dict[StylePreset, str] = {
    StylePreset.DECONTRACTE: "décontracté",
    StylePreset.STANDARD: "standard",
    StylePreset.PROFESSIONNEL: "professionnel",
    StylePreset.ACADEMIQUE: "académique",
}

#: Nombre maximal de termes du glossaire injectés en contexte LLM (phases 3, 4).
#: Choisi pour garder le prompt court tout en couvrant les termes pertinents
#: d'un chapitre type. Source unique partagée entre les handlers concernés.
DEFAULT_TOP_K_GLOSSARY = 30


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
    response_format: dict[str, str] | None = None,
) -> LLMResponse:
    """Appelle le ``LLMProvider`` avec la ``PhaseConfig`` propre à ``phase_id``.

    Le plafond de tokens de sortie (anti-troncature) est celui de ``invoke_llm_chat``
    (``DEFAULT_MAX_OUTPUT_TOKENS``) — source unique partagée avec la pédagogie.

    Args:
        ctx: Contexte d'exécution.
        phase_id: Phase courante (sert à lire ``phases_config[phase_id]``).
        system_prompt: Prompt système optionnel.
        user_prompt: Prompt utilisateur (corps de la requête).
        response_format: Contrainte de format provider (cf.
            ``invoke_llm_chat``). À passer
            ``JSON_OBJECT_RESPONSE_FORMAT`` pour toute phase dont la sortie est
            destinée à ``parse_json_response``.

    Returns:
        ``LLMResponse``.
    """
    return invoke_llm_chat(
        ctx.llm_provider,
        model=str(ctx.settings.llm_model),
        config=ctx.settings.phases_config[phase_id],
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        response_format=response_format,
    )


def parse_json_response(
    content: str,
    *,
    phase_id: PhaseId,
    finish_reason: str | None = None,
) -> Any:  # noqa: ANN401
    """Parse une réponse LLM JSON (délègue à ``parse_llm_json``).

    Args:
        content: Contenu textuel de la réponse LLM.
        phase_id: Phase courante (pour le message d'erreur).
        finish_reason: Raison de fin de génération du provider
            (``LLMResponse.finish_reason``). Reportée dans les
            ``technical_details`` de ``LLM.INVALID_JSON`` quand fournie ; aide
            à discriminer une réponse tronquée (``"length"``, etc.) d'une
            réponse complète mais malformée (``"stop"``).

    Returns:
        L'objet Python décodé.

    Raises:
        LLMError: ``LLM.INVALID_JSON`` si le contenu n'est pas du JSON valide.
    """
    return parse_llm_json(
        content, context_label=phase_id.value, finish_reason=finish_reason
    )


def build_succeeded_phase(
    *,
    phase_id: PhaseId,
    artifact_path: Path,
    started_at: datetime,
    cost_usd: float,
    per_source_costs: Mapping[SourceId, float] | None = None,
) -> PhaseExecution:
    """Construit une ``PhaseExecution`` SUCCEEDED standard.

    Args:
        phase_id: Phase.
        artifact_path: Chemin de l'artefact produit.
        started_at: Timestamp de début.
        cost_usd: Coût cumulé total (per-source attribué + résidu batch).
        per_source_costs: Ventilation per-source optionnelle (phases batch
            mixtes — phase 5 fact-ledger / video-summary, phase 6 traduction
            per source × langue). ``None`` = pas de ventilation (phase per-
            source pure ou batch pur). Le mapping est gelé en
            ``MappingProxyType`` à la construction.

    Returns:
        Une ``PhaseExecution`` finalisée.
    """
    frozen = (
        MappingProxyType(dict(per_source_costs))
        if per_source_costs is not None
        else MappingProxyType({})
    )
    return PhaseExecution(
        phase_id=phase_id,
        status=PhaseStatus.SUCCEEDED,
        started_at=started_at,
        finished_at=datetime.now(tz=UTC),
        artifact_path=artifact_path,
        cost_usd=cost_usd,
        per_source_costs=frozen,
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
    master_path = glossary_master_path(workspace)
    if not master_path.exists():
        return []
    payload = json.loads(master_path.read_text(encoding="utf-8"))
    terms = payload.get("terms", [])
    return [dict(t) for t in terms]


def load_transcription_text(workspace: Path, source_id: str) -> str:
    """Charge le texte complet d'une transcription persistée (phase 0).

    Source unique partagée par les handlers qui consomment la transcription
    brute (phases 1 et 3). Le texte de tous les segments est concaténé par
    une espace ; un document non STT (segment unique préservant la structure)
    revient donc tel quel.

    Args:
        workspace: Dossier de travail du run.
        source_id: ULID de la source.

    Returns:
        Le texte concaténé de tous les segments.

    Raises:
        StorageError: ``STORAGE.TRANSCRIPT_MISSING`` si le fichier n'existe pas.
    """
    path = transcript_path(workspace, source_id)
    if not path.exists():
        raise StorageError(
            code="STORAGE.TRANSCRIPT_MISSING",
            user_message=(
                f"La transcription pour {source_id} est introuvable. "
                "Relance la phase STT."
            ),
            severity=Severity.ERROR,
            technical_details={"path": str(path)},
        )
    payload = json.loads(path.read_text(encoding="utf-8"))
    segments = payload.get("segments", [])
    return " ".join(str(s.get("text", "")) for s in segments)


def load_reformulated_text(workspace: Path, source_id: str) -> str:
    """Charge le contenu reformulé d'une source (phase 3).

    Source unique partagée par les handlers qui consomment l'artefact de la
    phase 3 (typiquement la phase 4 de structuration).

    Args:
        workspace: Dossier de travail du run.
        source_id: ULID de la source.

    Returns:
        Le contenu Markdown reformulé.

    Raises:
        StorageError: ``STORAGE.REFORMULATED_MISSING`` si le fichier n'existe pas.
    """
    path = reformulated_path(workspace, source_id)
    if not path.exists():
        raise StorageError(
            code="STORAGE.REFORMULATED_MISSING",
            user_message=(
                f"Le contenu reformulé pour {source_id} est introuvable. "
                "Relance la phase de reformulation."
            ),
            severity=Severity.ERROR,
            technical_details={"path": str(path)},
        )
    return path.read_text(encoding="utf-8")


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
