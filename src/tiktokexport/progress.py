from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    ProgressColumn,
    SpinnerColumn,
    Task,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.text import Text


class ExportReporter(Protocol):
    def start_batch(self, total: int) -> None:
        ...

    def start_video(self, index: int, total: int, url: str) -> None:
        ...

    def stage(self, message: str) -> None:
        ...

    def warning(self, message: str) -> None:
        ...

    def transcribing_file(self, path: Path, device: str) -> None:
        ...

    def tqdm(self, *args: Any, **kwargs: Any) -> Any:
        ...

    def success(self, markdown_path: Path) -> None:
        ...

    def failure(self, url: str, error: str) -> None:
        ...


class SpeedColumn(ProgressColumn):
    def render(self, task: Task) -> Text:
        speed = task.speed
        unit = task.fields.get("unit", "items")
        if speed is None:
            return Text(f"-- {unit}/s")
        return Text(f"{speed:,.0f} {unit}/s")


class RichExportReporter:
    def __init__(self, console: Console) -> None:
        self.console = console
        self.current_stage = "Starting"
        self.current_file = ""
        self.current_device = ""
        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold cyan]{task.fields[stage]}"),
            BarColumn(),
            TaskProgressColumn(),
            TextColumn("{task.completed:,.0f}/{task.total:,.0f} {task.fields[unit]}"),
            SpeedColumn(),
            TimeRemainingColumn(),
            TimeElapsedColumn(),
            console=console,
        )

    def __enter__(self) -> "RichExportReporter":
        self.progress.start()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.progress.stop()

    def start_batch(self, total: int) -> None:
        self.console.print(f"[bold]Exporting {total} TikTok video(s)[/bold]")

    def start_video(self, index: int, total: int, url: str) -> None:
        self.console.rule(f"Video {index}/{total}")
        self.console.print(url)

    def stage(self, message: str) -> None:
        self.current_stage = message
        self.console.print(f"[cyan]{message}[/cyan]")

    def warning(self, message: str) -> None:
        self.console.print(f"[yellow]{message}[/yellow]")

    def transcribing_file(self, path: Path, device: str) -> None:
        self.current_file = path.name
        self.current_device = device
        self.current_stage = f"Transcribing {path.name} on {device}"
        self.console.print(f"[cyan]{self.current_stage}[/cyan]")

    def tqdm(self, *args: Any, **kwargs: Any) -> "_RichTqdm":
        return _RichTqdm(self, *args, **kwargs)

    def success(self, markdown_path: Path) -> None:
        self.console.print(f"[green]OK[/green] {markdown_path}")

    def failure(self, url: str, error: str) -> None:
        self.console.print(f"[red]FAILED[/red] {url}: {error}")


class _RichTqdm:
    def __init__(
        self,
        reporter: RichExportReporter,
        *_args: Any,
        total: float | None = None,
        unit: str = "items",
        disable: bool = False,
        **_kwargs: Any,
    ) -> None:
        self.reporter = reporter
        self.total = total or 0
        self.unit = unit
        self.disable = disable
        self.task_id: int | None = None

    def __enter__(self) -> "_RichTqdm":
        if not self.disable:
            self.task_id = self.reporter.progress.add_task(
                "",
                total=self.total,
                stage=self.reporter.current_stage,
                unit=self.unit,
            )
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def update(self, value: float = 1) -> None:
        if self.task_id is not None:
            self.reporter.progress.update(self.task_id, advance=value)

    def close(self) -> None:
        if self.task_id is not None:
            self.reporter.progress.update(self.task_id, completed=self.total)
            self.task_id = None

    def set_description(self, *_args: Any, **_kwargs: Any) -> None:
        return None

    def set_postfix(self, *_args: Any, **_kwargs: Any) -> None:
        return None
