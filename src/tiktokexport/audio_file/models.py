from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from tiktokexport.core.models import ProcessingFailure


TranscriptFormat = Literal["md", "txt"]


@dataclass(frozen=True)
class AudioTranscriptionOptions:
    output_dir: Path
    model_name: str = "turbo"
    device: str = "auto"
    output_format: TranscriptFormat = "md"
    fail_fast: bool = False
    created_at: str | None = None


@dataclass(frozen=True)
class TranscribedAudio:
    source_path: Path
    transcript_path: Path


@dataclass(frozen=True)
class AudioTranscriptionFailure(ProcessingFailure):
    source_path: Path

    def __init__(self, source_path: Path, error: str) -> None:
        object.__setattr__(self, "source", str(source_path))
        object.__setattr__(self, "source_path", source_path)
        object.__setattr__(self, "error", error)


@dataclass(frozen=True)
class AudioTranscriptionSummary:
    successes: tuple[TranscribedAudio, ...]
    failures: tuple[AudioTranscriptionFailure, ...]

