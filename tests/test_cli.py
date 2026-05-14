from pathlib import Path

import typer
import pytest

from tiktokexport.cli import _resolve_output_dir, _validate_device
from tiktokexport.config import AppConfig


def test_resolve_output_dir_uses_project_export_default(
    monkeypatch,
    tmp_path: Path,
) -> None:
    expected = tmp_path / "export"

    monkeypatch.setattr("tiktokexport.cli.load_config", lambda: AppConfig())
    monkeypatch.setattr("tiktokexport.cli.default_output_dir", lambda: expected)

    assert _resolve_output_dir(None) == expected.resolve()


def test_validate_device_normalizes_known_values() -> None:
    assert _validate_device(" CUDA ") == "cuda"


def test_validate_device_rejects_unknown_values() -> None:
    with pytest.raises(typer.BadParameter):
        _validate_device("metal")
