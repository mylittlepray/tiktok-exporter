from __future__ import annotations

from pathlib import Path


def parse_links_text(text: str) -> list[str]:
    """Parse newline-separated URLs, skipping blanks, comments, and duplicates."""
    links: list[str] = []
    seen: set[str] = set()

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line in seen:
            continue

        seen.add(line)
        links.append(line)

    return links


def parse_links_file(path: Path) -> list[str]:
    return parse_links_text(path.read_text(encoding="utf-8-sig"))
