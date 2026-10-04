"""Subtitle parsing helpers.

The dubbing worker already writes a localized SRT next to the dubbed video. To burn those
captions onto that video we need them as timed cues again, so this parses the SRT back into
`{startMs, endMs, text}` segments (the same shape `caption_styles.build_ass` consumes).

Kept deliberately small and dependency-free: SRT is the only format produced here.
"""

from __future__ import annotations

import re
from typing import Any

_TIMESTAMP = re.compile(r"(\d{1,2}):(\d{2}):(\d{2})[,.](\d{1,3})")
_BLOCK = re.compile(r"\n\s*\n")


def _to_ms(match: re.Match[str]) -> int:
    hours, minutes, seconds, millis = match.groups()
    return (
        (int(hours) * 3600 + int(minutes) * 60 + int(seconds)) * 1000
        + int(millis.ljust(3, "0"))
    )


def parse_srt(text: str) -> list[dict[str, Any]]:
    """Parse an SRT document into `{startMs, endMs, text, speaker}` cues.

    Blank-separated blocks; the timestamp line is located by its `-->` rather than trusting
    the index line, and any following lines are joined into one cue text.
    """
    segments: list[dict[str, Any]] = []
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        return segments

    for block in _BLOCK.split(normalized):
        lines = [line.strip() for line in block.split("\n") if line.strip()]
        if not lines:
            continue
        timestamp_index = next(
            (index for index, line in enumerate(lines) if "-->" in line), None
        )
        if timestamp_index is None:
            continue
        start_text, _, end_text = lines[timestamp_index].partition("-->")
        start_match = _TIMESTAMP.search(start_text)
        end_match = _TIMESTAMP.search(end_text)
        if start_match is None or end_match is None:
            continue
        body = " ".join(lines[timestamp_index + 1 :]).strip()
        if not body:
            continue
        start_ms = _to_ms(start_match)
        end_ms = max(start_ms + 1, _to_ms(end_match))
        segments.append(
            {"startMs": start_ms, "endMs": end_ms, "text": body, "speaker": None}
        )
    return segments


__all__ = ["parse_srt"]
