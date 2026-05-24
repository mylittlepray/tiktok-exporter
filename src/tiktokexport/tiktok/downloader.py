from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from tiktokexport.core.ffmpeg import AUDIO_SUFFIXES, imageio_ffmpeg_path
from tiktokexport.core.models import DownloadedPost, MediaAsset, MediaKind, SourceMetadata


class TikTokDownloadError(RuntimeError):
    pass


class TikTokDownloader:
    def download(
        self,
        url: str,
        work_dir: Path,
        cookies: Path | None = None,
        cookies_from_browser: str | None = None,
    ) -> DownloadedPost:
        try:
            from yt_dlp import YoutubeDL
        except ImportError as exc:
            raise TikTokDownloadError(
                "yt-dlp is not installed. Run `uv sync` before exporting media."
            ) from exc

        work_dir.mkdir(parents=True, exist_ok=True)
        options = _ydl_options(work_dir, cookies, cookies_from_browser)

        try:
            with YoutubeDL(options) as ydl:
                info = _extract_info_with_photo_retry(ydl, url)
                metadata = _metadata_from_info(info, fallback_url=url)
                photo_urls = _photo_urls_from_info(info)
                if _is_photo_slideshow(info, photo_urls):
                    if not photo_urls:
                        photo_urls = _photo_urls_from_web_data(ydl, info)
                    if not photo_urls:
                        raise TikTokDownloadError(
                            "TikTok slideshow detected, but no photo URLs were exposed by yt-dlp."
                        )
                    return DownloadedPost(
                        metadata=metadata,
                        kind=MediaKind.PHOTO_SLIDESHOW,
                        assets=_download_photo_assets(ydl, photo_urls, work_dir),
                    )

                video_path = _downloaded_video_filepath(info, work_dir)
                return DownloadedPost(
                    metadata=metadata,
                    kind=MediaKind.VIDEO,
                    assets=(
                        MediaAsset(kind=MediaKind.VIDEO, path=video_path, sequence=1),
                    ),
                )
        except TikTokDownloadError:
            raise
        except Exception as exc:
            raise TikTokDownloadError(str(exc)) from exc


def _extract_info_with_photo_retry(ydl: Any, url: str) -> dict[str, Any]:
    url = _resolve_tiktok_redirect(ydl, url)
    try:
        return ydl.extract_info(_video_compatible_tiktok_url(url), download=True)
    except Exception as exc:
        retry_url = _unsupported_photo_url_from_error(exc)
        if retry_url is None:
            raise
        return ydl.extract_info(_video_compatible_tiktok_url(retry_url), download=True)


def _resolve_tiktok_redirect(ydl: Any, url: str) -> str:
    parsed = urlparse(url)
    if not parsed.netloc.lower().endswith("tiktok.com") or parsed.netloc.lower() in {
        "www.tiktok.com",
        "m.tiktok.com",
    }:
        return url

    try:
        response = ydl.urlopen(url)
    except Exception:
        return url

    try:
        return str(getattr(response, "url", "") or url)
    finally:
        close = getattr(response, "close", None)
        if close is not None:
            close()


def _video_compatible_tiktok_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.netloc.lower().endswith("tiktok.com") and "/photo/" in parsed.path:
        return url.replace("/photo/", "/video/", 1)
    return url


def _unsupported_photo_url_from_error(exc: Exception) -> str | None:
    match = re.search(r"https://www\.tiktok\.com/@[^\s]+/photo/\d+[^\s]*", str(exc))
    if match is None:
        return None
    return match.group(0).rstrip(".,;")


def _photo_urls_from_web_data(ydl: Any, info: dict[str, Any]) -> tuple[str, ...]:
    try:
        from yt_dlp.extractor.tiktok import TikTokIE
    except ImportError:
        return ()

    webpage_url = str(info.get("webpage_url") or info.get("original_url") or "")
    video_id = str(info.get("id") or "")
    if not webpage_url or not video_id:
        return ()

    try:
        extractor = TikTokIE(ydl)
        video_data, status = extractor._extract_web_data_and_status(  # noqa: SLF001
            _video_compatible_tiktok_url(webpage_url),
            video_id,
            fatal=False,
        )
    except Exception:
        return ()

    if status != 0 or not video_data:
        return ()
    return _photo_urls_from_info(video_data)


def _ydl_options(
    work_dir: Path,
    cookies: Path | None,
    cookies_from_browser: str | None,
) -> dict[str, Any]:
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
    return options


def _downloaded_video_filepath(info: dict[str, Any], work_dir: Path) -> Path:
    for download in info.get("requested_downloads") or []:
        filepath = download.get("filepath")
        if filepath and Path(filepath).exists() and not _is_audio_suffix(Path(filepath).suffix):
            return Path(filepath)

    filepath = info.get("filepath")
    if filepath and Path(filepath).exists() and not _is_audio_suffix(Path(filepath).suffix):
        return Path(filepath)

    video_id = str(info.get("id") or "")
    matches = sorted(work_dir.glob(f"{video_id}.*")) if video_id else sorted(work_dir.iterdir())
    files = [path for path in matches if path.is_file() and not _is_audio_suffix(path.suffix)]
    if files:
        return files[0]

    raise TikTokDownloadError("yt-dlp finished without a downloaded video file.")


def _download_photo_assets(ydl: Any, photo_urls: tuple[str, ...], work_dir: Path) -> tuple[MediaAsset, ...]:
    assets: list[MediaAsset] = []
    for sequence, photo_url in enumerate(photo_urls, start=1):
        response = ydl.urlopen(photo_url)
        content_type = str(response.headers.get("Content-Type") or "")
        suffix = _image_suffix(photo_url, content_type)
        path = work_dir / f"photo-{sequence:02d}{suffix}"
        path.write_bytes(response.read())
        assets.append(
            MediaAsset(
                kind=MediaKind.PHOTO,
                path=path,
                sequence=sequence,
                source_url=photo_url,
            )
        )
    return tuple(assets)


def _metadata_from_info(info: dict[str, Any], fallback_url: str) -> SourceMetadata:
    source_url = fallback_url
    source_id = str(info.get("id") or _fallback_video_id(source_url))
    description = str(info.get("description") or info.get("title") or "").strip()
    account = _account_from_info(info, fallback_url=fallback_url)
    duration = _duration_from_info(info)

    return SourceMetadata(
        source_url=source_url,
        account=account,
        description=description,
        source_id=source_id,
        duration_seconds=duration,
    )


def _duration_from_info(info: dict[str, Any]) -> float:
    try:
        return float(info.get("duration") or 0)
    except (TypeError, ValueError):
        return 0.0


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


def _is_photo_slideshow(info: dict[str, Any], photo_urls: tuple[str, ...]) -> bool:
    if len(photo_urls) >= 2:
        return True

    if _has_video_format(info):
        return False

    return _is_audio_suffix(str(info.get("ext") or "")) or any(
        _is_audio_suffix(str(download.get("filepath") or ""))
        for download in info.get("requested_downloads") or []
    )


def _has_video_format(info: dict[str, Any]) -> bool:
    formats = info.get("formats") or []
    for item in formats:
        if str(item.get("vcodec") or "").lower() not in {"", "none"}:
            return True

    requested = info.get("requested_formats") or []
    for item in requested:
        if str(item.get("vcodec") or "").lower() not in {"", "none"}:
            return True
    return False


def _is_audio_suffix(value: str) -> bool:
    suffix = Path(value).suffix.lower() if "." in value else f".{value.lower().lstrip('.')}"
    return suffix in AUDIO_SUFFIXES


def _photo_urls_from_info(info: dict[str, Any]) -> tuple[str, ...]:
    explicit_urls: list[str] = []

    for path in (
        ("imagePost", "images"),
        ("image_post_info", "images"),
        ("image_post", "images"),
        ("photo_post", "images"),
    ):
        for image in _nested_values(info, path):
            explicit_urls.extend(_preferred_image_urls_from_post_image(image))

    if explicit_urls:
        return _dedupe_urls(url for url in explicit_urls if _looks_like_remote_image(url))

    return _dedupe_urls(url for url in _image_urls_from_node(info, path=()) if _looks_like_remote_image(url))


def _preferred_image_urls_from_post_image(image: Any) -> list[str]:
    if not isinstance(image, dict):
        return _image_urls_from_node(image, path=("imagePost", "images"))

    for path in (
        ("imageURL", "urlList"),
        ("imageURL", "url_list"),
        ("imageURL", "urls"),
        ("image_url", "url_list"),
        ("image_url", "urls"),
        ("urlList",),
        ("url_list",),
        ("urls",),
    ):
        values = _nested_values(image, path)
        for value in values:
            if isinstance(value, str) and _looks_like_remote_image(value):
                return [value]
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, str) and _looks_like_remote_image(item):
                        return [item]

    return _image_urls_from_node(image, path=("imagePost", "images"))


def _nested_values(node: Any, path: tuple[str, ...]) -> list[Any]:
    if not path:
        return [node]
    if not isinstance(node, dict):
        return []

    head, *tail = path
    value = node.get(head)
    if isinstance(value, list):
        return [
            result
            for item in value
            for result in _nested_values(item, tuple(tail))
        ]
    return _nested_values(value, tuple(tail))


def _image_urls_from_node(node: Any, path: tuple[str, ...]) -> list[str]:
    if isinstance(node, str):
        if _path_suggests_photo(path) and _looks_like_remote_image(node):
            return [node]
        return []

    if isinstance(node, list):
        urls: list[str] = []
        for item in node:
            urls.extend(_image_urls_from_node(item, path=path))
        return urls

    if not isinstance(node, dict):
        return []

    urls: list[str] = []
    for key, value in node.items():
        key_path = (*path, str(key))
        if _path_is_excluded_image_container(key_path):
            continue
        urls.extend(_image_urls_from_node(value, path=key_path))
    return urls


def _path_suggests_photo(path: tuple[str, ...]) -> bool:
    lowered = tuple(part.lower() for part in path)
    if _path_is_excluded_image_container(lowered):
        return False
    return any(part in {"imagepost", "image_post_info", "image_post", "photo_post"} for part in lowered) or (
        any("image" in part or "photo" in part for part in lowered)
        and any(part in {"urllist", "url_list", "urls", "url"} for part in lowered)
    )


def _path_is_excluded_image_container(path: tuple[str, ...]) -> bool:
    excluded = ("thumbnail", "cover", "avatar", "author", "music")
    return any(any(token in part.lower() for token in excluded) for part in path)


def _looks_like_remote_image(value: str) -> bool:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"}:
        return False
    lowered = parsed.path.lower()
    return any(lowered.endswith(suffix) for suffix in (".jpg", ".jpeg", ".png", ".webp", ".heic")) or (
        "image" in lowered or "photo" in lowered
    )


def _dedupe_urls(urls: Any) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for raw in urls:
        url = str(raw).strip()
        if not url or url in seen:
            continue
        seen.add(url)
        result.append(url)
    return tuple(result)


def _image_suffix(url: str, content_type: str) -> str:
    suffix = Path(urlparse(url).path).suffix.lower()
    if suffix in {".jpg", ".jpeg", ".png", ".webp", ".heic"}:
        return suffix

    normalized = content_type.lower().split(";", 1)[0].strip()
    return {
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/heic": ".heic",
    }.get(normalized, ".jpg")
