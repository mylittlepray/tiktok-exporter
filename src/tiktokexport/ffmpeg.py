from __future__ import annotations

import os
import shutil
from pathlib import Path

from platformdirs import user_cache_dir

from .config import APP_NAME


def imageio_ffmpeg_path() -> Path | None:
    try:
        import imageio_ffmpeg
    except ImportError:
        return None

    try:
        return Path(imageio_ffmpeg.get_ffmpeg_exe())
    except Exception:
        return None


def ensure_ffmpeg_command_on_path() -> None:
    ffmpeg_path = imageio_ffmpeg_path()
    if ffmpeg_path is None:
        return

    executable = _ensure_ffmpeg_executable_name(ffmpeg_path)
    _prepend_to_path(executable.parent)


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
