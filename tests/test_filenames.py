from pathlib import Path

from tiktokexport.core.filenames import build_base_filename, sanitize_component, unique_base_path


def test_sanitize_component_removes_windows_unsafe_characters() -> None:
    assert sanitize_component('@Bad: Name?/<>*"') == "bad_name"


def test_build_base_filename_uses_date_author_and_id() -> None:
    assert build_base_filename("2026-05-14", "@Author", "12345") == "2026-05-14_author_12345"


def test_unique_base_path_adds_counter_when_any_output_exists(tmp_path: Path) -> None:
    (tmp_path / "2026-05-14_author_123.md").write_text("", encoding="utf-8")

    assert unique_base_path(tmp_path, "2026-05-14_author_123", (".md", ".mp4")) == (
        "2026-05-14_author_123_2"
    )
