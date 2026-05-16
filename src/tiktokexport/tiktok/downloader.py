from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from tiktokexport.core.ffmpeg import imageio_ffmpeg_path
from tiktokexport.tiktok.models import DownloadedVideo, VideoMetadata


class TikTokDownloadError(RuntimeError):
    pass


class TikTokDownloader:
    def download(
        self,
        url: str,
        work_dir: Path,
        cookies: Path | None = None,
        cookies_from_browser: str | None = None,
    ) -> DownloadedVideo:
        try:
            from yt_dlp import YoutubeDL
        except ImportError as exc:
            raise TikTokDownloadError(
                "yt-dlp is not installed. Run `uv sync` before exporting videos."
            ) from exc

        work_dir.mkdir(parents=True, exist_ok=True)

        options: dict[str, Any] = {
            "format": "bv*+ba/best",
            "merge_output_format": "mp4",
            "outtmpl": str(work_dir / "%(id)s.%(ext)s"),
            "noprogress": True,
            "quiet": True,
            "no_warnings": True,
            "windowsfilenames": True,
        }

        ffmpeg_path = imageio_ffmpeg_path()
        if ffmpeg_path is not None:
            options["ffmpeg_location"] = str(ffmpeg_path)
        if cookies is not None:
            options["cookiefile"] = str(cookies)
        if cookies_from_browser:
            options["cookiesfrombrowser"] = (cookies_from_browser,)

        try:
            with YoutubeDL(options) as ydl:
                info = ydl.extract_info(url, download=True)
        except Exception as exc:
            raise TikTokDownloadError(str(exc)) from exc

        video_path = _downloaded_filepath(info, work_dir)
        metadata = _metadata_from_info(info, fallback_url=url)
        return DownloadedVideo(metadata=metadata, video_path=video_path)


def _downloaded_filepath(info: dict[str, Any], work_dir: Path) -> Path:
    for download in info.get("requested_downloads") or []:
        filepath = download.get("filepath")
        if filepath and Path(filepath).exists():
            return Path(filepath)

    filepath = info.get("filepath")
    if filepath and Path(filepath).exists():
        return Path(filepath)

    video_id = str(info.get("id") or "")
    matches = sorted(work_dir.glob(f"{video_id}.*")) if video_id else sorted(work_dir.iterdir())
    files = [path for path in matches if path.is_file()]
    if files:
        return files[0]

    raise TikTokDownloadError("yt-dlp finished without a downloaded video file.")


def _metadata_from_info(info: dict[str, Any], fallback_url: str) -> VideoMetadata:
    source_url = fallback_url
    video_id = str(info.get("id") or _fallback_video_id(source_url))
    description = str(info.get("description") or info.get("title") or "").strip()
    account = _account_from_info(info, fallback_url=fallback_url)

    return VideoMetadata(
        source_url=source_url,
        account=account,
        description=description,
        video_id=video_id,
    )


def _account_from_info(info: dict[str, Any], fallback_url: str = "") -> str:
    for raw in _account_candidates(info, fallback_url):
        account = str(raw).strip().removeprefix("@")
        if account and not account.isdigit():
            return f"@{account}"

    account = str(info.get("uploader_id") or info.get("channel_id") or "unknown").strip()
    if not account:
        account = "unknown"
    if not account.startswith("@"):
        account = f"@{account}"
    return account


def _account_candidates(info: dict[str, Any], fallback_url: str) -> list[str]:
    candidates: list[str] = []
    for key in ("uploader", "channel", "creator", "artist", "uploader_id", "channel_id"):
        value = info.get(key)
        if value:
            candidates.append(str(value))

    for key in ("webpage_url", "original_url", "url"):
        value = info.get(key)
        if value:
            candidates.extend(_accounts_from_url(str(value)))
    if fallback_url:
        candidates.extend(_accounts_from_url(fallback_url))

    return candidates


def _accounts_from_url(url: str) -> list[str]:
    return [match.group(1) for match in re.finditer(r"/@([^/?#]+)", url)]


def _fallback_video_id(source_url: str) -> str:
    return hashlib.sha1(source_url.encode("utf-8")).hexdigest()[:12]
