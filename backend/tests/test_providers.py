from app.config import Settings
from app.providers.cassette import CassetteStore
from app.providers.llm import LlmProvider


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
