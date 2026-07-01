"""Entités de la fonctionnalité Génération : ``GenerationSettings``, ``ParallelismConfig``.

``GenerationSettings`` regroupe tous les paramètres métier de la génération (vidéos →
document consolidé). Le nom et l'emplacement du projet n'en font **pas** partie : ils
sont portés par ``Project`` (identité minimale, cf. ``domain.project``).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from fahmi2.domain.enums import (
    CloudSttModel,
    ConsolidationMode,
    ExportFormat,
    Language,
    LLMModel,
    LocalSttModel,
    PhaseId,
    SttProvider,
    StylePreset,
    VisionModel,
)
from fahmi2.domain.phase import PhaseConfig

_DEFAULT_STT_CLOUD_WORKERS = 3
_DEFAULT_LLM_WORKERS = 16

#: Bornes hautes proposées dans l'UI. La limite DeepSeek est par concurrence
#: (très au-dessus), donc le LLM peut monter haut ; OpenAI Whisper (STT cloud) a
#: de vraies limites RPM → borne plus basse.
MAX_STT_CLOUD_WORKERS = 8
MAX_LLM_WORKERS = 64
_LLM_PHASES: frozenset[PhaseId] = frozenset(
    p for p in PhaseId if p is not PhaseId.STT
)

#: Sous-dossier du workspace dédié aux artefacts de la fonctionnalité Génération.
GENERATION_WORKSPACE_SUBDIR = "generation"

#: Sous-dossier des livrables finaux de la génération (sous le dossier feature).
GENERATION_OUTPUT_SUBDIR = "output"


def consolidated_doc_filename(language: Language) -> str:
    """Nom de fichier du document consolidé pour une langue.

    Args:
        language: Langue cible.

    Returns:
        Le nom de fichier (ex: ``"consolidated.fr.md"``).
    """
    return f"consolidated.{language}.md"


def glossary_doc_filename(language: Language) -> str:
    """Nom de fichier du glossaire pour une langue.

    Args:
        language: Langue cible.

    Returns:
        Le nom de fichier (ex: ``"glossary.fr.md"``).
    """
    return f"glossary.{language}.md"


#: Formats d'export documentaire autorisés en génération (pas d'APKG : pas de cartes).
GENERATION_EXPORT_FORMATS: frozenset[ExportFormat] = frozenset(
    {ExportFormat.MARKDOWN, ExportFormat.PDF, ExportFormat.HTML, ExportFormat.DOCX}
)

#: Formats cochés par défaut pour un nouveau projet (vide = opt-in).
DEFAULT_GENERATION_EXPORT_FORMATS: frozenset[ExportFormat] = frozenset()


@dataclass(frozen=True)
class ParallelismConfig:
    """Configuration de parallélisme du pipeline.

    Note:
        STT local est toujours séquentiel (1 GPU). Seuls STT cloud et LLM sont
        parallélisables.

    Attributes:
        stt_cloud_workers: Workers concurrents pour le STT cloud (>= 1).
        llm_workers: Workers concurrents pour les appels LLM (>= 1).
    """

    stt_cloud_workers: int = _DEFAULT_STT_CLOUD_WORKERS
    llm_workers: int = _DEFAULT_LLM_WORKERS

    def __post_init__(self) -> None:
        if self.stt_cloud_workers < 1:
            raise ValueError("stt_cloud_workers must be >= 1")
        if self.llm_workers < 1:
            raise ValueError("llm_workers must be >= 1")


@dataclass(frozen=True)
class GenerationSettings:
    """Paramètres de la fonctionnalité Génération (vidéos → document consolidé).

    Les phases LLM (1..7) doivent toutes être configurées dans ``phases_config``.
    ``output_languages`` doit toujours contenir ``source_language``.

    Attributes:
        input_folder: Dossier d'entrée contenant les vidéos.
        source_language: Langue source du contenu.
        output_languages: Tuple des langues de sortie demandées.
        style_preset: Style de rendu.
        style_directives: Directives stylistiques libres (peuvent être vides).
        stt_provider: Provider STT (local ou cloud).
        stt_local_model: Modèle faster-whisper utilisé en STT local.
        stt_cloud_model: Modèle de transcription OpenAI utilisé en STT cloud.
        llm_model: Modèle DeepSeek utilisé.
        phases_config: Configuration des phases LLM 1..7.
        cost_ceiling_usd: Plafond de coût (``None`` = pas de plafond).
        parallelism: Configuration de parallélisme.
        delete_audio_after_stt: Si ``True``, l'audio extrait est supprimé après STT.
        export_formats: Formats d'export documentaire (sous-ensemble de
            {MARKDOWN, PDF, HTML} ; vide par défaut = opt-in).
        reformulate_documents: Si ``True`` (défaut), les documents texte passent
            par la reformulation (phase 3) comme une transcription ; sinon ils
            sont insérés tels quels (pass-through, structure préservée).
        youtube_urls: Liens YouTube **unitaires** à traiter (ajoutés aux sources
            après les fichiers du dossier d'entrée).
        source_order: Clés stables (``InputSource.order_key()`` : nom de fichier
            ou URL) des sources **incluses**, dans l'ordre de traitement souhaité.
        excluded_sources: Clés stables des sources **exclues** (présentes mais
            non traitées).
        slides_sources: Clés stables (``InputSource.order_key()``) des sources
            vidéo/YouTube dont l'analyse des slides est activée (contenu des
            slides intercalé dans la transcription, phase 0). Réconciliées au
            scan comme ``excluded_sources`` (clés obsolètes ignorées).
        vision_model: Modèle vision OpenAI utilisé pour lire les slides.
        delete_frames_after_analysis: Si ``True`` (défaut), les images de
            slides extraites sont supprimées après analyse ; sinon les images
            **représentatives** (une par slide) sont conservées dans
            ``frames/<source>/`` (visualisation / dépannage, miroir de
            ``delete_audio_after_stt``).
        consolidation_mode: Mode d'assemblage du consolidé (phase 5).
            ``ORDERED`` (défaut) : 1 source = 1 chapitre dans l'ordre choisi.
            ``THEMATIC`` : refonte thématique transversale par le LLM (en ce mode,
            ``source_order`` n'a pas d'effet et ``reformulate_documents`` est
            ignoré — tout entrant est matière première).
    """

    input_folder: Path
    source_language: Language
    output_languages: tuple[Language, ...]
    style_preset: StylePreset
    style_directives: str
    stt_provider: SttProvider
    llm_model: LLMModel
    phases_config: dict[PhaseId, PhaseConfig]
    cost_ceiling_usd: float | None
    parallelism: ParallelismConfig
    delete_audio_after_stt: bool
    stt_local_model: LocalSttModel = LocalSttModel.LARGE_V3_TURBO
    stt_cloud_model: CloudSttModel = CloudSttModel.WHISPER_1
    export_formats: frozenset[ExportFormat] = DEFAULT_GENERATION_EXPORT_FORMATS
    reformulate_documents: bool = True
    youtube_urls: tuple[str, ...] = ()
    source_order: tuple[str, ...] = ()
    excluded_sources: tuple[str, ...] = ()
    slides_sources: tuple[str, ...] = ()
    vision_model: VisionModel = VisionModel.GPT_5_MINI
    delete_frames_after_analysis: bool = True
    consolidation_mode: ConsolidationMode = ConsolidationMode.ORDERED

    def __post_init__(self) -> None:
        if not self.output_languages:
            raise ValueError("output_languages must contain at least one language")
        if self.source_language not in self.output_languages:
            raise ValueError(
                f"output_languages must contain source_language "
                f"({self.source_language})"
            )
        configured = set(self.phases_config)
        expected = set(_LLM_PHASES)
        if configured != expected:
            missing = sorted(expected - configured)
            extra = sorted(configured - expected)
            raise ValueError(
                "phases_config must cover exactly LLM phases (1..7). "
                f"Missing: {missing}, Extra: {extra}"
            )
        if self.cost_ceiling_usd is not None and self.cost_ceiling_usd < 0:
            raise ValueError(
                f"cost_ceiling_usd must be >= 0 or None, got {self.cost_ceiling_usd}"
            )
        if not self.export_formats <= GENERATION_EXPORT_FORMATS:
            invalid = sorted(
                f.value for f in self.export_formats - GENERATION_EXPORT_FORMATS
            )
            allowed = sorted(f.value for f in GENERATION_EXPORT_FORMATS)
            raise ValueError(
                f"export_formats must be a subset of {allowed}; "
                f"got invalid: {invalid}"
            )

    def effective_slides_sources(self) -> tuple[str, ...]:
        """Clés « analyser les slides » réellement actives (hors exclues).

        L'état coché d'une source **exclue** est conservé (pour une future
        réinclusion) mais ne doit déclencher ni exigence de clé OpenAI ni
        construction de l'analyseur.

        Returns:
            Les clés de ``slides_sources`` non présentes dans
            ``excluded_sources``, dans l'ordre d'origine.
        """
        excluded = set(self.excluded_sources)
        return tuple(key for key in self.slides_sources if key not in excluded)
