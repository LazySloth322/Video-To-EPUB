"""Small shared utilities."""

from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Any


def eprint(*args: Any, **kwargs: Any) -> None:
    """Print to stderr immediately."""
    kwargs.setdefault("file", sys.stderr)
    kwargs.setdefault("flush", True)
    print(*args, **kwargs)


def format_timecode(seconds: float) -> str:
    """
    Format seconds as HH:MM:SS.mmm for captions.
    """
    if not math.isfinite(seconds) or seconds < 0:
        seconds = 0.0

    total_ms = int(round(seconds * 1000))
    hours, rem = divmod(total_ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, millis = divmod(rem, 1_000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


def format_filename_timestamp(seconds: float) -> str:
    """
    Format seconds as HH-MM-SS for stable filenames.

    The exact numeric timestamp is preserved separately in Screenshot.timestamp.
    """
    if not math.isfinite(seconds) or seconds < 0:
        seconds = 0.0

    total_s = int(math.floor(seconds))
    hours, rem = divmod(total_s, 3600)
    minutes, secs = divmod(rem, 60)
    return f"{hours:02d}-{minutes:02d}-{secs:02d}"


def ensure_parent_dir(path: Path) -> None:
    """Create the parent directory for path if needed."""
    path.parent.mkdir(parents=True, exist_ok=True)