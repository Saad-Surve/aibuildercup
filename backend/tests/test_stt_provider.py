from types import SimpleNamespace

from app.config import Settings
from app.providers.stt import SttProvider, _duration_to_ms, _response_to_dict


def _provider() -> SttProvider:
    return SttProvider(Settings())


def test_gcs_uri_for_uses_media_bucket() -> None:
    assert (
        _provider().gcs_uri_for("users/u/projects/p/source/a.mp4")
        == "gs://habeas-codus-media/users/u/projects/p/source/a.mp4"
    )


def test_duration_to_ms() -> None:
    assert _duration_to_ms(None) == 0
    assert _duration_to_ms(SimpleNamespace(seconds=1, nanos=500_000_000)) == 1500
    assert _duration_to_ms(SimpleNamespace(seconds=0, nanos=0)) == 0


def _word(text: str, start_ms: int, end_ms: int) -> SimpleNamespace:
    return SimpleNamespace(
        word=text,
        start_offset=SimpleNamespace(seconds=start_ms // 1000, nanos=(start_ms % 1000) * 1_000_000),
        end_offset=SimpleNamespace(seconds=end_ms // 1000, nanos=(end_ms % 1000) * 1_000_000),
    )


def test_response_to_dict_extracts_word_timings() -> None:
    result = SimpleNamespace(
        results={
            "output": SimpleNamespace(
                inline_result=SimpleNamespace(
                    alternatives=[
                        SimpleNamespace(
                            words=[_word("hello", 0, 300), _word("world", 300, 600)]
                        )
                    ]
                )
            )
        }
    )
    assert _response_to_dict(result) == {
        "words": [
            {"word": "hello", "startMs": 0, "endMs": 300},
            {"word": "world", "startMs": 300, "endMs": 600},
        ]
    }


def test_response_to_dict_skips_files_without_inline_results() -> None:
    result = SimpleNamespace(
        results={"output": SimpleNamespace(cloud_storage_result="gs://b/o.json")}
    )
    assert _response_to_dict(result) == {"words": []}


def test_response_to_dict_handles_empty_response() -> None:
    assert _response_to_dict(SimpleNamespace(results={})) == {"words": []}
