"""Dubbing helpers: the voice catalog and pure track assembly.

The worker does the I/O (Cloud TTS, FFmpeg, Storage); this module owns the two pieces that
must be exactly reproducible and easy to reason about:

- The **voice catalog**: which languages and voices dubbing offers. English is the first
  fully supported target, but the catalog is language-agnostic, so adding a language is one
  entry here and nothing else changes.
- The **timeline math**: place each synthesized segment on one PCM timeline, trimming it to
  its window and writing a mono 16-bit WAV.

Nothing here touches a Google SDK, FFmpeg, or Firestore.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from io import BytesIO


@dataclass(frozen=True)
class Voice:
    #: Stable id the API accepts and stores (`voice` on a localization).
    id: str
    #: Cloud Text-to-Speech voice name (`en-US-Neural2-D`).
    name: str
    label: str
    gender: str
    #: Full BCP-47 code Text-to-Speech expects (`en-US`).
    language_code: str


@dataclass(frozen=True)
class Language:
    code: str
    label: str
    voices: tuple[Voice, ...]


def _v(
    vid: str, name: str, gender: str, language_code: str, label: str
) -> Voice:
    return Voice(id=vid, name=name, label=label, gender=gender, language_code=language_code)


#: Languages offered by the dubbing feature. The first voice in each list is the default.
CATALOG: tuple[Language, ...] = (
    Language(
        code="en",
        label="English",
        voices=(
            _v("en-us-david", "en-US-Neural2-D", "male", "en-US", "David — US male"),
            _v("en-us-aria", "en-US-Neural2-F", "female", "en-US", "Aria — US female"),
            _v("en-gb-sonia", "en-GB-Neural2-A", "female", "en-GB", "Sonia — UK female"),
            _v("en-au-matilda", "en-AU-Wavenet-A", "female", "en-AU", "Matilda — AU female"),
        ),
    ),
    Language(
        code="hi",
        label="Hindi",
        voices=(
            _v("hi-in-prabhat", "hi-IN-Wavenet-B", "male", "hi-IN", "Prabhat — Hindi male"),
            _v("hi-in-aditi", "hi-IN-Wavenet-A", "female", "hi-IN", "Aditi — Hindi female"),
            _v("hi-in-viraj", "hi-IN-Wavenet-D", "male", "hi-IN", "Viraj — Hindi male"),
        ),
    ),
    Language(
        code="es",
        label="Spanish",
        voices=(
            _v("es-es-nestor", "es-ES-Wavenet-B", "male", "es-ES", "Néstor — ES male"),
            _v("es-es-lucia", "es-ES-Wavenet-C", "female", "es-ES", "Lucía — ES female"),
            _v("es-us-elena", "es-US-Neural2-A", "female", "es-US", "Elena — US female"),
        ),
    ),
    Language(
        code="fr",
        label="French",
        voices=(
            _v("fr-fr-henri", "fr-FR-Wavenet-B", "male", "fr-FR", "Henri — FR male"),
            _v("fr-fr-amelie", "fr-FR-Wavenet-A", "female", "fr-FR", "Amélie — FR female"),
            _v("fr-ca-lea", "fr-CA-Neural2-A", "female", "fr-CA", "Léa — CA female"),
        ),
    ),
    Language(
        code="de",
        label="German",
        voices=(
            _v("de-de-hans", "de-DE-Wavenet-B", "male", "de-DE", "Hans — DE male"),
            _v("de-de-anna", "de-DE-Wavenet-A", "female", "de-DE", "Anna — DE female"),
            _v("de-de-viktor", "de-DE-Wavenet-D", "male", "de-DE", "Viktor — DE male"),
        ),
    ),
    Language(
        code="pt",
        label="Portuguese",
        voices=(
            _v("pt-br-ricardo", "pt-BR-Wavenet-B", "male", "pt-BR", "Ricardo — BR male"),
            _v("pt-br-camila", "pt-BR-Wavenet-A", "female", "pt-BR", "Camila — BR female"),
        ),
    ),
    Language(
        code="ja",
        label="Japanese",
        voices=(
            _v("ja-jp-takumi", "ja-JP-Wavenet-B", "male", "ja-JP", "Takumi — JP male"),
            _v("ja-jp-mizuki", "ja-JP-Wavenet-A", "female", "ja-JP", "Mizuki — JP female"),
        ),
    ),
    Language(
        code="ar",
        label="Arabic",
        voices=(
            _v("ar-xa-tarik", "ar-XA-Wavenet-B", "male", "ar-XA", "Tarik — Arabic male"),
            _v("ar-xa-hala", "ar-XA-Wavenet-A", "female", "ar-XA", "Hala — Arabic female"),
        ),
    ),
)


def catalog() -> tuple[Language, ...]:
    return CATALOG


def base_code(code: str | None) -> str:
    """Normalise `en-US`/`en_US` to the catalog key `en`."""
    if not code:
        return ""
    return code.replace("_", "-").split("-", 1)[0].lower()


def find_language(code: str | None) -> Language | None:
    wanted = base_code(code)
    for language in CATALOG:
        if language.code == wanted:
            return language
    return None


def find_voice(language_code: str | None, voice_id: str | None) -> Voice | None:
    language = find_language(language_code)
    if language is None or not voice_id:
        return None
    for voice in language.voices:
        if voice.id == voice_id or voice.name == voice_id:
            return voice
    return None


def default_voice(language_code: str | None, preferred: str | None) -> Voice:
    """Resolve the voice for the first speaker.

    Raises `ValueError` when the language is not in the catalog, so the API can reject an
    unsupported `targetLanguage` instead of failing later inside the worker.
    """
    language = find_language(language_code)
    if language is None or not language.voices:
        raise ValueError(f"Unsupported target language: {language_code!r}")
    chosen = find_voice(language_code, preferred)
    return chosen or language.voices[0]


def assign_voices(
    language_code: str, preferred_voice_id: str | None, speakers: Iterable[int | None]
) -> dict[int | None, Voice]:
    """Pick a voice per diarized speaker, cycling through the language catalog.

    Speaker 0 (the first distinct speaker) always gets the preferred voice. `None` (an
    undiarized transcript) is treated as one speaker.
    """
    ordered: list[int | None] = []
    for speaker in speakers:
        if speaker not in ordered:
            ordered.append(speaker)
    if not ordered:
        ordered = [None]

    first = default_voice(language_code, preferred_voice_id)
    language = find_language(language_code)
    assert language is not None  # default_voice proved it exists
    rest = [voice for voice in language.voices if voice.id != first.id]
    pool = [first, *rest]

    return {speaker: pool[index % len(pool)] for index, speaker in enumerate(ordered)}


# --------------------------------------------------------------------- timeline


def samples_for(ms: int, sample_rate_hz: int) -> int:
    if ms <= 0:
        return 0
    return round(ms * sample_rate_hz / 1000)


def tempo_for(
    actual_ms: int, target_ms: int, *, min_tempo: float, max_tempo: float
) -> float:
    """Pitch-preserving tempo that squeezes `actual_ms` into `target_ms`.

    Returns 1.0 when either duration is unknown. The result is clamped, so the caller still
    has to trim (too long) or pad (too short) the decoded audio.
    """
    if actual_ms <= 0 or target_ms <= 0:
        return 1.0
    tempo = actual_ms / target_ms
    return max(min_tempo, min(max_tempo, tempo))


def build_track_wav(
    placements: Sequence[tuple[int, int, bytes]],
    *,
    total_ms: int,
    sample_rate_hz: int,
) -> bytes:
    """Assemble `(startMs, endMs, pcm_s16le_mono)` takes onto one silent timeline.

    Each take is trimmed to its window so segments never overlap; a take shorter than its
    window leaves silence. Returns a complete WAV file as bytes.
    """
    import wave

    total_samples = samples_for(total_ms, sample_rate_hz)
    buffer = bytearray(total_samples * 2)
    for start_ms, end_ms, pcm in placements:
        start = samples_for(max(0, start_ms), sample_rate_hz)
        window = max(0, samples_for(end_ms, sample_rate_hz) - start)
        if window <= 0 or not pcm:
            continue
        byte_start = start * 2
        byte_end = byte_start + window * 2
        if byte_start >= len(buffer):
            continue
        byte_end = min(byte_end, len(buffer))
        chunk = pcm[: byte_end - byte_start]
        buffer[byte_start : byte_start + len(chunk)] = chunk

    out = BytesIO()
    with wave.open(out, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate_hz)
        handle.writeframes(bytes(buffer))
    return out.getvalue()
