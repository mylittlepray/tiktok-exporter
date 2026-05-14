from pathlib import Path

from tiktokexport.links import parse_links_file, parse_links_text


def test_parse_links_text_skips_comments_blanks_and_duplicates() -> None:
    assert parse_links_text(
        """
        # comment
        https://www.tiktok.com/@one/video/1

        https://www.tiktok.com/@one/video/1
        https://www.tiktok.com/@two/video/2
        """
    ) == [
        "https://www.tiktok.com/@one/video/1",
        "https://www.tiktok.com/@two/video/2",
    ]


def test_parse_links_file_supports_utf8_sig(tmp_path: Path) -> None:
    path = tmp_path / "links.txt"
    path.write_text("\ufeffhttps://www.tiktok.com/@one/video/1\n", encoding="utf-8")

    assert parse_links_file(path) == ["https://www.tiktok.com/@one/video/1"]
