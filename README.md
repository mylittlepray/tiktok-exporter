# TikTokExport

CLI for saving TikTok videos as Obsidian-friendly Markdown notes. It downloads the video, transcribes it with local Whisper, and writes a `.md` file next to the saved video.

## Install

```powershell
uv sync
```

The first real export can take time because `yt-dlp`, Whisper dependencies, and the `turbo` model need to be available locally.

## Configure

By default, exports are written to the project `export/` folder. You can set a different default Obsidian output folder:

```powershell
uv run tiktokexport config init --out "C:\path\to\Obsidian\TikTok"
```

## Export

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
uv run python -c "import torch; print(torch.__version__); print(torch.cuda.is_available()); print(torch.version.cuda)"
```

If this prints a CPU-only build or `False`, install a CUDA-enabled PyTorch build that matches your NVIDIA driver/CUDA setup.
