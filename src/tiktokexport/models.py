from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class VideoMetadata:
    source_url: str
    account: str
    description: str
    video_id: str


@dataclass(frozen=True)
class DownloadedVideo:
    metadata: VideoMetadata
    video_path: Path


@dataclass(frozen=True)
class ExportedNote:
    source_url: str
    markdown_path: Path
    video_path: Path


@dataclass(frozen=True)
class ExportFailure:
    source_url: str
    error: str


@dataclass(frozen=True)
class ExportSummary:
    successes: tuple[ExportedNote, ...]
    failures: tuple[ExportFailure, ...]
