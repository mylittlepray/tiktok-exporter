from __future__ import annotations

from pathlib import Path
from typing import Protocol

from tiktokexport.core.models import DownloadedPost
from tiktokexport.progress import ExportReporter


class MediaDownloader(Protocol):
    def download(
        self,
        url: str,
        work_dir: Path,
        cookies: Path | None = None,
        cookies_from_browser: str | None = None,
    ) -> DownloadedPost:
        ...


class Transcriber(Protocol):
    def transcribe(
        self,
        media_path: Path,
        reporter: ExportReporter | None = None,
    ) -> str:
        ...


class OcrRecognizer(Protocol):
    def recognize(
        self,
        image_path: Path,
        reporter: ExportReporter | None = None,
    ) -> str:
        ...


class TagGenerator(Protocol):
    def generate_tags(
        self,
        *,
        description: str,
        transcript: str = "",
        ocr_text: str = "",
    ) -> list[str]:
        ...


class NoOpOcrRecognizer:
    def recognize(
        self,
        image_path: Path,
        reporter: ExportReporter | None = None,
    ) -> str:
        return ""


class NoOpTagGenerator:
    def generate_tags(
        self,
        *,
        description: str,
        transcript: str = "",
        ocr_text: str = "",
    ) -> list[str]:
        return []
