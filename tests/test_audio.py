from pathlib import Path

import pytest
import yaml

from tiktokexport.core.audio import (
    AudioFileTranscriber,
    AudioTranscriptionOptions,
    normalize_transcript_format,
    supported_audio_extensions,
)


class FakeTranscriber:
    def transcribe(self, media_path: Path, reporter=None) -> str:
        return f"Transcript for {media_path.name}"


def test_transcribe_audio_writes_markdown_transcript(tmp_path: Path) -> None:
    source = tmp_path / "Voice Note.MP3"
    source.write_bytes(b"audio")
    output_dir = tmp_path / "out"

    summary = AudioFileTranscriber(FakeTranscriber()).transcribe_files(
        [source],
        AudioTranscriptionOptions(output_dir=output_dir, created_at="2026-05-14"),
    )

    assert len(summary.successes) == 1
    transcript_path = output_dir / "2026-05-14_voice_note.md"
    assert summary.successes[0].transcript_path == transcript_path

    markdown = transcript_path.read_text(encoding="utf-8")
    _, frontmatter, body = markdown.split("---", 2)
    parsed = yaml.safe_load(frontmatter)

    assert parsed["tags"] == ["transcription", "audio"]
    assert parsed["source_file"] == "Voice Note.MP3"
    assert "## Транскрипт" in body
    assert "Transcript for Voice Note.MP3" in body


def test_transcribe_audio_writes_plain_text(tmp_path: Path) -> None:
    source = tmp_path / "clip.wav"
    source.write_bytes(b"audio")
    output_dir = tmp_path / "out"

    summary = AudioFileTranscriber(FakeTranscriber()).transcribe_files(
        [source],
        AudioTranscriptionOptions(
            output_dir=output_dir,
            output_format="txt",
            created_at="2026-05-14",
        ),
    )

    transcript_path = output_dir / "2026-05-14_clip.txt"
    assert summary.successes[0].transcript_path == transcript_path
    assert transcript_path.read_text(encoding="utf-8") == "Transcript for clip.wav\n"


def test_transcribe_audio_records_unsupported_format_failure(tmp_path: Path) -> None:
    source = tmp_path / "notes.txt"
    source.write_text("not audio", encoding="utf-8")

    summary = AudioFileTranscriber(FakeTranscriber()).transcribe_files(
        [source],
        AudioTranscriptionOptions(output_dir=tmp_path / "out"),
    )

    assert len(summary.successes) == 0
    assert len(summary.failures) == 1
    assert "Unsupported audio format" in summary.failures[0].error


def test_normalize_transcript_format() -> None:
    assert normalize_transcript_format(".MD") == "md"
    assert ".mp3" in supported_audio_extensions()
    with pytest.raises(ValueError):
        normalize_transcript_format("srt")

