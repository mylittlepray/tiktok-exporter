import json
from pathlib import Path

import pytest

from tiktokexport.core.models import DownloadedPost, MediaAsset, MediaKind, SourceMetadata
from tiktokexport.tiktok.models import ExportOptions
from tiktokexport.tiktok.pipeline import TikTokExporter


class FakeDownloader:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def download(
        self,
        url: str,
        work_dir: Path,
        cookies: Path | None = None,
        cookies_from_browser: str | None = None,
    ) -> DownloadedPost:
        self.calls.append(url)
        if "bad" in url:
            raise RuntimeError("download failed")
        if "interrupt" in url:
            raise KeyboardInterrupt()

        metadata = SourceMetadata(
            source_url=url,
            account="@author",
            description="Slideshow description." if "photo" in url else "Short description.",
            source_id="123",
            duration_seconds=0.0 if "photo" in url else 12.5,
        )

        if "photo" in url:
            first = work_dir / "first.jpg"
            second = work_dir / "second.webp"
            first.write_bytes(b"photo1")
            second.write_bytes(b"photo2")
            return DownloadedPost(
                metadata=metadata,
                kind=MediaKind.PHOTO_SLIDESHOW,
                assets=(
                    MediaAsset(kind=MediaKind.PHOTO, path=first, sequence=1),
                    MediaAsset(kind=MediaKind.PHOTO, path=second, sequence=2),
                ),
            )

        video_path = work_dir / "123.mp4"
        video_path.write_bytes(b"video")
        return DownloadedPost(
            metadata=metadata,
            kind=MediaKind.VIDEO,
            assets=(MediaAsset(kind=MediaKind.VIDEO, path=video_path),),
        )


class FakeTranscriber:
    def __init__(self) -> None:
        self.calls: list[Path] = []

    def transcribe(self, video_path: Path, reporter=None) -> str:
        self.calls.append(video_path)
        return "Transcript text."


class FailingTranscriber:
    def transcribe(self, video_path: Path, reporter=None) -> str:
        raise RuntimeError("whisper failed")


@pytest.fixture(autouse=True)
def reports_dir(monkeypatch, tmp_path: Path) -> Path:
    report_dir = tmp_path / "reports"
    monkeypatch.setattr(
        "tiktokexport.tiktok.report._default_reports_dir",
        lambda: report_dir,
    )
    monkeypatch.setattr(
        "tiktokexport.tiktok.pipeline.write_export_report",
        lambda summary: __import__("tiktokexport.tiktok.report", fromlist=["write_export_report"]).write_export_report(
            summary,
            reports_dir=report_dir,
        ),
    )
    return report_dir


def test_export_urls_continues_after_failures_and_writes_video_successes(
    tmp_path: Path,
    reports_dir: Path,
) -> None:
    transcriber = FakeTranscriber()
    exporter = TikTokExporter(downloader=FakeDownloader(), transcriber=transcriber)

    summary = exporter.export_urls(
        [
            "https://www.tiktok.com/@author/video/123",
            "https://www.tiktok.com/@bad/video/456",
        ],
        ExportOptions(output_dir=tmp_path, created_at="2026-05-14"),
    )

    assert len(summary.successes) == 1
    assert len(summary.failures) == 1
    assert summary.failures[0].source_url == "https://www.tiktok.com/@bad/video/456"
    assert (tmp_path / "@author - Short description.mp4").read_bytes() == b"video"
    markdown = (tmp_path / "@author - Short description.md").read_text(encoding="utf-8")
    assert "Transcript text." in markdown
    assert transcriber.calls == [tmp_path / "@author - Short description.mp4"]
    assert summary.report_path is not None
    assert summary.report_path.parent == reports_dir
    report = json.loads(summary.report_path.read_text(encoding="utf-8"))
    assert report["successful_exports"] == 1
    assert report["error_exports"] == 1
    assert report["unprocessed_exports"] == 0
    assert report["transcription_failed"] == 0
    assert report["successful"][0]["url"] == "https://www.tiktok.com/@author/video/123"
    assert report["successful"][0]["duration_seconds"] == 12.5
    assert report["successful"][0]["export_duration_seconds"] >= 0
    assert report["successful"][0]["exported_at"]
    assert report["successful"][0]["details"] == {
        "status": "success",
        "transcription": "success",
    }
    assert report["errors"] == [
        {
            "url": "https://www.tiktok.com/@bad/video/456",
            "error": "download failed",
            "details": "download failed",
        }
    ]
    assert report["unprocessed"] == []


def test_export_video_can_skip_transcription(tmp_path: Path) -> None:
    transcriber = FakeTranscriber()
    exporter = TikTokExporter(downloader=FakeDownloader(), transcriber=transcriber)

    summary = exporter.export_urls(
        ["https://www.tiktok.com/@author/video/123"],
        ExportOptions(output_dir=tmp_path, transcribe=False, created_at="2026-05-14"),
    )

    assert len(summary.successes) == 1
    assert transcriber.calls == []
    assert summary.successes[0].details.status == "success"
    assert summary.successes[0].details.transcription == "skipped"
    markdown = (tmp_path / "@author - Short description.md").read_text(encoding="utf-8")
    assert "## Транскрипт" not in markdown
    assert "media_type: video" in markdown


def test_export_video_records_transcription_failure_without_failing_export(
    tmp_path: Path,
) -> None:
    exporter = TikTokExporter(downloader=FakeDownloader(), transcriber=FailingTranscriber())

    summary = exporter.export_urls(
        ["https://www.tiktok.com/@author/video/123"],
        ExportOptions(output_dir=tmp_path, created_at="2026-05-14"),
    )

    assert len(summary.successes) == 1
    assert len(summary.failures) == 0
    assert summary.successes[0].details.status == "success"
    assert summary.successes[0].details.transcription == "whisper failed"
    markdown = (tmp_path / "@author - Short description.md").read_text(encoding="utf-8")
    assert "## Транскрипт" not in markdown
    report = json.loads(summary.report_path.read_text(encoding="utf-8"))
    assert report["successful_exports"] == 1
    assert report["error_exports"] == 0
    assert report["unprocessed_exports"] == 0
    assert report["transcription_failed"] == 1
    assert report["successful"][0]["details"] == {
        "status": "success",
        "transcription": "whisper failed",
    }


def test_export_skips_url_when_note_with_source_url_already_exists(tmp_path: Path) -> None:
    existing = tmp_path / "existing.md"
    existing.write_text(
        "---\nsource_url: https://www.tiktok.com/@author/video/123\nmedia_type: video\n---\n\n# Existing\n",
        encoding="utf-8",
    )
    downloader = FakeDownloader()
    exporter = TikTokExporter(downloader=downloader, transcriber=FakeTranscriber())

    summary = exporter.export_urls(
        ["https://www.tiktok.com/@author/video/123"],
        ExportOptions(output_dir=tmp_path, created_at="2026-05-14"),
    )

    assert downloader.calls == []
    assert len(summary.successes) == 1
    assert summary.successes[0].markdown_path == existing
    assert summary.successes[0].details.status == "already downloaded"
    report = json.loads(summary.report_path.read_text(encoding="utf-8"))
    assert report["successful_exports"] == 1
    assert report["successful"][0]["details"] == {
        "status": "already downloaded",
        "transcription": "skipped",
    }


def test_export_interrupt_writes_report_with_unprocessed_urls(tmp_path: Path) -> None:
    exporter = TikTokExporter(downloader=FakeDownloader(), transcriber=FakeTranscriber())

    summary = exporter.export_urls(
        [
            "https://www.tiktok.com/@author/video/123",
            "https://www.tiktok.com/@author/video/interrupt",
            "https://www.tiktok.com/@author/video/not-reached",
        ],
        ExportOptions(output_dir=tmp_path, created_at="2026-05-14"),
    )

    assert summary.interrupted is True
    assert len(summary.successes) == 1
    assert len(summary.failures) == 0
    assert [item.source_url for item in summary.unprocessed] == [
        "https://www.tiktok.com/@author/video/interrupt",
        "https://www.tiktok.com/@author/video/not-reached",
    ]
    report = json.loads(summary.report_path.read_text(encoding="utf-8"))
    assert report["successful_exports"] == 1
    assert report["error_exports"] == 0
    assert report["unprocessed_exports"] == 2
    assert report["unprocessed"] == [
        {
            "url": "https://www.tiktok.com/@author/video/interrupt",
            "details": "interrupted",
        },
        {
            "url": "https://www.tiktok.com/@author/video/not-reached",
            "details": "interrupted",
        },
    ]


def test_export_photo_slideshow_creates_subfolder_note_and_numbered_photos(tmp_path: Path) -> None:
    transcriber = FakeTranscriber()
    exporter = TikTokExporter(downloader=FakeDownloader(), transcriber=transcriber)

    summary = exporter.export_urls(
        ["https://www.tiktok.com/@author/video/photo"],
        ExportOptions(output_dir=tmp_path, created_at="2026-05-14"),
    )

    note_dir = tmp_path / "@author - Slideshow description"
    markdown_path = note_dir / "@author - Slideshow description.md"
    first_photo = note_dir / "01. PHOTO - @author - Slideshow description.jpg"
    second_photo = note_dir / "02. PHOTO - @author - Slideshow description.webp"

    assert len(summary.successes) == 1
    assert summary.successes[0].media_kind == MediaKind.PHOTO_SLIDESHOW
    assert summary.successes[0].media_duration_seconds == 0.0
    assert summary.successes[0].details.status == "success"
    assert summary.successes[0].details.transcription == "skipped"
    assert markdown_path.exists()
    assert first_photo.read_bytes() == b"photo1"
    assert second_photo.read_bytes() == b"photo2"
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "media_type: photo_slideshow" in markdown
    assert "![[01. PHOTO - @author - Slideshow description.jpg]]" in markdown
    assert "![[02. PHOTO - @author - Slideshow description.webp]]" in markdown
    assert transcriber.calls == []


def test_export_urls_fail_fast_stops_after_first_failure(tmp_path: Path) -> None:
    exporter = TikTokExporter(downloader=FakeDownloader(), transcriber=FakeTranscriber())

    summary = exporter.export_urls(
        [
            "https://www.tiktok.com/@bad/video/456",
            "https://www.tiktok.com/@author/video/123",
        ],
        ExportOptions(output_dir=tmp_path, fail_fast=True, created_at="2026-05-14"),
    )

    assert len(summary.successes) == 0
    assert len(summary.failures) == 1
    assert not (tmp_path / "@author - Short description.md").exists()
