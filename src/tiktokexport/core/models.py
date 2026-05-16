from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


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

