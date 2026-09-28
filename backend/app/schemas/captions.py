"""Caption burn-in schemas.

`CaptionStyle` is the single source of truth for how burned captions look: the API validates
it, `caption_styles.build_ass` renders it with libass, and the web client hydrates its controls
from `GET /caption-presets`. Sizes are expressed in pixels relative to a 1080-tall reference
frame so one preset looks right on 720p, 1080p, and vertical video.
"""

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class CaptionFont(StrEnum):
    """Families bundled in `app/assets/fonts` so rendering is reproducible everywhere."""

    montserrat = "Montserrat"
    poppins = "Poppins"


class CaptionPosition(StrEnum):
    top = "top"
    middle = "middle"
    bottom = "bottom"


class CaptionBackground(StrEnum):
    outline = "outline"
    box = "box"
    none = "none"


_HEX = "#[0-9A-Fa-f]{6}"


class CaptionStyle(BaseModel):
    """How a burned caption looks. Every field has a sane default (the `clean` preset)."""

    preset: str = "clean"
    fontFamily: CaptionFont = CaptionFont.montserrat
    #: Font size in pixels at a 1080-tall reference frame; scaled to the real video.
    fontSize: int = Field(default=54, ge=18, le=140)
    bold: bool = True
    italic: bool = False
    uppercase: bool = False
    textColor: str = Field(default="#FFFFFF", pattern=_HEX)
    outlineColor: str = Field(default="#000000", pattern=_HEX)
    #: Outline thickness in reference pixels; also pads the box when `background == "box"`.
    outlineWidth: int = Field(default=3, ge=0, le=16)
    shadow: int = Field(default=2, ge=0, le=16)
    background: CaptionBackground = CaptionBackground.outline
    backgroundColor: str = Field(default="#000000", pattern=_HEX)
    backgroundOpacity: int = Field(default=60, ge=0, le=100)
    position: CaptionPosition = CaptionPosition.bottom
    #: Distance from the top/bottom edge in reference pixels (ignored when centred).
    marginV: int = Field(default=72, ge=0, le=600)
    maxCharsPerLine: int = Field(default=32, ge=12, le=64)
    maxLines: int = Field(default=2, ge=1, le=4)
    #: Karaoke highlight: the spoken words fill with `highlightColor`.
    highlightEnabled: bool = False
    highlightColor: str = Field(default="#FFD400", pattern=_HEX)
    #: Prefix each cue with the speaker name when the transcript has more than one speaker.
    speakerLabels: bool = False

    @field_validator(
        "textColor", "outlineColor", "backgroundColor", "highlightColor", mode="after"
    )
    @classmethod
    def _upper_hex(cls, value: str) -> str:
        return value.upper()


class CaptionRenderRequest(BaseModel):
    style: CaptionStyle = Field(default_factory=CaptionStyle)
    #: Render a specific saved transcript generation; defaults to the active one.
    transcriptVersion: int | None = None
    #: Optional human name stored on the render (used for the downloaded file name).
    fileName: str | None = Field(default=None, max_length=200)


class CaptionRenderStatus(StrEnum):
    queued = "queued"
    rendering = "rendering"
    ready = "ready"
    failed = "failed"


class CaptionRender(BaseModel):
    captionRenderId: str
    projectId: str
    status: CaptionRenderStatus
    style: CaptionStyle
    sourceAssetId: str | None = None
    sourceTranscriptId: str | None = None
    transcriptVersion: int | None = None
    fileName: str | None = None
    storagePath: str | None = None
    assStoragePath: str | None = None
    mimeType: str = "video/mp4"
    sizeBytes: int = 0
    durationMs: int = 0
    width: int = 0
    height: int = 0
    jobId: str | None = None
    error: dict[str, Any] | None = None
    #: Short-lived signed URL, minted on read for ready renders only.
    downloadUrl: str | None = None
    createdAt: datetime
    updatedAt: datetime


class CaptionRenderList(BaseModel):
    items: list[CaptionRender]


class CaptionRenderAccepted(BaseModel):
    captionRenderId: str
    jobId: str
    status: str


class CaptionPreset(BaseModel):
    id: str
    label: str
    description: str
    style: CaptionStyle


class CaptionPresetList(BaseModel):
    items: list[CaptionPreset]
