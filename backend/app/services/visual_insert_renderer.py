"""Render source-grounded typography and charts as silent six-second MP4 inserts."""

from functools import partial
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from app.schemas.packaging import VisualInsertIdea
from app.services.video_tools import run_ffmpeg_command

_FONTS = Path(__file__).resolve().parents[1] / "assets" / "fonts"
_BG = "#191A2C"
_INK = "#F3F1FA"
_MUTED = "#B2B4CB"
_COLORS = ("#7DDCD2", "#CAB2FC", "#F4C788", "#88B6F5", "#E9A8BC")


def _lines(draw: ImageDraw.ImageDraw, text: str, font, width: int) -> list[str]:
    lines: list[str] = []
    current = ""
    for word in text.split():
        candidate = f"{current} {word}".strip()
        if draw.textlength(candidate, font=font) <= width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
            # Very long tokens still fit the canvas; they are never silently clipped.
            while draw.textlength(current, font=font) > width:
                cut = len(current) - 1
                while cut > 1 and draw.textlength(current[:cut], font=font) > width:
                    cut -= 1
                lines.append(current[:cut])
                current = current[cut:]
    if current:
        lines.append(current)
    return lines


def _text(
    draw,
    text: str,
    xy: tuple[int, int],
    width: int,
    size: int,
    max_lines: int,
    *,
    color: str = _INK,
    bold: bool = False,
    events: list[str],
) -> int:
    font_path = _FONTS / ("Poppins-Bold.ttf" if bold else "Poppins-Regular.ttf")
    while True:
        font = ImageFont.truetype(str(font_path), size)
        lines = _lines(draw, text, font, width)
        if len(lines) <= max_lines or size <= 12:
            break
        size -= 2
    y = xy[1]
    red, green, blue = color[1:3], color[3:5], color[5:7]
    for line in lines:
        # libass supplies HarfBuzz shaping (Hindi, Arabic, etc.), even when the
        # Pillow wheel lacks libraqm. Pillow is used only for layout and bars.
        text = line.replace("\\", "＼").replace("{", "(").replace("}", ")")
        override = (
            f"{{\\an7\\pos({xy[0]},{y})\\fs{round(size * 1.3)}"
            f"\\b{1 if bold else 0}\\c&H{blue}{green}{red}&}}"
        )
        events.append(f"Dialogue: 0,0:00:00.00,0:00:06.00,Default,,0,0,0,,{override}{text}")
        y += int(size * 1.5)
    return y


def render_graphic(
    idea: VisualInsertIdea,
    *,
    aspect_ratio: str,
    tmpdir: str,
    ffmpeg_path: str,
) -> str:
    """72 bounded raster frames; FFmpeg encodes at 24fps for editing compatibility."""
    width, height = (1280, 720) if aspect_ratio == "16:9" else (720, 1280)
    padding = 64 if width > height else 40
    available = width - 2 * padding
    vertical = height > width
    events: list[str] = []
    for index in range(72):
        image = Image.new("RGB", (width, height), _BG)
        draw = ImageDraw.Draw(image)
        events.clear()
        draw_text = partial(_text, draw, events=events)
        progress = min(1.0, index / 18)
        ease = 1 - (1 - progress) ** 3
        draw.rounded_rectangle(
            (padding, padding, padding + 48, padding + 6), radius=3, fill=_COLORS[0]
        )
        y = draw_text(
            idea.headline,
            (padding, padding + 22),
            available,
            34 if idea.kind == "chart" else (46 if not vertical else 40),
            2 if idea.kind == "chart" else 3,
            bold=True,
        )
        y = draw_text(
            idea.body,
            (padding, y + 10),
            available,
            18 if idea.kind == "chart" else 24,
            3,
            color=_MUTED,
        )
        if idea.kind == "chart":
            # Horizontal bars keep labels readable on both landscape and vertical cuts.
            y += 28 if not vertical else 48
            maximum = max((point.value for point in idea.chart), default=1) or 1
            row = min(110 if vertical else 72, (height - y - 90) // len(idea.chart))
            for i, point in enumerate(idea.chart):
                value = f"{point.value:,}".removesuffix(".0")
                if unit := idea.chartUnit.strip():
                    value += ("" if unit.startswith("%") else " ") + unit
                draw_text(point.label, (padding, y), available - 190, 21, 1)
                draw_text(
                    value, (width - padding - 180, y), 180, 21, 1, color=_COLORS[i], bold=True
                )
                top = y + 34
                draw.rounded_rectangle(
                    (padding, top, width - padding, top + 13), radius=6, fill="#303249"
                )
                length = int(available * point.value / maximum * ease)
                if length > 0:
                    draw.rounded_rectangle(
                        (padding, top, padding + length, top + 13), radius=6, fill=_COLORS[i]
                    )
                y += row
        else:
            # The quote is an editorial anchor; no fabricated supporting numbers.
            y = max(y + 40, int(height * 0.46))
            draw.rectangle((padding, y, padding + 5, height - padding - 55), fill=_COLORS[1])
            quote = " ".join(idea.sourceQuote.split())
            if len(quote) > 240:
                quote = quote[:237].rsplit(" ", 1)[0] + "…"
            draw_text(
                quote,
                (padding + 24, y),
                available - 24,
                32 if not vertical else 29,
                6,
                color=_COLORS[1],
            )
        start = idea.sourceStartMs // 1000
        stamp = f"{start // 60:02d}:{start % 60:02d}  /  FROM THE VIDEO"
        draw_text(stamp, (padding, height - padding), available, 16, 1, color=_MUTED)
        image.save(Path(tmpdir) / f"frame-{index:03d}.png")
    output = str(Path(tmpdir) / "insert.mp4")
    ass = Path(tmpdir) / "insert.ass"
    ass.write_text(
        f"[Script Info]\nScriptType: v4.00+\nPlayResX: {width}\nPlayResY: {height}\n"
        "WrapStyle: 2\nScaledBorderAndShadow: yes\n\n[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
        "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
        "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        "Style: Default,Poppins,24,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,"
        "0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1\n\n[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
        + "\n".join(events)
        + "\n",
        encoding="utf-8",
    )

    def filter_value(value: Path) -> str:
        return "'" + str(value).replace("\\", "/").replace(":", "\\:").replace("'", "\\'") + "'"

    run_ffmpeg_command(
        [
            ffmpeg_path,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-framerate",
            "12",
            "-i",
            str(Path(tmpdir) / "frame-%03d.png"),
            "-vf",
            f"ass=filename={filter_value(ass)}:fontsdir={filter_value(_FONTS)}",
            "-t",
            "6",
            "-r",
            "24",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "20",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            output,
        ],
        timeout_seconds=120,
    )
    return output
