from pathlib import Path

from tiktokexport.tiktok.models import DownloadedVideo, VideoMetadata
from tiktokexport.tiktok.pipeline import ExportOptions, TikTokExporter


class FakeDownloader:
    def download(
        self,
        url: str,
        work_dir: Path,
        cookies: Path | None = None,
        cookies_from_browser: str | None = None,
    ) -> DownloadedVideo:
        if "bad" in url:
            raise RuntimeError("download failed")

        video_path = work_dir / "123.mp4"
        video_path.write_bytes(b"video")
        return DownloadedVideo(
            metadata=VideoMetadata(
                source_url=url,
                account="@author",
                description="Description",
                video_id="123",
            ),
            video_path=video_path,
        )


class FakeTranscriber:
    def transcribe(self, video_path: Path, reporter=None) -> str:
        return "Transcript text."


def test_export_urls_continues_after_failures_and_writes_successes(tmp_path: Path) -> None:
    exporter = TikTokExporter(downloader=FakeDownloader(), transcriber=FakeTranscriber())

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
    assert (tmp_path / "2026-05-14_author_123.mp4").read_bytes() == b"video"
    markdown = (tmp_path / "2026-05-14_author_123.md").read_text(encoding="utf-8")
    assert "Transcript text." in markdown


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
    assert not (tmp_path / "2026-05-14_author_123.md").exists()
