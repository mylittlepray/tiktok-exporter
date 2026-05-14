from pathlib import Path

from tiktokexport.ffmpeg import _ensure_ffmpeg_executable_name


def test_ensure_ffmpeg_executable_name_returns_existing_ffmpeg_name(tmp_path: Path) -> None:
    ffmpeg = tmp_path / "ffmpeg.exe"
    ffmpeg.write_bytes(b"ffmpeg")

    assert _ensure_ffmpeg_executable_name(ffmpeg) == ffmpeg
