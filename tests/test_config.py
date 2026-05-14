from pathlib import Path

from tiktokexport.config import default_output_dir


def test_default_output_dir_is_project_export_folder() -> None:
    assert default_output_dir().name == "export"
    assert (default_output_dir().parent / "pyproject.toml").exists()
