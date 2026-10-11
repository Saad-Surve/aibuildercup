from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CreatorLibraryNode(BaseModel):
    id: str
    itemId: str
    title: str
    kind: Literal["video", "article", "post", "profile"]
    modality: Literal["text", "image"]
    excerpt: str
    url: str | None = None
    thumbnailUrl: str | None = None
    startSeconds: float | None = None
    indexed: bool = False
    x: float | None = None
    y: float | None = None
    score: float | None = None


class CreatorLibrary(BaseModel):
    sourceType: Literal["folder_import", "youtube"] | None = None
    displayName: str = "Your creator library"
    model: str
    dimensions: int
    itemCount: int = 0
    totalNodes: int = 0
    indexedNodes: int = 0
    omittedPassages: int = 0
    nodes: list[CreatorLibraryNode] = Field(default_factory=list)
    projection: Literal["pca"] = "pca"
    errorMessage: str | None = None


class CreatorLibraryQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=1, max_length=1000)

    @field_validator("query")
    @classmethod
    def strip_query(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Enter a search query")
        return value.strip()


class CreatorLibrarySearch(BaseModel):
    mode: Literal["semantic", "lexical"]
    matches: list[CreatorLibraryNode]
