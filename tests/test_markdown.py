from pathlib import Path

import yaml

from tiktokexport.tiktok.models import DownloadedVideo, VideoMetadata
from tiktokexport.tiktok.pipeline import render_tiktok_markdown


def test_render_markdown_contains_frontmatter_and_transcript() -> None:
    markdown = render_tiktok_markdown(
        downloaded=DownloadedVideo(
            metadata=VideoMetadata(
                source_url="https://www.tiktok.com/@author/video/123",
                account="@author",
                description="Video description",
                video_id="123",
            ),
            video_path=Path("unused.mp4"),
        ),
        created_at="2026-05-14",
        video_filename="@author - Video description.mp4",
        transcript="Full transcript.",
    )

    _, frontmatter, body = markdown.split("---", 2)
    parsed = yaml.safe_load(frontmatter)

    assert parsed["created_at"] == "2026-05-14"
    assert parsed["tags"] == ["tiktok"]
    assert parsed["account"] == "@author"
    assert parsed["video_file"] == "@author - Video description.mp4"
    assert "Оригинал:" not in body
    assert "Аккаунт:" not in body
    assert "Локальное видео:" not in body
    assert "## Описание" in body
    assert "## Содержание" in body
    assert "Full transcript." in body
