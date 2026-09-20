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


class _FlakyClient:
    """Fails with `error` for the first `failures` calls, then succeeds."""

    def __init__(self, error: Exception, failures: int = 1) -> None:
        self.calls = 0
        self._error = error
        self._failures = failures
        self.models = SimpleNamespace(generate_content=self._generate)

    def _generate(self, **_: object) -> SimpleNamespace:
        self.calls += 1
        if self.calls <= self._failures:
            raise self._error
        return SimpleNamespace(text='{"ok": true}')


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


async def test_llm_retries_transient_error_then_succeeds(monkeypatch, tmp_path) -> None:
    from google.genai import errors as genai_errors

    client = _FlakyClient(
        genai_errors.ServerError(
            503, {"error": {"code": 503, "status": "UNAVAILABLE"}}, None
        ),
        failures=1,
    )
    monkeypatch.setattr("google.genai.Client", lambda **_: client)
    settings = Settings(
        mock_mode="auto",
        cassette_dir=str(tmp_path),
        gemini_api_key="k",
        llm_retry_base_seconds=0,
    )
    provider = LlmProvider(settings, CassetteStore(str(tmp_path)))

    result = await provider.complete_json(
        model="m", prompt_version="v1", system="s", user="u", schema={}
    )

    assert result == {"ok": True}
    assert client.calls == 2


async def test_llm_does_not_retry_client_error(monkeypatch, tmp_path) -> None:
    from google.genai import errors as genai_errors

    client = _FlakyClient(
        genai_errors.ClientError(
            404, {"error": {"code": 404, "status": "NOT_FOUND"}}, None
        ),
        failures=1,
    )
    monkeypatch.setattr("google.genai.Client", lambda **_: client)
    settings = Settings(
        mock_mode="auto",
        cassette_dir=str(tmp_path),
        gemini_api_key="k",
        llm_retry_base_seconds=0,
    )
    provider = LlmProvider(settings, CassetteStore(str(tmp_path)))

    with pytest.raises(genai_errors.ClientError):
        await provider.complete_json(
            model="m", prompt_version="v1", system="s", user="u", schema={}
        )
    assert client.calls == 1
