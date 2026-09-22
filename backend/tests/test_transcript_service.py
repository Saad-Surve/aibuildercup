import pytest

from app.errors import NotFoundError
from app.schemas.projects import CreateProject
from app.services.project_service import ProjectService
from app.services.transcript_service import (
    TranscriptService,
    build_segments,
    build_srt,
    build_vtt,
    format_vtt_timestamp,
    normalize_words,
)
from tests.fakes import FakeFirestoreClient, FakeStorageClient

UID = "uid-1"


def _words(n: int, start: int = 0, step: int = 400) -> list[dict]:
    return [
        {"word": f"w{i}", "startMs": start + i * step, "endMs": start + (i + 1) * step}
        for i in range(n)
    ]


def test_normalize_words_sorts_sanitises_and_clamps() -> None:
    response = {
        "words": [
            {"word": "  world ", "startMs": 800, "endMs": 400},
            {"word": "", "startMs": 0, "endMs": 100},
            {"word": "hello.", "startMs": 0, "endMs": 400},
            {"word": "bad", "startMs": "x", "endMs": 100},
        ]
    }
    assert normalize_words(response) == [
        {"word": "hello.", "startMs": 0, "endMs": 400},
        {"word": "world", "startMs": 800, "endMs": 800},
    ]


def test_build_segments_splits_on_sentence_end() -> None:
    words = [
        {"word": "Hello", "startMs": 0, "endMs": 300},
        {"word": "world.", "startMs": 300, "endMs": 600},
        {"word": "Next", "startMs": 600, "endMs": 900},
        {"word": "idea.", "startMs": 900, "endMs": 1200},
    ]
    segments = build_segments(words)
    assert [s["text"] for s in segments] == ["Hello world.", "Next idea."]
    assert segments[0]["segmentId"] == "seg-1"
    assert segments[0]["index"] == 0
    assert (segments[0]["startMs"], segments[0]["endMs"]) == (0, 600)


def test_build_segments_caps_words_and_duration() -> None:
    segments = build_segments(_words(30))
    assert len(segments) >= 3
    assert all(len(s["text"].split()) <= 14 for s in segments)
    assert all(s["endMs"] - s["startMs"] <= 8000 for s in segments)


def test_format_vtt_timestamp() -> None:
    assert format_vtt_timestamp(0) == "00:00:00.000"
    assert format_vtt_timestamp(61_234) == "00:01:01.234"
    assert format_vtt_timestamp(3_723_005) == "01:02:03.005"


def test_build_vtt_and_srt_shapes() -> None:
    segments = build_segments(
        [
            {"word": "Hi.", "startMs": 0, "endMs": 500},
            {"word": "Bye.", "startMs": 1000, "endMs": 1500},
        ]
    )
    vtt = build_vtt(segments)
    assert vtt.startswith("WEBVTT\n")
    assert "00:00:00.000 --> 00:00:00.500" in vtt
    assert "Hi." in vtt
    srt = build_srt(segments)
    assert "00:00:00,000 --> 00:00:00,500" in srt
    assert srt.startswith("1\n")


def test_build_vtt_empty_is_header_only() -> None:
    assert build_vtt([]) == "WEBVTT\n"


class Harness:
    def __init__(self) -> None:
        self.client = FakeFirestoreClient()
        self.storage = FakeStorageClient()
        self.projects = ProjectService(self.client)
        self.service = TranscriptService(self.client, storage=self.storage)

    def project(self, language: str = "en") -> str:
        return self.projects.create(
            owner_uid=UID, payload=CreateProject(name="P", primaryLanguage=language)
        ).projectId


def test_save_and_get_roundtrip() -> None:
    h = Harness()
    project_id = h.project()
    words = [
        {"word": "Welcome", "startMs": 0, "endMs": 400},
        {"word": "back.", "startMs": 400, "endMs": 800},
    ]
    transcript_id = h.service.save(
        owner_uid=UID,
        project_id=project_id,
        source_asset_id="asset-1",
        language="en-US",
        words=words,
    )
    transcript = h.service.get(owner_uid=UID, project_id=project_id)
    assert transcript.transcriptId == transcript_id
    assert transcript.language == "en-US"
    assert transcript.durationMs == 800
    assert [s.text for s in transcript.segments] == ["Welcome back."]
    assert h.service.next_version(owner_uid=UID, project_id=project_id) == 2

    project = h.client.docs[f"users/{UID}/projects/{project_id}"]
    assert project["activeTranscriptId"] == transcript_id
    doc = h.client.docs[f"users/{UID}/projects/{project_id}/transcripts/{transcript_id}"]
    assert doc["wordCount"] == 2
    assert h.storage.objects[doc["storagePath"]].startswith('{\n  "version": 1')
    assert h.storage.objects[doc["vttStoragePath"]].startswith("WEBVTT")


def test_get_without_transcript_raises_not_found() -> None:
    h = Harness()
    project_id = h.project()
    with pytest.raises(NotFoundError):
        h.service.get(owner_uid=UID, project_id=project_id)


def test_get_rejects_other_owner() -> None:
    h = Harness()
    project_id = h.project()
    h.service.save(
        owner_uid=UID,
        project_id=project_id,
        source_asset_id="asset-1",
        language="en-US",
        words=_words(3),
    )
    with pytest.raises(NotFoundError):
        h.service.get(owner_uid="someone-else", project_id=project_id)
