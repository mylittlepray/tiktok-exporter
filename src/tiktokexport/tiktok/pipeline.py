from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Protocol

from tiktokexport.core.files import ensure_output_dir
from tiktokexport.core.filenames import build_base_filename, unique_base_path
from tiktokexport.core.markdown import MarkdownDocument, render_transcript_markdown
from tiktokexport.core.transcriber import WhisperTranscriber
from tiktokexport.progress import ExportReporter
from tiktokexport.tiktok.downloader import TikTokDownloader
from tiktokexport.tiktok.models import DownloadedVideo, ExportedNote, ExportFailure, ExportSummary


class Downloader(Protocol):
    def download(
        self,
        url: str,
        work_dir: Path,
        cookies: Path | None = None,
        cookies_from_browser: str | None = None,
    ) -> DownloadedVideo:
        ...


class Transcriber(Protocol):
    def transcribe(
        self,
        media_path: Path,
        reporter: ExportReporter | None = None,
    ) -> str:
        ...


@dataclass(frozen=True)
class ExportOptions:
    output_dir: Path
    model_name: str = "turbo"
    cookies: Path | None = None
    cookies_from_browser: str | None = None
    fail_fast: bool = False
    device: str = "auto"
    created_at: str | None = None


class TikTokExporter:
    def __init__(
        self,
        downloader: Downloader | None = None,
        transcriber: Transcriber | None = None,
    ) -> None:
        self.downloader = downloader or TikTokDownloader()
        self.transcriber = transcriber

    def export_urls(
        self,
        urls: list[str],
        options: ExportOptions,
        reporter: ExportReporter | None = None,
    ) -> ExportSummary:
        successes: list[ExportedNote] = []
        failures: list[ExportFailure] = []
        transcriber = self.transcriber or WhisperTranscriber(
            options.model_name,
            device=options.device,
        )
        if reporter is not None:
            reporter.start_batch(len(urls))

        for index, url in enumerate(urls, start=1):
            if reporter is not None:
                reporter.start_video(index, len(urls), url)
            try:
                successes.append(self.export_one(url, options, transcriber, reporter))
                if reporter is not None:
                    reporter.success(successes[-1].markdown_path)
            except Exception as exc:
                failures.append(ExportFailure(source_url=url, error=str(exc)))
                if reporter is not None:
                    reporter.failure(url, str(exc))
                if options.fail_fast:
                    break

        return ExportSummary(successes=tuple(successes), failures=tuple(failures))

    def export_one(
        self,
        url: str,
        options: ExportOptions,
        transcriber: Transcriber | None = None,
        reporter: ExportReporter | None = None,
    ) -> ExportedNote:
        output_dir = ensure_output_dir(options.output_dir)
        created_at = options.created_at or date.today().isoformat()
        transcriber = transcriber or self.transcriber or WhisperTranscriber(options.model_name)

        with tempfile.TemporaryDirectory(prefix="tiktokexport-") as temp_dir_raw:
            temp_dir = Path(temp_dir_raw)
            if reporter is not None:
                reporter.stage("Downloading video")
            downloaded = self.downloader.download(
                url,
                temp_dir,
                cookies=options.cookies,
                cookies_from_browser=options.cookies_from_browser,
            )
            transcript = transcriber.transcribe(downloaded.video_path, reporter=reporter)

            video_suffix = downloaded.video_path.suffix or ".mp4"
            base = build_base_filename(
                created_at,
                downloaded.metadata.account,
                downloaded.metadata.video_id,
            )
            base = unique_base_path(output_dir, base, (".md", video_suffix))
            video_path = output_dir / f"{base}{video_suffix}"
            markdown_path = output_dir / f"{base}.md"

            if reporter is not None:
                reporter.stage("Saving Markdown note and video")
            shutil.move(str(downloaded.video_path), video_path)
            markdown = render_tiktok_markdown(
                downloaded=downloaded,
                created_at=created_at,
                video_filename=video_path.name,
                transcript=transcript,
            )
            markdown_path.write_text(markdown, encoding="utf-8")

        return ExportedNote(
            source_url=url,
            markdown_path=markdown_path,
            video_path=video_path,
        )


def render_tiktok_markdown(
    *,
    downloaded: DownloadedVideo,
    created_at: str,
    video_filename: str,
    transcript: str,
) -> str:
    metadata = downloaded.metadata
    description = metadata.description.strip() or "Описание отсутствует."
    return render_transcript_markdown(
        MarkdownDocument(
            title=f"TikTok - {metadata.account or '@unknown'}",
            transcript=transcript,
            frontmatter={
                "created_at": created_at,
                "tags": ["tiktok"],
                "source_url": metadata.source_url,
                "account": metadata.account,
                "description": metadata.description,
                "video_file": video_filename,
            },
            sections=(
                (
                    "Источник",
                    (
                        f"- Оригинал: {metadata.source_url}\n"
                        f"- Аккаунт: {metadata.account or '@unknown'}\n"
                        f"- Локальное видео: {video_filename}"
                    ),
                ),
                ("Описание", description),
            ),
        )
    )
