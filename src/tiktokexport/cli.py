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
from tiktokexport.config import AppConfig, default_output_dir, init_config, load_config
from tiktokexport.core.transcriber import torch_device_report
from tiktokexport.links import parse_links_file
from tiktokexport.progress import RichExportReporter
from tiktokexport.tiktok.link_exporter import (
    LinkSection,
    export_tiktok_links,
    load_tiktok_link_blocks,
    normalize_link_sections,
)
from tiktokexport.tiktok.models import ExportFailure, ExportOptions
from tiktokexport.tiktok.pipeline import TikTokExporter


app = typer.Typer(help="Export TikTok media and transcribe local audio.")
tiktok_app = typer.Typer(help="Export TikTok video and photo posts.")
audio_app = typer.Typer(help="Transcribe local audio files.")
config_app = typer.Typer(help="Manage TikTokExport configuration.")

app.add_typer(tiktok_app, name="tiktok")
app.add_typer(audio_app, name="audio")
app.add_typer(config_app, name="config")

console = Console()


@config_app.command("init")
def init_config_command(
    out: Path = typer.Option(
        ...,
        "--out",
        "-o",
        help="Default folder for exported notes and media.",
    ),
) -> None:
    path = init_config(out)
    console.print(f"Config saved: [bold]{path}[/bold]")
    console.print(f"Default output folder: [bold]{out.expanduser().resolve()}[/bold]")


@tiktok_app.command("export")
def tiktok_export_command(
    urls: Optional[list[str]] = typer.Argument(None, help="One or more TikTok URLs."),
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
    transcribe: bool = typer.Option(
        True,
        "--transcribe/--no-transcribe",
        help="Transcribe TikTok videos with Whisper. Photo slideshows are never transcribed.",
    ),
    model: str = typer.Option(
        "turbo",
        "--model",
        "-m",
        help="Local Whisper model name when transcription is enabled.",
    ),
    device: str = typer.Option(
        "auto",
        "--device",
        help="Transcription device: auto, cuda, or cpu.",
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
    collected_urls = _collect_urls(urls=urls, file=file)
    device = _validate_device(device)
    output_dir = _resolve_output_dir(out)
    _validate_cookies(cookies)

    with RichExportReporter(console) as reporter:
        summary = TikTokExporter().export_urls(
            collected_urls,
            ExportOptions(
                output_dir=output_dir,
                model_name=model,
                cookies=cookies,
                cookies_from_browser=cookies_from_browser,
                fail_fast=fail_fast,
                device=device,
                transcribe=transcribe,
            ),
            reporter=reporter,
        )

    if summary.failures:
        _print_report_path(summary.report_path)
        _print_tiktok_failures(summary.failures)
        raise typer.Exit(code=1)
    if summary.interrupted:
        console.print("[yellow]Interrupted[/yellow]: export report was saved.")
        _print_report_path(summary.report_path)
        raise typer.Exit(code=130)

    console.print(f"[green]Done[/green]: exported {len(summary.successes)} TikTok post(s).")
    _print_report_path(summary.report_path)


@tiktok_app.command("export-links")
def tiktok_export_links_command(
    file: Path = typer.Option(
        ...,
        "--file",
        "-f",
        help="TikTok user_data_tiktok.json export file.",
    ),
    section: Optional[list[str]] = typer.Option(
        None,
        "--section",
        "-s",
        help="Section to export: favorite, likes, or both. Can be passed multiple times.",
    ),
    out: Optional[Path] = typer.Option(
        None,
        "--out",
        "-o",
        help="Output folder for exported TXT link files. Defaults to exported_links/.",
    ),
) -> None:
    if not file.exists() or not file.is_file():
        raise typer.BadParameter(f"TikTok JSON file does not exist: {file}")

    blocks = load_tiktok_link_blocks(file)
    _print_link_block_counts(blocks.favorite_videos, blocks.like_list)
    selected_sections = _resolve_link_sections(section)
    exported = export_tiktok_links(
        blocks,
        selected_sections,
        output_dir=out.expanduser().resolve() if out is not None else None,
    )

    console.print(
        f"[green]Done[/green]: exported {exported.link_count} link(s) to "
        f"[bold]{exported.path}[/bold]"
    )


@audio_app.command("transcribe")
def audio_transcribe_command(
    files: Optional[list[Path]] = typer.Argument(
        None,
        help="One or more local audio files.",
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
    config = load_config()
    return _resolve_output_dir_from_config(out, config)


def _resolve_output_dir_from_config(out: Path | None, config: AppConfig) -> Path:
    if out is not None:
        return out.expanduser().resolve()
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


def _validate_cookies(cookies: Path | None) -> None:
    if cookies is not None and (not cookies.exists() or not cookies.is_file()):
        raise typer.BadParameter(f"Cookies file does not exist: {cookies}")


def _print_tiktok_failures(failures: tuple[ExportFailure, ...]) -> None:
    table = Table(title="Failed TikTok URLs")
    table.add_column("URL", overflow="fold")
    table.add_column("Error", overflow="fold")

    for failure in failures:
        table.add_row(failure.source_url, failure.error)

    console.print(table)


def _print_report_path(report_path: Path | None) -> None:
    if report_path is not None:
        console.print(f"Export report: [bold]{report_path}[/bold]")


def _print_link_block_counts(favorite_links: tuple[str, ...], like_links: tuple[str, ...]) -> None:
    table = Table(title="TikTok Link Blocks")
    table.add_column("Block")
    table.add_column("Links", justify="right")
    table.add_row("Favorite Videos", str(len(favorite_links)))
    table.add_row("Like List", str(len(like_links)))
    console.print(table)


def _resolve_link_sections(section: list[str] | None) -> tuple[LinkSection, ...]:
    if section:
        try:
            return normalize_link_sections(section)
        except ValueError as exc:
            raise typer.BadParameter(str(exc)) from exc

    raw = typer.prompt("Save which links? favorite, likes, or both", default="both")
    try:
        return normalize_link_sections([raw])
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc


def _print_audio_failures(failures: tuple[AudioTranscriptionFailure, ...]) -> None:
    table = Table(title="Failed audio files")
    table.add_column("File", overflow="fold")
    table.add_column("Error", overflow="fold")

    for failure in failures:
        table.add_row(str(failure.source_path), failure.error)

    console.print(table)
