from tiktokexport.downloader import _fallback_video_id, _metadata_from_info


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
