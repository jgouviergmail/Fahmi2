"""Énumérations stables du domaine Fahmi2."""

from __future__ import annotations

from enum import StrEnum


class Language(StrEnum):
    """Langues supportées en v1 (entrée et sortie)."""

    FR = "fr"
    EN = "en"


class StylePreset(StrEnum):
    """Style de rendu de la reformulation."""

    DECONTRACTE = "decontracte"
    STANDARD = "standard"
    PROFESSIONNEL = "professionnel"
    ACADEMIQUE = "academique"


class PhaseId(StrEnum):
    """Identifiants stables des phases du pipeline."""

    STT = "phase_0_stt"
    TERM_EXTRACTION = "phase_1_term_extraction"
    GLOSSARY_RECONCILIATION = "phase_2_glossary_reconciliation"
    REFORMULATION = "phase_3_reformulation"
    STRUCTURATION = "phase_4_structuration"
    CONSOLIDATION = "phase_5_consolidation"
    TRANSLATION = "phase_6_translation"
    COHERENCE = "phase_7_coherence"


class RunStatus(StrEnum):
    """État global d'un Run."""

    CREATED = "created"
    RUNNING = "running"
    PAUSED = "paused"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    FAILED = "failed"


class PhaseStatus(StrEnum):
    """État d'exécution d'une phase (pour une vidéo ou pour le batch)."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"


class SttProvider(StrEnum):
    """Providers de speech-to-text supportés."""

    FASTER_WHISPER_LOCAL = "faster_whisper_local"
    OPENAI_CLOUD = "openai_cloud"


class LLMModel(StrEnum):
    """Modèles DeepSeek supportés."""

    DEEPSEEK_V4_FLASH = "deepseek-v4-flash"
    DEEPSEEK_V4_PRO = "deepseek-v4-pro"
