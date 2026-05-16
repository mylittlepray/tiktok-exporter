from __future__ import annotations

from dataclasses import dataclass

import yaml

from .models import VideoMetadata


@dataclass(frozen=True)
class MarkdownNote:
    created_at: str
    metadata: VideoMetadata
    video_filename: str
    transcript: str


def render_markdown(note: MarkdownNote) -> str:
    frontmatter = {
        "created_at": note.created_at,
        "tags": ["tiktok"],
        "source_url": note.metadata.source_url,
        "account": note.metadata.account,
        "description": note.metadata.description,
        "video_file": note.video_filename,
    }
    yaml_body = yaml.safe_dump(
        frontmatter,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
    ).strip()

    account = note.metadata.account or "@unknown"
    description = note.metadata.description.strip() or "Описание отсутствует."
    transcript = note.transcript.strip() or "Текст не распознан."

    return (
        f"---\n{yaml_body}\n---\n\n"
        f"# TikTok - {account}\n\n"
        f"- Оригинал: {note.metadata.source_url}\n"
        f"- Аккаунт: {account}\n"
        f"- Локальное видео: {note.video_filename}\n\n"
        f"## Описание\n\n"
        f"{description}\n\n"
        f"## Содержание\n\n"
        f"{transcript}\n"
    )

