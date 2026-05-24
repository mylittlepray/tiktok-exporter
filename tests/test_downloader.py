from tiktokexport.tiktok.downloader import (
    _account_from_info,
    _fallback_video_id,
    _is_photo_slideshow,
    _metadata_from_info,
    _photo_urls_from_info,
    _preferred_image_urls_from_post_image,
    _resolve_tiktok_redirect,
    _unsupported_photo_url_from_error,
    _video_compatible_tiktok_url,
)


def test_metadata_keeps_user_supplied_source_url() -> None:
    metadata = _metadata_from_info(
        {
            "webpage_url": "https://www.tiktok.com/@canonical/video/123",
            "id": "123",
            "uploader": "author",
            "description": "Description",
        },
        fallback_url="https://vm.tiktok.com/short-link/",
    )

    assert metadata.source_url == "https://vm.tiktok.com/short-link/"
    assert metadata.source_id == "123"


def test_fallback_video_id_is_stable() -> None:
    assert _fallback_video_id("https://vm.tiktok.com/short-link/") == (
        _fallback_video_id("https://vm.tiktok.com/short-link/")
    )


def test_account_prefers_non_numeric_username() -> None:
    assert (
        _account_from_info(
            {
                "uploader_id": "7340699841255818245",
                "uploader": "real_username",
            }
        )
        == "@real_username"
    )


def test_account_uses_username_from_url_before_numeric_id() -> None:
    assert (
        _account_from_info(
            {
                "uploader_id": "7340699841255818245",
                "webpage_url": "https://www.tiktok.com/@real_username/video/123",
            }
        )
        == "@real_username"
    )


def test_photo_urls_from_info_extracts_image_post_urls_without_thumbnails() -> None:
    urls = _photo_urls_from_info(
        {
            "imagePost": {
                "images": [
                    {
                        "imageURL": {
                            "urlList": [
                                "https://p16.example.com/photo1.jpeg",
                                "https://p19.example.com/photo1.jpeg",
                            ]
                        }
                    },
                    {
                        "imageURL": {
                            "urlList": [
                                "https://p16.example.com/photo2.webp",
                                "https://p19.example.com/photo2.webp",
                            ]
                        }
                    },
                ],
            },
            "thumbnails": [{"url": "https://cdn.example.com/thumbnail.jpeg"}],
        }
    )

    assert urls == (
        "https://p16.example.com/photo1.jpeg",
        "https://p16.example.com/photo2.webp",
    )


def test_preferred_image_urls_from_post_image_uses_first_cdn_mirror() -> None:
    assert _preferred_image_urls_from_post_image(
        {
            "imageURL": {
                "urlList": [
                    "https://p16.example.com/photo.jpeg",
                    "https://p19.example.com/photo.jpeg",
                ]
            },
            "imageWidth": 1080,
        }
    ) == ["https://p16.example.com/photo.jpeg"]


def test_is_photo_slideshow_detects_multiple_photos() -> None:
    assert _is_photo_slideshow(
        {"formats": [{"vcodec": "h264"}], "ext": "mp4"},
        ("https://cdn.example.com/photo1.jpeg", "https://cdn.example.com/photo2.jpeg"),
    )


def test_is_photo_slideshow_detects_audio_only_tiktok_post() -> None:
    assert _is_photo_slideshow({"formats": [{"vcodec": "none"}], "ext": "mp3"}, ())


def test_video_compatible_tiktok_url_rewrites_direct_photo_url() -> None:
    assert _video_compatible_tiktok_url(
        "https://www.tiktok.com/@motiwe25/photo/7622058656217042194?_r=1"
    ) == "https://www.tiktok.com/@motiwe25/video/7622058656217042194?_r=1"


def test_unsupported_photo_url_from_error_extracts_redirect_target() -> None:
    error = RuntimeError(
        "ERROR: Unsupported URL: "
        "https://www.tiktok.com/@motiwe25/photo/7622058656217042194?_r=1&_t=abc"
    )

    assert _unsupported_photo_url_from_error(error) == (
        "https://www.tiktok.com/@motiwe25/photo/7622058656217042194?_r=1&_t=abc"
    )


def test_resolve_tiktok_redirect_uses_response_url_for_short_links() -> None:
    ydl = FakeYdl("https://www.tiktok.com/@author/photo/123")

    assert _resolve_tiktok_redirect(ydl, "https://vt.tiktok.com/abc/") == (
        "https://www.tiktok.com/@author/photo/123"
    )
    assert ydl.opened_urls == ["https://vt.tiktok.com/abc/"]


def test_resolve_tiktok_redirect_leaves_regular_tiktok_url_alone() -> None:
    ydl = FakeYdl("unused")

    assert _resolve_tiktok_redirect(ydl, "https://www.tiktok.com/@author/video/123") == (
        "https://www.tiktok.com/@author/video/123"
    )
    assert ydl.opened_urls == []


class FakeYdl:
    def __init__(self, response_url: str) -> None:
        self.response_url = response_url
        self.opened_urls: list[str] = []

    def urlopen(self, url: str) -> "FakeResponse":
        self.opened_urls.append(url)
        return FakeResponse(self.response_url)


class FakeResponse:
    def __init__(self, url: str) -> None:
        self.url = url
        self.closed = False

    def close(self) -> None:
        self.closed = True
