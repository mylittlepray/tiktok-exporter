# TikTokExport

CLI for local Whisper transcription workflows. It can export TikTok videos into Obsidian-friendly Markdown notes and transcribe local audio files into Markdown or plain text.

The code is split by responsibility:

- `tiktokexport.core`: shared media, ffmpeg, filename, and Whisper transcription logic.
- `tiktokexport.tiktok`: TikTok download/export workflow and TikTok Markdown rendering.
- `tiktokexport.cli`: Typer command layer.

## Install

```powershell
.\scripts\setup.ps1
```

The setup script creates the virtual environment, installs project dependencies, checks NVIDIA/PyTorch GPU support, and prints device diagnostics.

The first real export can take time because `yt-dlp`, Whisper dependencies, and the `turbo` model need to be available locally.

## Configure

By default, exports are written to the project `export/` folder. You can set a different default Obsidian output folder:

```powershell
uv run tiktokexport config init --out "C:\path\to\Obsidian\TikTok"
```

## Export TikTok

Single URL:

```powershell
uv run tiktokexport export "https://www.tiktok.com/@account/video/123"
```

TXT file with one URL per line:

```powershell
uv run tiktokexport export --file links.txt
```

Useful flags:

```powershell
uv run tiktokexport export --file links.txt --out "C:\vault\TikTok" --model turbo
uv run tiktokexport export "https://..." --device auto
uv run tiktokexport export "https://..." --cookies cookies.txt
uv run tiktokexport export "https://..." --cookies-from-browser chrome
uv run tiktokexport export --file links.txt --fail-fast
```

TXT input ignores blank lines and lines that start with `#`. Duplicate URLs in one run are skipped.

If neither `--out` nor a saved config value is set, output goes to:

```text
export/
```

## Output

For each video, TikTokExport creates files like:

```text
2026-05-14_author_1234567890.md
2026-05-14_author_1234567890.mp4
```

The Markdown note contains YAML frontmatter with `created_at`, `tags: [tiktok]`, the original URL, account, description, and local video filename, followed by the full Whisper transcript.

## Transcribe Audio Files

Single audio file:

```powershell
uv run tiktokexport transcribe "C:\audio\voice-note.mp3"
```

Multiple audio files:

```powershell
uv run tiktokexport transcribe "C:\audio\meeting.wav" "C:\audio\memo.m4a"
```

Useful flags:

```powershell
uv run tiktokexport transcribe "C:\audio\meeting.wav" --out "C:\vault\Transcripts"
uv run tiktokexport transcribe "C:\audio\meeting.wav" --format txt
uv run tiktokexport transcribe "C:\audio\meeting.wav" --model turbo --device auto
uv run tiktokexport transcribe "C:\audio\bad.wav" "C:\audio\good.mp3" --fail-fast
```

Supported audio extensions: `.aac`, `.aiff`, `.alac`, `.flac`, `.m4a`, `.mp3`, `.oga`, `.ogg`, `.opus`, `.wav`, `.wma`.

Audio transcripts are written with names like:

```text
2026-05-14_voice-note.md
2026-05-14_meeting.txt
```

Markdown audio transcripts contain YAML frontmatter with `created_at`, `tags: [transcription, audio]`, `source_file`, and `media_type`, followed by the transcript.

## Transcription device and progress

`--device auto` is the default. It uses CUDA first when PyTorch can see a CUDA device, then falls back to CPU if the CUDA attempt fails.

```powershell
uv run tiktokexport export "https://..." --device auto
uv run tiktokexport export "https://..." --device cuda
uv run tiktokexport export "https://..." --device cpu
```

During export the CLI logs the current video, pipeline stage, active transcription file, device, progress, speed, elapsed time, and estimated remaining time.

If the app still uses CPU, check what PyTorch can see:

```powershell
uv run tiktokexport doctor
uv run python -c "import torch; print(torch.__version__); print(torch.cuda.is_available()); print(torch.version.cuda)"
```

If this prints a CPU-only build or `False`, install a CUDA-enabled PyTorch build that matches your NVIDIA driver/CUDA setup.

On Windows, a common cause is a CPU-only torch package inside `.venv`. If `nvidia-smi` sees your GPU but `tiktokexport doctor` shows `torch_version` ending in `+cpu`, fix PyTorch rather than the app.

Recommended path:

1. Update the NVIDIA driver to a current version.
2. Run `.\scripts\setup.ps1` again.
3. Re-run `uv run tiktokexport doctor` and confirm `cuda_available` is `True`.

This project is configured to use the official PyTorch CUDA 11.8 wheel index on Windows. CUDA 11.8 requires NVIDIA Windows driver `522.06` or newer.

Manual recovery command if the environment was already created with CPU-only torch:

```powershell
uv pip uninstall torch torchvision torchaudio
uv pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
uv run tiktokexport doctor
```

If you cannot update the NVIDIA driver and it only supports CUDA 11.7, use an older Python/PyTorch combination that still provides CUDA 11.7 wheels, or create a separate Python 3.10/3.11 environment for this project.
