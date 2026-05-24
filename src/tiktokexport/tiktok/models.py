from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from tiktokexport.core.models import MediaKind, ProcessingFailure


@dataclass(frozen=True)
class ExportOptions:
    output_dir: Path
    model_name: str = "turbo"
    cookies: Path | None = None
    cookies_from_browser: str | None = None
    fail_fast: bool = False
    device: str = "auto"
    transcribe: bool = True
    created_at: str | None = None


@dataclass(frozen=True)
class ExportDetails:
    status: str
    transcription: str


@dataclass(frozen=True)
class ExportedNote:
    source_url: str
    markdown_path: Path
    media_paths: tuple[Path, ...]
    media_kind: MediaKind
    media_duration_seconds: float
    export_duration_seconds: float
    exported_at: str
    details: ExportDetails


@dataclass(frozen=True)
class ExportFailure(ProcessingFailure):
    source_url: str

    def __init__(self, source_url: str, error: str) -> None:
        object.__setattr__(self, "source", source_url)
        object.__setattr__(self, "source_url", source_url)
        object.__setattr__(self, "error", error)


@dataclass(frozen=True)
class UnprocessedExport:
    source_url: str
    details: str


@dataclass(frozen=True)
class ExportSummary:
    successes: tuple[ExportedNote, ...]
    failures: tuple[ExportFailure, ...]
    unprocessed: tuple[UnprocessedExport, ...] = ()
    report_path: Path | None = None
    interrupted: bool = False
