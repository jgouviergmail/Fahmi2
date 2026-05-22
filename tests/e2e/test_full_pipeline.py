"""Test E2E du pipeline complet (8 phases) avec STT et LLM fakes.

Vérifie le happy path : un Run sur 2 vidéos courtes, langues source FR +
sortie FR + EN, produit tous les artefacts attendus dans ``output_dir``.

ffmpeg est utilisé pour de vrai (extraction audio depuis un MP4 généré à la
volée), tandis que STT et LLM sont mockés via les ``Fake*Provider``.
"""

from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from fahmi2.app.project_service import ProjectService
from fahmi2.app.run_orchestrator import RunOrchestrator
from fahmi2.core.retrieval.interface import PassthroughRetriever
from fahmi2.core.retry.policy import RetryPolicy
from fahmi2.domain.enums import Language, RunStatus
from fahmi2.infra.audio.ffmpeg_extractor import FFmpegExtractor
from fahmi2.infra.llm._fakes import FakeLLMProvider
from fahmi2.infra.llm.interface import LLMResponse
from fahmi2.infra.prompts.loader import PromptLoader
from fahmi2.infra.storage.fs_artifacts import FsArtifactStore
from fahmi2.infra.storage.sqlite_state import SqliteState
from fahmi2.infra.stt._fakes import FakeSTTProvider
from fahmi2.infra.stt.interface import Transcription, TranscriptionSegment
from fahmi2.pipeline.engine import PipelineEngine
from fahmi2.pipeline.event_bus import EventBus
from fahmi2.pipeline.handlers.phase_0_stt import Phase0SttHandler
from fahmi2.pipeline.handlers.phase_1_term_extraction import (
    Phase1TermExtractionHandler,
)
from fahmi2.pipeline.handlers.phase_2_glossary_reconciliation import (
    Phase2GlossaryReconciliationHandler,
)
from fahmi2.pipeline.handlers.phase_3_reformulation import Phase3ReformulationHandler
from fahmi2.pipeline.handlers.phase_4_structuration import Phase4StructurationHandler
from fahmi2.pipeline.handlers.phase_5_consolidation import Phase5ConsolidationHandler
from fahmi2.pipeline.handlers.phase_6_translation import Phase6TranslationHandler
from fahmi2.pipeline.handlers.phase_7_coherence import Phase7CoherenceHandler
from fahmi2.pipeline.pause_token import PauseToken
from fahmi2.pipeline.phase_handler import PhaseContext
from fahmi2.pipeline.phase_registry import PhaseRegistry


def _generate_mp4(out: Path, duration: float = 1.0) -> None:
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"sine=frequency=440:duration={duration}",
            "-f", "lavfi", "-i", f"testsrc=duration={duration}:size=64x48:rate=10",
            "-c:a", "aac", "-c:v", "libx264", "-shortest",
            "-loglevel", "error", str(out),
        ],
        check=True,
        capture_output=True,
    )


@pytest.fixture(scope="module")
def e2e_input_folder(
    tmp_path_factory: pytest.TempPathFactory,
) -> Path:
    folder = tmp_path_factory.mktemp("e2e_input")
    _generate_mp4(folder / "video_01.mp4")
    _generate_mp4(folder / "video_02.mp4")
    return folder


def _llm_response_for_phase(phase_name: str) -> LLMResponse:
    """Construit une réponse fake adaptée au phase courante.

    Args:
        phase_name: Identifiant de phase pour décider du contenu.

    Returns:
        ``LLMResponse``.
    """
    if "term_extraction" in phase_name:
        content = json.dumps(
            {
                "terms": [
                    {"term": "PIB", "definition": "produit intérieur brut", "aliases": []}
                ]
            }
        )
    elif "glossary_reconciliation" in phase_name:
        content = json.dumps(
            {
                "terms": [
                    {
                        "term": "PIB",
                        "definition": "produit intérieur brut",
                        "aliases": [],
                        "sources": [],
                    }
                ]
            }
        )
    elif "consolidation" in phase_name and "video_summary" not in phase_name:
        content = json.dumps(
            {
                "global_title": "Cours d'économie",
                "summary_markdown": "Vue d'ensemble synthétique du cours.",
                "introduction_markdown": "Introduction.",
                "plan_markdown": "1. Chapitre 1\n2. Chapitre 2",
                "conclusion_markdown": "Conclusion.",
            }
        )
    elif "video_summary" in phase_name:
        content = json.dumps(
            {"title": "Chapitre", "outline": ["a"], "key_ideas": ["x"]}
        )
    else:
        content = "# Titre\n\nContenu fictif."
    return LLMResponse(
        content=content,
        thinking_content=None,
        prompt_tokens=100,
        completion_tokens=50,
        cached_prompt_tokens=0,
        cost_usd=0.001,
    )


class _RotatingFakeLLM(FakeLLMProvider):
    """FakeLLM qui retourne une réponse contextuelle selon le contenu envoyé.

    Inspecte le prompt utilisateur pour décider quelle réponse retourner :
    on cherche un fragment d'identifiant de phase ou un mot-clé dans les
    messages pour router.
    """

    def chat(  # noqa: PLR0911
        self,
        *,
        messages: Any,
        model: str,
        thinking: bool,
        reasoning_effort: str | None = None,
        temperature: float,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        user_content = " ".join(
            m.content for m in messages if m.role == "user"
        )
        if (
            "Réponds STRICTEMENT en JSON" in user_content
            and "glossaire pédagogique" in user_content
        ):
            return _llm_response_for_phase("term_extraction")
        if "consolide un glossaire" in user_content:
            return _llm_response_for_phase("glossary_reconciliation")
        if "résumé condensé" in user_content and "carte mentale" in user_content:
            return _llm_response_for_phase("video_summary")
        if "rédige les méta-éléments" in user_content:
            return _llm_response_for_phase("consolidation")
        if "Traduis" in user_content:
            return _llm_response_for_phase("translation")
        if "passe de cohérence" in user_content:
            return _llm_response_for_phase("coherence")
        return _llm_response_for_phase("default")


def test_full_pipeline_produces_expected_outputs(
    tmp_path: Path,
    make_generation_settings: Any,
    e2e_input_folder: Path,
) -> None:
    state = SqliteState(tmp_path / "state.db")
    workspace = tmp_path / "workspace"
    output_dir = tmp_path / "output"

    project_service = ProjectService(state)
    settings = make_generation_settings(
        input_folder=e2e_input_folder,
        source_language=Language.FR,
        output_languages=(Language.FR, Language.EN),
    )
    project = project_service.create_project(
        name="E2E", workspace_folder=workspace, generation=settings
    )

    registry = PhaseRegistry(
        [
            Phase0SttHandler(),
            Phase1TermExtractionHandler(),
            Phase2GlossaryReconciliationHandler(),
            Phase3ReformulationHandler(),
            Phase4StructurationHandler(),
            Phase5ConsolidationHandler(),
            Phase6TranslationHandler(),
            Phase7CoherenceHandler(),
        ]
    )
    engine = PipelineEngine(
        registry=registry,
        retry_policy=RetryPolicy(jitter=False, initial_delay_seconds=0.001),
    )
    orchestrator = RunOrchestrator(
        state=state, engine=engine, project_service=project_service
    )
    run = orchestrator.create_run(project)
    assert len(run.sources) == 2

    fake_stt = FakeSTTProvider(
        default_transcription=Transcription(
            segments=(
                TranscriptionSegment(
                    start_seconds=0.0,
                    end_seconds=1.0,
                    text="le PIB mesure la production",
                ),
            ),
            detected_language=Language.FR,
            duration_seconds=1.0,
        )
    )

    ctx = PhaseContext(
        run=run,
        settings=run.settings_snapshot,
        workspace=workspace,
        output_dir=output_dir,
        state=state,
        artifacts=FsArtifactStore(),
        stt_provider=fake_stt,
        llm_provider=_RotatingFakeLLM(),
        ffmpeg=FFmpegExtractor(),
        retriever=PassthroughRetriever(),
        prompts=PromptLoader(),
        pause_token=PauseToken(),
        event_bus=EventBus(),
    )

    final_status = orchestrator.execute(run=run, ctx=ctx)
    assert final_status is RunStatus.COMPLETED, (
        f"Pipeline failed: status={final_status}"
    )

    # Artefacts par-vidéo FR + EN
    for video in run.sources:
        assert (
            output_dir / "per-video" / "fr" / f"{video.source_id.value}.md"
        ).exists()
        assert (
            output_dir / "per-video" / "en" / f"{video.source_id.value}.md"
        ).exists()

    # Document consolidé FR + EN
    assert (output_dir / "consolidated.fr.md").exists()
    assert (output_dir / "consolidated.en.md").exists()

    # Glossaire FR + EN
    assert (output_dir / "glossary.fr.md").exists()
    assert (output_dir / "glossary.en.md").exists()

    # Glossaire master en workspace
    assert (workspace / "glossary_master.json").exists()
    assert (workspace / "consolidated_master.md").exists()

    # Le document consolidé master s'ouvre sur la section Résumé (sous le titre).
    master_md = (workspace / "consolidated_master.md").read_text(encoding="utf-8")
    assert "## Résumé" in master_md
    assert "Vue d'ensemble synthétique du cours." in master_md

    # Statut Run persiste en SQLite avec finished_at non-null et timestamp datetime UTC
    reloaded = orchestrator.get_run(run.id)
    assert reloaded is not None
    assert reloaded.status is RunStatus.COMPLETED
    assert reloaded.finished_at is not None
    assert reloaded.finished_at <= datetime.now(tz=UTC)
