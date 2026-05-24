import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from tiktokexport.tiktok.link_exporter import (
    export_tiktok_links,
    load_tiktok_link_blocks,
    normalize_link_sections,
)


def test_load_tiktok_link_blocks_reads_tiktok_export_shape(tmp_path: Path) -> None:
    source = tmp_path / "user_data_tiktok.json"
    source.write_text(
        json.dumps(
            {
                "Likes and Favorites": {
                    "Favorite Videos": {
                        "App": 1,
                        "FavoriteVideoList": [
                            {"Date": "2026-05-22 10:31:43", "Link": "https://www.tiktokv.com/share/video/1/"},
                            {"Date": "2026-05-22 10:31:14", "Link": "https://www.tiktokv.com/share/video/2/"},
                        ],
                    },
                    "Like List": {
                        "App": 1,
                        "ItemFavoriteList": [
                            {"date": "2026-05-18 17:16:36", "link": "https://www.tiktokv.com/share/video/3/"},
                        ],
                    },
                }
            }
        ),
        encoding="utf-8",
    )

    blocks = load_tiktok_link_blocks(source)

    assert blocks.favorite_videos == (
        "https://www.tiktokv.com/share/video/1/",
        "https://www.tiktokv.com/share/video/2/",
    )
    assert blocks.like_list == ("https://www.tiktokv.com/share/video/3/",)


def test_export_tiktok_links_writes_deduped_txt(tmp_path: Path) -> None:
    source = tmp_path / "user_data_tiktok.json"
    source.write_text(
        json.dumps(
            {
                "Likes and Favorites": {
                    "Favorite Videos": {
                        "FavoriteVideoList": [
                            {"Link": "https://www.tiktokv.com/share/video/1/"},
                            {"Link": "https://www.tiktokv.com/share/video/2/"},
                        ]
                    },
                    "Like List": {
                        "ItemFavoriteList": [
                            {"link": "https://www.tiktokv.com/share/video/2/"},
                            {"link": "https://www.tiktokv.com/share/video/3/"},
                        ]
                    },
                }
            }
        ),
        encoding="utf-8",
    )
    blocks = load_tiktok_link_blocks(source)

    exported = export_tiktok_links(
        blocks,
        ("favorite_videos", "like_list"),
        output_dir=tmp_path / "exported_links",
        generated_at=datetime(2026, 5, 23, 12, 0, tzinfo=timezone.utc),
    )

    assert exported.link_count == 3
    assert exported.path.name == "tiktok-links-2026-05-23T12-00-00+00-00.txt"
    assert exported.path.read_text(encoding="utf-8") == (
        "https://www.tiktokv.com/share/video/1/\n"
        "https://www.tiktokv.com/share/video/2/\n"
        "https://www.tiktokv.com/share/video/3/\n"
    )


def test_normalize_link_sections_accepts_aliases() -> None:
    assert normalize_link_sections(["favorite", "likes"]) == ("favorite_videos", "like_list")
    assert normalize_link_sections(["both"]) == ("favorite_videos", "like_list")


def test_normalize_link_sections_rejects_unknown_value() -> None:
    with pytest.raises(ValueError):
        normalize_link_sections(["comments"])
