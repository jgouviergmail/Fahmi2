"""Énumérations stables du domaine Fahmi2."""

from __future__ import annotations

from enum import StrEnum


class Language(StrEnum):
    """Langues supportées (entrée et sortie)."""

    FR = "fr"
    EN = "en"
    DE = "de"
    ES = "es"
    IT = "it"
    ZH = "zh"
    AR = "ar"


class StylePreset(StrEnum):
    """Style de rendu de la reformulation."""

    DECONTRACTE = "decontracte"
    STANDARD = "standard"
    PROFESSIONNEL = "professionnel"
    ACADEMIQUE = "academique"


class ConsolidationMode(StrEnum):
    """Mode d'assemblage du document consolidé (phase 5).

    ``ORDERED`` (défaut) : 1 source = 1 chapitre, contenu recopié dans l'ordre
    choisi. ``THEMATIC`` : refonte thématique transversale — le LLM agrège et
    structure les contenus de tous les entrants (rigueur sur le fond, souplesse
    sur la forme).
    """

    ORDERED = "ordered"
    THEMATIC = "thematic"


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
    """État d'exécution d'une phase (pour une source ou pour le batch)."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"


class SourceKind(StrEnum):
    """Origine d'une source d'entrée de la génération."""

    VIDEO = "video"
    AUDIO = "audio"
    DOCUMENT = "document"
    YOUTUBE = "youtube"


class SttProvider(StrEnum):
    """Providers de speech-to-text supportés."""

    FASTER_WHISPER_LOCAL = "faster_whisper_local"
    OPENAI_CLOUD = "openai_cloud"


class LocalSttModel(StrEnum):
    """Modèles faster-whisper locaux (téléchargés au 1er usage, mis en cache).

    Identifiants reconnus par ``faster_whisper.WhisperModel`` (résolus vers les
    dépôts Hugging Face). Aucun poids n'est packagé : le modèle sélectionné est
    téléchargé à sa première utilisation dans ``%LOCALAPPDATA%/Fahmi2/models/``.
    """

    LARGE_V3_TURBO = "large-v3-turbo"  # défaut : équilibre vitesse/qualité
    LARGE_V3 = "large-v3"              # précision maximale (plus lent, + VRAM)
    MEDIUM = "medium"                  # plus léger/rapide, VRAM réduite
    SMALL = "small"                    # le plus rapide, faible VRAM, qualité moindre


class CloudSttModel(StrEnum):
    """Modèles de transcription cloud OpenAI.

    ``whisper-1`` renvoie des **segments horodatés** (``verbose_json``) ; les
    modèles ``gpt-4o-*-transcribe`` ne renvoient que du texte (``json``), sans
    timestamps de segments (l'adapter produit alors un segment unique par tranche
    audio, le contenu transcrit restant identique).
    """

    WHISPER_1 = "whisper-1"                          # défaut : timestamps fins
    GPT_4O_TRANSCRIBE = "gpt-4o-transcribe"          # précision supérieure
    GPT_4O_MINI_TRANSCRIBE = "gpt-4o-mini-transcribe"  # 2× moins cher


class LLMModel(StrEnum):
    """Modèles DeepSeek supportés."""

    DEEPSEEK_V4_FLASH = "deepseek-v4-flash"
    DEEPSEEK_V4_PRO = "deepseek-v4-pro"


class EmbeddingModel(StrEnum):
    """Modèles d'embedding OpenAI supportés (retrieval sémantique du Dialogue).

    Le retrieval **lexical** n'en consomme aucun ; en mode cloud (``AUTO`` ou
    ``SEMANTIC``), l'utilisateur choisit le compromis coût/précision. Changer de
    modèle modifie l'empreinte de l'index, ce qui force une **réindexation**.
    """

    TEXT_EMBEDDING_3_SMALL = "text-embedding-3-small"  # défaut : économique
    TEXT_EMBEDDING_3_LARGE = "text-embedding-3-large"  # précision supérieure
    TEXT_EMBEDDING_ADA_002 = "text-embedding-ada-002"  # génération précédente


class ReasoningEffort(StrEnum):
    """Niveau d'effort de raisonnement (DeepSeek ``reasoning_effort``).

    Utilisé conjointement à ``thinking_enabled`` : si le thinking est désactivé,
    ce champ est ignoré et n'est pas envoyé à l'API.
    """

    HIGH = "high"
    MAX = "max"


class SupportType(StrEnum):
    """Types de supports de révision générables."""

    FLASHCARDS_CONCEPTS = "flashcards_concepts"
    QCM = "qcm"
    TRUE_FALSE = "true_false"
    CLOZE = "cloze"
    OPEN_QUESTIONS = "open_questions"
    REVISION_SHEET = "revision_sheet"
    KEY_POINTS = "key_points"
    MOCK_EXAM = "mock_exam"


class TargetAudience(StrEnum):
    """Public cible des supports (règle l'exigence et le registre)."""

    DISCOVERY = "discovery"
    HIGH_SCHOOL = "high_school"
    LICENCE = "licence"
    MASTER_EXPERT = "master_expert"


class BloomObjective(StrEnum):
    """Objectif cognitif (taxonomie de Bloom, regroupements simples)."""

    AUTO = "auto"
    RESTITUTE = "restitute"
    UNDERSTAND_APPLY = "understand_apply"
    ANALYZE_BEYOND = "analyze_beyond"


class SupportDensity(StrEnum):
    """Densité (volume) des supports générés."""

    LIGHT = "light"
    STANDARD = "standard"
    DENSE = "dense"


class ExportFormat(StrEnum):
    """Formats d'export des supports."""

    APKG = "apkg"
    MARKDOWN = "markdown"
    PDF = "pdf"
    HTML = "html"
    DOCX = "docx"


class ChatGroundingMode(StrEnum):
    """Posture de fidélité des réponses du chat de dialogue."""

    STRICT = "strict"        # uniquement le corpus, citations, refus hors-corpus
    AUGMENTED = "augmented"  # corpus prioritaire + complément balisé


class RetrievalStrategy(StrEnum):
    """Stratégie de récupération des passages du corpus."""

    AUTO = "auto"            # défaut : sémantique si clé OpenAI dispo, sinon lexical
    LEXICAL = "lexical"      # TF-IDF (+ query expansion), 100% offline
    SEMANTIC = "semantic"    # embeddings OpenAI


class ChatTabState(StrEnum):
    """États de l'onglet Dialogue (machine UX, cf. spec §10.1)."""

    NO_PROJECT = "no_project"
    NO_CORPUS = "no_corpus"
    READY = "ready"
    ANSWERING = "answering"
    ERROR = "error"
