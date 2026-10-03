"""Dubbing / localization schemas.

A *localization* is one request to dub a project's source video into a target language:
translate the transcript (when needed), synthesize one Text-to-Speech take per segment,
duration-normalize each take into its window, and mux the track onto the video.

`LocalizationVoiceList` is the single source of truth for the languages and voices the UI
offers; it is built from the catalog in `app/services/dubbing.py`, which the worker uses to
resolve a voice id to a real Cloud TTS voice. Registering a new language means adding one
catalog entry — no schema or UI change.
"""

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class VoiceGender(StrEnum):
    male = "male"
    female = "female"
    neutral = "neutral"


class LocalizationStatus(StrEnum):
    queued = "queued"
    translating = "translating"
    synthesizing = "synthesizing"
    muxing = "muxing"
    ready = "ready"
    failed = "failed"


class LocalizationRequest(BaseModel):
    #: Short BCP-47 code, for example `en`. The catalog decides which are supported.
    targetLanguage: str = Field(min_length=2, max_length=16)
    #: Preferred voice id for the first speaker; later speakers borrow later catalog voices.
    voice: str | None = Field(default=None, max_length=128)
    transcriptVersion: int | None = None
    keepOriginalAudio: bool = False
    fileName: str | None = Field(default=None, max_length=200)


class LocalizationVoice(BaseModel):
    id: str
    #: Provider voice name (for example `en-US-Neural2-D`). Present in responses so the client
    #: can show it, but never trusted as input.
    name: str
    label: str
    gender: VoiceGender


class LocalizationLanguage(BaseModel):
    language: str
    label: str
    voices: list[LocalizationVoice]


class LocalizationVoiceList(BaseModel):
    items: list[LocalizationLanguage]


class Localization(BaseModel):
    localizationId: str
    projectId: str
    status: LocalizationStatus
    sourceAssetId: str | None = None
    sourceTranscriptId: str | None = None
    transcriptVersion: int | None = None
    sourceLanguage: str | None = None
    targetLanguage: str
    voice: str | None = None
    speakerVoices: dict[str, str] = Field(default_factory=dict)
    keepOriginalAudio: bool = False
    fileName: str | None = None
    videoStoragePath: str | None = None
    audioStoragePath: str | None = None
    captionsStoragePath: str | None = None
    mimeType: str = "video/mp4"
    sizeBytes: int = 0
    durationMs: int = 0
    width: int = 0
    height: int = 0
    jobId: str | None = None
    error: dict[str, Any] | None = None
    #: Short-lived signed URL, minted on read for ready dubs only.
    downloadUrl: str | None = None
    #: Short-lived signed URL for the localized SRT, when one was generated.
    captionsUrl: str | None = None
    #: Corpus and glossary versions this dub was built with, for reproducibility.
    corpusVersion: int = 0
    glossaryVersion: int = 0
    createdAt: datetime
    updatedAt: datetime


class LocalizationList(BaseModel):
    items: list[Localization]


class LocalizationAccepted(BaseModel):
    localizationId: str
    jobId: str
    status: str


class GlossaryTerm(BaseModel):
    source: str = Field(min_length=1, max_length=200)
    target: str = Field(min_length=1, max_length=400)
    #: Short target-language code this term applies to (`hi`, `es`). Empty means any target.
    targetLanguage: str = Field(default="", max_length=16)


class Glossary(BaseModel):
    """The single versioned glossary attached to a project."""

    projectId: str
    sourceLanguage: str = "en"
    terms: list[GlossaryTerm] = Field(default_factory=list)
    version: int = 0
    updatedAt: datetime | None = None


class GlossaryUpdate(BaseModel):
    sourceLanguage: str = Field(default="en", min_length=2, max_length=16)
    terms: list[GlossaryTerm] = Field(default_factory=list, max_length=2000)
    #: Optimistic concurrency: reject the write when the stored version differs.
    expectedVersion: int | None = None


class CorpusLanguagePair(BaseModel):
    sourceLanguage: str
    targetLanguage: str


class GlobalCorpus(BaseModel):
    """The bundled global corpus: its version and the pairs it covers."""

    version: int
    pairs: list[CorpusLanguagePair]
