from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from tiktokexport.tiktok.models import ExportFailure, ExportedNote, ExportSummary, UnprocessedExport


def write_export_report(
    summary: ExportSummary,
    reports_dir: Path | None = None,
    generated_at: datetime | None = None,
) -> Path:
    generated_at = generated_at or datetime.now().astimezone()
    reports_dir = reports_dir or _default_reports_dir()
    reports_dir.mkdir(parents=True, exist_ok=True)

    path = reports_dir / f"export-report-{_filename_timestamp(generated_at)}.json"
    path.write_text(
        json.dumps(_report_payload(summary), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def _report_payload(summary: ExportSummary) -> dict[str, Any]:
    return {
        "successful_exports": len(summary.successes),
        "error_exports": len(summary.failures),
        "unprocessed_exports": len(summary.unprocessed),
        "transcription_failed": sum(
            1 for item in summary.successes if item.details.transcription not in {"success", "skipped"}
        ),
        "successful": [_success_payload(item) for item in summary.successes],
        "errors": [_error_payload(item) for item in summary.failures],
        "unprocessed": [_unprocessed_payload(item) for item in summary.unprocessed],
    }


def _success_payload(item: ExportedNote) -> dict[str, Any]:
    return {
        "url": item.source_url,
        "duration_seconds": item.media_duration_seconds,
        "export_duration_seconds": item.export_duration_seconds,
        "exported_at": item.exported_at,
        "details": {
            "status": item.details.status,
            "transcription": item.details.transcription,
        },
    }


def _error_payload(item: ExportFailure) -> dict[str, str]:
    return {
        "url": item.source_url,
        "error": item.error,
        "details": item.error,
    }


def _unprocessed_payload(item: UnprocessedExport) -> dict[str, str]:
    return {
        "url": item.source_url,
        "details": item.details,
    }


def _default_reports_dir() -> Path:
    return Path.cwd() / "reports"


def _filename_timestamp(value: datetime) -> str:
    return value.isoformat(timespec="seconds").replace(":", "-")
