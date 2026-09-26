"""Transcript persistence and STT normalisation.

Pure helpers (`normalize_words`, `build_segments`, `build_vtt`, `build_srt`) are unit tested.
`TranscriptService` persists via the narrow `FirestoreClient`/`StorageClient` protocols and
checks `ownerUid` on every read, like the other services.
"""

import json
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from app.errors import NotFoundError
from app.schemas.transcripts import Transcript, TranscriptSegment, TranscriptVersion
from app.services.firestore_service import (
    FirestoreClient,
    project_path,
    transcript_object_path,
    transcript_path,
    transcript_segment_path,
    transcript_srt_object_path,
    transcript_vtt_object_path,
    transcripts_collection_path,
)
from app.services.storage_service import StorageClient

# Segmentation bounds: keep cues readable and the heatmap bins (5s) meaningful.
MAX_WORDS_PER_SEGMENT = 14
MAX_SEGMENT_MS = 8000

_SENTENCE_END = (".", "?", "!", "。", "؟")


def normalize_words(response: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract and sanitise word timings from an STT provider response."""
    words: list[dict[str, Any]] = []
    for entry in response.get("words") or []:
        text = str(entry.get("word", "")).strip()
        if not text:
            continue
        try:
            start_ms = max(0, int(entry.get("startMs", 0)))
            end_ms = max(0, int(entry.get("endMs", 0)))
        except (TypeError, ValueError):
            continue
        if end_ms < start_ms:
            end_ms = start_ms
        speaker = entry.get("speaker")
        try:
            speaker = int(speaker) if speaker is not None else None
        except (TypeError, ValueError):
            speaker = None
        words.append(
            {"word": text, "startMs": start_ms, "endMs": end_ms, "speaker": speaker}
        )
    words.sort(key=lambda w: (w["startMs"], w["endMs"]))
    return words


def build_segments(words: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group word timings into sentence-like segments with stable ids."""
    segments: list[dict[str, Any]] = []
    current: list[dict[str, Any]] = []

    def flush() -> None:
        if not current:
            return
        index = len(segments)
        segments.append(
            {
                "segmentId": f"seg-{index + 1}",
                "index": index,
                "startMs": current[0]["startMs"],
                "endMs": current[-1]["endMs"],
                "text": " ".join(w["word"] for w in current),
                "speaker": current[0].get("speaker"),
            }
        )
        current.clear()

    for word in words:
        # A speaker change starts a new cue so each segment belongs to one voice. Checked before
        # appending, while `current` still holds the previous speaker's words.
        if current and word.get("speaker") != current[-1].get("speaker"):
            flush()
        current.append(word)
        text = word["word"]
        span_ms = word["endMs"] - current[0]["startMs"] if current else 0
        sentence_end = text.endswith(_SENTENCE_END)
        if sentence_end or len(current) >= MAX_WORDS_PER_SEGMENT or span_ms >= MAX_SEGMENT_MS:
            flush()
    flush()
    return segments


def format_vtt_timestamp(ms: int) -> str:
    ms = max(0, int(ms))
    hours, remainder = divmod(ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{millis:03d}"


def format_srt_timestamp(ms: int) -> str:
    return format_vtt_timestamp(ms).replace(".", ",")


def _speaker_count(segments: list[dict[str, Any]]) -> int:
    return len({s.get("speaker") for s in segments if s.get("speaker") is not None})


def build_vtt(segments: list[dict[str, Any]]) -> str:
    # Voice tags only when there is a real turn to distinguish; a single speaker would just add
    # noise to every cue.
    label_speakers = _speaker_count(segments) > 1
    lines = ["WEBVTT", ""]
    for segment in segments:
        lines.append(
            f"{format_vtt_timestamp(segment['startMs'])} --> "
            f"{format_vtt_timestamp(segment['endMs'])}"
        )
        text = segment["text"]
        if label_speakers and segment.get("speaker") is not None:
            text = f"<v Speaker {segment['speaker']}>{text}"
        lines.append(text)
        lines.append("")
    return "\n".join(lines).rstrip("\n") + "\n" if len(lines) > 2 else "WEBVTT\n"


def build_srt(segments: list[dict[str, Any]]) -> str:
    label_speakers = _speaker_count(segments) > 1
    blocks: list[str] = []
    for number, segment in enumerate(segments, start=1):
        text = segment["text"]
        if label_speakers and segment.get("speaker") is not None:
            text = f"Speaker {segment['speaker']}: {text}"
        blocks.append(
            f"{number}\n"
            f"{format_srt_timestamp(segment['startMs'])} --> "
            f"{format_srt_timestamp(segment['endMs'])}\n"
            f"{text}\n"
        )
    return "\n".join(blocks)


def is_owner(document: dict[str, Any], owner_uid: str) -> bool:
    return document.get("ownerUid") == owner_uid


def _to_transcript(
    transcript_id: str,
    data: dict[str, Any],
    segments: list[dict[str, Any]],
) -> Transcript:
    ordered = sorted(segments, key=lambda s: s.get("index", 0))
    return Transcript(
        transcriptId=transcript_id,
        language=data.get("language", "en"),
        durationMs=int(data.get("durationMs", 0)),
        segments=[
            TranscriptSegment(
                segmentId=s["segmentId"],
                index=int(s.get("index", i)),
                startMs=int(s.get("startMs", 0)),
                endMs=int(s.get("endMs", 0)),
                text=str(s.get("text", "")),
                speaker=s.get("speaker"),
            )
            for i, s in enumerate(ordered)
        ],
    )


class TranscriptService:
    def __init__(self, client: FirestoreClient, *, storage: StorageClient) -> None:
        self.client = client
        self.storage = storage

    def get(
        self, *, owner_uid: str, project_id: str, version: int | None = None
    ) -> Transcript:
        project = self.client.get_document(project_path(owner_uid, project_id))
        if project is None or not is_owner(project, owner_uid):
            raise NotFoundError("Project not found", details={"projectId": project_id})
        if version is None:
            transcript_id = project.get("activeTranscriptId")
            if not transcript_id:
                raise NotFoundError(
                    "Transcript not ready", details={"projectId": project_id}
                )
        else:
            rows = self.client.query_collection(
                transcripts_collection_path(owner_uid, project_id),
                filters=[("version", "==", version)],
                order_by=[],
                limit=1,
                offset=0,
            )
            match = next(
                (tid, data) for tid, data in rows if is_owner(data, owner_uid)
            )
            if match is None:
                raise NotFoundError(
                    "Transcript version not found",
                    details={"projectId": project_id, "version": version},
                )
            transcript_id = match[0]
        return self.get_by_id(
            owner_uid=owner_uid, project_id=project_id, transcript_id=transcript_id
        )

    def list_versions(
        self, *, owner_uid: str, project_id: str
    ) -> list[TranscriptVersion]:
        """Every saved transcript generation, oldest first."""
        project = self.client.get_document(project_path(owner_uid, project_id))
        if project is None or not is_owner(project, owner_uid):
            raise NotFoundError("Project not found", details={"projectId": project_id})
        rows = self.client.query_collection(
            transcripts_collection_path(owner_uid, project_id),
            filters=[],
            order_by=[("version", "ASCENDING")],
            limit=100,
            offset=0,
        )
        return [
            TranscriptVersion(
                transcriptId=transcript_id,
                version=int(data.get("version", 0)),
                language=str(data.get("language", "")),
                durationMs=int(data.get("durationMs", 0)),
                wordCount=int(data.get("wordCount", 0)),
                createdAt=data.get("createdAt"),
            )
            for transcript_id, data in rows
            if is_owner(data, owner_uid)
        ]

    def get_by_id(
        self, *, owner_uid: str, project_id: str, transcript_id: str
    ) -> Transcript:
        """Load a specific transcript, whatever the project's active one is now."""
        data = self.client.get_document(transcript_path(owner_uid, project_id, transcript_id))
        if data is None or not is_owner(data, owner_uid):
            raise NotFoundError("Transcript not found", details={"projectId": project_id})
        rows = self.client.query_collection(
            f"{transcript_path(owner_uid, project_id, transcript_id)}/segments",
            filters=[],
            order_by=[("index", "ASCENDING")],
            limit=2000,
            offset=0,
        )
        # The segment id is the document id; reattach it for the public shape.
        segments = [{"segmentId": seg_id, **doc} for seg_id, doc in rows]
        return _to_transcript(transcript_id, data, segments)

    def get_segment(
        self, *, owner_uid: str, project_id: str, segment_id: str
    ) -> TranscriptSegment:
        project = self.client.get_document(project_path(owner_uid, project_id))
        if project is None or not is_owner(project, owner_uid):
            raise NotFoundError("Project not found", details={"projectId": project_id})
        transcript_id = project.get("activeTranscriptId")
        if not transcript_id:
            raise NotFoundError("Transcript not ready", details={"projectId": project_id})
        data = self.client.get_document(
            transcript_segment_path(owner_uid, project_id, transcript_id, segment_id)
        )
        if data is None or not is_owner(data, owner_uid):
            raise NotFoundError("Segment not found", details={"segmentId": segment_id})
        return TranscriptSegment(
            segmentId=segment_id,
            index=int(data.get("index", 0)),
            startMs=int(data.get("startMs", 0)),
            endMs=int(data.get("endMs", 0)),
            text=str(data.get("text", "")),
            speaker=data.get("speaker"),
        )

    def save(
        self,
        *,
        owner_uid: str,
        project_id: str,
        source_asset_id: str,
        language: str,
        words: list[dict[str, Any]],
    ) -> str:
        """Persist a normalised transcript. Returns the transcript id."""
        project = self.client.get_document(project_path(owner_uid, project_id))
        if project is None or not is_owner(project, owner_uid):
            raise NotFoundError("Project not found", details={"projectId": project_id})

        segments = build_segments(words)
        duration_ms = max((w["endMs"] for w in words), default=0)
        version = int(project.get("transcriptVersionCounter", 0) or 0) + 1
        transcript_id = uuid4().hex
        now = datetime.now(UTC)

        storage_path = transcript_object_path(owner_uid, project_id, version)
        vtt_path = transcript_vtt_object_path(owner_uid, project_id, language)
        srt_path = transcript_srt_object_path(owner_uid, project_id, language)
        canonical = {
            "version": version,
            "language": language,
            "speakerCount": _speaker_count(segments),
            "segments": [
                {
                    "id": s["segmentId"],
                    "startMs": s["startMs"],
                    "endMs": s["endMs"],
                    "text": s["text"],
                    "speaker": s.get("speaker"),
                    "words": [],
                }
                for s in segments
            ],
        }
        self.storage.upload_text(
            storage_path, json.dumps(canonical, indent=2), content_type="application/json"
        )
        self.storage.upload_text(vtt_path, build_vtt(segments), content_type="text/vtt")
        self.storage.upload_text(
            srt_path, build_srt(segments), content_type="application/x-subrip"
        )

        self.client.set_document(
            transcript_path(owner_uid, project_id, transcript_id),
            {
                "ownerUid": owner_uid,
                "projectId": project_id,
                "sourceAssetId": source_asset_id,
                "version": version,
                "status": "ready",
                "language": language,
                "storagePath": storage_path,
                "vttStoragePath": vtt_path,
                "srtStoragePath": srt_path,
                "durationMs": duration_ms,
                "wordCount": len(words),
                "segmentCount": len(segments),
                "speakerCount": _speaker_count(segments),
                "createdAt": now,
                "updatedAt": now,
            },
        )
        base = transcript_path(owner_uid, project_id, transcript_id)
        for segment in segments:
            self.client.set_document(
                f"{base}/segments/{segment['segmentId']}",
                {
                    "ownerUid": owner_uid,
                    "index": segment["index"],
                    "startMs": segment["startMs"],
                    "endMs": segment["endMs"],
                    "text": segment["text"],
                    "speaker": segment.get("speaker"),
                    "wordCount": len(segment["text"].split()),
                    "createdAt": now,
                },
            )
        self.client.update_document(
            project_path(owner_uid, project_id),
            {
                "activeTranscriptId": transcript_id,
                "transcriptVersionCounter": version,
                "updatedAt": now,
            },
        )
        return transcript_id

    def next_version(self, *, owner_uid: str, project_id: str) -> int:
        rows = self.client.query_collection(
            transcripts_collection_path(owner_uid, project_id),
            filters=[],
            order_by=[],
            limit=100,
            offset=0,
        )
        versions = [int(d.get("version", 0)) for _, d in rows if is_owner(d, owner_uid)]
        return (max(versions, default=0)) + 1
