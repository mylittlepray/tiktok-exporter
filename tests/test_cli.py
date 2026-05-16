from pathlib import Path

import typer
import pytest

from tiktokexport.cli import (
    _collect_audio_paths,
    _collect_urls,
    _resolve_output_dir,
    _validate_device,
    _validate_transcript_format,
)
from tiktokexport.config import AppConfig


def test_resolve_output_dir_uses_project_export_default(
    monkeypatch,
    tmp_path: Path,
) -> None:
    expected = tmp_path / "export"

    monkeypatch.setattr("tiktokexport.cli.load_config", lambda: AppConfig())
    monkeypatch.setattr("tiktokexport.cli.default_output_dir", lambda: expected)

    assert _resolve_output_dir(None) == expected.resolve()


def test_validate_device_normalizes_known_values() -> None:
    assert _validate_device(" CUDA ") == "cuda"


def test_validate_device_rejects_unknown_values() -> None:
    with pytest.raises(typer.BadParameter):
        _validate_device("metal")


def test_validate_transcript_format_normalizes_known_values() -> None:
    assert _validate_transcript_format(".TXT") == "txt"


def test_validate_transcript_format_rejects_unknown_values() -> None:
    with pytest.raises(typer.BadParameter):
        _validate_transcript_format("srt")


def test_collect_urls_accepts_multiple_urls() -> None:
    assert _collect_urls(["https://a", "https://b", "https://a"], None) == [
        "https://a",
        "https://b",
    ]


def test_collect_audio_paths_from_directory(tmp_path: Path) -> None:
    first = tmp_path / "a.mp3"
    second = tmp_path / "b.wav"
    ignored = tmp_path / "notes.txt"
    first.write_bytes(b"audio")
    second.write_bytes(b"audio")
    ignored.write_text("text", encoding="utf-8")

    assert _collect_audio_paths(None, tmp_path, recursive=False) == [
        first.resolve(),
        second.resolve(),
    ]
