from pathlib import Path

import yaml

from tiktokexport.core.markdown import MarkdownNote, render_markdown_note
from tiktokexport.core.models import DownloadedPost, MediaAsset, MediaKind, SourceMetadata
from tiktokexport.tiktok.pipeline import render_tiktok_photo_note, render_tiktok_video_note


def test_render_markdown_note_contains_frontmatter_and_sections() -> None:
    markdown = render_markdown_note(
        MarkdownNote(
            title="Note title",
            frontmatter={"created_at": "2026-05-14", "tags": ["x"]},
            sections=(("Описание", "Body text."),),
        )
    )

    _, frontmatter, body = markdown.split("---", 2)
    parsed = yaml.safe_load(frontmatter)

    assert parsed["created_at"] == "2026-05-14"
    assert parsed["tags"] == ["x"]
    assert "# Note title" in body
    assert "## Описание" in body


def test_render_tiktok_video_note_contains_video_frontmatter_and_transcript() -> None:
    markdown = render_tiktok_video_note(
        downloaded=_downloaded_video(),
        created_at="2026-05-14",
        video_filename="@author - Video description.mp4",
        transcript="Full transcript.",
    )

    _, frontmatter, body = markdown.split("---", 2)
    parsed = yaml.safe_load(frontmatter)

    assert parsed["created_at"] == "2026-05-14"
    assert parsed["tags"] == ["tiktok", "video"]
    assert parsed["account"] == "@author"
    assert parsed["media_type"] == "video"
    assert parsed["video_file"] == "@author - Video description.mp4"
    assert "## Описание" in body
    assert "## Транскрипт" in body
    assert "Full transcript." in body


def test_render_tiktok_photo_note_contains_photo_frontmatter_and_embeds() -> None:
    markdown = render_tiktok_photo_note(
        downloaded=_downloaded_photo(),
        created_at="2026-05-14",
        photo_filenames=("01. PHOTO - @author - Photo post.jpg",),
    )

    _, frontmatter, body = markdown.split("---", 2)
    parsed = yaml.safe_load(frontmatter)

    assert parsed["media_type"] == "photo_slideshow"
    assert parsed["photo_files"] == ["01. PHOTO - @author - Photo post.jpg"]
    assert "## Содержание" in body
    assert "![[01. PHOTO - @author - Photo post.jpg]]" in body


def _metadata(description: str) -> SourceMetadata:
    return SourceMetadata(
        source_url="https://www.tiktok.com/@author/video/123",
        account="@author",
        description=description,
        source_id="123",
    )


def _downloaded_video() -> DownloadedPost:
    return DownloadedPost(
        metadata=_metadata("Video description"),
        kind=MediaKind.VIDEO,
        assets=(MediaAsset(kind=MediaKind.VIDEO, path=Path("unused.mp4")),),
    )


def _downloaded_photo() -> DownloadedPost:
    return DownloadedPost(
        metadata=_metadata("Photo post"),
        kind=MediaKind.PHOTO_SLIDESHOW,
        assets=(MediaAsset(kind=MediaKind.PHOTO, path=Path("unused.jpg")),),
    )
