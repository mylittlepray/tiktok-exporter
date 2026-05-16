from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from platformdirs import user_cache_dir

from ..config import APP_NAME


AUDIO_SUFFIXES = frozenset(
    {
        ".aac",
        ".aiff",
        ".alac",
        ".flac",
        ".m4a",
        ".mp3",
        ".oga",
        ".ogg",
        ".opus",
        ".wav",
        ".wma",
    }
)

VIDEO_SUFFIXES = frozenset(
    {
        ".avi",
        ".m4v",
        ".mkv",
        ".mov",
        ".mp4",
        ".mpeg",
        ".mpg",
        ".webm",
        ".wmv",
    }
)


class MediaConversionError(RuntimeError):
    pass


def imageio_ffmpeg_path() -> Path | None:
    try:
        import imageio_ffmpeg
    except ImportError:
        return None

    try:
        return Path(imageio_ffmpeg.get_ffmpeg_exe())
    except Exception:
        return None


def ffmpeg_command() -> str:
    ffmpeg_path = imageio_ffmpeg_path()
    if ffmpeg_path is None:
        return "ffmpeg"
    return str(_ensure_ffmpeg_executable_name(ffmpeg_path))


def ensure_ffmpeg_command_on_path() -> None:
    ffmpeg_path = imageio_ffmpeg_path()
    if ffmpeg_path is None:
        return

    executable = _ensure_ffmpeg_executable_name(ffmpeg_path)
    _prepend_to_path(executable.parent)


def is_audio_file(path: Path) -> bool:
    return path.suffix.lower() in AUDIO_SUFFIXES


def is_video_file(path: Path) -> bool:
    return path.suffix.lower() in VIDEO_SUFFIXES


def extract_audio(
    source_path: Path,
    output_path: Path,
    *,
    sample_rate: int = 16000,
    channels: int = 1,
) -> Path:
    """Extract normalized audio from a video or audio container with ffmpeg."""
    source_path = source_path.expanduser().resolve()
    output_path = output_path.expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    ensure_ffmpeg_command_on_path()

    command = [
        ffmpeg_command(),
        "-y",
        "-i",
        str(source_path),
        "-vn",
        "-ac",
        str(channels),
        "-ar",
        str(sample_rate),
        str(output_path),
    ]

    try:
        subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError as exc:
        raise MediaConversionError(
            "ffmpeg is not available. Install ffmpeg or run `uv sync` to use imageio-ffmpeg."
        ) from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or str(exc)).strip()
        raise MediaConversionError(f"ffmpeg failed to extract audio: {detail}") from exc

    return output_path


def _ensure_ffmpeg_executable_name(ffmpeg_path: Path) -> Path:
    if ffmpeg_path.name.lower() == "ffmpeg.exe" or ffmpeg_path.name.lower() == "ffmpeg":
        return ffmpeg_path

    shim_dir = Path(user_cache_dir(APP_NAME)) / "ffmpeg"
    shim_dir.mkdir(parents=True, exist_ok=True)
    shim_path = shim_dir / "ffmpeg.exe"

    if _needs_copy(source=ffmpeg_path, target=shim_path):
        shutil.copy2(ffmpeg_path, shim_path)

    return shim_path


def _needs_copy(source: Path, target: Path) -> bool:
    if not target.exists():
        return True
    try:
        source_stat = source.stat()
        target_stat = target.stat()
    except OSError:
        return True

    return source_stat.st_size != target_stat.st_size


def _prepend_to_path(directory: Path) -> None:
    directory_raw = str(directory)
    path_parts = os.environ.get("PATH", "").split(os.pathsep)
    if directory_raw not in path_parts:
        os.environ["PATH"] = os.pathsep.join([directory_raw, *path_parts])

