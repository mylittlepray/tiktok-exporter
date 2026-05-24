# TikTokExport

CLI for exporting TikTok videos/photo slideshows into Obsidian-friendly notes and transcribing local audio files with Whisper.

The project is split by responsibility:

- `tiktokexport.core`: shared domain models, ports, ffmpeg helpers, filenames, Markdown rendering, and Whisper transcription.
- `tiktokexport.tiktok`: TikTok download/classification and export workflows.
- `tiktokexport.audio_file`: local audio-file discovery and transcription workflow.
- `tiktokexport.cli`: Typer command layer.

## Install

```powershell
.\scripts\setup.ps1
```

The setup script creates the virtual environment, installs project dependencies, checks NVIDIA/PyTorch GPU support, and prints device diagnostics.

## Configure

By default, exports are written to the project `export/` folder. You can set a different default Obsidian output folder:

```powershell
uv run tiktokexport config init --out "C:\path\to\Obsidian\TikTok"
```

## Export TikTok

Single URL:

```powershell
uv run tiktokexport tiktok export "https://www.tiktok.com/@account/video/123"
```

Multiple URLs:

```powershell
uv run tiktokexport tiktok export "https://www.tiktok.com/@one/video/123" "https://www.tiktok.com/@two/video/456"
```

TXT file with one URL per line:

```powershell
uv run tiktokexport tiktok export --file links.txt
```

Useful flags:

```powershell
uv run tiktokexport tiktok export --file links.txt --out "C:\vault\TikTok"
uv run tiktokexport tiktok export "https://..." --no-transcribe
uv run tiktokexport tiktok export "https://..." --model turbo --device auto
uv run tiktokexport tiktok export "https://..." --cookies cookies.txt
uv run tiktokexport tiktok export "https://..." --cookies-from-browser chrome
uv run tiktokexport tiktok export --file links.txt --fail-fast
```

TikTok video transcription is enabled by default. Photo slideshows are exported as photos and are not transcribed.

Each TikTok batch export writes a JSON report into `reports/`. Report files are local/untracked and contain success/error/unprocessed counts, `transcription_failed`, successful URL entries with media duration, export duration, export timestamp and details, plus failed URL entries with error details.

Before downloading a URL, TikTokExport scans existing Markdown notes in the output folder. If a note already has the same `source_url`, the URL is skipped and recorded as a successful export with `details.status: already downloaded`.

If the CLI is interrupted with `Ctrl+C`, the current batch stops, processed entries stay in the report, and the current plus remaining URLs are written to the report's `unprocessed` block with `details: interrupted`.

## Export Links From TikTok Data

TikTok's downloaded account data includes liked and favorite video lists in `user_data_tiktok.json`. Export them into a TXT file:

```powershell
uv run tiktokexport tiktok export-links --file user_data_tiktok.json
```

The command shows how many links are available in `Favorite Videos` and `Like List`, then asks which block to save: `favorite`, `likes`, or `both`.

For non-interactive use:

```powershell
uv run tiktokexport tiktok export-links --file user_data_tiktok.json --section both
uv run tiktokexport tiktok export-links --file user_data_tiktok.json --section favorite --out "C:\vault\TikTok Links"
```

Link export TXT files are written to `exported_links/` by default. The folder contents are local/untracked.

## TikTok Output

Video posts are exported as a note and video file:

```text
@author - Short description.md
@author - Short description.mp4
```

Photo slideshows are exported into a dedicated folder:

```text
@author - Slideshow description/
  @author - Slideshow description.md
  01. PHOTO - @author - Slideshow description.jpg
  02. PHOTO - @author - Slideshow description.webp
```

The slideshow note contains Obsidian embeds:

```markdown
![[01. PHOTO - @author - Slideshow description.jpg]]
![[02. PHOTO - @author - Slideshow description.webp]]
```

## Transcribe Audio Files

Single audio file:

```powershell
uv run tiktokexport audio transcribe "C:\audio\voice-note.mp3"
```

Multiple audio files:

```powershell
uv run tiktokexport audio transcribe "C:\audio\meeting.wav" "C:\audio\memo.m4a"
```

Folder with audio files:

```powershell
uv run tiktokexport audio transcribe --dir "C:\audio"
uv run tiktokexport audio transcribe --dir "C:\audio" --recursive
```

Useful flags:

```powershell
uv run tiktokexport audio transcribe "C:\audio\meeting.wav" --out "C:\vault\Transcripts"
uv run tiktokexport audio transcribe "C:\audio\meeting.wav" --format txt
uv run tiktokexport audio transcribe "C:\audio\meeting.wav" --model turbo --device auto
uv run tiktokexport audio transcribe "C:\audio\bad.wav" "C:\audio\good.mp3" --fail-fast
```

Supported audio extensions: `.aac`, `.aiff`, `.alac`, `.flac`, `.m4a`, `.mp3`, `.oga`, `.ogg`, `.opus`, `.wav`, `.wma`.

## Device Diagnostics

```powershell
uv run tiktokexport doctor
```

`--device auto` uses CUDA first when PyTorch can see a CUDA device, then falls back to CPU if CUDA transcription fails.
