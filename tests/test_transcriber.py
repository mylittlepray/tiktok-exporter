import pytest

from tiktokexport.transcriber import TranscriptionError, _device_attempts


@pytest.mark.parametrize(
    ("preference", "cuda_available", "expected"),
    [
        ("auto", True, ["cuda", "cpu"]),
        ("auto", False, ["cpu"]),
        ("cuda", False, ["cuda", "cpu"]),
        ("cpu", True, ["cpu"]),
    ],
)
def test_device_attempts(preference: str, cuda_available: bool, expected: list[str]) -> None:
    assert _device_attempts(preference, cuda_available) == expected


def test_device_attempts_rejects_unknown_device() -> None:
    with pytest.raises(TranscriptionError):
        _device_attempts("metal", cuda_available=False)
