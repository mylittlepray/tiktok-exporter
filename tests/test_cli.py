from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from tiktokexport.audio_file.models import (
    AudioTranscriptionOptions,
    AudioTranscriptionSummary,
    TranscribedAudio,
)
from tiktokexport.cli import (
    _collect_audio_paths,
    _collect_urls,
    _resolve_output_dir,
    _validate_device,
    _validate_transcript_format,
    app,
)
from tiktokexport.config import AppConfig
from tiktokexport.core.models import MediaKind
from tiktokexport.tiktok.models import ExportDetails, ExportedNote, ExportOptions, ExportSummary


runner = CliRunner()


def test_resolve_output_dir_uses_project_export_default(
    monkeypatch,
    tmp_path: Path,
) -> None:
    expected = tmp_path / "export"

    monkeypatch.setattr("tiktokexport.cli.load_config", lambda: AppConfig())
    monkeypatch.setattr("tiktokexport.cli.default_output_dir", lambda: expected)

    assert _resolve_output_dir(None) == expected.resolve()


def test_validate_device_normalizes_known_values() -> None:
    assert _validate_device(" CUDA ") == "cuda"


def test_validate_device_rejects_unknown_values() -> None:
    with pytest.raises(typer.BadParameter):
        _validate_device("metal")


def test_validate_transcript_format_normalizes_known_values() -> None:
    assert _validate_transcript_format(".TXT") == "txt"


def test_validate_transcript_format_rejects_unknown_values() -> None:
    with pytest.raises(typer.BadParameter):
        _validate_transcript_format("srt")


def test_collect_urls_accepts_multiple_urls() -> None:
    assert _collect_urls(["https://a", "https://b", "https://a"], None) == [
        "https://a",
        "https://b",
    ]


def test_collect_audio_paths_from_directory(tmp_path: Path) -> None:
    first = tmp_path / "a.mp3"
    second = tmp_path / "b.wav"
    ignored = tmp_path / "notes.txt"
    first.write_bytes(b"audio")
    second.write_bytes(b"audio")
    ignored.write_text("text", encoding="utf-8")

    assert _collect_audio_paths(None, tmp_path, recursive=False) == [
        first.resolve(),
        second.resolve(),
    ]


def test_tiktok_export_cli_accepts_direct_url(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}
    _patch_reporter(monkeypatch)
    _patch_output_dir(monkeypatch, tmp_path)

    class FakeTikTokExporter:
        def export_urls(self, urls: list[str], options: ExportOptions, reporter=None) -> ExportSummary:
            captured["urls"] = urls
            captured["options"] = options
            return ExportSummary(
                successes=(
                    ExportedNote(
                        source_url=urls[0],
                        markdown_path=tmp_path / "note.md",
                        media_paths=(),
                        media_kind=MediaKind.VIDEO,
                        media_duration_seconds=12.0,
                        export_duration_seconds=1.5,
                        exported_at="2026-05-23T12:00:00+00:00",
                        details=ExportDetails(status="success", transcription="success"),
                    ),
                ),
                failures=(),
            )

    monkeypatch.setattr("tiktokexport.cli.TikTokExporter", FakeTikTokExporter)

    result = runner.invoke(app, ["tiktok", "export", "https://www.tiktok.com/@a/video/1"])

    assert result.exit_code == 0
    assert captured["urls"] == ["https://www.tiktok.com/@a/video/1"]
    assert isinstance(captured["options"], ExportOptions)
    assert captured["options"].transcribe is True


def test_tiktok_export_cli_accepts_links_file_and_no_transcribe(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}
    links = tmp_path / "links.txt"
    links.write_text("https://a\nhttps://b\n", encoding="utf-8")
    _patch_reporter(monkeypatch)
    _patch_output_dir(monkeypatch, tmp_path)

    class FakeTikTokExporter:
        def export_urls(self, urls: list[str], options: ExportOptions, reporter=None) -> ExportSummary:
            captured["urls"] = urls
            captured["options"] = options
            return ExportSummary(successes=(), failures=())

    monkeypatch.setattr("tiktokexport.cli.TikTokExporter", FakeTikTokExporter)

    result = runner.invoke(app, ["tiktok", "export", "--file", str(links), "--no-transcribe"])

    assert result.exit_code == 0
    assert captured["urls"] == ["https://a", "https://b"]
    assert captured["options"].transcribe is False


def test_tiktok_export_links_cli_prompts_and_writes_selected_links(tmp_path: Path) -> None:
    source = tmp_path / "user_data_tiktok.json"
    source.write_text(
        """
        {
          "Likes and Favorites": {
            "Favorite Videos": {
              "FavoriteVideoList": [
                {"Link": "https://www.tiktokv.com/share/video/1/"}
              ]
            },
            "Like List": {
              "ItemFavoriteList": [
                {"link": "https://www.tiktokv.com/share/video/2/"}
              ]
            }
          }
        }
        """,
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "tiktok",
            "export-links",
            "--file",
            str(source),
            "--out",
            str(tmp_path / "links"),
        ],
        input="likes\n",
    )

    assert result.exit_code == 0
    files = list((tmp_path / "links").glob("*.txt"))
    assert len(files) == 1
    assert files[0].read_text(encoding="utf-8") == "https://www.tiktokv.com/share/video/2/\n"
    assert "Favorite Videos" in result.output
    assert "Like List" in result.output


def test_tiktok_export_links_cli_accepts_section_option(tmp_path: Path) -> None:
    source = tmp_path / "user_data_tiktok.json"
    source.write_text(
        """
        {
          "Likes and Favorites": {
            "Favorite Videos": {"FavoriteVideoList": [{"Link": "https://www.tiktokv.com/share/video/1/"}]},
            "Like List": {"ItemFavoriteList": [{"link": "https://www.tiktokv.com/share/video/2/"}]}
          }
        }
        """,
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "tiktok",
            "export-links",
            "--file",
            str(source),
            "--section",
            "both",
            "--out",
            str(tmp_path / "links"),
        ],
    )

    assert result.exit_code == 0
    files = list((tmp_path / "links").glob("*.txt"))
    assert len(files) == 1
    assert files[0].read_text(encoding="utf-8") == (
        "https://www.tiktokv.com/share/video/1/\n"
        "https://www.tiktokv.com/share/video/2/\n"
    )


def test_audio_transcribe_cli_accepts_file(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}
    source = tmp_path / "voice.mp3"
    source.write_bytes(b"audio")
    _patch_reporter(monkeypatch)
    _patch_output_dir(monkeypatch, tmp_path)

    class FakeAudioFileTranscriber:
        def transcribe_files(
            self,
            paths: list[Path],
            options: AudioTranscriptionOptions,
            reporter=None,
        ) -> AudioTranscriptionSummary:
            captured["paths"] = paths
            captured["options"] = options
            return AudioTranscriptionSummary(
                successes=(TranscribedAudio(source_path=paths[0], transcript_path=tmp_path / "voice.md"),),
                failures=(),
            )

    monkeypatch.setattr("tiktokexport.cli.AudioFileTranscriber", FakeAudioFileTranscriber)

    result = runner.invoke(app, ["audio", "transcribe", str(source)])

    assert result.exit_code == 0
    assert captured["paths"] == [source]
    assert captured["options"].output_format == "md"


def test_audio_transcribe_cli_accepts_directory(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}
    source = tmp_path / "voice.mp3"
    source.write_bytes(b"audio")
    _patch_reporter(monkeypatch)
    _patch_output_dir(monkeypatch, tmp_path)

    class FakeAudioFileTranscriber:
        def transcribe_files(
            self,
            paths: list[Path],
            options: AudioTranscriptionOptions,
            reporter=None,
        ) -> AudioTranscriptionSummary:
            captured["paths"] = paths
            captured["options"] = options
            return AudioTranscriptionSummary(
                successes=(TranscribedAudio(source_path=paths[0], transcript_path=tmp_path / "voice.md"),),
                failures=(),
            )

    monkeypatch.setattr("tiktokexport.cli.AudioFileTranscriber", FakeAudioFileTranscriber)

    result = runner.invoke(app, ["audio", "transcribe", "--dir", str(tmp_path), "--recursive"])

    assert result.exit_code == 0
    assert captured["paths"] == [source.resolve()]
    assert captured["options"].output_format == "md"


class DummyReporter:
    def __init__(self, *_args, **_kwargs) -> None:
        pass

    def __enter__(self) -> "DummyReporter":
        return self

    def __exit__(self, *_args) -> None:
        return None


def _patch_reporter(monkeypatch) -> None:
    monkeypatch.setattr("tiktokexport.cli.RichExportReporter", DummyReporter)


def _patch_output_dir(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("tiktokexport.cli._resolve_output_dir", lambda _out: tmp_path)
