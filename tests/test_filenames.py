from pathlib import Path

from tiktokexport.core.filenames import (
    build_base_filename,
    sanitize_component,
    sanitize_filename,
    summarize_sentence_for_filename,
    unique_base_path,
)


def test_sanitize_component_removes_windows_unsafe_characters() -> None:
    assert sanitize_component('@Bad: Name?/<>*"') == "bad_name"


def test_build_base_filename_uses_date_author_and_id() -> None:
    assert build_base_filename("2026-05-14", "@Author", "12345") == "2026-05-14_author_12345"


def test_unique_base_path_adds_counter_when_any_output_exists(tmp_path: Path) -> None:
    (tmp_path / "2026-05-14_author_123.md").write_text("", encoding="utf-8")

    assert unique_base_path(tmp_path, "2026-05-14_author_123", (".md", ".mp4")) == (
        "2026-05-14_author_123_2"
    )


def test_sanitize_filename_keeps_spaces_and_removes_unsafe_characters() -> None:
    assert sanitize_filename('@Author - Bad: Name?/<>*"#^[tag]|') == "@Author - Bad Name tag"


def test_summarize_sentence_for_filename_prefers_sentence_boundary() -> None:
    text = "First sentence. Second sentence is too long for the filename limit."

    assert summarize_sentence_for_filename(text, limit=30) == "First sentence."


def test_summarize_sentence_for_filename_uses_first_limit_when_boundary_too_short() -> None:
    assert summarize_sentence_for_filename("A. Long sentence continues here", limit=20) == (
        "A. Long sentence con"
    )
