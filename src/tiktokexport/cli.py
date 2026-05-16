from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from tiktokexport.audio_file.models import (
    AudioTranscriptionFailure,
    AudioTranscriptionOptions,
    TranscriptFormat,
)
from tiktokexport.audio_file.pipeline import (
    AudioFileTranscriber,
    collect_audio_files,
    normalize_transcript_format,
)
from tiktokexport.config import default_output_dir, init_config, load_config
from tiktokexport.core.transcriber import torch_device_report
from tiktokexport.links import parse_links_file
from tiktokexport.progress import RichExportReporter
from tiktokexport.tiktok.pipeline import ExportOptions, TikTokExporter


app = typer.Typer(help="Run local Whisper transcription workflows.")
config_app = typer.Typer(help="Manage TikTokExport configuration.")
app.add_typer(config_app, name="config")
console = Console()


@config_app.command("init")
def init_config_command(
    out: Path = typer.Option(
        ...,
        "--out",
        "-o",
        help="Default folder for Markdown notes and downloaded videos.",
    ),
) -> None:
    path = init_config(out)
    console.print(f"Config saved: [bold]{path}[/bold]")
    console.print(f"Default output folder: [bold]{out.expanduser().resolve()}[/bold]")


@app.command("export")
def export_command(
    urls: Optional[list[str]] = typer.Argument(None, help="One or more TikTok URLs to export."),
    file: Optional[Path] = typer.Option(
        None,
        "--file",
        "-f",
        help="TXT file with one TikTok URL per line.",
    ),
    out: Optional[Path] = typer.Option(
        None,
        "--out",
        "-o",
        help="Output folder. Overrides the saved config and project export/ default.",
    ),
    model: str = typer.Option(
        "turbo",
        "--model",
        "-m",
        help="Local Whisper model name.",
    ),
    device: str = typer.Option(
        "auto",
        "--device",
        help="Transcription device: auto, cuda, or cpu. auto uses CUDA first when PyTorch can see it.",
    ),
    cookies: Optional[Path] = typer.Option(
        None,
        "--cookies",
        help="Path to a Netscape cookies.txt file for yt-dlp.",
    ),
    cookies_from_browser: Optional[str] = typer.Option(
        None,
        "--cookies-from-browser",
        help="Browser name for yt-dlp cookies extraction, for example chrome or firefox.",
    ),
    fail_fast: bool = typer.Option(
        False,
        "--fail-fast",
        help="Stop batch processing after the first failed URL.",
    ),
) -> None:
    urls = _collect_urls(urls=urls, file=file)
    device = _validate_device(device)
    output_dir = _resolve_output_dir(out)
    if cookies is not None and (not cookies.exists() or not cookies.is_file()):
        raise typer.BadParameter(f"Cookies file does not exist: {cookies}")

    with RichExportReporter(console) as reporter:
        summary = TikTokExporter().export_urls(
            urls,
            ExportOptions(
                output_dir=output_dir,
                model_name=model,
                cookies=cookies,
                cookies_from_browser=cookies_from_browser,
                fail_fast=fail_fast,
                device=device,
            ),
            reporter=reporter,
        )

    if summary.failures:
        _print_failures(summary.failures)
        raise typer.Exit(code=1)

    console.print(f"[green]Done[/green]: exported {len(summary.successes)} video(s).")


@app.command("transcribe")
def transcribe_command(
    files: Optional[list[Path]] = typer.Argument(
        None,
        help="One or more local audio files to transcribe.",
    ),
    directory: Optional[Path] = typer.Option(
        None,
        "--dir",
        "-d",
        help="Directory with audio files to transcribe.",
    ),
    recursive: bool = typer.Option(
        False,
        "--recursive",
        "-r",
        help="When --dir is used, include audio files from nested directories.",
    ),
    out: Optional[Path] = typer.Option(
        None,
        "--out",
        "-o",
        help="Output folder. Overrides the saved config and project export/ default.",
    ),
    model: str = typer.Option(
        "turbo",
        "--model",
        "-m",
        help="Local Whisper model name.",
    ),
    device: str = typer.Option(
        "auto",
        "--device",
        help="Transcription device: auto, cuda, or cpu.",
    ),
    output_format: str = typer.Option(
        "md",
        "--format",
        help="Transcript output format: md or txt.",
    ),
    fail_fast: bool = typer.Option(
        False,
        "--fail-fast",
        help="Stop batch processing after the first failed audio file.",
    ),
) -> None:
    device = _validate_device(device)
    transcript_format = _validate_transcript_format(output_format)
    output_dir = _resolve_output_dir(out)
    audio_paths = _collect_audio_paths(files=files, directory=directory, recursive=recursive)

    with RichExportReporter(console) as reporter:
        summary = AudioFileTranscriber().transcribe_files(
            audio_paths,
            AudioTranscriptionOptions(
                output_dir=output_dir,
                model_name=model,
                device=device,
                output_format=transcript_format,
                fail_fast=fail_fast,
            ),
            reporter=reporter,
        )

    if summary.failures:
        _print_audio_failures(summary.failures)
        raise typer.Exit(code=1)

    console.print(f"[green]Done[/green]: transcribed {len(summary.successes)} audio file(s).")


@app.command("doctor")
def doctor_command() -> None:
    """Print local GPU/PyTorch diagnostics."""
    report = torch_device_report()

    table = Table(title="TikTokExport Device Diagnostics")
    table.add_column("Check")
    table.add_column("Value")
    for key, value in report.items():
        table.add_row(key, str(value))
    console.print(table)

    if not report["cuda_available"]:
        console.print(
            "[yellow]CUDA is not available to PyTorch in this environment. "
            "Whisper will run on CPU until a CUDA-enabled torch build and compatible "
            "NVIDIA driver are installed.[/yellow]"
        )


def _collect_urls(urls: list[str] | None, file: Path | None) -> list[str]:
    if bool(urls) == bool(file):
        raise typer.BadParameter("Pass TikTok URL(s) or --file links.txt.")

    if file is not None:
        if not file.exists() or not file.is_file():
            raise typer.BadParameter(f"Links file does not exist: {file}")
        collected = parse_links_file(file)
    else:
        collected = _dedupe_non_empty_urls(urls or [])

    if not collected:
        raise typer.BadParameter("No TikTok URLs found.")

    return collected


def _dedupe_non_empty_urls(urls: list[str]) -> list[str]:
    collected: list[str] = []
    seen: set[str] = set()
    for raw_url in urls:
        url = raw_url.strip()
        if not url or url in seen:
            continue
        seen.add(url)
        collected.append(url)
    return collected


def _collect_audio_paths(
    files: list[Path] | None,
    directory: Path | None,
    recursive: bool,
) -> list[Path]:
    if bool(files) == bool(directory):
        raise typer.BadParameter("Pass audio file(s) or --dir audio-folder.")

    if directory is not None:
        try:
            paths = collect_audio_files(directory, recursive=recursive)
        except ValueError as exc:
            raise typer.BadParameter(str(exc)) from exc
    else:
        paths = list(files or [])

    if not paths:
        raise typer.BadParameter("No audio files found.")

    return paths


def _resolve_output_dir(out: Path | None) -> Path:
    if out is not None:
        return out.expanduser().resolve()

    config = load_config()
    if config.output_dir is not None:
        return config.output_dir.expanduser().resolve()

    return default_output_dir().expanduser().resolve()


def _validate_device(device: str) -> str:
    normalized = device.strip().lower()
    if normalized not in {"auto", "cuda", "cpu"}:
        raise typer.BadParameter("Device must be one of: auto, cuda, cpu.")
    return normalized


def _validate_transcript_format(output_format: str) -> TranscriptFormat:
    try:
        return normalize_transcript_format(output_format)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc


def _print_failures(failures: tuple) -> None:
    table = Table(title="Failed URLs")
    table.add_column("URL", overflow="fold")
    table.add_column("Error", overflow="fold")

    for failure in failures:
        table.add_row(failure.source_url, failure.error)

    console.print(table)


def _print_audio_failures(failures: tuple[AudioTranscriptionFailure, ...]) -> None:
    table = Table(title="Failed audio files")
    table.add_column("File", overflow="fold")
    table.add_column("Error", overflow="fold")

    for failure in failures:
        table.add_row(str(failure.source_path), failure.error)

    console.print(table)
