from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SourceFile:
    path: Path


@dataclass(frozen=True)
class GeneratedFile:
    path: Path


@dataclass(frozen=True)
class ProcessingFailure:
    source: str
    error: str


class MediaKind(str, Enum):
    VIDEO = "video"
    PHOTO = "photo"
    PHOTO_SLIDESHOW = "photo_slideshow"
    AUDIO = "audio"


@dataclass(frozen=True)
class SourceMetadata:
    source_url: str
    account: str
    description: str
    source_id: str
    duration_seconds: float = 0.0


@dataclass(frozen=True)
class MediaAsset:
    kind: MediaKind
    path: Path
    sequence: int = 1
    source_url: str | None = None
    role: str = "primary"


@dataclass(frozen=True)
class DownloadedPost:
    metadata: SourceMetadata
    kind: MediaKind
    assets: tuple[MediaAsset, ...]


@dataclass(frozen=True)
class RecognitionResult:
    transcript: str = ""
    ocr_texts: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class NoteContent:
    title: str
    frontmatter: dict[str, Any]
    sections: tuple[tuple[str, str], ...]

