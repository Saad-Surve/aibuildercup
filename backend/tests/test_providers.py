from types import SimpleNamespace

import pytest

from app.config import Settings
from app.providers.cassette import CassetteStore
from app.providers.llm import LlmProvider


class _FakeClient:
    """Captures how `genai.Client` was constructed and returns a fixed JSON answer."""

    def __init__(self, captured: list[dict], **kwargs: object) -> None:
        captured.append(kwargs)
        self.models = SimpleNamespace(
            generate_content=lambda **_: SimpleNamespace(text='{"ok": true}')
        )


def test_cassette_key_is_stable() -> None:
    a = CassetteStore.make_key("llm", "m", "v1", {"user": "hi"})
    b = CassetteStore.make_key("llm", "m", "v1", {"user": "hi"})
    assert a == b


def test_cassette_key_changes_with_prompt_version() -> None:
    a = CassetteStore.make_key("llm", "m", "v1", {"user": "hi"})
    b = CassetteStore.make_key("llm", "m", "v2", {"user": "hi"})
    assert a != b


async def test_llm_replays_from_cassette(tmp_path) -> None:
    settings = Settings(mock_mode="on", cassette_dir=str(tmp_path))
    store = CassetteStore(str(tmp_path))
    provider = LlmProvider(settings, store)

    request = {"system": "s", "user": "u", "schema": {"type": "object"}}
    key = CassetteStore.make_key("llm", "model-x", "v1", request)
    store.save(
        "llm",
        key,
        model="model-x",
        prompt_version="v1",
        request_summary="test",
        response={"ok": True},
    )

    result = await provider.complete_json(
        model="model-x",
        prompt_version="v1",
        system="s",
        user="u",
        schema={"type": "object"},
    )
    assert result == {"ok": True}


async def test_llm_uses_gemini_api_key_when_set(monkeypatch, tmp_path) -> None:
    captured: list[dict] = []
    monkeypatch.setattr(
        "google.genai.Client", lambda **kwargs: _FakeClient(captured, **kwargs)
    )
    settings = Settings(
        mock_mode="auto", cassette_dir=str(tmp_path), gemini_api_key="test-key"
    )
    provider = LlmProvider(settings, CassetteStore(str(tmp_path)))

    await provider.complete_json(
        model="m", prompt_version="v1", system="s", user="u", schema={}
    )

    assert captured == [{"api_key": "test-key"}]


async def test_llm_requires_api_key(monkeypatch, tmp_path) -> None:
    captured: list[dict] = []
    monkeypatch.setattr(
        "google.genai.Client", lambda **kwargs: _FakeClient(captured, **kwargs)
    )
    settings = Settings(
        mock_mode="auto", cassette_dir=str(tmp_path), gemini_api_key=None
    )
    provider = LlmProvider(settings, CassetteStore(str(tmp_path)))

    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        await provider.complete_json(
            model="m", prompt_version="v1", system="s", user="u", schema={}
        )
    assert captured == []
