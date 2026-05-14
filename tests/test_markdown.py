import yaml

from tiktokexport.markdown import MarkdownNote, render_markdown
from tiktokexport.models import VideoMetadata


def test_render_markdown_contains_frontmatter_and_transcript() -> None:
    markdown = render_markdown(
        MarkdownNote(
            created_at="2026-05-14",
            metadata=VideoMetadata(
                source_url="https://www.tiktok.com/@author/video/123",
                account="@author",
                description="Video description",
                video_id="123",
            ),
            video_filename="2026-05-14_author_123.mp4",
            transcript="Full transcript.",
        )
    )

    _, frontmatter, body = markdown.split("---", 2)
    parsed = yaml.safe_load(frontmatter)

    assert parsed["created_at"] == "2026-05-14"
    assert parsed["tags"] == ["tiktok"]
    assert parsed["account"] == "@author"
    assert parsed["video_file"] == "2026-05-14_author_123.mp4"
    assert "## Содержание" in body
    assert "Full transcript." in body
