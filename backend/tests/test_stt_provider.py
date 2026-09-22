from types import SimpleNamespace

import pytest
from google.cloud import speech_v2

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


def _file_result(
    words: list[SimpleNamespace],
    *,
    language: str = "en-US",
    error: SimpleNamespace | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        error=error,
        transcript=None,
        inline_result=SimpleNamespace(
            transcript=SimpleNamespace(
                results=[
                    SimpleNamespace(
                        language_code=language,
                        alternatives=[SimpleNamespace(words=words)],
                    )
                ]
            )
        ),
    )


def test_response_to_dict_extracts_word_timings_and_language() -> None:
    result = SimpleNamespace(
        results={"uri": _file_result([_word("hello", 0, 300), _word("world", 300, 600)])}
    )
    assert _response_to_dict(result) == {
        "words": [
            {"word": "hello", "startMs": 0, "endMs": 300},
            {"word": "world", "startMs": 300, "endMs": 600},
        ],
        "language": "en-US",
    }


def test_response_to_dict_uses_file_level_transcript_when_no_inline() -> None:
    result = SimpleNamespace(
        results={
            "uri": SimpleNamespace(
                inline_result=None,
                transcript=SimpleNamespace(
                    results=[
                        SimpleNamespace(
                            language_code="hi-IN",
                            alternatives=[SimpleNamespace(words=[_word("नमस्ते", 0, 500)])],
                        )
                    ]
                ),
            )
        }
    )
    assert _response_to_dict(result) == {
        "words": [{"word": "नमस्ते", "startMs": 0, "endMs": 500}],
        "language": "hi-IN",
    }


def test_response_to_dict_skips_files_without_results() -> None:
    result = SimpleNamespace(
        results={"output": SimpleNamespace(cloud_storage_result="gs://b/o.json")}
    )
    assert _response_to_dict(result) == {"words": [], "language": None}


def test_response_to_dict_surfaces_per_file_errors() -> None:
    result = SimpleNamespace(
        results={
            "uri": SimpleNamespace(
                error=SimpleNamespace(code=3, message="Audio data is unsupported"),
                inline_result=None,
                transcript=None,
            )
        }
    )
    with pytest.raises(RuntimeError, match="Audio data is unsupported"):
        _response_to_dict(result)


def test_response_to_dict_handles_empty_response() -> None:
    assert _response_to_dict(SimpleNamespace(results={})) == {"words": [], "language": None}


def test_decoding_config_uses_explicit_aac_for_video_containers() -> None:
    config = _provider()._decoding_config(speech_v2, "gs://b/u/p/clip.mp4")
    explicit = config["explicit_decoding_config"]
    assert explicit.encoding == speech_v2.ExplicitDecodingConfig.AudioEncoding.MP4_AAC
    assert explicit.sample_rate_hertz == 44100
    assert explicit.audio_channel_count == 2


def test_decoding_config_auto_detects_audio_only_formats() -> None:
    config = _provider()._decoding_config(speech_v2, "gs://b/u/p/song.mp3")
    assert "auto_decoding_config" in config
    assert "explicit_decoding_config" not in config
