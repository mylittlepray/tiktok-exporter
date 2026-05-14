from __future__ import annotations

import importlib
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from .ffmpeg import ensure_ffmpeg_command_on_path
from .progress import ExportReporter


class TranscriptionError(RuntimeError):
    pass


class WhisperTranscriber:
    def __init__(self, model_name: str = "turbo", device: str = "auto") -> None:
        self.model_name = model_name
        self.device = device
        self._active_device: str | None = None
        self._model = None

    def transcribe(
        self,
        video_path: Path,
        reporter: ExportReporter | None = None,
    ) -> str:
        ensure_ffmpeg_command_on_path()

        try:
            import whisper
        except ImportError as exc:
            raise TranscriptionError(
                "openai-whisper is not installed. Run `uv sync` before exporting videos."
            ) from exc

        attempts = _device_attempts(self.device, _cuda_available())
        last_error: Exception | None = None

        for index, device in enumerate(attempts):
            try:
                if reporter is not None and device == "cpu" and index > 0:
                    reporter.warning("CUDA transcription failed; falling back to CPU.")
                result = self._transcribe_on_device(whisper, video_path, device, reporter)
                return str(result.get("text") or "").strip()
            except Exception as exc:
                last_error = exc
                self._model = None
                self._active_device = None
                _empty_cuda_cache()
                if device == "cpu" or index == len(attempts) - 1:
                    break

        raise TranscriptionError(str(last_error)) from last_error

    def _transcribe_on_device(
        self,
        whisper: Any,
        video_path: Path,
        device: str,
        reporter: ExportReporter | None,
    ) -> dict[str, Any]:
        if reporter is not None:
            reporter.stage(f"Loading Whisper model '{self.model_name}' on {device}")

        if self._model is None or self._active_device != device:
            self._model = whisper.load_model(self.model_name, device=device)
            self._active_device = device

        if reporter is not None:
            reporter.transcribing_file(video_path, device)

        with _whisper_tqdm(reporter):
            return self._model.transcribe(str(video_path), verbose=False)


def _device_attempts(device_preference: str, cuda_available: bool) -> list[str]:
    normalized = device_preference.strip().lower()
    if normalized == "cpu":
        return ["cpu"]
    if normalized == "cuda":
        return ["cuda", "cpu"]
    if normalized != "auto":
        raise TranscriptionError("Device must be one of: auto, cuda, cpu.")
    if cuda_available:
        return ["cuda", "cpu"]
    return ["cpu"]


def _cuda_available() -> bool:
    try:
        import torch
    except ImportError:
        return False

    return bool(torch.cuda.is_available())


def _empty_cuda_cache() -> None:
    try:
        import torch
    except ImportError:
        return

    if torch.cuda.is_available():
        torch.cuda.empty_cache()


@contextmanager
def _whisper_tqdm(reporter: ExportReporter | None) -> Iterator[None]:
    if reporter is None:
        yield
        return

    transcribe_module = importlib.import_module("whisper.transcribe")
    original_tqdm = transcribe_module.tqdm.tqdm
    transcribe_module.tqdm.tqdm = reporter.tqdm
    try:
        yield
    finally:
        transcribe_module.tqdm.tqdm = original_tqdm
