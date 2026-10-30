"""Dependency checks."""

from __future__ import annotations

import importlib
import shutil

from .errors import DependencyError


RUNTIME_MODULES = [
    ("whisper", "openai-whisper"),
    ("av", "av"),
    ("PIL", "Pillow"),
    ("numpy", "numpy"),
    ("ebooklib", "ebooklib"),
]


def check_dependencies(quiet: bool = False) -> None:
    """
    Verify Python packages and the FFmpeg executable required by openai-whisper.

    This does not download the Whisper model.
    """
    missing: list[str] = []

    for module_name, distribution_name in RUNTIME_MODULES:
        try:
            importlib.import_module(module_name)
        except ImportError:
            missing.append(distribution_name)

    if missing:
        pretty = ", ".join(sorted(set(missing)))
        raise DependencyError(
            "Missing Python dependencies: "
            f"{pretty}. Install them with: python -m pip install -r requirements.txt"
        )

    if shutil.which("ffmpeg") is None:
        raise DependencyError(
            "FFmpeg executable was not found on PATH. openai-whisper requires FFmpeg "
            "to extract audio from video files. Install FFmpeg and verify with: "
            "ffmpeg -version"
        )

    import whisper

    try:
        models = whisper.available_models()
    except Exception:
        models = []

    if "turbo" not in models:
        raise DependencyError(
            "The installed openai-whisper package does not expose the 'turbo' model. "
            "Upgrade with: python -m pip install --upgrade openai-whisper. "
            "Verify with: python -c \"import whisper; print(whisper.available_models())\""
        )