from types import SimpleNamespace

import pytest

from app.config import Settings
from app.providers.llm import LlmProvider


class _FakeClient:
    """Captures how `genai.Client` was constructed and returns a fixed JSON answer."""

    def __init__(self, captured: list[dict], **kwargs: object) -> None:
        captured.append(kwargs)
        self.models = SimpleNamespace(generate_content=lambda **_: _result('{"ok": true}'))


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
        return _result('{"ok": true}')


def _result(text: str) -> SimpleNamespace:
    return SimpleNamespace(
        text=text,
        usage_metadata=SimpleNamespace(
            prompt_token_count=120,
            candidates_token_count=30,
            thoughts_token_count=8,
        ),
    )


async def test_llm_uses_gemini_api_key_when_set(monkeypatch) -> None:
    captured: list[dict] = []
    monkeypatch.setattr(
        "google.genai.Client", lambda **kwargs: _FakeClient(captured, **kwargs)
    )
    provider = LlmProvider(Settings(gemini_api_key="test-key"))

    await provider.complete_json(
        model="m", prompt_version="v1", system="s", user="u", schema={}
    )

    assert captured == [{"api_key": "test-key"}]


async def test_llm_requires_api_key(monkeypatch) -> None:
    captured: list[dict] = []
    monkeypatch.setattr(
        "google.genai.Client", lambda **kwargs: _FakeClient(captured, **kwargs)
    )
    provider = LlmProvider(Settings(gemini_api_key=None))

    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        await provider.complete_json(
            model="m", prompt_version="v1", system="s", user="u", schema={}
        )
    assert captured == []


async def test_llm_vertex_backend_uses_adc_without_api_key(monkeypatch) -> None:
    captured: list[dict] = []
    monkeypatch.setattr(
        "google.genai.Client", lambda **kwargs: _FakeClient(captured, **kwargs)
    )
    provider = LlmProvider(
        Settings(llm_backend="vertex", project_id="proj", vertex_location="global")
    )

    await provider.complete_json(
        model="gemini-3.8-flash", prompt_version="v1", system="s", user="u", schema={}
    )

    # Vertex is authenticated with ADC, so no api_key is passed; project + location instead.
    assert captured == [{"vertexai": True, "project": "proj", "location": "global"}]


async def test_llm_retries_transient_error_then_succeeds(monkeypatch) -> None:
    from google.genai import errors as genai_errors

    client = _FlakyClient(
        genai_errors.ServerError(
            503, {"error": {"code": 503, "status": "UNAVAILABLE"}}, None
        ),
        failures=1,
    )
    monkeypatch.setattr("google.genai.Client", lambda **_: client)
    provider = LlmProvider(
        Settings(gemini_api_key="k", llm_retry_base_seconds=0)
    )

    result = await provider.complete_json(
        model="m", prompt_version="v1", system="s", user="u", schema={}
    )

    assert result.data == {"ok": True}
    assert client.calls == 2


async def test_llm_reports_token_usage(monkeypatch) -> None:
    captured: list[dict] = []
    monkeypatch.setattr(
        "google.genai.Client", lambda **kwargs: _FakeClient(captured, **kwargs)
    )
    provider = LlmProvider(Settings(gemini_api_key="test-key"))

    result = await provider.complete_json(
        model="m", prompt_version="v1", system="s", user="u", schema={}
    )

    # Thinking tokens are billed as output, so they join the candidate count.
    assert result.usage.input_tokens == 120
    assert result.usage.output_tokens == 38


async def test_llm_usage_defaults_to_zero_when_absent(monkeypatch) -> None:
    class _NoUsageClient:
        def __init__(self, **_: object) -> None:
            self.models = SimpleNamespace(
                generate_content=lambda **_: SimpleNamespace(text='{"ok": true}')
            )

    monkeypatch.setattr("google.genai.Client", lambda **_: _NoUsageClient())
    provider = LlmProvider(Settings(gemini_api_key="test-key"))

    result = await provider.complete_json(
        model="m", prompt_version="v1", system="s", user="u", schema={}
    )

    assert result.data == {"ok": True}
    assert result.usage.input_tokens == 0
    assert result.usage.output_tokens == 0


async def test_llm_does_not_retry_client_error(monkeypatch) -> None:
    from google.genai import errors as genai_errors

    client = _FlakyClient(
        genai_errors.ClientError(
            404, {"error": {"code": 404, "status": "NOT_FOUND"}}, None
        ),
        failures=1,
    )
    monkeypatch.setattr("google.genai.Client", lambda **_: client)
    provider = LlmProvider(
        Settings(gemini_api_key="k", llm_retry_base_seconds=0)
    )

    with pytest.raises(genai_errors.ClientError):
        await provider.complete_json(
            model="m", prompt_version="v1", system="s", user="u", schema={}
        )
    assert client.calls == 1
