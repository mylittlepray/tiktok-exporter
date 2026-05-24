from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal


LinkSection = Literal["favorite_videos", "like_list"]

SECTION_LABELS: dict[LinkSection, str] = {
    "favorite_videos": "Favorite Videos",
    "like_list": "Like List",
}


@dataclass(frozen=True)
class TikTokLinkBlocks:
    favorite_videos: tuple[str, ...]
    like_list: tuple[str, ...]


@dataclass(frozen=True)
class ExportedLinks:
    path: Path
    selected_sections: tuple[LinkSection, ...]
    link_count: int


def load_tiktok_link_blocks(path: Path) -> TikTokLinkBlocks:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    root = data.get("Likes and Favorites", data) if isinstance(data, dict) else data

    favorite_block = _block_by_name(root, "Favorite Videos")
    like_block = _block_by_name(root, "Like List")

    return TikTokLinkBlocks(
        favorite_videos=tuple(_links_from_block(favorite_block, preferred_list_key="FavoriteVideoList")),
        like_list=tuple(_links_from_block(like_block, preferred_list_key="ItemFavoriteList")),
    )


def export_tiktok_links(
    blocks: TikTokLinkBlocks,
    sections: tuple[LinkSection, ...],
    output_dir: Path | None = None,
    generated_at: datetime | None = None,
) -> ExportedLinks:
    output_dir = output_dir or Path.cwd() / "exported_links"
    generated_at = generated_at or datetime.now().astimezone()
    output_dir.mkdir(parents=True, exist_ok=True)

    links = _dedupe_links(
        link
        for section in sections
        for link in _links_for_section(blocks, section)
    )
    path = output_dir / f"tiktok-links-{_filename_timestamp(generated_at)}.txt"
    path.write_text("\n".join(links) + ("\n" if links else ""), encoding="utf-8")

    return ExportedLinks(
        path=path,
        selected_sections=sections,
        link_count=len(links),
    )


def normalize_link_sections(values: list[str]) -> tuple[LinkSection, ...]:
    if not values:
        raise ValueError("Select at least one link section.")

    sections: list[LinkSection] = []
    for value in values:
        normalized = value.strip().lower().replace("-", "_").replace(" ", "_")
        if normalized in {"favorite", "favorites", "favorite_video", "favorite_videos"}:
            section: LinkSection = "favorite_videos"
        elif normalized in {"like", "likes", "liked", "like_list"}:
            section = "like_list"
        elif normalized == "both":
            for item in ("favorite_videos", "like_list"):
                if item not in sections:
                    sections.append(item)
            continue
        else:
            raise ValueError("Section must be one of: favorite, likes, both.")

        if section not in sections:
            sections.append(section)

    return tuple(sections)


def _block_by_name(root: Any, name: str) -> Any:
    if isinstance(root, dict):
        if name in root:
            return root[name]
        for value in root.values():
            found = _block_by_name(value, name)
            if found is not None:
                return found
    elif isinstance(root, list):
        for item in root:
            found = _block_by_name(item, name)
            if found is not None:
                return found
    return None


def _links_from_block(block: Any, preferred_list_key: str) -> list[str]:
    if isinstance(block, dict) and preferred_list_key in block:
        return _dedupe_links(_links_from_node(block[preferred_list_key]))
    return _dedupe_links(_links_from_node(block))


def _links_from_node(node: Any) -> list[str]:
    if isinstance(node, str):
        value = node.strip()
        return [value] if _looks_like_tiktok_url(value) else []

    if isinstance(node, list):
        return [link for item in node for link in _links_from_node(item)]

    if isinstance(node, dict):
        links: list[str] = []
        for key, value in node.items():
            if str(key).lower() in {"link", "url", "href"} and isinstance(value, str):
                value = value.strip()
                if _looks_like_tiktok_url(value):
                    links.append(value)
                    continue
            links.extend(_links_from_node(value))
        return links

    return []


def _links_for_section(blocks: TikTokLinkBlocks, section: LinkSection) -> tuple[str, ...]:
    if section == "favorite_videos":
        return blocks.favorite_videos
    if section == "like_list":
        return blocks.like_list
    raise ValueError(f"Unsupported link section: {section}")


def _looks_like_tiktok_url(value: str) -> bool:
    lowered = value.lower()
    return lowered.startswith(("http://", "https://")) and (
        "tiktok.com" in lowered or "tiktokv.com" in lowered
    )


def _dedupe_links(values: Any) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for raw in values:
        link = str(raw).strip()
        if not link or link in seen:
            continue
        seen.add(link)
        result.append(link)
    return result


def _filename_timestamp(value: datetime) -> str:
    return value.isoformat(timespec="seconds").replace(":", "-")
