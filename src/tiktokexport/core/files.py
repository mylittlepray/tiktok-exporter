from __future__ import annotations

from pathlib import Path

from tiktokexport.core.filenames import sanitize_component, unique_base_path


def ensure_output_dir(path: Path) -> Path:
    output_dir = path.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def build_unique_output_path(
    output_dir: Path,
    base: str,
    suffix: str,
) -> Path:
    unique_base = unique_base_path(output_dir, sanitize_component(base, fallback="output"), (suffix,))
    return output_dir / f"{unique_base}{suffix}"

