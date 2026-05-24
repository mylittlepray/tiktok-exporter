from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import cast

from tiktokexport.audio_file.models import (
    AudioTranscriptionFailure,
    AudioTranscriptionOptions,
    AudioTranscriptionSummary,
    TranscribedAudio,
    TranscriptFormat,
)
from tiktokexport.core.ffmpeg import AUDIO_SUFFIXES, is_audio_file
from tiktokexport.core.files import ensure_output_dir
from tiktokexport.core.filenames import sanitize_component, unique_base_path
from tiktokexport.core.markdown import MarkdownNote, render_markdown_note
from tiktokexport.core.ports import Transcriber
from tiktokexport.core.transcriber import WhisperTranscriber
from tiktokexport.progress import ExportReporter


SUPPORTED_TRANSCRIPT_FORMATS = frozenset({"md", "txt"})


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
        source_path = validate_audio_path(path)
        output_dir = ensure_output_dir(options.output_dir)
        created_at = options.created_at or date.today().isoformat()
        output_format = normalize_transcript_format(options.output_format)
        transcriber = transcriber or self.transcriber or WhisperTranscriber(
            options.model_name,
            device=options.device,
        )

        if reporter is not None:
            reporter.stage("Transcribing audio file")
        transcript = transcriber.transcribe(source_path, reporter=reporter)

        suffix = f".{output_format}"
        base = f"{created_at}_{sanitize_component(source_path.stem, fallback='audio')}"
        base = unique_base_path(output_dir, base, (suffix,))
        transcript_path = output_dir / f"{base}{suffix}"

        if reporter is not None:
            reporter.stage("Saving transcript")
        transcript_path.write_text(
            render_audio_transcript(
                source_path=source_path,
                created_at=created_at,
                transcript=transcript,
                output_format=output_format,
            ),
            encoding="utf-8",
        )

        return TranscribedAudio(source_path=source_path, transcript_path=transcript_path)


def collect_audio_files(directory: Path, recursive: bool = False) -> list[Path]:
    root = directory.expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise ValueError(f"Audio directory does not exist: {directory}")

    iterator = root.rglob("*") if recursive else root.iterdir()
    return sorted(path for path in iterator if path.is_file() and is_audio_file(path))


def normalize_transcript_format(value: str) -> TranscriptFormat:
    normalized = value.strip().lower().lstrip(".")
    if normalized not in SUPPORTED_TRANSCRIPT_FORMATS:
        raise ValueError("Transcript format must be one of: md, txt.")
    return cast(TranscriptFormat, normalized)


def supported_audio_extensions() -> tuple[str, ...]:
    return tuple(sorted(AUDIO_SUFFIXES))


def validate_audio_path(path: Path) -> Path:
    source_path = path.expanduser().resolve()
    if not source_path.exists() or not source_path.is_file():
        raise ValueError(f"Audio file does not exist: {path}")
    if not is_audio_file(source_path):
        extensions = ", ".join(supported_audio_extensions())
        suffix = source_path.suffix or "<none>"
        raise ValueError(f"Unsupported audio format: {suffix}. Supported: {extensions}")
    return source_path


def render_audio_transcript(
    *,
    source_path: Path,
    created_at: str,
    transcript: str,
    output_format: TranscriptFormat,
) -> str:
    transcript = transcript.strip() or "Текст не распознан."
    if output_format == "txt":
        return f"{transcript}\n"

    return render_markdown_note(
        MarkdownNote(
            title=source_path.stem,
            frontmatter={
                "created_at": created_at,
                "tags": ["transcription", "audio"],
                "source_file": source_path.name,
                "media_type": "audio",
            },
            sections=(("Транскрипт", transcript),),
        )
    )

