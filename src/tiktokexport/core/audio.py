from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Literal, Protocol, cast

import yaml

from .ffmpeg import AUDIO_SUFFIXES, is_audio_file
from .filenames import sanitize_component, unique_base_path
from .transcriber import WhisperTranscriber
from ..progress import ExportReporter


TranscriptFormat = Literal["md", "txt"]
SUPPORTED_TRANSCRIPT_FORMATS = frozenset({"md", "txt"})


class Transcriber(Protocol):
    def transcribe(
        self,
        media_path: Path,
        reporter: ExportReporter | None = None,
    ) -> str:
        ...


@dataclass(frozen=True)
class AudioTranscriptionOptions:
    output_dir: Path
    model_name: str = "turbo"
    device: str = "auto"
    output_format: TranscriptFormat = "md"
    fail_fast: bool = False
    created_at: str | None = None


@dataclass(frozen=True)
class TranscribedAudio:
    source_path: Path
    transcript_path: Path


@dataclass(frozen=True)
class AudioTranscriptionFailure:
    source_path: Path
    error: str


@dataclass(frozen=True)
class AudioTranscriptionSummary:
    successes: tuple[TranscribedAudio, ...]
    failures: tuple[AudioTranscriptionFailure, ...]


class AudioFileTranscriber:
    def __init__(self, transcriber: Transcriber | None = None) -> None:
        self.transcriber = transcriber

    def transcribe_files(
        self,
        paths: list[Path],
        options: AudioTranscriptionOptions,
        reporter: ExportReporter | None = None,
    ) -> AudioTranscriptionSummary:
        successes: list[TranscribedAudio] = []
        failures: list[AudioTranscriptionFailure] = []
        transcriber = self.transcriber or WhisperTranscriber(
            options.model_name,
            device=options.device,
        )

        if reporter is not None:
            reporter.start_batch(len(paths), item_label="audio file")

        for index, path in enumerate(paths, start=1):
            if reporter is not None:
                reporter.start_item(index, len(paths), "Audio", str(path))
            try:
                successes.append(self.transcribe_one(path, options, transcriber, reporter))
                if reporter is not None:
                    reporter.success(successes[-1].transcript_path)
            except Exception as exc:
                failures.append(AudioTranscriptionFailure(source_path=path, error=str(exc)))
                if reporter is not None:
                    reporter.failure(str(path), str(exc))
                if options.fail_fast:
                    break

        return AudioTranscriptionSummary(successes=tuple(successes), failures=tuple(failures))

    def transcribe_one(
        self,
        path: Path,
        options: AudioTranscriptionOptions,
        transcriber: Transcriber | None = None,
        reporter: ExportReporter | None = None,
    ) -> TranscribedAudio:
        source_path = _validate_audio_path(path)
        output_dir = options.output_dir.expanduser().resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        created_at = options.created_at or date.today().isoformat()
        output_format = normalize_transcript_format(options.output_format)
        transcriber = transcriber or self.transcriber or WhisperTranscriber(
            options.model_name,
            device=options.device,
        )

        if reporter is not None:
            reporter.stage("Transcribing audio file")
        transcript = transcriber.transcribe(source_path, reporter=reporter)

        base = f"{created_at}_{sanitize_component(source_path.stem, fallback='audio')}"
        suffix = f".{output_format}"
        base = unique_base_path(output_dir, base, (suffix,))
        transcript_path = output_dir / f"{base}{suffix}"

        if reporter is not None:
            reporter.stage("Saving transcript")
        transcript_path.write_text(
            _render_transcript(
                source_path=source_path,
                created_at=created_at,
                transcript=transcript,
                output_format=output_format,
            ),
            encoding="utf-8",
        )

        return TranscribedAudio(source_path=source_path, transcript_path=transcript_path)


def normalize_transcript_format(value: str) -> TranscriptFormat:
    normalized = value.strip().lower().lstrip(".")
    if normalized not in SUPPORTED_TRANSCRIPT_FORMATS:
        raise ValueError("Transcript format must be one of: md, txt.")
    return cast(TranscriptFormat, normalized)


def supported_audio_extensions() -> tuple[str, ...]:
    return tuple(sorted(AUDIO_SUFFIXES))


def _validate_audio_path(path: Path) -> Path:
    source_path = path.expanduser().resolve()
    if not source_path.exists() or not source_path.is_file():
        raise ValueError(f"Audio file does not exist: {path}")
    if not is_audio_file(source_path):
        extensions = ", ".join(supported_audio_extensions())
        suffix = source_path.suffix or "<none>"
        raise ValueError(f"Unsupported audio format: {suffix}. Supported: {extensions}")
    return source_path


def _render_transcript(
    *,
    source_path: Path,
    created_at: str,
    transcript: str,
    output_format: TranscriptFormat,
) -> str:
    transcript = transcript.strip() or "Текст не распознан."
    if output_format == "txt":
        return f"{transcript}\n"

    frontmatter = {
        "created_at": created_at,
        "tags": ["transcription", "audio"],
        "source_file": source_path.name,
        "media_type": "audio",
    }
    yaml_body = yaml.safe_dump(
        frontmatter,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
    ).strip()

    return (
        f"---\n{yaml_body}\n---\n\n"
        f"# {source_path.stem}\n\n"
        f"## Транскрипт\n\n"
        f"{transcript}\n"
    )
