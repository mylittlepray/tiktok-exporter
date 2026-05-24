from __future__ import annotations

import shutil
import tempfile
import time
from datetime import date, datetime
from pathlib import Path

import yaml

from tiktokexport.core.files import ensure_output_dir
from tiktokexport.core.filenames import (
    sanitize_filename,
    summarize_sentence_for_filename,
    unique_base_path,
)
from tiktokexport.core.markdown import MarkdownNote, render_markdown_note
from tiktokexport.core.models import DownloadedPost, MediaAsset, MediaKind
from tiktokexport.core.ports import (
    MediaDownloader,
    NoOpOcrRecognizer,
    NoOpTagGenerator,
    OcrRecognizer,
    TagGenerator,
    Transcriber,
)
from tiktokexport.core.transcriber import WhisperTranscriber
from tiktokexport.progress import ExportReporter
from tiktokexport.tiktok.downloader import TikTokDownloader
from tiktokexport.tiktok.models import (
    ExportDetails,
    ExportedNote,
    ExportFailure,
    ExportOptions,
    ExportSummary,
    UnprocessedExport,
)
from tiktokexport.tiktok.report import write_export_report


class TikTokExporter:
    def __init__(
        self,
        downloader: MediaDownloader | None = None,
        transcriber: Transcriber | None = None,
        ocr: OcrRecognizer | None = None,
        tag_generator: TagGenerator | None = None,
    ) -> None:
        self.downloader = downloader or TikTokDownloader()
        self.transcriber = transcriber
        self.ocr = ocr or NoOpOcrRecognizer()
        self.tag_generator = tag_generator or NoOpTagGenerator()

    def export_urls(
        self,
        urls: list[str],
        options: ExportOptions,
        reporter: ExportReporter | None = None,
    ) -> ExportSummary:
        successes: list[ExportedNote] = []
        failures: list[ExportFailure] = []
        unprocessed: list[UnprocessedExport] = []
        interrupted = False
        transcriber = self._build_transcriber(options) if options.transcribe else None

        if reporter is not None:
            reporter.start_batch(len(urls))

        for index, url in enumerate(urls, start=1):
            if reporter is not None:
                reporter.start_video(index, len(urls), url)
            try:
                started_at = time.perf_counter()
                exported_at = datetime.now().astimezone().isoformat(timespec="seconds")
                note = self.export_one(url, options, transcriber, reporter)
                successes.append(
                    _with_export_timing(
                        note,
                        export_duration_seconds=time.perf_counter() - started_at,
                        exported_at=exported_at,
                    )
                )
                if reporter is not None:
                    reporter.success(successes[-1].markdown_path)
            except Exception as exc:
                failures.append(ExportFailure(source_url=url, error=str(exc)))
                if reporter is not None:
                    reporter.failure(url, str(exc))
                if options.fail_fast:
                    break
            except KeyboardInterrupt:
                interrupted = True
                unprocessed.extend(
                    UnprocessedExport(source_url=remaining_url, details="interrupted")
                    for remaining_url in urls[index - 1 :]
                )
                if reporter is not None:
                    reporter.warning("Export interrupted; saving report for processed and unprocessed URLs.")
                break

        summary = ExportSummary(
            successes=tuple(successes),
            failures=tuple(failures),
            unprocessed=tuple(unprocessed),
            interrupted=interrupted,
        )
        report_path = write_export_report(summary)
        return ExportSummary(
            successes=summary.successes,
            failures=summary.failures,
            unprocessed=summary.unprocessed,
            report_path=report_path,
            interrupted=summary.interrupted,
        )

    def export_one(
        self,
        url: str,
        options: ExportOptions,
        transcriber: Transcriber | None = None,
        reporter: ExportReporter | None = None,
    ) -> ExportedNote:
        output_dir = ensure_output_dir(options.output_dir)
        created_at = options.created_at or date.today().isoformat()
        existing_note = find_existing_note_by_source_url(output_dir, url)
        if existing_note is not None:
            return ExportedNote(
                source_url=url,
                markdown_path=existing_note,
                media_paths=(),
                media_kind=_media_kind_from_existing_note(existing_note),
                media_duration_seconds=0.0,
                export_duration_seconds=0.0,
                exported_at="",
                details=ExportDetails(status="already downloaded", transcription="skipped"),
            )

        active_transcriber = transcriber
        if active_transcriber is None and options.transcribe:
            active_transcriber = self._build_transcriber(options)

        with tempfile.TemporaryDirectory(prefix="tiktokexport-") as temp_dir_raw:
            temp_dir = Path(temp_dir_raw)
            if reporter is not None:
                reporter.stage("Downloading TikTok media")
            downloaded = self.downloader.download(
                url,
                temp_dir,
                cookies=options.cookies,
                cookies_from_browser=options.cookies_from_browser,
            )

            if downloaded.kind == MediaKind.VIDEO:
                return self._export_video(
                    downloaded=downloaded,
                    output_dir=output_dir,
                    created_at=created_at,
                    transcriber=active_transcriber,
                    reporter=reporter,
                )
            if downloaded.kind == MediaKind.PHOTO_SLIDESHOW:
                return self._export_photo_slideshow(
                    downloaded=downloaded,
                    output_dir=output_dir,
                    created_at=created_at,
                    reporter=reporter,
                )

            raise ValueError(f"Unsupported TikTok media kind: {downloaded.kind.value}")

    def _build_transcriber(self, options: ExportOptions) -> Transcriber:
        return self.transcriber or WhisperTranscriber(options.model_name, device=options.device)

    def _export_video(
        self,
        *,
        downloaded: DownloadedPost,
        output_dir: Path,
        created_at: str,
        transcriber: Transcriber | None,
        reporter: ExportReporter | None,
    ) -> ExportedNote:
        video_asset = _single_asset(downloaded, MediaKind.VIDEO)
        suffix = video_asset.path.suffix or ".mp4"
        base = build_tiktok_base_filename(
            downloaded.metadata.account,
            downloaded.metadata.description,
        )
        base = unique_base_path(output_dir, base, (".md", suffix))
        video_path = output_dir / f"{base}{suffix}"
        markdown_path = output_dir / f"{base}.md"

        if reporter is not None:
            reporter.stage("Saving TikTok video")
        shutil.move(str(video_asset.path), video_path)

        transcript = ""
        transcription_details = "success" if transcriber is not None else "skipped"
        if transcriber is not None:
            if reporter is not None:
                reporter.stage("Transcribing TikTok video")
            try:
                transcript = transcriber.transcribe(video_path, reporter=reporter)
            except Exception as exc:
                transcription_details = str(exc)
                if reporter is not None:
                    reporter.warning(f"Transcription failed: {exc}")

        if reporter is not None:
            reporter.stage("Saving Markdown note")
        markdown_path.write_text(
            render_tiktok_video_note(
                downloaded=downloaded,
                created_at=created_at,
                video_filename=video_path.name,
                transcript=transcript,
                generated_tags=tuple(
                    self.tag_generator.generate_tags(
                        description=downloaded.metadata.description,
                        transcript=transcript,
                    )
                ),
            ),
            encoding="utf-8",
        )

        return ExportedNote(
            source_url=downloaded.metadata.source_url,
            markdown_path=markdown_path,
            media_paths=(video_path,),
            media_kind=MediaKind.VIDEO,
            media_duration_seconds=max(downloaded.metadata.duration_seconds, 0.0),
            export_duration_seconds=0.0,
            exported_at="",
            details=ExportDetails(status="success", transcription=transcription_details),
        )

    def _export_photo_slideshow(
        self,
        *,
        downloaded: DownloadedPost,
        output_dir: Path,
        created_at: str,
        reporter: ExportReporter | None,
    ) -> ExportedNote:
        photo_assets = tuple(asset for asset in downloaded.assets if asset.kind == MediaKind.PHOTO)
        if not photo_assets:
            raise ValueError("TikTok slideshow has no photo assets.")

        base = build_tiktok_base_filename(
            downloaded.metadata.account,
            downloaded.metadata.description,
        )
        folder_base = unique_folder_path(output_dir, base)
        note_dir = output_dir / folder_base
        note_dir.mkdir(parents=True, exist_ok=False)
        markdown_path = note_dir / f"{folder_base}.md"

        if reporter is not None:
            reporter.stage("Saving TikTok slideshow photos")
        photo_paths = tuple(
            _move_numbered_photo(asset, note_dir, folder_base)
            for asset in sorted(photo_assets, key=lambda item: item.sequence)
        )
        ocr_texts = tuple(
            text
            for path in photo_paths
            if (text := self.ocr.recognize(path, reporter=reporter).strip())
        )
        generated_tags = tuple(
            self.tag_generator.generate_tags(
                description=downloaded.metadata.description,
                ocr_text="\n\n".join(ocr_texts),
            )
        )

        if reporter is not None:
            reporter.stage("Saving Markdown note")
        markdown_path.write_text(
            render_tiktok_photo_note(
                downloaded=downloaded,
                created_at=created_at,
                photo_filenames=tuple(path.name for path in photo_paths),
                ocr_texts=ocr_texts,
                generated_tags=generated_tags,
            ),
            encoding="utf-8",
        )

        return ExportedNote(
            source_url=downloaded.metadata.source_url,
            markdown_path=markdown_path,
            media_paths=photo_paths,
            media_kind=MediaKind.PHOTO_SLIDESHOW,
            media_duration_seconds=0.0,
            export_duration_seconds=0.0,
            exported_at="",
            details=ExportDetails(status="success", transcription="skipped"),
        )


def render_tiktok_video_note(
    *,
    downloaded: DownloadedPost,
    created_at: str,
    video_filename: str,
    transcript: str,
    generated_tags: tuple[str, ...] = (),
) -> str:
    metadata = downloaded.metadata
    sections = [("Описание", _description_or_fallback(metadata.description))]
    if transcript.strip():
        sections.append(("Транскрипт", transcript.strip()))

    tags = ["tiktok", "video"]
    tags.extend(_dedupe_tag_values(list(generated_tags)))

    return render_markdown_note(
        MarkdownNote(
            title=f"TikTok - {metadata.account or '@unknown'}",
            frontmatter={
                "created_at": created_at,
                "tags": tags,
                "source_url": metadata.source_url,
                "account": metadata.account,
                "description": metadata.description,
                "media_type": MediaKind.VIDEO.value,
                "video_file": video_filename,
            },
            sections=tuple(sections),
        )
    )


def render_tiktok_photo_note(
    *,
    downloaded: DownloadedPost,
    created_at: str,
    photo_filenames: tuple[str, ...],
    ocr_texts: tuple[str, ...] = (),
    generated_tags: tuple[str, ...] = (),
) -> str:
    metadata = downloaded.metadata
    photo_embeds = "\n".join(f"![[{filename}]]" for filename in photo_filenames)
    sections = [
        ("Описание", _description_or_fallback(metadata.description)),
        ("Содержание", photo_embeds),
    ]
    if ocr_texts:
        sections.append(("OCR", "\n\n".join(ocr_texts)))

    tags = ["tiktok", "photo_slideshow"]
    tags.extend(_dedupe_tag_values(list(generated_tags)))

    return render_markdown_note(
        MarkdownNote(
            title=f"TikTok - {metadata.account or '@unknown'}",
            frontmatter={
                "created_at": created_at,
                "tags": tags,
                "source_url": metadata.source_url,
                "account": metadata.account,
                "description": metadata.description,
                "media_type": MediaKind.PHOTO_SLIDESHOW.value,
                "photo_files": list(photo_filenames),
            },
            sections=tuple(sections),
        )
    )


def build_tiktok_base_filename(account: str, description: str) -> str:
    account_part = sanitize_filename(account or "@unknown", fallback="@unknown", max_length=40)
    description_part = summarize_sentence_for_filename(description, limit=50)
    description_part = sanitize_filename(description_part, fallback="без описания", max_length=50)
    return f"{account_part} - {description_part}"


def unique_folder_path(output_dir: Path, base: str) -> str:
    candidate = base
    counter = 2
    while (output_dir / candidate).exists():
        candidate = f"{base}_{counter}"
        counter += 1
    return candidate


def _single_asset(downloaded: DownloadedPost, kind: MediaKind) -> MediaAsset:
    for asset in downloaded.assets:
        if asset.kind == kind:
            return asset
    raise ValueError(f"TikTok post has no {kind.value} asset.")


def _move_numbered_photo(asset: MediaAsset, note_dir: Path, base: str) -> Path:
    suffix = asset.path.suffix or ".jpg"
    target = note_dir / f"{asset.sequence:02d}. PHOTO - {base}{suffix}"
    shutil.move(str(asset.path), target)
    return target


def _description_or_fallback(description: str) -> str:
    return description.strip() or "Описание отсутствует."


def _dedupe_tag_values(tags: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for tag in tags:
        normalized = tag.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def _with_export_timing(
    note: ExportedNote,
    *,
    export_duration_seconds: float,
    exported_at: str,
) -> ExportedNote:
    return ExportedNote(
        source_url=note.source_url,
        markdown_path=note.markdown_path,
        media_paths=note.media_paths,
        media_kind=note.media_kind,
        media_duration_seconds=note.media_duration_seconds,
        export_duration_seconds=round(max(export_duration_seconds, 0.0), 3),
        exported_at=exported_at,
        details=note.details,
    )


def find_existing_note_by_source_url(output_dir: Path, source_url: str) -> Path | None:
    if not output_dir.exists():
        return None

    for path in sorted(output_dir.rglob("*.md")):
        frontmatter = _read_markdown_frontmatter(path)
        if frontmatter.get("source_url") == source_url:
            return path
    return None


def _read_markdown_frontmatter(path: Path) -> dict[str, object]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {}

    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}

    try:
        loaded = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _media_kind_from_existing_note(path: Path) -> MediaKind:
    media_type = _read_markdown_frontmatter(path).get("media_type")
    try:
        return MediaKind(str(media_type))
    except ValueError:
        return MediaKind.VIDEO
