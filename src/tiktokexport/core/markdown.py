from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import yaml


@dataclass(frozen=True)
class MarkdownNote:
    title: str
    frontmatter: dict[str, Any]
    sections: tuple[tuple[str, str], ...] = field(default_factory=tuple)


def render_markdown_note(note: MarkdownNote) -> str:
    yaml_body = yaml.safe_dump(
        note.frontmatter,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
    ).strip()
    sections = "".join(
        f"## {heading}\n\n{body.strip()}\n\n"
        for heading, body in note.sections
        if body.strip()
    )

    return f"---\n{yaml_body}\n---\n\n# {note.title}\n\n{sections}".rstrip() + "\n"
