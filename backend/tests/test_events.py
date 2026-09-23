import pytest

from app.events import EVENT_SCHEMA_VERSION, UnknownEventType, build_event, topic_for_event


def test_topic_for_event_routes_known_types() -> None:
    assert topic_for_event("video.uploaded") == "video-events"
    assert topic_for_event("transcript.ready") == "transcription-events"
    assert topic_for_event("analysis.requested") == "analysis-events"


def test_topic_for_event_rejects_unknown_types() -> None:
    with pytest.raises(UnknownEventType):
        topic_for_event("not.an.event")


def test_build_event_envelope_shape() -> None:
    event = build_event(
        event_type="transcript.ready",
        owner_uid="u1",
        project_id="p1",
        job_id="j1",
        payload={"transcriptId": "t1"},
    )
    assert event["type"] == "transcript.ready"
    assert event["ownerUid"] == "u1"
    assert event["projectId"] == "p1"
    assert event["jobId"] == "j1"
    assert event["payload"] == {"transcriptId": "t1"}
    assert event["schemaVersion"] == EVENT_SCHEMA_VERSION
    assert event["eventId"]
    assert event["occurredAt"]
