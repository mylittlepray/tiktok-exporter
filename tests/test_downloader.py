from tiktokexport.tiktok.downloader import _account_from_info, _fallback_video_id, _metadata_from_info


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
