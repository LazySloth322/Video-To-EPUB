"""Command-line configuration."""

from __future__ import annotations

import argparse
from pathlib import Path


DEFAULT_INTERVAL_SECONDS = 5.0
DEFAULT_PIXEL_DIFF_THRESHOLD = 12
DEFAULT_CHANGE_THRESHOLD = 0.2
DEFAULT_RESIZE_WIDTH = 640
DEFAULT_CONFIRM_SAMPLES = 1
DEFAULT_DEBOUNCE_SECONDS = 1.0
DEFAULT_SCREENSHOT_WIDTH = 1920
DEFAULT_JPEG_QUALITY = 90


def _int_range(min_value: int, max_value: int):
    def checker(value: str) -> int:
        ivalue = int(value)
        if ivalue < min_value or ivalue > max_value:
            raise argparse.ArgumentTypeError(
                f"must be between {min_value} and {max_value}, got {ivalue}"
            )
        return ivalue

    return checker


def _nonnegative_int(value: str) -> int:
    ivalue = int(value)
    if ivalue < 0:
        raise argparse.ArgumentTypeError(f"must be >= 0, got {ivalue}")
    return ivalue


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="video_to_epub.py",
        description=(
            "Convert a video presentation into an EPUB containing a timestamped "
            "Whisper transcript interleaved with slide/scene screenshots."
        ),
    )

    parser.add_argument(
        "input_video",
        type=Path,
        help="Local input video file.",
    )

    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Output EPUB path. Defaults to input filename with .epub extension.",
    )

    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite the output EPUB if it already exists.",
    )

    parser.add_argument(
        "--keep-temp",
        action="store_true",
        help="Keep temporary screenshots/files for debugging.",
    )

    parser.add_argument(
        "--temp-dir",
        type=Path,
        default=None,
        help="Directory in which to create temporary files.",
    )

    parser.add_argument(
        "--interval-seconds",
        type=float,
        default=DEFAULT_INTERVAL_SECONDS,
        help=(
            "Video sampling interval in seconds. Default: "
            f"{DEFAULT_INTERVAL_SECONDS}."
        ),
    )

    parser.add_argument(
        "--pixel-diff-threshold",
        type=_int_range(0, 255),
        default=DEFAULT_PIXEL_DIFF_THRESHOLD,
        help=(
            "Per-pixel grayscale intensity difference required to count a pixel as "
            "changed. Range 0-255. Default: "
            f"{DEFAULT_PIXEL_DIFF_THRESHOLD}."
        ),
    )

    parser.add_argument(
        "--change-threshold",
        type=float,
        default=DEFAULT_CHANGE_THRESHOLD,
        help=(
            "Fraction of changed pixels required to count as a slide/scene change. "
            "Range 0-1. Default: "
            f"{DEFAULT_CHANGE_THRESHOLD}."
        ),
    )

    parser.add_argument(
        "--resize-width",
        type=_int_range(16, 10000),
        default=DEFAULT_RESIZE_WIDTH,
        help=(
            "Width used to downscale frames before comparison. Height is scaled "
            "from the first sampled frame and reused. Default: "
            f"{DEFAULT_RESIZE_WIDTH}."
        ),
    )

    parser.add_argument(
        "--confirm-samples",
        type=_int_range(1, 1000),
        default=DEFAULT_CONFIRM_SAMPLES,
        help=(
            "Number of consecutive changed samples required before saving a "
            "screenshot. Higher values reduce false positives but delay capture. "
            f"Default: {DEFAULT_CONFIRM_SAMPLES}."
        ),
    )

    parser.add_argument(
        "--debounce-seconds",
        type=float,
        default=DEFAULT_DEBOUNCE_SECONDS,
        help=(
            "Minimum seconds between saved screenshots. Helps suppress animation/"
            "noise but may suppress legitimate rapid slide changes. Default: "
            f"{DEFAULT_DEBOUNCE_SECONDS}."
        ),
    )

    parser.add_argument(
        "--screenshot-width",
        type=_nonnegative_int,
        default=DEFAULT_SCREENSHOT_WIDTH,
        help=(
            "Maximum saved screenshot width in pixels. 0 keeps original decoded "
            f"frame width. Default: {DEFAULT_SCREENSHOT_WIDTH}."
        ),
    )

    parser.add_argument(
        "--jpeg-quality",
        type=_int_range(1, 100),
        default=DEFAULT_JPEG_QUALITY,
        help=f"JPEG quality for saved screenshots. Default: {DEFAULT_JPEG_QUALITY}.",
    )

    parser.add_argument(
        "--language",
        default=None,
        help=(
            "Optional Whisper language code, e.g. 'en'. Default: automatic spoken "
            "language detection. This does not request translation."
        ),
    )

    parser.add_argument(
        "--device",
        default=None,
        help="Optional Whisper device, e.g. 'cuda' or 'cpu'. Default: automatic.",
    )

    parser.add_argument(
        "--title",
        default=None,
        help="EPUB title. Defaults to the input filename stem.",
    )

    parser.add_argument(
        "--author",
        default=None,
        help="Optional EPUB author metadata.",
    )

    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress progress messages.",
    )

    parser.add_argument(
        "--debug",
        action="store_true",
        help="Show full traceback for unexpected errors.",
    )
    parser.add_argument(
        "--plain-text",
        action="store_true",
        help=(
            "Render transcript as plain prose, separated by spaces, "
            "without visible timestamps. Screenshot captions also omit timestamps."
        ),
    )

    args = parser.parse_args(argv)

    if args.interval_seconds <= 0:
        parser.error("--interval-seconds must be > 0")

    if args.change_threshold < 0 or args.change_threshold > 1:
        parser.error("--change-threshold must be between 0 and 1")

    if args.debounce_seconds < 0:
        parser.error("--debounce-seconds must be >= 0")

    return args