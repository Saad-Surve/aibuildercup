"""Caption style presets and the ASS subtitle builder.

Burning captions "beautifully" means controlling libass, and libass wants ASS. This module
turns transcript segments plus a `CaptionStyle` into an ASS document, then FFmpeg renders it
over the video (`caption_worker`).

Everything here is pure: no FFmpeg, no storage, no I/O beyond reading the bundled font
directory path. That keeps styling logic easy to reason about and to reuse for the web
preview's presets.

Sizes in `CaptionStyle` are reference pixels at a 1080-tall frame. `build_ass` scales them to
the real video with `min(width, height) / 1080`, so a preset looks the same on landscape 1080p
and vertical 9:16.
"""

from pathlib import Path
from typing import Any, Final

from app.schemas.captions import (
    CaptionBackground,
    CaptionFont,
    CaptionPosition,
    CaptionPreset,
    CaptionStyle,
)

#: Latin faces are bundled; script-specific Noto faces are installed in the runtime image and
#: resolved by libass through fontconfig. The worker still passes this directory so the selected
#: Montserrat/Poppins face is deterministic for Latin-script captions.
FONTS_DIR: Final = (Path(__file__).resolve().parent.parent / "assets" / "fonts").resolve()

REFERENCE_MIN_DIMENSION: Final = 1080

# These family names are provided by Debian's fonts-noto-core/fonts-noto-cjk packages. Keep
# this map aligned with the dubbing catalog in `services/dubbing.py`: Latin-script languages
# deliberately retain the creator's selected Montserrat/Poppins face.
_SCRIPT_FONTS: Final[dict[str, str]] = {
    "ar": "Noto Sans Arabic",
    "bn": "Noto Sans Bengali",
    "gu": "Noto Sans Gujarati",
    "hi": "Noto Sans Devanagari",
    "ja": "Noto Sans CJK JP",
    "kn": "Noto Sans Kannada",
    "ko": "Noto Sans CJK KR",
    "ml": "Noto Sans Malayalam",
    "mr": "Noto Sans Devanagari",
    "pa": "Noto Sans Gurmukhi",
    "ta": "Noto Sans Tamil",
    "te": "Noto Sans Telugu",
    "th": "Noto Sans Thai",
    "ur": "Noto Sans Arabic",
    "yue": "Noto Sans CJK HK",
    "zh": "Noto Sans CJK SC",
}

#: Presets the UI offers. The defaults in `CaptionStyle` mirror the `clean` preset.
_PRESETS: Final[tuple[CaptionPreset, ...]] = (
    CaptionPreset(
        id="clean",
        label="Clean",
        description="Crisp white text with a tight outline. Safe on any footage.",
        style=CaptionStyle(
            preset="clean",
            fontFamily=CaptionFont.montserrat,
            fontSize=54,
            bold=True,
            textColor="#FFFFFF",
            outlineColor="#000000",
            outlineWidth=2,
            shadow=2,
            background=CaptionBackground.outline,
            position=CaptionPosition.bottom,
        ),
    ),
    CaptionPreset(
        id="bold_pop",
        label="Bold Pop",
        description="Big, uppercase, high-contrast — built for short-form feeds.",
        style=CaptionStyle(
            preset="bold_pop",
            fontFamily=CaptionFont.montserrat,
            fontSize=64,
            bold=True,
            uppercase=True,
            textColor="#FFFFFF",
            outlineColor="#000000",
            outlineWidth=5,
            shadow=3,
            background=CaptionBackground.outline,
            position=CaptionPosition.bottom,
            marginV=92,
            maxCharsPerLine=26,
            highlightEnabled=True,
            highlightColor="#FFD400",
        ),
    ),
    CaptionPreset(
        id="boxed",
        label="Boxed",
        description="White text on a translucent black plate. Maximum readability.",
        style=CaptionStyle(
            preset="boxed",
            fontFamily=CaptionFont.poppins,
            fontSize=50,
            bold=False,
            textColor="#FFFFFF",
            backgroundColor="#000000",
            backgroundOpacity=60,
            background=CaptionBackground.box,
            outlineWidth=2,
            shadow=0,
            position=CaptionPosition.bottom,
        ),
    ),
    CaptionPreset(
        id="karaoke",
        label="Karaoke",
        description="Words fill in as they are spoken. Energetic and modern.",
        style=CaptionStyle(
            preset="karaoke",
            fontFamily=CaptionFont.poppins,
            fontSize=56,
            bold=True,
            textColor="#FFFFFF",
            outlineColor="#000000",
            outlineWidth=4,
            shadow=2,
            background=CaptionBackground.outline,
            position=CaptionPosition.bottom,
            highlightEnabled=True,
            highlightColor="#7CFF6B",
        ),
    ),
    CaptionPreset(
        id="minimal",
        label="Minimal",
        description="Small, understated, lifted off the bottom edge. Documentary feel.",
        style=CaptionStyle(
            preset="minimal",
            fontFamily=CaptionFont.montserrat,
            fontSize=44,
            bold=False,
            textColor="#F5F5F5",
            outlineColor="#000000",
            outlineWidth=2,
            shadow=0,
            background=CaptionBackground.none,
            position=CaptionPosition.bottom,
            marginV=140,
            maxCharsPerLine=40,
        ),
    ),
)

PRESETS: Final[dict[str, CaptionPreset]] = {preset.id: preset for preset in _PRESETS}


def preset_list() -> list[CaptionPreset]:
    return list(_PRESETS)


def default_style() -> CaptionStyle:
    return CaptionStyle()


def _scale(width: int, height: int) -> float:
    if width <= 0 or height <= 0:
        return 1.0
    return max(0.4, min(2.5, min(width, height) / REFERENCE_MIN_DIMENSION))


def _ass_color(hex_color: str, opacity: int = 100) -> str:
    """`#RRGGBB` -> ASS `&HAABBGGRR` (alpha 00 opaque, FF transparent)."""
    value = hex_color.lstrip("#")
    red, green, blue = value[0:2], value[2:4], value[4:6]
    alpha = round((100 - max(0, min(100, opacity))) / 100 * 255)
    return f"&H{alpha:02X}{blue}{green}{red}"


def _ass_timestamp(ms: int) -> str:
    ms = max(0, int(ms))
    hours, remainder = divmod(ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, millis = divmod(remainder, 1000)
    return f"{hours:d}:{minutes:02d}:{seconds:02d}.{millis // 10:02d}"


def _escape_ass(text: str) -> str:
    # Curly braces would open an override block; newlines become hard breaks.
    return text.replace("\\", "\\\\").replace("{", "(").replace("}", ")").replace("\n", "\\N")


def _language_base(language: str | None) -> str:
    if not language:
        return ""
    return language.replace("_", "-").split("-", 1)[0].lower()


#: Scripts written without spaces between words: wrap them by character instead of by word.
_UNSPACED_LANGUAGES: Final = frozenset({"ja", "zh", "yue"})


def caption_font_family(selected_font: str, language: str | None) -> str:
    """Return a libass/fontconfig family that contains the caption language's script."""
    return _SCRIPT_FONTS.get(_language_base(language), selected_font)


def _layout_word_lists(
    words: list[str], max_chars: int, max_lines: int, joiner: str = " "
) -> tuple[list[list[str]], bool]:
    lines: list[list[str]] = []
    current: list[str] = []
    for word in words:
        if current and len(joiner.join([*current, word])) > max_chars:
            lines.append(current)
            current = [word]
        else:
            current.append(word)
    if current:
        lines.append(current)
    truncated = len(lines) > max_lines
    return lines[:max_lines], truncated


def _word_timings(word_lists: list[list[str]], duration_cs: int) -> list[int]:
    """Split a cue's duration across its visible words by length, summing exactly."""
    words = [word for line in word_lists for word in line]
    if not words:
        return []
    weights = [max(1, len(word)) for word in words]
    total_weight = sum(weights)
    timings: list[int] = []
    remaining = max(1, duration_cs)
    for index, weight in enumerate(weights):
        if index == len(weights) - 1:
            timings.append(max(1, remaining))
            break
        share = max(1, round(duration_cs * weight / total_weight))
        share = min(share, max(1, remaining - (len(weights) - index - 1)))
        timings.append(share)
        remaining -= share
    return timings


def _cue_text(
    segment: dict[str, Any], style: CaptionStyle, *, supports_uppercase: bool
) -> str:
    text = str(segment.get("text", "")).strip()
    if style.uppercase and supports_uppercase:
        text = text.upper()
    return text


def _speaker_prefix(segment: dict[str, Any], labels: dict[str, str]) -> str:
    speaker = segment.get("speaker")
    if speaker is None:
        return ""
    name = labels.get(str(speaker)) or f"Speaker {speaker}"
    return f"{name}: "


def _render_cue(
    segment: dict[str, Any],
    style: CaptionStyle,
    *,
    supports_uppercase: bool,
    unspaced: bool = False,
) -> str:
    text = _cue_text(segment, style, supports_uppercase=supports_uppercase)
    if not text:
        return ""
    # CJK has no word spaces and each glyph is about twice as wide as a Latin letter, so
    # wrap by character with half the per-line budget.
    joiner = "" if unspaced else " "
    words = [char for char in text if not char.isspace()] if unspaced else text.split()
    max_chars = max(1, style.maxCharsPerLine // 2) if unspaced else style.maxCharsPerLine
    word_lists, truncated = _layout_word_lists(words, max_chars, style.maxLines, joiner)
    if not word_lists:
        return ""
    suffix = "…" if truncated else ""

    if not style.highlightEnabled:
        body = "\\N".join(_escape_ass(joiner.join(line)) for line in word_lists) + suffix
        return body

    duration_cs = max(1, int((int(segment.get("endMs", 0)) - int(segment.get("startMs", 0))) / 10))
    timings = _word_timings(word_lists, duration_cs)
    flat_index = 0
    rendered_lines: list[str] = []
    for line in word_lists:
        rendered_words: list[str] = []
        for word in line:
            cs = timings[flat_index] if flat_index < len(timings) else 1
            rendered_words.append(f"{{\\k{cs}}}{_escape_ass(word)}")
            flat_index += 1
        rendered_lines.append(joiner.join(rendered_words))
    return "\\N".join(rendered_lines) + suffix


def build_ass(
    segments: list[dict[str, Any]],
    style: CaptionStyle,
    *,
    width: int,
    height: int,
    language: str | None = None,
    speaker_labels: dict[str, str] | None = None,
) -> str:
    """Render transcript segments into an ASS document for `style` at `width`x`height`."""
    labels = speaker_labels or {}
    speakers = {
        segment.get("speaker")
        for segment in segments
        if segment.get("speaker") is not None
    }
    show_speakers = style.speakerLabels and len(speakers) > 1

    scale = _scale(width, height)
    font_size = max(12, round(style.fontSize * scale))
    margin_lr = round(40 * scale)
    margin_v = round(style.marginV * scale)
    alignment = {
        CaptionPosition.bottom: 2,
        CaptionPosition.middle: 5,
        CaptionPosition.top: 8,
    }[style.position]

    if style.background == CaptionBackground.box:
        border_style = 3
        outline = max(6, round(font_size * 0.22))
        outline_colour = _ass_color(style.backgroundColor, style.backgroundOpacity)
    else:
        border_style = 1
        outline = (
            round(style.outlineWidth * scale)
            if style.background == CaptionBackground.outline
            else 0
        )
        outline_colour = _ass_color(style.outlineColor)

    primary = (
        _ass_color(style.highlightColor)
        if style.highlightEnabled
        else _ass_color(style.textColor)
    )
    secondary = _ass_color(style.textColor)
    back_colour = _ass_color(style.outlineColor, 40)
    font_family = caption_font_family(style.fontFamily.value, language)
    supports_uppercase = _language_base(language) not in _SCRIPT_FONTS

    header = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {max(1, int(width))}",
        f"PlayResY: {max(1, int(height))}",
        "WrapStyle: 2",
        "ScaledBorderAndShadow: yes",
        "YCbCr Matrix: TV.709",
        "",
        "[V4+ Styles]",
        (
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
            "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, "
            "ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, "
            "MarginL, MarginR, MarginV, Encoding"
        ),
        (
            "Style: Default,"
            f"{font_family},{font_size},{primary},{secondary},"
            f"{outline_colour},{back_colour},"
            f"{-1 if style.bold else 0},{-1 if style.italic else 0},0,0,"
            f"100,100,0,0,{border_style},{outline},{round(style.shadow * scale)},{alignment},"
            f"{margin_lr},{margin_lr},{margin_v},1"
        ),
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]

    events: list[str] = []
    for segment in segments:
        body = _render_cue(
            segment,
            style,
            supports_uppercase=supports_uppercase,
            unspaced=_language_base(language) in _UNSPACED_LANGUAGES,
        )
        if not body:
            continue
        text = body
        if show_speakers:
            prefix = _escape_ass(_speaker_prefix(segment, labels))
            if prefix:
                text = f"{prefix}{body}"
        start = _ass_timestamp(int(segment.get("startMs", 0)))
        end = _ass_timestamp(int(segment.get("endMs", 0)))
        if end == start:
            continue
        events.append(
            f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}"
        )

    return "\n".join([*header, *events]) + "\n"


__all__ = [
    "FONTS_DIR",
    "PRESETS",
    "REFERENCE_MIN_DIMENSION",
    "build_ass",
    "caption_font_family",
    "default_style",
    "preset_list",
]
