from __future__ import annotations

import re
from pathlib import Path

WINDOWS_RESERVED_NAMES = {
    "con",
    "prn",
    "aux",
    "nul",
    "com1",
    "com2",
    "com3",
    "com4",
    "com5",
    "com6",
    "com7",
    "com8",
    "com9",
    "lpt1",
    "lpt2",
    "lpt3",
    "lpt4",
    "lpt5",
    "lpt6",
    "lpt7",
    "lpt8",
    "lpt9",
}


def sanitize_component(value: str, fallback: str = "unknown", max_length: int = 80) -> str:
    value = value.strip().lstrip("@").lower()
    value = re.sub(r"[<>:\"/\\|?*\x00-\x1f]", " ", value)
    value = re.sub(r"\s+", "_", value)
    value = re.sub(r"[^\w.-]+", "_", value, flags=re.UNICODE)
    value = value.strip("._-")

    if not value:
        value = fallback
    if value in WINDOWS_RESERVED_NAMES:
        value = f"{value}_"

    return value[:max_length].rstrip("._-") or fallback


def sanitize_filename(value: str, fallback: str = "untitled", max_length: int = 120) -> str:
    value = value.strip()
    value = re.sub(r"[<>:\"/\\|?*\x00-\x1f]", " ", value)
    value = re.sub(r"\s+", " ", value)
    value = value.strip(" .")

    if not value:
        value = fallback
    if value.lower() in WINDOWS_RESERVED_NAMES:
        value = f"{value}_"

    return value[:max_length].rstrip(" .") or fallback


def summarize_sentence_for_filename(value: str, limit: int = 50) -> str:
    value = re.sub(r"\s+", " ", value.strip())
    if len(value) <= limit:
        return value

    sentence_ends = {".", "!", "?", "。", "！", "？", "…"}
    last_sentence_end = -1
    for index, char in enumerate(value[:limit]):
        if char in sentence_ends:
            last_sentence_end = index

    if last_sentence_end >= 0:
        candidate = value[: last_sentence_end + 1].strip()
        if len(candidate) >= 5:
            return candidate

    return value[:limit].strip()


def build_base_filename(created_at: str, account: str, video_id: str) -> str:
    author = sanitize_component(account, fallback="unknown")
    identifier = sanitize_component(video_id, fallback="video")
    return f"{created_at}_{author}_{identifier}"


def unique_base_path(output_dir: Path, base: str, suffixes: tuple[str, ...]) -> str:
    candidate = base
    counter = 2

    while any((output_dir / f"{candidate}{suffix}").exists() for suffix in suffixes):
        candidate = f"{base}_{counter}"
        counter += 1

    return candidate

