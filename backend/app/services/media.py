"""MP4 audio normalization for Speech-to-Text.

Some uploads (typically re-muxed downloads) carry a pathological MP4 container:
thousands of micro-chunks, sample-group boxes, or a bogus sample-entry rate.
Google's STT batch importer fails those files with an internal error even though
the AAC audio itself decodes fine — players use the embedded AudioSpecificConfig
and never notice.

When that happens the transcribe worker falls back to this module: demux the raw
AAC frames out of the broken container and re-mux them into a minimal clean
`.m4a`, which STT accepts. Pure stdlib, no FFmpeg (the API container has none),
audio-only (video is irrelevant to transcription).

Only AAC-LC is supported; anything else returns None and the caller keeps the
original STT error. Edit lists are dropped, so cue boundaries may shift by a
few milliseconds on files that used them — acceptable for a transcript.
"""

import logging
import struct
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# AAC sampling-frequency-index table (ISO 14496-3). Index 15 means the rate is
# written explicitly afterwards, which we do not support.
_SAMPLE_RATES = (
    96000,
    88200,
    64000,
    48000,
    44100,
    32000,
    24000,
    22050,
    16000,
    12000,
    11025,
    8000,
    7350,
)

_AAC_LC = 2
_SAMPLES_PER_FRAME = 1024  # AAC-LC always carries 1024 samples per frame.


@dataclass(frozen=True)
class AacTrack:
    sample_rate_hz: int
    channel_count: int
    frames: tuple[bytes, ...]


def extract_aac_track(data: bytes) -> AacTrack | None:
    """Demux the first AAC-LC audio track out of an MP4/MOV/M4A file.

    Returns the raw AAC frames plus the rate/channel count from the track's
    AudioSpecificConfig, or None when the file has no usable AAC-LC track.
    """
    try:
        return _extract(data)
    except Exception:  # noqa: BLE001 - corrupt input must read as "no track"
        logger.debug("extract_aac_track: input is not a usable MP4", exc_info=True)
        return None


def _extract(data: bytes) -> AacTrack | None:
    moov = _child(data, 0, len(data), b"moov")
    if moov is None:
        return None
    for trak in _children(data, *moov, b"trak"):
        track = _audio_track(data, trak)
        if track is not None:
            return track
    return None


def _audio_track(data: bytes, trak: tuple[int, int]) -> AacTrack | None:
    mdia = _child(data, *trak, b"mdia")
    if mdia is None:
        return None
    hdlr = _child(data, *mdia, b"hdlr")
    if hdlr is None or data[hdlr[0] + 8 : hdlr[0] + 12] != b"soun":
        return None
    minf = _child(data, *mdia, b"minf")
    if minf is None:
        return None
    stbl = _child(data, *minf, b"stbl")
    if stbl is None:
        return None

    config = _aac_config(data, stbl)
    if config is None:
        return None
    sample_rate_hz, channel_count = config

    stsz = _child(data, *stbl, b"stsz")
    stsc = _child(data, *stbl, b"stsc")
    chunk_offsets = _chunk_offsets(data, stbl)
    if stsz is None or stsc is None or chunk_offsets is None:
        return None
    sizes = _sample_sizes(data, stsz)
    runs = _chunk_runs(data, stsc)
    if not sizes or not runs:
        return None

    frames: list[bytes] = []
    sample = 0
    for chunk_no, offset in enumerate(chunk_offsets, start=1):
        per_chunk = runs[0][1]
        for first_chunk, samples_per_chunk in runs[1:]:
            if chunk_no >= first_chunk:
                per_chunk = samples_per_chunk
        pos = offset
        for _ in range(per_chunk):
            if sample >= len(sizes):
                break
            size = sizes[sample]
            frames.append(bytes(data[pos : pos + size]))
            pos += size
            sample += 1
    if sample != len(sizes) or not frames:
        return None
    return AacTrack(
        sample_rate_hz=sample_rate_hz, channel_count=channel_count, frames=tuple(frames)
    )


def _aac_config(data: bytes, stbl: tuple[int, int]) -> tuple[int, int] | None:
    """Read (sample_rate_hz, channel_count) from the track's AudioSpecificConfig."""
    stsd = _child(data, *stbl, b"stsd")
    if stsd is None:
        return None
    entry_count = struct.unpack(">I", data[stsd[0] + 4 : stsd[0] + 8])[0]
    pos = stsd[0] + 8
    for _ in range(entry_count):
        size = struct.unpack(">I", data[pos : pos + 4])[0]
        if data[pos + 4 : pos + 8] == b"mp4a":
            channels = struct.unpack(">H", data[pos + 8 + 16 : pos + 8 + 18])[0]
            esds_at = data.find(b"esds", pos, pos + size)
            if esds_at < 0:
                return None
            esds_size = struct.unpack(">I", data[esds_at - 4 : esds_at])[0]
            esds = data[esds_at - 4 : esds_at - 4 + esds_size]
            rate = _parse_asc_rate(esds)
            if rate is None or channels not in (1, 2):
                return None
            return rate, channels
        pos += size
    return None


def _parse_asc_rate(esds: bytes) -> int | None:
    """Find the AudioSpecificConfig inside an esds box and return its sample rate.

    Walks the descriptor tags (`03` -> `04` -> `05`) instead of assuming fixed
    offsets, since descriptor lengths use the 0x80-continuation form.
    """
    asc = _decoder_specific_info(esds)
    if asc is None or len(asc) < 2:
        return None
    first, second = asc[0], asc[1]
    audio_object_type = first >> 3
    frequency_index = ((first & 0x07) << 1) | (second >> 7)
    if audio_object_type != _AAC_LC:
        return None
    if frequency_index >= len(_SAMPLE_RATES):
        return None
    return _SAMPLE_RATES[frequency_index]


def _decoder_specific_info(esds: bytes) -> bytes | None:
    """Return the DecoderSpecificInfo payload of an esds box (the ASC for AAC)."""
    # Skip the 8-byte box header plus version/flags; then expect ES_Descriptor (0x03).
    pos = 12
    if pos >= len(esds) or esds[pos] != 0x03:
        return None
    pos = _skip_descriptor_length(esds, pos + 1)
    # ES_ID (2) + flags (1), then DecoderConfigDescriptor (0x04).
    pos += 3
    if pos >= len(esds) or esds[pos] != 0x04:
        return None
    pos = _skip_descriptor_length(esds, pos + 1)
    # objectType + streamType + bufferSize(3) + maxBitrate(4) + avgBitrate(4).
    pos += 13
    if pos >= len(esds) or esds[pos] != 0x05:
        return None
    pos = _skip_descriptor_length(esds, pos + 1)
    return esds[pos:]


def _skip_descriptor_length(esds: bytes, pos: int) -> int:
    while pos < len(esds) and esds[pos] & 0x80:
        pos += 1
    return pos + 1


def _sample_sizes(data: bytes, stsz: tuple[int, int]) -> list[int]:
    start, _ = stsz
    default, count = struct.unpack(">II", data[start + 4 : start + 12])
    if default:
        return [default] * count
    if count > (len(data) - start - 12) // 4:
        return []
    return list(struct.unpack(f">{count}I", data[start + 12 : start + 12 + 4 * count]))


def _chunk_runs(data: bytes, stsc: tuple[int, int]) -> list[tuple[int, int]]:
    start, _ = stsc
    count = struct.unpack(">I", data[start + 4 : start + 8])[0]
    runs = []
    for i in range(count):
        first_chunk, samples_per_chunk, _ = struct.unpack(
            ">III", data[start + 8 + 12 * i : start + 20 + 12 * i]
        )
        runs.append((first_chunk, samples_per_chunk))
    return runs


def _chunk_offsets(data: bytes, stbl: tuple[int, int]) -> list[int] | None:
    stco = _child(data, *stbl, b"stco")
    if stco is not None:
        count = struct.unpack(">I", data[stco[0] + 4 : stco[0] + 8])[0]
        return list(
            struct.unpack(f">{count}I", data[stco[0] + 8 : stco[0] + 8 + 4 * count])
        )
    co64 = _child(data, *stbl, b"co64")
    if co64 is not None:
        count = struct.unpack(">I", data[co64[0] + 4 : co64[0] + 8])[0]
        return list(
            struct.unpack(f">{count}Q", data[co64[0] + 8 : co64[0] + 8 + 8 * count])
        )
    return None


def mux_m4a(track: AacTrack) -> bytes:
    """Mux raw AAC-LC frames into a minimal single-track `.m4a` file."""
    asc = _asc_bytes(track.sample_rate_hz, track.channel_count)
    esds = _fullbox(
        b"esds",
        0,
        0,
        # ES_Descriptor (0x03) / DecoderConfigDescriptor (0x04, AAC) /
        # DecoderSpecificInfo (0x05) carrying the 2-byte ASC.
        b"\x03\x19\x00\x00\x00"
        b"\x04\x11\x40\x15" + bytes(3 + 4 + 4) + b"\x05\x02" + asc + b"\x06\x01\x02",
    )
    mp4a_entry = (
        bytes(6)
        + struct.pack(">H", 1)
        + bytes(8)
        + struct.pack(">HHI", track.channel_count, 16, track.sample_rate_hz << 16)
        + esds
    )
    mp4a = struct.pack(">I", 8 + len(mp4a_entry)) + b"mp4a" + mp4a_entry

    frames = track.frames
    count = len(frames)
    ticks = count * _SAMPLES_PER_FRAME
    ms = round(ticks * 1000 / track.sample_rate_hz)
    sizes = [len(frame) for frame in frames]

    ftyp = _box(b"ftyp", b"M4A " + struct.pack(">I", 0) + b"M4A ")
    mvhd = _fullbox(
        b"mvhd",
        0,
        0,
        struct.pack(">IIII", 0, 0, 1000, ms)
        + struct.pack(">I", 0x00010000)
        + struct.pack(">H", 0x0100)
        + bytes(10)
        + bytes(36)
        + bytes(24)
        + struct.pack(">I", 2),
    )
    tkhd = _fullbox(
        b"tkhd",
        0,
        7,
        struct.pack(">IIII", 0, 0, 1, 0)
        + struct.pack(">I", ms)
        + bytes(8)
        + struct.pack(">HHhH", 0, 0, 0x0100, 0)
        + bytes(36)
        + struct.pack(">II", 0, 0),
    )
    mdhd = _fullbox(
        b"mdhd",
        0,
        0,
        struct.pack(">IIII", 0, 0, track.sample_rate_hz, ticks)
        + struct.pack(">HH", 0x55C4, 0),
    )
    hdlr = _fullbox(
        b"hdlr", 0, 0, struct.pack(">I", 0) + b"soun" + bytes(12) + b"SoundHandler\x00"
    )
    smhd = _fullbox(b"smhd", 0, 0, struct.pack(">H", 0) + bytes(2))
    url = _fullbox(b"url ", 0, 1, b"")
    dinf = _box(b"dinf", _fullbox(b"dref", 0, 0, struct.pack(">I", 1) + url))

    stsd = _fullbox(b"stsd", 0, 0, struct.pack(">I", 1) + mp4a)
    stts = _fullbox(
        b"stts", 0, 0, struct.pack(">I", 1) + struct.pack(">II", count, _SAMPLES_PER_FRAME)
    )
    stsc = _fullbox(b"stsc", 0, 0, struct.pack(">I", 1) + struct.pack(">III", 1, count, 1))
    stsz = _fullbox(
        b"stsz", 0, 0, struct.pack(">II", 0, count) + struct.pack(f">{count}I", *sizes)
    )
    stco_ph = _fullbox(b"stco", 0, 0, struct.pack(">I", 1) + struct.pack(">I", 0))
    moov_ph = _moov(mvhd, tkhd, mdhd, hdlr, smhd, dinf, stsd, stts, stsc, stsz, stco_ph)
    chunk_offset = len(ftyp) + len(moov_ph) + 8
    stco = _fullbox(
        b"stco", 0, 0, struct.pack(">I", 1) + struct.pack(">I", chunk_offset)
    )
    moov = _moov(mvhd, tkhd, mdhd, hdlr, smhd, dinf, stsd, stts, stsc, stsz, stco)
    assert len(moov) == len(moov_ph)
    mdat = struct.pack(">I", 8 + sum(sizes)) + b"mdat" + b"".join(frames)
    return ftyp + moov + mdat


def _moov(
    mvhd: bytes,
    tkhd: bytes,
    mdhd: bytes,
    hdlr: bytes,
    smhd: bytes,
    dinf: bytes,
    stsd: bytes,
    stts: bytes,
    stsc: bytes,
    stsz: bytes,
    stco: bytes,
) -> bytes:
    stbl = _box(b"stbl", stsd + stts + stsc + stsz + stco)
    minf = _box(b"minf", smhd + dinf + stbl)
    mdia = _box(b"mdia", mdhd + hdlr + minf)
    return _box(b"moov", mvhd + _box(b"trak", tkhd + mdia))


def _asc_bytes(sample_rate_hz: int, channel_count: int) -> bytes:
    """Two-byte AudioSpecificConfig for AAC-LC. Raises KeyError for odd rates."""
    frequency_index = _SAMPLE_RATES.index(sample_rate_hz)
    return bytes(
        [
            (_AAC_LC << 3) | (frequency_index >> 1),
            ((frequency_index & 0x01) << 7) | ((channel_count & 0x0F) << 3),
        ]
    )


def _box(typ: bytes, payload: bytes) -> bytes:
    return struct.pack(">I", 8 + len(payload)) + typ + payload


def _fullbox(typ: bytes, version: int, flags: int, payload: bytes) -> bytes:
    return _box(typ, struct.pack(">I", (version << 24) | flags) + payload)


def _children(data: bytes, start: int, end: int, typ: bytes) -> list[tuple[int, int]]:
    """Direct child boxes of type `typ` as (content_start, content_end) ranges."""
    found = []
    pos = start
    while pos + 8 <= end:
        size = struct.unpack(">I", data[pos : pos + 4])[0]
        if size == 1:
            size = struct.unpack(">Q", data[pos + 8 : pos + 16])[0]
            header = 16
        elif size == 0:
            size = end - pos
            header = 8
        else:
            header = 8
        if size < 8 or pos + size > end:
            break
        if data[pos + 4 : pos + 8] == typ:
            found.append((pos + header, pos + size))
        pos += size
    return found


def _child(data: bytes, start: int, end: int, typ: bytes) -> tuple[int, int] | None:
    found = _children(data, start, end, typ)
    return found[0] if found else None
