from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from platformdirs import user_config_dir


APP_NAME = "TikTokExport"
CONFIG_FILENAME = "config.yaml"
DEFAULT_EXPORT_DIRNAME = "export"


@dataclass(frozen=True)
class AppConfig:
    output_dir: Path | None = None


def config_path() -> Path:
    return Path(user_config_dir(APP_NAME)) / CONFIG_FILENAME


def project_root() -> Path:
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "pyproject.toml").exists():
            return candidate
    return Path.cwd().resolve()


def default_output_dir() -> Path:
    return project_root() / DEFAULT_EXPORT_DIRNAME


def load_config(path: Path | None = None) -> AppConfig:
    path = path or config_path()
    if not path.exists():
        return AppConfig()

    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Config file must contain a YAML mapping: {path}")

    output_dir = _optional_path(data.get("output_dir"))
    return AppConfig(output_dir=output_dir)


def save_config(config: AppConfig, path: Path | None = None) -> Path:
    path = path or config_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    data: dict[str, Any] = {}
    if config.output_dir is not None:
        data["output_dir"] = str(config.output_dir)

    path.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return path


def init_config(output_dir: Path, path: Path | None = None) -> Path:
    output_dir = output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    return save_config(AppConfig(output_dir=output_dir), path=path)


def _optional_path(value: Any) -> Path | None:
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise ValueError("Config value output_dir must be a string path.")
    return Path(value).expanduser()
