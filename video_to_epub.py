#!/usr/bin/env python3
"""
Convenience entry point so the sample command works from the project root:

    python video_to_epub.py presentation.mp4 --output presentation.epub
"""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"

if SRC.exists() and str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from video_to_epub.cli import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())