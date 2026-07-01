"""Tests de l'adapter vision OpenAI (client factice, parsing JSON, coûts)."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from fahmi2.core.errors.exceptions import VisionError
from fahmi2.domain.enums import Language
from fahmi2.infra.prompts.loader import PromptLoader
from fahmi2.infra.vision.openai_vision import OpenAIVisionAdapter


class _FakeCompletions:
    """Endpoint ``chat.completions`` factice, enregistrant le dernier appel."""

    def __init__(self, payload: str, usage: SimpleNamespace) -> None:
        self._payload = payload
        self._usage = usage
        self.last_kwargs: dict[str, object] = {}

    def create(self, **kwargs: object) -> SimpleNamespace:
        self.last_kwargs = kwargs
        message = SimpleNamespace(content=self._payload)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=message)], usage=self._usage
        )


def _fake_client(
    payload: str, *, prompt_tokens: int = 100, completion_tokens: int = 50
) -> tuple[SimpleNamespace, _FakeCompletions]:
    completions = _FakeCompletions(
        payload,
        SimpleNamespace(
            prompt_tokens=prompt_tokens, completion_tokens=completion_tokens
        ),
    )
    return SimpleNamespace(chat=SimpleNamespace(completions=completions)), completions


@pytest.fixture
def image_file(tmp_path: Path) -> Path:
    path = tmp_path / "slide.jpg"
    path.write_bytes(b"\xff\xd8\xff\xdbfake-jpeg")
    return path


def test_analyze_slide_parses_json_and_cost(image_file: Path) -> None:
    payload = json.dumps({"texte": "Titre de la slide", "visuels": "Un graphique"})
    client, completions = _fake_client(payload)
    adapter = OpenAIVisionAdapter(
        api_key="sk-test", prompts=PromptLoader(), client=client
    )
    analysis = adapter.analyze_slide(image_file, language=Language.FR)
    assert analysis.content.text == "Titre de la slide"
    assert analysis.content.visuals_description == "Un graphique"
    assert analysis.cost_usd > 0.0
    assert completions.last_kwargs["response_format"] == {"type": "json_object"}


def test_analyze_slide_empty_content(image_file: Path) -> None:
    payload = json.dumps({"texte": "", "visuels": ""})
    client, _ = _fake_client(payload)
    adapter = OpenAIVisionAdapter(
        api_key="sk-test", prompts=PromptLoader(), client=client
    )
    assert adapter.analyze_slide(image_file, language=Language.FR).content.is_empty()


def test_analyze_slide_invalid_json_raises_vision_error(image_file: Path) -> None:
    client, _ = _fake_client("pas du JSON")
    adapter = OpenAIVisionAdapter(
        api_key="sk-test", prompts=PromptLoader(), client=client
    )
    with pytest.raises(VisionError) as excinfo:
        adapter.analyze_slide(image_file, language=Language.FR)
    assert excinfo.value.code == "VISION.INVALID_RESPONSE"
