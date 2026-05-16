from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import yaml


@dataclass(frozen=True)
class MarkdownDocument:
    title: str
    transcript: str
    frontmatter: dict[str, Any]
    sections: tuple[tuple[str, str], ...] = field(default_factory=tuple)
    transcript_heading: str = "Транскрипт"


def render_transcript_markdown(document: MarkdownDocument) -> str:
    yaml_body = yaml.safe_dump(
        document.frontmatter,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
    ).strip()
    transcript = document.transcript.strip() or "Текст не распознан."
    sections = "".join(
        f"## {heading}\n\n{body.strip()}\n\n"
        for heading, body in document.sections
        if body.strip()
    )

    return (
        f"---\n{yaml_body}\n---\n\n"
        f"# {document.title}\n\n"
        f"{sections}"
        f"## {document.transcript_heading}\n\n"
        f"{transcript}\n"
    )
